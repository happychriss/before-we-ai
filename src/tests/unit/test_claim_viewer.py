import subprocess
import sys
from pathlib import Path

import json

from before_we_ai.model import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    Predicate,
    Probe,
    ProbeVerdict,
    QuestionCard,
    RoleBindingClaim,
    Source,
    create_claim,
)
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.model.objects import ColumnProfile
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
    parent = attach_evidence(parent, probe, [])
    assert parent.status is ClaimStatus.CONTRADICTED
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
        profile := ColumnProfile(
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


def test_funnel_counts_the_pipeline_stages(tmp_path):
    root = init_project(tmp_path / "funnel")
    store = ProjectStore(root)

    bound = create_claim(
        "Postings reference invoices",
        Actor.AI,
        predicate=Predicate(
            name="references",
            params={"left": "erp__postings.doc", "right": "erp__invoices.doc"},
        ),
    )
    store.save_claim(bound)
    probe = Probe(template="anti_join", claim_id=bound.id, params={})
    store.save_probe(probe)
    result = EvidenceRecord(
        type=EvidenceType.PROBE_RESULT,
        actor=Actor.PROBE,
        claim_id=bound.id,
        probe_id=probe.id,
        verdict=ProbeVerdict.PASS,
        population=10,
        exception_count=0,
    )
    store.add_evidence(result)
    store.save_claim(attach_evidence(bound, result, []))

    unbound = create_claim(
        "Orders reference customers",
        Actor.AI,
        predicate=Predicate(
            name="references",
            params={"left": "erp__orders.cust", "right": "erp__customers.id"},
        ),
    )
    store.save_claim(unbound)
    # V2 declares why it built no probe — the model's verbatim reason, persisted
    refusal = EvidenceRecord(
        type=EvidenceType.DECLARATION,
        actor=Actor.SYSTEM,
        claim_id=unbound.id,
        payload={
            "decision": "unbindable",
            "reason": "no documented pairs available to populate the template",
        },
    )
    store.add_evidence(refusal)
    store.save_claim(attach_evidence(unbound, refusal, []))

    semantic = create_claim(
        "Betrag means amount",
        Actor.AI,
        predicate=Predicate(
            name="semantic_equivalent",
            params={"left": "erp__postings.betrag", "right": "erp__postings.amount"},
        ),
    )
    store.save_claim(semantic)

    html = render_project(root)

    assert "The funnel" in html
    assert 'data-stage-chip="bound"' in html
    # one claim per stage: bound / unbindable / semantic-only
    assert html.count('data-stage="bound"') == 1
    assert html.count('data-stage="unbindable"') == 1
    assert html.count('data-stage="semantic_only"') == 1
    assert html.count('data-executed="yes"') == 1
    # the refusal is readable where the probe would have been
    assert "no documented pairs available to populate the template" in html
    assert "Never tested" in html
    # the funnel filters on the derived status, not the stored one
    assert 'data-status="tested"' in html


def test_role_elections_show_winner_loser_and_fachfrage(tmp_path):
    root = init_project(tmp_path / "elections")
    store = ProjectStore(root)

    winner = RoleBindingClaim(
        statement="role 'journal' is played by de_erp__gl_postings",
        created_by=Actor.AI,
        role="journal",
        binding={"table": "de_erp__gl_postings"},
    )
    loser = RoleBindingClaim(
        statement="role 'journal' is played by buchungen_report",
        created_by=Actor.AI,
        role="journal",
        binding={"table": "buchungen_report"},
    )
    orphan = RoleBindingClaim(
        statement="role 'intercompany' is played by de_erp__intercompany",
        created_by=Actor.AI,
        role="intercompany",
        binding={"table": "de_erp__intercompany"},
    )
    for claim in (winner, loser, orphan):
        store.save_claim(claim)

    for claim, verdict, exceptions in (
        (winner, ProbeVerdict.PASS, 0),
        (loser, ProbeVerdict.FAIL, 24),
        (orphan, ProbeVerdict.FAIL, 1),
    ):
        template = "balance" if claim is not orphan else "ic_symmetry"
        probe = Probe(template=template, claim_id=claim.id, roles=[claim.role], params={})
        store.save_probe(probe)
        record = EvidenceRecord(
            type=EvidenceType.PROBE_RESULT,
            actor=Actor.PROBE,
            claim_id=claim.id,
            probe_id=probe.id,
            verdict=verdict,
            population=383,
            exception_count=exceptions,
        )
        store.add_evidence(record)
        store.save_claim(attach_evidence(claim, record, []))

    card = QuestionCard(
        question="Für die Rolle 'intercompany' hat keine Bindung ihre Sonde bestanden — welche Quelle führt?",
        claim_ids=[orphan.id],
    )
    store.save_question(card)

    html = render_project(root)

    assert "Role elections" in html
    assert "Elected:" in html
    assert "felled by" in html
    assert "24 exceptions in 383 rows" in html
    assert "finance law" in html  # the domain-law tag of the invariant template
    assert "No winner → Fachfrage" in html
    assert f'href="#question-{card.id}"' in html
    # the Fachfragen inbox lists the open question on top
    assert "Fachfragen — open questions (1)" in html


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
