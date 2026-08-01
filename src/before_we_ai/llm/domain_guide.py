"""The domain guide: business objects with fields in, honest resolution out.

The guide is data, never code — it names the business objects of a domain
(journal, subledger, intercompany) with one definition each, and the fields
those objects carry (the posting amount, the document reference, the
account). The product stays domain-agnostic because the file is supplied per
project (``llm.domain_guide_file`` in before-ai.yaml). Invariant checks are
formulated against the guide's names; the binding of a name to concrete
columns is itself a MappingClaim that must earn its status.

**Objects and fields are not the same kind of thing, and the schema says so.**
An object is what a domain law judges — a law's subject. A field is carried
*inside* its object's law or decided by a human, and **a field can never
declare a law**: the guide cannot even express it. That is by construction,
not by lint: a field owning a settlement path is what once made the finance
guide declare `amount_local: decided_by: balance`, which drew a question
about knowledge that was never missing.

Every entry declares how it can ever be settled (``decided_by``):

- an object: the name of the domain law that can elect it (``balance``, ...)
  — the checks decide; or ``clarification`` — the candidates go to the humans
  as a drafted question;
- a field: ``slot`` — elected inside its object's law, naming with ``fills``
  which slot of that law it is (the law then settles it with the column the
  passing run actually consumed); or ``clarification`` — no arithmetic can
  decide what a column *means*.

The load-time lint rejects a guide that cannot hold together: silence must be
a declared property, never an accident, and a slot must be a slot a law
really has. (An object can look decidable and still be beyond any check — a
journal balances per period AND per document AND per year, so a passing law
never proves what its *grouping* column means. Such params are deliberately
not slots; see ``CheckDefinition.slots``.)

``resolve_mappings`` is the honesty valve, completing the rule *every object
and every clarification-decided field ends in a check verdict or a
clarification question — never in nothing*:

- law-decided object, candidates checked, none stands ≥ test-supported → clarification question;
- law-decided object whose law could never be bound to any candidate
  (all carry V2's no-check declarations) → clarification question — knowledge is
  missing to even apply the law;
- clarification-decided entry with candidates → clarification question listing them;
- any such entry for which the search proposed no candidate at all
  → clarification question;
- slot field whose object settled: answered by the column the passing run
  consumed — and if that run consumed none, a clarification question, because
  a slot may ride a law but may not disappear into it.

The losing candidates keep their derived statuses; nothing is silently
discarded.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from before_we_ai.core.enums import ClaimStatus, CheckVerdict, EvidenceType
from before_we_ai.core.objects import ClarificationQuestion, MappingClaim, Scope
from before_we_ai.checks.library import REGISTRY
from before_we_ai.store.repository import ProjectStore

_SETTLED = (ClaimStatus.TEST_SUPPORTED, ClaimStatus.BUSINESS_CONFIRMED)

DECIDED_BY_CLARIFICATION = "clarification"
DECIDED_BY_SLOT = "slot"

# Reserved for the guide-drafting contract (post-M5): AI may draft generic
# entries, but an organisational binding enters only as a human-answered
# clarification. Curated guides are human-confirmed by definition.
PROVENANCE_HUMAN = "confirmed-by-human"
PROVENANCE_AI = "drafted-by-ai"

# The question a human is asked, in the register a business reader thinks in:
# the ask first, then the guide's own definition of what is being asked about,
# then what the machine already tried. The candidates are NOT written into the
# text — the card links them (`claim_ids`), and a list of bindings flattened
# into prose is the least readable form of data we have.
QUESTION_LOST = (
    "Which source is the authoritative '{role}'? {definition} Every proposed "
    "candidate was put to the {law} law, and every one of them failed it."
)
QUESTION_UNBOUND = (
    "What is missing before the '{role}' can be tested? {definition} No "
    "proposed candidate could be put to the {law} law at all, so nothing "
    "about it has been tested."
)
QUESTION_CHOOSE = (
    "Which of the proposed candidates is the '{role}'? {definition} No check "
    "can settle this — what the data means is a business fact, not an "
    "arithmetic one."
)
QUESTION_EMPTY = (
    "Does the '{role}' exist in this data at all? {definition} Nothing in the "
    "scanned sources was proposed as a candidate for it."
)
QUESTION_SLOT_UNCONSUMED = (
    "Which column is the '{role}'? {definition} It should have been settled "
    "as the '{slot}' of the {law} law of '{object}', but the run that passed "
    "consumed no column for it."
)


class FieldSpec(BaseModel):
    """One field of a business object: definition and settlement path.

    ``decided_by`` is ``slot`` or ``clarification`` — never a law. A field
    that could declare a law would be an object.
    """

    model_config = ConfigDict(extra="forbid")

    definition: str
    decided_by: str  # "slot" or "clarification"
    fills: str | None = None  # slot only: which slot param of its object's law
    provenance: str = PROVENANCE_HUMAN


class ObjectSpec(BaseModel):
    """One business object: definition, settlement path, and its fields."""

    model_config = ConfigDict(extra="forbid")

    definition: str
    decided_by: str  # a domain-law template name, or "clarification"
    fields: dict[str, FieldSpec] = {}
    provenance: str = PROVENANCE_HUMAN


class DomainGuide(BaseModel):
    """One domain's business objects with their fields, linted on load."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    objects: dict[str, ObjectSpec]

    @property
    def entries(self) -> dict[str, ObjectSpec | FieldSpec]:
        """Every guide entry by name, objects each followed by their fields.

        This flat view is what the model is shown (name + definition only)
        and what MappingClaim.role refers to — the hierarchy is consumed by
        the lint, the resolution and the elections, never on the wire.
        """
        flat: dict[str, ObjectSpec | FieldSpec] = {}
        for name, spec in self.objects.items():
            flat[name] = spec
            flat.update(spec.fields)
        return flat

    @property
    def names(self) -> list[str]:
        return list(self.entries)

    def owner_of(self, field: str) -> str | None:
        """The object a field belongs to; None for an object itself."""
        for name, spec in self.objects.items():
            if field in spec.fields:
                return name
        return None

    @model_validator(mode="after")
    def _lint(self) -> "DomainGuide":
        """The coherence lint: no entry silent, no law misassigned, no slot
        that its object's law does not have."""
        laws = {name for name, spec in REGISTRY.items()
                if spec.domain == self.domain}
        errors = []
        seen: set[str] = set()
        for name, spec in self.objects.items():
            seen.add(name)
            decider = spec.decided_by
            law = REGISTRY.get(decider)
            if decider == DECIDED_BY_SLOT:
                errors.append(
                    f"object {name!r}: decided_by 'slot' — an object is what a "
                    "law judges, never what it carries; only fields are slots"
                )
            elif decider == DECIDED_BY_CLARIFICATION:
                pass
            elif law is None:
                errors.append(
                    f"object {name!r}: decided_by {decider!r} is no check "
                    f"template and not {DECIDED_BY_CLARIFICATION!r}"
                )
            elif decider not in laws:
                errors.append(
                    f"object {name!r}: decided_by {decider!r} is not a "
                    f"domain law of {self.domain!r} — a generic template "
                    "cannot elect an object"
                )
            filled: dict[str, str] = {}
            for field_name, field in spec.fields.items():
                if field_name in seen:
                    errors.append(
                        f"field {field_name!r} of {name!r}: the name is already "
                        "taken in this guide — entry names are one namespace"
                    )
                seen.add(field_name)
                errors += self._lint_field(name, spec, field_name, field,
                                           law if decider in laws else None,
                                           filled)
        if errors:
            raise ValueError("domain guide lint: " + "; ".join(errors))
        return self

    def _lint_field(self, object_name, object_spec, field_name, field, law,
                    filled) -> list[str]:
        where = f"field {field_name!r} of {object_name!r}"
        if field.decided_by == DECIDED_BY_CLARIFICATION:
            if field.fills is not None:
                return [f"{where}: 'fills' is meaningless without "
                        f"decided_by {DECIDED_BY_SLOT!r}"]
            return []
        if field.decided_by != DECIDED_BY_SLOT:
            # the structural rule of the whole shape, stated as a load error
            return [f"{where}: decided_by {field.decided_by!r} — a field can "
                    f"never declare a law; it is {DECIDED_BY_SLOT!r} or "
                    f"{DECIDED_BY_CLARIFICATION!r}. Only its object settles "
                    "through a law"]
        if law is None:
            return [f"{where}: a slot needs a law to ride, but {object_name!r} "
                    "is not decided by one"]
        if field.fills is None:
            return [f"{where}: a slot must name the law slot it fills "
                    f"(fills: one of {sorted(law.slots) or 'none'})"]
        if field.fills not in law.slots:
            return [f"{where}: fills {field.fills!r} is no slot of the "
                    f"{object_spec.decided_by!r} law "
                    f"(it has {sorted(law.slots) or 'none'})"]
        if field.fills in filled:
            return [f"{where}: slot {field.fills!r} is already filled by "
                    f"{filled[field.fills]!r} — one slot, one field"]
        filled[field.fills] = field_name
        return []


