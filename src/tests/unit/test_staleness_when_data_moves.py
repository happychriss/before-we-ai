"""The check ran on Tuesday. On Wednesday the data changed.

Supersession (``test_staleness.py``) covers the case where *we* produce a
newer reading. This is the other one, and it is the dangerous one: nobody
produces anything, the analyst simply corrects a posting, and every stored
conclusion keeps its confident wording. Status still test-supported,
verdict still ready, and the sentence that proves it quotes a run over
rows that no longer exist.

The store cannot watch a filesystem, so it notices at the one moment it
honestly can: when the sources are read again. What was measured against
the old fingerprints stops counting, the statuses fall back to what the
remaining evidence supports, and the question cards say that the number
they carry is from a reading nobody has taken since.

Flagging is one-way — evidence is append-only and a flag is not un-set by
editing the record. Freshness comes back the way it was earned the first
time: run the check again, find the quote again.
"""

from pathlib import Path

import pytest
import pymupdf
import yaml

from before_we_ai import scan
from before_we_ai.core import Actor, ClaimStatus, EvidenceType, Scope
from before_we_ai.core.objects import (
    CheckPlan,
    Claim,
    ClarificationQuestion,
    EvidenceRecord,
    Predicate,
)
from before_we_ai.documents import read_documents
from before_we_ai.engine import run_ready
from before_we_ai.sources import open_catalog
from before_we_ai.staleness import current_stamps, moved, refresh, why_stale
from before_we_ai.store import ProjectStore, init_project
from before_we_ai.store.proposals import ProposalStore
from readiness_report.projection import build_view_model

pytestmark = pytest.mark.integration

ROWS = [
    "id,amount",
    "a,10.00",
    "b,20.00",
    "c,30.00",
]


def _csv(root: Path, rows: list[str]) -> None:
    (root / "sources" / "ledger.csv").write_text("\n".join(rows) + "\n",
                                                 encoding="utf-8")


def _pdf(path: Path, lines: list[str]) -> None:
    document = pymupdf.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 100 + index * 20), line)
    document.save(str(path))
    document.close()


@pytest.fixture
def project(tmp_path):
    """One CSV, one claim about it, one check that passes over it."""
    root = init_project(tmp_path / "proj")
    _csv(root, ROWS)
    config = yaml.safe_load((root / "before-ai.yaml").read_text())
    config["sources"] = [
        {"name": "ledger", "kind": "csv", "location": "sources/ledger.csv"},
    ]
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    scan(root)

    store = ProjectStore(root)
    claim = store.add_claim(Claim(
        statement="id identifies a row of the ledger",
        predicate=Predicate(name="unique_key",
                            params={"table": "ledger__ledger", "key_columns": ["id"]}),
        created_by=Actor.AI,
    ))
    store.save_check_plan(CheckPlan(
        template="duplicate", claim_id=claim.id,
        params={"table": "ledger__ledger", "key_columns": ["id"]},
    ))
    with open_catalog(root) as con:
        run_ready(ProjectStore(root), con)
    return root, claim.id


def _sweep(root: Path) -> None:
    with open_catalog(root) as con:
        run_ready(ProjectStore(root), con)


def _results(store: ProjectStore) -> list[EvidenceRecord]:
    return [e for e in store.evidence.values()
            if e.type is EvidenceType.CHECK_RESULT]


def _reason_for_the_check(root: Path, report) -> str:
    """A scan flags whatever it outran, and the normalization declaration
    goes with the file. These tests are about the reading of the table."""
    store = ProjectStore(root)
    return next(reason for record_id, reason in report.flagged
                if store.evidence[record_id].type is EvidenceType.CHECK_RESULT)


