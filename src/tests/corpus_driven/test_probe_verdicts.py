"""M3 acceptance: probes against handwritten ground-truth claims.

Per the architecture milestone plan: probes run against **handwritten
claims from the ground truth** — expected verdicts for the T1–T6/T11/T12
trap shapes, and **False-Promotion = 0**. All finance knowledge in this
file (accounts, sign conventions, role bindings) is test-side data; the
product package stays domain-agnostic.

Tolerance note: `subledger_equals_gl` runs with the 100k override in
before-ai.yaml — the M0-documented F20 acceptance (unapplied cash makes
AR ≠ GL by ~23k by design).
"""

from pathlib import Path

import pytest
import yaml

from before_we_ai import scan
from before_we_ai.engine import load_tolerances, run_ready
from before_we_ai.model import Actor, ClaimStatus, Probe, ProbeVerdict, create_claim
from before_we_ai.model.objects import RoleBindingClaim
from before_we_ai.sources import open_catalog
from before_we_ai.store import ProjectStore, check_integrity, init_project

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"

SOURCES = [
    {"name": "de_erp", "kind": "duckdb", "location": str(CORPUS / "DE" / "erp.duckdb")},
    {"name": "us_erp", "kind": "duckdb", "location": str(CORPUS / "US" / "erp.duckdb")},
    {"name": "kunden_migration", "kind": "xlsx", "location": str(CORPUS / "kunden_migration.xlsx")},
    {"name": "buchungen_report", "kind": "csv", "location": str(CORPUS / "buchungen_report.csv")},
]

MONTHS_24 = [f"{y}-{m:02d}" for y in (2024, 2025) for m in range(1, 13)]
MONTHS_36 = MONTHS_24 + [f"2026-{m:02d}" for m in range(1, 13)]


