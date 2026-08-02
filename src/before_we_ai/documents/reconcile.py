"""The multi-anchor rule: what a pile of anchors is allowed to conclude.

Anchors never promote — ``resolve_status`` does not read them — so this
module decides something narrower and more interesting: whether
reconciliation may *propose a link* between a claim and the rule item it
answers, or whether it must surface the situation to a human instead.

The rule applies to **value corroboration**, where a document figure is
offered as agreeing with a number the data produces. It does not apply to
**definitional grounding**, where a policy sentence states a rule the data
cannot show. One accounting policy saying "credit amounts are stored
negative" once is what a policy *is*; demanding a second document would
make policy documents worthless. Nothing is lost by letting that through,
because a link is not evidence: the claim still sits at ``proposed`` until
a check tests it or a human confirms it.

The concerns this raises are the product, as much as the verdict is. A
figure that appears only inside a chart, two figures competing for one
slot, a number that matches only if you assume a locale — each is a
sentence a reader can act on, and none of them is a silent refusal.
"""

from dataclasses import dataclass, field
from decimal import Decimal

from before_we_ai.core.enums import AnchorKind, AnchorMatch, EvidenceType
from before_we_ai.core.objects import EvidenceRecord
from before_we_ai.documents.figures import match_quote, restated_values

# Kinds that can carry a corroborating figure at all. A chart label is a
# picture of a number: the value was chosen by whoever drew it, and no
# reader can check it against anything on the page.
CORROBORATING_KINDS = (AnchorKind.TEXT.value, AnchorKind.TABLE.value)
COUNTING_MATCHES = (AnchorMatch.EXACT.value, AnchorMatch.ROUNDED.value)

CHART_ONLY = "chart_only"
RESTATEMENT = "restatement"
SINGLE_ANCHOR = "single_anchor"
NO_AGREEMENT = "no_agreement"


@dataclass(frozen=True)
class AssessedAnchor:
    """One anchor with everything the rule needs to judge it."""

    record_id: str
    source: str
    page: int
    kind: str
    quote: str
    match: str

    @property
    def place(self) -> tuple[str, int]:
        """Two anchors on one page of one document are not independent."""
        return (self.source, self.page)

    @property
    def counts(self) -> bool:
        return self.kind in CORROBORATING_KINDS and self.match in COUNTING_MATCHES


@dataclass(frozen=True)
class Concern:
    """Something a human should see, with the sentence to show them."""

    code: str
    detail: str


@dataclass(frozen=True)
class Reconciliation:
    """What the anchors for one claim add up to."""

    may_link: bool
    reason: str
    assessed: tuple[AssessedAnchor, ...] = ()
    concerns: tuple[Concern, ...] = field(default=())

    @property
    def counting(self) -> tuple[AssessedAnchor, ...]:
        return tuple(a for a in self.assessed if a.counts)

    @property
    def disregarded(self) -> tuple[AssessedAnchor, ...]:
        return tuple(a for a in self.assessed if not a.counts)


def assess(record: EvidenceRecord, target: Decimal) -> AssessedAnchor:
    """One anchor, measured against the value it is offered for."""
    payload = record.payload
    quote = str(payload.get("quote", ""))
    match, _figure = match_quote(quote, target)
    return AssessedAnchor(
        record_id=record.id,
        source=str(payload.get("source", "")),
        page=int(payload.get("page", 0)),
        kind=str(payload.get("kind", "")),
        quote=quote,
        match=match,
    )


def anchors_for(records: list[EvidenceRecord]) -> list[EvidenceRecord]:
    return [r for r in records if r.type is EvidenceType.DOCUMENT_ANCHOR]


