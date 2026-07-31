"""The domain-guide coherence lint and the no-silence rule of resolve_mappings.

A guide is business objects with fields. An object declares how it can ever
be settled (a domain law, or a clarification question); a field is a slot of
its object's law or a clarification — and **a field can never declare a
law**. resolve_mappings must leave no object and no clarification-decided
field without a check verdict or a clarification question, and must not let a
slot disappear into a law that never consumed it."""

import pytest

from before_we_ai.llm.domain_guide import (
    DomainGuide,
    resolve_mappings,
    settled_slots,
)
from before_we_ai.model import Actor, EvidenceRecord, EvidenceType, CheckVerdict
from before_we_ai.model.objects import CheckPlan, MappingClaim
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.store import ProjectStore, init_project


def _guide(**objects) -> DomainGuide:
    """Each keyword is one object: ``name=decided_by`` or
    ``name=(decided_by, {field: {"decided_by": ..., "fills": ...}})``."""
    spec = {}
    for name, value in objects.items():
        decided_by, fields = value if isinstance(value, tuple) else (value, {})
        spec[name] = {
            "definition": f"the {name}",
            "decided_by": decided_by,
            "fields": {fname: {"definition": f"the {fname}", **fspec}
                       for fname, fspec in fields.items()},
        }
    return DomainGuide(domain="finance", objects=spec)


_SLOT_AMOUNT = {"amount_local": {"decided_by": "slot", "fills": "amount"}}


def _candidate(store, role, table, binding=None):
    claim = MappingClaim(
        statement=f"role '{role}' is played by {table}",
        created_by=Actor.AI,
        role=role,
        binding=binding or {"table": table},
    )
    store.save_claim(claim)
    return claim


def _check(store, claim, verdict, template="balance", params=None):
    plan = CheckPlan(template=template, roles=[claim.role],
                     params=params if params is not None else {})
    store.save_check_plan(plan)
    record = EvidenceRecord(
        type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
        claim_id=claim.id, check_plan_id=plan.id, verdict=verdict,
        population=100, exception_count=0 if verdict is CheckVerdict.PASS else 3,
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, []))
    return plan


def _fail_check(store, claim):
    _check(store, claim, CheckVerdict.FAIL)


def _passing_journal(store, params=None):
    """The elected journal: balance passed, consuming an amount column."""
    claim = _candidate(store, "journal", "de_erp__gl_postings")
    _check(store, claim, CheckVerdict.PASS, params=params if params is not None
           else {"journal": "de_erp__gl_postings",
                 "amount": "amount_local_currency",
                 "group_column": "period"})
    return claim


def _declare_unbindable(store, claim):
    record = EvidenceRecord(
        type=EvidenceType.DECLARATION, actor=Actor.SYSTEM,
        claim_id=claim.id,
        payload={"decision": "unbindable", "reason": "knowledge missing"},
    )
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, []))


# --- the lint -------------------------------------------------------------

def test_lint_rejects_an_object_without_a_settlement_path():
    with pytest.raises(ValueError, match="domain guide lint"):
        _guide(journal="no_such")


def test_lint_rejects_a_generic_template_as_decider():
    # anti_join exists but is generic — it cannot elect an object
    with pytest.raises(ValueError, match="cannot elect an object"):
        _guide(journal="anti_join")


def test_lint_rejects_a_law_of_another_domain():
    with pytest.raises(ValueError, match="not a domain law of 'logistics'"):
        DomainGuide(domain="logistics", objects={
            "journal": {"definition": "the ledger", "decided_by": "balance"},
        })


def test_lint_rejects_an_object_declared_as_a_slot():
    with pytest.raises(ValueError, match="an object is what a law judges"):
        _guide(journal="slot")


def test_lint_rejects_a_field_that_declares_a_law():
    """The amount_local bug class: the amount is a slot of the journal's
    balance law, never the owner of one. The schema keeps this out of any
    guide — the lint says so in words."""
    with pytest.raises(ValueError, match="a field can never declare a law"):
        _guide(journal=("balance",
                        {"amount_local": {"decided_by": "balance"}}))


