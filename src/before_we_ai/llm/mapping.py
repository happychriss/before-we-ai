"""Deterministic mapping from validated LLM answers to core objects.

Pure functions, no IO, no LLM: given a schema-valid answer and the
project's profile index, produce Claims and Checks via the M1 core — or a
list of error strings. The ``check_*`` functions double as the semantic
half of the retry loop: their errors are fed back to the model verbatim,
so retry feedback and final mapping can never disagree.

Everything created here carries ``Actor.AI`` and therefore starts (and,
without check/human evidence, stays) ``proposed`` — that is the M1 core's
law, not this module's choice.

Params are canonicalized (stripped strings, sorted string lists) before
they enter a ``Predicate``, so ``semantics.claim_key`` dedups paraphrases
of the same rule.
"""

from typing import TYPE_CHECKING

from before_we_ai.llm.schemas import (
    AnswerRequestDraft,
    DocumentFinding,
    Hypothesis,
    CheckPlanProposal,
    KnowledgeItemProposal,
    MappingProposal,
)
from before_we_ai.llm.vocabulary import (
    COLUMN_PARAMS,
    ROLE_TEMPLATES,
    PREDICATES,
    ROLE_BINDING_PREDICATE,
    VIEW_PARAMS,
    check_template_params,
    normalize_template_params,
)
from before_we_ai.core.enums import Actor, KnowledgeKind
from before_we_ai.core.objects import (
    AnswerRequest,
    Claim,
    ConceptClaim,
    KnowledgeItem,
    Predicate,
    CheckPlan,
    MappingClaim,
    Scope,
    Validity,
)
from before_we_ai.core.transitions import create_claim
from before_we_ai.store.repository import ProjectStore

if TYPE_CHECKING:  # domain_guide imports nothing from here; keep it that way
    from before_we_ai.llm.domain_guide import DomainGuide


class ProfileIndex:
    """The ground the answers must stand on: known views and columns."""

    def __init__(self, store: ProjectStore):
        self.columns: dict[str, str] = {}  # "view.column" -> source_id
        self.views: dict[str, str] = {}  # view -> source_id
        # A bare column name -> the source_ids of every view carrying it.
        # More than one means the name identifies nothing on its own.
        bare: dict[str, set[str]] = {}
        for p in store.profiles.values():
            self.columns[f"{p.table}.{p.column}"] = p.source_id
            self.views[p.table] = p.source_id
            bare.setdefault(p.column, set()).add(f"{p.table}.{p.column}")
        self.unique_columns: dict[str, str] = {
            column: self.columns[next(iter(qualified))]
            for column, qualified in bare.items() if len(qualified) == 1
        }
        self.scopes: dict[str, Scope | None] = {
            s.id: s.scope for s in store.sources.values()
        }

    def scope_of(self, source_ids: list[str]) -> Scope | None:
        """The one scope these sources agree on, or None.

        A binding that reaches across sources whose owners were declared
        differently belongs to no single entity — it is landscape-wide, and
        saying otherwise would put it in an election it does not compete in.
        Undeclared sources are landscape-wide too, so a project that never
        declares a scope behaves exactly as it did before scopes existed.
        """
        declared = {self.scopes.get(sid) for sid in source_ids}
        if len(declared) == 1:
            return declared.pop()
        return None

    def check_ref(self, value: str) -> str | None:
        """Error string if ``value`` looks like a catalog reference but isn't one."""
        if value in self.views or value in self.columns:
            return None
        prefix = value.split(".", 1)[0]
        if prefix in self.views:
            return f"unknown column reference {value!r}"
        return None  # not a reference — plain values pass through unchecked

    def source_ids(self, values: list[str]) -> list[str]:
        ids = {self.columns[v] for v in values if v in self.columns}
        ids |= {self.views[v] for v in values if v in self.views}
        # A bare column name grounds too, but only where the landscape
        # leaves no doubt which column it is. Some predicates (`decodes`)
        # declare no table param at all, so an unqualified name is the only
        # thing the model can write and rejecting it says "grounded in
        # nothing" about a column that plainly exists. Where two views share
        # the name it stays ungrounded — that is a real ambiguity, not a
        # majority to pick from.
        ids |= {self.unique_columns[v] for v in values
                if v in self.unique_columns}
        return sorted(ids)


