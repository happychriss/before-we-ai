"""The top of the machine: a business question, and what it depends on.

Everything here guards one idea — the question *bounds* discovery. An
AnswerRequest carries a scope, the RequiredKnowledge derived from it
inherits that scope item by item, and from there the scope reaches the
clarification questions. The regression at the bottom of this file is the
reason the scope had to become a field at all.
"""

import pytest
from pydantic import ValidationError

from before_we_ai.core import (
    ActKind,
    Actor,
    AnswerRequest,
    Claim,
    ClarificationQuestion,
    KnowledgeAct,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeLink,
    RequiredKnowledge,
    Scope,
    create_claim,
)
from before_we_ai.llm.mapping import item_to_knowledge
from before_we_ai.llm.schemas import KnowledgeItemProposal
from before_we_ai.store import ProjectStore, check_integrity
from before_we_ai.store.repository import AppendOnlyViolation

pytestmark = pytest.mark.integration


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "proj", create=True)


def _request(**kw) -> AnswerRequest:
    return AnswerRequest(
        question="Can these files reliably produce actual P&L by entity and month?",
        requested_output="profit and loss, per entity, per month",
        **kw,
    )


class TestAnswerRequest:
    def test_it_records_the_question_as_the_human_asked_it(self):
        request = _request(scope=Scope(entity="DE", period="2024"))
        assert request.question.endswith("by entity and month?")
        assert request.scope.label() == "entity DE, period 2024"

    def test_a_request_without_a_scope_is_landscape_wide(self):
        assert _request().scope.is_explicit() is False
        assert _request().scope.label() == ""

    def test_authorship_is_fixed_by_the_shape_so_no_field_records_it(self):
        """A field whose value never varies carries no information.

        `created_by` was on both objects and would have read `human` on
        every AnswerRequest ever written — while being *wrong* about two of
        the three content fields, since `requested_output` and `scope` are
        the contract's, not the asker's. Nothing set it and nothing read it. The same
        defect class as the redundant `Hypothesis.kind` (M5 kickoff).

        The contrast is the point: `Claim.created_by` and
        `KnowledgeLink.linked_by` genuinely vary, and the code branches on
        them — those earn their place.
        """
        for obj in (_request(), RequiredKnowledge(request_id="r")):
            assert not hasattr(obj, "created_by")
        assert Claim(statement="x", created_by=Actor.AI).created_by is Actor.AI
        assert KnowledgeLink(claim_id="c", linked_by=Actor.AI).linked_by \
            is Actor.AI

    def test_there_is_no_answer_half_on_either_object(self):
        """`sql`/`result_ref` sat on the question card, moved here in M6, and
        are now gone from both. Nothing set them, nothing read them, and no
        milestone plans to produce SQL — so they were a third field that
        would be reasoned about as if it meant something."""
        for obj in (_request(), ClarificationQuestion(question="?")):
            assert not hasattr(obj, "sql")
            assert not hasattr(obj, "result_ref")


