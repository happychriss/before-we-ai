"""The top of the machine: a business question, and what it depends on.

Everything here guards one idea — the question *bounds* discovery. An
AnswerRequest carries a scope, the RequiredKnowledge derived from it
inherits that scope item by item, and from there the scope reaches the
clarification questions. The regression at the bottom of this file is the
reason the scope had to become a field at all.
"""

import pytest
from pydantic import ValidationError

from before_we_ai.model import (
    Actor,
    AnswerRequest,
    Claim,
    ClarificationQuestion,
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeLink,
    RequiredKnowledge,
    Scope,
    create_claim,
)
from before_we_ai.store import ProjectStore, check_integrity


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
        V4's, not the asker's. Nothing set it and nothing read it. The same
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

    def test_it_carries_the_answer_half_the_question_card_used_to_hold(self):
        """sql/result_ref moved off ClarificationQuestion — the card asks, the
        request answers, and neither is truth on its own."""
        request = _request(sql="select 1", result_ref="cache/answer.parquet")
        assert request.sql and request.result_ref
        assert not hasattr(ClarificationQuestion(question="?"), "sql")


class TestRequiredKnowledge:
    def test_every_item_inherits_the_requests_scope(self):
        scope = Scope(entity="DE")
        items = [
            KnowledgeItem(kind=KnowledgeKind.OBJECT, name="journal",
                          why="the P&L is summed from it", scope=scope),
            KnowledgeItem(kind=KnowledgeKind.FIELD, name="amount",
                          of_object="journal", why="it is what gets summed",
                          scope=scope),
            KnowledgeItem(kind=KnowledgeKind.RULE, name="sign_convention",
                          why="credits and debits must not cancel wrongly",
                          scope=scope),
        ]
        required = RequiredKnowledge(request_id="req", items=items)
        assert {i.scope.entity for i in required.items} == {"DE"}

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
