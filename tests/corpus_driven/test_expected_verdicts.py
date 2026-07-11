"""Bridge to the frozen corpus (m0-corpus-v1).

These tests parametrize the M1 state machine from
``corpus/data/expected_verdicts.yaml`` — ground truth is read on the TEST
side only; the product package never imports or reads anything under
``corpus/``. For each trap we script the evidence sequence its trap class
(K1–K8) implies and assert the epistemic core lands on the corpus's
expected behavior. Because the checks key off K-class tags rather than
trap IDs, the owner's blind traps are exercised automatically.
"""

from pathlib import Path

import pytest
import yaml

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

GROUND_TRUTH = Path(__file__).resolve().parents[2] / "corpus" / "data" / "expected_verdicts.yaml"

_DATA = yaml.safe_load(GROUND_TRUTH.read_text(encoding="utf-8"))
TRAPS = _DATA["traps"]
DENY_SET = set(_DATA["deny_set"])


def classes(trap: dict) -> set[str]:
    return set(trap["category"].split(","))


def trap_ids(predicate) -> list[str]:
    return [tid for tid, trap in sorted(TRAPS.items()) if predicate(tid, trap)]


def claim_for(tid: str, records: list[EvidenceRecord]):
    claim = create_claim(TRAPS[tid]["description"], Actor.AI)
    claim = claim.model_copy(update={"evidence_ids": [r.id for r in records]})
    return claim


ALL = trap_ids(lambda tid, t: True)
DENY = trap_ids(lambda tid, t: t.get("deny_promotion") or tid in DENY_SET)
K6_ORPHANS = trap_ids(lambda tid, t: "K6" in classes(t))
K8_TELL = trap_ids(lambda tid, t: "K8" in classes(t))


def test_every_recall_trap_is_representable():
    """recall_set: every trap must be able to exist as a claim — inferred."""
    for tid in _DATA["recall_set"]:
        assert tid in TRAPS
        assert claim_for(tid, []).status is ClaimStatus.INFERRED


@pytest.mark.parametrize("tid", DENY)
def test_deny_traps_never_promote_on_ai_evidence(tid):
    """K7 poisoned anchors: the tempting evidence is a document hit authored
    by AI (a press-release number, a chart-only figure, a restated value).
    No stack of such evidence may ever move the claim past inferred."""
    records = [
        EvidenceRecord(type=EvidenceType.DOCUMENT_ANCHOR, actor=Actor.AI),
        EvidenceRecord(type=EvidenceType.DOCUMENT_ANCHOR, actor=Actor.AI),
        EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI),
    ]
    claim = claim_for(tid, records)
    assert resolve_status(claim, records) is ClaimStatus.INFERRED


@pytest.mark.parametrize("tid", K6_ORPHANS)
def test_k6_orphans_are_not_contradictions(tid):
    """K6 legitimate orphans: the probe finding is inconclusive (a business
    question), never a contradiction — Waise ist kein Fehler."""
    records = [
        EvidenceRecord(
            type=EvidenceType.PROBE_RESULT,
            actor=Actor.PROBE,
            verdict=ProbeVerdict.INCONCLUSIVE,
        )
    ]
    claim = claim_for(tid, records)
    status = resolve_status(claim, records)
    assert status is not ClaimStatus.CONTRADICTED
    assert status is ClaimStatus.INFERRED  # open question, still unpromoted


@pytest.mark.parametrize("tid", K8_TELL)
def test_k8_statement_contradicted_by_data_goes_unresolved(tid):
    """F28 pattern: a user statement vs. a contradicting probe is a loud
    conflict — the statement must not silently win, nor silently lose."""
    records = [
        EvidenceRecord(
            type=EvidenceType.TESTIMONIAL,
            actor=Actor.HUMAN,
            statement=TRAPS[tid]["description"],
        ),
        EvidenceRecord(
            type=EvidenceType.PROBE_RESULT,
            actor=Actor.PROBE,
            verdict=ProbeVerdict.FAIL,
        ),
    ]
    claim = claim_for(tid, records)
    assert resolve_status(claim, records) is ClaimStatus.UNRESOLVED


@pytest.mark.parametrize("tid", K8_TELL)
def test_k8_confirmation_requires_explicit_scope(tid):
    """F29 pattern: the mirror-loop must ask for the scope; a confirmation
    that never states one cannot lift the statement to business-confirmed."""
    testimonial = EvidenceRecord(
        type=EvidenceType.TESTIMONIAL,
        actor=Actor.HUMAN,
        statement=TRAPS[tid]["description"],
    )
    claim = claim_for(tid, [testimonial])
    scopeless = EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN)
    with pytest.raises(PromotionError):
        attach_evidence(claim, scopeless, [testimonial])

    scoped = EvidenceRecord(
        type=EvidenceType.CONFIRMATION,
        actor=Actor.HUMAN,
        scope=Scope(entity="US"),
    )
    updated = attach_evidence(claim, scoped, [testimonial])
    assert updated.status is ClaimStatus.BUSINESS_CONFIRMED


def test_false_promotion_rate_is_zero_across_all_traps():
    """The hard invariant, run over the whole catalog: with only weak or
    AI-authorable evidence, not a single trap claim ends up promoted."""
    promoted = []
    for tid in ALL:
        records = [
            EvidenceRecord(type=EvidenceType.DOCUMENT_ANCHOR, actor=Actor.AI),
            EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI),
        ]
        claim = claim_for(tid, records)
        if resolve_status(claim, records) is not ClaimStatus.INFERRED:
            promoted.append(tid)
    assert promoted == [], f"false promotions: {promoted}"
