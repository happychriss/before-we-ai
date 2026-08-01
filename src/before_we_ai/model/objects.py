"""Pydantic models of the epistemic core.

All cross-references run over ULIDs, never nested objects — the store keeps
one YAML file per object and ``integrity`` checks that every reference
resolves. None of these models performs IO.
"""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from before_we_ai.model.enums import (
    Actor,
    ClaimStatus,
    EvidenceType,
    CheckVerdict,
    KnowledgeKind,
)
from before_we_ai.model.ids import new_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Scope(BaseModel):
    """Explicit validity scope of a claim or confirmation.

    The mirror-loop requires the scope to be spelled out (entity, period,
    segment) before a testimonial claim may become business-confirmed —
    "gilt für: alle Gesellschaften?" must have been answered, not assumed.

    Frozen, and therefore hashable: a scope is a value, not a thing you
    edit. Elections group candidates by it, so two claims about DE must be
    the same key — and a scope that could be changed underneath a grouping
    would move a claim into another entity's election.
    """

    model_config = ConfigDict(frozen=True)

    entity: str | None = None
    period: str | None = None
    segment: str | None = None

    def is_explicit(self) -> bool:
        return any(v is not None for v in (self.entity, self.period, self.segment))

    def label(self) -> str:
        """The scope in business words, or "" when it is not explicit.

        Used wherever two scopes must be told apart by a reader — a question
        card, a readiness item — so "the same question, twice" reads as the
        two different questions it is.
        """
        parts = [
            f"{name} {value}"
            for name, value in (
                ("entity", self.entity),
                ("period", self.period),
                ("segment", self.segment),
            )
            if value is not None
        ]
        return ", ".join(parts)


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
    """A connected data source (database, file drop, document).

    ``scope`` is a human declaration of whose books these are, carried over
    from ``before-ai.yaml``. It is what lets a role be elected per entity
    instead of once for the whole landscape — and it is declared rather
    than inferred, because nothing in a file says which entity owns it.
    """

    id: str = Field(default_factory=new_id)
    name: str
    kind: str  # e.g. "duckdb", "csv", "xlsx", "pdf", "text"
    location: str
    scope: Scope | None = None
    fingerprint: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class DataProfile(BaseModel):
    """Measured statistics of one column — input for hypotheses, never data."""

    id: str = Field(default_factory=new_id)
    source_id: str
    table: str
    column: str
    stats: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


# Row-level observations are evidence *content*, strictly bounded: a check
# reports the aggregate plus a hand-picked, representative sample of
# counterexamples. Anything larger belongs in cache/ (via result_ref),
# never in the truth files.
MAX_EXCEPTION_SAMPLES = 20