def _canonical_params(params: dict) -> dict:
    canonical = {}
    for key, value in params.items():
        if isinstance(value, str):
            canonical[key] = value.strip()
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            canonical[key] = sorted(v.strip() for v in value)
        else:
            canonical[key] = value
    return canonical


def _string_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _string_values(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _string_values(v)]
    return []


# -- V1: hypotheses -------------------------------------------------------

def check_hypothesis(h: Hypothesis, index: ProfileIndex) -> list[str]:
    errors = []
    spec = PREDICATES[h.predicate]
    # kind is derived from the predicate, so it can no longer disagree with
    # it. What is left to check is that a concept says what it defines.
    if h.kind == "concept" and not (h.term or "").strip():
        errors.append(
            f"hypothesis {h.statement!r}: a concept hypothesis must name the "
            "term it defines"
        )
    keys = set(h.params)
    for missing in sorted(spec.required_params - keys):
        errors.append(
            f"hypothesis {h.statement!r}: predicate {h.predicate!r} "
            f"requires param {missing!r}"
        )
    for unknown in sorted(keys - spec.allowed_params):
        errors.append(
            f"hypothesis {h.statement!r}: param {unknown!r} is not allowed "
            f"for predicate {h.predicate!r}"
        )
    refs = list(h.columns) + _string_values(h.params)
    for ref in refs:
        problem = index.check_ref(ref)
        if problem:
            errors.append(f"hypothesis {h.statement!r}: {problem}")
    for column in h.columns:
        if column not in index.columns:
            errors.append(
                f"hypothesis {h.statement!r}: column {column!r} is not "
                "in the profiles"
            )
    if h.kind == "rule" and not index.source_ids(refs):
        errors.append(
            f"hypothesis {h.statement!r}: grounded in no known view or column"
        )
    return errors


def hypothesis_to_claim(h: Hypothesis, index: ProfileIndex) -> Claim:
    """Deterministic Hypothesis -> Claim/ConceptClaim; assumes checks passed."""
    predicate = Predicate(name=h.predicate, params=_canonical_params(h.params))
    scope = Scope(**h.scope.model_dump()) if h.scope else None
    validity = (
        Validity(valid_from=h.valid_from, valid_to=h.valid_to)
        if (h.valid_from or h.valid_to) else None
    )
    source_ids = index.source_ids(list(h.columns) + _string_values(h.params))
    if h.kind == "concept":
        return ConceptClaim(
            statement=h.statement,
            created_by=Actor.AI,
            predicate=predicate,
            scope=scope,
            validity=validity,
            source_ids=source_ids,
            term=h.term,
            # A model that names the term and then writes the definition as
            # its statement has said the same thing twice, not left something
            # out. Falling back costs nothing and rescues an otherwise
            # complete hypothesis.
            definition=(h.definition or h.statement).strip(),
        )
    return create_claim(
        h.statement,
        Actor.AI,
        predicate=predicate,
        scope=scope,
        validity=validity,
        source_ids=source_ids,
    )


# -- role bindings --------------------------------------------------------

def check_mapping_proposal(p: MappingProposal, role_names: list[str],
                        index: ProfileIndex) -> list[str]:
    errors = []
    if p.role not in role_names:
        errors.append(f"proposal binds unknown role {p.role!r}")
    if not p.binding:
        errors.append(
            f"proposal for role {p.role!r}: must bind at least one part"
        )
    for part, value in p.binding.items():
        if value not in index.views and value not in index.columns:
            errors.append(
                f"proposal for role {p.role!r}: binding part {part!r} "
                f"references unknown {value!r}"
            )
    return errors