def load_domain_guide(path: str | Path) -> DomainGuide:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DomainGuide.model_validate(data)


def _has_no_check_declaration(store: ProjectStore,
                              claim: MappingClaim) -> bool:
    return any(
        e.type is EvidenceType.DECLARATION and "decision" in e.payload
        for e in store.evidence_for(claim)
    )


def _candidates(store: ProjectStore, role: str,
                scope: Scope | None = None) -> list[MappingClaim]:
    """The claims competing for a role — within one scope when given.

    ``scope=None`` means every candidate, whatever its scope: that is what
    a landscape-wide view asks for, and it is what a project with no scope
    declarations always gets.
    """
    return sorted(
        (c for c in store.claims.values()
         if isinstance(c, MappingClaim) and c.role == role
         and (scope is None or c.scope == scope)),
        key=lambda c: c.id,
    )


def scopes_of(store: ProjectStore, role: str) -> list[Scope | None]:
    """The scopes a role is contested in, in a stable order.

    One entry per declared owner with a candidate, plus ``None`` when
    landscape-wide candidates exist. A project that declares nothing gets
    exactly ``[None]`` — one election, as before.
    """
    seen = {c.scope for c in _candidates(store, role)}
    explicit = sorted((s for s in seen if s is not None),
                      key=lambda s: s.label())
    return ([None] if None in seen else []) + explicit


