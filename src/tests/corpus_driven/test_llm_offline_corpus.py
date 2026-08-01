"""M4 offline acceptance: the full LLM pipeline against the frozen corpus,
stub-driven, deterministic, no network.

scan -> V1 hypothesize -> role proposals -> V2 bind -> engine run_ready ->
resolve_mappings, with every LLM answer replayed from recorded fixtures
through the exact validation/mapping path of the real client. Corpus
knowledge (and the fixtures that encode it) stays test-side.

Also home of the **fixture drift guard**: every fixture pins the sha256
of the input it answered; the guard rebuilds those inputs from the frozen
corpus and compares. A prompt or builder change turns this red loudly —
the fix is re-recording fixtures (tests/eval/refresh_fixtures.py online,
or re-authoring by hand), never loosening the guard.
"""

import json
from pathlib import Path

import pytest
import yaml

from before_we_ai import scan
from before_we_ai.engine import run_ready
from before_we_ai.llm import ask, plan_checks, hypothesize, load_domain_guide, propose_mappings, resolve_mappings
from before_we_ai.llm.domain_guide import settled_slots
from before_we_ai.llm.inputs import (
    build_binding_context,
    build_profile_context,
    build_question_context,
    build_role_context,
    claim_label_map,
)
from before_we_ai.llm.mapping import admissible_templates
from before_we_ai.llm.prompts import render_template_docs
from before_we_ai.llm.v2_bind import _untested_claims
from before_we_ai.model import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    KnowledgeKind,
    Scope,
)
from before_we_ai.model.objects import MappingClaim
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.profile.candidates import load_matrix
from before_we_ai.readiness import Ground, Readiness, evaluate_request
from before_we_ai.sources import open_catalog
from before_we_ai.store import ProjectStore, init_project

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm"
DOMAIN_GUIDE_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "domain_guide_finance.yaml"

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

# Tokens that must never reach a prompt: they exist only in test/corpus
# metadata, so their presence in a built input means corpus knowledge leaked
# into the product.
LEAK_TOKENS = ("trap", "decoy", "BLIND_", "expected_verdicts", "F27", "Seeded")