def proposal_to_mapping_claim(p: MappingProposal, index: ProfileIndex) -> MappingClaim:
    binding = {k: v.strip() for k, v in sorted(p.binding.items())}
    rendered = ", ".join(f"{k}={v}" for k, v in binding.items())
    source_ids = index.source_ids(list(binding.values()))
    # The scope comes from the declared owner of the sources the binding
    # touches — never from the model, which has not been told about scopes
    # and must not be: which entity a table serves is a human's statement.
    # It joins the claim key, so DE's journal and US's journal are two
    # claims rather than one paraphrase of the other.
    return MappingClaim(
        statement=f"role '{p.role}' is played by {rendered}",
        created_by=Actor.AI,
        predicate=Predicate(
            name=ROLE_BINDING_PREDICATE,
            params={"role": p.role, "binding": binding},
        ),
        scope=index.scope_of(source_ids),
        source_ids=source_ids,
        role=p.role,
        binding=binding,
    )


# -- the request and what it requires -------------------------------------

def check_knowledge_item(item: KnowledgeItemProposal,
                         guide: "DomainGuide") -> list[str]:
    """Does this dependency name something the domain vocabulary has?

    Objects and fields must exist and sit where the item says they sit —
    a required-knowledge item that names nothing is a dependency the
    readiness evaluator could never resolve, so it never becomes silence
    later: it fails here, visibly, and the model is told why.

    Rules are the opposite case: they exist *because* the vocabulary has
    no entry for them. So a rule is rejected only when it names a
    vocabulary entry — that is a mis-kinded object or field, not a rule.
    """
    errors = []
    if not item.name.strip():
        errors.append("required-knowledge item: name is empty")
    if not item.why.strip():
        errors.append(
            f"required-knowledge item {item.name!r}: 'why' is empty — an "
            "item nobody can prune on may as well not be listed"
        )
    if item.kind == "field":
        if not item.of_object:
            errors.append(
                f"field {item.name!r}: must name the object it belongs to"
            )
        elif item.of_object not in guide.objects:
            errors.append(
                f"field {item.name!r}: {item.of_object!r} is no business "
                "object of the vocabulary"
            )
        elif item.name not in guide.objects[item.of_object].fields:
            owner = guide.owner_of(item.name)
            errors.append(
                f"field {item.name!r} is not a field of {item.of_object!r}"
                + (f" — it belongs to {owner!r}" if owner else
                   " and belongs to no object in the vocabulary")
            )
        return errors
    if item.of_object:
        errors.append(
            f"{item.kind} {item.name!r}: only a field belongs to an object"
        )
    if item.kind == "object" and item.name not in guide.objects:
        errors.append(
            f"object {item.name!r} is no business object of the vocabulary"
            + (f" — it is a field of {guide.owner_of(item.name)!r}"
               if guide.owner_of(item.name) else "")
        )
    if item.kind == "rule" and item.name in guide.entries:
        errors.append(
            f"rule {item.name!r} names a vocabulary entry — say "
            f"kind={'field' if guide.owner_of(item.name) else 'object'} "
            "instead; a rule is what the vocabulary does not contain"
        )
    return errors


def check_classification(draft: AnswerRequestDraft,
                         guide: "DomainGuide") -> str | None:
    """Whether the classification names an answer type this guide declares.

    Unlike a bad item, a bad classification is not skippable: it is the one
    claim the call exists to make, and everything the answer depends on
    follows from it. Naming a type that does not exist fails the whole call
    so the retry can name a real one — or honestly name none.
    """
    if draft.answer_type is None:
        return None
    if draft.answer_type in guide.answer_types:
        return None
    return (
        f"answer_type {draft.answer_type!r} is not declared by this domain "
        f"(it has {sorted(guide.answer_types) or 'none'}) — name one of "
        "those, or null if none covers the question"
    )


def draft_to_request(question: str, draft: AnswerRequestDraft) -> AnswerRequest:
    return AnswerRequest(
        question=question.strip(),
        requested_output=draft.requested_output.strip(),
        answer_type=draft.answer_type,
        scope=Scope(**draft.scope.model_dump()) if draft.scope else Scope(),
    )