class TestRequiredKnowledge:
    def test_objects_and_fields_inherit_the_requests_scope(self):
        """For them a scope is a *selector*: it decides which table or column
        plays the role, so DE's ledger and US's compete separately."""
        scope = Scope(entity="DE")
        required = RequiredKnowledge(request_id="req", items=[
            KnowledgeItem(kind=KnowledgeKind.OBJECT, name="journal",
                          why="the P&L is summed from it", scope=scope),
            KnowledgeItem(kind=KnowledgeKind.FIELD, name="amount",
                          of_object="journal", why="it is what gets summed",
                          scope=scope),
        ])
        assert {i.scope.entity for i in required.items} == {"DE"}

    def test_a_rule_carries_no_scope_because_it_selects_nothing(self):
        """There is no "DE's copy" of an accounting policy to choose among.
        Where a rule is valid belongs to the claim that states it —
        `Claim.scope` and `Claim.validity`, which can also say *from when*."""
        with pytest.raises(ValidationError, match="a rule item carries no scope"):
            KnowledgeItem(kind=KnowledgeKind.RULE, name="sign_convention",
                          why="w", scope=Scope(entity="DE"))
        # and the mapping drops it rather than passing it through
        item = item_to_knowledge(
            KnowledgeItemProposal(kind="rule", name="sign_convention",
                                  why="w"),
            Scope(entity="DE"))
        assert item.scope.is_explicit() is False

    def test_a_field_must_name_its_object_and_only_a_field_may(self):
        with pytest.raises(ValidationError, match="must name the object"):
            KnowledgeItem(kind=KnowledgeKind.FIELD, name="amount")
        with pytest.raises(ValidationError, match="must not carry one"):
            KnowledgeItem(kind=KnowledgeKind.RULE, name="r", of_object="journal")

    def test_ref_addresses_the_item_in_the_guides_terms(self):
        field = KnowledgeItem(kind=KnowledgeKind.FIELD, name="amount",
                              of_object="journal")
        assert field.ref() == "journal.amount"
        assert KnowledgeItem(kind=KnowledgeKind.OBJECT, name="journal").ref() == "journal"


class TestStore:
    def test_request_and_knowledge_share_answers_and_survive_reload(self, store):
        request = _request(scope=Scope(entity="US"))
        required = RequiredKnowledge(
            request_id=request.id,
            items=[KnowledgeItem(kind=KnowledgeKind.OBJECT, name="journal",
                                 scope=request.scope)],
        )
        store.save_request(request)
        store.save_required_knowledge(required)

        reloaded = ProjectStore(store.root)
        assert reloaded.requests[request.id] == request
        assert reloaded.required[required.id] == required
        assert reloaded.knowledge_for(request.id) == required
        assert check_integrity(reloaded) == []

    def test_knowledge_pointing_at_no_request_is_an_integrity_finding(self, store):
        store.save_required_knowledge(RequiredKnowledge(request_id="01NOPE"))
        findings = check_integrity(ProjectStore(store.root))
        assert any("dangling request reference 01NOPE" in f for f in findings)


