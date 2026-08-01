"""The epistemic core: the objects, the state machine, the promotion rules.

No IO, no filesystem, no network. Everything here is unit-testable in
isolation; persistence lives in ``before_we_ai.store``.

Named ``core`` and not ``model`` on purpose. Throughout this codebase "the
model" means the LLM, and the central safety argument is about what the
model may and may not do — ``Actor.AI`` cannot author promoting evidence.
Importing that very constraint from a package called ``model`` invited the
wrong reading, and pydantic's ``model_validate`` / ``model_dump`` /
``model_config`` sit on the same prefix. The prose has always called this
the epistemic core; the package now agrees with it.
"""

from before_we_ai.core.enums import (
    Actor,
    ClaimStatus,
    EvidenceType,
    CheckVerdict,
    KnowledgeKind,
)
from before_we_ai.core.ids import new_id
from before_we_ai.core.objects import (
    MAX_EXCEPTION_SAMPLES,
    AnswerRequest,
    Claim,
    DataProfile,
    ConceptClaim,
    EvidenceRecord,
    KnowledgeItem,
    KnowledgeLink,
    Predicate,
    CheckPlan,
    ClarificationQuestion,
    MappingClaim,
    RequiredKnowledge,
    Scope,
    Source,
    Validity,
)
from before_we_ai.core.scheduler import CycleError, ready_for_check, topological_order
from before_we_ai.core.semantics import (
    claim_key,
    gap_load,
    is_answered,
    questions_resting_on,
    settling_claims,
)
from before_we_ai.core.transitions import (
    PromotionError,
    create_claim,
    escalate_exception,
    resolve_status,
)

__all__ = [
    "Actor",
    "AnswerRequest",
    "Claim",
    "ClaimStatus",
    "DataProfile",
    "ConceptClaim",
    "CycleError",
    "EvidenceRecord",
    "EvidenceType",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeLink",
    "MAX_EXCEPTION_SAMPLES",
    "Predicate",
    "CheckPlan",
    "CheckVerdict",
    "PromotionError",
    "ClarificationQuestion",
    "MappingClaim",
    "RequiredKnowledge",
    "Scope",
    "Source",
    "Validity",
    "claim_key",
    "create_claim",
    "escalate_exception",
    "gap_load",
    "is_answered",
    "new_id",
    "questions_resting_on",
    "resolve_status",
    "settling_claims",
    "topological_order",
]