def item_to_knowledge(item: KnowledgeItemProposal, scope: Scope) -> KnowledgeItem:
    """One drafted dependency, wearing the request's scope.

    The scope is inherited, never taken from the model: the request says
    what it is about, and every item it spawns is about the same thing.

    Except a rule, which takes none. Scope selects among candidates and a
    rule has none to select among; where a rule is valid is a property of
    the claim that states it, not of the dependency.
    """
    kind = KnowledgeKind(item.kind)
    return KnowledgeItem(
        kind=kind,
        name=item.name.strip(),
        of_object=item.of_object.strip() if item.of_object else None,
        why=item.why.strip(),
        scope=Scope() if kind is KnowledgeKind.RULE else scope,
    )


# -- V2: check bindings ---------------------------------------------------

def admissible_templates(claim: Claim) -> tuple[str, ...]:
    if isinstance(claim, MappingClaim):
        return ROLE_TEMPLATES
    if claim.predicate and claim.predicate.name in PREDICATES:
        return PREDICATES[claim.predicate.name].templates
    return ()


def check_binding(b: CheckPlanProposal, claims_by_id: dict[str, Claim],
                  index: ProfileIndex) -> list[str]:
    claim = claims_by_id.get(b.claim_id)
    if claim is None:
        return [f"binding references unknown claim {b.claim_id!r}"]
    if b.template is None:
        return ([] if b.no_template_reason
                else [f"claim {b.claim_id}: template=null requires no_template_reason"])
    errors = []
    if b.no_template_reason:
        errors.append(
            f"claim {b.claim_id}: no_template_reason is only valid with template=null"
        )
    allowed = admissible_templates(claim)
    if b.template not in allowed:
        errors.append(
            f"claim {b.claim_id}: template {b.template!r} cannot test "
            f"predicate {claim.predicate.name if claim.predicate else None!r} "
            f"(admissible: {sorted(allowed) or 'none'})"
        )
    params, _corrections = normalize_template_params(
        b.template, b.params, index.views)
    errors += [f"claim {b.claim_id}: {e}"
               for e in check_template_params(b.template, params)]
    for ref in _string_values(params):
        problem = index.check_ref(ref)
        if problem:
            errors.append(f"claim {b.claim_id}: {problem}")
    # referential integrity of the instantiation: views exist, columns
    # exist on the view they are used against
    for view_param in sorted(VIEW_PARAMS & set(params)):
        view = params[view_param]
        if not isinstance(view, str) or view not in index.views:
            errors.append(
                f"claim {b.claim_id}: {view_param}={view!r} must name a known view"
            )
    for column_param, view_param in COLUMN_PARAMS.get(b.template, ()):
        view = params.get(view_param)
        columns = params.get(column_param)
        if not isinstance(view, str) or view not in index.views or columns is None:
            continue
        for column in columns if isinstance(columns, list) else [columns]:
            if isinstance(column, str) and f"{view}.{column}" not in index.columns:
                errors.append(
                    f"claim {b.claim_id}: column {column!r} does not exist "
                    f"on view {view!r} (param {column_param!r})"
                )
    return errors


def proposal_to_check_plan(b: CheckPlanProposal, claim: Claim,
                           index: "ProfileIndex | None" = None
                           ) -> tuple[CheckPlan | None, list[dict]]:
    """Deterministic CheckPlanProposal -> CheckPlan; assumes checks passed.

    Returns the plan and every correction made on the way, so the caller
    can record them. A correction that only lived inside this function
    would be a silent rewrite of what the model asked for.
    """
    if b.template is None:
        return None, []
    params, corrections = normalize_template_params(
        b.template, b.params, index.views if index else ())
    plan = CheckPlan(
        template=b.template,
        claim_id=claim.id,
        roles=[claim.role] if isinstance(claim, MappingClaim) else [],
        params=_canonical_params(params),
    )
    return plan, corrections


# -- V3: document findings ------------------------------------------------