def ground_definition(records: list[EvidenceRecord]) -> Reconciliation:
    """Definitional grounding: a policy sentence stating a rule.

    No corroboration is being claimed, so the multi-anchor threshold does
    not apply — but a rule read off a chart label is still not a rule, so
    the kind test stays.
    """
    assessed = tuple(
        AssessedAnchor(
            record_id=r.id,
            source=str(r.payload.get("source", "")),
            page=int(r.payload.get("page", 0)),
            kind=str(r.payload.get("kind", "")),
            quote=str(r.payload.get("quote", "")),
            # Nothing numeric is being compared; the label would be a lie.
            match="",
        )
        for r in anchors_for(records)
    )
    stated = [a for a in assessed if a.kind in CORROBORATING_KINDS]
    if not stated:
        return Reconciliation(
            may_link=False,
            reason="no passage states this rule in a readable part of a document",
            assessed=assessed,
            concerns=tuple(
                Concern(CHART_ONLY,
                        f"the only passage found for this rule sits inside a "
                        f"figure in {a.source} p.{a.page}, where a reader "
                        f"cannot check it")
                for a in assessed
            ),
        )
    where = ", ".join(f"{a.source} p.{a.page}" for a in stated)
    return Reconciliation(
        may_link=True,
        reason=f"stated in {where}; the claim stays proposed until a check "
               f"tests it or a human confirms it",
        assessed=assessed,
    )


def corroborate(records: list[EvidenceRecord], target: Decimal, *,
                check_supported: bool = False) -> Reconciliation:
    """Value corroboration under the multi-anchor rule.

    ``check_supported`` says a check on this claim already produced the
    same value from the data — the second witness that lets one document
    anchor be enough.
    """
    anchors = anchors_for(records)
    assessed = tuple(assess(r, target) for r in anchors)
    counting = [a for a in assessed if a.counts]
    places = {a.place for a in counting}
    concerns: list[Concern] = []

    restated = [a for a in assessed if len(restated_values(a.quote)) > 1]
    for anchor in restated:
        values = ", ".join(str(v) for v in restated_values(anchor.quote))
        concerns.append(Concern(
            RESTATEMENT,
            f"{anchor.source} p.{anchor.page} gives more than one figure for "
            f"the same thing ({values}) — which one applies is a decision, "
            f"not a calculation",
        ))

    for anchor in assessed:
        if anchor.kind == AnchorKind.CHART.value:
            concerns.append(Concern(
                CHART_ONLY,
                f"the figure in {anchor.source} p.{anchor.page} appears only "
                f"inside a chart, so nothing on the page supports it",
            ))
        elif anchor.match == AnchorMatch.COINCIDENTAL_CANDIDATE.value:
            concerns.append(Concern(
                NO_AGREEMENT,
                f"the figure quoted from {anchor.source} p.{anchor.page} does "
                f"not agree with the value it was offered for",
            ))

    if restated:
        return Reconciliation(
            may_link=False,
            reason="a restatement must be decided by a human, never "
                   "reconciled to one of its figures",
            assessed=assessed,
            concerns=tuple(concerns),
        )
    if len(places) >= 2:
        where = ", ".join(f"{s} p.{p}" for s, p in sorted(places))
        return Reconciliation(
            may_link=True,
            reason=f"{len(places)} independent documents agree ({where})",
            assessed=assessed,
            concerns=tuple(concerns),
        )
    if len(places) == 1 and check_supported:
        source, page = next(iter(places))
        return Reconciliation(
            may_link=True,
            reason=f"{source} p.{page} agrees with what the data produces",
            assessed=assessed,
            concerns=tuple(concerns),
        )
    if len(places) == 1:
        source, page = next(iter(places))
        concerns.append(Concern(
            SINGLE_ANCHOR,
            f"only {source} p.{page} carries this figure, and no check has "
            f"produced it from the data",
        ))
        return Reconciliation(
            may_link=False,
            reason="one document alone does not corroborate a figure",
            assessed=assessed,
            concerns=tuple(concerns),
        )
    return Reconciliation(
        may_link=False,
        reason="nothing found in the documents agrees with this value",
        assessed=assessed,
        concerns=tuple(concerns),
    )
