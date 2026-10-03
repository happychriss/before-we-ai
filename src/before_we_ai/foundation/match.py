"""Propose a binding: which view and column each term of the document is.

Not a decision — a proposal a person signs off, with the reason for every
line. Three kinds of reason, in falling strength:

* **arithmetic** — the document has a rule of some shape, the data has a
  tie of the same shape (`foundation.discover`), and the columns are
  assigned by it. No name was consulted and no model was asked.
* **name, and the rules hold** — an identifier or status has no arithmetic.
  It is paired with the column whose name resembles it most, and kept only
  if every rule that mentions it then holds.
* **name only** — the resemblance, with nothing to back it.

Whatever is left has no counterpart the machine could find, and is said so.

The matching by name is a heuristic over word fragments. It is the weakest
part of this module on purpose: where it is wrong the rules that mention
the quantity fail, and a failed rule is visible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from before_we_ai.foundation.discover import Discovery, Tie, _num, _q
from before_we_ai.foundation.reader import Foundation, Rule

ARITHMETIC = "arithmetic"
NAME_AND_RULES = "name, and the rules hold"
NAME_ONLY = "name only"
_NAME = r"[a-z][a-z0-9_]*"
_NAME_THRESHOLD = 0.5
# A tie of the right shape is not enough to say *which* rule it is: every
# `a = b * c` fits every product. Tried on the vessel data, shape alone bound
# "contract price = original price + change orders" to gross = net + VAT, and
# the rule then "held" on 24 of 24 rows of the wrong table. So the names have
# to agree as well — the table's with the object's, the columns' with the
# quantities'. Below this, the tie is reported as unclaimed and a person says
# which rule it is.
_ARITHMETIC_THRESHOLD = 1.0
_OBJECT_WEIGHT = 2.0


@dataclass
class Proposed:
    object: str
    quantity: str | None  # None for the object itself
    view: str
    column: str | None
    reason: str
    detail: str = ""
    invert: bool = False
    rivals: list[str] = field(default_factory=list)


@dataclass
class Proposal:
    lines: list[Proposed] = field(default_factory=list)
    unbound: list[tuple[str, str | None]] = field(default_factory=list)
    #: ties the data has and no rule could be named for — for a person to
    #: say which rule each one is, or that it is none
    unclaimed: list[Tie] = field(default_factory=list)

    def as_binding(self, parameters: dict[str, str] | None = None) -> dict:
        objects, quantities = {}, {}
        for line in self.lines:
            if line.quantity is None:
                objects[line.object] = {"view": line.view}
            else:
                spec = {"column": line.column}
                if line.invert:
                    spec["invert"] = True
                quantities[f"{line.object}.{line.quantity}"] = spec
        return {"objects": objects, "quantities": quantities,
                "parameters": dict(parameters or {})}


# ---------------------------------------------------------------- shapes


def rule_shape(rule: Rule) -> tuple[str, str, str, str | None] | None:
    """An IDENTITY rule as (shape, a, b, c) over quantity names, in the
    forms the tie search looks for — or None if it has another form."""
    if rule.kind != "IDENTITY" or rule.parts.get("op") != "=":
        return None
    left = "".join(rule.parts["left"].split())
    right = "".join(rule.parts["right"].split())
    if not re.fullmatch(_NAME, left):
        if re.fullmatch(_NAME, right):
            left, right = right, left
        else:
            return None
    for pattern, build in (
        (rf"({_NAME})\*\(1\+({_NAME})\)", lambda b, c: ("markup", left, b, c)),
        (rf"\(1\+({_NAME})\)\*({_NAME})", lambda c, b: ("markup", left, b, c)),
        (rf"({_NAME})\+({_NAME})", lambda b, c: ("sum", left, b, c)),
        (rf"({_NAME})-({_NAME})", lambda b, c: ("sum", b, left, c)),
        (rf"({_NAME})\*({_NAME})", lambda b, c: ("product", left, b, c)),
        (rf"({_NAME})/({_NAME})", lambda b, c: ("product", b, left, c)),
        (rf"({_NAME})", lambda b: ("equal", left, b, None)),
    ):
        match = re.fullmatch(pattern, right)
        if match:
            return build(*match.groups())
    return None


_STOP = {"per", "of", "in", "to", "by", "the", "eur", "usd"}


def _tokens(name: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", name.lower())
            if t and t not in _STOP}


# Words nearly every finance column carries. Sharing one says little:
# `vat_amount` resembles `amount_functional` only in being an amount.
_GENERIC = {"amount", "amt", "value", "total", "sum", "rate", "id", "no",
            "number", "num", "nr", "code", "date", "dt", "type", "name",
            "key", "ref", "reference", "line", "item", "doc", "document"}
_GENERIC_WEIGHT = 0.25


def _alike(x: str, y: str) -> bool:
    """`qty` and `quantity`, `curr` and `currency`, `amt` and `amount`:
    equal, or the shorter one is the longer one with letters left out —
    same first letter, same order."""
    if x == y:
        return True
    short, long = sorted((x, y), key=len)
    if len(short) < 3 or short[0] != long[0]:
        return False
    rest = iter(long)
    return all(letter in rest for letter in short)


def _weight(token: str) -> float:
    return _GENERIC_WEIGHT if token in _GENERIC else 1.0


def similarity(term: str, column: str) -> float:
    """How much of the two names is shared, counting an ordinary word such
    as `amount` for a quarter of a telling one such as `gross`."""
    a, b = _tokens(term), _tokens(column)
    if not a or not b:
        return 0.0
    shared = sum(_weight(x) for x in a if any(_alike(x, y) for y in b))
    return shared / max(sum(map(_weight, a)), sum(map(_weight, b)))


# ---------------------------------------------------------------- matching


def _assignments(shape, tie: Tie, quantities, types, magnitudes):
    """Ways a rule's (a, b, c) can sit on a tie's columns."""
    _, a, b, c = shape
    if shape[0] == "equal":
        yield {a: tie.a, b: tie.b}, set()
        yield {a: tie.b, b: tie.a}, set()
        return
    yield {a: tie.a, b: tie.b, c: tie.c}, set()
    if shape[0] in ("sum", "product"):
        yield {a: tie.a, b: tie.c, c: tie.b}, set()
    if shape[0] == "product":
        # The same relation quoted the other way round: the rule multiplies
        # by a rate, the data divides by it. Only offered where the document
        # itself calls the third quantity a rate; the smaller factor is taken
        # to be the rate.
        for rate, other in ((b, c), (c, b)):
            if types.get(rate) != "rate":
                continue
            small, large = sorted((tie.b, tie.c),
                                  key=lambda col: magnitudes.get(col, 0.0))
            yield {a: large, other: tie.a, rate: small}, {rate}


def _rate_is_smallest(mapping, types, magnitudes) -> bool:
    """A quantity the document calls a rate sits on the tie's smallest
    column; an amount does not. Without this an exchange rate is as happy
    on the column of totals as on the column of rates."""
    if len(mapping) < 3:
        return True
    smallest = min(mapping.values(), key=lambda col: magnitudes.get(col, 0.0))
    rates = [q for q in mapping if types.get(q) == "rate"]
    return all(mapping[q] == smallest for q in rates)


def propose(con, foundation: Foundation, discovery: Discovery) -> Proposal:
    views = [r[0] for r in con.execute(
        "SELECT view_name FROM duckdb_views() WHERE NOT internal "
        "ORDER BY view_name").fetchall()]
    columns = {v: [r[0] for r in con.execute(f"DESCRIBE {_q(v)}").fetchall()]
               for v in views}
    magnitudes = {}
    for view in discovery.numeric:
        for column in discovery.numeric[view]:
            magnitudes[(view, column)] = con.execute(
                f"SELECT median(abs({_num(column)})) FROM {_q(view)}"
            ).fetchone()[0] or 0.0

    # 1. arithmetic. Every (rule, tie, assignment) that the names do not
    #    contradict, strongest first.
    candidates = []
    for rule in foundation.rules:
        shape = rule_shape(rule)
        if shape is None:
            continue
        obj = rule.parts["object"]
        types = {q: foundation.quantities[(obj, q)]["type"]
                 for _, q in rule.quantities}
        for tie in discovery.ties:
            if tie.shape != shape[0]:
                continue
            local = {c: magnitudes.get((tie.view, c), 0.0)
                     for c in (tie.a, tie.b, tie.c) if c}
            table = similarity(obj, tie.view.split("__")[-1])
            options = []
            for mapping, inverted in _assignments(shape, tie, rule.quantities,
                                                  types, local):
                if not _rate_is_smallest(mapping, types, local):
                    continue
                named = sum(similarity(q, col) for q, col in mapping.items())
                options.append((named, mapping, inverted))
            if not options:
                continue
            options.sort(key=lambda o: -o[0])
            named, mapping, inverted = options[0]
            # the table has to resemble the object, or the columns the
            # quantities — a shape alone names nothing
            if table < 0.5 and named < _ARITHMETIC_THRESHOLD:
                continue
            other_ways = [m for n, m, _ in options[1:] if n >= named - 1e-9]
            candidates.append((named + _OBJECT_WEIGHT * table, rule, tie,
                               mapping, inverted, other_ways))
    candidates.sort(key=lambda c: -c[0])

    proposal = Proposal()
    bound_view: dict[str, str] = {}
    bound: dict[tuple[str, str], str] = {}
    claimed = set()
    for score, rule, tie, mapping, inverted, other_ways in candidates:
        obj = rule.parts["object"]
        if bound_view.get(obj, tie.view) != tie.view:
            continue  # the object already lives in another table
        taken = {col: q for (o, q), col in bound.items() if o == obj}
        if any(bound.get((obj, q), col) != col or taken.get(col, q) != q
               for q, col in mapping.items()):
            continue  # one column cannot be two quantities
        if obj not in bound_view:
            bound_view[obj] = tie.view
            proposal.lines.append(Proposed(
                obj, None, tie.view, None, ARITHMETIC,
                f"{rule.id} fits a tie found in this table"))
        claimed.add(id(tie))
        for quantity, column in mapping.items():
            if (obj, quantity) in bound:
                continue
            bound[(obj, quantity)] = column
            proposal.lines.append(Proposed(
                obj, quantity, tie.view, column, ARITHMETIC,
                f"{rule.id} '{rule.formal}' fits {tie.formula()} on "
                f"{tie.satisfied} of {tie.evaluable} rows"
                + ("; the rate is quoted the other way round"
                   if quantity in inverted else ""),
                invert=quantity in inverted,
                rivals=sorted({way[quantity] for way in other_ways
                               if way.get(quantity) not in (None, column)})))
    proposal.unclaimed = [t for t in discovery.ties if id(t) not in claimed]

    # 2. objects no rule placed: by the table's name
    for obj in foundation.objects:
        if obj in bound_view:
            continue
        scored = sorted(((similarity(obj, v.split("__")[-1]), v)
                         for v in views), reverse=True)
        if not scored or scored[0][0] < _NAME_THRESHOLD:
            proposal.unbound.append((obj, None))
            continue
        bound_view[obj] = scored[0][1]
        proposal.lines.append(Proposed(
            obj, None, scored[0][1], None, NAME_ONLY,
            f"the table name resembles '{obj}'",
            rivals=[v for sc, v in scored[1:3] if sc >= _NAME_THRESHOLD]))

    # 3. everything else, by name — at most one quantity per column
    for (obj, quantity) in foundation.quantities:
        if obj not in bound_view or (obj, quantity) in bound:
            continue
        view = bound_view[obj]
        taken = {col for (o, _), col in bound.items() if o == obj}
        scored = sorted(((similarity(quantity, col), col)
                         for col in columns[view] if col not in taken),
                        reverse=True)
        if not scored or scored[0][0] < _NAME_THRESHOLD:
            proposal.unbound.append((obj, quantity))
            continue
        bound[(obj, quantity)] = scored[0][1]
        proposal.lines.append(Proposed(
            obj, quantity, view, scored[0][1], NAME_ONLY,
            f"the column name resembles '{quantity}'",
            rivals=[c for sc, c in scored[1:3] if sc >= _NAME_THRESHOLD]))
    return proposal