class TestWhatAScanNotices:
    def test_the_claim_stands_while_the_data_stands(self, project):
        root, claim_id = project
        scan(root)
        store = ProjectStore(root)
        assert store.claims[claim_id].status is ClaimStatus.TEST_SUPPORTED
        assert not any(record.stale for record in _results(store))

    def test_an_edited_value_outruns_the_reading_that_passed(self, project):
        """The case row counts and schemas miss entirely: same rows, same
        columns, one corrected amount. Without a content digest the store
        would report a check over data that no longer exists."""
        root, claim_id = project
        _csv(root, ["id,amount", "a,10.00", "b,99.99", "c,30.00"])

        result = scan(root)

        assert result.stale.flagged
        store = ProjectStore(root)
        assert all(record.stale for record in _results(store))
        assert store.claims[claim_id].status is ClaimStatus.PROPOSED

    def test_the_flag_says_what_moved(self, project):
        root, _claim_id = project
        _csv(root, ["id,amount", "a,10.00", "b,99.99", "c,30.00"])

        reason = _reason_for_the_check(root, scan(root).stale)

        assert reason == 'values in "ledger__ledger" have changed since this ran'

    def test_a_new_row_is_named_as_a_new_row(self, project):
        """Row count first: it is the change a reader can picture."""
        root, _claim_id = project
        _csv(root, [*ROWS, "d,40.00"])

        reason = _reason_for_the_check(root, scan(root).stale)

        assert reason == '"ledger__ledger" had 3 rows when this ran and has 4 now'

    def test_a_scan_over_unchanged_data_flags_nothing_twice(self, project):
        """Idempotence, and the reason it matters: a flag that reappears on
        every scan is a flag a reader learns to ignore."""
        root, _claim_id = project
        _csv(root, [*ROWS, "d,40.00"])
        scan(root)
        _sweep(root)

        assert not scan(root).stale.flagged

    def test_nothing_is_judged_in_a_project_nobody_has_scanned(self, tmp_path):
        """A store that knows of no sources knows nothing about freshness.
        Judging against that emptiness would mark every record stale — the
        loudest possible way to say nothing."""
        store = ProjectStore(init_project(tmp_path / "empty"), create=True)
        claim = store.add_claim(Claim(statement="something", created_by=Actor.AI))
        store.add_evidence(EvidenceRecord(
            type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
            verdict="pass", claim_id=claim.id,
            source_fingerprints={"nowhere": {"kind": "table", "row_count": 7}},
        ))

        assert not refresh(store).flagged


class TestWhatAHumanSaidStaysSaid:
    """Moving data is not an argument. A testimonial expires through a
    check that contradicts it (spec :57) and a business confirmation does
    not lapse from data movement at all — so neither is even offered to
    the comparison."""

    def test_a_testimonial_is_not_touched_by_a_changed_table(self, project):
        root, claim_id = project
        store = ProjectStore(root)
        record = EvidenceRecord(
            type=EvidenceType.TESTIMONIAL, actor=Actor.HUMAN,
            claim_id=claim_id, statement="ids are unique, always have been",
            source_fingerprints={"ledger__ledger": {"kind": "table", "row_count": 3}},
        )
        store.add_evidence(record)

        _csv(root, [*ROWS, "d,40.00"])
        scan(root)

        assert not ProjectStore(root).evidence[record.id].stale

    def test_a_confirmation_is_not_touched_either(self, project):
        root, claim_id = project
        store = ProjectStore(root)
        record = EvidenceRecord(
            type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN,
            claim_id=claim_id, scope=Scope(entity="DE"),
            source_fingerprints={"ledger__ledger": {"kind": "table", "row_count": 3}},
        )
        store.add_evidence(record)

        _csv(root, [*ROWS, "d,40.00"])
        scan(root)

        assert not ProjectStore(root).evidence[record.id].stale


