"""The ReadinessMap: what the system is permitted to claim.

Two guarantees are load-bearing here and each has its own block below.
A verdict of blocked or ready_with_limitations must **name** the
dependency it rests on — a verdict whose reason a reader has to hunt for
is a verdict they will take on trust. And every satisfied item must say
**how**, because *satisfied* and *promoted* are different things: a slot
field is satisfied by the run that consumed its column while its own claims
stay proposed.
"""

import pytest
from pydantic import ValidationError

from before_we_ai.llm.domain_guide import DomainGuide, load_domain_guide
from before_we_ai.core import (
    Actor,
    AnswerRequest,
    ClaimStatus,
    ConceptClaim,
    EvidenceRecord,
    EvidenceType,
    CheckVerdict,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeLink,
    MappingClaim,
    Predicate,
    Provenance,
    RequiredKnowledge,
    Scope,
    create_claim,
)
from before_we_ai.core.objects import CheckPlan
from before_we_ai.core.transitions import attach_evidence
from before_we_ai.readiness import (
    Ground,
    Readiness,
    UnlinkableItem,
    add_item,
    assemble,
    confirm_classification,
    evaluate,
    evaluate_request,
    link_claim,
    require_again,
    waive_item,
)
from before_we_ai.store import ProjectStore, check_integrity, init_project

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


def _rule(name="sign convention for income", scope=Scope(), links=None):
    return KnowledgeItem(kind=KnowledgeKind.RULE, name=name,
                         why="it decides profit from loss", scope=scope,
                         satisfied_by=links or [])


def _link(claim, linked_by=Actor.HUMAN, note=""):
    return KnowledgeLink(claim_id=claim.id, linked_by=linked_by, note=note)


def _confirmed_policy(store, term="sign convention for income"):
    """The shape M5 will produce: a policy read into a settled claim."""
    claim = ConceptClaim(
        statement="income is stored as a negative amount",
        created_by=Actor.HUMAN, term=term,
        definition="income negative, expense positive",
        status=ClaimStatus.BUSINESS_CONFIRMED,
    )
    store.save_claim(claim)
    return claim


