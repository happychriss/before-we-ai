"""The ReadinessMap: what the system is permitted to claim.

Two guarantees are load-bearing here and each has its own block below.
A verdict of blocked or ready_with_limitations must **name** the
dependency it rests on — a verdict whose reason a reader has to hunt for
is a verdict they will take on trust. And every satisfied item must say
**how**, because since the owner's decision of 2026-07-31 *satisfied* and
*promoted* are different things: a slot field is satisfied by the run that
consumed its column while its own claims stay proposed.
"""

import pytest

from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.model import (
    Actor,
    AnswerRequest,
    ClaimStatus,
    ConceptClaim,
    EvidenceRecord,
    EvidenceType,
    CheckVerdict,
    KnowledgeItem,
    KnowledgeKind,
    MappingClaim,
    Predicate,
    RequiredKnowledge,
    Scope,
    create_claim,
)
from before_we_ai.model.objects import CheckPlan
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.readiness import Ground, Readiness, evaluate, evaluate_request
from before_we_ai.store import ProjectStore, init_project

DE = Scope(entity="DE")


@pytest.fixture
def guide() -> DomainGuide:
    return DomainGuide.model_validate({
        "domain": "finance",
        "objects": {
            "journal": {
                "decided_by": "balance",
                "definition": "the ledger of record",
                "fields": {
                    "amount_local": {"decided_by": "slot", "fills": "amount",
                                     "definition": "the signed amount"},
                    "entity": {"decided_by": "clarification",
                               "definition": "the legal entity"},
                },
            },
        },
    })


@pytest.fixture
def store(tmp_path) -> ProjectStore:
    return ProjectStore(init_project(tmp_path / "p"))


def _obj(name="journal", scope=Scope(), why="the figures come from it"):
    return KnowledgeItem(kind=KnowledgeKind.OBJECT, name=name, why=why,
                         scope=scope)


def _field(name="amount_local", of="journal", scope=Scope()):
    return KnowledgeItem(kind=KnowledgeKind.FIELD, name=name, of_object=of,
                         why="it is what gets summed", scope=scope)


def _rule(name="sign convention for income", scope=Scope()):
    return KnowledgeItem(kind=KnowledgeKind.RULE, name=name,
                         why="it decides profit from loss", scope=scope)


def _map(store, guide, *items) -> "ReadinessMap":
    request = AnswerRequest(question="Can these files produce actual P&L?",
                            requested_output="P&L per entity per month",
                            scope=items[0].scope if items else Scope())
    required = RequiredKnowledge(request_id=request.id, items=list(items))
    return evaluate(store, guide, request, required)


def _candidate(store, role, table, scope=None, status=None):
    claim = MappingClaim(statement=f"role '{role}' is played by {table}",
                         created_by=Actor.AI, role=role, scope=scope,
                         binding={"table": table})
    if status:
        claim = claim.model_copy(update={"status": status})
    store.save_claim(claim)
    return claim


def _passing_balance(store, claim, column="amount_local_currency"):
    plan = CheckPlan(template="balance", roles=[claim.role],
                     params={"journal": claim.binding["table"],
                             "amount": column, "group_column": "period"})
    store.save_check_plan(plan)
    record = EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
                            claim_id=claim.id, check_plan_id=plan.id,
                            verdict=CheckVerdict.PASS, population=100,
                            exception_count=0)
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, []))
    return store.claims[claim.id]


