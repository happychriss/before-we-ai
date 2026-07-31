"""The ReadinessMap: what the system is *permitted to claim* about an answer.

This is the bottom of the machine and the last handover. A check never
proves a claim and never produces an answer:

    CheckPlan -> CheckRun -> Evidence -> claim status -> readiness decision

The AI proposes the path, the engine measures, evidence changes what may be
*believed* — and only here is it decided what may be *claimed*. Nothing in
this module writes anything: the map is derived on every read, from the
claims and evidence it rests on, exactly like ``resolve_status``. A stored
readiness verdict could drift away from the evidence under it, and a
verdict that has drifted is worse than none.

Two rules govern the output and are not negotiable:

1. ``blocked`` and ``ready_with_limitations`` **name the dependency**. A
   verdict without its reason is the one thing this product may not ship.
2. Every satisfied item says **how** it is satisfied. Since the owner's
   decision of 2026-07-31, *satisfied* and *promoted* are deliberately
   different things — a slot field can be satisfied by the run that
   consumed its column while its own claims stay ``proposed`` — so an item
   that said only "satisfied" would hide precisely the distinction that
   decision preserves.
"""

import re
from dataclasses import dataclass
from enum import Enum

from before_we_ai.llm.domain_guide import DomainGuide, settled_slots
from before_we_ai.model.enums import ClaimStatus, KnowledgeKind
from before_we_ai.model.objects import (
    AnswerRequest,
    Claim,
    ConceptClaim,
    KnowledgeItem,
    MappingClaim,
    RequiredKnowledge,
    Scope,
)
from before_we_ai.store.repository import ProjectStore

_SETTLED = (ClaimStatus.TEST_SUPPORTED, ClaimStatus.BUSINESS_CONFIRMED)


class Readiness(str, Enum):
    """What the system permits for one requested answer.

    Deliberately not in ``model/enums.py``: the epistemic core says what may
    be *believed*, and this says what may be *claimed*. Keeping the two
    vocabularies apart is the handover principle, spelled as a module
    boundary.
    """

    READY = "ready"
    READY_WITH_LIMITATIONS = "ready_with_limitations"
    BLOCKED = "blocked"


class Ground(str, Enum):
    """Why an item is satisfied — or why it is not."""

    # satisfied
    ELECTED = "elected"  # its own claim carries check or human evidence
    SLOT_DERIVATION = "slot_derivation"  # its object's passing law consumed it
    STATED_RULE = "stated_rule"  # a settled claim states the rule
    # unsatisfied
    NOTHING_PROPOSED = "nothing_proposed"
    ALL_CONTRADICTED = "all_contradicted"
    UNDECIDED = "undecided"  # candidates exist, none settled


@dataclass(frozen=True)
class ReadinessItem:
    """One required-knowledge item, judged."""

    item: KnowledgeItem
    satisfied: bool
    ground: Ground
    because: str  # the derived sentence; never a model's words
    claim_ids: tuple[str, ...] = ()

    @property
    def ref(self) -> str:
        return self.item.ref()

    @property
    def structural(self) -> bool:
        """Is this what the answer is computed *from*?

        An object or a field is a number's source; not knowing it means no
        number can be produced. A rule is what the number *means*.
        """
        return self.item.kind is not KnowledgeKind.RULE


@dataclass(frozen=True)
class ReadinessMap:
    """Per required-knowledge item: claim, evidence, status, remaining gap —
    and the one verdict they add up to."""

    request: AnswerRequest
    items: tuple[ReadinessItem, ...]
    verdict: Readiness

    def unsupported(self) -> list[ReadinessItem]:
        return [i for i in self.items if not i.satisfied]

    def blocking(self) -> list[ReadinessItem]:
        """The unsupported items that cost the answer its numbers."""
        return [i for i in self.unsupported() if i.structural]

    def limitations(self) -> list[ReadinessItem]:
        """The unsupported items that cost the answer its meaning."""
        return [i for i in self.unsupported() if not i.structural]

    def reason(self) -> str:
        """The verdict as one sentence that names what it rests on.

        Every branch names dependencies, because a verdict whose reason a
        reader has to go looking for is a verdict they will take on trust.
        """
        if self.verdict is Readiness.READY:
            n = len(self.items)
            if n == 0:
                return "This answer was declared to depend on nothing."
            if n == 1:
                return "The one thing this answer depends on is supported."
            return f"All {n} things this answer depends on are supported."
        if self.verdict is Readiness.BLOCKED:
            one = len(self.blocking()) == 1
            missing = _list(i.ref for i in self.blocking())
            return (
                f"The answer cannot be produced: {missing} "
                f"{'is' if one else 'are'} unsupported, and the figures are "
                f"computed from {'it' if one else 'them'}."
            )
        one = len(self.limitations()) == 1
        missing = _list(i.ref for i in self.limitations())
        return (
            f"The figures can be produced, but what they mean is not "
            f"settled: {missing} {'remains' if one else 'remain'} unsupported."
        )


