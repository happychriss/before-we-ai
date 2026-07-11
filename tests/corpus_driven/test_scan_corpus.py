"""M2 acceptance against the frozen corpus (m0-corpus-v1).

Per the architecture milestone plan: **T1/T9 survive normalization, the
candidate matrix contains all value-based seeds including the negative
control (T6).** Corpus paths appear only here, on the test side — the
product package stays domain-agnostic.

Trap mapping onto the finance corpus:

* T1 — zero-padded text keys (``invoices.document_number`` and the
  references pointing at it) must survive ingestion untouched.
* T9 — ``kunden_migration.xlsx`` stores IDs as numbers and dates as Excel
  datetimes; the pre-reader must normalize with declared decisions.
* T6 — chance value overlap: ``customer_hierarchy.valid_from`` ↔
  ``orders.order_date`` are semantically unrelated, yet overlap fully.
  The matrix must *contain* it — measurement doesn't editorialize; the
  false-positive path is closed later (M3), and M2 can promote nothing
  because it creates no claims at all.
"""

import json
import shutil
from pathlib import Path

import duckdb
import pytest
import yaml

from before_we_ai import scan
from before_we_ai.model import EvidenceType
from before_we_ai.sources import build_catalog, file_fingerprint
from before_we_ai.scan import load_specs
from before_we_ai.store import ProjectStore, check_integrity, init_project

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"

SOURCES = [
    {"name": "de_erp", "kind": "duckdb", "location": str(CORPUS / "DE" / "erp.duckdb")},
    {"name": "us_erp", "kind": "duckdb", "location": str(CORPUS / "US" / "erp.duckdb")},
    {"name": "kunden_migration", "kind": "xlsx", "location": str(CORPUS / "kunden_migration.xlsx")},
    {"name": "marketing_grouping", "kind": "xlsx", "location": str(CORPUS / "marketing_grouping.xlsx")},
    {"name": "kontakte_aussendienst", "kind": "xlsx",
     "location": str(CORPUS / "kontakte_aussendienst.xlsx")},
    {"name": "buchungen_report", "kind": "csv", "location": str(CORPUS / "buchungen_report.csv")},
    {"name": "management_report", "kind": "pdf", "location": str(CORPUS / "management_report.pdf")},
]

# The value-based seed relationships the ground truth builds in — every
# one of these MUST surface in the candidate matrix. (Intercompany's
# customer_id/account_id columns hold a single distinct value each — one
# IC partner per entity — and sit below the cardinality floor, so their
# relationships are not value-matrix material.)
VALUE_BASED_SEEDS = [
    ("de_erp__invoices.customer_id", "de_erp__customers.customer_id"),
    ("de_erp__invoices.order_reference", "de_erp__orders.order_id"),
    ("de_erp__invoice_items.invoice_id", "de_erp__invoices.document_number"),
    ("de_erp__ar_open_items.invoice_reference", "de_erp__invoices.document_number"),  # T1
    ("de_erp__credit_notes_legacy.invoice_reference", "de_erp__invoices.document_number"),  # F4
    ("de_erp__gl_postings.account_id", "de_erp__chart_of_accounts.account_id"),
    ("de_erp__gl_postings.document_reference", "de_erp__invoices.document_number"),
    ("de_erp__customer_hierarchy.customer_id", "de_erp__customers.customer_id"),
    ("de_erp__crm_activities.rep_id", "de_erp__sales_reps.rep_id"),
    ("de_erp__sales_reps.territory_id", "de_erp__territory_plz.territory_id"),
    # F5: the migration mapping exists ONLY in the xlsx — cross-format,
    # discoverable solely through canonicalization (Excel number vs
    # BIGINT vs DOUBLE legacy_id).
    ("kunden_migration__kundenmigration.old_customer_id", "de_erp__customers.legacy_id"),
    ("kunden_migration__kundenmigration.new_customer_id", "de_erp__customers.customer_id"),
    ("marketing_grouping__produktgruppen_marketing.material_id", "de_erp__materials.material_id"),
    ("kontakte_aussendienst__aussendienst_kontakte.rep_id", "de_erp__sales_reps.rep_id"),
    # F27 decoy: the aggregated report must be *connected*, so that its
    # seductive (and wrong) role binding can lose against gl_postings in M3.
    ("buchungen_report__buchungen_report.konto", "de_erp__chart_of_accounts.account_id"),
    # And the US entity mirrors the core chain.
    ("us_erp__invoices.customer_id", "us_erp__customers.customer_id"),
    ("us_erp__gl_postings.account_id", "us_erp__chart_of_accounts.account_id"),
]

NEGATIVE_CONTROL = ("de_erp__customer_hierarchy.valid_from", "de_erp__orders.order_date")


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    root = init_project(tmp_path_factory.mktemp("scan") / "corpus-scan", name="corpus-scan")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = SOURCES
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    result = scan(root)
    return root, result