class TestTheActRecord:
    """The dependency list is derived; what a human did to it is stored.

    So these records carry the whole history of decisions about a list that
    itself leaves no trace — which is why they are append-only and why a
    waiver may not exist without its reason.
    """

    def test_acts_survive_reload_in_the_order_they_were_taken(self, store):
        request = _request()
        store.save_request(request)
        for kind, extra in [
            (ActKind.CONFIRM, {"answer_type": "profit_and_loss"}),
            (ActKind.WAIVE, {"ref": "intercompany", "reason": "one entity only"}),
            (ActKind.REQUIRE_AGAIN, {"ref": "intercompany"}),
        ]:
            store.save_act(KnowledgeAct(request_id=request.id, kind=kind,
                                        actor=Actor.HUMAN, **extra))

        reloaded = ProjectStore(store.root)
        assert [a.kind for a in reloaded.acts_for(request.id)] == [
            ActKind.CONFIRM, ActKind.WAIVE, ActKind.REQUIRE_AGAIN
        ]
        assert check_integrity(reloaded) == []

    def test_an_act_is_never_overwritten(self, store):
        request = _request()
        store.save_request(request)
        act = KnowledgeAct(request_id=request.id, kind=ActKind.CONFIRM,
                           actor=Actor.HUMAN, answer_type="profit_and_loss")
        store.save_act(act)
        with pytest.raises(AppendOnlyViolation):
            store.save_act(act)

    def test_a_waiver_without_a_reason_cannot_be_constructed(self):
        with pytest.raises(ValidationError, match="reason"):
            KnowledgeAct(request_id="01R", kind=ActKind.WAIVE,
                         actor=Actor.HUMAN, ref="intercompany")

    def test_an_act_on_one_item_must_name_it(self):
        with pytest.raises(ValidationError, match="must name the item"):
            KnowledgeAct(request_id="01R", kind=ActKind.REQUIRE_AGAIN,
                         actor=Actor.HUMAN)

    def test_a_link_act_must_name_its_claim(self):
        with pytest.raises(ValidationError, match="name the claim"):
            KnowledgeAct(request_id="01R", kind=ActKind.LINK,
                         actor=Actor.AI, ref="sign convention")

    def test_a_confirmation_is_about_the_whole_list(self):
        with pytest.raises(ValidationError, match="whole list"):
            KnowledgeAct(request_id="01R", kind=ActKind.CONFIRM,
                         actor=Actor.HUMAN, ref="journal")

    def test_an_act_records_which_guide_it_was_made_against(self, store):
        request = _request()
        store.save_request(request)
        store.save_act(KnowledgeAct(
            request_id=request.id, kind=ActKind.CONFIRM, actor=Actor.HUMAN,
            answer_type="profit_and_loss", guide_fingerprint="a" * 64,
        ))
        assert ProjectStore(store.root).acts_for(request.id)[0] \
            .guide_fingerprint == "a" * 64

    def test_an_act_pointing_at_no_request_is_an_integrity_finding(self, store):
        store.save_act(KnowledgeAct(request_id="01NOPE", kind=ActKind.CONFIRM,
                                    actor=Actor.HUMAN))
        findings = check_integrity(ProjectStore(store.root))
        assert any("dangling request reference 01NOPE" in f for f in findings)

    def test_a_link_to_a_missing_claim_is_an_integrity_finding(self, store):
        request = _request()
        store.save_request(request)
        store.save_act(KnowledgeAct(request_id=request.id, kind=ActKind.LINK,
                                    actor=Actor.AI, ref="sign convention",
                                    claim_id="01GONE"))
        findings = check_integrity(ProjectStore(store.root))
        assert any("missing claim 01GONE" in f for f in findings)


class TestQuestionDedup:
    """Two scopes, one role, two cards.

    Regression for the defect the question rewrite introduced: with the
    candidate list out of the wording, the same role asked about DE and
    about US produces byte-identical text. Deduplicating on text alone
    would drop the second card and silently lose its candidates — the one
    outcome this product forbids.
    """

    TEXT = "Which of the proposed candidates is the 'doc_ref'?"

    def test_the_same_wording_in_two_scopes_is_two_questions(self, store):
        de = ClarificationQuestion(question=self.TEXT, scope=Scope(entity="DE"))
        us = ClarificationQuestion(question=self.TEXT, scope=Scope(entity="US"))
        store.save_question(de)
        assert store.find_question(us) is None
        store.save_question(us)
        assert len(ProjectStore(store.root).questions) == 2

    def test_the_same_wording_in_the_same_scope_is_one_question(self, store):
        store.save_question(
            ClarificationQuestion(question=self.TEXT, scope=Scope(entity="DE"))
        )
        again = ClarificationQuestion(question=self.TEXT, scope=Scope(entity="DE"))
        assert store.find_question(again) is not None

    def test_a_scopeless_card_does_not_absorb_a_scoped_one(self, store):
        """The landscape-wide question and the DE question are different
        questions: one asks about everything, one about DE."""
        store.save_question(ClarificationQuestion(question=self.TEXT))
        scoped = ClarificationQuestion(question=self.TEXT, scope=Scope(entity="DE"))
        assert store.find_question(scoped) is None

    def test_dedup_survives_a_reload(self, store):
        claim = create_claim("x", Actor.AI)
        store.save_claim(claim)
        store.save_question(
            ClarificationQuestion(question=self.TEXT, scope=Scope(entity="DE"),
                                  claim_ids=[claim.id])
        )
        reloaded = ProjectStore(store.root)
        again = ClarificationQuestion(question=self.TEXT, scope=Scope(entity="DE"))
        assert reloaded.find_question(again) is not None