def settled_slots(store: ProjectStore, guide: DomainGuide, object_name: str,
                  scope: Scope | None = None) -> dict[str, str]:
    """Which slot fields of an object a passing run of its law answered.

    ``{field name: the column the run consumed}``. The evidence is already
    there and needs no second author: the elected journal's balance check
    passed *with* ``amount=amount_local_currency``, so that column is the
    posting amount — nothing else had to be asked. Empty while the object
    itself is unsettled: what its fields are is not a question yet.

    Scoped, because the answer is: DE's journal and US's journal each
    consumed their own column, and one entity's passing run says nothing
    about the other's.
    """
    spec = guide.objects[object_name]
    law = REGISTRY.get(spec.decided_by)
    slot_fields = {f.fills: name for name, f in spec.fields.items()
                   if f.decided_by == DECIDED_BY_SLOT and f.fills}
    if law is None or not slot_fields:
        return {}
    answered: dict[str, str] = {}
    for claim in _candidates(store, object_name, scope):
        if claim.status not in _SETTLED:
            continue
        for record in store.evidence_for(claim):
            if (record.type is not EvidenceType.CHECK_RESULT
                    or record.stale
                    or record.verdict is not CheckVerdict.PASS):
                continue
            plan = store.checks.get(record.check_plan_id or "")
            if plan is None or plan.template != spec.decided_by:
                continue
            for slot, field_name in slot_fields.items():
                column = plan.params.get(slot)
                view = plan.params.get(law.slots[slot])
                if column and view:
                    answered[field_name] = f"{view}.{column}"
    return answered


