import subprocess
import sys
from pathlib import Path

import json

import yaml

from before_we_ai.model import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    Predicate,
    CheckPlan,
    CheckVerdict,
    ClarificationQuestion,
    MappingClaim,
    Source,
    create_claim,
)
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.model.objects import DataProfile
from before_we_ai.checks.library import REGISTRY
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
        question="Für die Rolle 'intercompany' hat keine Bindung ihre Sonde bestanden — welche Quelle führt?",
        claim_ids=[orphan.id],
    )
    store.save_question(card)

    html = render_project(root)

    assert "4 · Decided — what the checks settled" in html
    assert "Elected:" in html
    assert "felled by" in html
    assert "24 exceptions in 383 rows" in html
    assert "finance law" in html  # the domain-law tag of the invariant template
    assert "No winner → clarification question" in html
    assert f'href="#question-{card.id}"' in html
    # the open-questions inbox is its own pipeline step, and counts
    assert "5 · Open — what only a human can answer (1)" in html


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

    # every stage is a link into the section that produced it
    for anchor in ("inputs", "measured", "proposed", "decided", "open"):
        assert f'<div class="node-title"><a href="#{anchor}">' in html
    # the counts are read from this project, not written into the template
    laws = sum(1 for spec in REGISTRY.values() if spec.domain)
    assert "<strong>1</strong> source" in html
    assert "<strong>1+1</strong> objects + fields" in html
    assert f"<strong>{laws}</strong> domain laws" in html
    assert "<strong>1</strong> column profiles" in html
    assert "<strong>2</strong> claims" in html
    assert "<strong>2</strong> check runs" in html
    assert "<strong>1/2</strong> roles elected" in html
    assert "<strong>1</strong> open question" in html
    # the invariant, drawn: the AI's side of the line proposes and nothing more
    assert "no proposal may promote itself" in html
    assert "AI — proposals only" in html
    assert "check — may promote" in html
    # what is not built says so, rather than being left out
    assert "M5 · documents" in html and "M6 · question → readiness" in html
    assert html.count("not built") == 2


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

    assert "Answered by the balance law of" in html
    assert "de_erp__gl_postings.amount_local_currency</code></p>" in html
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
