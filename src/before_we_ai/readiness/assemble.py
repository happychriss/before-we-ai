"""The dependency list, assembled on every read — and who vouches for it.

Nothing stores the list. It is put together here, every time, from three
sources in this order:

1. the **answer type** the question was classified to, expanded from the
   domain guide (``expand``) — reviewed items, marked ``contract``;
2. whatever the request contract **drafted freely** for this question —
   because no answer type matched, or because the question carries a delta
   the type does not cover; marked ``proposed``;
3. the **acts** a human (or, for links, the AI) has taken on it, replayed
   oldest first, so a later act answers an earlier one.

Deriving it is what keeps it honest. A stored list would go on describing a
guide that has since changed, and a dependency list that is quietly out of
date is the same failure as one that was short to begin with: nobody can
test, waive or clarify what is not on it.

The second job here is the **review state**. Whether the dependencies hold is
one question; whether the list of them can be trusted is another, and the
product must answer both. Only a human confirmation answers the second, and a
confirmation lapses when the guide it was given against changes — it was a
statement about *that* list.
"""

from dataclasses import dataclass

from before_we_ai.core.enums import ActKind, KnowledgeKind, Provenance
from before_we_ai.core.objects import (
    AnswerRequest,
    KnowledgeItem,
    KnowledgeLink,
)
from before_we_ai.llm.domain_guide import DomainGuide, short_fingerprint
from before_we_ai.readiness.expand import UnknownAnswerType, expand
from before_we_ai.store.repository import ProjectStore


@dataclass(frozen=True)
class Review:
    """Who, if anyone, has vouched for the dependency list itself.

    ``confirmed`` is the only state in which a verdict may read ``ready``.
    Everything else caps it, because a verdict computed over a list nobody
    has read is only as complete as the list — and its incompleteness would
    not show up anywhere.
    """

    answer_type: str | None = None
    confirmed: bool = False
    #: Confirmed once, and then something moved under it: "guide" or
    #: "question". Which one matters to the reader — one is a change to the
    #: vocabulary everyone shares, the other is a change they made
    #: themselves — so it is carried rather than collapsed to a boolean.
    lapsed_by: str = ""
    drafted: int = 0  # items the model drafted for this question alone
    broken: str = ""  # the contract cannot be expanded at all

    @property
    def lapsed(self) -> bool:
        return bool(self.lapsed_by)

    def note(self) -> str:
        """The clause a verdict carries when the list is not vouched for."""
        if self.broken:
            return self.broken
        if self.confirmed:
            return ""
        if self.lapsed_by == "guide":
            return (
                "The dependency list was confirmed against an earlier version "
                "of the domain guide, and the guide has changed since — what "
                "was reviewed is not what is listed here."
            )
        if self.lapsed_by == "question":
            return (
                "The dependency list was confirmed for an earlier wording of "
                "this question, and the question has been revised since — "
                "what was reviewed is not what is being asked here."
            )
        if self.answer_type is None:
            return (
                "No answer type of the domain guide covers this question, so "
                "its dependency list was drafted for this question alone and "
                "nobody has reviewed it: what was never listed cannot be "
                "tested, waived or asked about."
            )
        if self.drafted:
            return (
                f"The dependency list rests on the answer type "
                f"'{self.answer_type}' plus {self.drafted} item"
                f"{'s' if self.drafted != 1 else ''} drafted for this question "
                "alone, and nobody has confirmed it."
            )
        return (
            f"The dependency list was expanded from the answer type "
            f"'{self.answer_type}', but nobody has confirmed that this "
            "question depends on nothing more."
        )


#: What ``evaluate`` assumes when a caller hands it a list directly: that the
#: caller is the reviewer. The stored path never uses it — ``assemble``
#: always works out the real state.
REVIEWED = Review(confirmed=True)


@dataclass(frozen=True)
class Assembly:
    items: tuple[KnowledgeItem, ...]
    review: Review


