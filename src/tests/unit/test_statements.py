"""The human's voice: ``tell``, and the mirror loop that guards it.

The two corpus statements are the cases worth naming. F28 — "we only
supply pharmacies and wholesalers" — is unverifiable: no column says who a
customer is allowed to be, so it must end up visible and unproven rather
than quietly believed. F29 — "the fiscal year runs May to April" — carries
a scope in the corpus, and confirming it *without* one must be refused,
because a US fiscal year confirmed for the whole group is a wrong answer
with a human's signature on it.
"""

import json

import pytest
import yaml

from before_we_ai.core import Actor, ClaimStatus, EvidenceType, Scope
from before_we_ai.core.transitions import PromotionError
from before_we_ai.llm.client import Completion
from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.statements import (
    STATEMENTS,
    answer_question,
    confirm_claim,
    record_statement,
    tell,
)
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.integration

F28 = "Wir beliefern nur Apotheken und Grosshaendler."
F29 = "Geschaeftsjahr laeuft Mai bis April."


class _ScriptedClient:
    name = "scripted"

    def __init__(self, findings):
        self.payload = {"findings": findings}

    def complete(self, **kwargs) -> Completion:
        return Completion(text=json.dumps(self.payload), usage={}, ms=0)


def _structures(statement, term, definition, quote=None):
    return _ScriptedClient([{
        "chunk_id": f"{STATEMENTS}:p1:0",
        "quote": quote or statement,
        "reads_as": "definition",
        "statement": definition,
        "term": term,
        "definition": definition,
        "answers": None,
        "rationale": "the speaker states it",
    }])


@pytest.fixture
def guide() -> DomainGuide:
    return DomainGuide.model_validate({
        "domain": "finance",
        "objects": {"journal": {"decided_by": "balance",
                                "definition": "the ledger of record"}},
    })


@pytest.fixture
def project(tmp_path):
    root = init_project(tmp_path / "p")
    config = yaml.safe_load((root / "before-ai.yaml").read_text())
    config["llm"] = {"offline": False}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    return root


class TestTell:
    def test_the_words_are_kept_verbatim(self, project, guide):
        report = tell(project, F28, guide=guide,
                      client=_structures(F28, "customer channel",
                                         "only pharmacies and wholesalers"))
        store = ProjectStore(project)
        testimonials = [e for e in store.evidence.values()
                        if e.type is EvidenceType.TESTIMONIAL]
        assert [e.statement for e in testimonials] == [F28]
        assert report.testimonials

    def test_a_told_claim_is_proposed_not_believed(self, project, guide):
        """F28: somebody said it. That is not the same fact as it being true."""
        report = tell(project, F28, guide=guide,
                      client=_structures(F28, "customer channel",
                                         "only pharmacies and wholesalers"))
        store = ProjectStore(project)
        assert report.claims_created
        assert all(store.claims[c].status is ClaimStatus.PROPOSED
                   for c in report.claims_created)

    def test_the_statement_becomes_searchable(self, project, guide):
        tell(project, F29, guide=guide,
             client=_structures(F29, "fiscal year", "May to April"))
        from before_we_ai.documents import load_chunks
        import duckdb

        con = duckdb.connect(str(project / "cache" / "analysis.duckdb"))
        try:
            assert any(c.source == STATEMENTS and F29 in c.text
                       for c in load_chunks(con))
        finally:
            con.close()

    def test_a_statement_nothing_can_be_made_of_is_parked_not_lost(
            self, project, guide):
        report = tell(project, "Things have been difficult lately.",
                      guide=guide, client=_ScriptedClient([]))
        assert report.claims_created == []
        assert report.mirror.parked
        assert "carries no weight" in report.mirror.question()

    def test_a_misquoted_statement_creates_nothing(self, project, guide):
        """The same string match documents get — a paraphrase is not what
        the person said."""
        report = tell(project, F28, guide=guide,
                      client=_structures(F28, "channel", "…",
                                         quote="Wir beliefern Apotheken."))
        assert report.claims_created == []
        assert report.skipped

    def test_an_empty_statement_is_refused(self, project, guide):
        with pytest.raises(ValueError, match="says nothing"):
            record_statement(ProjectStore(project), "   ")

    def test_two_statements_get_their_own_passages(self, project, guide):
        tell(project, F28, guide=guide,
             client=_structures(F28, "channel", "pharmacies and wholesalers"))
        second = tell(project, F29, guide=guide,
                      client=_ScriptedClient([]))
        assert second.chunk_id == f"{STATEMENTS}:p1:1"


