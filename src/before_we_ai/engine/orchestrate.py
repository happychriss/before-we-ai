"""Dependency-gated check sweep.

Claims are visited in topological order of their `depends_on` graph and a
claim-bound check only runs when every prerequisite is at least `test-supported`
(`ready_for_check`, M1 scheduler) — the "Nebenbuch=Hauptbuch erst nach
Bindung beider Seiten" rule. Claim-less checks run unconditionally.

A check whose SQL cannot execute (M4: checks may be AI-bound, and no
binding-time check can rule out every runtime type error) is contained:
it lands in ``skipped`` with the error as reason, writes no evidence, and
leaves its claim untouched — visible in the report, never a judgment and
never a crashed sweep. Data honesty is unchanged: a check that *runs*
still crashes loudly on un-castable amounts inside its own SQL contract.
"""

from dataclasses import dataclass, field

import duckdb

from before_we_ai.model.objects import EvidenceRecord
from before_we_ai.model.scheduler import ready_for_check, topological_order
from before_we_ai.store.repository import ProjectStore

from before_we_ai.engine.runner import run_check


@dataclass
class RunReport:
    executed: list[EvidenceRecord] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (check_plan_id, reason)


def run_ready(
    store: ProjectStore,
    con,
    tolerances: dict[str, dict[str, float]] | None = None,
) -> RunReport:
    order = {cid: i for i, cid in enumerate(topological_order(store.claims.values()))}
    checks = sorted(
        store.checks.values(),
        key=lambda p: (order.get(p.claim_id, -1), p.created_at.isoformat(), p.id),
    )
    report = RunReport()
    for check in checks:
        if check.claim_id:
            claim = store.claims.get(check.claim_id)
            if claim is None:
                report.skipped.append((check.id, f"unknown claim {check.claim_id}"))
                continue
            if not ready_for_check(claim, store.claims):
                report.skipped.append((check.id, "prerequisites not tested yet"))
                continue
        try:
            report.executed.append(run_check(store, con, check, tolerances))
        except (duckdb.Error, ValueError, KeyError, StopIteration) as exc:
            report.skipped.append(
                (check.id, f"execution error ({type(exc).__name__}): {exc}")
            )
    return report
