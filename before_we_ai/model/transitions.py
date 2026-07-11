"""State machine and promotion rules — pure functions, no IO.

The epistemic laws implemented here:

* AI can only create ``inferred`` claims; nothing an AI authors ever
  changes a status.
* Only probe results and human confirmations promote.
* Conflicting evidence forces ``unresolved`` — conflict is never averaged
  away and never silently resolved by recency.
* A confirmation on a testimonial claim must carry an explicit scope
  (mirror-loop); without it the confirmation is inadmissible.
* Stale evidence carries no epistemic weight.

Status is always *derived* from the evidence list via ``resolve_status``;
the stored status field is a cached rendering of that derivation.
"""

from before_we_ai.model.enums import Actor, ClaimStatus, EvidenceType, ProbeVerdict
from before_we_ai.model.objects import Claim, EvidenceRecord, Scope


class PromotionError(Exception):
    """Raised when evidence would violate a promotion rule."""


def create_claim(
    statement: str,
    created_by: Actor,
    *,
    depends_on: list[str] | None = None,
    scope: Scope | None = None,
    open_assumptions: list[str] | None = None,
) -> Claim:
    """Create a claim. Every claim starts ``inferred`` — no exceptions.

    Promotion happens only afterwards, through evidence.
    """
    return Claim(
        statement=statement,
        created_by=created_by,
        status=ClaimStatus.INFERRED,
        depends_on=depends_on or [],
        scope=scope,
        open_assumptions=open_assumptions or [],
    )


def is_testimonial(claim: Claim, evidence: list[EvidenceRecord]) -> bool:
    """A claim is testimonial if it rests on a user statement."""
    return any(
        e.type is EvidenceType.TESTIMONIAL and not e.stale
        for e in _for_claim(claim, evidence)
    )


def _for_claim(claim: Claim, evidence: list[EvidenceRecord]) -> list[EvidenceRecord]:
    ids = set(claim.evidence_ids)
    return [e for e in evidence if e.id in ids]


def _confirmation_admissible(
    record: EvidenceRecord, claim: Claim, evidence: list[EvidenceRecord]
) -> bool:
    """Mirror-loop rule: confirming a testimonial claim requires explicit scope."""
    if record.type is not EvidenceType.CONFIRMATION:
        return True
    if not is_testimonial(claim, evidence):
        return True
    return record.scope is not None and record.scope.is_explicit()


def admit_evidence(
    claim: Claim, record: EvidenceRecord, evidence: list[EvidenceRecord]
) -> None:
    """Check a new evidence record against the claim before attaching it.

    Raises PromotionError if the record is inadmissible. ``evidence`` is
    the claim's existing evidence (the new record not yet attached).
    """
    if not _confirmation_admissible(record, claim, evidence):
        raise PromotionError(
            "confirmation of a testimonial claim requires an explicit scope "
            "(mirror-loop): entity, period or segment must be stated"
        )


def resolve_status(claim: Claim, evidence: list[EvidenceRecord]) -> ClaimStatus:
    """Derive the claim's status from its non-stale evidence.

    Order-independent: the same evidence set always yields the same status,
    regardless of arrival order. Weak evidence (document anchors,
    declarations, the testimonial statement itself) never promotes.
    """
    live = [e for e in _for_claim(claim, evidence) if not e.stale]

    probe_pass = any(
        e.type is EvidenceType.PROBE_RESULT and e.verdict is ProbeVerdict.PASS
        for e in live
    )
    probe_fail = any(
        e.type is EvidenceType.PROBE_RESULT and e.verdict is ProbeVerdict.FAIL
        for e in live
    )
    testimonial = any(e.type is EvidenceType.TESTIMONIAL for e in live)
    confirmed = any(
        e.type is EvidenceType.CONFIRMATION
        and _confirmation_admissible(e, claim, evidence)
        for e in live
    )

    if probe_fail and (probe_pass or confirmed or testimonial):
        # Conflict: contradicting probe vs. supporting probe, human
        # confirmation, or user statement. Conflict forces unresolved —
        # this is also the only expiry of business-confirmed claims.
        return ClaimStatus.UNRESOLVED
    if probe_fail:
        return ClaimStatus.CONTRADICTED
    if confirmed:
        return ClaimStatus.BUSINESS_CONFIRMED
    if probe_pass:
        return ClaimStatus.TESTED
    return ClaimStatus.INFERRED


def attach_evidence(
    claim: Claim, record: EvidenceRecord, evidence: list[EvidenceRecord]
) -> Claim:
    """Attach a record to the claim and recompute its status.

    Returns an updated copy; raises PromotionError if inadmissible.
    ``evidence`` is the claim's existing evidence records.
    """
    admit_evidence(claim, record, evidence)
    updated = claim.model_copy(
        update={"evidence_ids": [*claim.evidence_ids, record.id]}
    )
    updated.status = resolve_status(updated, [*evidence, record])
    return updated
