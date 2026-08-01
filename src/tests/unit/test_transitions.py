"""All promotion paths of the state machine — the M1 acceptance suite.

The tests deliberately punish decisiveness where `unresolved` is correct,
and prove that no AI-authored evidence can ever promote a claim
(False-Promotion-Rate = 0 as a structural property).
"""

import pytest
from pydantic import ValidationError

from before_we_ai.core import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    CheckVerdict,
    PromotionError,
    Scope,
    create_claim,
)
from before_we_ai.core.transitions import attach_evidence, resolve_status


def check(verdict: CheckVerdict) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK, verdict=verdict
    )


def confirmation(scope: Scope | None = None) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN, scope=scope
    )


def tell(statement: str = "Wir beliefern nur Apotheken.") -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.TESTIMONIAL, actor=Actor.HUMAN, statement=statement
    )


def anchor(actor: Actor = Actor.AI) -> EvidenceRecord:
    return EvidenceRecord(type=EvidenceType.DOCUMENT_ANCHOR, actor=actor)


def declaration() -> EvidenceRecord:
    return EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)


def with_evidence(records: list[EvidenceRecord], **claim_kw):
    claim = create_claim("test claim", Actor.AI, **claim_kw)
    claim = claim.model_copy(update={"evidence_ids": [r.id for r in records]})
    return claim, records


class TestCreation:
    @pytest.mark.parametrize("actor", list(Actor))
    def test_every_claim_starts_proposed(self, actor):
        assert create_claim("x", actor).status is ClaimStatus.PROPOSED


class TestPromotionMatrix:
    """(evidence set) -> expected status, independent of arrival order."""

    CASES = [
        ([], ClaimStatus.PROPOSED),
        ([check(CheckVerdict.PASS)], ClaimStatus.TEST_SUPPORTED),
        ([check(CheckVerdict.FAIL)], ClaimStatus.CONTRADICTED),
        ([check(CheckVerdict.INCONCLUSIVE)], ClaimStatus.PROPOSED),
        ([anchor()], ClaimStatus.PROPOSED),
        ([declaration()], ClaimStatus.PROPOSED),
        ([tell()], ClaimStatus.PROPOSED),
        ([confirmation()], ClaimStatus.BUSINESS_CONFIRMED),
        # conflict forces unresolved
        ([check(CheckVerdict.PASS), check(CheckVerdict.FAIL)], ClaimStatus.UNRESOLVED),
        ([confirmation(), check(CheckVerdict.FAIL)], ClaimStatus.UNRESOLVED),
        ([tell(), check(CheckVerdict.FAIL)], ClaimStatus.UNRESOLVED),
        # confirmation outranks a passing check, fail still forces conflict
        ([confirmation(), check(CheckVerdict.PASS)], ClaimStatus.BUSINESS_CONFIRMED),
        (
            [confirmation(), check(CheckVerdict.PASS), check(CheckVerdict.FAIL)],
            ClaimStatus.UNRESOLVED,
        ),
        # weak evidence adds nothing on top of strong evidence
        ([anchor(), check(CheckVerdict.PASS)], ClaimStatus.TEST_SUPPORTED),
        ([anchor(), declaration(), check(CheckVerdict.FAIL)], ClaimStatus.CONTRADICTED),
    ]

    @pytest.mark.parametrize("records,expected", CASES)
    def test_forward(self, records, expected):
        claim, evidence = with_evidence(records)
        assert resolve_status(claim, evidence) is expected

    @pytest.mark.parametrize("records,expected", CASES)
    def test_order_independent(self, records, expected):
        claim, evidence = with_evidence(list(reversed(records)))
        assert resolve_status(claim, evidence) is expected


