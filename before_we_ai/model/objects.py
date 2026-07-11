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


class Validity(BaseModel):
    """Temporal validity of a rule (valid_from/valid_to, ISO dates or periods).

    A rule that changes over time (a hierarchy re-parenting, a cost-center
    remap) is two claims with adjoining validities — not one claim that is
    sometimes wrong.
    """

    valid_from: str | None = None
    valid_to: str | None = None


class Predicate(BaseModel):
    """The parameterised, machine-comparable form of a semantic rule.

    A claim states a *rule* ("every AR item references a GL posting",
    "account range X is revenue"), never a fact about one row. ``name``
    identifies the rule form, ``params`` its parameterisation — together
    with scope and validity they give the claim its identity for
    deduplication.
    """

    name: str
    params: dict[str, object] = Field(default_factory=dict)


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


# Row-level observations are evidence *content*, strictly bounded: a probe
# reports the aggregate plus a hand-picked, representative sample of
# counterexamples. Anything larger belongs in cache/ (via result_ref),
# never in the truth files.
MAX_EXCEPTION_SAMPLES = 20


class EvidenceRecord(BaseModel):
    """One append-only piece of evidence.

    Records are never modified or deleted; ``stale`` is the single mutable
    flag (set when source fingerprints no longer match). A probe result
    must carry a verdict and be authored by a probe; confirmations and
    testimonials can only come from a human.

    A probe over N rows produces exactly one record: ``population`` rows
    checked, ``exception_count`` violations, at most
    ``MAX_EXCEPTION_SAMPLES`` representative counterexamples in
    ``exception_samples``, and optionally a ``result_ref`` pointing at the
    full exception set in the disposable cache.
    """

    id: str = Field(default_factory=new_id)
    type: EvidenceType
    actor: Actor
    claim_id: str | None = None
    verdict: ProbeVerdict | None = None
    scope: Scope | None = None
    statement: str | None = None  # verbatim user statement for testimonials
    population: int | None = None
    exception_count: int | None = None
    exception_samples: list[dict[str, object]] = Field(default_factory=list)
    result_ref: str | None = None  # cache/ path to the full result — disposable
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
        if len(self.exception_samples) > MAX_EXCEPTION_SAMPLES:
            raise ValueError(
                f"at most {MAX_EXCEPTION_SAMPLES} representative exception samples "
                "per record — the full set belongs in cache/ (result_ref)"
            )
        if (
            self.population is not None
            and self.exception_count is not None
            and self.exception_count > self.population
        ):
            raise ValueError("exception_count cannot exceed population")
        return self

    def exception_rate(self) -> float | None:
        if self.population in (None, 0) or self.exception_count is None:
            return None
        return self.exception_count / self.population


class Claim(BaseModel):
    """A reusable semantic rule about the data landscape, with a status.

    A claim describes a *rule or relationship* over a scope — never a fact
    about an individual row. Row-level material enters only as bounded
    evidence content; a dataset of 100,000 rows therefore yields one claim
    with one probe record, not 100,000 claims.

    Status is a derivation from the claim's evidence (``resolve_status``),
    persisted for readability — never hand-edited truth. ``depends_on``
    gates probe execution: prerequisites must be at least ``tested``.
    Identity for deduplication is (predicate, scope, validity, sources) —
    see ``semantics.claim_key``.
    """

    id: str = Field(default_factory=new_id)
    statement: str
    created_by: Actor
    status: ClaimStatus = ClaimStatus.INFERRED
    predicate: Predicate | None = None
    scope: Scope | None = None
    validity: Validity | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    # provenance when escalated from an exception: the parent claim and the
    # evidence record whose exceptions surfaced it — provenance only, NOT
    # status-bearing evidence (the parent's probe verdict says nothing
    # about the child rule)
    derived_from: str | None = None
    derived_from_evidence: str | None = None
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