class TestTheOtherHalfIsTheRerun:
    """Flagging alone would be a system that can only ever get less sure.
    What makes it a loop is that running the check again settles it."""

    def test_the_rerun_puts_the_claim_back_on_its_feet(self, project):
        root, claim_id = project
        _csv(root, [*ROWS, "d,40.00"])
        scan(root)
        assert ProjectStore(root).claims[claim_id].status is ClaimStatus.PROPOSED

        _sweep(root)

        assert ProjectStore(root).claims[claim_id].status is ClaimStatus.TEST_SUPPORTED

    def test_the_old_reading_is_kept_and_stays_stale(self, project):
        """One-way by design. The rerun does not rehabilitate the record it
        replaced — it adds the reading somebody actually took."""
        root, _claim_id = project
        _csv(root, [*ROWS, "d,40.00"])
        scan(root)
        _sweep(root)

        results = _results(ProjectStore(root))
        assert sorted(record.stale for record in results) == [False, True]

    def test_data_moving_back_does_not_un_flag_the_old_reading(self, project):
        root, _claim_id = project
        _csv(root, [*ROWS, "d,40.00"])
        scan(root)
        _csv(root, ROWS)
        scan(root)

        assert all(record.stale for record in _results(ProjectStore(root)))

    def test_the_reason_tells_a_replaced_reading_from_an_outrun_one(self, project):
        root, _claim_id = project
        _csv(root, [*ROWS, "d,40.00"])
        scan(root)
        outrun = next(iter(_results(ProjectStore(root))))
        _sweep(root)

        store = ProjectStore(root)
        assert why_stale(store.evidence[outrun.id], store) == (
            "a later run of the same check replaced this reading")


class TestTheQuestionCardSaysSo:
    """A finding is a measurement: "1 exception in 24 rows". When the rows
    have moved, the card is holding up a number from a reading nobody has
    taken since — and a reader deciding what to work on next has to know
    that before they act on it."""

    @pytest.fixture
    def failing(self, project):
        """Break the data so the check fails and drafts a card."""
        root, claim_id = project
        _csv(root, ["id,amount", "a,10.00", "a,20.00", "c,30.00"])
        scan(root)
        _sweep(root)
        return root, claim_id

    def test_the_card_exists_and_carries_its_size(self, failing):
        root, _claim_id = failing
        card = next(iter(ProjectStore(root).questions.values()))
        assert card.finding
        assert not card.stale

    def test_the_card_goes_stale_when_its_finding_is_outrun(self, failing):
        root, _claim_id = failing
        _csv(root, ["id,amount", "a,10.00", "a,20.00", "c,99.99"])

        result = scan(root)

        assert result.stale.questions_flagged
        assert next(iter(ProjectStore(root).questions.values())).stale

    def test_the_rerun_clears_it(self, failing):
        """The acceptance sentence in miniature: flags propagate into the
        cards, and a rerun clears them."""
        root, _claim_id = failing
        _csv(root, ["id,amount", "a,10.00", "a,20.00", "c,99.99"])
        scan(root)

        _sweep(root)

        assert not next(iter(ProjectStore(root).questions.values())).stale

    def test_a_question_about_meaning_is_left_alone(self, failing):
        """Which column is the account is not a question data movement can
        answer, and a card with no check behind it must not wear a flag
        that says a measurement went out of date."""
        root, claim_id = failing
        store = ProjectStore(root)
        role_card = ClarificationQuestion(question="Which column is the account?")
        store.save_question(role_card)

        _csv(root, ["id,amount", "a,10.00", "a,20.00", "c,99.99"])
        scan(root)

        assert not ProjectStore(root).questions[role_card.id].stale


class TestWhatTheReaderIsTold:
    """A flag is bookkeeping. What a reader needs is the sentence: which
    of their tables moved, and what that costs the number in front of
    them."""

    @pytest.fixture
    def report(self, project):
        root, claim_id = project
        _csv(root, ["id,amount", "a,10.00", "a,20.00", "c,30.00"])
        scan(root)
        _sweep(root)                                     # the card appears
        _csv(root, ["id,amount", "a,10.00", "a,20.00", "c,99.99"])
        scan(root)                                       # and is outrun
        store = ProjectStore(root)
        config = yaml.safe_load((root / "before-ai.yaml").read_text())
        return build_view_model(store, root, config), claim_id

    def test_the_evidence_says_why_it_is_stale(self, report):
        model, _claim_id = report
        details = [detail
                   for claim in model.claims
                   for record in claim.evidence
                   for detail in record.details]
        assert ("why stale",
                'values in "ledger__ledger" have changed since this ran') in details

    def test_the_card_no_longer_presents_its_size_as_current(self, report):
        model, _claim_id = report
        card = next(iter(model.open_questions))
        assert card.finding.endswith(
            "— measured before the data moved; nobody has re-run the check since")


