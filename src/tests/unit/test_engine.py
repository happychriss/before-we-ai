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
        assert record.payload["tested"] == [
            {"view": "a", "filter": "grp = 'y'", "rows": 1, "of": 2},
            {"view": "b", "filter": "grp = 'y'", "rows": 1, "of": 2},
        ]

    def test_an_empty_table_does_not_promote(self, store):
        con = duckdb.connect()
        con.execute("CREATE TABLE t (id BIGINT)")
        claim = store.add_claim(create_claim("t.id is unique", Actor.AI))
        record = run_check(store, con, CheckPlan(
            template="duplicate", claim_id=claim.id,
            params={"table": "t", "key_columns": ["id"]}))
        assert record.verdict is CheckVerdict.INCONCLUSIVE
        assert store.claims[claim.id].status is ClaimStatus.PROPOSED