def assemble(store: ProjectStore, guide: DomainGuide,
             request: AnswerRequest) -> Assembly:
    """The dependency list for one request as it stands right now."""
    items, broken = _from_contract(guide, request)
    drafted = _drafted(store, request)
    items += drafted
    review = _review(store, guide, request, len(drafted), broken)
    return Assembly(items=_replay(store, request, items), review=review)


def _from_contract(guide: DomainGuide,
                   request: AnswerRequest) -> tuple[list[KnowledgeItem], str]:
    if request.answer_type is None:
        return [], ""
    try:
        return expand(request.answer_type, guide, request.scope), ""
    except UnknownAnswerType:
        # The guide dropped or renamed the type this question was classified
        # to. Expanding to nothing would be the silent short list the whole
        # design exists to prevent, so this blocks and says why.
        return [], (
            f"This question was classified as '{request.answer_type}', which "
            f"the {guide.domain} guide no longer declares — until it is "
            "classified again, nothing states what the answer depends on."
        )


def _drafted(store: ProjectStore,
             request: AnswerRequest) -> list[KnowledgeItem]:
    """The freely drafted items — the fallback list, or the delta."""
    required = store.knowledge_for(request.id)
    if required is None:
        return []
    return [item.model_copy(update={"provenance": Provenance.PROPOSED})
            for item in required.items]


def _review(store: ProjectStore, guide: DomainGuide, request: AnswerRequest,
            drafted: int, broken: str) -> Review:
    confirmed = False
    lapsed_by = ""
    for act in store.acts_for(request.id):
        if act.kind is not ActKind.CONFIRM:
            continue
        # A confirmation is a statement about one list, and two things
        # decide what that list says: the guide it was expanded from and
        # the question it was expanded for. Either moving means the human
        # vouched for something else.
        guide_held = act.guide_fingerprint == guide.fingerprint
        question_held = act.request_fingerprint == request.fingerprint()
        confirmed = guide_held and question_held
        lapsed_by = "" if confirmed else ("question" if guide_held else "guide")
    return Review(answer_type=request.answer_type, confirmed=confirmed,
                  lapsed_by=lapsed_by, drafted=drafted, broken=broken)


def _replay(store: ProjectStore, request: AnswerRequest,
            items: list[KnowledgeItem]) -> tuple[KnowledgeItem, ...]:
    """Apply every act in the order it was taken.

    Waivers and links do **not** lapse with the guide, unlike a
    confirmation. A confirmation says "this list is complete", which stops
    being true when the list changes. A waiver says "this item does not
    matter for this question" and a link says "this claim speaks to this
    item" — both are about one item, and a change elsewhere in the guide
    leaves them exactly as true as they were.
    """
    by_ref = {item.ref(): item for item in items}
    for act in store.acts_for(request.id):
        if act.kind is ActKind.ADD and act.item is not None:
            item = act.item.model_copy(update={"provenance": Provenance.ADDED})
            by_ref[item.ref()] = item
            continue
        current = by_ref.get(act.ref) if act.ref else None
        if current is None:
            continue  # the item it spoke about is no longer on the list
        if act.kind is ActKind.WAIVE:
            by_ref[act.ref] = current.model_copy(
                update={"waived_because": act.reason})
        elif act.kind is ActKind.REQUIRE_AGAIN:
            by_ref[act.ref] = current.model_copy(
                update={"waived_because": None})
        elif act.kind is ActKind.LINK and current.kind is KnowledgeKind.RULE:
            kept = [l for l in current.satisfied_by
                    if l.claim_id != act.claim_id]
            by_ref[act.ref] = current.model_copy(update={"satisfied_by": kept + [
                KnowledgeLink(claim_id=act.claim_id, linked_by=act.actor,
                              note=act.note)
            ]})
    return tuple(by_ref.values())


def guide_label(guide: DomainGuide) -> str:
    """How the report names the guide a list was expanded from."""
    return short_fingerprint(guide.fingerprint) or "unversioned"