class TestAQuoteCanGoSilentlyUntrue:
    """The document half. A policy PDF is replaced by next year's edition;
    the anchor still cites page 2 and the store still shows the sentence.
    Nothing about the claim would have moved."""

    @pytest.fixture
    def documents(self, tmp_path):
        root = init_project(tmp_path / "docs")
        _pdf(root / "sources" / "policy.pdf",
             ["Accounting Policy",
              "Credit amounts are booked as negative numbers."])
        _pdf(root / "sources" / "rebates.pdf",
             ["Master Rebate Agreement",
              "Annual volume above EUR 500,000 earns 2%."])
        config = yaml.safe_load((root / "before-ai.yaml").read_text())
        config["sources"] = [
            {"name": "policy", "kind": "pdf", "location": "sources/policy.pdf"},
            {"name": "rebates", "kind": "pdf", "location": "sources/rebates.pdf"},
        ]
        (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
        read_documents(root)

        store = ProjectStore(root)
        claim = store.add_claim(Claim(
            statement="credits are booked negative", created_by=Actor.AI))
        chunks = _chunks(root)
        chunk = next(c for c in chunks if "negative numbers" in c.text)
        ProposalStore(store).anchor(
            claim.id, quote="Credit amounts are booked as negative numbers.",
            chunk_id=chunk.id, chunk_text=chunk.text, kind=chunk.kind,
            source="policy", page=chunk.page)
        return root, claim.id

    def test_an_untouched_document_leaves_its_anchors_alone(self, documents):
        root, _claim_id = documents
        result = read_documents(root)
        assert not result.stale.flagged
        assert not result.revalidated

    def test_editing_another_document_does_not_reach_this_anchor(self, documents):
        """Per passage, not per project: the stamp is the chunk the quote
        was found in."""
        root, _claim_id = documents
        _pdf(root / "sources" / "rebates.pdf",
             ["Master Rebate Agreement", "Annual volume above EUR 750,000 earns 3%."])

        assert not read_documents(root).stale.flagged

    def test_a_rewritten_passage_flags_the_quote_that_lived_in_it(self, documents):
        root, _claim_id = documents
        _pdf(root / "sources" / "policy.pdf",
             ["Accounting Policy", "Credits are recorded as positive amounts."])

        result = read_documents(root)

        assert result.stale.flagged
        assert not result.revalidated
        store = ProjectStore(root)
        anchors = [e for e in store.evidence.values()
                   if e.type is EvidenceType.DOCUMENT_ANCHOR]
        assert [a.stale for a in anchors] == [True]

    def test_a_surviving_quote_is_picked_back_up_without_a_model(self, documents):
        """The edit touched the passage but not the sentence. Making a human
        re-confirm that, or spending a model call to find it again, would
        be a cost our bookkeeping invented."""
        root, _claim_id = documents
        _pdf(root / "sources" / "policy.pdf",
             ["Accounting Policy (rev. 2)",
              "Credit amounts are booked as negative numbers."])

        result = read_documents(root)

        assert result.revalidated == 1
        store = ProjectStore(root)
        anchors = [e for e in store.evidence.values()
                   if e.type is EvidenceType.DOCUMENT_ANCHOR]
        assert sorted(a.stale for a in anchors) == [False, True]

    def test_the_fresh_anchor_carries_the_new_passage(self, documents):
        root, _claim_id = documents
        _pdf(root / "sources" / "policy.pdf",
             ["Accounting Policy (rev. 2)",
              "Credit amounts are booked as negative numbers."])
        read_documents(root)

        store = ProjectStore(root)
        live = next(e for e in store.evidence.values()
                    if e.type is EvidenceType.DOCUMENT_ANCHOR and not e.stale)
        assert not moved(live, current_stamps(store.sources.values()))


def _chunks(root: Path):
    from before_we_ai.documents.chunk import chunk_pdf
    return chunk_pdf(root / "sources" / "policy.pdf", "policy")