def evaluate(store: ProjectStore, guide: DomainGuide, request: AnswerRequest,
             required: RequiredKnowledge) -> ReadinessMap:
    """Walk the required knowledge down to claims and evidence.

    The verdict follows from *what kind* of dependency is missing, not from
    anyone's opinion of how important it is. An object or field is what the
    figures are computed from — without it there is no number, so the answer
    is **blocked**. A rule is what the figures mean — the number exists but
    is qualified, so the answer is **ready_with_limitations** and the map
    names every qualification. Nothing missing: **ready**.
    """
    items = tuple(_judge(store, guide, item) for item in required.items)
    if all(i.satisfied for i in items):
        verdict = Readiness.READY
    elif any(not i.satisfied and i.structural for i in items):
        verdict = Readiness.BLOCKED
    else:
        verdict = Readiness.READY_WITH_LIMITATIONS
    return ReadinessMap(request=request, items=items, verdict=verdict)


def evaluate_request(store: ProjectStore, guide: DomainGuide,
                     request_id: str) -> ReadinessMap | None:
    """The map for a stored request, or None when nothing requires anything
    of it yet (V4 has not run, or a human pruned the draft to nothing)."""
    request = store.requests.get(request_id)
    required = store.knowledge_for(request_id) if request else None
    if request is None or required is None:
        return None
    return evaluate(store, guide, request, required)


# -- judging one item ------------------------------------------------------

def _judge(store: ProjectStore, guide: DomainGuide,
           item: KnowledgeItem) -> ReadinessItem:
    if item.kind is KnowledgeKind.RULE:
        return _judge_rule(store, item)
    if item.kind is KnowledgeKind.FIELD:
        derived = _slot_derivation(store, guide, item)
        if derived is not None:
            return derived
    return _judge_binding(store, item)


def _judge_binding(store: ProjectStore, item: KnowledgeItem) -> ReadinessItem:
    """An object or a field, satisfied by a settled mapping claim of its own."""
    candidates = [c for c in store.claims.values()
                  if isinstance(c, MappingClaim) and c.role == item.name
                  and _covers(c.scope, item.scope)]
    winners = [c for c in candidates if c.status in _SETTLED]
    if winners:
        won = winners[0]
        return ReadinessItem(
            item=item, satisfied=True, ground=Ground.ELECTED,
            because=(
                f"Satisfied because its own claim is {won.status.value}: "
                f"{_name(won)} plays '{item.name}'"
                f"{_scope_note(won.scope, item.scope)}."
            ),
            claim_ids=tuple(sorted(c.id for c in winners)),
        )
    return ReadinessItem(item=item, satisfied=False,
                         claim_ids=tuple(sorted(c.id for c in candidates)),
                         **_why_not(candidates, item, "plays it"))


def _slot_derivation(store: ProjectStore, guide: DomainGuide,
                     item: KnowledgeItem) -> ReadinessItem | None:
    """The owner's decision of 2026-07-31, made visible.

    A slot field is answered by the column its object's passing law
    consumed. Its own candidate claims keep their evidence-derived status —
    today ``proposed`` — because no run ever tested one of them alone. The
    map reads that derivation and says so in those words, rather than
    letting the run's evidence promote a claim it was never bound to.
    """
    if item.of_object not in guide.objects:
        return None
    # a scope that names nothing IS the landscape-wide one, which claims
    # carry as None — the two spellings must not miss each other
    asked = item.scope if item.scope.is_explicit() else None
    column = settled_slots(store, guide, item.of_object, asked).get(item.name)
    if column is None and asked is not None:
        # a landscape-wide run covers a scoped question, as a landscape-wide
        # claim does
        column = settled_slots(store, guide, item.of_object, None).get(item.name)
    if column is None:
        return None
    law = guide.objects[item.of_object].decided_by
    return ReadinessItem(
        item=item, satisfied=True, ground=Ground.SLOT_DERIVATION,
        because=(
            f"Satisfied because the {law} law of '{item.of_object}' passed "
            f"while reading {column} — that run is the answer. Its own "
            "candidate claims are still proposed: no check tested one of "
            "them on its own."
        ),
    )


