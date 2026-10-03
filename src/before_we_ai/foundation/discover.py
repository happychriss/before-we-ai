"""Let the data say which of its columns are arithmetically tied.

Applying a rule needs a binding — which column is the local amount, which
the rate. Run B showed what happens when a model chooses that, and the
first foundation experiment needed a person who already knew the data. This
is the third way: no judgement at all. For a handful of rule *shapes* the
machine tries every combination of numeric columns in a table and reports
the ones that hold on nearly every row:

    a = b + c        a = b * c        a = b * (1 + c)        a = b

(`a = b / c` is the product `b = a * c` read from the other side, so the
direction an exchange rate is quoted in falls out by itself.)

It is measurement, the same kind stage 2 already does when it counts value
overlap between columns — and like the candidate matrix it never judges.
A tie says three columns move together. It does not say what they are
called; a foundation document's rule of the same shape supplies the names.

Two guards against coincidence, both learned on small tables: a tie needs a
minimum number of rows it could be evaluated on, and its columns need to
vary — `a = b * c` where c is always 1 is `a = b` wearing a hat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from itertools import combinations, permutations

SHAPES = ("sum", "product", "markup", "equal")
ABSOLUTE = 1.0  # whole currency units: exports are often rounded
RELATIVE = 0.005
AMOUNT_SCALE = 100.0  # below this a value is a rate or a count, not an amount
MIN_ROWS = 20
MIN_SHARE = 0.95
MIN_DISTINCT = 3  # a column that barely varies proves little
_NUMERIC_SHARE = 0.9  # share of non-blank values that must read as numbers
_BATCH = 400


@dataclass(frozen=True)
class Tie:
    view: str
    shape: str
    a: str
    b: str
    c: str | None
    satisfied: int
    evaluable: int

    @property
    def share(self) -> float:
        return self.satisfied / self.evaluable if self.evaluable else 0.0

    @property
    def exceptions(self) -> int:
        return self.evaluable - self.satisfied

    def formula(self) -> str:
        return {
            "sum": f"{self.a} = {self.b} + {self.c}",
            "product": f"{self.a} = {self.b} * {self.c}",
                    "markup": f"{self.a} = {self.b} * (1 + {self.c})",
            "equal": f"{self.a} = {self.b}",
        }[self.shape]


@dataclass
class Discovery:
    ties: list[Tie] = field(default_factory=list)
    numeric: dict[str, list[str]] = field(default_factory=dict)  # view -> columns
    skipped: dict[str, str] = field(default_factory=dict)  # view -> why


def _q(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"not a plain view or column name: {name!r}")
    return f'"{name}"'


def _num(column: str) -> str:
    return f"TRY_CAST({_q(column)} AS DOUBLE)"


def numeric_columns(con, view: str, min_rows: int = MIN_ROWS) -> dict[str, float]:
    """Columns that hold numbers and vary, each with its typical magnitude.

    Identifiers that happen to be digits are kept — telling a key from a
    quantity is not this module's call — but a column with fewer than
    ``MIN_DISTINCT`` values is not. The magnitude (median absolute value)
    is what lets a rate be told from an amount.
    """
    columns = [r[0] for r in con.execute(f"DESCRIBE {_q(view)}").fetchall()]
    out = {}
    for column in columns:
        try:
            filled, numbers, distinct, typical = con.execute(
                f"SELECT count({_q(column)}), count({_num(column)}), "
                f"count(DISTINCT {_num(column)}), median(abs({_num(column)})) "
                f"FROM {_q(view)}").fetchone()
        except Exception:  # noqa: BLE001 — an unreadable column is not numeric
            continue
        if (filled >= min_rows and numbers >= _NUMERIC_SHARE * filled
                and distinct >= MIN_DISTINCT):
            out[column] = float(typical or 0.0)
    return out


def _expression(shape: str, a: str, b: str, c: str | None) -> tuple[str, str]:
    """(left, right) as SQL over numeric casts."""
    A, B = _num(a), _num(b)
    if shape == "equal":
        return A, B
    C = _num(c)
    right = {
        "sum": f"({B} + {C})",
        "product": f"({B} * {C})",
        "markup": f"({B} * (1 + {C}))",
    }[shape]
    return A, right


def _candidates(columns: dict[str, float]):
    """Every (shape, a, b, c) worth testing, without mirror images.

    `a = b / c` is not tried: it is `b = a * c`, which is. A markup is only
    tried with a rate in the third place — a column whose values are
    typically below one. With an amount there, `b * (1 + c)` and `b * c`
    differ by less than any tolerance and every product would echo as a
    markup.
    """
    names = list(columns)
    for a, b in combinations(names, 2):
        yield "equal", a, b, None
    for a in names:
        others = [c for c in names if c != a]
        for b, c in combinations(others, 2):
            yield "sum", a, b, c  # b + c is symmetric
            yield "product", a, b, c
        for b, c in permutations(others, 2):
            if columns[c] < 1:
                yield "markup", a, b, c


def discover_view(con, view: str, *, min_rows: int = MIN_ROWS,
                  min_share: float = MIN_SHARE) -> tuple[list[Tie], list[str]]:
    columns = numeric_columns(con, view, min_rows)
    candidates = list(_candidates(columns))
    ties: list[Tie] = []
    for start in range(0, len(candidates), _BATCH):
        batch = candidates[start:start + _BATCH]
        parts = []
        for shape, a, b, c in batch:
            left, right = _expression(shape, a, b, c)
            evaluable = f"{left} IS NOT NULL AND {right} IS NOT NULL"
            # Whole-unit rounding is forgiven for amounts, not for rates: one
            # unit of slack on a value of 0.19 would make anything fit.
            scale = f"greatest(abs({left}), abs({right}))"
            ok = (f"(abs({left} - {right}) <= {RELATIVE} * {scale} OR "
                  f"(abs({left} - {right}) <= {ABSOLUTE} AND {scale} >= "
                  f"{AMOUNT_SCALE}))")
            parts.append(f"count(*) FILTER (WHERE {evaluable})")
            parts.append(f"count(*) FILTER (WHERE {evaluable} AND {ok})")
        row = con.execute(
            f"SELECT {', '.join(parts)} FROM {_q(view)}").fetchone()
        for i, (shape, a, b, c) in enumerate(batch):
            evaluable, satisfied = row[2 * i], row[2 * i + 1]
            if evaluable >= min_rows and satisfied >= min_share * evaluable:
                ties.append(Tie(view, shape, a, b, c, satisfied, evaluable))
    return _prune(ties), list(columns)


def _prune(ties: list[Tie]) -> list[Tie]:
    """Drop what only repeats a simpler tie.

    If x = y on nearly every row, then `x = y + c` and `x = y * c` hold too
    whenever c is small or near one — the third column is riding along
    inside the tolerance. Those say nothing the equality does not.
    """
    equal = {frozenset((t.a, t.b)): t.satisfied
             for t in ties if t.shape == "equal"}
    out = []
    for tie in sorted(ties, key=lambda t: (-t.share, -t.evaluable, t.view,
                                           t.shape, t.a, t.b, t.c or "")):
        if tie.shape != "equal":
            # ... unless it holds on rows the equality does not: then the
            # third column is doing work (a rate that is 1 almost always).
            echoes = [equal[pair] for pair in (frozenset((tie.a, tie.b)),
                                               frozenset((tie.a, tie.c)))
                      if pair in equal]
            if echoes and tie.satisfied <= max(echoes):
                continue
        out.append(tie)
    return out


def discover(con, views: list[str] | None = None, *, min_rows: int = MIN_ROWS,
             min_share: float = MIN_SHARE) -> Discovery:
    """Every arithmetic tie in every view of the catalog."""
    if views is None:
        views = [r[0] for r in con.execute(
            "SELECT view_name FROM duckdb_views() WHERE NOT internal "
            "ORDER BY view_name").fetchall()]
    result = Discovery()
    for view in views:
        rows = con.execute(f"SELECT count(*) FROM {_q(view)}").fetchone()[0]
        if rows < min_rows:
            result.skipped[view] = (
                f"{rows} rows — too few to tell a rule from a coincidence")
            continue
        ties, columns = discover_view(con, view, min_rows=min_rows,
                                      min_share=min_share)
        result.numeric[view] = columns
        result.ties.extend(ties)
    return result