def test_lint_rejects_a_slot_the_law_does_not_have():
    with pytest.raises(ValueError, match="fills 'grouping' is no slot"):
        _guide(journal=("balance", {"doc_ref": {"decided_by": "slot",
                                                "fills": "grouping"}}))


def test_lint_rejects_two_fields_in_one_slot():
    with pytest.raises(ValueError, match="one slot, one field"):
        _guide(journal=("balance", {
            "amount_local": {"decided_by": "slot", "fills": "amount"},
            "amount_doc": {"decided_by": "slot", "fills": "amount"},
        }))


def test_lint_rejects_a_slot_without_a_law_to_ride():
    with pytest.raises(ValueError, match="a slot needs a law to ride"):
        _guide(journal=("clarification", _SLOT_AMOUNT))


def test_lint_rejects_a_slot_that_names_no_law_slot():
    with pytest.raises(ValueError, match="must name the law slot it fills"):
        _guide(journal=("balance", {"amount_local": {"decided_by": "slot"}}))


def test_lint_rejects_fills_on_a_clarification_field():
    with pytest.raises(ValueError, match="'fills' is meaningless"):
        _guide(journal=("balance", {"period": {"decided_by": "clarification",
                                               "fills": "amount"}}))


def test_lint_rejects_a_name_used_twice():
    with pytest.raises(ValueError, match="already taken in this guide"):
        _guide(journal=("balance", {"journal": {"decided_by": "clarification"}}))


def test_lint_accepts_objects_with_fields_and_flattens_them_in_order():
    guide = _guide(
        journal=("balance", {**_SLOT_AMOUNT,
                             "period": {"decided_by": "clarification"}}),
        intercompany="ic_symmetry",
    )
    assert guide.names == ["journal", "amount_local", "period", "intercompany"]
    assert guide.owner_of("amount_local") == "journal"
    assert guide.owner_of("journal") is None


# --- resolution: objects --------------------------------------------------

def test_checked_and_lost_object_drafts_the_lost_clarification(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    claim = _candidate(store, "intercompany", "de_erp__intercompany")
    _fail_check(store, claim)
    cards = resolve_mappings(store, _guide(intercompany="ic_symmetry"))
    assert len(cards) == 1
    assert "no proposed binding passed its invariant check" in cards[0].question


def test_law_that_could_never_be_bound_drafts_a_clarification(tmp_path):
    """The subledger_ar case: check-decidable, candidates exist, but V2
    declared every one unbindable — knowledge is missing to apply the law."""
    store = ProjectStore(init_project(tmp_path / "p"))
    for table in ("de_erp__ar_open_items", "us_erp__ar_open_items"):
        _declare_unbindable(store, _candidate(store, "subledger_ar", table))
    cards = resolve_mappings(store, _guide(subledger_ar="subledger_equals_gl"))
    assert len(cards) == 1
    assert "what domain knowledge is missing" in cards[0].question
    assert len(cards[0].claim_ids) == 2


def test_pending_candidates_draft_nothing(tmp_path):
    """No check result AND no V2 declaration = binding still in flight —
    a question about an untried binding would be noise."""
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "journal", "de_erp__gl_postings")
    assert resolve_mappings(store, _guide(journal="balance")) == []


def test_clarification_field_lists_its_candidates(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "journal", "de_erp__gl_postings")  # still in flight
    _candidate(store, "period", "de_erp__gl_postings")
    _candidate(store, "period", "buchungen_report")
    guide = _guide(journal=("balance", {"period": {"decided_by": "clarification"}}))
    cards = resolve_mappings(store, guide)
    assert len(cards) == 1
    assert "which binding applies" in cards[0].question
    # candidates listed, deterministically sorted — answerable in one pick
    assert cards[0].question.index("buchungen_report") < cards[0].question.index(
        "de_erp__gl_postings"
    )
    assert len(cards[0].claim_ids) == 2


