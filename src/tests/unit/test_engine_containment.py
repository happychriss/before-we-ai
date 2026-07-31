"""One malformed check must not kill the sweep (M4: checks may be AI-bound).

An execution error is contained into RunReport.skipped with the error as
reason — no evidence written, the claim untouched, the remaining checks
still run. Visibility instead of a crash; never a judgment."""

import duckdb

from before_we_ai.engine import run_ready
from before_we_ai.model import Actor, ClaimStatus, create_claim
from before_we_ai.model.objects import Predicate, CheckPlan
from before_we_ai.store import ProjectStore, init_project


def test_execution_error_is_contained_and_the_sweep_continues(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    con = duckdb.connect()
    con.execute("CREATE TABLE j (doc VARCHAR, amount DOUBLE)")
    con.execute("INSERT INTO j VALUES ('D1', 5.0), ('D1', -5.0)")

    claim = create_claim("journal balances per document", Actor.AI,
                         predicate=Predicate(name="balances",
                                             params={"journal": "j"}))
    store.add_claim(claim)
    broken = CheckPlan(template="balance", claim_id=claim.id,
                   params={"journal": "j", "amount": "no_such_column",
                           "group_column": "doc"})
    healthy = CheckPlan(template="balance",
                    params={"journal": "j", "amount": "amount",
                            "group_column": "doc"})
    store.save_check_plan(broken)
    store.save_check_plan(healthy)

    report = run_ready(store, con)

    assert len(report.executed) == 1  # the healthy check still ran
    assert len(report.skipped) == 1
    check_plan_id, reason = report.skipped[0]
    assert check_plan_id == broken.id
    assert reason.startswith("execution error")
    # no evidence, no judgment: the claim is untouched
    assert store.claims[claim.id].status is ClaimStatus.PROPOSED
    assert store.claims[claim.id].evidence_ids == []
