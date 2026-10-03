"""Dependency scheduler: topological order, cycles, check gating."""

import pytest

from before_we_ai.core import Actor, ClaimStatus, CycleError, create_claim
from before_we_ai.core.scheduler import ready_for_check, topological_order

pytestmark = pytest.mark.unit


def claim(statement, depends_on=(), status=ClaimStatus.PROPOSED):
    c = create_claim(statement, Actor.AI, depends_on=list(depends_on))
    c.status = status
    return c


class TestTopologicalOrder:
    def test_chain(self):
        a = claim("a")
        b = claim("b", [a.id])
        c = claim("c", [b.id])
        order = topological_order([c, a, b])
        assert order.index(a.id) < order.index(b.id) < order.index(c.id)

    def test_diamond(self):
        a = claim("a")
        b = claim("b", [a.id])
        c = claim("c", [a.id])
        d = claim("d", [b.id, c.id])
        order = topological_order([d, c, b, a])
        assert order.index(a.id) < order.index(b.id)
        assert order.index(a.id) < order.index(c.id)
        assert order.index(b.id) < order.index(d.id)
        assert order.index(c.id) < order.index(d.id)

    def test_cycle_is_a_hard_error(self):
        a = claim("a")
        b = claim("b", [a.id])
        a.depends_on = [b.id]
        with pytest.raises(CycleError):
            topological_order([a, b])

    def test_unknown_dependency_raises(self):
        a = claim("a", ["01JUNKJUNKJUNKJUNKJUNKJUNK"])
        with pytest.raises(KeyError):
            topological_order([a])


class TestReadyForCheck:
    @pytest.mark.parametrize(
        "dep_status,ready",
        [
            (ClaimStatus.PROPOSED, False),
            (ClaimStatus.UNRESOLVED, False),
            (ClaimStatus.CONTRADICTED, False),
            (ClaimStatus.TEST_SUPPORTED, True),
            (ClaimStatus.BUSINESS_CONFIRMED, True),
        ],
    )
    def test_prerequisite_must_be_at_least_tested(self, dep_status, ready):
        dep = claim("dep", status=dep_status)
        dependent = claim("dependent", [dep.id])
        assert ready_for_check(dependent, {dep.id: dep}) is ready

    def test_no_dependencies_is_always_ready(self):
        assert ready_for_check(claim("a"), {}) is True

    def test_unknown_dependency_raises(self):
        dependent = claim("dependent", ["01JUNKJUNKJUNKJUNKJUNKJUNK"])
        with pytest.raises(KeyError):
            ready_for_check(dependent, {})