# The question the whole pipeline is answering for. Generic finance, no
# corpus knowledge — it names nothing this landscape happens to contain.
DEMO_QUESTION = "Can these files reliably produce actual P&L by entity and month?"


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    root = init_project(tmp_path_factory.mktemp("llm") / "corpus-llm", name="corpus-llm")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = SOURCES
    config["llm"] = {"offline": True, "fixtures_dir": str(FIXTURES),
                     "domain_guide_file": str(DOMAIN_GUIDE_FILE)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    scan(root)
    store = ProjectStore(root)
    roles = load_domain_guide(DOMAIN_GUIDE_FILE)

    results = {"root": root, "roles": roles}
    results["v4"] = ask(root, DEMO_QUESTION, guide=roles, store=store,
                        scenario="corpus")
    results["v1"] = hypothesize(root, store=store, scenario="corpus")
    results["proposals"] = propose_mappings(root, roles=roles, store=store,
                                                 scenario="corpus")
    results["v2"] = plan_checks(root, store=store, scenario="corpus")
    con = open_catalog(root)
    try:
        results["engine"] = run_ready(store, con)
    finally:
        con.close()
    results["store"] = ProjectStore(root)  # reload from disk
    results["role_cards"] = resolve_mappings(results["store"], roles)
    return results


def test_contracts_ran_clean_offline(pipeline):
    """Pinned against the recorded real answers (Opus 4.8 / Sonnet 5,
    refreshed  after the terminology realignment). A red here
    after a fixture refresh is the guard working: review the new numbers
    and re-pin deliberately."""
    v4, v1 = pipeline["v4"], pipeline["v1"]
    proposals, v2 = pipeline["proposals"], pipeline["v2"]
    assert v4.failure is None and v4.skipped == []
    assert len(v4.required.items) == 9
    assert v1.failure is None
    assert len(v1.claims_created) == 52
    assert v1.claims_deduped == 0
    assert len(v1.skipped) == 3  # residual bad items skipped, batch survived
    assert proposals.failure is None and len(proposals.claims_created) == 22
    assert v2.failures == [] and v2.unanswered == []
    assert len(v2.check_plans_created) == 42
    assert len(v2.skipped) == 7  # validation-rejected bindings — skipped, not crashed
    assert len(v2.semantic_only) == 6  # no admissible template — never sent
    assert len(v2.unbindable) == 19  # honest template=null answers
    assert len(pipeline["engine"].executed) == 42
    assert pipeline["engine"].skipped == []

    # every claim that ends without a check says why, in the store — the reason
    # must outlive the disposable call log
    store = pipeline["store"]
    reasons = {
        record.claim_id: record.payload
        for record in store.evidence.values()
        if record.type is EvidenceType.DECLARATION and "decision" in record.payload
    }
    assert len(reasons) == 32  # 19 unbindable + 6 semantic-only + 7 skipped
    assert sorted(p["decision"] for p in reasons.values()) == (
        ["semantic_only"] * 6 + ["skipped"] * 7 + ["unbindable"] * 19
    )
    assert all(p["reason"] for p in reasons.values())  # never an empty reason
    for claim_id in reasons:
        assert store.claims[claim_id].status is ClaimStatus.PROPOSED


def test_llm_path_cannot_promote(pipeline):
    """False-Promotion = 0 on the LLM path: every AI-created object was an
    proposed claim or a check; status changes came from check evidence only."""
    store = pipeline["store"]
    ai_claims = [c for c in store.claims.values() if c.created_by is Actor.AI]
    assert len(ai_claims) == 74  # 52 hypotheses + 22 role candidates
    for evidence in store.evidence.values():
        assert evidence.actor is not Actor.AI
    # promotions happened, but only through check evidence
    for claim in ai_claims:
        if claim.status is not ClaimStatus.PROPOSED:
            assert any(
                store.evidence[eid].actor is Actor.CHECK
                for eid in claim.evidence_ids
            )


def test_verdicts_land_on_the_corpus_ground_truth(pipeline):
    """The invariants decided the journal — the epistemic heart of M4: the
    real ledger wins, the F27 decoy loses, the US ledger honestly fails on
    the F22 imbalance. In this recording the model declined to bind the
    intercompany invariant (template=null), so those candidates stay
    proposed and settle via a clarification question — the honest path,
    never a silent discard."""
    store = pipeline["store"]

    def role_claims(role: str, token: str):
        return [c for c in store.claims.values()
                if isinstance(c, MappingClaim) and c.role == role
                and any(token in v for v in c.binding.values())]

    (gl,) = role_claims("journal", "de_erp__gl_postings")
    assert gl.status is ClaimStatus.TEST_SUPPORTED
    (decoy,) = role_claims("journal", "buchungen_report")
    assert decoy.status is ClaimStatus.CONTRADICTED  # F27
    (us_gl,) = role_claims("journal", "us_erp__gl_postings")
    assert us_gl.status is ClaimStatus.CONTRADICTED  # F22 missing IC leg
    ic = [c for c in store.claims.values()
          if isinstance(c, MappingClaim) and c.role == "intercompany"]
    assert ic and all(c.status is ClaimStatus.PROPOSED for c in ic)  # unbound this recording
    # claims V2 could not bind stay proposed — visible, never promoted
    unbound_ids = {cid for cid, _ in pipeline["v2"].unbindable}
    assert all(store.claims[cid].status is ClaimStatus.PROPOSED
               for cid in unbound_ids)
    # semantic-only claims (T7 class among them) stay proposed
    for cid in pipeline["v2"].semantic_only:
        assert store.claims[cid].status is ClaimStatus.PROPOSED


def test_every_unsettled_role_becomes_a_clarification_not_a_silent_discard(pipeline):
    """Every object and every clarification-decided field ends in a check
    verdict or a clarification question: in this recording the laws of
    intercompany and subledger_ar could never be bound to a candidate (honest
    template=null); the four clarification-decided journal fields (account,
    doc_ref, entity, period) list their candidates for the humans to choose.
    The settled object (journal) drafts nothing — and neither does its
    amount_local slot, which the passing balance run answered."""
    cards = pipeline["role_cards"]
    by_role = {}
    for card in cards:
        role = card.question.split("'")[1]
        by_role[role] = card
    assert sorted(by_role) == [
        "account", "doc_ref", "entity", "intercompany", "period",
        "subledger_ar",
    ]
    ic = by_role["intercompany"]
    # never bound: the law never got to speak, so the question asks what is
    # missing rather than which candidate lost
    assert "What is missing before the 'intercompany' can be tested?" in ic.question
    assert "could be put to the ic_symmetry law at all" in ic.question
    assert len(ic.claim_ids) == 2  # both candidates attached
    assert ("What is missing before the 'subledger_ar' can be tested?"
            in by_role["subledger_ar"].question)
    for role in ("account", "doc_ref", "entity", "period"):
        card = by_role[role]
        assert f"Which of the proposed candidates is the '{role}'?" in card.question
        # the guide's definition is in the question; the candidates are links
        assert "business fact, not an arithmetic one" in card.question
        assert "de_erp__gl_postings" not in card.question
        assert card.claim_ids  # the candidates ride along, answerable in one pick
    # resolution is idempotent
    assert resolve_mappings(pipeline["store"], pipeline["roles"]) == []


def test_the_slot_of_a_settled_object_is_answered_not_asked(pipeline):
    """What the guide restructure bought: amount_local is a slot of the
    journal's balance law, so the passing run on the elected ledger *is* its
    answer — no question about knowledge that was never missing. The column
    named here is the one the check actually consumed."""
    assert settled_slots(pipeline["store"], pipeline["roles"], "journal") == {
        "amount_local": "de_erp__gl_postings.amount_local_currency"
    }
    # ... and a law that never ran answers nothing
    assert settled_slots(pipeline["store"], pipeline["roles"], "subledger_ar") == {}


def test_call_logs_are_complete(pipeline):
    logs = sorted((pipeline["root"] / "cache" / "llm_log").glob("*.json"))
    assert len(logs) == 5  # v4, v1, role proposals, v2 role batch, v2 claim batch
    outcomes = []
    for path in logs:
        entry = json.loads(path.read_text(encoding="utf-8"))
        assert entry["provider"] == "stub"
        assert entry["input_sha256"]
        assert entry["request"]["system"] and entry["request"]["user"]
        outcomes.append(entry["outcome"])
        if entry["outcome"] == "partial":
            assert entry["attempts"][-1]["validation_errors"]  # skips are visible
    # the recorded V1 and V2-claims answers keep a few bad items even after
    # their retry — replayed as "partial", same items skipped every run
    assert sorted(outcomes) == ["ok", "ok", "ok", "partial", "partial"]


def test_pipeline_is_idempotent(pipeline):
    """Re-running the contracts creates nothing new — claim-key dedup for
    claims; bound claims drop out of the V2 selection entirely."""
    root, store = pipeline["root"], pipeline["store"]
    again = hypothesize(root, store=store, scenario="corpus")
    assert again.claims_created == [] and again.claims_deduped == 52
    proposals = propose_mappings(root, roles=pipeline["roles"], store=store,
                                      scenario="corpus")
    assert proposals.claims_created == [] and proposals.claims_deduped == 22
    # only the honestly unbound claims are still selectable for V2:
    # 19 unbindable + 6 semantic-only + 7 skipped bindings
    assert len(_untested_claims(store, None)) == 32


def test_built_inputs_leak_no_corpus_hints(pipeline):
    store, root = pipeline["store"], pipeline["root"]
    matrix = load_matrix(root)
    built = build_profile_context(store, matrix)
    role_built = build_role_context(store, matrix, pipeline["roles"])
    question_built = build_question_context(DEMO_QUESTION, pipeline["roles"])
    for text in (built.text, role_built.text, question_built.text):
        lowered = text.lower()
        for token in LEAK_TOKENS:
            assert token.lower() not in lowered, f"built input leaks {token!r}"


# --- M6 acceptance: the six demo behaviours -------------------------------
#
# The acceptance criteria of the narrow demo (findings §12), run against the
# frozen corpus and its *recorded real* answers rather than a hand-authored
# demo set: identify both journal candidates, contradict the wrong one,
# surface the missing business rule, ask one focused clarification, build the
# ReadinessMap, and permit / narrow / block the answer. Numbers here are
# pinned to the recording, like every other assertion in this module.


def _readiness(pipeline):
    store = pipeline["store"]
    request = pipeline["v4"].request
    return evaluate_request(store, pipeline["roles"], request.id)


def test_demo_1_and_2_both_journals_are_found_and_the_wrong_one_is_contradicted(pipeline):
    """The decoy is an *attractive* wrong answer — a plausible-looking
    posting export. Nothing about its shape says so; the balance law does."""
    store = pipeline["store"]
    journals = [c for c in store.claims.values()
                if isinstance(c, MappingClaim) and c.role == "journal"]
    tables = {c.binding.get("table", "") for c in journals}
    assert any("de_erp__gl_postings" in t for t in tables)
    assert any("buchungen_report" in t for t in tables)
    (decoy,) = [c for c in journals if "buchungen_report" in c.binding.get("table", "")]
    assert decoy.status is ClaimStatus.CONTRADICTED


def test_demo_3_the_rules_no_column_layout_reveals_are_surfaced_by_name(pipeline):
    """The three conventions a P&L rests on and no data can supply. They are
    listed as required knowledge and then found unsupported — the opposite of
    the failure mode where an answer is produced as if they were known."""
    result = _readiness(pipeline)
    rules = {i.ref for i in result.items
             if i.item.kind is KnowledgeKind.RULE}
    assert rules == {
        "which accounts are profit and loss",
        "sign convention for income and expense",
        "month cut-off for late postings",
    }
    assert all(not i.satisfied for i in result.items
               if i.item.kind is KnowledgeKind.RULE)


def test_demo_4_the_clarifications_are_focused_and_scoped_to_the_question(pipeline):
    """Six cards, each about one role, none of them a wall of candidates."""
    cards = pipeline["role_cards"]
    assert len(cards) == 6
    for card in cards:
        assert card.question.count("?") == 1
        assert len(card.question) < 320


def test_demo_5_the_readiness_map_covers_every_required_item(pipeline):
    result = _readiness(pipeline)
    assert len(result.items) == len(pipeline["v4"].required.items) == 9
    # nothing is silent: every item carries a derived sentence saying where
    # it stands, satisfied or not
    assert all(i.because for i in result.items)
    assert all(i.because.startswith(("Satisfied because", "Not supported:"))
               for i in result.items)


def test_demo_6_the_answer_is_blocked_and_the_blockers_are_named(pipeline):
    """The honest verdict on this landscape: the ledger of record is
    identified and its amount column is settled by the run that consumed it —
    but nothing yet says which column carries the entity or the period, and a
    P&L *by entity and month* is computed from exactly those."""
    result = _readiness(pipeline)
    assert result.verdict is Readiness.BLOCKED

    satisfied = {i.ref: i.ground for i in result.items if i.satisfied}
    assert satisfied == {
        "journal": Ground.ELECTED,
        "journal.amount_local": Ground.SLOT_DERIVATION,
    }
    assert sorted(i.ref for i in result.blocking()) == [
        "intercompany", "journal.account", "journal.entity", "journal.period",
    ]
    reason = result.reason()
    for blocker in ("journal.entity", "journal.period", "journal.account"):
        assert f"'{blocker}'" in reason
    assert "the figures are computed from them" in reason


def test_demo_6_answering_the_clarifications_narrows_instead_of_blocking(pipeline,
                                                                        tmp_path):
    """The other side of "permit, narrow, or block". A human answers the four
    open mapping questions; the figures become computable, and what is left
    is what they *mean* — so the verdict narrows rather than clearing. The
    three conventions are named as the limitations they are."""
    store = ProjectStore(pipeline["root"])  # a private reload; the module
    for card in pipeline["role_cards"]:     # fixture must stay untouched
        # what answering a card *is*: the human picks one of its candidates
        picked = store.claims[card.claim_ids[0]]
        record = EvidenceRecord(
            type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN,
            claim_id=picked.id, scope=Scope(entity="DE"),
        )
        store.add_evidence(record)
        store.save_claim(attach_evidence(picked, record,
                                         store.evidence_for(picked)))

    result = evaluate_request(store, pipeline["roles"],
                              pipeline["v4"].request.id)

    assert result.verdict is Readiness.READY_WITH_LIMITATIONS
    assert result.blocking() == []
    assert sorted(i.ref for i in result.limitations()) == [
        "month cut-off for late postings",
        "sign convention for income and expense",
        "which accounts are profit and loss",
    ]
    assert "what they mean is not settled" in result.reason()
    # and the promotions came from the human, never from the AI
    for item in result.items:
        for claim_id in item.claim_ids:
            claim = store.claims[claim_id]
            if claim.status is ClaimStatus.BUSINESS_CONFIRMED:
                assert any(store.evidence[eid].actor is Actor.HUMAN
                           for eid in claim.evidence_ids)


def test_the_readiness_map_never_writes_anything(pipeline):
    """Derived, never stored — the same discipline as claim status."""
    root = pipeline["root"]
    before = {p: p.stat().st_mtime_ns for p in sorted(root.rglob("*.yaml"))}
    _readiness(pipeline)
    assert {p: p.stat().st_mtime_ns for p in sorted(root.rglob("*.yaml"))} == before


def test_fixtures_match_current_inputs(pipeline):
    """THE drift guard: each fixture answered a specific input; rebuild those
    inputs from the frozen corpus and compare hashes. Red here means a
    builder/prompt/profile change made the recorded answers stale — refresh
    the fixtures, do not touch this test."""
    store, root = pipeline["store"], pipeline["root"]
    matrix = load_matrix(root)

    def fixture(name: str) -> dict:
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))

    assert fixture("v4_request__corpus")["input_sha256"] == \
        build_question_context(DEMO_QUESTION, pipeline["roles"]).sha256
    assert fixture("v1_hypotheses__corpus")["input_sha256"] == \
        build_profile_context(store, matrix).sha256
    assert fixture("role_binding__corpus")["input_sha256"] == \
        build_role_context(store, matrix, pipeline["roles"]).sha256

    # reconstruct the V2 batches exactly as plan_checks selects them, from a
    # claim set as it stood before binding (checks exclude claims, so take
    # all AI claims and ignore the bound-filter)
    ai_claims = sorted(
        (c for c in store.claims.values()
         if c.created_by is Actor.AI and c.predicate is not None),
        key=lambda c: c.id,
    )
    role_claims = [c for c in ai_claims if isinstance(c, MappingClaim)]
    ordinary = [c for c in ai_claims
                if not isinstance(c, MappingClaim) and admissible_templates(c)]
    docs = render_template_docs()
    assert fixture("v2_bind__corpus_roles")["input_sha256"] == \
        build_binding_context(store, claim_label_map(role_claims), docs).sha256
    assert fixture("v2_bind__corpus_claims")["input_sha256"] == \
        build_binding_context(store, claim_label_map(ordinary), docs).sha256
