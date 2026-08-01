"""Rule identity and impact — pure derivations over claims and questions.

``claim_key`` gives a parameterised claim a deterministic identity so the
same rule proposed twice (different wording, different session) lands on
one claim. Impact is never stored: which questions rest on a claim is
derived from the question cards' bills of materials, so it can never
drift from reality.
"""

import hashlib
import json
from collections.abc import Iterable, Mapping

from before_we_ai.core.enums import ClaimStatus
from before_we_ai.core.objects import Claim, ClarificationQuestion

_PROVEN = (ClaimStatus.TEST_SUPPORTED, ClaimStatus.BUSINESS_CONFIRMED)


def claim_key(claim: Claim) -> str | None:
    """Deterministic identity of a parameterised claim, or None.

    Built from what the rule *is* — predicate name + params, scope,
    validity, affected sources — never from its wording: the same rule
    phrased two ways is one claim. Free-text claims (no predicate) have no
    key and never deduplicate.
    """
    if claim.predicate is None:
        return None
    material = {
        "predicate": claim.predicate.name,
        "params": claim.predicate.params,
        "scope": claim.scope.model_dump() if claim.scope else None,
        "validity": claim.validity.model_dump() if claim.validity else None,
        "sources": sorted(claim.source_ids),
    }
    canonical = json.dumps(material, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def questions_resting_on(
    claim_id: str, questions: Iterable[ClarificationQuestion]
) -> list[ClarificationQuestion]:
    """All question cards whose bill of materials includes the claim."""
    return [q for q in questions if claim_id in q.claim_ids]


def is_answered(card: ClarificationQuestion,
                claims: Mapping[str, Claim]) -> bool:
    """Has this question been answered? Derived, never stored.

    A card is answered when at least one claim it rests on has settled. For
    a pick-one-of-these card that is exactly right: the human chose, the
    chosen candidate carries their confirmation, the question is done. For
    a card the engine drafted over a failing check it is right the other
    way round — that claim is ``contradicted``, never settled, so the
    question stays open until someone deals with it. A card resting on no
    claim at all (nothing was ever proposed) can never be answered this
    way, which is also correct: nothing has changed for it.

    Derived rather than flagged because a stored "answered" is a fact that
    can fall out of step with the evidence — the same reason status and
    readiness are derived. It is what keeps the open-questions list and
    the ReadinessMap from disagreeing about the same store.
    """
    return any(
        cid in claims and claims[cid].status in _PROVEN
        for cid in card.claim_ids
    )


def settling_claims(card: ClarificationQuestion,
                    claims: Mapping[str, Claim]) -> list[Claim]:
    """The settled claims that answer this card — what to show instead of
    the question."""
    return [claims[cid] for cid in card.claim_ids
            if cid in claims and claims[cid].status in _PROVEN]


def gap_load(
    claims: Iterable[Claim], questions: Iterable[ClarificationQuestion]
) -> list[tuple[Claim, int]]:
    """Unproven claims ranked by how many questions rest on them.

    This is the impact measure: an untested assumption carrying five
    questions outranks one carrying none. Proven claims (tested,
    business-confirmed) carry no gap load.
    """
    cards = list(questions)
    ranked = [
        (claim, len(questions_resting_on(claim.id, cards)))
        for claim in claims
        if claim.status not in _PROVEN
    ]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked
