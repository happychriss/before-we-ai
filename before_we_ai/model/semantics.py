"""Rule identity and impact — pure derivations over claims and questions.

``claim_key`` gives a parameterised claim a deterministic identity so the
same rule proposed twice (different wording, different session) lands on
one claim. Impact is never stored: which questions rest on a claim is
derived from the question cards' bills of materials, so it can never
drift from reality.
"""

import hashlib
import json
from collections.abc import Iterable

from before_we_ai.model.enums import ClaimStatus
from before_we_ai.model.objects import Claim, QuestionCard

_PROVEN = (ClaimStatus.TESTED, ClaimStatus.BUSINESS_CONFIRMED)


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
    claim_id: str, questions: Iterable[QuestionCard]
) -> list[QuestionCard]:
    """All question cards whose bill of materials includes the claim."""
    return [q for q in questions if claim_id in q.claim_ids]


def gap_load(
    claims: Iterable[Claim], questions: Iterable[QuestionCard]
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
