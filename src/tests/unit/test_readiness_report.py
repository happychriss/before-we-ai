import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

import json

import yaml

import pytest

from before_we_ai.core import (
    Actor,
    AnswerRequest,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    Predicate,
    CheckPlan,
    CheckVerdict,
    ClarificationQuestion,
    ConceptClaim,
    KnowledgeItem,
    KnowledgeKind,
    MappingClaim,
    RequiredKnowledge,
    Scope,
    Source,
    create_claim,
)
from before_we_ai.core.transitions import attach_evidence
from before_we_ai.core.objects import DataProfile
from before_we_ai.checks.library import REGISTRY
from before_we_ai.stages import BOUNDARY_TEXT, STAGES
from before_we_ai.llm.domain_guide import load_domain_guide
from before_we_ai.readiness import confirm_classification, link_claim
from before_we_ai.store import ProjectStore, init_project
from readiness_report import render_project
from readiness_report.projection import load_view_model

pytestmark = pytest.mark.integration


def _rich_text(value):
    return "".join(part.text for part in value.parts)


def _stage(view, name):
    return next(stage for stage in view.stages if stage.name == name)


def _claim(view, claim_id):
    return next(claim for claim in view.claims if claim.index.id == claim_id)


def _outcome_text(election):
    return tuple((css, _rich_text(text)) for css, text in election.outcome.paragraphs)


class _DocumentLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.urls = []
        self.fragments = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        for name in ("href", "src"):
            value = values.get(name)
            if not value:
                continue
            self.urls.append(value)
            if value.startswith("#") and len(value) > 1:
                self.fragments.add(value[1:])


def _document(html):
    document = _DocumentLinks()
    document.feed(html)
    return document


def test_view_model_handles_empty_project(tmp_path):
    root = init_project(tmp_path / "empty")
    view = load_view_model(root)

    assert view.funnel.empty == "No claims yet."
    assert view.measurement.source_count == 0
    assert view.measurement.sources == ()
    assert view.integrity == ()