def _map(store, guide, *items) -> "ReadinessMap":
    """Judge a list handed in directly — the caller is its reviewer, so the
    review cap is inert and what is under test is the verdict rule alone."""
    request = AnswerRequest(question="Can these files produce actual P&L?",
                            requested_output="P&L per entity per month",
                            scope=items[0].scope if items else Scope())
    return evaluate(store, guide, request, list(items))


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
        """The owner's decision: the map reads settled_slots
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

    def test_a_rule_is_satisfied_by_a_linked_claim_and_names_who_linked_it(
            self, store, guide):
        claim = _confirmed_policy(store)
        item = _map(store, guide,
                    _rule(links=[_link(claim, Actor.HUMAN)])).items[0]
        assert item.satisfied and item.ground is Ground.STATED_RULE
        assert "a business-confirmed claim is linked to it by the human" in \
            item.because
        assert "income is stored as a negative amount" in item.because

    def test_a_linked_claim_that_is_only_proposed_is_not_support(
            self, store, guide):
        """The link routes; it never vouches. Status still decides."""
        claim = ConceptClaim(statement="income is probably negative",
                             created_by=Actor.AI, term="sign", definition="g")
        store.save_claim(claim)
        item = _map(store, guide, _rule(links=[_link(claim, Actor.AI)])).items[0]
        assert not item.satisfied and item.ground is Ground.UNDECIDED

    def test_a_claim_that_states_the_rule_but_is_not_linked_is_not_support(
            self, store, guide):
        """Name matching was rejected (owner decision): the contract names a
        rule in the human's words and whatever produces the claim coins its
        own term, so a match would miss where it matters and could hit
        something unrelated that happens to slug the same. A verdict resting
        on a coincidence of wording is not a verdict."""
        _confirmed_policy(store)  # term == the rule's name, exactly
        item = _map(store, guide, _rule()).items[0]
        assert not item.satisfied and item.ground is Ground.NOTHING_PROPOSED
        assert "nothing in this project is linked to it" in item.because

    def test_an_ai_may_link_because_a_link_cannot_promote(self, store, guide):
        """The whole reason V3 is allowed to do this in M5."""
        claim = _confirmed_policy(store)
        item = _map(store, guide, _rule(links=[_link(claim, Actor.AI)])).items[0]
        assert item.satisfied
        assert "linked to it by the ai" in item.because  # attributed, visibly

    def test_a_link_to_a_claim_that_vanished_says_the_link_is_broken(
            self, store, guide):
        """Distinct from 'nobody answered' — one is missing knowledge, the
        other is a broken pointer, and they need different repairs."""
        item = _map(store, guide, _rule(links=[
            KnowledgeLink(claim_id="01GONE", linked_by=Actor.HUMAN)])).items[0]
        assert not item.satisfied
        assert "the link is broken, not the knowledge" in item.because


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


class TestLinking:
    """The seam M5 needs: V3 reads a policy, produces a claim, and says which
    open dependency that claim answers."""

    def _asked(self, store, *items, guide=None):
        """A request whose list a human has already vouched for, so the
        review cap is inert and these tests isolate their own subject."""
        request = AnswerRequest(question="q?", requested_output="o")
        store.save_request(request)
        store.save_required_knowledge(
            RequiredKnowledge(request_id=request.id, items=list(items)))
        if guide is not None:
            confirm_classification(store, guide, request.id)
        return request

    def test_linking_turns_a_named_gap_into_a_satisfied_item(self, store, guide):
        request = self._asked(store, _rule(), guide=guide)
        assert evaluate_request(store, guide, request.id).verdict is \
            Readiness.READY_WITH_LIMITATIONS
        claim = _confirmed_policy(store)

        link_claim(store, guide, request.id, "sign convention for income", claim.id,
                   linked_by=Actor.AI, note="Buchhaltungsrichtlinie §2")

        result = evaluate_request(ProjectStore(store.root), guide, request.id)
        assert result.verdict is Readiness.READY
        assert result.items[0].ground is Ground.STATED_RULE

    def test_a_link_cannot_promote_the_claim_it_points_at(self, store, guide):
        """The property that makes it safe for an AI to do."""
        request = self._asked(store, _rule(), guide=guide)
        claim = ConceptClaim(statement="guessed", created_by=Actor.AI,
                             term="t", definition="d")
        store.save_claim(claim)
        link_claim(store, guide, request.id, "sign convention for income", claim.id,
                   linked_by=Actor.AI)
        assert ProjectStore(store.root).claims[claim.id].status is \
            ClaimStatus.PROPOSED
        assert not evaluate_request(store, guide, request.id).items[0].satisfied

    def test_an_object_cannot_be_linked_because_the_guide_decides_it(
            self, store, guide):
        """A link that could satisfy an object would be a way around the
        scoped election, which is the whole point of having a guide."""
        request = self._asked(store, _obj())
        claim = _confirmed_policy(store)
        with pytest.raises(UnlinkableItem, match="only a rule"):
            link_claim(store, guide, request.id, "journal", claim.id,
                       linked_by=Actor.HUMAN)
        # and the model refuses to hold one even if constructed directly
        with pytest.raises(ValidationError, match="only a rule is satisfied"):
            KnowledgeItem(kind=KnowledgeKind.OBJECT, name="journal",
                          satisfied_by=[_link(claim)])

    def test_linking_something_the_question_does_not_require_is_refused(
            self, store, guide):
        request = self._asked(store, _rule(), guide=guide)
        claim = _confirmed_policy(store)
        with pytest.raises(UnlinkableItem, match="is not required by"):
            link_claim(store, guide, request.id, "month cut-off", claim.id,
                       linked_by=Actor.HUMAN)

    def test_linking_a_claim_that_does_not_exist_is_refused(self, store, guide):
        request = self._asked(store, _rule(), guide=guide)
        with pytest.raises(UnlinkableItem, match="no claim"):
            link_claim(store, guide, request.id, "sign convention for income",
                       "01NOPE", linked_by=Actor.HUMAN)

    def test_relinking_the_same_claim_does_not_stack(self, store, guide):
        request = self._asked(store, _rule(), guide=guide)
        claim = _confirmed_policy(store)
        for _ in range(3):
            link_claim(store, guide, request.id,
                       "sign convention for income", claim.id,
                       linked_by=Actor.HUMAN)
        # three acts are recorded — the history is not rewritten — but the
        # list they replay into carries one link
        assert len(store.acts_for(request.id)) == 4  # 3 links + the confirmation
        item = assemble(store, guide, request).items[0]
        assert len(item.satisfied_by) == 1

    def test_a_broken_link_is_an_integrity_finding(self, store, guide):
        request = self._asked(store, _rule(links=[
            KnowledgeLink(claim_id="01GONE", linked_by=Actor.AI)]))
        findings = check_integrity(ProjectStore(store.root))
        assert any("linked to missing claim 01GONE" in f for f in findings)


class TestConflictIsNeverSilent:
    """A rule can carry several links. If one of them is contradicted, the
    verdict may still stand — but the conflict must be said out loud. A
    conflict this product does not report is the one failure it exists to
    prevent."""

    def _both(self, store):
        good = _confirmed_policy(store)
        bad = ConceptClaim(
            statement="income is positive", created_by=Actor.AI, term="b",
            definition="d", status=ClaimStatus.CONTRADICTED)
        store.save_claim(bad)
        return good, bad

    def test_a_contradicted_co_link_is_named(self, store, guide):
        good, bad = self._both(store)
        item = _map(store, guide, _rule(
            links=[_link(good), _link(bad, Actor.AI)])).items[0]
        assert item.satisfied  # the settled claim still decides
        assert "A contradicted claim is also linked to this rule" in item.because
        assert "income is positive" in item.because
        assert "read both before relying on the answer" in item.because

    def test_both_claims_are_reachable_from_the_item(self, store, guide):
        good, bad = self._both(store)
        item = _map(store, guide, _rule(
            links=[_link(good), _link(bad, Actor.AI)])).items[0]
        assert set(item.claim_ids) == {good.id, bad.id}

    def test_no_conflict_means_no_clause(self, store, guide):
        item = _map(store, guide,
                    _rule(links=[_link(_confirmed_policy(store))])).items[0]
        assert "contradicted" not in item.because


class TestWaiving:
    """A list over-lists by design. Without pruning, an item nobody needs blocks
    the answer forever — and pruning is what justifies persisting the draft
    at all."""

    def _asked(self, store, *items, guide=None):
        """A request whose list a human has already vouched for, so the
        review cap is inert and these tests isolate their own subject."""
        request = AnswerRequest(question="q?", requested_output="o")
        store.save_request(request)
        store.save_required_knowledge(
            RequiredKnowledge(request_id=request.id, items=list(items)))
        if guide is not None:
            confirm_classification(store, guide, request.id)
        return request

    def test_waiving_unblocks_the_answer_and_keeps_the_reason(self, store, guide):
        request = self._asked(store, _obj("journal"), guide=guide)
        assert evaluate_request(store, guide, request.id).verdict is \
            Readiness.BLOCKED

        waive_item(store, guide, request.id, "journal",
                   "this question is answered from the plan, not the ledger")

        result = evaluate_request(ProjectStore(store.root), guide, request.id)
        assert result.verdict is Readiness.READY
        item = result.items[0]
        assert item.ground is Ground.WAIVED
        assert item.because == (
            "Not required: a human waived this dependency — this question is "
            "answered from the plan, not the ledger")

    def test_a_waived_item_is_kept_not_deleted(self, store, guide):
        """A deleted dependency is invisible; a waived one still shows, with
        the judgement attached."""
        request = self._asked(store, _obj("journal"), guide=guide)
        waive_item(store, guide, request.id, "journal", "not needed here")
        items = assemble(ProjectStore(store.root), guide, request).items
        assert len(items) == 1
        assert items[0].waived_because == "not needed here"
        assert items[0].waived is True

    def test_a_waiver_without_a_reason_is_refused(self, store, guide):
        """Indistinguishable from an oversight six months later."""
        request = self._asked(store, _obj("journal"), guide=guide)
        with pytest.raises(UnlinkableItem, match="requires a reason"):
            waive_item(store, guide, request.id, "journal", "   ")

    def test_a_waiver_can_be_revisited(self, store, guide):
        request = self._asked(store, _obj("journal"), guide=guide)
        waive_item(store, guide, request.id, "journal", "thought we did not need it")
        require_again(store, guide, request.id, "journal")
        result = evaluate_request(ProjectStore(store.root), guide, request.id)
        assert result.verdict is Readiness.BLOCKED
        assert result.items[0].item.waived is False

    def test_waiving_something_not_required_is_refused(self, store, guide):
        request = self._asked(store, _obj("journal"), guide=guide)
        with pytest.raises(UnlinkableItem, match="is not required by"):
            waive_item(store, guide, request.id, "intercompany", "nope")

    def test_any_kind_may_be_waived_unlike_linking(self, store, guide):
        """Linking is rule-only because it would bypass an election. Waiving
        bypasses nothing — it removes a requirement, which is the human's to
        do for any kind."""
        request = self._asked(store, _obj("journal"), _field(), _rule(), guide=guide)
        for ref in ("journal", "journal.amount_local",
                    "sign convention for income"):
            waive_item(store, guide, request.id, ref, "out of scope for this answer")
        assert evaluate_request(store, guide, request.id).verdict is \
            Readiness.READY


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


# -- the list itself -------------------------------------------------------

def _typed_guide(*, requires=None, path=None) -> DomainGuide:
    """The finance guide with one answer type, loaded from a file so it has
    a fingerprint — which is what a human act records itself against."""
    requires = requires or ["- object: journal",
                            "- rule: sign convention for income"]
    text = _GUIDE_TEXT + "answer_types:\n  profit_and_loss:\n" \
        "    definition: the result of a period\n    requires:\n" \
        + "".join(f"      {line}\n" for line in requires)
    path.write_text(text, encoding="utf-8")
    return load_domain_guide(path)


_GUIDE_TEXT = """\
domain: finance
objects:
  journal:
    decided_by: balance
    definition: the ledger of record
    fields:
      amount_local:
        decided_by: slot
        fills: amount
        definition: the signed amount
