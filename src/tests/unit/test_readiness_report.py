import subprocess
import sys
from pathlib import Path

import json

import yaml

from before_we_ai.model import (
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
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.model.objects import DataProfile
from html import escape

from before_we_ai.checks.library import REGISTRY
from before_we_ai.stages import BOUNDARY_TEXT, STAGES
from before_we_ai.readiness import link_claim
from before_we_ai.store import ProjectStore, init_project
from readiness_report import render_project


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

    html = render_project(root)

    assert "Invoices reference orders" in html
    assert "Conflict is present" in html or "failing check" in html
    assert f'href="#claim-{parent.id}"' in html
    assert f'id="evidence-{check.id}"' in html
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

    html = render_project(root)

    assert "3 · Proposed — what the AI guessed" in html
    assert 'data-stage-chip="bound"' in html
    # one claim per stage: bound / unbindable / semantic-only
    assert html.count('data-stage="bound"') == 1
    assert html.count('data-stage="unbindable"') == 1
    assert html.count('data-stage="semantic_only"') == 1
    assert html.count('data-executed="yes"') == 1
    # the refusal is readable where the check would have been
    assert "no documented pairs available to populate the template" in html
    assert "Never tested" in html
    # the funnel filters on the derived status, not the stored one
    assert 'data-status="test-supported"' in html


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

    html = render_project(root)

    assert "4 · Tested — what the checks settled" in html
    assert "<strong>Identified.</strong> The balance law passed on" in html
    assert "felled by" in html
    assert "24 exceptions in 383 rows" in html
    assert "finance law" in html  # the domain-law tag of the invariant template
    assert "<strong>Open — a human has to answer it.</strong>" in html
    assert f'href="#question-{card.id}"' in html
    # the open-questions inbox is its own pipeline step, and counts
    assert "5 · Clarification — what only a human can answer (1)" in html


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

    html = render_project(root)

    # every stage of the spine draws a node linking into its own section —
    # the diagram renders before_we_ai.stages, it does not restate it
    for stage in STAGES:
        assert f'<div class="node-title"><a href="#{stage.name}">' in html
        assert escape(stage.actor) in html
    assert BOUNDARY_TEXT in html
    # the counts are read from this project, not written into the template
    laws = sum(1 for spec in REGISTRY.values() if spec.domain)
    assert "<strong>1</strong> source" in html
    assert "<strong>1+1</strong> objects + fields" in html
    assert f"<strong>{laws}</strong> domain laws" in html
    assert "<strong>1</strong> column profiles" in html
    assert "<strong>2</strong> claims" in html
    assert "<strong>2</strong> check runs" in html
    assert "<strong>1/2</strong> elections settled" in html
    assert "<strong>1</strong> open question" in html

    # readiness is a real stage now; nothing was asked of this project, and
    # the diagram says that rather than showing a verdict nobody earned
    assert "<strong>—</strong> no question asked" in html
    # what is not built still says so, rather than being left out
    assert "M5 · documents" in html
    assert html.count("not built") == 1


def test_a_question_lists_candidates_and_hides_its_ids(tmp_path):
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

    html = render_project(root)

    # a clarification-decided role is answered by picking one of its candidates
    assert "Pick one — 2 candidates were proposed:" in html
    # a role whose law never ran is not a pick — it is asking for knowledge
    assert "no law could be applied to any of them" in html
    # the candidates are named by their binding; the claim's own sprawling
    # statement survives only where the model's words belong (quoted and
    # attributed) and in the hidden search index — never as a heading
    short = "&#x27;doc_ref&#x27; is played by de_erp__gl_postings.document_reference"
    assert f"<h3>{short}</h3>" in html
    assert f"<div>{short}</div>" in html  # the index card in the sidebar
    # ids and timestamps are reachable, never in the way
    assert "<details class='tech'><summary>Technical details</summary>" in html
    # and the YAML the page only renders is one click away
    assert "questions/" in html and ".yaml" in html


def test_the_page_speaks_in_three_voices(tmp_path):
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

    html = render_project(root)

    # 1 — the derived voice states what happened, from the numbers
    assert "The check refuted the claim: 8 exceptions in 400 rows (2.00% of the rows)." in html
    # 2 — the AI's own sentence is kept, attributed, and marked a proposal
    assert "wrote it, verbatim; a proposal, not a finding" in html
    # 3 — the human's words are verbatim and marked as theirs
    assert "Postings from the legacy migration never got an invoice." in html
    assert "— stated by a human, verbatim" in html
    # what this check tries to break, in business words, from its definition
    assert "Every entry on one side must have a counterpart on the other." in html
    # how far the claim got — a failing check against a human's word is a
    # conflict, and the strip says which step reached which state
    assert "1 proposed — the AI wrote it" in html
    assert "2 planned — bound to a check" in html
    assert "3 judged — a check ran" in html
    assert "4 settled — status unresolved" in html


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

    html = render_project(root)

    assert "Rendered SQL — the question that was asked of the data" in html
    # the exact SQL, escaped, inside a code block under the check card
    assert "<pre><code>" in html
    assert "GROUP BY &quot;doc_ref&quot;" in html
    assert "HAVING abs(total) &gt; 0.01" in html


def test_check_without_a_run_says_no_sql_was_asked(tmp_path):
    root = init_project(tmp_path / "no-sql")
    store = ProjectStore(root)

    claim = create_claim("Postings reference invoices", Actor.AI)
    store.save_claim(claim)
    store.save_check_plan(CheckPlan(template="anti_join", claim_id=claim.id, params={}))

    html = render_project(root)

    assert "No rendered SQL yet" in html


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

    html = render_project(root)

    # the confusion this narration exists to end: the field IS answered, and
    # its candidates still read `proposed` — both said, in that order
    assert "<strong>Answered — without anyone being asked.</strong>" in html
    assert ("The balance law of <code>journal</code> passed while reading "
            "<code>de_erp__gl_postings.amount_local_currency</code>") in html
    assert "nothing can prove by arithmetic what a single column" in html
    # and the candidate row the law actually read says so where the eye is
    assert "<strong>The passing run consumed this column</strong>" in html
    assert "field of <code>journal</code>" in html  # nested under its object


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
        "    definition: The accounts-receivable open items.\n",
        encoding="utf-8",
    )
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8")) or {}
    config["sources"] = [
        {"name": "de_erp", "kind": "duckdb", "location": "/data/DE/erp.duckdb"}
    ]
    config["llm"] = {"domain_guide_file": str(domain_guide_file)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")

    html = render_project(root)

    assert "1 · Inputs — what a human declared" in html
    # 1 — the declared sources
    assert "de_erp" in html and "/data/DE/erp.duckdb" in html
    # 2 — the domain guide: file, domain, shape and names
    assert "2 business objects with 1 field" in html
    assert "journal" in html and "subledger_ar" in html
    # the field is shown under its object, with the slot it fills
    assert "amount_local" in html
    assert "slot — elected as the &#x27;amount&#x27; of its object&#x27;s law" in html
    assert str(domain_guide_file) in html
    # 3 — the domain-law templates, and the generic remainder named as such
    for template in ("balance", "subledger_equals_gl", "ic_symmetry"):
        assert f"<code>{template}</code>" in html
    assert "finance law" in html
    generic = len(REGISTRY) - sum(1 for spec in REGISTRY.values() if spec.domain)
    assert f"The other {generic} templates in the catalog are generic" in html


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

    html = render_project(root)

    laws = sum(1 for spec in REGISTRY.values() if spec.domain)
    # no finance law is presented as an input of a shipbuilding project
    for finance_law in ("balance", "subledger_equals_gl", "ic_symmetry"):
        assert f'<code>{finance_law}</code> <span class="badge' not in html
    # and the absence is stated, with its consequence
    assert "No domain law is shipped for <strong>shipbuilding</strong>" in html
    assert "nothing here can be promoted by a check" in html
    assert f"A further {laws} domain laws in the catalog belong to other domains" in html


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

    html = render_project(root)

    assert html.count("<code>journal</code>") >= 2
    assert "for entity DE" in html and "for entity US" in html
    assert "<strong>0/2</strong> elections settled" in html


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
    return root, store


def test_readiness_is_a_real_stage_and_the_verdict_names_what_it_rests_on(tmp_path):
    """The bottom of the machine, on the page. The question is the human's
    words, the verdict is derived, and the AI's reason for listing a
    dependency is attributed and subordinate to it."""
    root, store = _p_and_l_project(tmp_path)
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

    html = render_project(root)

    # the ghost is gone; the stage is real and carries live numbers
    assert "M6 · question → readiness" not in html
    assert "<strong>2/3</strong> dependencies supported" in html
    assert "0 · Request — the question, and what it requires" in html
    assert "6 · Readiness — what may be answered" in html

    # the human's question, verbatim — and the AI's restatement attributed to
    # the AI, not folded into the human's voice for sitting on one record
    assert "Can these files reliably produce actual P&amp;L by entity and month?" in html
    assert "— the business question, as it was asked" in html
    assert "— the AI, on what the answer must deliver" in html
    assert html.index("as it was asked") < html.index("what the answer must deliver")

    # the verdict is narrowed, not blocked: the figures compute, the meaning
    # is unsettled — and it names what is unsettled
    assert "Ready, with limitations." in html
    assert "&#x27;sign convention&#x27;" in html
    assert "what they mean is not settled" in html

    # every satisfied item says HOW, and the two grounds differ
    assert "Satisfied because its own claim is test-supported" in html
    assert "the balance law of &#x27;journal&#x27; passed while reading" in html
    assert "still proposed" in html

    # three voices: the AI's why is attributed and never the headline
    assert "— the AI, on why the answer depends on this" in html
    # section 0 states the dependency and the AI's reason for it; section 6
    # states what became of it. The derived line is never below the AI's.
    assert html.index("the figures are summed from it") < \
        html.index("Satisfied because its own claim")


def test_a_blocked_answer_says_so_before_it_says_anything_else(tmp_path):
    root, _ = _p_and_l_project(tmp_path, "blocked")

    html = render_project(root)

    assert "Blocked." in html
    assert "The answer cannot be produced" in html
    assert "Not supported: nothing in this project plays it" in html
    assert "<strong>blocked</strong> verdict" in html


def test_a_linked_rule_shows_who_linked_it_and_why(tmp_path):
    """A rule is only ever satisfied by an explicit link, so the link is part
    of the audit trail: a wrong one points a verdict at an unrelated claim."""
    root, store = _p_and_l_project(tmp_path, "linked")
    policy = ConceptClaim(
        statement="income is stored as a negative amount",
        created_by=Actor.HUMAN, term="haben_konvention",
        definition="income negative, expense positive",
        status=ClaimStatus.BUSINESS_CONFIRMED,
    )
    store.save_claim(policy)
    link_claim(store, next(iter(store.requests)), "sign convention", policy.id,
               linked_by=Actor.AI, note="Buchhaltungsrichtlinie §2")

    html = render_project(root)

    assert "a business-confirmed claim is linked to it by the ai" in html
    assert "Linked by the ai — Buchhaltungsrichtlinie §2" in html
    # the claim's term and the rule's name do not match; only the link joins
    # them, which is the whole reason the link exists
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

    assert "5 · Clarification — what only a human can answer (2)" in render_project(root)

    # the human answers one of them
    record = EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN,
                            claim_id=picked.id)
    store.add_evidence(record)
    store.save_claim(attach_evidence(picked, record, []))

    html = render_project(root)

    assert "5 · Clarification — what only a human can answer (1)" in html
    assert "Answered questions (1)" in html
    assert "<strong>Answered.</strong> Settled by 1 claim" in html
    # kept, not dropped: what settled it is part of the record
    assert "the &#x27;period&#x27;" in html
    assert "the &#x27;account&#x27;" in html


def test_a_project_nobody_asked_a_question_of_says_that_plainly(tmp_path):
    """Without a question the report describes a landscape, and whether a
    landscape is generally sound is a question nobody asked."""
    html = render_project(init_project(tmp_path / "unasked"))

    assert "No business question has been asked of this project yet" in html
    assert "<strong>—</strong> no question asked" in html


def test_domain_pack_panel_is_honest_when_nothing_is_declared(tmp_path):
    root = init_project(tmp_path / "undeclared")

    html = render_project(root)

    assert "No sources declared in before-ai.yaml." in html
    assert "No domain guide declared (llm.domain_guide_file)." in html


def test_core_terms_define_the_canonical_vocabulary(tmp_path):
    root = init_project(tmp_path / "terms")

    html = render_project(root)

    assert "Core terms" in html
    for term in (
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
    ):
        assert f"<dt>{term}</dt>" in html


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
