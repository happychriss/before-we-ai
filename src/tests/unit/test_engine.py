"""Engine: gating, claim status wiring, store persistence, integrity."""

import duckdb

import pytest

from before_we_ai.engine import run_check, run_ready
from before_we_ai.core import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    CheckPlan,
    CheckVerdict,
    create_claim,
)
from before_we_ai.store import ProjectStore, check_integrity

pytestmark = pytest.mark.integration


@pytest.fixture
def con():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (id BIGINT)")
    con.execute("INSERT INTO t VALUES (1), (2), (2)")
    return con


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "proj", create=True)


def test_check_run_updates_claim_status(store, con):
    claim = store.add_claim(create_claim("t.id is unique", Actor.AI))
    check = CheckPlan(template="duplicate", claim_id=claim.id,
                  params={"table": "t", "key_columns": ["id"]})
    record = run_check(store, con, check)
    assert record.verdict is CheckVerdict.FAIL
    assert store.claims[claim.id].status is ClaimStatus.CONTRADICTED
    assert record.id in store.claims[claim.id].evidence_ids
    assert check_integrity(store) == []


def test_run_ready_gates_on_dependencies(store, con):
    base = store.add_claim(create_claim("base rule", Actor.AI))
    dependent = store.add_claim(
        create_claim("depends on base", Actor.AI, depends_on=[base.id])
    )
    store.save_check_plan(CheckPlan(template="grain", claim_id=dependent.id,
                           params={"table": "t", "key_columns": ["id"]}))
    report = run_ready(store, con)
    assert report.executed == []
    assert report.skipped == [(next(iter(store.checks)), "prerequisites not tested yet")]

    # Base gets tested -> the gate opens on the next sweep.
    ok = EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
                        verdict=CheckVerdict.PASS, claim_id=base.id)
    store.add_evidence(ok)
    from before_we_ai.core.transitions import attach_evidence
    store.save_claim(attach_evidence(base, ok, []))
    report = run_ready(store, con)
    assert len(report.executed) == 1
    assert report.skipped == []


def test_run_ready_orders_checks_topologically(store, con):
    upstream = store.add_claim(create_claim("upstream: t.id unique... not", Actor.AI))
    downstream = store.add_claim(
        create_claim("downstream", Actor.AI, depends_on=[upstream.id])
    )
    store.save_check_plan(CheckPlan(template="grain", claim_id=downstream.id,
                           params={"table": "t", "key_columns": ["id"]}))
    store.save_check_plan(CheckPlan(template="duplicate", claim_id=upstream.id,
                           params={"table": "t", "key_columns": ["id"]}))
    report = run_ready(store, con)
    # Upstream ran first, FAILED -> downstream stayed gated in the same sweep.
    assert len(report.executed) == 1
    assert report.executed[0].claim_id == upstream.id
    assert [reason for _, reason in report.skipped] == ["prerequisites not tested yet"]


def test_checks_round_trip_and_integrity(store, con, tmp_path):
    claim = store.add_claim(create_claim("rule", Actor.AI))
    check = CheckPlan(template="duplicate", claim_id=claim.id,
                  params={"table": "t", "key_columns": ["id"]})
    run_check(store, con, check)

    reloaded = ProjectStore(store.root)
    assert reloaded.checks[check.id].params == check.params
    assert check_integrity(reloaded) == []

    # Dangling check reference is a finding.
    orphan = EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK,
                            verdict=CheckVerdict.PASS, check_plan_id="01XXXXXXXXXXXXXXXXXXXXXXXX")
    reloaded.add_evidence(orphan)
    assert any("dangling check reference" in f for f in check_integrity(reloaded))


