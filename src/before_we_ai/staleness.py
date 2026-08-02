"""Data moves. What was read against it does not follow by itself.

A check ran on Tuesday and passed. On Wednesday somebody corrects a
posting. Nothing in the store notices: the claim still says
*test-supported*, the readiness verdict still says ready, and the sentence
that proves it quotes a run over data that no longer exists. That is the
one failure mode this product cannot have — a wrong answer delivered
confidently, produced not by a model but by bookkeeping that stopped
looking.

Every record that rests on data carries the fingerprints of what it read
(`sources/fingerprint.py`). This module is the reader of those stamps:
compare what a record recorded against what the sources look like now, and
mark the ones whose ground has moved. ``resolve_status`` already stops
counting stale evidence, so the flag is all it takes for the status, the
readiness map and the verdict to tell the truth again.

**Stale is one-way.** Evidence is append-only; the single permitted
mutation sets the flag, and nothing clears it. Freshness is not restored
by editing an old record but by producing a new one — re-run the check,
re-validate the anchor. If the data moves back to where it was, the old
record still describes a reading nobody took again; the new one describes
the reading somebody did. Question cards are not evidence and do behave
both ways: a card is stale while nothing live backs its finding, and a
re-run that produces a live result clears it.

**What data movement may not touch.** Testimonials and confirmations carry
no source fingerprints and are deliberately excluded here rather than
accidentally spared by an empty dict. What a human said stays said when a
table changes; a testimonial expires only through a check that contradicts
it (spec :57), and a business confirmation never lapses from data moving
at all. Moving data is not an argument.
"""

from dataclasses import dataclass, field

from before_we_ai.core.enums import EvidenceType
from before_we_ai.core.objects import EvidenceRecord, Source
from before_we_ai.core.transitions import resolve_status
from before_we_ai.store.repository import ProjectStore

#: The kinds of evidence that rest on data and can therefore be outrun by
#: it. Everything else is a human's word — see the module docstring.
RESTS_ON_DATA = (
    EvidenceType.CHECK_RESULT,
    EvidenceType.DECLARATION,
    EvidenceType.DOCUMENT_ANCHOR,
)


@dataclass(frozen=True)
class Stamps:
    """What the declared sources look like *now*, in the three shapes a
    record can have stamped: whole files, analysis views, document chunks.

    Built from the Source records, which ``scan`` and ``read_documents``
    refresh on every pass — so "now" means "as of the last time anybody
    looked", which is the only honest meaning available to a store that
    does not watch the filesystem.
    """

    views: dict[str, dict] = field(default_factory=dict)   # view -> table fp
    files: dict[str, dict] = field(default_factory=dict)   # source -> file fp
    chunks: dict[str, dict] = field(default_factory=dict)  # source -> {chunk: digest}


def current_stamps(sources) -> Stamps:
    stamps = Stamps()
    for source in sources:
        fingerprint = source.fingerprint or {}
        if fingerprint.get("file"):
            stamps.files[source.name] = fingerprint["file"]
        for view, table in (fingerprint.get("tables") or {}).items():
            stamps.views[view] = table
        if fingerprint.get("chunks"):
            stamps.chunks[source.name] = fingerprint["chunks"]
    return stamps


def _file_moved(name: str, recorded: object, current: dict | None) -> str | None:
    if current is None:
        return None  # nothing to compare — see `moved`
    was = recorded.get("sha256") if isinstance(recorded, dict) else recorded
    if was and was != current.get("sha256"):
        return f"the file behind {name} has changed"
    return None


def _chunk_moved(name: str, recorded: dict, current: dict | None) -> str | None:
    if current is None:
        return None  # nothing to compare — see `moved`
    chunk_id = recorded.get("chunk_id")
    now = current.get(chunk_id)
    if now is None:
        return f"the passage {chunk_id} is no longer in {name}"
    if recorded.get("sha256") and recorded["sha256"] != now:
        return f"the passage {chunk_id} in {name} has been rewritten"
    return None


def _table_moved(view: str, recorded: dict, current: dict | None) -> str | None:
    """The comparison in the order a reader wants to hear it: the biggest
    change first, so the sentence names the reason rather than a symptom.

    A field the record does not carry is not compared. A store written
    before a fingerprint gained a field must not read as stale in bulk the
    day the field is added — that would be a flag nobody can act on.
    """
    if current is None:
        return None  # nothing to compare — see `moved`
    if recorded.get("schema_hash") and recorded["schema_hash"] != current.get("schema_hash"):
        return f'the columns of "{view}" have changed'
    if (recorded.get("row_count") is not None
            and recorded["row_count"] != current.get("row_count")):
        return (f'"{view}" had {recorded["row_count"]:,} rows when this ran '
                f'and has {current.get("row_count", 0):,} now')
    if recorded.get("content_hash") and recorded["content_hash"] != current.get("content_hash"):
        return f'values in "{view}" have changed since this ran'
    if recorded.get("max_date") and recorded["max_date"] != current.get("max_date"):
        return (f'"{view}" now carries data up to {current.get("max_date")}, '
                f'not {recorded["max_date"]}')
    return None