class TestAICannotPromote:
    def test_ai_evidence_never_leaves_proposed(self):
        # every evidence type an AI is allowed to author, stacked together
        records = [anchor(), declaration(), anchor(), declaration()]
        claim, evidence = with_evidence(records)
        assert resolve_status(claim, evidence) is ClaimStatus.PROPOSED

    def test_ai_cannot_author_check_results(self):
        with pytest.raises(ValidationError):
            EvidenceRecord(
                type=EvidenceType.CHECK_RESULT,
                actor=Actor.AI,
                verdict=CheckVerdict.PASS,
            )

    @pytest.mark.parametrize(
        "ev_type", [EvidenceType.CONFIRMATION, EvidenceType.TESTIMONIAL]
    )
    def test_ai_cannot_author_human_evidence(self, ev_type):
        with pytest.raises(ValidationError):
            EvidenceRecord(type=ev_type, actor=Actor.AI, statement="x")


class TestMirrorLoop:
    """F29 law: confirming a testimonial claim requires an explicit scope."""

    def test_scopeless_confirmation_on_testimonial_claim_is_rejected(self):
        claim, evidence = with_evidence([tell()])
        with pytest.raises(PromotionError):
            attach_evidence(claim, confirmation(), evidence)

    def test_empty_scope_counts_as_scopeless(self):
        claim, evidence = with_evidence([tell()])
        with pytest.raises(PromotionError):
            attach_evidence(claim, confirmation(Scope()), evidence)

    def test_scoped_confirmation_promotes_testimonial_claim(self):
        claim, evidence = with_evidence([tell()])
        record = confirmation(Scope(entity="US"))
        updated = attach_evidence(claim, record, evidence)
        assert updated.status is ClaimStatus.BUSINESS_CONFIRMED

    def test_scopeless_confirmation_fine_on_non_testimonial_claim(self):
        claim = create_claim("x", Actor.AI)
        updated = attach_evidence(claim, confirmation(), [])
        assert updated.status is ClaimStatus.BUSINESS_CONFIRMED

    def test_force_attached_scopeless_confirmation_still_does_not_promote(self):
        # defense in depth: even bypassing attach_evidence, the derivation
        # refuses to count an inadmissible confirmation
        claim, evidence = with_evidence([tell(), confirmation()])
        assert resolve_status(claim, evidence) is ClaimStatus.PROPOSED


class TestBusinessConfirmedExpiry:
    def test_contradicting_check_pulls_confirmed_claim_to_unresolved(self):
        claim, evidence = with_evidence([tell(), confirmation(Scope(entity="US"))])
        assert resolve_status(claim, evidence) is ClaimStatus.BUSINESS_CONFIRMED
        failing = check(CheckVerdict.FAIL)
        updated = attach_evidence(claim, failing, evidence)
        assert updated.status is ClaimStatus.UNRESOLVED


class TestStaleness:
    def test_stale_evidence_carries_no_weight(self):
        passing = check(CheckVerdict.PASS)
        claim, evidence = with_evidence([passing])
        assert resolve_status(claim, evidence) is ClaimStatus.TEST_SUPPORTED
        stale = passing.model_copy(update={"stale": True})
        assert resolve_status(claim, [stale]) is ClaimStatus.PROPOSED

    def test_stale_contradiction_releases_conflict(self):
        passing, failing = check(CheckVerdict.PASS), check(CheckVerdict.FAIL)
        claim, evidence = with_evidence([passing, failing])
        assert resolve_status(claim, evidence) is ClaimStatus.UNRESOLVED
        stale_fail = failing.model_copy(update={"stale": True})
        assert resolve_status(claim, [passing, stale_fail]) is ClaimStatus.TEST_SUPPORTED


class TestEvidenceScoping:
    def test_unreferenced_evidence_has_no_effect(self):
        claim = create_claim("x", Actor.AI)  # no evidence_ids
        assert resolve_status(claim, [check(CheckVerdict.FAIL)]) is ClaimStatus.PROPOSED

    def test_attach_evidence_appends_and_recomputes(self):
        claim = create_claim("x", Actor.AI)
        record = check(CheckVerdict.PASS)
        updated = attach_evidence(claim, record, [])
        assert updated.evidence_ids == [record.id]
        assert updated.status is ClaimStatus.TEST_SUPPORTED
        assert claim.status is ClaimStatus.PROPOSED  # original untouched