def resolve_mappings(store: ProjectStore,
                     guide: DomainGuide) -> list[ClarificationQuestion]:
    """Every object and every clarification field ends in a check verdict or
    a clarification question — once per scope it is contested in.

    The election unit is role × scope. DE and US each legitimately own a
    journal, an account column, a period column; electing one winner across
    the landscape would force a human to discard correct mappings, and
    would report a working ledger as contradicted because another entity's
    ledger balances better. A role whose candidates declare no scope is
    contested once, landscape-wide — which is every project that has not
    said whose books its sources are.

    Idempotent: cards dedup on wording *and* scope. Entries still genuinely
    in flight (candidates without a check result and without a V2 no-check
    declaration) draft nothing — a question about an untried binding would
    be noise.
    """
    any_candidates = any(
        isinstance(c, MappingClaim) for c in store.claims.values()
    )
    drafted = []
    for object_name, spec in guide.objects.items():
        slots = {name: f for name, f in spec.fields.items()
                 if f.decided_by == DECIDED_BY_SLOT}
        for scope in scopes_of(store, object_name) or [None]:
            object_settled = any(c.status in _SETTLED
                                 for c in _candidates(store, object_name, scope))
            _draft(store, drafted, object_name, spec.decided_by,
                   spec.definition, any_candidates, scope)
            answered = (settled_slots(store, guide, object_name, scope)
                        if object_settled else {})
            for field_name, field in slots.items():
                if not object_settled or field_name in answered:
                    # the object's own question carries an unsettled field;
                    # a settled one has its answer in the passing run
                    continue
                text = QUESTION_SLOT_UNCONSUMED.format(
                    role=field_name, definition=_sentence(field.definition),
                    law=spec.decided_by, object=object_name, slot=field.fills,
                )
                _save(store, drafted, text,
                      _candidates(store, field_name, scope), scope)
        # a clarification field is contested in its own candidates' scopes,
        # not its object's: nothing ties the two sets together
        for field_name, field in spec.fields.items():
            if field.decided_by == DECIDED_BY_SLOT:
                continue
            for scope in scopes_of(store, field_name) or [None]:
                _draft(store, drafted, field_name, field.decided_by,
                       field.definition, any_candidates, scope)
    return drafted


def _sentence(definition: str) -> str:
    """The guide's own definition, as one sentence inside a question.

    The guide is the only human-written business vocabulary we have; a
    question that names a role without saying what it means is answerable
    only by someone who already knows the guide.
    """
    text = " ".join(definition.split())
    if text and not text.endswith((".", "?", "!")):
        text += "."
    return text


def _draft(store: ProjectStore, drafted: list, role: str, decided_by: str,
           definition: str, any_candidates: bool,
           scope: Scope | None = None) -> None:
    """The verdict-or-question rule for one law- or clarification-decided
    entry, within one scope."""
    candidates = _candidates(store, role, scope)
    if any(c.status in _SETTLED for c in candidates):
        return
    said = _sentence(definition)
    if not candidates:
        # only once the search has run at all — an empty store is
        # a project that has not reached the proposal step yet
        if not any_candidates:
            return
        text = QUESTION_EMPTY.format(role=role, definition=said)
    elif decided_by == DECIDED_BY_CLARIFICATION:
        text = QUESTION_CHOOSE.format(role=role, definition=said)
    else:  # a domain law decides — did it get to speak?
        checked = any(
            e.type is EvidenceType.CHECK_RESULT and not e.stale
            for c in candidates
            for e in store.evidence_for(c)
        )
        if checked:
            text = QUESTION_LOST.format(role=role, definition=said,
                                        law=decided_by)
        elif all(_has_no_check_declaration(store, c) for c in candidates):
            text = QUESTION_UNBOUND.format(role=role, definition=said,
                                           law=decided_by)
        else:
            return  # binding still pending, not yet a question
    _save(store, drafted, text, candidates, scope)


def _scoped(text: str, scope: Scope | None) -> str:
    """The question, told which books it is about.

    Two entities each own a journal. One sentence asked of both would have
    the reader answer for the wrong one — so the scope leads, before the
    question, where it cannot be missed.
    """
    if scope is None or not scope.is_explicit():
        return text
    return f"For {scope.label()}: {text}"


def _save(store: ProjectStore, drafted: list, text: str,
          candidates: list[MappingClaim], scope: Scope | None = None) -> None:
    card = ClarificationQuestion(question=_scoped(text, scope), scope=scope,
                                 claim_ids=[c.id for c in candidates])
    if store.find_question(card):
        return
    store.save_question(card)
    drafted.append(card)
