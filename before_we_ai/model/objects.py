"""Pydantic models of the epistemic core.

All cross-references run over ULIDs, never nested objects — the store keeps
one YAML file per object and ``integrity`` checks that every reference
resolves. None of these models performs IO.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, Field, model_validator

from before_we_ai.model.enums import Actor, ClaimStatus, EvidenceType, ProbeVerdict
from before_we_ai.model.ids import new_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Scope(BaseModel):
    """Explicit validity scope of a claim or confirmation.

    The mirror-loop requires the scope to be spelled out (entity, period,
    segment) before a testimonial claim may become business-confirmed —
    "gilt für: alle Gesellschaften?" must have been answered, not assumed.
    """

    entity: str | None = None
    period: str | None = None
    segment: str | None = None

    def is_explicit(self) -> bool:
        return any(v is not None for v in (self.entity, self.period, self.segment))


class Source(BaseModel):
    """A connected data source (database, file drop, document)."""

    id: str = Field(default_factory=new_id)
    name: str
    kind: str  # e.g. "duckdb", "csv", "xlsx", "pdf", "text"
    location: str
    fingerprint: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class ColumnProfile(BaseModel):
    """Measured statistics of one column — input for hypotheses, never data."""

    id: str = Field(default_factory=new_id)
    source_id: str
    table: str
    column: str
    stats: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class EvidenceRecord(BaseModel):
    """One append-only piece of evidence.

    Records are never modified or deleted; ``stale`` is the single mutable
    flag (set when source fingerprints no longer match). A probe result
    must carry a verdict and be authored by a probe; confirmations and
    testimonials can only come from a human.
    """

    id: str = Field(default_factory=new_id)
    type: EvidenceType
    actor: Actor
    claim_id: str | None = None
    verdict: ProbeVerdict | None = None
    scope: Scope | None = None
    statement: str | None = None  # verbatim user statement for testimonials
    payload: dict[str, object] = Field(default_factory=dict)
    source_fingerprints: dict[str, object] = Field(default_factory=dict)
    stale: bool = False
    created_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _check_consistency(self) -> "EvidenceRecord":
        if self.type is EvidenceType.PROBE_RESULT:
            if self.verdict is None:
                raise ValueError("probe_result evidence requires a verdict")
            if self.actor is not Actor.PROBE:
                raise ValueError("probe_result evidence must be authored by a probe")
        else:
            if self.verdict is not None:
                raise ValueError("only probe_result evidence carries a verdict")
        if self.type in (EvidenceType.CONFIRMATION, EvidenceType.TESTIMONIAL):
            if self.actor is not Actor.HUMAN:
                raise ValueError(f"{self.type.value} evidence must come from a human")
        if self.type is EvidenceType.TESTIMONIAL and not self.statement:
            raise ValueError("testimonial evidence must carry the verbatim statement")
        return self


class Claim(BaseModel):
    """A statement about the data landscape with an epistemic status.

    Status is a derivation from the claim's evidence (``resolve_status``),
    persisted for readability — never hand-edited truth. ``depends_on``
    gates probe execution: prerequisites must be at least ``tested``.
    """

    id: str = Field(default_factory=new_id)
    statement: str
    created_by: Actor
    status: ClaimStatus = ClaimStatus.INFERRED
    evidence_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    scope: Scope | None = None
    open_assumptions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class ConceptClaim(Claim):
    """A claim about a business concept/definition (e.g. "revenue = external")."""

    term: str
    definition: str


class RoleBindingClaim(Claim):
    """A claim binding a domain role to concrete columns.

    Roles come from a flat, curated per-domain YAML (data, not code);
    invariant probes are formulated against roles, so the binding itself
    must earn its status like any other claim.
    """

    role: str
    binding: dict[str, str] = Field(default_factory=dict)  # e.g. {"table": ..., "column": ...}


class Probe(BaseModel):
    """A falsification attempt: an SQL template instance with a verdict function.

    ``claim_id`` is empty for invariant probes — those are bound to the
    landscape (via roles), not to a single claim.
    """

    id: str = Field(default_factory=new_id)
    template: str  # e.g. "anti_join", "validity_join", "reconciliation"
    claim_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    params: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class QuestionCard(BaseModel):
    """A business question with its epistemic bill of materials.

    ``claim_ids`` lists every claim the answer rests on — this is what
    makes an answer auditable and what staleness propagates into.
    """

    id: str = Field(default_factory=new_id)
    question: str
    sql: str | None = None
    result_ref: str | None = None
    claim_ids: list[str] = Field(default_factory=list)
    stale: bool = False
    created_at: datetime = Field(default_factory=_now)