class TestMirror:
    def test_it_asks_for_a_scope_when_none_was_given(self, project, guide):
        report = tell(project, F29, guide=guide,
                      client=_structures(F29, "fiscal year", "May to April"))
        assert report.mirror.needs_scope
        assert "Which companies, periods or segments" in report.mirror.question()

    def test_it_repeats_back_what_was_understood(self, project, guide):
        report = tell(project, F29, guide=guide,
                      client=_structures(F29, "fiscal year", "May to April"))
        assert "May to April" in report.mirror.question()

    def test_a_given_scope_closes_the_question(self, project, guide):
        report = tell(project, F29, guide=guide, scope=Scope(entity="US"),
                      client=_structures(F29, "fiscal year", "May to April"))
        assert not report.mirror.needs_scope
        assert "US" in report.mirror.question()


class TestConfirming:
    def _told(self, project, guide, scope=None):
        report = tell(project, F29, guide=guide, scope=scope,
                      client=_structures(F29, "fiscal year", "May to April"))
        return ProjectStore(project), report

    def test_f29_confirming_a_testimonial_without_a_scope_is_refused(
            self, project, guide):
        store, report = self._told(project, guide)
        with pytest.raises(PromotionError, match="explicit scope"):
            confirm_claim(store, report.claims_created[0])

    def test_f29_the_refusal_leaves_the_claim_where_it_was(self, project, guide):
        store, report = self._told(project, guide)
        with pytest.raises(PromotionError):
            confirm_claim(store, report.claims_created[0])
        assert ProjectStore(project).claims[
            report.claims_created[0]].status is ClaimStatus.PROPOSED

    def test_f29_with_a_scope_it_is_business_confirmed(self, project, guide):
        store, report = self._told(project, guide)
        confirm_claim(store, report.claims_created[0], scope=Scope(entity="US"))
        assert ProjectStore(project).claims[
            report.claims_created[0]].status is ClaimStatus.BUSINESS_CONFIRMED

    def test_the_confirmation_records_who_and_for_what(self, project, guide):
        store, report = self._told(project, guide)
        record = confirm_claim(store, report.claims_created[0],
                               scope=Scope(entity="US"), note="finance lead")
        assert record.actor is Actor.HUMAN
        assert record.scope.entity == "US"
        assert record.payload["note"] == "finance lead"


class TestAnsweringAQuestion:
    def test_answering_settles_every_claim_the_card_rests_on(
            self, project, guide):
        from before_we_ai.core.objects import ClarificationQuestion

        report = tell(project, F29, guide=guide,
                      client=_structures(F29, "fiscal year", "May to April"))
        store = ProjectStore(project)
        card = ClarificationQuestion(question="Which entity?",
                                     claim_ids=report.claims_created)
        store.save_question(card)

        answer_question(store, card.id, scope=Scope(entity="US"))
        after = ProjectStore(project)
        assert all(after.claims[c].status is ClaimStatus.BUSINESS_CONFIRMED
                   for c in report.claims_created)

    def test_a_refused_claim_refuses_the_whole_answer(self, project, guide):
        """Half an answer would let a reader think they had settled it."""
        from before_we_ai.core.objects import ClarificationQuestion

        report = tell(project, F29, guide=guide,
                      client=_structures(F29, "fiscal year", "May to April"))
        store = ProjectStore(project)
        card = ClarificationQuestion(question="Which entity?",
                                     claim_ids=report.claims_created)
        store.save_question(card)

        with pytest.raises(PromotionError):
            answer_question(store, card.id)  # no scope
        after = ProjectStore(project)
        assert not [e for e in after.evidence.values()
                    if e.type is EvidenceType.CONFIRMATION]

    def test_a_card_resting_on_nothing_cannot_be_answered(self, project):
        from before_we_ai.core.objects import ClarificationQuestion

        store = ProjectStore(project)
        card = ClarificationQuestion(question="Anything?")
        store.save_question(card)
        with pytest.raises(ValueError, match="settle nothing"):
            answer_question(store, card.id)