class EvidenceRecord(BaseModel):
    """One append-only piece of evidence.

    Records are never modified or deleted; ``stale`` is the single mutable
    flag (set when source fingerprints no longer match). A check result
    must carry a verdict and be authored by a check; confirmations and
    testimonials can only come from a human.

    A check over N rows produces exactly one record: ``population`` rows
    checked, ``exception_count`` violations, at most
    ``MAX_EXCEPTION_SAMPLES`` representative counterexamples in
    ``exception_samples``, and optionally a ``result_ref`` pointing at the
    full exception set in the disposable cache.
    """

    id: str = Field(default_factory=new_id)
    type: EvidenceType
    actor: Actor
    claim_id: str | None = None
    check_plan_id: str | None = None  # the persisted CheckPlan whose run produced this record
    verdict: CheckVerdict | None = None
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
        if self.type is EvidenceType.CHECK_RESULT:
            if self.verdict is None:
                raise ValueError("check_result evidence requires a verdict")
            if self.actor is not Actor.CHECK:
                raise ValueError("check_result evidence must be authored by a check")
        else:
            if self.verdict is not None:
                raise ValueError("only check_result evidence carries a verdict")
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
    with one check record, not 100,000 claims.

    Status is a derivation from the claim's evidence (``resolve_status``),
    persisted for readability — never hand-edited truth. ``depends_on``
    gates check execution: prerequisites must be at least ``test-supported``.
    Identity for deduplication is (predicate, scope, validity, sources) —
    see ``semantics.claim_key``.
    """

    id: str = Field(default_factory=new_id)
    statement: str
    created_by: Actor
    status: ClaimStatus = ClaimStatus.PROPOSED
    predicate: Predicate | None = None
    scope: Scope | None = None
    validity: Validity | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    # provenance when escalated from an exception: the parent claim and the
    # evidence record whose exceptions surfaced it — provenance only, NOT
    # status-bearing evidence (the parent's check verdict says nothing
    # about the child rule)
    derived_from: str | None = None
    derived_from_evidence: str | None = None
    open_assumptions: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class ConceptClaim(Claim):
    """A claim about a business concept/definition (e.g. "revenue = external")."""

    term: str
    definition: str


class MappingClaim(Claim):
    """A claim binding a domain role to concrete columns.

    Roles come from a flat, curated per-domain YAML (data, not code);
    invariant checks are formulated against roles, so the binding itself
    must earn its status like any other claim.
    """

    role: str
    binding: dict[str, str] = Field(default_factory=dict)  # e.g. {"table": ..., "column": ...}


class CheckPlan(BaseModel):
    """A falsification attempt: an SQL template instance with a verdict function.

    ``claim_id`` is empty for invariant checks — those are bound to the
    landscape (via roles), not to a single claim.
    """

    id: str = Field(default_factory=new_id)
    template: str  # e.g. "anti_join", "validity_join", "reconciliation"
    claim_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    params: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


class ClarificationQuestion(BaseModel):
    """A question drafted to resolve one specific uncertainty.

    ``claim_ids`` lists every claim the answer would touch — this is what
    makes an answer auditable and what staleness propagates into.

    ``scope`` is what makes the card unique: the same wording asked about
    two entities is two questions, and deduplication keys on
    ``dedup_key()`` — text *and* scope — so the second one can never
    collapse into the first. A card with no scope is landscape-wide.
    """

    id: str = Field(default_factory=new_id)
    question: str
    scope: Scope | None = None
    claim_ids: list[str] = Field(default_factory=list)
    stale: bool = False
    created_at: datetime = Field(default_factory=_now)

    def dedup_key(self) -> tuple[str, str]:
        """Identity for deduplication: the wording within its scope."""
        return (self.question, self.scope.label() if self.scope else "")


class AnswerRequest(BaseModel):
    """The structured form of one business question.

    The human asks a business question; this is its software
    representation — what output is wanted, over which scope. It is the top
    of the machine: the request *bounds* discovery, so what the answer
    depends on must be known and nothing else has to be. That is what keeps
    domain knowledge tied to a use case instead of an enterprise ontology.

    ``sql``/``result_ref`` are the answer half, migrated here from the
    pre-M6 question card: the query that would produce the requested output
    and a disposable ``cache/`` path to its result. Neither is truth — the
    ReadinessMap decides whether the answer may be given at all.

    **Authorship is fixed by the shape, so no field records it.**
    ``question`` is the human's, verbatim; ``requested_output`` and
    ``scope`` are V4's structuring of it. A ``created_by`` here would be
    ``human`` on every record ever written — and it would be *wrong* about
    two of the three fields, which is worse than absent. Contrast
    ``Claim.created_by`` and ``KnowledgeLink.linked_by``: those genuinely
    vary, and the code branches on them.
    """

    id: str = Field(default_factory=new_id)
    question: str  # verbatim, as the human asked it
    requested_output: str  # V4's one-line statement of what the answer delivers
    scope: Scope = Field(default_factory=Scope)
    sql: str | None = None
    result_ref: str | None = None
    created_at: datetime = Field(default_factory=_now)


class KnowledgeLink(BaseModel):
    """A pointer from a required rule to the claim that states it.

    A link **routes, it does not vouch**: it says "this claim is the one
    that speaks to this dependency", and nothing more. Whether the
    dependency is satisfied still comes from the claim's own status, so a
    link authored by the AI is structurally as harmless as an AI-authored
    claim — it cannot promote anything. What it does carry is
    responsibility, hence ``linked_by``: a wrong link points a verdict at
    an unrelated claim, and the reader must be able to see whose mistake
    that was.
    """

    claim_id: str
    linked_by: Actor
    note: str = ""  # why this claim answers this dependency


class KnowledgeItem(BaseModel):
    """One thing the requested answer depends on.

    ``kind`` says what it points at — a business object of the domain
    guide, one of that object's fields, or a rule. Every item carries its
    request's scope: that is what makes elections and questions scoped
    rather than landscape-wide, and it is inherited, never invented here.

    ``why`` states the dependency in business words. An item without a
    reason cannot be pruned by a human with any confidence, and pruning is
    exactly what the draft exists for.

    ``satisfied_by`` is for **rules only**. An object or a field resolves
    through the domain guide and its scoped election — that is what the
    guide is for, and a link that could bypass an election would be a way
    around it. A rule is precisely the thing the guide has no entry for, so
    nothing but an explicit link can connect it to the claim that states
    it.
    """

    kind: KnowledgeKind
    name: str
    of_object: str | None = None  # set for fields, empty otherwise
    why: str = ""
    scope: Scope = Field(default_factory=Scope)
    satisfied_by: list[KnowledgeLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_shape(self) -> "KnowledgeItem":
        if self.kind is KnowledgeKind.FIELD and not self.of_object:
            raise ValueError("a field item must name the object it belongs to")
        if self.kind is not KnowledgeKind.FIELD and self.of_object:
            raise ValueError(
                f"only a field belongs to an object — {self.kind.value} "
                f"'{self.name}' must not carry one"
            )
        if self.satisfied_by and self.kind is not KnowledgeKind.RULE:
            raise ValueError(
                f"{self.kind.value} '{self.name}': only a rule is satisfied by "
                "a linked claim — an object or field resolves through the "
                "domain guide's scoped election, and a link would bypass it"
            )
        return self

    def ref(self) -> str:
        """The item's address in the domain guide's terms."""
        return f"{self.of_object}.{self.name}" if self.of_object else self.name


class RequiredKnowledge(BaseModel):
    """What must be known before the requested answer can be produced.

    Derived from the AnswerRequest and drafted by the AI — then pruned by
    the human, as everywhere: the model proposes. It is persisted because
    that pruning is a human decision, not something re-derivable from the
    request.

    Drafted by V4 always, so — as on ``AnswerRequest`` — that is a fact
    about the shape and not a field. What does vary, and therefore is a
    field, is who linked each rule to the claim answering it
    (``KnowledgeLink.linked_by``).
    """

    id: str = Field(default_factory=new_id)
    request_id: str
    items: list[KnowledgeItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)