def test_entry_with_no_candidate_drafts_a_clarification_once_search_ran(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    guide = _guide(journal=("balance", {"period": {"decided_by": "clarification"}}))
    # before any proposal ran: an empty landscape asks nothing
    assert resolve_mappings(store, guide) == []
    # the search ran (some entry got candidates) but this field got none
    _candidate(store, "journal", "de_erp__gl_postings")
    cards = resolve_mappings(store, guide)
    assert [c.question for c in cards] == [
        "Clarification question: no candidate was proposed for the role "
        "'period' — does this role exist in this data landscape?"
    ]


# --- resolution: slot fields ride their object's law ----------------------

def test_slot_settles_with_the_column_the_passing_law_consumed(tmp_path):
    """The evidence was always there: the journal's balance check passed
    *with* amount=amount_local_currency. So the posting amount is answered —
    asking 'what domain knowledge is missing?' was the bug."""
    store = ProjectStore(init_project(tmp_path / "p"))
    _passing_journal(store)
    _declare_unbindable(store, _candidate(
        store, "amount_local", "de_erp__gl_postings",
        binding={"table": "de_erp__gl_postings",
                 "amount": "de_erp__gl_postings.amount_local_currency"}))
    guide = _guide(journal=("balance", _SLOT_AMOUNT))
    assert settled_slots(store, guide, "journal") == {
        "amount_local": "de_erp__gl_postings.amount_local_currency"
    }
    assert resolve_mappings(store, guide) == []


def test_slot_of_an_unsettled_object_rides_the_object_question(tmp_path):
    """No verdict on the journal yet: its own question carries the field.
    Two questions about one unknown would be noise, not honesty."""
    store = ProjectStore(init_project(tmp_path / "p"))
    _fail_check(store, _candidate(store, "journal", "buchungen_report"))
    _candidate(store, "amount_local", "buchungen_report")
    guide = _guide(journal=("balance", _SLOT_AMOUNT))
    cards = resolve_mappings(store, guide)
    assert [c.question.split("'")[1] for c in cards] == ["journal"]
    assert settled_slots(store, guide, "journal") == {}


def test_a_slot_may_ride_a_law_but_not_vanish_into_it(tmp_path):
    """The object settled, but the passing run consumed no column for the
    slot — that is a gap, and a gap is a question, never a silence."""
    store = ProjectStore(init_project(tmp_path / "p"))
    _passing_journal(store, params={"journal": "de_erp__gl_postings",
                                    "group_column": "period"})
    _candidate(store, "amount_local", "de_erp__gl_postings")
    cards = resolve_mappings(store, _guide(journal=("balance", _SLOT_AMOUNT)))
    assert len(cards) == 1
    assert "rides the 'balance' law of 'journal' as its 'amount'" in cards[0].question
    assert cards[0].claim_ids  # the candidate rides along, answerable in one pick


def test_settled_object_still_answers_its_clarification_fields(tmp_path):
    """A passing balance run proves the ledger conserves; it says nothing
    about what its grouping column *means* — doc_ref stays a question."""
    store = ProjectStore(init_project(tmp_path / "p"))
    _passing_journal(store)
    _candidate(store, "doc_ref", "de_erp__gl_postings")
    guide = _guide(journal=("balance", {
        **_SLOT_AMOUNT, "doc_ref": {"decided_by": "clarification"}}))
    cards = resolve_mappings(store, guide)
    assert [c.question.split("'")[1] for c in cards] == ["doc_ref"]


def test_resolution_is_idempotent(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"))
    _candidate(store, "journal", "de_erp__gl_postings")  # still in flight
    _candidate(store, "period", "de_erp__gl_postings")
    guide = _guide(journal=("balance", {"period": {"decided_by": "clarification"}}))
    first = resolve_mappings(store, guide)
    assert len(first) == 1
    assert resolve_mappings(store, guide) == []