def matrix_pairs(root):
    matrix = json.loads((root / "profiles" / "candidate_matrix.json").read_text(encoding="utf-8"))
    return matrix, {(c["left"], c["right"]): c for c in matrix["candidates"]}


def test_scan_covers_the_whole_corpus(project):
    root, result = project
    assert len(result.source_ids) == 7
    assert len(result.views) == 48  # 2 × 22 ERP tables + 3 sheets + 1 csv
    assert result.profiles_written > 200
    assert result.warnings == []


def test_t1_leading_zeros_survive_ingestion(project):
    root, _ = project
    con = duckdb.connect()
    build_catalog(root, load_specs(root), con)
    numbers = [r[0] for r in con.execute(
        "SELECT document_number FROM de_erp__invoices LIMIT 100"
    ).fetchall()]
    con.close()
    assert all(isinstance(n, str) and n.startswith("DE-INV-0") for n in numbers)

    _, pairs = matrix_pairs(root)
    hit = pairs[("de_erp__ar_open_items.invoice_reference", "de_erp__invoices.document_number")]
    assert hit["containment"] == 1.0


def test_t9_excel_dirt_survives_with_declared_decisions(project):
    root, _ = project
    parquet = root / "cache" / "normalized" / "kunden_migration__kundenmigration.parquet"
    con = duckdb.connect()
    rows = con.execute(
        f"SELECT old_customer_id, new_customer_id, migration_date FROM '{parquet}' "
        "ORDER BY old_customer_id"
    ).fetchall()
    con.close()
    assert rows[0] == ("1101", "1201", "2025-01-15")  # text, no '.0', ISO date
    assert all(isinstance(v, str) for row in rows for v in row)

    store = ProjectStore(root)
    declarations = [
        e for e in store.evidence.values()
        if e.type is EvidenceType.DECLARATION and e.payload.get("source") == "kunden_migration"
    ]
    rules = {(d.payload["column"], d.payload["rule"]) for d in declarations}
    assert ("old_customer_id", "numeric_to_text") in rules
    assert ("migration_date", "date_to_iso") in rules
    sha = file_fingerprint(CORPUS / "kunden_migration.xlsx")["sha256"]
    assert all(d.source_fingerprints == {"kunden_migration": sha} for d in declarations)


def test_all_value_based_seeds_are_in_the_matrix(project):
    root, _ = project
    _, pairs = matrix_pairs(root)
    missing = [
        seed for seed in VALUE_BASED_SEEDS if tuple(sorted(seed)) not in pairs
    ]
    assert missing == []


def test_negative_control_is_in_and_nothing_is_promoted(project):
    root, _ = project
    _, pairs = matrix_pairs(root)
    # The chance overlap IS reported — the matrix measures, it does not judge…
    assert tuple(sorted(NEGATIVE_CONTROL)) in pairs
    # …and no candidate carries any status: scanning created zero claims,
    # so a false promotion is structurally impossible in this phase.
    assert list((root / "claims").glob("*.yaml")) == []
    assert ProjectStore(root).claims == {}


def test_k4_blindness_is_honest(project):
    # F7 (positional hierarchy string) and F9 (PLZ BETWEEN ranges) are
    # NOT equality overlaps — the matrix must not pretend to see them.
    # Their recall belongs to V1 (M4) / the range_join & decode probes.
    root, _ = project
    matrix, _ = matrix_pairs(root)
    for c in matrix["candidates"]:
        pair = {c["left"], c["right"]}
        # F7: the encoded string never equality-matches the decoder table.
        # (The same column matching itself across entities is fine.)
        assert not (
            any("product_hierarchy_string" in p for p in pair)
            and any("material_hierarchy" in p for p in pair)
        )
        # F9: postal codes never equality-match the PLZ range bounds.
        assert not (
            any("postal_code" in p for p in pair) and any("plz_" in p for p in pair)
        )


def test_cache_is_disposable_and_scan_idempotent(project):
    root, _ = project
    before_matrix = (root / "profiles" / "candidate_matrix.json").read_text(encoding="utf-8")
    before_profiles = {
        p.id: p.stats for p in ProjectStore(root).profiles.values()
    }
    n_evidence = len(list((root / "evidence").glob("*.yaml")))

    shutil.rmtree(root / "cache")
    result = scan(root)

    assert (root / "profiles" / "candidate_matrix.json").read_text(encoding="utf-8") == before_matrix
    after_profiles = {p.id: p.stats for p in ProjectStore(root).profiles.values()}
    assert after_profiles == before_profiles  # same IDs, same stats — no drift
    assert result.declarations_added == 0  # same fingerprints, nothing new to declare
    assert len(list((root / "evidence").glob("*.yaml"))) == n_evidence


def test_integrity_after_scan(project):
    root, _ = project
    assert check_integrity(ProjectStore(root)) == []
