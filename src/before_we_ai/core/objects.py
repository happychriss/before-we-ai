"""Pydantic models of the epistemic core.

All cross-references run over ULIDs, never nested objects — the store keeps
one YAML file per object and ``integrity`` checks that every reference
resolves. None of these models performs IO.
"""

import hashlib
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from before_we_ai.core.enums import (
    ActKind,
    Actor,
    ClaimStatus,
    EvidenceType,
    CheckVerdict,
    KnowledgeKind,
    Provenance,
)
from before_we_ai.core.ids import new_id


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

    ``description`` is the other declared thing: one sentence saying what
    this file *is*, in the words of whoever put it there. A filename and a
    row count do not tell a reader whether `erp.duckdb` is the production
    ledger or last year's export somebody kept, and that difference decides
    how much of the report they should believe. Never inferred and never
    written by a model: a plausible sentence about a file nobody vouched
    for is worse than none.
    """

    id: str = Field(default_factory=new_id)
    name: str
    kind: str  # e.g. "duckdb", "csv", "xlsx", "pdf", "text"
    location: str
    description: str = ""
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


class DocumentProfile(BaseModel):
    """Measured shape of one document — what it contains, never what it means.

    The document twin of ``DataProfile``, and it obeys the same law: a
    document that has been read produces a profile and **zero claims**.
    What the text asserts is V3's proposal to make, in the next stage,
    where nothing can promote itself.

    ``kinds`` counts chunks per origin (text / table / chart), which is the
    first thing a reader wants to know about a document the multi-anchor
    rule will later be strict about.
    """

    id: str = Field(default_factory=new_id)
    source_id: str
    document: str  # the source name, as declared in before-ai.yaml
    pages: int
    chunk_count: int
    char_count: int
    kinds: dict[str, int] = Field(default_factory=dict)
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


class Deferral(BaseModel):
    """*I looked at this and I cannot answer it.*

    Recorded rather than derived, because it is a statement about a person
    at a time and nothing in the data implies it. What it deliberately does
    **not** do is change the verdict: a waiver says "this does not matter
    here" and removes an item from what blocks the answer; a deferral says
    "I do not know", which is exactly the state the answer was already in.
    All it moves is the work list — a question somebody has already stared
    at should stop sitting at the top of it, and should say who stared.
    """

    by: Actor
    note: str = ""  # anything the reader can say about why not
    at: datetime = Field(default_factory=_now)


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
    # How big the problem is, in the words of the run that found it: "1
    # exception in 24 rows". Deliberately NOT part of ``question`` — the
    # wording is the dedup key, so a count inside it would mint a fresh
    # card every time the number moved, and the same decision would face
    # the reader again and again wearing a new id. Kept beside the
    # question instead, where a list can show it and a re-run can update
    # it without splitting the card.
    #
    # It is here because a question without a magnitude cannot be triaged:
    # "the two do not agree" is one exception in twenty-four or forty per
    # cent of the rows, and those are different decisions.
    finding: str = ""
    scope: Scope | None = None
    claim_ids: list[str] = Field(default_factory=list)
    stale: bool = False
    #: Set when a human read this card and could not answer it. Mutable
    #: like the rest of a card — it is a note about the reader, not
    #: evidence about the data, and it is undone by answering.
    deferred: Deferral | None = None
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

    It carries **no answer half**. ``sql``/``result_ref`` came here from the
    pre-M6 question card, where they did not belong either — but nothing
    sets or reads them, and the milestone that would produce SQL is not
    planned. They are gone; whatever generates an answer will bring its own
    shape. (Third instance of one defect: a field nothing populates is a
    field that gets reasoned about as if it meant something.)

    **Authorship is fixed by the shape, so no field records it.**
    ``question`` is the human's, verbatim; ``requested_output`` and
    ``scope`` are the request contract's structuring of it. A ``created_by`` here would be
    ``human`` on every record ever written — and it would be *wrong* about
    two of the three fields, which is worse than absent. Contrast
    ``Claim.created_by`` and ``KnowledgeLink.linked_by``: those genuinely
    vary, and the code branches on them.
    """

    id: str = Field(default_factory=new_id)
    question: str  # verbatim, as the human asked it
    requested_output: str  # the contract's one-line statement of the output
    # Which answer type of the domain guide this question was classified to,
    # or None when none matched. A proposal like requested_output, and the
    # smallest claim the contract can make: everything the answer depends on
    # follows from it deterministically, so this one line is what a human
    # confirms instead of a list they must read item by item.
    answer_type: str | None = None
    scope: Scope = Field(default_factory=Scope)
    #: Which wording this is. A question gets edited — a typo, a narrower
    #: period, a different thing entirely — and the request keeps its
    #: identity through that: the acts taken on its list are still about
    #: this question, and throwing them away over a corrected typo would
    #: destroy a human's work. What does not survive is the confirmation
    #: (see ``fingerprint``).
    revision: int = 1
    #: The wordings this one replaced, oldest first. Kept because "Revision
    #: 3" is only useful next to what revisions 1 and 2 said.
    earlier: list["EarlierWording"] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)

    def fingerprint(self) -> str:
        """What a human saw when they confirmed this request's list.

        Everything a confirmation is a statement *about*: the question as
        asked, the contract's restatement of it, the family it was
        classified to, and the scope it was asked over. Change any of them
        and the sentence "this list is complete" is about something else,
        so the confirmation lapses exactly as it does when the guide moves.

        Deliberately the single mechanism: the act also stores which
        ``answer_type`` it confirmed, and comparing that separately would
        be the same decision in two places, ready to disagree.
        """
        payload = "\n".join([
            self.question.strip(),
            self.requested_output.strip(),
            self.answer_type or "",
            self.scope.label(),
        ])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def revised(self, **fields) -> "AnswerRequest":
        """This request re-asked: same identity, next revision.

        The previous wording moves into ``earlier`` rather than being
        overwritten — a reader comparing what they confirmed against what
        is in front of them now needs both.
        """
        previous = EarlierWording(
            question=self.question,
            requested_output=self.requested_output,
            answer_type=self.answer_type,
            revision=self.revision,
        )
        return self.model_copy(update={
            **fields,
            "revision": self.revision + 1,
            "earlier": [*self.earlier, previous],
        })


