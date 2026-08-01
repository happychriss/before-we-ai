"""The store capabilities available to model-facing proposal code.

The LLM layer may read project state and persist proposals. It does not
receive the general evidence-writing or staleness capabilities: each weak
evidence kind gets a narrow method that fixes its type and actor.
"""

from collections.abc import Mapping
from types import MappingProxyType

from before_we_ai.core.enums import Actor, EvidenceType
from before_we_ai.core.objects import (
    AnswerRequest,
    CheckPlan,
    Claim,
    ClarificationQuestion,
    DataProfile,
    EvidenceRecord,
    KnowledgeAct,
    RequiredKnowledge,
    Source,
)
from before_we_ai.core.transitions import attach_evidence
from before_we_ai.store.repository import ProjectStore


class ProposalStore:
    """Read project state and persist proposals without promotion authority."""

    def __init__(self, store: ProjectStore):
        self.__store = store

    # -- reading ---------------------------------------------------------

    @property
    def claims(self) -> Mapping[str, Claim]:
        return MappingProxyType(self.__store.claims)

    @property
    def evidence(self) -> Mapping[str, EvidenceRecord]:
        return MappingProxyType(self.__store.evidence)

    @property
    def questions(self) -> Mapping[str, ClarificationQuestion]:
        return MappingProxyType(self.__store.questions)

    @property
    def sources(self) -> Mapping[str, Source]:
        return MappingProxyType(self.__store.sources)

    @property
    def profiles(self) -> Mapping[str, DataProfile]:
        return MappingProxyType(self.__store.profiles)

    @property
    def checks(self) -> Mapping[str, CheckPlan]:
        return MappingProxyType(self.__store.checks)

    @property
    def requests(self) -> Mapping[str, AnswerRequest]:
        return MappingProxyType(self.__store.requests)

    @property
    def required(self) -> Mapping[str, RequiredKnowledge]:
        return MappingProxyType(self.__store.required)

    @property
    def acts(self) -> Mapping[str, KnowledgeAct]:
        return MappingProxyType(self.__store.acts)

    def find_claim(self, key: str) -> Claim | None:
        return self.__store.find_claim(key)

    def find_question(
        self, card: ClarificationQuestion
    ) -> ClarificationQuestion | None:
        return self.__store.find_question(card)

    def knowledge_for(self, request_id: str) -> RequiredKnowledge | None:
        return self.__store.knowledge_for(request_id)

    def acts_for(self, request_id: str) -> list[KnowledgeAct]:
        return self.__store.acts_for(request_id)

    def evidence_for(self, claim: Claim) -> list[EvidenceRecord]:
        return self.__store.evidence_for(claim)

    # -- proposal writing ------------------------------------------------

    def save_claim(self, claim: Claim) -> None:
        self.__store.save_claim(claim)

    def add_claim(self, claim: Claim) -> Claim:
        return self.__store.add_claim(claim)

    def save_check_plan(self, check: CheckPlan) -> None:
        self.__store.save_check_plan(check)

    def save_question(self, card: ClarificationQuestion) -> None:
        self.__store.save_question(card)

    def save_request(self, request: AnswerRequest) -> None:
        self.__store.save_request(request)

    def save_required_knowledge(self, required: RequiredKnowledge) -> None:
        self.__store.save_required_knowledge(required)

    def declare(self, claim_id: str, payload: dict[str, object]) -> None:
        """Attach one SYSTEM declaration, which cannot promote its claim."""
        self.__attach(
            EvidenceRecord(
                type=EvidenceType.DECLARATION,
                actor=Actor.SYSTEM,
                claim_id=claim_id,
                payload=payload,
            )
        )

    def __attach(self, record: EvidenceRecord) -> None:
        """Persist a narrowly constructed weak record and update its claim."""
        claim = self.__store.claims[record.claim_id]
        existing = self.__store.evidence_for(claim)
        self.__store.add_evidence(record)
        self.__store.save_claim(attach_evidence(claim, record, existing))