def test_view_model_shows_claim_evidence_lineage_and_data(tmp_path):
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
    check = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT,
        actor=Actor.CHECK,
        claim_id=parent.id,
        verdict=CheckVerdict.FAIL,
        population=12,
        exception_count=2,
        exception_samples=[{"invoice_id": "INV-1", "order_id": "missing"}],
        result_ref="cache/check.parquet",
        source_fingerprints={"erp": "abc"},
    )
    store.add_evidence(check)
    parent = attach_evidence(parent, check, [])
    assert parent.status is ClaimStatus.CONTRADICTED
    store.save_claim(parent)

    child = create_claim(
        "Legacy invoices require backfill",
        Actor.HUMAN,
        depends_on=[parent.id],
        source_ids=[source.id],
    ).model_copy(update={"derived_from": parent.id, "derived_from_evidence": check.id})
    store.save_claim(child)

    binding = MappingClaim(
        statement="Invoice id binds to invoice column",
        created_by=Actor.AI,
        role="invoice_id",
        binding={"table": "erp__invoices", "column": "invoice_id"},
        source_ids=[source.id],
    )
    store.save_claim(binding)

    store.save_question(ClarificationQuestion(question="Which invoices are missing orders?", claim_ids=[parent.id]))
    store.save_profile(
        profile := DataProfile(
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

    view = load_view_model(root)
    parent_view = _claim(view, parent.id)
    child_view = _claim(view, child.id)
    binding_view = _claim(view, binding.id)
    evidence_view = next(item for item in parent_view.evidence if item.id == check.id)
    question = next(
        item for item in view.open_questions
        if item.question == "Which invoices are missing orders?"
    )
    column = view.measurement.sources[0].tables[0].columns[0]

    assert parent_view.index.title == "Invoices reference orders"
    assert parent_view.index.derived_status == "contradicted"
    assert "failing check" in parent_view.headline
    assert child_view.lineage.parent.reference.id == parent.id
    assert child_view.lineage.evidence.reference.id == check.id
    assert evidence_view.sample_headers == ("invoice_id", "order_id")
    assert evidence_view.sample_rows == (("INV-1", "missing"),)
    assert question.id in {item.id for item in view.open_questions}
    assert column.key == "erp__invoices.invoice_id"
    assert [(item.other, item.overlap) for item in column.candidates] == [
        ("erp__orders.order_id", "10")
    ]
    assert binding_view.index.title == (
        "'invoice_id' is played by erp__invoices.invoice_id"
    )
    assert binding_view.statement == "Invoice id binds to invoice column"
    assert any("numeric_to_text" in item.payload for item in column.declarations)


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
    check = CheckPlan(template="anti_join", claim_id=bound.id, params={})
    store.save_check_plan(check)
    result = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT,
        actor=Actor.CHECK,
        claim_id=bound.id,
        check_plan_id=check.id,
        verdict=CheckVerdict.PASS,
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
    # V2 declares why it built no check — the model's verbatim reason, persisted
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

    view = load_view_model(root)
    claims = {claim.statement: claim for claim in view.claims}
    chips = {
        chip.stage: chip
        for stage in view.funnel.stages
        for chip in stage.chips
        if chip.stage
    }

    assert _stage(view, "proposed").label == "3 · proposed"
    assert chips["bound"].count == 1
    assert chips["unbindable"].count == 1
    assert chips["semantic_only"].count == 1
    assert chips["executed"].count == 1
    assert claims["Orders reference customers"].no_check.reason == (
        "no documented pairs available to populate the template"
    )
    assert claims["Betrag means amount"].headline.startswith("Never tested")
    assert claims["Postings reference invoices"].index.derived_status == "test-supported"


def test_role_elections_show_winner_loser_and_clarification(tmp_path):
    root = init_project(tmp_path / "elections")
    store = ProjectStore(root)

    winner = MappingClaim(
        statement="role 'journal' is played by de_erp__gl_postings",
        created_by=Actor.AI,
        role="journal",
        binding={"table": "de_erp__gl_postings"},
    )
    loser = MappingClaim(
        statement="role 'journal' is played by buchungen_report",
        created_by=Actor.AI,
        role="journal",
        binding={"table": "buchungen_report"},
    )
    orphan = MappingClaim(
        statement="role 'intercompany' is played by de_erp__intercompany",
        created_by=Actor.AI,
        role="intercompany",
        binding={"table": "de_erp__intercompany"},
    )
    for claim in (winner, loser, orphan):
        store.save_claim(claim)

    for claim, verdict, exceptions in (
        (winner, CheckVerdict.PASS, 0),
        (loser, CheckVerdict.FAIL, 24),
        (orphan, CheckVerdict.FAIL, 1),
    ):
        template = "balance" if claim is not orphan else "ic_symmetry"
        check = CheckPlan(template=template, claim_id=claim.id, roles=[claim.role], params={})
        store.save_check_plan(check)
        record = EvidenceRecord(
            type=EvidenceType.CHECK_RESULT,
            actor=Actor.CHECK,
            claim_id=claim.id,
            check_plan_id=check.id,
            verdict=verdict,
            population=383,
            exception_count=exceptions,
        )
        store.add_evidence(record)
        store.save_claim(attach_evidence(claim, record, []))

    card = ClarificationQuestion(
        question="No binding for the 'intercompany' role passed its check — which source leads?",
        claim_ids=[orphan.id],
    )
    store.save_question(card)

    view = load_view_model(root)
    journal = next(item for item in view.elections if item.role == "journal")
    intercompany = next(item for item in view.elections if item.role == "intercompany")
    journal_outcome = " ".join(text for _, text in _outcome_text(journal))
    loser_reasons = [
        _rich_text(reason)
        for candidate in journal.candidates
        if candidate.css == "loser"
        for reason in candidate.reasons
    ]
    intercompany_outcome = " ".join(text for _, text in _outcome_text(intercompany))

    assert _stage(view, "tested").title == "The checks judge"
    assert "Identified. The balance law passed on" in journal_outcome
    assert "felled" in journal_outcome
    assert any("24 exceptions in 383 rows" in reason for reason in loser_reasons)
    assert any("finance law" in reason for reason in loser_reasons)
    assert "Open — a human has to answer it." in intercompany_outcome
    assert any(
        part.reference and part.reference.id == card.id
        for _, paragraph in intercompany.outcome.paragraphs
        for part in paragraph.parts
    )
    assert _stage(view, "clarification").counts == (("1", "open question"),)


def test_the_process_diagram_carries_this_project_s_live_numbers(tmp_path):
    """The diagram is the map into the page: every stage links to its section,
    every number is counted from the store, and the actor boundary is drawn
    where authorship shifts — a proposal can never promote itself."""
    root = init_project(tmp_path / "diagram")
    store = ProjectStore(root)

    guide_file = tmp_path / "guide.yaml"
    guide_file.write_text(
        "domain: finance\n"
        "objects:\n"
        "  journal:\n"
        "    decided_by: balance\n"
        "    definition: The ledger of record.\n"
        "    fields:\n"
        "      amount_local:\n"
        "        decided_by: slot\n"
        "        fills: amount\n"
        "        definition: The signed posting amount.\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["sources"] = [
        {"name": "de_erp", "kind": "duckdb", "location": "/data/DE/erp.duckdb"}
    ]
    config["llm"] = {"domain_guide_file": str(guide_file)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    source = Source(name="de_erp", kind="duckdb", location="/data/DE/erp.duckdb")
    store.save_source(source)
    store.save_profile(
        DataProfile(source_id=source.id, table="gl_postings", column="amount", stats={})
    )

    elected = MappingClaim(
        statement="role 'journal' is played by de_erp__gl_postings",
        created_by=Actor.AI,
        role="journal",
        binding={"table": "de_erp__gl_postings"},
    )
    beaten = MappingClaim(
        statement="role 'intercompany' is played by de_erp__intercompany",
        created_by=Actor.AI,
        role="intercompany",
        binding={"table": "de_erp__intercompany"},
    )
    for claim, verdict in ((elected, CheckVerdict.PASS), (beaten, CheckVerdict.FAIL)):
        store.save_claim(claim)
        check = CheckPlan(template="balance", claim_id=claim.id, roles=[claim.role], params={})
        store.save_check_plan(check)
        record = EvidenceRecord(
            type=EvidenceType.CHECK_RESULT,
            actor=Actor.CHECK,
            claim_id=claim.id,
            check_plan_id=check.id,
            verdict=verdict,
            population=383,
            exception_count=0 if verdict is CheckVerdict.PASS else 24,
        )
        store.add_evidence(record)
        store.save_claim(attach_evidence(claim, record, []))
    store.save_question(
        ClarificationQuestion(question="Which source leads?", claim_ids=[beaten.id])
    )

    view = load_view_model(root)

    assert [(stage.name, stage.actor) for stage in view.stages] == [
        (stage.name, stage.actor) for stage in STAGES
    ]
    assert [stage.boundary_before for stage in view.stages if stage.boundary_before] == [
        BOUNDARY_TEXT
    ]
    laws = sum(1 for spec in REGISTRY.values() if spec.domain)
    assert _stage(view, "inputs").counts == (
        ("1", "source"),
        ("1+1", "objects + fields"),
        (str(laws), "domain laws"),
    )
    assert _stage(view, "measured").counts[0] == ("1", "column profiles")
    assert _stage(view, "proposed").counts == (("2", "claims"),)
    assert _stage(view, "tested").counts == (
        ("2", "check runs"),
        ("1/2", "elections settled"),
    )
    assert _stage(view, "clarification").counts == (("1", "open question"),)
    assert _stage(view, "readiness").counts == (("—", "no question asked"),)
    # No longer a ghost: M5 built it, and the diagram says what it does
    # rather than that it is missing.
    ghost = _rich_text(view.copy.process_ghost)
    assert ghost.startswith("Documents — ")
    assert "not built" not in ghost


def test_question_view_model_lists_candidates_and_technical_refs(tmp_path):
    """The owner's complaint, pinned: no wall of prose, and ids folded away.

    Whether the list is a *choice* comes from the guide, not from the
    question's wording — a clarification-decided role is picked; a role whose
    law could never be applied is asking for knowledge instead.
    """
    root = init_project(tmp_path / "picks")
    guide = tmp_path / "guide.yaml"
    guide.write_text(
        "domain: finance\n"
        "objects:\n"
        "  journal:\n"
        "    decided_by: balance\n"
        "    definition: The ledger of record.\n"
        "    fields:\n"
        "      doc_ref:\n"
        "        decided_by: clarification\n"
        "        definition: The document reference.\n"
        "  subledger_ar:\n"
        "    decided_by: subledger_equals_gl\n"
        "    definition: The open receivables.\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["llm"] = {"domain_guide_file": str(guide)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    store = ProjectStore(root)
    picks, unbound = [], []
    for role, table, column, bucket in (
        ("doc_ref", "de_erp__gl_postings", "document_reference", picks),
        ("doc_ref", "buchungen_report", "buchung_id", picks),
        ("subledger_ar", "de_erp__ar_open_items", "", unbound),
        ("subledger_ar", "us_erp__ar_open_items", "", unbound),
    ):
        binding = {"table": table} | ({role: f"{table}.{column}"} if column else {})
        claim = MappingClaim(
            statement=f"role '{role}' is played by " + ", ".join(
                f"{k}={v}" for k, v in sorted(binding.items())
            ),
            created_by=Actor.AI, role=role, binding=binding,
        )
        store.save_claim(claim)
        bucket.append(claim)
    store.save_question(ClarificationQuestion(
        question="Which of the proposed candidates is the 'doc_ref'? The document reference.",
        claim_ids=[c.id for c in picks],
    ))
    store.save_question(ClarificationQuestion(
        question="What is missing before the 'subledger_ar' can be tested? The open receivables.",
        claim_ids=[c.id for c in unbound],
    ))

    view = load_view_model(root)
    by_question = {item.question: item for item in view.open_questions}
    picked = by_question[
        "Which of the proposed candidates is the 'doc_ref'? The document reference."
    ]
    missing = by_question[
        "What is missing before the 'subledger_ar' can be tested? The open receivables."
    ]

    assert picked.lead == "Pick one — 2 candidates were proposed:"
    assert "no law could be applied to any of them" in missing.lead
    assert [item.binding for item in picked.options] == [
        "buchungen_report.buchung_id",
        "de_erp__gl_postings.document_reference",
    ]
    assert "'doc_ref' is played by de_erp__gl_postings.document_reference" in {
        claim.index.title for claim in view.claims
    }
    assert dict(picked.details)["id"] == picked.id
    assert picked.provenance.reference.kind == "questions"
    assert picked.provenance.reference.id == picked.id


def test_view_model_keeps_three_voices_separate(tmp_path):
    """Derived sentences headline; the AI is quoted and attributed; the
    human's words are verbatim. A model's prose may never headline a status."""
    root = init_project(tmp_path / "voices")
    store = ProjectStore(root)

    claim = create_claim(
        "Postings reference invoices",
        Actor.AI,
        predicate=Predicate(
            name="references",
            params={"left": "erp__postings.doc", "right": "erp__invoices.doc"},
        ),
    )
    store.save_claim(claim)
    check = CheckPlan(template="anti_join", claim_id=claim.id, params={})
    store.save_check_plan(check)
    failed = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK, claim_id=claim.id,
        check_plan_id=check.id, verdict=CheckVerdict.FAIL,
        population=400, exception_count=8,
    )
    store.add_evidence(failed)
    said = EvidenceRecord(
        type=EvidenceType.TESTIMONIAL, actor=Actor.HUMAN, claim_id=claim.id,
        statement="Postings from the legacy migration never got an invoice.",
    )
    store.add_evidence(said)
    claim = attach_evidence(claim, failed, [])
    store.save_claim(attach_evidence(claim, said, [failed]))

    view = load_view_model(root)
    claim_view = _claim(view, claim.id)
    failed_view = next(item for item in claim_view.evidence if item.id == failed.id)
    said_view = next(item for item in claim_view.evidence if item.id == said.id)

    assert failed_view.sentence == (
        "The check refuted the claim: 8 exceptions in 400 rows (2.00% of the rows)."
    )
    assert _rich_text(claim_view.proposal.cite).endswith(
        "wrote it, verbatim; a proposal, not a finding"
    )
    assert said_view.voice.text == (
        "Postings from the legacy migration never got an invoice."
    )
    assert _rich_text(said_view.voice.cite) == "— stated by a human, verbatim"
    assert claim_view.checks[0].sentence.startswith(
        "Every entry on one side must have a counterpart on the other."
    )
    assert [(step.label, step.explanation) for step in claim_view.stage_steps] == [
        ("1 proposed", "the AI wrote it"),
        ("2 planned", "bound to a check"),
        ("3 judged", "a check ran"),
        ("4 settled", "status unresolved"),
    ]


def test_check_card_shows_the_rendered_sql_that_was_asked(tmp_path):
    root = init_project(tmp_path / "sql")
    store = ProjectStore(root)

    claim = create_claim(
        "The journal balances per document",
        Actor.AI,
        predicate=Predicate(name="balance", params={"journal": "de_erp__gl_postings"}),
    )
    store.save_claim(claim)
    check = CheckPlan(template="balance", claim_id=claim.id, roles=["journal"], params={})
    store.save_check_plan(check)
    sql = (
        'SELECT "doc_ref", sum(CAST("amount_local_currency" AS DOUBLE)) AS total\n'
        'FROM "de_erp__gl_postings"\n'
        'GROUP BY "doc_ref"\n'
        "HAVING abs(total) > 0.01"
    )
    # The runner records the rendered SQL on the check-result payload — that is
    # where the viewer must read it from.
    record = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT,
        actor=Actor.CHECK,
        claim_id=claim.id,
        check_plan_id=check.id,
        verdict=CheckVerdict.PASS,
        population=4020,
        exception_count=0,
        payload={"template": "balance", "sql": sql, "summary": "no violations"},
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, []))

    view = load_view_model(root)
    check_view = _claim(view, claim.id).checks[0]

    assert check_view.rendered_sql == sql
    assert 'GROUP BY "doc_ref"' in check_view.rendered_sql
    assert "HAVING abs(total) > 0.01" in check_view.rendered_sql


def test_check_without_a_run_says_no_sql_was_asked(tmp_path):
    root = init_project(tmp_path / "no-sql")
    store = ProjectStore(root)

    claim = create_claim("Postings reference invoices", Actor.AI)
    store.save_claim(claim)
    store.save_check_plan(CheckPlan(template="anti_join", claim_id=claim.id, params={}))

    view = load_view_model(root)

    assert _claim(view, claim.id).checks[0].rendered_sql == ""


def test_a_slot_field_shows_the_column_its_object_s_law_consumed(tmp_path):
    """A slot holds no election of its own: the journal's passing balance run
    consumed a column, and that column is the answer — shown, not asked."""
    root = init_project(tmp_path / "slots")
    guide = tmp_path / "guide.yaml"
    guide.write_text(
        "domain: finance\n"
        "objects:\n"
        "  journal:\n"
        "    decided_by: balance\n"
        "    definition: The transactional ledger of record.\n"
        "    fields:\n"
        "      amount_local:\n"
        "        decided_by: slot\n"
        "        fills: amount\n"
        "        definition: The signed posting amount.\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["llm"] = {"domain_guide_file": str(guide)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    store = ProjectStore(root)
    journal = MappingClaim(
        statement="role 'journal' is played by de_erp__gl_postings",
        created_by=Actor.AI, role="journal",
        binding={"table": "de_erp__gl_postings"},
    )
    amount = MappingClaim(
        statement="role 'amount_local' is played by amount_local_currency",
        created_by=Actor.AI, role="amount_local",
        binding={"table": "de_erp__gl_postings",
                 "amount": "de_erp__gl_postings.amount_local_currency"},
    )
    store.save_claim(journal)
    store.save_claim(amount)
    check = CheckPlan(template="balance", claim_id=journal.id, roles=["journal"],
                      params={"journal": "de_erp__gl_postings",
                              "amount": "amount_local_currency",
                              "group_column": "period"})
    store.save_check_plan(check)
    record = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK, claim_id=journal.id,
        check_plan_id=check.id, verdict=CheckVerdict.PASS,
        population=383, exception_count=0,
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(journal, record, []))

    view = load_view_model(root)
    field = next(item for item in view.elections if item.role == "amount_local")
    outcome = " ".join(text for _, text in _outcome_text(field))
    consumed = [
        _rich_text(reason)
        for candidate in field.candidates
        for reason in candidate.reasons
    ]

    assert field.field is True
    assert field.owner == "journal"
    assert "Answered — without anyone being asked." in outcome
    assert (
        "The balance law of journal passed while reading "
        "de_erp__gl_postings.amount_local_currency"
    ) in outcome
    assert "nothing can prove by arithmetic what a single column means" in outcome
    assert any("The passing run consumed this column" in reason for reason in consumed)


def test_domain_pack_panel_lists_the_three_declared_inputs(tmp_path):
    root = init_project(tmp_path / "domain")
    domain_guide_file = tmp_path / "domain_guide_finance.yaml"
    domain_guide_file.write_text(
        "domain: finance\n"
        "objects:\n"
        "  journal:\n"
        "    decided_by: balance\n"
        "    definition: The transactional ledger of record.\n"
        "    fields:\n"
        "      amount_local:\n"
        "        decided_by: slot\n"
        "        fills: amount\n"
        "        definition: The signed posting amount.\n"
        "  subledger_ar:\n"
        "    decided_by: subledger_equals_gl\n"
        "    definition: The accounts-receivable open items.\n"
        "answer_types:\n"
        "  profit_and_loss_by_dimension:\n"
        "    definition: The result of a period, by a dimension.\n"
        "    requires:\n"
        "      - object: journal\n"
        "      - field: journal.amount_local\n"
        "      - rule: sign convention for income and expense\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["sources"] = [
        {"name": "de_erp", "kind": "duckdb", "location": "/data/DE/erp.duckdb"}
    ]
    config["llm"] = {"domain_guide_file": str(domain_guide_file)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    view = load_view_model(root)
    pack = view.domain_pack

    assert [(item.name, item.location) for item in pack.sources] == [
        ("de_erp", "/data/DE/erp.duckdb")
    ]
    assert pack.guide.state == "loaded"
    assert (pack.guide.object_count, pack.guide.field_count) == (2, 1)
    assert [item.name for item in pack.guide.entries] == ["journal", "subledger_ar"]
    assert pack.guide.entries[0].fields[0].name == "amount_local"
    assert pack.guide.entries[0].fields[0].decision == (
        "slot — elected as the 'amount' of its object's law"
    )
    assert pack.guide.path == str(domain_guide_file)
    # The answer types belong in the declared inputs: section 1 says which
    # one the question was treated as, and a reader can only judge that
    # against what was on offer and what the chosen one claims.
    (answer_type,) = pack.guide.answer_types
    assert answer_type.name == "profit_and_loss_by_dimension"
    assert answer_type.definition == "The result of a period, by a dimension."
    assert answer_type.requires == (
        "object: journal",
        "field: journal.amount_local",
        "rule: sign convention for income and expense",
    )
    assert {law.name for law in pack.laws.laws} == {
        "balance", "subledger_equals_gl", "ic_symmetry"
    }
    assert all(law.domain == "finance" for law in pack.laws.laws)
    generic = len(REGISTRY) - sum(1 for spec in REGISTRY.values() if spec.domain)
    assert pack.laws.generic_count == generic
    assert f"The other {generic} templates in the catalog are generic" in pack.laws.note


def test_the_law_panel_shows_this_project_s_domain_and_no_other(tmp_path):
    """"What this project declared" must not list another domain's laws.

    The guide lint refuses a law from a foreign domain, so showing one under
    the declared inputs would be a false claim about the project's inputs.
    """
    root = init_project(tmp_path / "foreign")
    guide = tmp_path / "guide.yaml"
    guide.write_text(
        "domain: shipbuilding\n"
        "objects:\n"
        "  purchase_order:\n"
        "    decided_by: clarification\n"
        "    definition: The committed orders placed with suppliers.\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["llm"] = {"domain_guide_file": str(guide)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    view = load_view_model(root)
    laws = view.domain_pack.laws
    domain_law_count = sum(1 for spec in REGISTRY.values() if spec.domain)

    assert not {"balance", "subledger_equals_gl", "ic_symmetry"} & {
        item.name for item in laws.laws
    }
    assert "No domain law is shipped for shipbuilding" in _rich_text(
        laws.empty_message
    )
    assert "nothing here can be promoted by a check" in _rich_text(
        laws.empty_message
    )
    assert laws.foreign_count == domain_law_count
    assert (
        f"A further {domain_law_count} domain laws in the catalog belong to other domains"
        in laws.note
    )


def test_two_entities_get_two_elections_and_the_page_says_which(tmp_path):
    """A landscape is typically multi-entity, and one election across all of
    it would report a working ledger as contradicted because another
    entity's balances better. The page must show one election per scope and
    name the books each is about."""
    root = init_project(tmp_path / "scoped")
    store = ProjectStore(root)
    guide = tmp_path / "guide.yaml"
    guide.write_text(
        "domain: finance\n"
        "objects:\n"
        "  journal:\n"
        "    decided_by: balance\n"
        "    definition: The transactional ledger of record.\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["llm"] = {"domain_guide_file": str(guide)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    for entity, table in (("DE", "de_erp__gl"), ("US", "us_erp__gl")):
        source = Source(name=entity, kind="duckdb", location=f"/tmp/{entity}.db",
                        scope=Scope(entity=entity))
        store.save_source(source)
        store.save_claim(MappingClaim(
            statement=f"role 'journal' is played by {table}",
            created_by=Actor.AI, role="journal", scope=Scope(entity=entity),
            binding={"table": table}, source_ids=[source.id],
        ))

    view = load_view_model(root)
    journal_elections = [item for item in view.elections if item.role == "journal"]

    assert len(journal_elections) == 2
    assert {item.scope for item in journal_elections} == {"entity DE", "entity US"}
    assert all(item.candidate_count == 1 for item in journal_elections)
    assert ("0/2", "elections settled") in _stage(view, "tested").counts


def _p_and_l_project(tmp_path, name="readiness"):
    """A project with a guide, a question asked of it, and one ledger."""
    root = init_project(tmp_path / name)
    store = ProjectStore(root)
    guide = tmp_path / f"{name}-guide.yaml"
    guide.write_text(
        "domain: finance\n"
        "objects:\n"
        "  journal:\n"
        "    decided_by: balance\n"
        "    definition: The transactional ledger of record.\n"
        "    fields:\n"
        "      amount_local:\n"
        "        decided_by: slot\n"
        "        fills: amount\n"
        "        definition: The signed posting amount.\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["llm"] = {"domain_guide_file": str(guide)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    request = AnswerRequest(
        question="Can these files reliably produce actual P&L by entity and month?",
        requested_output="P&L per entity per month",
    )
    store.save_request(request)
    store.save_required_knowledge(RequiredKnowledge(request_id=request.id, items=[
        KnowledgeItem(kind=KnowledgeKind.OBJECT, name="journal",
                      why="the figures are summed from it"),
        KnowledgeItem(kind=KnowledgeKind.FIELD, name="amount_local",
                      of_object="journal", why="it is what gets summed"),
        KnowledgeItem(kind=KnowledgeKind.RULE, name="sign convention",
                      why="it decides profit from loss"),
    ]))
    return root, store, load_domain_guide(guide)


def test_readiness_is_a_real_stage_and_the_verdict_names_what_it_rests_on(tmp_path):
    """The bottom of the machine, on the page. The question is the human's
    words, the verdict is derived, and the AI's reason for listing a
    dependency is attributed and subordinate to it."""
    root, store, _ = _p_and_l_project(tmp_path)
    journal = MappingClaim(statement="role 'journal' is played by de_erp__gl",
                           created_by=Actor.AI, role="journal",
                           binding={"table": "de_erp__gl"})
    store.save_claim(journal)
    plan = CheckPlan(template="balance", roles=["journal"],
                     params={"journal": "de_erp__gl", "amount": "betrag",
                             "group_column": "period"})
    store.save_check_plan(plan)
    record = EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
                            claim_id=journal.id, check_plan_id=plan.id,
                            verdict=CheckVerdict.PASS, population=9,
                            exception_count=0)
    store.add_evidence(record)
    store.save_claim(attach_evidence(journal, record, []))

    view = load_view_model(root)
    request = view.requests[0]
    readiness = view.readiness[0]
    items = {item.ref: item for group in readiness.groups for item in group.items}

    assert [stage.name for stage in view.stages] == [stage.name for stage in STAGES]
    assert ("2/3", "dependencies supported") in _stage(view, "readiness").counts
    assert _stage(view, "request").label == "1 · request"
    assert _stage(view, "readiness").label == "6 · readiness"
    assert request.question == (
        "Can these files reliably produce actual P&L by entity and month?"
    )
    assert request.requested_output == "P&L per entity per month"
    assert request.provenance.notes[0] == "asked by a human"
    assert readiness.headline == "Ready, with limitations."
    assert "'sign convention'" in readiness.reason
    assert "what they mean is not settled" in readiness.reason
    assert "What they mean is not fully settled" in readiness.explanation
    assert items["journal"].because.startswith(
        "Satisfied because its own claim is test-supported"
    )
    assert (
        "the balance law of 'journal' passed while reading"
        in items["journal.amount_local"].because
    )
    assert "still proposed" in items["journal.amount_local"].because
    assert next(item for item in request.items if item.ref == "journal").why_cite == (
        "— the AI, on why the answer depends on this"
    )


def test_an_unreviewed_dependency_list_says_so_where_it_is_listed(tmp_path):
    """The reader has to know what kind of list they are reading before they
    read it, so the classification headlines the request card — and when
    there is none, the card says the list was written for this question."""
    root, _, _ = _p_and_l_project(tmp_path, "unreviewed")

    view = load_view_model(root)

    assert _rich_text(view.requests[0].treated_as).startswith(
        "Treated as: no declared answer type."
    )
    assert "nobody has reviewed it as a whole" in _rich_text(
        view.requests[0].treated_as
    )
    assert {item.provenance for item in view.requests[0].items} == {
        "drafted for this question"
    }
    assert "No answer type of the domain guide covers this question" in (
        view.readiness[0].reason
    )


def test_a_classified_list_names_its_answer_type_and_its_guide(tmp_path):
    root, store, guide_path = _typed_project(tmp_path)

    view = load_view_model(root)
    request = view.requests[0]
    treated_as = _rich_text(request.treated_as)

    fingerprint = load_domain_guide(guide_path).fingerprint[:12]
    assert treated_as.startswith("Treated as: profit_and_loss")
    assert f"(guide {fingerprint})" in treated_as
    assert "not confirmed by anyone yet" in treated_as
    assert {item.provenance for item in request.items} == {"from the answer type"}
    assert {item.why_cite for item in request.items} == {
        "— the domain guide, on why an answer of this kind depends on it"
    }


def test_confirming_the_list_is_visible_on_the_page(tmp_path):
    root, store, guide_path = _typed_project(tmp_path)
    confirm_classification(store, load_domain_guide(guide_path),
                           next(iter(store.requests)))

    view = load_view_model(root)
    treated_as = _rich_text(view.requests[0].treated_as)

    assert "confirmed by a human" in treated_as
    assert "nobody has confirmed" not in treated_as


def _typed_project(tmp_path):
    """A project whose question was classified to a declared answer type."""
    root = init_project(tmp_path / "typed")
    store = ProjectStore(root)
    guide_path = tmp_path / "typed-guide.yaml"
    guide_path.write_text(
        "domain: finance\n"
        "objects:\n"
        "  journal:\n"
        "    decided_by: balance\n"
        "    definition: The transactional ledger of record.\n"
        "answer_types:\n"
        "  profit_and_loss:\n"
        "    definition: The result of a period.\n"
        "    requires:\n"
        "      - object: journal\n"
        "        why: the figures are summed from it\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["llm"] = {"domain_guide_file": str(guide_path)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
    store.save_request(AnswerRequest(
        question="Can these files reliably produce actual P&L?",
        requested_output="P&L per entity per month",
        answer_type="profit_and_loss",
    ))
    return root, store, guide_path


def test_a_blocked_answer_says_so_before_it_says_anything_else(tmp_path):
    root, _, _ = _p_and_l_project(tmp_path, "blocked")

    view = load_view_model(root)
    readiness = view.readiness[0]
    items = {item.ref: item for group in readiness.groups for item in group.items}

    assert readiness.headline == "Blocked."
    assert readiness.reason.startswith("The answer cannot be produced")
    assert readiness.explanation.startswith("The figures cannot be produced")
    assert items["journal"].because == (
        "Not supported: nothing in this project plays it."
    )
    assert ("blocked", "verdict") in _stage(view, "readiness").counts


def test_a_linked_rule_shows_who_linked_it_and_why(tmp_path):
    """A rule is only ever satisfied by an explicit link, so the link is part
    of the audit trail: a wrong one points a verdict at an unrelated claim."""
    root, store, guide = _p_and_l_project(tmp_path, "linked")
    policy = ConceptClaim(
        statement="income is stored as a negative amount",
        created_by=Actor.HUMAN, term="haben_konvention",
        definition="income negative, expense positive",
        status=ClaimStatus.BUSINESS_CONFIRMED,
    )
    store.save_claim(policy)
    link_claim(store, guide, next(iter(store.requests)), "sign convention",
               policy.id,
               linked_by=Actor.AI, note="Buchhaltungsrichtlinie §2")

    view = load_view_model(root)
    items = {
        item.ref: item
        for group in view.readiness[0].groups
        for item in group.items
    }
    linked = items["sign convention"]

    assert linked.because.startswith(
        "Satisfied because a business-confirmed claim is linked to it by the ai"
    )
    assert "income is stored as a negative amount" in linked.because
    assert [_rich_text(item.sentence) for item in linked.links] == [
        f"Linked by the ai — Buchhaltungsrichtlinie §2 → {policy.id[-6:]}"
    ]
    assert "haben_konvention" != "sign convention"


def test_an_answered_question_leaves_the_open_list(tmp_path):
    """Before this, answering a card left it in "5 · Open" forever while the
    readiness map called the same dependency settled — two surfaces of one
    store disagreeing. Answered is derived from the same evidence the map
    reads, so they cannot drift apart."""
    root = init_project(tmp_path / "answered")
    store = ProjectStore(root)
    picked = MappingClaim(statement="role 'period' is played by de_erp__gl",
                          created_by=Actor.AI, role="period",
                          binding={"table": "de_erp__gl"})
    store.save_claim(picked)
    store.save_question(ClarificationQuestion(
        question="Which of the proposed candidates is the 'period'?",
        claim_ids=[picked.id]))
    open_still = MappingClaim(statement="role 'account' is played by de_erp__gl",
                              created_by=Actor.AI, role="account",
                              binding={"table": "de_erp__gl"})
    store.save_claim(open_still)
    store.save_question(ClarificationQuestion(
        question="Which of the proposed candidates is the 'account'?",
        claim_ids=[open_still.id]))

    before = load_view_model(root)
    assert len(before.open_questions) == 2

    # the human answers one of them
    record = EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN,
                            claim_id=picked.id)
    store.add_evidence(record)
    store.save_claim(attach_evidence(picked, record, []))

    view = load_view_model(root)

    assert len(view.open_questions) == 1
    assert len(view.answered_questions) == 1
    assert view.answered_questions[0].summary == "Answered. Settled by 1 claim:"
    assert [item.link.reference.id for item in view.answered_questions[0].settled] == [
        picked.id
    ]
    assert "'period'" in view.answered_questions[0].settled[0].link.label
    assert "'account'" in view.open_questions[0].options[0].link.label


def test_a_project_nobody_asked_a_question_of_says_that_plainly(tmp_path):
    """Without a question the report describes a landscape, and whether a
    landscape is generally sound is a question nobody asked."""
    view = load_view_model(init_project(tmp_path / "unasked"))

    assert view.copy.no_request.startswith(
        "No business question has been asked of this project yet"
    )
    assert _stage(view, "readiness").counts == (("—", "no question asked"),)


def test_domain_pack_panel_is_honest_when_nothing_is_declared(tmp_path):
    root = init_project(tmp_path / "undeclared")

    view = load_view_model(root)

    assert view.domain_pack.sources == ()
    assert view.domain_pack.guide.state == "missing"


def test_core_terms_define_the_canonical_vocabulary(tmp_path):
    root = init_project(tmp_path / "terms")

    view = load_view_model(root)
    terms = {term for term, _ in view.glossary}

    assert {
        "hypothesis",
        "claim",
        "mapping claim",
        "status",
        "domain guide",
        "business object",
        "field",
        "role",
        "data profile",
        "check definition",
        "check plan",
        "check run",
        "evidence",
        "domain law",
        "clarification question",
    } <= terms


def test_html_renders_every_report_section(tmp_path):
    html = render_project(init_project(tmp_path / "sections"))
    document = _document(html)

    assert {
        "process", "inputs", "request", "measured", "proposed", "tested",
        "clarification", "readiness", "claims", "integrity", "terms",
    } <= document.ids


def test_html_numbers_its_subsections_after_the_stage_they_sit_in(tmp_path):
    """They read 1.1 / 1.2 / 1.3 inside a section called 0 — left over from
    the numbering the stage spine replaced. Two surfaces disagreeing about
    one thing is the defect the spine exists to prevent."""
    html = render_project(init_project(tmp_path / "numbering"))

    for n, title in enumerate(("Raw data", "Domain guide", "Domain-law"), start=1):
        assert f"0.{n} · {title}" in html
        assert f"1.{n} · {title}" not in html


def test_html_internal_anchors_resolve(tmp_path):
    root = init_project(tmp_path / "anchors")
    store = ProjectStore(root)
    source = Source(name="erp", kind="duckdb", location="/tmp/erp.duckdb")
    store.save_source(source)
    claim = create_claim(
        "Postings reference invoices", Actor.AI, source_ids=[source.id]
    )
    store.save_claim(claim)
    check = CheckPlan(template="anti_join", claim_id=claim.id, params={})
    store.save_check_plan(check)
    record = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT,
        actor=Actor.CHECK,
        claim_id=claim.id,
        check_plan_id=check.id,
        verdict=CheckVerdict.FAIL,
        population=4,
        exception_count=1,
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, []))
    store.save_question(
        ClarificationQuestion(question="Which source leads?", claim_ids=[claim.id])
    )

    document = _document(render_project(root))

    assert document.fragments - document.ids == set()


def test_html_escapes_user_visible_values(tmp_path):
    root = init_project(tmp_path / "escaping")
    store = ProjectStore(root)
    store.save_claim(create_claim("Revenue < forecast & plan", Actor.AI))

    html = render_project(root)

    assert "Revenue &lt; forecast &amp; plan" in html
    assert "Revenue < forecast & plan" not in html


def test_html_is_self_contained(tmp_path):
    html = render_project(init_project(tmp_path / "self-contained"))
    document = _document(html)

    assert "http://" not in html
    assert "https://" not in html
    assert not [url for url in document.urls if url.startswith("//")]


def test_html_preserves_three_voice_attributions(tmp_path):
    root = init_project(tmp_path / "html-voices")
    store = ProjectStore(root)
    claim = create_claim("Postings reference invoices", Actor.AI)
    store.save_claim(claim)
    check = CheckPlan(template="anti_join", claim_id=claim.id, params={})
    store.save_check_plan(check)
    failed = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT,
        actor=Actor.CHECK,
        claim_id=claim.id,
        check_plan_id=check.id,
        verdict=CheckVerdict.FAIL,
        population=400,
        exception_count=8,
    )
    said = EvidenceRecord(
        type=EvidenceType.TESTIMONIAL,
        actor=Actor.HUMAN,
        claim_id=claim.id,
        statement="Postings from the legacy migration never got an invoice.",
    )
    store.add_evidence(failed)
    store.add_evidence(said)
    claim = attach_evidence(claim, failed, [])
    store.save_claim(attach_evidence(claim, said, [failed]))
    request_root, _, _ = _p_and_l_project(tmp_path, "html-request-voices")

    html = render_project(root)
    request_html = render_project(request_root)

    assert "wrote it, verbatim; a proposal, not a finding" in html
    assert "Postings from the legacy migration never got an invoice." in html
    assert "— stated by a human, verbatim" in html
    assert "— the business question, as it was asked" in request_html
    assert "— the AI, on what the answer must deliver" in request_html
    assert request_html.index("as it was asked") < request_html.index(
        "what the answer must deliver"
    )
    assert request_html.index("the figures are summed from it") < (
        request_html.index("Not supported: nothing in this project plays it")
    )