class TestACheckThatTestedNothingHasNotPassed:
    """"No violations" among no rows is not a finding.

    Every exception-counting check passes on zero rows, and a pass promotes.
    The model writes the filter, so without this it could promote its own
    claim by choosing a filter that selects nothing.
    """

    @pytest.fixture
    def ledgers(self):
        con = duckdb.connect()
        con.execute("CREATE TABLE a (grp VARCHAR, amount DOUBLE)")
        con.execute("CREATE TABLE b (grp VARCHAR, amount DOUBLE)")
        con.execute("INSERT INTO a VALUES ('x', 10), ('y', 5)")
        con.execute("INSERT INTO b VALUES ('x', 999), ('y', 5)")
        return con

    def _reconcile(self, store, con, **filters):
        claim = store.add_claim(create_claim("a reconciles with b", Actor.AI))
        check = CheckPlan(template="reconciliation", claim_id=claim.id, params={
            "left": "a", "right": "b",
            "left_group_expr": "grp", "right_group_expr": "grp",
            "left_measure_expr": "amount", "right_measure_expr": "amount",
            **filters})
        return run_check(store, con, check), claim.id

    def test_unfiltered_the_disagreement_is_found(self, store, ledgers):
        record, claim_id = self._reconcile(store, ledgers)
        assert record.verdict is CheckVerdict.FAIL
        assert store.claims[claim_id].status is ClaimStatus.CONTRADICTED

    def test_a_filter_that_selects_nothing_does_not_promote(self, store, ledgers):
        record, claim_id = self._reconcile(
            store, ledgers, left_where="grp = 'nobody'",
            right_where="grp = 'nobody'")
        assert record.verdict is CheckVerdict.INCONCLUSIVE
        assert "nothing was tested" in record.payload["summary"]
        assert store.claims[claim_id].status is ClaimStatus.PROPOSED

    def test_a_filter_that_keeps_rows_still_passes_and_says_how_many(
            self, store, ledgers):
        record, claim_id = self._reconcile(
            store, ledgers, left_where="grp = 'y'", right_where="grp = 'y'")
        assert record.verdict is CheckVerdict.PASS
        assert store.claims[claim_id].status is ClaimStatus.TEST_SUPPORTED
        assert [(t["view"], t["filter"], t["rows"], t["of"])
                for t in record.payload["tested"]] == [
            ("a", "grp = 'y'", 1, 2), ("b", "grp = 'y'", 1, 2)]

    def test_a_filtered_pass_writes_its_limit_onto_the_claim(
            self, store, ledgers):
        """The test got narrower; the claim has to say so too, or a reader
        of the claim list sees an unqualified statement marked supported."""
        _, claim_id = self._reconcile(
            store, ledgers, left_where="grp = 'y'", right_where="grp = 'y'")
        assert store.claims[claim_id].open_assumptions == [
            "holds only where grp = 'y' — tested on 1 of 2 rows of a",
            "holds only where grp = 'y' — tested on 1 of 2 rows of b",
        ]

    def test_an_unfiltered_pass_carries_no_such_limit(self, store, ledgers):
        ledgers.execute("UPDATE b SET amount = 10 WHERE grp = 'x'")
        record, claim_id = self._reconcile(store, ledgers)
        assert record.verdict is CheckVerdict.PASS
        assert store.claims[claim_id].open_assumptions == []

    def test_a_measure_nobody_could_read_is_not_a_disagreement(self, store):
        """A column of formulas with no stored value arrives as NULLs.
        Setting a real total against that is not a contradiction."""
        con = duckdb.connect()
        con.execute("CREATE TABLE ledger (grp VARCHAR, amount DOUBLE)")
        con.execute("CREATE TABLE summary_sheet (grp VARCHAR, total DOUBLE)")
        con.execute("INSERT INTO ledger VALUES ('x', 10), ('y', 5)")
        con.execute("INSERT INTO summary_sheet VALUES ('x', NULL), ('y', NULL)")
        claim = store.add_claim(create_claim("pivot equals ledger", Actor.AI))
        record = run_check(store, con, CheckPlan(
            template="reconciliation", claim_id=claim.id, params={
                "left": "ledger", "right": "summary_sheet",
                "left_group_expr": "grp", "right_group_expr": "grp",
                "left_measure_expr": "amount", "right_measure_expr": "total"}))
        assert record.verdict is CheckVerdict.INCONCLUSIVE
        assert "is empty in every row of summary_sheet" in record.payload["summary"]
        assert store.claims[claim.id].status is ClaimStatus.PROPOSED


def test_a_check_that_cannot_run_says_so_on_the_claim(store, con):
    """Listed in the sweep's report and nowhere else, a crashed check left
    its claim looking as if nobody had tried."""
    claim = store.add_claim(create_claim("t reconciles with itself", Actor.AI))
    store.save_check_plan(CheckPlan(
        template="duplicate", claim_id=claim.id,
        params={"table": "t", "key_columns": ["no_such_column"]}))
    report = run_ready(store, con)
    assert len(report.skipped) == 1
    [record] = store.evidence_for(store.claims[claim.id])
    assert record.verdict is CheckVerdict.INCONCLUSIVE
    assert record.payload["could_not_run"] is True
    assert "could not run" in record.payload["summary"]
    assert store.claims[claim.id].status is ClaimStatus.PROPOSED

    def test_an_empty_table_does_not_promote(self, store):
        con = duckdb.connect()
        con.execute("CREATE TABLE t (id BIGINT)")
        claim = store.add_claim(create_claim("t.id is unique", Actor.AI))
        record = run_check(store, con, CheckPlan(
            template="duplicate", claim_id=claim.id,
            params={"table": "t", "key_columns": ["id"]}))
        assert record.verdict is CheckVerdict.INCONCLUSIVE
        assert store.claims[claim.id].status is ClaimStatus.PROPOSED