def build_ground_truth(store) -> dict[str, str]:
    """Handwritten claims + probes; returns scenario key -> claim id."""
    ids = {}

    def add(key, statement, probes, claim=None):
        claim = claim or create_claim(statement, Actor.AI)
        store.add_claim(claim)
        ids[key] = claim.id
        for template, params in probes:
            store.save_probe(Probe(template=template, claim_id=claim.id, params=params))

    # --- T1: normalization is part of the claim -------------------------
    add("t1_refs", "Offene-Posten-Referenzen zeigen auf Rechnungen", [
        ("anti_join", {"child": "de_erp__ar_open_items", "child_column": "invoice_reference",
                       "parent": "de_erp__invoices", "parent_column": "document_number"}),
    ])
    add("t1_canonical", "Migrationstabelle referenziert Alt-Kundennummern (kanonisch)", [
        ("anti_join", {"child": "kunden_migration__kundenmigration",
                       "child_column": "old_customer_id",
                       "parent": "de_erp__customers", "parent_column": "legacy_id"}),
    ])
    add("t1_raw", "Migrationstabelle referenziert Alt-Kundennummern (roh, ohne Normalisierung)", [
        ("anti_join", {"child": "kunden_migration__kundenmigration",
                       "child_column": "old_customer_id",
                       "parent": "de_erp__customers", "parent_column": "legacy_id",
                       "canonical": False}),
    ])

    # --- T2/K6: legitimate orphans are findings, never failures ---------
    add("k6_orders", "Jeder Auftrag hat eine Rechnung (F1: offene Aufträge)", [
        ("anti_join", {"child": "de_erp__orders", "child_column": "order_id",
                       "parent": "de_erp__invoices", "parent_column": "order_reference",
                       "expectation": "report"}),
    ])
    add("k6_prospects", "Jede CRM-Aktivität gehört zu einem Stammkunden (F13: Interessenten)", [
        ("anti_join", {"child": "de_erp__crm_activities", "child_column": "customer_reference",
                       "parent": "de_erp__customers", "parent_column": "customer_id",
                       "expectation": "report"}),
    ])

    # --- T3 shape: genuine contradiction (F11: name references) ---------
    add("t3_crm_refs", "Jede CRM-Kundenreferenz löst sich im Kundenstamm auf", [
        ("anti_join", {"child": "de_erp__crm_activities", "child_column": "customer_reference",
                       "parent": "de_erp__customers", "parent_column": "customer_id"}),
    ])

    # --- T4 shape: conflicting evidence forces unresolved (F4) ----------
    add("t4_credit_notes", "Erlösschmälerungen leben vollständig in credit_notes_legacy", [
        ("coverage", {"table": "de_erp__credit_notes_legacy", "unit_column": "period",
                      "expected": [f"2024-{m:02d}" for m in range(1, 7)]}),
        ("reconciliation", {
            "left": "de_erp__credit_notes_legacy", "right": "de_erp__invoices",
            "left_group_expr": '"period"', "right_group_expr": '"period"',
            "left_measure_expr": '"amount"', "right_measure_expr": '"amount_local_currency"',
            "right_where": "\"invoice_type\" = 'G'",
        }),
    ])

    # --- T6: the chance overlap must never test green -------------------
    add("t6_negative", "valid_from referenziert orders.order_date (Zufalls-Echo)", [
        ("cardinality", {"child": "de_erp__customer_hierarchy", "child_column": "valid_from",
                         "parent": "de_erp__orders", "parent_column": "order_date"}),
    ])
    add("t6_positive", "Rechnungen referenzieren den Kundenstamm", [
        ("cardinality", {"child": "de_erp__invoices", "child_column": "customer_id",
                         "parent": "de_erp__customers", "parent_column": "customer_id"}),
    ])

    # --- T11: genuine duplicates fail the key claim ---------------------
    add("t11_duplicates", "Kundenstamm ist eindeutig über (Name, PLZ)", [
        ("duplicate", {"table": "de_erp__customers",
                       "key_columns": ["customer_name", "postal_code"]}),
    ])

    # --- T12: partial coverage is a finding, not an error ---------------
    add("t12_gl", "Hauptbuch deckt alle 24 Monate", [
        ("coverage", {"table": "de_erp__gl_postings", "unit_column": "period",
                      "expected": MONTHS_24}),
    ])
    add("t12_plan", "Plan deckt 2024–2026 (Ist endet früher)", [
        ("coverage", {"table": "de_erp__plan", "unit_column": "plan_month",
                      "expected": MONTHS_36}),
    ])

    # --- K4: templates the corpus forces ---------------------------------
    add("k4_validity", "Kundenhierarchie ist überschneidungsfrei versioniert (F6)", [
        ("validity_join", {"table": "de_erp__customer_hierarchy", "key_column": "customer_id",
                           "valid_from": "valid_from", "valid_to": "valid_to"}),
    ])
    add("k4_range", "Externe Kunden-PLZ fallen in genau ein Gebiet (F9)", [
        ("range_join", {"table": "de_erp__customers", "value_column": "postal_code",
                        "ranges": "de_erp__territory_plz",
                        "range_from": "plz_from", "range_to": "plz_to",
                        "where": '"customer_id" < 90000'}),  # scope: external customers
    ])
    add("k4_decode", "Hierarchie-String decodiert positionsweise eindeutig (F7)", [
        ("decode", {"encoded": "de_erp__materials", "decode": "de_erp__material_hierarchy",
                    "key": "material_id", "column": "product_hierarchy_string",
                    "pairs": [
                        {"part_expr": "split_part(e.\"product_hierarchy_string\", ' ', 1)",
                         "decode_column": "hierarchy_level_1"},
                        {"part_expr": "split_part(e.\"product_hierarchy_string\", ' ', 2)",
                         "decode_column": "hierarchy_level_2"},
                        {"part_expr": "split_part(e.\"product_hierarchy_string\", ' ', 3)",
                         "decode_column": "hierarchy_level_3"},
                    ]}),
    ])

    # --- F5 continuity: attribute agreement across the migration --------
    add("f5_continuity", "Migrierte Kunden behalten Name über den Nummernwechsel", [
        ("attribute_contradiction", {
            "left": "de_erp__customers", "right": "de_erp__customers",
            "left_key": "legacy_id", "right_key": "customer_id",
            "left_attr": "customer_name", "right_attr": "customer_name"}),
    ])

    # --- Invariants against role bindings (K5) ---------------------------
    binding_gl = RoleBindingClaim(
        statement="Rolle journal = de_erp__gl_postings", created_by=Actor.AI,
        role="journal",
        binding={"table": "de_erp__gl_postings", "amount_local": "amount_local_currency",
                 "doc_ref": "document_reference", "account": "account_id",
                 "period": "period"},
    )
    add("binding_gl", None, [
        ("balance", {"journal": "de_erp__gl_postings", "amount": "amount_local_currency",
                     "group_column": "document_reference"}),
    ], claim=binding_gl)

    binding_report = RoleBindingClaim(
        statement="Rolle journal = buchungen_report (verführerisch, falsch — F27)",
        created_by=Actor.AI, role="journal",
        binding={"table": "buchungen_report__buchungen_report", "amount_local": "betrag_eur",
                 "doc_ref": "buchung_id", "period": "period"},
    )
    add("binding_report", None, [
        ("balance", {"journal": "buchungen_report__buchungen_report",
                     "amount": "betrag_eur", "group_column": "buchung_id"}),
    ], claim=binding_report)

    add("f22_us_balance", "US-Journal ist je Beleg ausgeglichen (Z4-Invariante)", [
        ("balance", {"journal": "us_erp__gl_postings", "amount": "amount_local_currency",
                     "group_column": "document_reference"}),
    ])
    add("f22_ic_symmetry", "Intercompany-Buchungen DE↔US sind symmetrisch", [
        ("ic_symmetry", {"left": "de_erp__intercompany", "right": "us_erp__intercompany",
                         "left_period": "period", "right_period": "period"}),
    ])
    add("f20_subledger", "Nebenbuch AR = Hauptbuch Konto 1200 (mit dokumentierter Toleranz)", [
        ("subledger_equals_gl", {
            "subledger": "de_erp__ar_open_items", "subledger_amount": "amount",
            "journal": "de_erp__gl_postings", "journal_amount": "amount_local_currency",
            "account": "account_id", "accounts": [1200]}),
    ])
    add("f27_reconciliation", "Report stimmt je Periode×Konto mit dem Hauptbuch überein", [
        ("reconciliation", {
            "left": "buchungen_report__buchungen_report", "right": "de_erp__gl_postings",
            "left_group_expr": "\"period\" || '|' || \"konto\"",
            "right_group_expr": "\"period\" || '|' || CAST(\"account_id\" AS VARCHAR)",
            "left_measure_expr": ("CASE WHEN \"s_h_indicator\" = 'H' "
                                  "THEN -TRY_CAST(\"betrag_eur\" AS DOUBLE) "
                                  "ELSE TRY_CAST(\"betrag_eur\" AS DOUBLE) END"),
            "right_measure_expr": '"amount_local_currency"',
            "left_where": "\"journal\" = 'DE'"}),
    ])
    return ids


