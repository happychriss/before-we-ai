import subprocess
import sys
from pathlib import Path

import json

from before_we_ai.model import (
    Actor,
    EvidenceRecord,
    EvidenceType,
    Predicate,
    ProbeVerdict,
    QuestionCard,
    RoleBindingClaim,
    Scope,
    Source,
    create_claim,
)
from before_we_ai.store import ProjectStore, init_project
from claim_viewer import render_project


def test_render_project_handles_empty_project(tmp_path):
    root = init_project(tmp_path / "empty")
    html = render_project(root)

    assert "No claims yet." in html
    assert "No sources yet." in html
    assert "No integrity findings." in html


def test_render_project_shows_claim_evidence_lineage_and_data(tmp_path):
    root = init_project(tmp_path / "project")
    store = ProjectStore(root)

    source = Source(name="erp", kind="duckdb", location="/tmp/erp.duckdb", fingerprint={"sha256": "abc"})
    store.save_source(source)
    parent = create_claim(
        "Invoices reference orders",
        Actor.AI,
        predicate=Predicate(name="foreign_key", params={"left": "invoice.order_id", "right": "orders.order_id"}),
        source_ids=[source.id],
    )
    store.save_claim(parent)
    probe = EvidenceRecord(
        type=EvidenceType.PROBE_RESULT,
        actor=Actor.PROBE,
        claim_id=parent.id,
        verdict=ProbeVerdict.FAIL,
        population=12,
        exception_count=2,
        exception_samples=[{"invoice_id": "INV-1", "order_id": "missing"}],
        result_ref="cache/probe.parquet",
        source_fingerprints={"erp": "abc"},
    )
    store.add_evidence(probe)
    parent.evidence_ids.append(probe.id)
    parent.status = ProbeVerdict.FAIL  # type: ignore[assignment]
    parent.status = parent.status.CONTRADICTED  # type: ignore[union-attr]
    store.save_claim(parent)

    child = create_claim(
        "Legacy invoices require backfill",
        Actor.HUMAN,
        depends_on=[parent.id],
        source_ids=[source.id],
    ).model_copy(update={"derived_from": parent.id, "derived_from_evidence": probe.id})
    store.save_claim(child)

    binding = RoleBindingClaim(
        statement="Invoice id binds to invoice column",
        created_by=Actor.AI,
        role="invoice_id",
        binding={"table": "erp__invoices", "column": "invoice_id"},
        source_ids=[source.id],
    )
    store.save_claim(binding)

    store.save_question(QuestionCard(question="Which invoices are missing orders?", claim_ids=[parent.id]))
    store.save_profile(
        profile := __import__("before_we_ai.model", fromlist=["ColumnProfile"]).ColumnProfile(
            source_id=source.id,
            table="erp__invoices",
            column="invoice_id",
            stats={"distinct_count": 12, "value_class": "text", "duckdb_type": "VARCHAR"},
        )
    )
    (root / "profiles" / "candidate_matrix.json").write_text(
        json.dumps(
            {
                "threshold": 0.5,
                "pair_cap": 50000,
                "pairs_examined": 1,
                "cap_hit": False,
                "warnings": [],
                "candidates": [
                    {
                        "left": "erp__invoices.invoice_id",
                        "right": "erp__orders.order_id",
                        "overlap": 10,
                        "left_distinct": 12,
                        "right_distinct": 12,
                        "containment": 0.8333,
                        "jaccard": 0.7143,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    declaration = EvidenceRecord(
        type=EvidenceType.DECLARATION,
        actor=Actor.SYSTEM,
        payload={"source": "erp", "table": "erp__invoices", "column": "invoice_id", "rule": "numeric_to_text"},
        source_fingerprints={"erp": "abc"},
    )
    store.add_evidence(declaration)

    html = render_project(root)

    assert "Invoices reference orders" in html
    assert "Conflict is present" in html or "failing probe" in html
    assert f'href="#claim-{parent.id}"' in html
    assert f'id="evidence-{probe.id}"' in html
    assert "Exception samples" in html
    assert "Which invoices are missing orders?" in html
    assert "erp__invoices.invoice_id" in html
    assert "erp__orders.order_id" in html
    assert "Invoice id binds to invoice column" in html
    assert "numeric_to_text" in html


def test_module_cli_writes_output_outside_project_by_default(tmp_path):
    root = init_project(tmp_path / "cli-project")
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-m", "claim_viewer", str(root)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    output = Path(result.stdout.strip())
    assert output == root.parent / f"{root.name}-claim-viewer.html"
    assert output.is_file()
    assert not (root / output.name).exists()
