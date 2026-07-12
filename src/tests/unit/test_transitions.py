"""All promotion paths of the state machine — the M1 acceptance suite.

The tests deliberately punish decisiveness where `unresolved` is correct,
and prove that no AI-authored evidence can ever promote a claim
(False-Promotion-Rate = 0 as a structural property).
"""

import pytest
from pydantic import ValidationError

from before_we_ai.model import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    ProbeVerdict,
    PromotionError,
    Scope,
    create_claim,
)
from before_we_ai.model.transitions import attach_evidence, resolve_status


def probe(verdict: ProbeVerdict) -> EvidenceRecord:
    return EvidenceRecord(
        type=EvidenceType.PROBE_RESULT, actor=Actor.PROBE, verdict=verdict
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
    def test_every_claim_starts_inferred(self, actor):
        assert create_claim("x", actor).status is ClaimStatus.INFERRED


class TestPromotionMatrix:
    """(evidence set) -> expected status, independent of arrival order."""

    CASES = [
        ([], ClaimStatus.INFERRED),
        ([probe(ProbeVerdict.PASS)], ClaimStatus.TESTED),
        ([probe(ProbeVerdict.FAIL)], ClaimStatus.CONTRADICTED),
        ([probe(ProbeVerdict.INCONCLUSIVE)], ClaimStatus.INFERRED),
        ([anchor()], ClaimStatus.INFERRED),
        ([declaration()], ClaimStatus.INFERRED),
        ([tell()], ClaimStatus.INFERRED),
        ([confirmation()], ClaimStatus.BUSINESS_CONFIRMED),
        # conflict forces unresolved
        ([probe(ProbeVerdict.PASS), probe(ProbeVerdict.FAIL)], ClaimStatus.UNRESOLVED),
        ([confirmation(), probe(ProbeVerdict.FAIL)], ClaimStatus.UNRESOLVED),
        ([tell(), probe(ProbeVerdict.FAIL)], ClaimStatus.UNRESOLVED),
        # confirmation outranks a passing probe, fail still forces conflict
        ([confirmation(), probe(ProbeVerdict.PASS)], ClaimStatus.BUSINESS_CONFIRMED),
        (
            [confirmation(), probe(ProbeVerdict.PASS), probe(ProbeVerdict.FAIL)],
            ClaimStatus.UNRESOLVED,
        ),
        # weak evidence adds nothing on top of strong evidence
        ([anchor(), probe(ProbeVerdict.PASS)], ClaimStatus.TESTED),
        ([anchor(), declaration(), probe(ProbeVerdict.FAIL)], ClaimStatus.CONTRADICTED),
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
    def test_ai_evidence_never_leaves_inferred(self):
        # every evidence type an AI is allowed to author, stacked together
        records = [anchor(), declaration(), anchor(), declaration()]
        claim, evidence = with_evidence(records)
        assert resolve_status(claim, evidence) is ClaimStatus.INFERRED

    def test_ai_cannot_author_probe_results(self):
        with pytest.raises(ValidationError):
            EvidenceRecord(
                type=EvidenceType.PROBE_RESULT,
                actor=Actor.AI,
                verdict=ProbeVerdict.PASS,
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
        assert resolve_status(claim, evidence) is ClaimStatus.INFERRED


class TestBusinessConfirmedExpiry:
    def test_contradicting_probe_pulls_confirmed_claim_to_unresolved(self):
        claim, evidence = with_evidence([tell(), confirmation(Scope(entity="US"))])
        assert resolve_status(claim, evidence) is ClaimStatus.BUSINESS_CONFIRMED
        failing = probe(ProbeVerdict.FAIL)
        updated = attach_evidence(claim, failing, evidence)
        assert updated.status is ClaimStatus.UNRESOLVED


class TestStaleness:
    def test_stale_evidence_carries_no_weight(self):
        passing = probe(ProbeVerdict.PASS)
        claim, evidence = with_evidence([passing])
        assert resolve_status(claim, evidence) is ClaimStatus.TESTED
        stale = passing.model_copy(update={"stale": True})
        assert resolve_status(claim, [stale]) is ClaimStatus.INFERRED

    def test_stale_contradiction_releases_conflict(self):
        passing, failing = probe(ProbeVerdict.PASS), probe(ProbeVerdict.FAIL)
        claim, evidence = with_evidence([passing, failing])
        assert resolve_status(claim, evidence) is ClaimStatus.UNRESOLVED
        stale_fail = failing.model_copy(update={"stale": True})
        assert resolve_status(claim, [passing, stale_fail]) is ClaimStatus.TESTED


class TestEvidenceScoping:
    def test_unreferenced_evidence_has_no_effect(self):
        claim = create_claim("x", Actor.AI)  # no evidence_ids
        assert resolve_status(claim, [probe(ProbeVerdict.FAIL)]) is ClaimStatus.INFERRED

    def test_attach_evidence_appends_and_recomputes(self):
        claim = create_claim("x", Actor.AI)
        record = probe(ProbeVerdict.PASS)
        updated = attach_evidence(claim, record, [])
        assert updated.evidence_ids == [record.id]
        assert updated.status is ClaimStatus.TESTED
        assert claim.status is ClaimStatus.INFERRED  # original untouched