EXPECTED_TESTED = {
    "t1_refs", "t1_canonical", "t6_positive", "t12_gl", "k4_validity", "k4_range",
    "k4_decode", "f5_continuity", "binding_gl", "f20_subledger", "f27_reconciliation",
}
EXPECTED_CONTRADICTED = {
    "t1_raw", "t3_crm_refs", "t6_negative", "t11_duplicates",
    "binding_report", "f22_us_balance", "f22_ic_symmetry",
}
EXPECTED_INFERRED = {"k6_orders", "k6_prospects", "t12_plan"}
EXPECTED_UNRESOLVED = {"t4_credit_notes"}


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    root = init_project(tmp_path_factory.mktemp("probes") / "corpus-probes", name="corpus-probes")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = SOURCES
    # F20: documented M0 acceptance — unapplied cash keeps AR ≠ GL by design.
    config["tolerances"] = {"subledger_equals_gl": {"absolute": 100_000}}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    scan(root)

    store = ProjectStore(root)
    ids = build_ground_truth(store)
    con = open_catalog(root)
    try:
        report = run_ready(store, con, load_tolerances(root))
    finally:
        con.close()
    return root, ProjectStore(root), ids, report  # reload: persistence is part of the claim


def status_of(store, ids, key):
    return store.claims[ids[key]].status


def test_all_probes_ran(run):
    _, store, ids, report = run
    assert report.skipped == []
    assert len(report.executed) == len(store.probes)
    assert check_integrity(store) == []


def test_t1_normalization_is_part_of_the_claim(run):
    _, store, ids, _ = run
    assert status_of(store, ids, "t1_refs") is ClaimStatus.TESTED
    assert status_of(store, ids, "t1_canonical") is ClaimStatus.TESTED
    # Without the declared normalization the very same relationship fails.
    assert status_of(store, ids, "t1_raw") is ClaimStatus.CONTRADICTED