class TestTheVerdict:
    def test_everything_supported_reads_ready(self, store, guide):
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        result = _map(store, guide, _obj())
        assert result.verdict is Readiness.READY
        assert result.reason() == \
            "The one thing this answer depends on is supported."

    def test_a_missing_object_blocks_because_no_number_can_be_produced(
            self, store, guide):
        result = _map(store, guide, _obj())
        assert result.verdict is Readiness.BLOCKED
        assert [i.ref for i in result.blocking()] == ["journal"]

    def test_a_missing_rule_narrows_rather_than_blocks(self, store, guide):
        """The figures exist; what they mean is qualified. That is the
        'narrow the answer' outcome, and the map names the qualification."""
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        result = _map(store, guide, _obj(), _rule())
        assert result.verdict is Readiness.READY_WITH_LIMITATIONS
        assert result.blocking() == []
        assert [i.ref for i in result.limitations()] == \
            ["sign convention for income"]

    def test_a_missing_object_outranks_a_missing_rule(self, store, guide):
        result = _map(store, guide, _obj(), _rule())
        assert result.verdict is Readiness.BLOCKED

    def test_an_empty_requirement_list_is_ready_and_says_so(self, store, guide):
        result = _map(store, guide)
        assert result.verdict is Readiness.READY
        assert result.reason() == \
            "This answer was declared to depend on nothing."

    def test_the_reason_agrees_with_itself_in_number(self, store, guide):
        """One blocker is 'it', several are 'them'. The derived sentences are
        the product's voice; a grammar slip in them reads as carelessness
        about the verdict."""
        one = _map(store, guide, _obj()).reason()
        assert "'journal' is unsupported" in one and "computed from it." in one
        many = _map(store, guide, _obj(), _field()).reason()
        assert "are unsupported" in many and "computed from them." in many


class TestTheVerdictNamesItsDependency:
    """The one thing this product may not ship is a verdict without a
    reason."""

    def test_blocked_names_every_dependency_that_costs_the_numbers(
            self, store, guide):
        result = _map(store, guide, _obj(), _field(), _rule())
        assert result.verdict is Readiness.BLOCKED
        reason = result.reason()
        assert "'journal'" in reason and "'journal.amount_local'" in reason
        assert "the figures are computed from them" in reason

    def test_narrowed_names_what_is_unsettled(self, store, guide):
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        reason = _map(store, guide, _obj(), _rule()).reason()
        assert "'sign convention for income'" in reason
        assert "what they mean is not settled" in reason

    def test_nothing_proposed_is_told_apart_from_tested_and_wrong(
            self, store, guide):
        """Three different jobs for the reader: declare a source, fix the
        data, or answer a question. The map must not blur them."""
        silent = _map(store, guide, _obj("journal")).items[0]
        assert silent.ground is Ground.NOTHING_PROPOSED
        assert "nothing in this project plays it" in silent.because

        wrong = _candidate(store, "journal", "buchungen_report",
                           status=ClaimStatus.CONTRADICTED)
        judged = _map(store, guide, _obj("journal")).items[0]
        assert judged.ground is Ground.ALL_CONTRADICTED
        assert "the data itself has to change" in judged.because
        assert judged.claim_ids == (wrong.id,)

        _candidate(store, "journal", "de_erp__gl")  # proposed, untested
        undecided = _map(store, guide, _obj("journal")).items[0]
        assert undecided.ground is Ground.UNDECIDED
        assert "a human has to answer, or a check has to run" in \
            undecided.because