def _judge_rule(store: ProjectStore, item: KnowledgeItem) -> ReadinessItem:
    """A rule the vocabulary does not contain, satisfied by a settled claim.

    Matching is by name, normalised: a concept claim's term, or a claim's
    predicate name. Anything else leaves the item unsupported and *named* —
    which is the point. The demo's non-inferable policy arrives exactly this
    way: unsupported until a human answers, then a business-confirmed claim
    carrying their words.
    """
    key = _slug(item.name)
    stating = [c for c in store.claims.values()
               if _states_rule(c, key) and _covers(c.scope, item.scope)]
    winners = [c for c in stating if c.status in _SETTLED]
    if winners:
        won = winners[0]
        return ReadinessItem(
            item=item, satisfied=True, ground=Ground.STATED_RULE,
            because=(
                f"Satisfied because a {won.status.value} claim states it: "
                f"{won.statement}{_scope_note(won.scope, item.scope)}."
            ),
            claim_ids=tuple(sorted(c.id for c in winners)),
        )
    return ReadinessItem(item=item, satisfied=False,
                         claim_ids=tuple(sorted(c.id for c in stating)),
                         **_why_not(stating, item, "states it"))


def _why_not(candidates: list[Claim], item: KnowledgeItem,
             verb: str) -> dict:
    """Why an item is unsupported, specifically enough to act on.

    "Unsupported" alone sends a reader hunting. Each branch says what state
    the evidence is actually in, because the three are three different jobs:
    declare a source, fix the data, or answer a question.
    """
    if not candidates:
        return {
            "ground": Ground.NOTHING_PROPOSED,
            "because": (
                f"Not supported: nothing in this project {verb}"
                f"{_scope_ask(item.scope)}."
            ),
        }
    if all(c.status is ClaimStatus.CONTRADICTED for c in candidates):
        n = len(candidates)
        return {
            "ground": Ground.ALL_CONTRADICTED,
            "because": (
                f"Not supported: all {n} candidate{'s' if n != 1 else ''} "
                f"{'were' if n != 1 else 'was'} tested and contradicted. "
                "This is not a missing answer but a wrong one — the data "
                "itself has to change."
            ),
        }
    n = len(candidates)
    return {
        "ground": Ground.UNDECIDED,
        "because": (
            f"Not supported: {n} candidate{'s' if n != 1 else ''} "
            f"{'are' if n != 1 else 'is'} proposed and none is settled — "
            "a human has to answer, or a check has to run."
        ),
    }


# -- helpers ---------------------------------------------------------------

def _covers(claim_scope: Scope | None, item_scope: Scope) -> bool:
    """Does a claim's scope reach the scope the question was asked in?

    A claim about the whole landscape covers any scope inside it — a shared
    account master genuinely serves every entity, and "no declared owner" is
    the normal state for one. The reverse is not true: DE's ledger says
    nothing about the landscape. The leniency is deliberate and never
    silent; ``_scope_note`` puts it in the sentence.
    """
    if claim_scope is None or not claim_scope.is_explicit():
        return True
    return claim_scope == item_scope


def _scope_note(claim_scope: Scope | None, item_scope: Scope) -> str:
    if not item_scope.is_explicit():
        return ""
    if claim_scope is None or not claim_scope.is_explicit():
        return (f" — though no source declares it as {item_scope.label()}'s, "
                "so this rests on a landscape-wide mapping")
    return f" for {claim_scope.label()}"


def _scope_ask(scope: Scope) -> str:
    return f" for {scope.label()}" if scope.is_explicit() else ""


def _states_rule(claim: Claim, key: str) -> bool:
    if isinstance(claim, ConceptClaim) and _slug(claim.term) == key:
        return True
    return bool(claim.predicate and _slug(claim.predicate.name) == key)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _name(claim: MappingClaim) -> str:
    table = claim.binding.get("table")
    if table:
        return str(table)
    return ", ".join(f"{k}={v}" for k, v in sorted(claim.binding.items()))


def _list(refs) -> str:
    refs = [f"'{r}'" for r in refs]
    if len(refs) == 1:
        return refs[0]
    return ", ".join(refs[:-1]) + " and " + refs[-1]
