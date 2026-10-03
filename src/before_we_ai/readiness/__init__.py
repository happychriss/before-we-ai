"""What the system is permitted to claim about one requested answer.

Deliberately its own package. The epistemic core decides what may be
*believed* from evidence; this decides what may be *claimed* from those
beliefs, and the two must not blur into each other — that separation is the
handover principle the whole design rests on.

Nothing here persists anything. The ReadinessMap is derived on every read,
like ``resolve_status``, so it can never drift from the claims and evidence
under it.
"""

from before_we_ai.readiness.assemble import (
    REVIEWED,
    Assembly,
    Review,
    assemble,
    guide_label,
)
from before_we_ai.readiness.evaluate import (
    Ground,
    Readiness,
    ReadinessItem,
    ReadinessMap,
    UnlinkableItem,
    add_item,
    confirm_classification,
    evaluate,
    evaluate_request,
    link_claim,
    require_again,
    waive_item,
)
from before_we_ai.readiness.expand import UnknownAnswerType, expand

__all__ = [
    "REVIEWED",
    "Assembly",
    "Ground",
    "Readiness",
    "ReadinessItem",
    "ReadinessMap",
    "Review",
    "UnknownAnswerType",
    "UnlinkableItem",
    "add_item",
    "assemble",
    "confirm_classification",
    "evaluate",
    "evaluate_request",
    "expand",
    "guide_label",
    "link_claim",
    "require_again",
    "waive_item",
]