class TestTheReportSaysTheSameThingAsTheLaw:
    """The bug M5 made reachable, and the reason it was worth waiting for.

    ``_status_rationale`` used to count every confirmation while
    ``resolve_status`` counted only admissible ones. A claim could read
    status ``proposed``, trail "1 confirmation", why "nothing stronger
    than proposed evidence is live yet" — three statements a reader cannot
    reconcile. Nothing created confirmations until now, so nothing could
    see it.
    """

    def _confirmed_without_scope(self, project, guide):
        """A store that already holds an unscoped confirmation.

        Every supported path refuses to create one — ``attach_evidence``
        enforces the rule, which is why this has to be assembled by hand.
        The state is still reachable on disk: evidence files are
        append-only and the mirror-loop rule has not always existed, so a
        project written earlier can carry exactly this record. The report
        must explain it rather than contradict itself over it.
        """
        from before_we_ai.core.objects import EvidenceRecord

        report = tell(project, F29, guide=guide,
                      client=_structures(F29, "fiscal year", "May to April"))
        store = ProjectStore(project)
        claim = store.claims[report.claims_created[0]]
        record = EvidenceRecord(type=EvidenceType.CONFIRMATION,
                                actor=Actor.HUMAN, claim_id=claim.id)
        store.add_evidence(record)
        store.save_claim(claim.model_copy(
            update={"evidence_ids": [*claim.evidence_ids, record.id]}))
        return ProjectStore(project), claim.id

    def test_the_claim_is_not_promoted(self, project, guide):
        store, claim_id = self._confirmed_without_scope(project, guide)
        assert store.claims[claim_id].status is ClaimStatus.PROPOSED

    def test_the_sentence_no_longer_contradicts_itself(self, project, guide):
        from readiness_report.projection import _status_rationale

        store, claim_id = self._confirmed_without_scope(project, guide)
        claim = store.claims[claim_id]
        sentence = _status_rationale(claim, store.evidence_for(claim))

        assert "count for nothing" in sentence
        assert "names no scope" in sentence
        assert "Nothing stronger than proposed evidence" not in sentence

    def test_an_admissible_confirmation_still_reads_plainly(
            self, project, guide):
        from readiness_report.projection import _status_rationale

        report = tell(project, F29, guide=guide,
                      client=_structures(F29, "fiscal year", "May to April"))
        store = ProjectStore(project)
        confirm_claim(store, report.claims_created[0], scope=Scope(entity="US"))

        store = ProjectStore(project)
        claim = store.claims[report.claims_created[0]]
        sentence = _status_rationale(claim, store.evidence_for(claim))
        assert "1 confirmation" in sentence
        assert "count for nothing" not in sentence


class TestAParkedStatementIsStillOnTheRecord:
    """Somebody said it, on a date. That is a fact whatever came of it.

    Found while reading the decision log: a statement the model could not
    structure left a searchable note and no evidence at all, so it vanished
    from every surface a person actually reads. The spec stores the words
    unconditionally, and a claim-less record is ordinary here — every
    normalization declaration is one.
    """

    def test_the_words_are_evidence_even_with_no_claim(self, project, guide):
        tell(project, "Things have been difficult lately.", guide=guide,
             client=_ScriptedClient([]))
        store = ProjectStore(project)
        testimonials = [e for e in store.evidence.values()
                        if e.type is EvidenceType.TESTIMONIAL]
        assert [e.statement for e in testimonials] == [
            "Things have been difficult lately."]
        assert testimonials[0].claim_id is None

    def test_it_promotes_nothing_because_there_is_nothing_to_promote(
            self, project, guide):
        tell(project, "Things have been difficult lately.", guide=guide,
             client=_ScriptedClient([]))
        assert ProjectStore(project).claims == {}