"""


def _classified(store, answer_type="profit_and_loss") -> AnswerRequest:
    request = AnswerRequest(question="Can these files produce actual P&L?",
                            requested_output="P&L per entity per month",
                            answer_type=answer_type)
    store.save_request(request)
    return request


class TestTheListIsDerived:
    """No stored list, so no list that can quietly describe an older guide."""

    def test_a_classified_request_needs_no_stored_list_at_all(
            self, store, tmp_path):
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store)
        result = evaluate_request(store, guide, request.id)
        assert [i.ref for i in result.items] == \
            ["journal", "sign convention for income"]
        assert store.knowledge_for(request.id) is None

    def test_every_derived_item_says_it_came_from_the_contract(
            self, store, tmp_path):
        guide = _typed_guide(path=tmp_path / "g.yaml")
        result = evaluate_request(store, guide, _classified(store).id)
        assert all(i.item.provenance is Provenance.CONTRACT
                   for i in result.items)

    def test_editing_the_guide_changes_the_list_without_touching_the_store(
            self, store, tmp_path):
        """Monday: confirm a list of two. Wednesday: the guide grows a third
        dependency. The verdict must move — a stored list would not have."""
        path = tmp_path / "g.yaml"
        guide = _typed_guide(path=path)
        request = _classified(store)
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        link_claim(store, guide, request.id, "sign convention for income",
                   _confirmed_policy(store).id, linked_by=Actor.HUMAN)
        confirm_classification(store, guide, request.id)
        assert evaluate_request(store, guide, request.id).verdict is \
            Readiness.READY

        grown = _typed_guide(path=path, requires=[
            "- object: journal",
            "- rule: sign convention for income",
            "- rule: month cut-off for late postings",
        ])
        result = evaluate_request(ProjectStore(store.root), grown, request.id)
        assert "month cut-off for late postings" in result.reason()
        assert result.verdict is Readiness.READY_WITH_LIMITATIONS

    def test_an_answer_type_the_guide_dropped_blocks_and_says_why(
            self, store, tmp_path):
        """Expanding to nothing would be the silent short list itself."""
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store, answer_type="balance_sheet")
        result = evaluate_request(store, guide, request.id)
        assert result.verdict is Readiness.BLOCKED
        assert "no longer declares" in result.reason()
        assert "balance_sheet" in result.reason()


class TestTheListItselfMustBeVouchedFor:
    """A verdict is never stronger than the list it was computed over.

    Whether the dependencies hold and whether anyone has read the list of
    them are two questions, and only the second protects against a list that
    was short to begin with.
    """

    def _supported(self, store, guide, request):
        _passing_balance(store, _candidate(store, "journal", "de_erp__gl"))
        link_claim(store, guide, request.id, "sign convention for income",
                   _confirmed_policy(store).id, linked_by=Actor.HUMAN)

    def test_an_unconfirmed_list_cannot_read_ready(self, store, tmp_path):
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store)
        self._supported(store, guide, request)
        result = evaluate_request(store, guide, request.id)
        assert result.verdict is Readiness.READY_WITH_LIMITATIONS
        assert result.confirmed is False
        assert "nobody has confirmed" in result.reason()

    def test_the_cap_does_not_hide_that_the_dependencies_hold(
            self, store, tmp_path):
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store)
        self._supported(store, guide, request)
        reason = evaluate_request(store, guide, request.id).reason()
        assert reason.startswith("All 2 things this answer depends on are "
                                 "supported.")

    def test_confirming_lifts_the_cap(self, store, tmp_path):
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store)
        self._supported(store, guide, request)
        confirm_classification(store, guide, request.id)
        result = evaluate_request(ProjectStore(store.root), guide, request.id)
        assert result.verdict is Readiness.READY
        assert result.confirmed is True

    def test_a_confirmation_lapses_when_the_guide_moves(self, store, tmp_path):
        path = tmp_path / "g.yaml"
        guide = _typed_guide(path=path)
        request = _classified(store)
        self._supported(store, guide, request)
        confirm_classification(store, guide, request.id)

        reworded = _typed_guide(path=path, requires=[
            "- object: journal",
            "- rule: sign convention for income",
        ])
        # same two dependencies, different bytes: the reader confirmed a list
        # that was rendered from something else
        path.write_text(path.read_text().replace("the ledger of record",
                                                 "the ledger"), encoding="utf-8")
        moved = load_domain_guide(path)
        result = evaluate_request(store, moved, request.id)
        assert result.verdict is Readiness.READY_WITH_LIMITATIONS
        assert "earlier version of the domain guide" in result.reason()
        assert reworded.fingerprint != moved.fingerprint

    def test_a_confirmation_does_not_travel_to_another_classification(
            self, store, tmp_path):
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store)
        confirm_classification(store, guide, request.id)
        reclassified = request.model_copy(update={"answer_type": "other"})
        store.save_request(reclassified)
        assert evaluate_request(store, guide, request.id).confirmed is False

    def test_a_waiver_does_not_lapse_with_the_guide(self, store, tmp_path):
        """Unlike a confirmation. 'This list is complete' stops being true
        when the list moves; 'this item does not matter here' does not."""
        path = tmp_path / "g.yaml"
        guide = _typed_guide(path=path)
        request = _classified(store)
        waive_item(store, guide, request.id, "sign convention for income",
                   "this question is gross-only")
        grown = _typed_guide(path=path, requires=[
            "- object: journal",
            "- rule: sign convention for income",
            "- rule: month cut-off for late postings",
        ])
        items = {i.ref: i for i in
                 evaluate_request(store, grown, request.id).items}
        assert items["sign convention for income"].ground is Ground.WAIVED

    def test_a_list_nobody_matched_says_so_in_the_verdict(self, store, guide):
        request = AnswerRequest(question="q?", requested_output="o")
        store.save_request(request)
        store.save_required_knowledge(
            RequiredKnowledge(request_id=request.id, items=[_rule()]))
        reason = evaluate_request(store, guide, request.id).reason()
        assert "No answer type of the domain guide covers this question" in reason

    def test_a_human_can_add_what_the_contract_missed(self, store, tmp_path):
        """The reader who spots the gap closes it, and the item is marked so
        nobody mistakes it for reviewed content."""
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store)
        add_item(store, guide, request.id,
                 _rule("month cut-off for late postings"))
        items = {i.ref: i.item for i in
                 evaluate_request(store, guide, request.id).items}
        assert items["month cut-off for late postings"].provenance is \
            Provenance.ADDED

    def test_a_drafted_delta_alongside_a_contract_is_named(
            self, store, tmp_path):
        guide = _typed_guide(path=tmp_path / "g.yaml")
        request = _classified(store)
        store.save_required_knowledge(RequiredKnowledge(
            request_id=request.id, items=[_rule("in USD, at which rate")]))
        result = evaluate_request(store, guide, request.id)
        assert "1 item drafted for this question alone" in result.reason()
        assert {i.item.provenance for i in result.items} == \
            {Provenance.CONTRACT, Provenance.PROPOSED}
