"""Claim-dependency resolution — a mini-scheduler, not a workflow system.

Claims may declare dependencies; a probe only runs once every prerequisite
claim is at least ``tested`` (e.g. subledger=GL only after both role
bindings hold). Resolution is a plain topological sort.
"""

from collections.abc import Iterable

from before_we_ai.model.enums import ClaimStatus
from before_we_ai.model.objects import Claim

_PROBE_READY = (ClaimStatus.TESTED, ClaimStatus.BUSINESS_CONFIRMED)


class CycleError(Exception):
    """Raised when claim dependencies form a cycle."""


def topological_order(claims: Iterable[Claim]) -> list[str]:
    """Return claim IDs so that every claim comes after its dependencies.

    Dependencies pointing outside the given set raise KeyError (dangling
    references are an integrity failure, not something to skip silently).
    """
    by_id = {c.id: c for c in claims}
    for claim in by_id.values():
        for dep in claim.depends_on:
            if dep not in by_id:
                raise KeyError(f"claim {claim.id} depends on unknown claim {dep}")

    order: list[str] = []
    state: dict[str, int] = {}  # 0 = unvisited, 1 = in progress, 2 = done

    def visit(cid: str, path: list[str]) -> None:
        if state.get(cid) == 2:
            return
        if state.get(cid) == 1:
            cycle = " -> ".join([*path[path.index(cid):], cid])
            raise CycleError(f"dependency cycle: {cycle}")
        state[cid] = 1
        for dep in by_id[cid].depends_on:
            visit(dep, [*path, cid])
        state[cid] = 2
        order.append(cid)

    for cid in by_id:
        visit(cid, [])
    return order


def ready_for_probe(claim: Claim, claims_by_id: dict[str, Claim]) -> bool:
    """A probe may run once every prerequisite is at least ``tested``."""
    for dep in claim.depends_on:
        if dep not in claims_by_id:
            raise KeyError(f"claim {claim.id} depends on unknown claim {dep}")
        if claims_by_id[dep].status not in _PROBE_READY:
            return False
    return True
