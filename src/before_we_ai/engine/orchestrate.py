"""Dependency-gated probe sweep.

Claims are visited in topological order of their `depends_on` graph and a
claim-bound probe only runs when every prerequisite is at least `tested`
(`ready_for_probe`, M1 scheduler) — the "Nebenbuch=Hauptbuch erst nach
Bindung beider Seiten" rule. Claim-less probes run unconditionally.

A probe whose SQL cannot execute (M4: probes may be AI-bound, and no
binding-time check can rule out every runtime type error) is contained:
it lands in ``skipped`` with the error as reason, writes no evidence, and
leaves its claim untouched — visible in the report, never a judgment and
never a crashed sweep. Data honesty is unchanged: a probe that *runs*
still crashes loudly on un-castable amounts inside its own SQL contract.
"""

from dataclasses import dataclass, field

import duckdb

from before_we_ai.model.objects import EvidenceRecord
from before_we_ai.model.scheduler import ready_for_probe, topological_order
from before_we_ai.store.repository import ProjectStore

from before_we_ai.engine.runner import run_probe


@dataclass
class RunReport:
    executed: list[EvidenceRecord] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (probe_id, reason)


def run_ready(
    store: ProjectStore,
    con,
    tolerances: dict[str, dict[str, float]] | None = None,
) -> RunReport:
    order = {cid: i for i, cid in enumerate(topological_order(store.claims.values()))}
    probes = sorted(
        store.probes.values(),
        key=lambda p: (order.get(p.claim_id, -1), p.created_at.isoformat(), p.id),
    )
    report = RunReport()
    for probe in probes:
        if probe.claim_id:
            claim = store.claims.get(probe.claim_id)
            if claim is None:
                report.skipped.append((probe.id, f"unknown claim {probe.claim_id}"))
                continue
            if not ready_for_probe(claim, store.claims):
                report.skipped.append((probe.id, "prerequisites not tested yet"))
                continue
        try:
            report.executed.append(run_probe(store, con, probe, tolerances))
        except (duckdb.Error, ValueError, KeyError, StopIteration) as exc:
            report.skipped.append(
                (probe.id, f"execution error ({type(exc).__name__}): {exc}")
            )
    return report
