"""Engine: gating, claim status wiring, store persistence, integrity."""

import duckdb
import pytest

from before_we_ai.engine import run_probe, run_ready
from before_we_ai.model import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    Probe,
    ProbeVerdict,
    create_claim,
)
from before_we_ai.store import ProjectStore, check_integrity


@pytest.fixture
def con():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (id BIGINT)")
    con.execute("INSERT INTO t VALUES (1), (2), (2)")
    return con


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "proj", create=True)


def test_probe_run_updates_claim_status(store, con):
    claim = store.add_claim(create_claim("t.id is unique", Actor.AI))
    probe = Probe(template="duplicate", claim_id=claim.id,
                  params={"table": "t", "key_columns": ["id"]})
    record = run_probe(store, con, probe)
    assert record.verdict is ProbeVerdict.FAIL
    assert store.claims[claim.id].status is ClaimStatus.CONTRADICTED
    assert record.id in store.claims[claim.id].evidence_ids
    assert check_integrity(store) == []


def test_run_ready_gates_on_dependencies(store, con):
    base = store.add_claim(create_claim("base rule", Actor.AI))
    dependent = store.add_claim(
        create_claim("depends on base", Actor.AI, depends_on=[base.id])
    )
    store.save_probe(Probe(template="grain", claim_id=dependent.id,
                           params={"table": "t", "key_columns": ["id"]}))
    report = run_ready(store, con)
    assert report.executed == []
    assert report.skipped == [(next(iter(store.probes)), "prerequisites not tested yet")]

    # Base gets tested -> the gate opens on the next sweep.
    ok = EvidenceRecord(type=EvidenceType.PROBE_RESULT, actor=Actor.PROBE,
                        verdict=ProbeVerdict.PASS, claim_id=base.id)
    store.add_evidence(ok)
    from before_we_ai.model.transitions import attach_evidence
    store.save_claim(attach_evidence(base, ok, []))
    report = run_ready(store, con)
    assert len(report.executed) == 1
    assert report.skipped == []


def test_run_ready_orders_probes_topologically(store, con):
    upstream = store.add_claim(create_claim("upstream: t.id unique... not", Actor.AI))
    downstream = store.add_claim(
        create_claim("downstream", Actor.AI, depends_on=[upstream.id])
    )
    store.save_probe(Probe(template="grain", claim_id=downstream.id,
                           params={"table": "t", "key_columns": ["id"]}))
    store.save_probe(Probe(template="duplicate", claim_id=upstream.id,
                           params={"table": "t", "key_columns": ["id"]}))
    report = run_ready(store, con)
    # Upstream ran first, FAILED -> downstream stayed gated in the same sweep.
    assert len(report.executed) == 1
    assert report.executed[0].claim_id == upstream.id
    assert [reason for _, reason in report.skipped] == ["prerequisites not tested yet"]


def test_probes_round_trip_and_integrity(store, con, tmp_path):
    claim = store.add_claim(create_claim("rule", Actor.AI))
    probe = Probe(template="duplicate", claim_id=claim.id,
                  params={"table": "t", "key_columns": ["id"]})
    run_probe(store, con, probe)

    reloaded = ProjectStore(store.root)
    assert reloaded.probes[probe.id].params == probe.params
    assert check_integrity(reloaded) == []

    # Dangling probe reference is a finding.
    orphan = EvidenceRecord(type=EvidenceType.PROBE_RESULT, actor=Actor.PROBE,
                            verdict=ProbeVerdict.PASS, probe_id="01XXXXXXXXXXXXXXXXXXXXXXXX")
    reloaded.add_evidence(orphan)
    assert any("dangling probe reference" in f for f in check_integrity(reloaded))