def moved(record: EvidenceRecord, stamps: Stamps) -> str | None:
    """Why this record no longer describes the data — or None if it still does.

    A stamp with nothing to compare against is not judged — neither a
    record without fingerprints nor one naming a source the store does not
    know. That is not indulgence: a project nobody has scanned yet knows
    of no sources at all, and judging against that emptiness would mark
    every record in it stale, which is a flag nobody can act on. A source
    that really was withdrawn is a change to the *declaration*, and it
    surfaces where declarations do — stage 0 lists it as gone and its
    checks skip for want of a view.
    """
    if record.type not in RESTS_ON_DATA:
        return None
    for name, recorded in (record.source_fingerprints or {}).items():
        kind = recorded.get("kind") if isinstance(recorded, dict) else "file"
        if kind == "table":
            reason = _table_moved(name, recorded, stamps.views.get(name))
        elif kind == "chunk":
            reason = _chunk_moved(name, recorded, stamps.chunks.get(name))
        else:
            reason = _file_moved(name, recorded, stamps.files.get(name))
        if reason:
            return reason
    return None


def why_stale(record: EvidenceRecord, store: ProjectStore,
              stamps: Stamps | None = None) -> str:
    """The reason a stale record is stale, derived rather than stored.

    Two things set the flag and a reader needs to tell them apart: a later
    run of the same check plan replaced this reading, or the data it read
    moved. Neither is written down — the first is visible in the trail,
    the second in the fingerprints, and deriving both keeps the record
    itself immutable.
    """
    if not record.stale:
        return ""
    if record.check_plan_id and any(
        other.check_plan_id == record.check_plan_id
        and other.id != record.id
        and not other.stale
        for other in store.evidence.values()
    ):
        return "a later run of the same check replaced this reading"
    reason = moved(record, stamps or current_stamps(store.sources.values()))
    if reason:
        return reason
    # Flagged, but nothing on record says why any more — the data moved and
    # then moved back, or a later reading was itself superseded. Saying so
    # is better than inventing the more interesting of the two.
    return "the data this read has moved on since"


@dataclass
class StalenessReport:
    """What one refresh changed, in the words the walkthrough prints."""

    flagged: list[tuple[str, str]] = field(default_factory=list)  # (id, reason)
    claims_rederived: list[str] = field(default_factory=list)
    questions_flagged: list[str] = field(default_factory=list)
    questions_cleared: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.flagged or self.claims_rederived
                    or self.questions_flagged or self.questions_cleared)


def refresh(store: ProjectStore, sources: list[Source] | None = None) -> StalenessReport:
    """Compare every live record against the sources as they are now.

    Called at the end of the seams where the answer can change: after a
    scan or a document read (the sources moved) and after a check sweep
    (a new reading arrived). It is idempotent — running it twice over
    unchanged data flags nothing the second time.
    """
    stamps = current_stamps(sources if sources is not None else store.sources.values())
    report = StalenessReport()

    for record in list(store.evidence.values()):
        if record.stale:
            continue
        reason = moved(record, stamps)
        if reason:
            store.mark_evidence_stale(record.id)
            report.flagged.append((record.id, reason))

    if report.flagged:
        report.claims_rederived = _rederive(store, {rid for rid, _ in report.flagged})
    refresh_questions(store, report)
    return report


def _rederive(store: ProjectStore, flagged: set[str]) -> list[str]:
    """A claim's stored status is a cached rendering of its evidence.

    The cache is what the scheduler reads to decide whether a dependent
    check may run, so leaving it behind a flag would let a check run on a
    prerequisite that is no longer supported. Only claims that actually
    touch a flagged record are re-derived.
    """
    changed = []
    for claim in list(store.claims.values()):
        if not flagged.intersection(claim.evidence_ids):
            continue
        status = resolve_status(claim, store.evidence_for(claim))
        if status is not claim.status:
            store.save_claim(claim.model_copy(update={"status": status}))
            changed.append(claim.id)
    return changed


def refresh_questions(
    store: ProjectStore, report: StalenessReport | None = None
) -> StalenessReport:
    """A card is stale while nothing live backs the finding it reports.

    The finding — "1 exception in 24 rows" — came from a check run. When
    every check result behind the card's claims is stale, the number in
    front of the reader describes data nobody has looked at since, and the
    card says so rather than quietly keeping it. A card whose claims never
    had a check result is untouched: it is a question about meaning, and
    data moving is not an answer to it.

    Public and separate from ``refresh`` because a check sweep needs this
    half alone. A sweep reads the data directly and may well run against
    data the Source records have not caught up with — judging fingerprints
    at that moment would mark the sweep's own fresh results as stale. What
    a sweep *can* settle is which cards have a live reading behind them
    again, and that is decided in the store, without a fingerprint.
    """
    report = report if report is not None else StalenessReport()
    for card in list(store.questions.values()):
        results = [
            record
            for claim_id in card.claim_ids
            if (claim := store.claims.get(claim_id))
            for record in store.evidence_for(claim)
            if record.type is EvidenceType.CHECK_RESULT
        ]
        if not results:
            continue
        stale = all(record.stale for record in results)
        if stale == card.stale:
            continue
        store.save_question(card.model_copy(update={"stale": stale}))
        (report.questions_flagged if stale else report.questions_cleared).append(card.id)
    return report