def test_html_renders_verdict_headline_wording(tmp_path):
    root, store, _ = _p_and_l_project(tmp_path, "html-verdict")
    blocked_html = render_project(root)
    journal = MappingClaim(
        statement="role 'journal' is played by de_erp__gl",
        created_by=Actor.AI,
        role="journal",
        binding={"table": "de_erp__gl"},
    )
    store.save_claim(journal)
    plan = CheckPlan(
        template="balance",
        roles=["journal"],
        params={
            "journal": "de_erp__gl",
            "amount": "betrag",
            "group_column": "period",
        },
    )
    store.save_check_plan(plan)
    record = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT,
        actor=Actor.CHECK,
        claim_id=journal.id,
        check_plan_id=plan.id,
        verdict=CheckVerdict.PASS,
        population=9,
        exception_count=0,
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(journal, record, []))
    limited_html = render_project(root)

    assert "<strong>Blocked.</strong>" in blocked_html
    assert "<strong>Ready, with limitations.</strong>" in limited_html


def test_module_cli_writes_output_outside_project_by_default(tmp_path):
    root = init_project(tmp_path / "cli-project")
    repo_root = Path(__file__).resolve().parents[2]

    result = subprocess.run(
        [sys.executable, "-m", "readiness_report", str(root)],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    output = Path(result.stdout.strip())
    assert output == root.parent / f"{root.name}-readiness-report.html"
    assert output.is_file()
    assert not (root / output.name).exists()
