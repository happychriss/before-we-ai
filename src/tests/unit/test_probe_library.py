"""Templates and verdict functions on small synthetic tables."""

import duckdb
import pytest

from before_we_ai.model.enums import ProbeVerdict
from before_we_ai.model.objects import Probe
from before_we_ai.probes import REGISTRY
from before_we_ai.probes.verdicts import (
    anti_join_verdict,
    cardinality_verdict,
    coverage_verdict,
    empty_expected,
    report_only,
)
from before_we_ai.engine.runner import run_probe
from before_we_ai.store import ProjectStore


@pytest.fixture
def con():
    con = duckdb.connect()
    con.execute("CREATE TABLE parents (id BIGINT, name VARCHAR)")
    con.executemany("INSERT INTO parents VALUES (?, ?)", [(i, f"P{i}") for i in range(1, 6)])
    con.execute("CREATE TABLE children (ref VARCHAR, period VARCHAR)")
    con.executemany(
        "INSERT INTO children VALUES (?, ?)",
        [("1", "2024-01"), ("2", "2024-01"), ("9", "2024-02"), ("9", "2024-03")],
    )
    return con


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "proj", create=True)


def run(store, con, template, params, tolerances=None):
    return run_probe(store, con, Probe(template=template, params=params), tolerances)


class TestVerdictFunctions:
    def test_empty_expected(self):
        assert empty_expected([], [], {}).verdict is ProbeVerdict.PASS
        assert empty_expected([(1,)], [], {}).verdict is ProbeVerdict.FAIL

    def test_report_only_never_fails(self):
        # K6: legitimate orphans are a finding, structurally never FAIL.
        assert report_only([], [], {}).verdict is ProbeVerdict.PASS
        assert report_only([(1,)] * 500, [], {}).verdict is ProbeVerdict.INCONCLUSIVE

    def test_anti_join_dispatch(self):
        assert anti_join_verdict([(1,)], [], {"expectation": "empty"}).verdict is ProbeVerdict.FAIL
        assert (
            anti_join_verdict([(1,)], [], {"expectation": "report"}).verdict
            is ProbeVerdict.INCONCLUSIVE
        )

    def test_coverage_grades(self):
        ctx = {"expected_count": 4}
        assert coverage_verdict([], [], ctx).verdict is ProbeVerdict.PASS
        assert coverage_verdict([(1,)], [], ctx).verdict is ProbeVerdict.INCONCLUSIVE
        assert coverage_verdict([(1,)] * 4, [], ctx).verdict is ProbeVerdict.FAIL

    def test_cardinality_thresholds(self):
        cols = ["child_distinct", "parent_distinct", "parent_rows", "overlap"]
        ctx = {"min_containment": 0.95, "min_uniqueness": 0.99}
        good = cardinality_verdict([(10, 100, 100, 10)], cols, ctx)
        assert good.verdict is ProbeVerdict.PASS
        fanout = cardinality_verdict([(2, 600, 4000, 2)], cols, ctx)  # T6 shape
        assert fanout.verdict is ProbeVerdict.FAIL
        assert "uniqueness" in fanout.summary


class TestProbeRuns:
    def test_anti_join_fail_and_artifacts(self, store, con):
        record = run(store, con, "anti_join", {
            "child": "children", "child_column": "ref",
            "parent": "parents", "parent_column": "id",
        })
        assert record.verdict is ProbeVerdict.FAIL
        assert record.population == 4
        assert record.exception_count == 1  # '9' as a group
        assert record.exception_samples[0]["value"] == "9"
        assert record.probe_id in store.probes  # probe persisted with the run
        assert "SELECT" in record.payload["sql"]
        assert set(record.source_fingerprints) == {"children", "parents"}
        assert (store.root / record.result_ref).is_file()

    def test_anti_join_without_canonicalization_fails_on_types(self, store, con):
        # T1's lesson: raw text rendering of BIGINT vs VARCHAR diverges.
        ok = run(store, con, "anti_join", {
            "child": "children", "child_column": "ref",
            "parent": "parents", "parent_column": "id",
        })
        assert ok.exception_count == 1  # only the genuinely missing '9'
        con.execute("CREATE TABLE parents_dbl AS SELECT CAST(id AS DOUBLE) AS id FROM parents")
        raw = run(store, con, "anti_join", {
            "child": "children", "child_column": "ref",
            "parent": "parents_dbl", "parent_column": "id", "canonical": False,
        })
        assert raw.exception_count == 3  # '1'/'2' no longer match '1.0'/'2.0'

    def test_report_expectation_drafts_question(self, store, con):
        record = run(store, con, "anti_join", {
            "child": "children", "child_column": "ref",
            "parent": "parents", "parent_column": "id", "expectation": "report",
        })
        assert record.verdict is ProbeVerdict.INCONCLUSIVE
        assert len(store.questions) == 1
        question = next(iter(store.questions.values()))
        assert "children" in question.question
        # Re-running the same probe shape does not duplicate the Fachfrage.
        run(store, con, "anti_join", {
            "child": "children", "child_column": "ref",
            "parent": "parents", "parent_column": "id", "expectation": "report",
        })
        assert len(store.questions) == 1

    def test_duplicate_and_grain(self, store, con):
        dup = run(store, con, "duplicate", {"table": "children", "key_columns": ["ref"]})
        assert dup.verdict is ProbeVerdict.FAIL  # '9' twice
        clean = run(store, con, "grain", {"table": "parents", "key_columns": ["id"]})
        assert clean.verdict is ProbeVerdict.PASS

    def test_coverage(self, store, con):
        partial = run(store, con, "coverage", {
            "table": "children", "unit_column": "period",
            "expected": ["2024-01", "2024-02", "2024-03", "2024-04"],
        })
        assert partial.verdict is ProbeVerdict.INCONCLUSIVE
        assert partial.exception_samples == [{"missing_unit": "2024-04"}]

    def test_tolerance_override_comes_from_config_only(self, store, con):
        con.execute("CREATE TABLE l (grp VARCHAR, amount DOUBLE)")
        con.execute("INSERT INTO l VALUES ('a', 100.0)")
        con.execute("CREATE TABLE r (grp VARCHAR, amount DOUBLE)")
        con.execute("INSERT INTO r VALUES ('a', 60.0)")
        params = {
            "left": "l", "right": "r",
            "left_group_expr": '"grp"', "right_group_expr": '"grp"',
            "left_measure_expr": '"amount"', "right_measure_expr": '"amount"',
        }
        assert run(store, con, "reconciliation", params).verdict is ProbeVerdict.FAIL
        tolerant = run(
            store, con, "reconciliation", params,
            tolerances={"reconciliation": {"absolute": 50.0}},
        )
        assert tolerant.verdict is ProbeVerdict.PASS

    def test_unknown_template_raises(self, store, con):
        with pytest.raises(ValueError, match="unknown probe template"):
            run(store, con, "clairvoyance", {})

    def test_illegal_identifier_raises(self, store, con):
        with pytest.raises(ValueError, match="illegal identifier"):
            run(store, con, "duplicate", {"table": 'x" --', "key_columns": ["id"]})


def test_every_registry_entry_has_a_template_file():
    from importlib import resources
    files = {f.name for f in resources.files("before_we_ai.probes").joinpath("templates").iterdir()}
    for name, spec in REGISTRY.items():
        assert spec.file in files, name