class TestEverySatisfiedItemSaysHow:
    def test_an_elected_binding_says_its_claim_carries_the_evidence(
            self, store, guide):
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        item = _map(store, guide, _obj()).items[0]
        assert item.ground is Ground.ELECTED
        assert item.because.startswith(
            "Satisfied because its own claim is test-supported")
        assert "de_erp__gl plays 'journal'" in item.because

    def test_a_slot_field_is_satisfied_by_the_derivation_and_says_so(
            self, store, guide):
        """The owner's decision of 2026-07-31: the map reads settled_slots
        and the field's own claims keep their status. An item that said only
        'satisfied' would hide exactly that."""
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"),
                         column="betrag")
        proposed = _candidate(store, "amount_local", "de_erp__gl")

        item = _map(store, guide, _field()).items[0]

        assert item.satisfied and item.ground is Ground.SLOT_DERIVATION
        assert "the balance law of 'journal' passed while reading " \
               "de_erp__gl.betrag" in item.because
        assert "still proposed" in item.because
        # and no promotion happened on the way past
        assert store.claims[proposed.id].status is ClaimStatus.PROPOSED

    def test_a_slot_whose_law_never_ran_is_not_quietly_satisfied(
            self, store, guide):
        _candidate(store, "journal", "de_erp__gl")  # never checked
        item = _map(store, guide, _field()).items[0]
        assert not item.satisfied and item.ground is Ground.NOTHING_PROPOSED

    def test_a_clarification_field_still_needs_its_own_claim(self, store, guide):
        """entity is not a slot: a passing balance says nothing about which
        column names the company, so the derivation must not reach it."""
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        item = _map(store, guide, _field("entity")).items[0]
        assert not item.satisfied

    def test_a_rule_is_satisfied_by_a_claim_that_states_it(self, store, guide):
        claim = ConceptClaim(
            statement="income is stored as a negative amount",
            created_by=Actor.HUMAN, term="sign convention for income",
            definition="income negative, expense positive",
            status=ClaimStatus.BUSINESS_CONFIRMED,
        )
        store.save_claim(claim)
        item = _map(store, guide, _rule()).items[0]
        assert item.satisfied and item.ground is Ground.STATED_RULE
        assert "a business-confirmed claim states it" in item.because
        assert "income is stored as a negative amount" in item.because

    def test_a_rule_stated_only_as_a_proposal_is_not_support(self, store, guide):
        store.save_claim(ConceptClaim(
            statement="income is probably negative", created_by=Actor.AI,
            term="sign convention for income", definition="guessed",
        ))
        item = _map(store, guide, _rule()).items[0]
        assert not item.satisfied and item.ground is Ground.UNDECIDED

    def test_a_rule_matches_a_settled_predicate_claim_too(self, store, guide):
        claim = create_claim("every AR item references a GL posting", Actor.AI,
                             predicate=Predicate(name="references"))
        store.save_claim(claim.model_copy(
            update={"status": ClaimStatus.TEST_SUPPORTED}))
        item = _map(store, guide, _rule("references")).items[0]
        assert item.satisfied and item.ground is Ground.STATED_RULE


class TestScope:
    def test_a_claim_of_the_right_entity_satisfies_a_scoped_item(
            self, store, guide):
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl",
                                           scope=DE))
        item = _map(store, guide, _obj(scope=DE)).items[0]
        assert item.satisfied and "for entity DE" in item.because

    def test_another_entitys_claim_does_not(self, store, guide):
        _passing_balance(store, _candidate(store, "journal", "us_erp__gl",
                                           scope=Scope(entity="US")))
        item = _map(store, guide, _obj(scope=DE)).items[0]
        assert not item.satisfied
        assert "for entity DE" in item.because

    def test_a_landscape_wide_claim_covers_a_scoped_item_and_says_it_does(
            self, store, guide):
        """A shared account master genuinely serves every entity, and "no
        declared owner" is its normal state. The leniency is real, so it is
        stated rather than hidden."""
        _passing_balance(store, _candidate(store, "journal", "shared__gl"))
        item = _map(store, guide, _obj(scope=DE)).items[0]
        assert item.satisfied
        assert "no source declares it as entity DE's" in item.because
        assert "rests on a landscape-wide mapping" in item.because


class TestDerivedNeverStored:
    def test_evaluating_writes_nothing(self, store, guide, tmp_path):
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        before = sorted(p.name for p in (store.root).rglob("*.yaml"))
        _map(store, guide, _obj(), _rule())
        assert sorted(p.name for p in (store.root).rglob("*.yaml")) == before

    def test_the_verdict_follows_the_evidence_when_it_changes(
            self, store, guide):
        claim = _candidate(store, "journal", "de_erp__gl")
        assert _map(store, guide, _obj()).verdict is Readiness.BLOCKED
        _passing_balance(store, claim)
        assert _map(store, guide, _obj()).verdict is Readiness.READY

    def test_evaluate_request_reads_the_stored_request(self, store, guide):
        request = AnswerRequest(question="q?", requested_output="o")
        store.save_request(request)
        store.save_required_knowledge(
            RequiredKnowledge(request_id=request.id, items=[_obj()]))
        result = evaluate_request(store, guide, request.id)
        assert result.verdict is Readiness.BLOCKED
        assert result.request == request

    def test_a_request_nothing_requires_anything_of_has_no_map(
            self, store, guide):
        request = AnswerRequest(question="q?", requested_output="o")
        store.save_request(request)
        assert evaluate_request(store, guide, request.id) is None
        assert evaluate_request(store, guide, "01NOPE") is None
