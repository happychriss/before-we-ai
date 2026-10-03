"""Deterministic verdict functions — no judgment ever comes from a model.

Each function looks at the exception rows a template's SQL produced and
returns a verdict plus the rows that count as exceptions. The K6 rule
lives here: a claim declared with ``expectation="report"`` (legitimate
orphans — open orders, prospects) can end INCONCLUSIVE with findings,
but structurally never FAIL.
"""

from dataclasses import dataclass, field

from before_we_ai.core.enums import CheckVerdict


@dataclass
class Assessment:
    verdict: CheckVerdict
    exceptions: list[tuple] = field(default_factory=list)
    summary: str = ""


def empty_expected(rows: list[tuple], columns: list[str], ctx: dict) -> Assessment:
    """The workhorse: any exception row falsifies the claim."""
    if not rows:
        return Assessment(CheckVerdict.PASS, [], "no violations")
    return Assessment(CheckVerdict.FAIL, rows, f"{len(rows)} violating groups")


def report_only(rows: list[tuple], columns: list[str], ctx: dict) -> Assessment:
    """K6: a finding is an observation, never a falsification."""
    if not rows:
        return Assessment(CheckVerdict.PASS, [], "no orphans")
    return Assessment(
        CheckVerdict.INCONCLUSIVE, rows, f"{len(rows)} orphaned groups — needs a domain answer"
    )


def anti_join_verdict(rows: list[tuple], columns: list[str], ctx: dict) -> Assessment:
    if ctx.get("expectation") == "report":
        return report_only(rows, columns, ctx)
    return empty_expected(rows, columns, ctx)


def coverage_verdict(rows: list[tuple], columns: list[str], ctx: dict) -> Assessment:
    expected = ctx["expected_count"]
    missing = len(rows)
    if missing == 0:
        return Assessment(CheckVerdict.PASS, [], f"all {expected} units covered")
    if missing >= expected:
        return Assessment(CheckVerdict.FAIL, rows, "no expected unit is covered")
    return Assessment(
        CheckVerdict.INCONCLUSIVE,
        rows,
        f"partial coverage: {missing} of {expected} units missing — a finding, not an error",
    )


def cardinality_verdict(rows: list[tuple], columns: list[str], ctx: dict) -> Assessment:
    """Counter-evidence for chance overlaps (T6): a real reference needs
    high containment AND an identifying parent column."""
    stats = dict(zip(columns, rows[0]))
    child_distinct = stats["child_distinct"] or 0
    parent_rows = stats["parent_rows"] or 0
    containment = (stats["overlap"] / child_distinct) if child_distinct else 0.0
    uniqueness = (stats["parent_distinct"] / parent_rows) if parent_rows else 0.0
    summary = f"containment={containment:.3f}, parent uniqueness={uniqueness:.3f}"
    if containment >= ctx["min_containment"] and uniqueness >= ctx["min_uniqueness"]:
        return Assessment(CheckVerdict.PASS, [], summary)
    # The stat row is the reasoning, not a per-row exception list.
    return Assessment(CheckVerdict.FAIL, [], f"not reference-shaped: {summary}")
