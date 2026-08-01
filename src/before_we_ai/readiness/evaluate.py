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

Three rules govern the output and are not negotiable:

1. ``blocked`` and ``ready_with_limitations`` **name the dependency**. A
   verdict without its reason is the one thing this product may not ship.
2. Every satisfied item says **how** it is satisfied. *Satisfied* and
   *promoted* are deliberately different things — a slot field can be
   satisfied by the run that consumed its column while its own claims stay
   ``proposed`` — so an item reading only "satisfied" would hide exactly
   that distinction.
3. A verdict is never stronger than the list it was computed over. Whether
   the dependencies hold is one question; whether anyone has vouched for the
   *list* of them is another (``assemble.Review``), and an unreviewed list
   caps the verdict at ``ready_with_limitations`` naming itself. An
   incomplete list would otherwise produce a confident ``ready`` with
   nothing anywhere to show what was missing.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Sequence

from before_we_ai.llm.domain_guide import DomainGuide, settled_slots
from before_we_ai.core.enums import ActKind, Actor, ClaimStatus, KnowledgeKind
from before_we_ai.core.objects import (
    AnswerRequest,
    Claim,
    KnowledgeAct,
    KnowledgeItem,
    MappingClaim,
    Scope,
)
from before_we_ai.readiness.assemble import REVIEWED, Review, assemble
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
    WAIVED = "waived"  # a human decided the answer does not rest on it
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
    review: Review = REVIEWED

    @property
    def answer_type(self) -> str | None:
        return self.review.answer_type

    @property
    def confirmed(self) -> bool:
        return self.review.confirmed

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
        The review clause is appended rather than folded in: what is missing
        from the list and what is missing from the *review of* the list are
        two different gaps, and a reader has to act on them differently.
        """
        note = self.review.note()
        return f"{self._dependencies()} {note}".strip() if note \
            else self._dependencies()

    def _dependencies(self) -> str:
        if self.blocking():
            one = len(self.blocking()) == 1
            missing = _list(i.ref for i in self.blocking())
            return (
                f"The answer cannot be produced: {missing} "
                f"{'is' if one else 'are'} unsupported, and the figures are "
                f"computed from {'it' if one else 'them'}."
            )
        if self.limitations():
            one = len(self.limitations()) == 1
            missing = _list(i.ref for i in self.limitations())
            return (
                f"The figures can be produced, but what they mean is not "
                f"settled: {missing} {'remains' if one else 'remain'} "
                "unsupported."
            )
        n = len(self.items)
        if n == 0:
            return "This answer was declared to depend on nothing."
        if n == 1:
            return "The one thing this answer depends on is supported."
        return f"All {n} things this answer depends on are supported."


def evaluate(store: ProjectStore, guide: DomainGuide, request: AnswerRequest,
             items: Sequence[KnowledgeItem], *,
             review: Review = REVIEWED) -> ReadinessMap:
    """Walk the dependency list down to claims and evidence.

    The verdict follows from *what kind* of dependency is missing, not from
    anyone's opinion of how important it is. An object or field is what the
    figures are computed from — without it there is no number, so the answer
    is **blocked**. A rule is what the figures mean — the number exists but
    is qualified, so the answer is **ready_with_limitations** and the map
    names every qualification. Nothing missing: **ready**.

    ``review`` says whether anyone has vouched for the list itself, and an
    unvouched-for list can never read ``ready``. The default assumes the
    caller *is* the reviewer, which is true of a list handed in directly and
    never assumed on the stored path — ``evaluate_request`` always works the
    real state out.
    """
    judged = tuple(_judge(store, guide, item, request.scope) for item in items)
    if review.broken:
        # No dependency list at all is worse than an unsupported one: there
        # is nothing to test and nothing to name.
        verdict = Readiness.BLOCKED
    elif any(not i.satisfied and i.structural for i in judged):
        verdict = Readiness.BLOCKED
    elif all(i.satisfied for i in judged) and review.confirmed:
        verdict = Readiness.READY
    else:
        verdict = Readiness.READY_WITH_LIMITATIONS
    return ReadinessMap(request=request, items=judged, verdict=verdict,
                        review=review)


class UnlinkableItem(Exception):
    """Raised when an act is aimed at something that cannot carry one."""


def _act_on(store: ProjectStore, guide: DomainGuide, request_id: str,
            ref: str) -> tuple[AnswerRequest, KnowledgeItem]:
    """The request and the one assembled item ``ref`` names.

    Acts are recorded against the *derived* list, so the item has to be
    found there rather than in a stored record — there is no stored record
    of the list any more, and that is the point.
    """
    request = store.requests.get(request_id)
    if request is None:
        raise UnlinkableItem(f"no request {request_id} in this project")
    items = assemble(store, guide, request).items
    for item in items:
        if item.ref() == ref:
            return request, item
    raise UnlinkableItem(
        f"{ref!r} is not required by request {request_id} — "
        f"required: {sorted(i.ref() for i in items)}"
    )


def waive_item(store: ProjectStore, guide: DomainGuide, request_id: str,
               ref: str, because: str) -> KnowledgeAct:
    """A human strikes a dependency the answer does not actually rest on.

    Without it, a listed dependency nobody needs blocks the answer forever.

    Waived, not deleted: the item stays in the map, struck through, carrying
    the reason. A reason is mandatory; a waiver without one is the silence
    this product forbids, and it is also the only thing that distinguishes
    a judgement from a mistake six months later.

    Unlike a confirmation, a waiver does **not** lapse when the guide
    changes. A confirmation says "this list is complete", which stops being
    true the moment the list moves; a waiver says "this item does not matter
    for this question", which a change elsewhere leaves untouched.
    """
    if not because.strip():
        raise UnlinkableItem(
            f"waiving {ref!r} requires a reason — an unexplained waiver is "
            "indistinguishable from an oversight"
        )
    _act_on(store, guide, request_id, ref)
    return _record(store, request_id, ActKind.WAIVE, Actor.HUMAN, guide,
                   ref=ref, reason=because.strip())


def require_again(store: ProjectStore, guide: DomainGuide, request_id: str,
                  ref: str) -> KnowledgeAct:
    """Undo a waiver — a judgement call may be revisited.

    The waiver is not erased; this answers it. Both stay readable as the
    history of one decision being taken and taken back.
    """
    _act_on(store, guide, request_id, ref)
    return _record(store, request_id, ActKind.REQUIRE_AGAIN, Actor.HUMAN,
                   guide, ref=ref)


def link_claim(store: ProjectStore, guide: DomainGuide, request_id: str,
               ref: str, claim_id: str, *, linked_by: Actor,
               note: str = "") -> KnowledgeAct:
    """Point a required rule at the claim that states it.

    The seam M5 needs: V3 reads a policy document, produces a claim, and
    says which open dependency that claim answers. It is also how a human
    answering a clarification connects their answer to the question it
    settles.

    Linking is deliberately *not* evidence: the claim's own status still
    decides whether the dependency is satisfied, so this cannot promote
    anything and an AI may do it. Re-linking the same claim replaces the
    earlier link rather than stacking duplicates.
    """
    if claim_id not in store.claims:
        raise UnlinkableItem(f"no claim {claim_id} in this project")
    _, item = _act_on(store, guide, request_id, ref)
    if item.kind is not KnowledgeKind.RULE:
        raise UnlinkableItem(
            f"{item.kind.value} {ref!r} resolves through the domain "
            "guide's scoped election; only a rule takes a linked claim"
        )
    return _record(store, request_id, ActKind.LINK, linked_by, guide,
                   ref=ref, claim_id=claim_id, note=note)


def add_item(store: ProjectStore, guide: DomainGuide, request_id: str,
             item: KnowledgeItem) -> KnowledgeAct:
    """A human puts on the list something the contract did not.

    The answer to under-listing that does not wait for the guide to be
    fixed: the reader who spots the gap can close it here, and the item is
    marked ``added`` so nobody mistakes it for reviewed content.
    """
    if request_id not in store.requests:
        raise UnlinkableItem(f"no request {request_id} in this project")
    return _record(store, request_id, ActKind.ADD, Actor.HUMAN, guide,
                   item=item)


def confirm_classification(store: ProjectStore, guide: DomainGuide,
                           request_id: str, *,
                           by: Actor = Actor.HUMAN) -> KnowledgeAct:
    """A human vouches for the dependency list as a whole.

    This is the act the cap exists to ask for. It says two things at once:
    the question was classified correctly, and the list that classification
    expands to is complete. It is recorded against this guide's fingerprint,
    so it lapses when the guide moves and the reader is asked again.
    """
    request = store.requests.get(request_id)
    if request is None:
        raise UnlinkableItem(f"no request {request_id} in this project")
    return _record(store, request_id, ActKind.CONFIRM, by, guide,
                   answer_type=request.answer_type)


def _record(store: ProjectStore, request_id: str, kind: ActKind, actor: Actor,
            guide: DomainGuide, **fields) -> KnowledgeAct:
    act = KnowledgeAct(request_id=request_id, kind=kind, actor=actor,
                       guide_fingerprint=guide.fingerprint, **fields)
    store.save_act(act)
    return act


def evaluate_request(store: ProjectStore, guide: DomainGuide,
                     request_id: str) -> ReadinessMap | None:
    """The map for a stored request, or None when nothing states what it
    depends on yet — no answer type, and no freely drafted list either."""
    request = store.requests.get(request_id)
    if request is None:
        return None
    built = assemble(store, guide, request)
    if not built.items and not built.review.broken:
        return None
    return evaluate(store, guide, request, built.items, review=built.review)


# -- judging one item ------------------------------------------------------

def _judge(store: ProjectStore, guide: DomainGuide, item: KnowledgeItem,
           asked: Scope) -> ReadinessItem:
    if item.waived:
        # A waiver is a human overriding the draft, so it says who decided
        # and why — it never reads as evidence, and it never reads as a gap.
        return ReadinessItem(
            item=item, satisfied=True, ground=Ground.WAIVED,
            because=(
                "Not required: a human waived this dependency — "
                f"{item.waived_because}"
            ),
        )
    if item.kind is KnowledgeKind.RULE:
        # a rule carries no scope of its own; what matters is whether the
        # claim stating it reaches the scope the question was asked in
        return _judge_rule(store, item, asked)
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
    """The owner's decision, made visible.

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