class EarlierWording(BaseModel):
    """One superseded wording of a request, kept beside the current one."""

    question: str
    requested_output: str
    answer_type: str | None = None
    revision: int = 1
    replaced_at: datetime = Field(default_factory=_now)


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
    guide, one of that object's fields, or a rule.

    ``scope`` is inherited from the request, and only objects and fields
    carry one. For those it is a **selector**: it decides *which* table or
    column plays the role, so DE's ledger and US's compete in separate
    elections. A rule has nothing to select among — there is no "DE's copy"
    of an accounting policy — so its scope would be meaningless here. Where
    a rule's validity genuinely lives is on the **claim** that states it
    (``Claim.scope`` and ``Claim.validity``), which can also say *from when*
    — richer than this item could express. The evaluator asks whether that
    claim's scope reaches the scope the question was asked in.

    ``why`` states the dependency in business words. An item without a
    reason cannot be pruned by a human with any confidence, and pruning is
    exactly what the draft exists for.

    ``satisfied_by`` is for **rules only**. An object or a field resolves
    through the domain guide and its scoped election — that is what the
    guide is for, and a link that could bypass an election would be a way
    around it. A rule is precisely the thing the guide has no entry for, so
    nothing but an explicit link can connect it to the claim that states
    it.

    ``waived_because`` is how a human prunes the list — the pruning the
    list exists to allow. An item nobody needs would otherwise block an
    answer forever. Waived, **not deleted**: a deleted dependency is
    invisible, and "we decided this does not matter, here is why" is
    exactly the kind of decision this product refuses to lose. A waived
    item still appears in the map, struck through, carrying its reason.

    It is set by the overlay, not by whoever built the item: the waiver
    itself is a stored ``KnowledgeAct``, because the list is derived and a
    derived thing cannot remember a decision.
    """

    kind: KnowledgeKind
    name: str
    of_object: str | None = None  # set for fields, empty otherwise
    why: str = ""
    # Where the item came from — see Provenance. Defaults to `proposed`
    # because that is what an item is when nobody says otherwise.
    provenance: Provenance = Provenance.PROPOSED
    scope: Scope = Field(default_factory=Scope)
    satisfied_by: list[KnowledgeLink] = Field(default_factory=list)
    # None = required. A reason is the only way to stop requiring it — there
    # is no bare `waived: bool`, because a waiver without a reason is the
    # silence this product forbids.
    waived_because: str | None = None

    @property
    def waived(self) -> bool:
        return self.waived_because is not None

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
        if self.kind is KnowledgeKind.RULE and self.scope.is_explicit():
            raise ValueError(
                f"rule '{self.name}': a rule item carries no scope. A scope "
                "selects among candidates and a rule has none; the validity "
                "of a rule lives on the claim that states it (Claim.scope / "
                "Claim.validity)"
            )
        return self

    def ref(self) -> str:
        """The item's address in the domain guide's terms."""
        return f"{self.of_object}.{self.name}" if self.of_object else self.name


class RequiredKnowledge(BaseModel):
    """The model's freely drafted items for one request — the fallback list.

    **This is no longer the dependency list.** That list is derived on every
    read (``readiness.assemble``): an answer type expands deterministically
    into ``contract`` items, and only what a human *did* to them is stored
    (``KnowledgeAct``). A stored list would go stale the moment the guide it
    was drafted against changed — and a stale dependency list is exactly the
    silent under-listing this design exists to prevent.

    What remains here is what cannot be derived: the items the contract
    could **not** supply, drafted by the model for this one question,
    because no answer type matched or because the question carries a delta
    the type does not cover. They are ``proposed`` items, they are labelled
    as such wherever they appear, and while a request rests on them its
    verdict is capped.
    """

    id: str = Field(default_factory=new_id)
    request_id: str
    items: list[KnowledgeItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_now)


class KnowledgeAct(BaseModel):
    """One decision taken about a dependency list, stored append-only.

    The list is derived; these are the only records of it that persist. An
    act is never edited — a waiver is undone by a later ``require_again``,
    so the pair stays readable as the history it is.

    Two fingerprints make the derivation safe to trust, and they cover the
    two halves a confirmation is a statement about: ``guide_fingerprint``
    is the vocabulary and the answer type the list was expanded from,
    ``request_fingerprint`` the question that was asked. Either can move
    under a human's signature — the guide gains an answer type, or somebody
    edits the question — and in both cases what was reviewed is not what is
    on the page now.

    Only a ``confirm`` lapses. A confirmation says *"this list is
    complete"*, which stops being true the moment the list changes. Every
    other act is about one item — "this does not matter here", "this claim
    speaks to it" — and a change elsewhere leaves that exactly as true as
    it was. Lapsing them too would destroy a human's work to no one's
    benefit; the confirmation lapsing is what brings them back in front of
    a reader anyway.
    """

    id: str = Field(default_factory=new_id)
    request_id: str
    kind: ActKind
    actor: Actor
    guide_fingerprint: str = ""
    request_fingerprint: str = ""
    ref: str | None = None  # which item — waive / require_again / link
    reason: str = ""  # waive: why it does not matter here
    claim_id: str | None = None  # link
    note: str = ""  # link: why this claim answers this dependency
    item: KnowledgeItem | None = None  # add
    answer_type: str | None = None  # confirm: what was confirmed
    created_at: datetime = Field(default_factory=_now)

    @model_validator(mode="after")
    def _check_shape(self) -> "KnowledgeAct":
        if self.kind in (ActKind.WAIVE, ActKind.REQUIRE_AGAIN, ActKind.LINK):
            if not self.ref:
                raise ValueError(f"a {self.kind.value} act must name the item "
                                 "it acts on")
        if self.kind is ActKind.WAIVE and not self.reason.strip():
            raise ValueError(
                "a waiver must carry a reason — 'we decided this does not "
                "matter' without the why is the silence this product forbids"
            )
        if self.kind is ActKind.LINK and not self.claim_id:
            raise ValueError("a link act must name the claim it routes to")
        if self.kind is ActKind.ADD and self.item is None:
            raise ValueError("an add act must carry the item it adds")
        if self.kind is ActKind.CONFIRM and self.ref:
            raise ValueError(
                "a confirmation is about the whole list, not one item — that "
                "is the point of it"
            )
        return self
