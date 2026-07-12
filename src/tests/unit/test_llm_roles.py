"""The role-pack lint and the no-silence rule of resolve_roles.

A role pack must declare, per role, how it can ever be settled
(decided_by) — and resolve_roles must leave no non-slot role without a
probe verdict or a Fachfrage."""

import pytest

from before_we_ai.llm.roles import RoleSet, resolve_roles
from before_we_ai.model import Actor, EvidenceRecord, EvidenceType, ProbeVerdict
from before_we_ai.model.objects import RoleBindingClaim
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.store import ProjectStore, init_project


def _pack(**roles) -> RoleSet:
    return RoleSet(domain="finance", roles={
        name: {"definition": f"the {name}", "decided_by": decided_by}
        for name, decided_by in roles.items()
    })


def _candidate(store, role, table):
    claim = RoleBindingClaim(
        statement=f"role '{role}' is played by {table}",
        created_by=Actor.AI,
        role=role,
        binding={"table": table},
    )
    store.save_claim(claim)
    return claim


def _fail_probe(store, claim):
    record = EvidenceRecord(
        type=EvidenceType.PROBE_RESULT, actor=Actor.PROBE,
        claim_id=claim.id, verdict=ProbeVerdict.FAIL,
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
    with pytest.raises(ValueError, match="role pack lint"):
        RoleSet(domain="finance", roles={
            "journal": {"definition": "the ledger", "decided_by": "no_such"},
        })


def test_lint_rejects_a_generic_template_as_decider():
    # anti_join exists but is generic — it cannot elect a role
    with pytest.raises(ValueError, match="cannot elect a role"):
        _pack(journal="anti_join")


def test_lint_rejects_a_law_of_another_domain():
    with pytest.raises(ValueError, match="not a domain law of 'logistics'"):
        RoleSet(domain="logistics", roles={
            "journal": {"definition": "the ledger", "decided_by": "balance"},
        })


def test_lint_accepts_the_three_settlement_paths():
    pack = _pack(journal="balance", period="fachfrage", entity="slot")
    assert pack.names == ["journal", "period", "entity"]


def test_probed_and_lost_role_drafts_the_lost_fachfrage(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    claim = _candidate(store, "intercompany", "de_erp__intercompany")
    _fail_probe(store, claim)
    cards = resolve_roles(store, _pack(intercompany="ic_symmetry"))
    assert len(cards) == 1
    assert "Invarianten-Sonde bestanden" in cards[0].question


def test_law_that_could_never_be_bound_drafts_a_fachfrage(tmp_path):
    """The subledger_ar case: probe-decidable, candidates exist, but V2
    declared every one unbindable — knowledge is missing to apply the law."""
    store = ProjectStore(init_project(tmp_path / "p"))
    for table in ("de_erp__ar_open_items", "us_erp__ar_open_items"):
        _declare_unbindable(store, _candidate(store, "subledger_ar", table))
    cards = resolve_roles(store, _pack(subledger_ar="subledger_equals_gl"))
    assert len(cards) == 1
    assert "welches Fachwissen fehlt" in cards[0].question
    assert len(cards[0].claim_ids) == 2


def test_pending_candidates_draft_nothing(tmp_path):
    """No probe result AND no V2 declaration = binding still in flight —
    a question about an untried binding would be noise."""
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "journal", "de_erp__gl_postings")
    assert resolve_roles(store, _pack(journal="balance")) == []


def test_fachfrage_role_lists_its_candidates(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "period", "de_erp__gl_postings")
    _candidate(store, "period", "buchungen_report")
    cards = resolve_roles(store, _pack(period="fachfrage"))
    assert len(cards) == 1
    assert "welche Bindung gilt" in cards[0].question
    # candidates listed, deterministically sorted — answerable in one pick
    assert cards[0].question.index("buchungen_report") < cards[0].question.index(
        "de_erp__gl_postings"
    )
    assert len(cards[0].claim_ids) == 2


def test_role_with_no_candidate_drafts_a_fachfrage_once_search_ran(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    # before any proposal ran: an empty landscape asks nothing
    assert resolve_roles(store, _pack(period="fachfrage")) == []
    # the search ran (some role got candidates) but this role got none
    _candidate(store, "journal", "de_erp__gl_postings")
    cards = resolve_roles(store, _pack(journal="balance", period="fachfrage"))
    assert [c.question for c in cards] == [
        "Fachfrage: Für die Rolle 'period' wurde kein Kandidat vorgeschlagen — "
        "gibt es diese Rolle in dieser Datenlandschaft?"
    ]


def test_slot_roles_never_draft_anything(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "journal", "de_erp__gl_postings")
    assert resolve_roles(store, _pack(journal="balance", entity="slot")) == []


def test_resolution_is_idempotent(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "period", "de_erp__gl_postings")
    first = resolve_roles(store, _pack(period="fachfrage"))
    assert len(first) == 1
    assert resolve_roles(store, _pack(period="fachfrage")) == []