def _judge_rule(store: ProjectStore, item: KnowledgeItem,
                asked: Scope) -> ReadinessItem:
    """A rule the vocabulary does not contain, satisfied by a **linked** claim.

    Only an explicit link counts. The alternative — matching the rule's name
    against a concept claim's term or a predicate name — was tried and
    rejected (owner decision): a rule is named in the human's
    words ("sign convention for income and expense") while whatever produces
    the claim coins its own term, so the match would miss where it matters
    and, worse, could hit something unrelated that happens to slug the same.
    A verdict resting on a coincidence of wording is not a verdict.

    Unlinked therefore means unsupported and *named*, which is the correct
    default: a rule nobody has connected to evidence is a rule nobody has
    answered. The demo's non-inferable policy arrives exactly this way —
    unsupported until a human answers, then a business-confirmed claim
    carrying their words, linked to the dependency it settles.
    """
    linked = [(link, store.claims[link.claim_id])
              for link in item.satisfied_by if link.claim_id in store.claims]
    dangling = [link for link in item.satisfied_by
                if link.claim_id not in store.claims]
    in_scope = [(link, claim) for link, claim in linked
                if _covers(claim.scope, asked)]
    winners = [(link, claim) for link, claim in in_scope
               if claim.status in _SETTLED]
    if winners:
        link, claim = winners[0]
        # A rule can carry several links. Satisfaction rests on the settled
        # one — but a contradicted claim linked to the same rule is a
        # conflict, and a conflict this product does not say out loud is the
        # one failure it exists to prevent. Named, verdict unchanged: the
        # contradicted claim may simply be the loser.
        beaten = [c for _, c in in_scope
                  if c.status is ClaimStatus.CONTRADICTED]
        conflict = (
            f" A contradicted claim is also linked to this rule "
            f"({'; '.join(c.statement for c in beaten)}) — read both before "
            "relying on the answer." if beaten else ""
        )
        return ReadinessItem(
            item=item, satisfied=True, ground=Ground.STATED_RULE,
            because=(
                f"Satisfied because a {claim.status.value} claim is linked to "
                f"it by the {link.linked_by.value}: {claim.statement}"
                f"{_rule_scope_note(claim.scope, asked)}.{conflict}"
            ),
            claim_ids=tuple(sorted(c.id for _, c in in_scope)),
        )
    if dangling:
        # integrity also reports it; the verdict must not read as a mere gap
        return ReadinessItem(
            item=item, satisfied=False, ground=Ground.NOTHING_PROPOSED,
            because=(
                f"Not supported: this rule is linked to "
                f"{len(dangling)} claim(s) that no longer exist "
                f"({', '.join(sorted(l.claim_id for l in dangling))}) — the "
                "link is broken, not the knowledge."
            ),
        )
    return ReadinessItem(
        item=item, satisfied=False,
        claim_ids=tuple(sorted(c.id for _, c in in_scope)),
        **_why_not([c for _, c in in_scope], item, "is linked to it",
                   asked))


def _why_not(candidates: list[Claim], item: KnowledgeItem, verb: str,
             asked: Scope | None = None) -> dict:
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
                f"{_scope_ask(asked if asked is not None else item.scope)}."
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


def _rule_scope_note(claim_scope: Scope | None, asked: Scope) -> str:
    """The scope clause for a rule — which must not talk about sources.

    ``_scope_note`` was written for role bindings, where "no source
    declares it as DE's" is the right sentence. An accounting policy has no
    source and is not a mapping; what it has is a validity, on the claim.
    """
    if not asked.is_explicit():
        return ""
    if claim_scope is None or not claim_scope.is_explicit():
        return (" — the claim states no scope of its own, so it is taken to "
                f"hold for {asked.label()} as well")
    return f", and that claim holds for {claim_scope.label()}"


def _scope_ask(scope: Scope) -> str:
    return f" for {scope.label()}" if scope.is_explicit() else ""


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
