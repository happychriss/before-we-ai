"""Fixing the data has to be a way forward, not a new kind of stuck.

The report tells a reader, in so many words, that a refuted claim "is not
a missing answer but a wrong one — the data itself has to change". Before
this, taking that advice did not work: the check ran again, the new PASS
was appended, the old FAIL stayed live beside it, and ``resolve_status``
called the pair a conflict. You corrected your books and the system moved
the claim from *contradicted* to *unresolved*.

Evidence stays append-only. Nothing is deleted or rewritten; the earlier
reading is marked **stale**, which is the single mutation the store
permits, and the status derivation stops counting it. Both readings remain
in the trail — what changes is which one describes the data as it is now.
"""

import duckdb
import pytest

from before_we_ai.core import Actor, ClaimStatus, EvidenceType, resolve_status
from before_we_ai.core.objects import CheckPlan, Claim, Predicate
from before_we_ai.engine import run_ready
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.integration


@pytest.fixture
def project(tmp_path):
    """A claim that the data refutes, and the check that says so."""
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    claim = Claim(
        statement="every posting has a counter-posting",
        predicate=Predicate(name="unique_key",
                            params={"table": "ledger", "key_columns": ["id"]}),
        created_by=Actor.AI,
    )
    store.save_claim(claim)
    store.save_check_plan(CheckPlan(
        template="duplicate", claim_id=claim.id,
        params={"table": "ledger", "key_columns": ["id"]},
    ))
    con = duckdb.connect()
    # Two rows share an id: the claim is false as the data stands. The view
    # is what the check reads, so the fix below edits the table under it.
    con.execute("CREATE TABLE postings (id VARCHAR)")
    con.execute("INSERT INTO postings VALUES ('a'), ('a'), ('b')")
    con.execute('CREATE VIEW "ledger" AS SELECT * FROM postings')
    return ProjectStore(store.root), con, claim.id


def _results(store):
    return [e for e in store.evidence.values()
            if e.type is EvidenceType.CHECK_RESULT]


def test_the_data_refutes_the_claim_to_begin_with(project):
    store, con, claim_id = project
    run_ready(store, con)
    store = ProjectStore(store.root)
    assert store.claims[claim_id].status is ClaimStatus.CONTRADICTED


def test_fixing_the_data_settles_the_claim_rather_than_confusing_it(project):
    """The whole point. Before, this landed on unresolved."""
    store, con, claim_id = project
    run_ready(store, con)

    con.execute("DELETE FROM postings WHERE rowid = 0")  # the duplicate goes
    store = ProjectStore(store.root)
    run_ready(store, con)

    store = ProjectStore(store.root)
    assert store.claims[claim_id].status is ClaimStatus.TEST_SUPPORTED


def test_the_earlier_reading_is_kept_and_marked_stale(project):
    """Append-only: nothing is deleted, and the trail still shows both."""
    store, con, _claim_id = project
    run_ready(store, con)
    store = ProjectStore(store.root)
    run_ready(store, con)

    store = ProjectStore(store.root)
    results = _results(store)
    assert len(results) == 2
    assert sorted(e.stale for e in results) == [False, True]


def test_only_the_live_reading_decides_the_status(project):
    store, con, claim_id = project
    run_ready(store, con)
    store = ProjectStore(store.root)
    run_ready(store, con)

    store = ProjectStore(store.root)
    claim = store.claims[claim_id]
    evidence = store.evidence_for(claim)
    assert resolve_status(claim, evidence) is claim.status


def test_a_rerun_over_unchanged_data_does_not_pile_up_live_evidence(project):
    """Running twice used to double the live trail — 49 results became 98,
    and the claim's status became a conflict with itself."""
    store, con, _claim_id = project
    for _ in range(3):
        store = ProjectStore(store.root)
        run_ready(store, con)

    store = ProjectStore(store.root)
    live = [e for e in _results(store) if not e.stale]
    assert len(live) == 1
    assert len(_results(store)) == 3


def test_a_second_plan_on_the_same_claim_is_not_superseded(project):
    """Only *this* plan's earlier runs go stale. Two different checks on one
    claim are two different readings, and both stay live."""
    store, con, claim_id = project
    store.save_check_plan(CheckPlan(
        template="grain", claim_id=claim_id,
        params={"table": "ledger", "key_columns": ["id"]},
    ))
    store = ProjectStore(store.root)
    run_ready(store, con)

    store = ProjectStore(store.root)
    live = [e for e in _results(store) if not e.stale]
    assert len({e.check_plan_id for e in live}) == 2


class TestTheQuestionCarriesItsSize:
    """"They do not agree" is one row in twenty-four or two in five, and
    those are different decisions. A question a reader cannot triage is a
    question that sits in the list."""

    def test_a_failed_check_says_how_big_the_problem_is(self, project):
        store, con, _claim_id = project
        run_ready(store, con)
        store = ProjectStore(store.root)
        card = next(iter(store.questions.values()))
        assert card.finding == "1 exception in 3 rows (33.3%)"

    def test_the_size_is_not_part_of_the_question_s_identity(self, project):
        """The trap this avoids. dedup_key() is the wording, so a count
        inside it would mint a fresh card every time the number moved and
        put one decision in front of the reader again and again."""
        store, con, _claim_id = project
        run_ready(store, con)
        store = ProjectStore(store.root)
        card = next(iter(store.questions.values()))
        assert card.finding not in card.question
        assert card.dedup_key() == (card.question, "")

    def test_a_rerun_updates_the_size_on_the_same_card(self, project):
        """Same decision, new measurement — not a second question."""
        store, con, _claim_id = project
        run_ready(store, con)
        store = ProjectStore(store.root)
        before = next(iter(store.questions.values()))

        con.execute("INSERT INTO postings VALUES ('b')")  # a second duplicate
        store = ProjectStore(store.root)
        run_ready(store, con)

        store = ProjectStore(store.root)
        assert len(store.questions) == 1
        after = next(iter(store.questions.values()))
        assert after.id == before.id
        assert after.finding != before.finding
