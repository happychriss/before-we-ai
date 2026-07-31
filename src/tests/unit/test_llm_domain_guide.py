"""The role-pack lint and the no-silence rule of resolve_mappings.

A domain guide must declare, per role, how it can ever be settled
(decided_by) — and resolve_mappings must leave no non-slot role without a
check verdict or a clarification question."""

import pytest

from before_we_ai.llm.domain_guide import DomainGuide, resolve_mappings
from before_we_ai.model import Actor, EvidenceRecord, EvidenceType, CheckVerdict
from before_we_ai.model.objects import MappingClaim
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.store import ProjectStore, init_project


def _pack(**roles) -> DomainGuide:
    return DomainGuide(domain="finance", roles={
        name: {"definition": f"the {name}", "decided_by": decided_by}
        for name, decided_by in roles.items()
    })


def _candidate(store, role, table):
    claim = MappingClaim(
        statement=f"role '{role}' is played by {table}",
        created_by=Actor.AI,
        role=role,
        binding={"table": table},
    )
    store.save_claim(claim)
    return claim


def _fail_check(store, claim):
    record = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
        claim_id=claim.id, verdict=CheckVerdict.FAIL,
        population=100, exception_count=3,
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, []))


def _declare_unbindable(store, claim):
    record = EvidenceRecord(
        type=EvidenceType.DECLARATION, actor=Actor.SYSTEM,
        claim_id=claim.id,
        payload={"decision": "unbindable", "reason": "knowledge missing"},
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, []))


def test_lint_rejects_a_role_without_a_settlement_path():
    with pytest.raises(ValueError, match="domain guide lint"):
        DomainGuide(domain="finance", roles={
            "journal": {"definition": "the ledger", "decided_by": "no_such"},
        })


def test_lint_rejects_a_generic_template_as_decider():
    # anti_join exists but is generic — it cannot elect a role
    with pytest.raises(ValueError, match="cannot elect a role"):
        _pack(journal="anti_join")


def test_lint_rejects_a_law_of_another_domain():
    with pytest.raises(ValueError, match="not a domain law of 'logistics'"):
        DomainGuide(domain="logistics", roles={
            "journal": {"definition": "the ledger", "decided_by": "balance"},
        })


def test_lint_accepts_the_three_settlement_paths():
    pack = _pack(journal="balance", period="clarification", entity="slot")
    assert pack.names == ["journal", "period", "entity"]


def test_checked_and_lost_role_drafts_the_lost_clarification(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    claim = _candidate(store, "intercompany", "de_erp__intercompany")
    _fail_check(store, claim)
    cards = resolve_mappings(store, _pack(intercompany="ic_symmetry"))
    assert len(cards) == 1
    assert "no proposed binding passed its invariant check" in cards[0].question


def test_law_that_could_never_be_bound_drafts_a_clarification(tmp_path):
    """The subledger_ar case: check-decidable, candidates exist, but V2
    declared every one unbindable — knowledge is missing to apply the law."""
    store = ProjectStore(init_project(tmp_path / "p"))
    for table in ("de_erp__ar_open_items", "us_erp__ar_open_items"):
        _declare_unbindable(store, _candidate(store, "subledger_ar", table))
    cards = resolve_mappings(store, _pack(subledger_ar="subledger_equals_gl"))
    assert len(cards) == 1
    assert "what domain knowledge is missing" in cards[0].question
    assert len(cards[0].claim_ids) == 2


def test_pending_candidates_draft_nothing(tmp_path):
    """No check result AND no V2 declaration = binding still in flight —
    a question about an untried binding would be noise."""
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "journal", "de_erp__gl_postings")
    assert resolve_mappings(store, _pack(journal="balance")) == []


def test_clarification_role_lists_its_candidates(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "period", "de_erp__gl_postings")
    _candidate(store, "period", "buchungen_report")
    cards = resolve_mappings(store, _pack(period="clarification"))
    assert len(cards) == 1
    assert "which binding applies" in cards[0].question
    # candidates listed, deterministically sorted — answerable in one pick
    assert cards[0].question.index("buchungen_report") < cards[0].question.index(
        "de_erp__gl_postings"
    )
    assert len(cards[0].claim_ids) == 2


def test_role_with_no_candidate_drafts_a_clarification_once_search_ran(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    # before any proposal ran: an empty landscape asks nothing
    assert resolve_mappings(store, _pack(period="clarification")) == []
    # the search ran (some role got candidates) but this role got none
    _candidate(store, "journal", "de_erp__gl_postings")
    cards = resolve_mappings(store, _pack(journal="balance", period="clarification"))
    assert [c.question for c in cards] == [
        "Clarification question: no candidate was proposed for the role "
        "'period' — does this role exist in this data landscape?"
    ]


def test_slot_roles_never_draft_anything(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "journal", "de_erp__gl_postings")
    assert resolve_mappings(store, _pack(journal="balance", entity="slot")) == []


def test_resolution_is_idempotent(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "period", "de_erp__gl_postings")
    first = resolve_mappings(store, _pack(period="clarification"))
    assert len(first) == 1
    assert resolve_mappings(store, _pack(period="clarification")) == []