def check_document_finding(f: DocumentFinding, chunks: dict[str, object],
                           open_items: set[str]) -> list[str]:
    """Is this finding really in the document it says it is?

    The spec's quote validation, and the only check here that matters
    more than tidiness: the quote must appear **character for character**
    in the passage it cites. A model that remembers a policy correctly
    but rewords it slightly is still reporting something the document
    does not say, and an anchor pointing at words nobody wrote is worse
    than no anchor — it survives review by looking exactly like one that
    was checked.
    """
    errors = []
    chunk = chunks.get(f.chunk_id)
    if chunk is None:
        errors.append(
            f"passage {f.chunk_id!r} was not in this document's input; "
            "quote only from the passages supplied"
        )
    elif not f.quote.strip():
        errors.append(f"passage {f.chunk_id}: the quote is empty")
    elif f.quote not in getattr(chunk, "text", ""):
        errors.append(
            f"passage {f.chunk_id}: the quote does not appear verbatim in "
            f"that passage — quote the document's exact words: {f.quote!r}"
        )
    if not f.statement.strip():
        errors.append(f"passage {f.chunk_id}: 'statement' is empty")
    if f.reads_as == "definition":
        if not (f.term or "").strip():
            errors.append(
                f"passage {f.chunk_id}: a definition needs the term it defines"
            )
        if not (f.definition or "").strip():
            errors.append(
                f"passage {f.chunk_id}: a definition needs its definition"
            )
    elif f.term or f.definition:
        errors.append(
            f"passage {f.chunk_id}: term/definition belong to "
            "reads_as=definition, not to a figure"
        )
    if f.reads_as == "figure":
        errors += _check_stated_value(f)
    elif f.value:
        errors.append(
            f"passage {f.chunk_id}: 'value' belongs to reads_as=figure — a "
            "definition states a rule, not a number"
        )
    if f.answers is not None and f.answers not in open_items:
        errors.append(
            f"passage {f.chunk_id}: {f.answers!r} is not one of the open "
            "questions listed in the input"
        )
    return errors


def _check_stated_value(f: DocumentFinding) -> list[str]:
    """The figure the finding is about must be in the words it quotes.

    This is the whole reason the model is allowed to name it. Which number
    a sentence is *about* is a reading, not a computation — the engine used
    to guess and took the year out of "Prior year Q1 2023 revenue: EUR
    3,200,000" — but a reading can be checked, and an unchecked one would
    be a free hand to point an anchor at any number it liked.
    """
    from before_we_ai.documents.figures import read_figures

    value = (f.value or "").strip()
    if not value:
        return [f"passage {f.chunk_id}: a figure needs the number it is "
                "about, in 'value', exactly as the document writes it"]
    if value not in f.quote:
        return [f"passage {f.chunk_id}: {value!r} is not in the quote it is "
                "taken from — name the number as the document writes it"]
    # One number, not one *bare* number. A real run names "EUR 2,847,000",
    # which is how the document writes it and how a person would point at
    # it; demanding bare digits would be a formatting rule with nothing
    # epistemic behind it. What must hold is that the span names exactly
    # one figure — "from 1.2m to 3.4m" names two, and then we do not know
    # which one the finding is about, which is the whole reason this field
    # exists.
    figures = [fig for fig in read_figures(value) if fig.readings]
    if len(figures) != 1:
        return [f"passage {f.chunk_id}: {value!r} names "
                f"{'no number' if not figures else 'more than one number'} — "
                "'value' must point at exactly one figure"]
    return []


def finding_to_claim(f: DocumentFinding, source_id: str) -> Claim:
    """One finding becomes one proposed claim — never anything stronger.

    A figure becomes a plain claim stating what the document says, so the
    assertion is visible and anchorable rather than floating in a report.
    Its status is decided the way every claim's is: by evidence, of which
    a document anchor is the weakest kind there is.
    """
    if f.reads_as == "definition":
        term = (f.term or "").strip()
        return ConceptClaim(
            statement=f.statement.strip(),
            created_by=Actor.AI,
            predicate=Predicate(name="concept_definition",
                                params=_canonical_params({"term": term})),
            source_ids=[source_id],
            term=term,
            definition=(f.definition or "").strip(),
        )
    return create_claim(
        f.statement.strip(),
        Actor.AI,
        source_ids=[source_id],
    )