def test_k6_orphans_are_questions_not_failures(run):
    _, store, ids, _ = run
    for key in ("k6_orders", "k6_prospects"):
        claim = store.claims[ids[key]]
        assert claim.status is ClaimStatus.INFERRED
        verdicts = [store.evidence[e].verdict for e in claim.evidence_ids]
        assert verdicts == [ProbeVerdict.INCONCLUSIVE]
    questions = [q.question for q in store.questions.values()]
    assert any("de_erp__orders" in q for q in questions)


def test_contradiction_is_loud(run):
    _, store, ids, _ = run
    assert status_of(store, ids, "t3_crm_refs") is ClaimStatus.CONTRADICTED
    assert status_of(store, ids, "t11_duplicates") is ClaimStatus.CONTRADICTED


def test_t4_conflict_forces_unresolved(run):
    _, store, ids, _ = run
    claim = store.claims[ids["t4_credit_notes"]]
    assert claim.status is ClaimStatus.UNRESOLVED
    verdicts = {store.evidence[e].verdict for e in claim.evidence_ids}
    assert verdicts == {ProbeVerdict.PASS, ProbeVerdict.FAIL}


def test_t6_chance_overlap_never_tests_green(run):
    _, store, ids, _ = run
    assert status_of(store, ids, "t6_negative") is ClaimStatus.CONTRADICTED
    assert status_of(store, ids, "t6_positive") is ClaimStatus.TESTED


def test_t12_partial_coverage_is_a_finding(run):
    _, store, ids, _ = run
    assert status_of(store, ids, "t12_gl") is ClaimStatus.TESTED
    plan = store.claims[ids["t12_plan"]]
    assert plan.status is ClaimStatus.INFERRED
    record = store.evidence[plan.evidence_ids[0]]
    assert record.verdict is ProbeVerdict.INCONCLUSIVE
    assert record.exception_count == 12  # the twelve 2026 months


def test_invariants_find_exactly_the_seeded_break(run):
    _, store, ids, _ = run
    # F22: the deliberate IC break — found, localized, loud.
    us = store.claims[ids["f22_us_balance"]]
    assert us.status is ClaimStatus.CONTRADICTED
    record = store.evidence[us.evidence_ids[0]]
    assert record.exception_count == 1
    assert record.exception_samples[0]["grp"] == "IC-2024-06"
    assert float(record.exception_samples[0]["balance"]) == pytest.approx(50_000.0)

    ic = store.claims[ids["f22_ic_symmetry"]]
    assert ic.status is ClaimStatus.CONTRADICTED
    ic_record = store.evidence[ic.evidence_ids[0]]
    assert [s["period"] for s in ic_record.exception_samples] == ["2024-06"]


def test_f27_role_binding_decided_by_invariant(run):
    _, store, ids, _ = run
    assert status_of(store, ids, "binding_gl") is ClaimStatus.TESTED
    report_binding = store.claims[ids["binding_report"]]
    assert report_binding.status is ClaimStatus.CONTRADICTED
    # …with a documented reason: the rendered SQL sits on the evidence.
    record = store.evidence[report_binding.evidence_ids[0]]
    assert "buchungen_report" in record.payload["sql"]
    # The report itself stays valuable as a secondary source: it reconciles.
    assert status_of(store, ids, "f27_reconciliation") is ClaimStatus.TESTED


def test_f20_documented_tolerance(run):
    _, store, ids, _ = run
    assert status_of(store, ids, "f20_subledger") is ClaimStatus.TESTED


def test_false_promotion_rate_is_zero(run):
    _, store, ids, _ = run
    key_by_id = {v: k for k, v in ids.items()}
    promoted = {
        key_by_id[c.id]
        for c in store.claims.values()
        if c.status in (ClaimStatus.TESTED, ClaimStatus.BUSINESS_CONFIRMED)
    }
    assert promoted == EXPECTED_TESTED  # nothing extra, nothing missing
    for key, expected in [
        *[(k, ClaimStatus.CONTRADICTED) for k in EXPECTED_CONTRADICTED],
        *[(k, ClaimStatus.INFERRED) for k in EXPECTED_INFERRED],
        *[(k, ClaimStatus.UNRESOLVED) for k in EXPECTED_UNRESOLVED],
    ]:
        assert status_of(store, ids, key) is expected, key
