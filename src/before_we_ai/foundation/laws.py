"""Apply a foundation document's rules to bound data.

A rule in the document speaks of business objects and quantities. A
**binding** says which view and which column each of them is in this
landscape — and, where the guide has one, which role that column would
play. Binding is a human act here: the experiment this module supports
asks whether general industry knowledge settles roles at all, and letting a
model choose what a law is tested on would put the old hole back.

Two things differ from the checks in ``checks/library.py``, both learned on
the vessel landscape (Run B):

* **A rule holds by share, not by a single row.** It is measured over every
  record it can be evaluated on; at or above the document's ``MIN_SHARE`` it
  holds, and the records where it does not are *findings* — reported, never
  a verdict on the column. One wrong FX conversion in 138 rows is a row to
  look at, not proof that the amount column is something else.
* **The tolerance belongs to the rule**, by way of the document's tolerance
  classes. "Hours times rate equals cost" is true to the euro, not to the
  cent, and that is a fact about the business.

What a holding rule establishes is that the quantities in it are
arithmetically tied the way the business says they must be. That is
evidence the columns are what the binding says. It is not proof of meaning:
a copy of the real ledger passes every rule the real ledger passes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from before_we_ai.foundation.reader import Foundation, Rule

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MAX_SAMPLES = 5


@dataclass
class Binding:
    """Where a document's objects and quantities live in one landscape."""

    objects: dict[str, dict]  # object -> {"view": ..., "role": ...}
    quantities: dict[tuple[str, str], dict]  # -> {"column": ..., "role": ...}
    parameters: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "Binding":
        quantities = {}
        for key, spec in (data.get("quantities") or {}).items():
            obj, _, quantity = key.partition(".")
            quantities[(obj, quantity)] = spec
        return cls(objects=data.get("objects") or {}, quantities=quantities,
                   parameters={k: str(v) for k, v in
                               (data.get("parameters") or {}).items()})

    def view(self, obj: str) -> str:
        return self.objects[obj]["view"]

    def column(self, obj: str, quantity: str) -> str:
        return self.quantities[(obj, quantity)]["column"]

    def source(self, obj: str) -> str:
        """What the object's records are read from: the view, or the rows of
        it a person said make up this object (`where:` in the binding — the
        clearing account's lines are the ledger lines on certain accounts)."""
        spec = self.objects[obj]
        if spec.get("where"):
            return f"(SELECT * FROM {_q(spec['view'])} WHERE {spec['where']})"
        return _q(spec["view"])

    def sql(self, obj: str, quantity: str) -> str:
        """The quantity as a value. `columns: [a, b]` binds one business key
        to several columns — an order line is an order number and a position."""
        spec = self.quantities[(obj, quantity)]
        if spec.get("expr"):
            # written by the person who binds — e.g. an order line's key
            # built the way the ledger's assignment field spells it
            return f"({spec['expr']})"
        if spec.get("columns"):
            return " || '|' || ".join(
                f"CAST({_q(c)} AS VARCHAR)" for c in spec["columns"])
        return _q(spec["column"])

    def number(self, obj: str, quantity: str) -> str:
        """The quantity as a number. ``invert: true`` in the binding says
        the company stores it the other way round — an exchange rate quoted
        as foreign units per home unit instead of home per foreign. That is
        a company parameter, not a different rule."""
        spec = self.quantities[(obj, quantity)]
        value = _num(spec["column"])
        if spec.get("negative_when"):
            # debit and credit kept as an indicator beside an unsigned amount
            column, mark = next(iter(spec["negative_when"].items()))
            mark = str(mark).replace("'", "''")
            value = (f"(CASE WHEN CAST({_q(column)} AS VARCHAR) = '{mark}' "
                     f"THEN -{value} ELSE {value} END)")
        return f"(1.0 / NULLIF({value}, 0))" if spec.get("invert") else value

    def missing(self, rule: Rule) -> list[str]:
        """What the landscape has no counterpart for — in the reader's words."""
        gaps = [f"object `{o}`" for o in rule.objects if o not in self.objects]
        gaps += [f"quantity `{o}.{q}`" for o, q in rule.quantities
                 if o in self.objects and (o, q) not in self.quantities]
        gaps += [f"parameter `{p}`" for p in rule.parameters
                 if p not in self.parameters]
        return gaps


@dataclass
class LawResult:
    rule: Rule
    applicable: bool
    reason: str = ""  # why not applicable
    evaluable: int = 0  # records the rule could be evaluated on
    satisfied: int = 0
    not_evaluable: int = 0  # records with a blank where a value is needed
    samples: list[dict] = field(default_factory=list)
    sql: str = ""
    error: str = ""

    @property
    def share(self) -> float:
        return self.satisfied / self.evaluable if self.evaluable else 0.0

    @property
    def exceptions(self) -> int:
        return self.evaluable - self.satisfied

    def holds(self, min_share: float) -> bool:
        return self.applicable and self.evaluable > 0 and self.share >= min_share


def _q(name: str) -> str:
    # catalog views are named after files and may start with a digit
    if not re.fullmatch(r"[A-Za-z0-9_]+", name):
        raise ValueError(f"not a bare identifier: {name!r}")
    return f'"{name}"'


def _num(column: str) -> str:
    return f"TRY_CAST({_q(column)} AS DOUBLE)"


def _blank(value: str) -> str:
    return f"(({value}) IS NULL OR trim(CAST(({value}) AS VARCHAR)) = '')"


def _within(left: str, right: str, tolerance, op: str = "=") -> str:
    """`left OP right`, allowing for the rule's tolerance. For <= and >= the
    tolerance widens the permitted side: "at most" means at most, give or
    take rounding."""
    tests = []
    if tolerance.absolute is not None:
        tests.append(f"abs(({left}) - ({right})) <= {tolerance.absolute}")
    if tolerance.relative is not None:
        tests.append(
            f"abs(({left}) - ({right})) <= {tolerance.relative} * "
            f"greatest(abs({left}), abs({right}))")
    if not tests:  # exact — allowing for floating-point noise only
        tests.append(f"abs(({left}) - ({right})) <= 1e-9")
    close = "(" + " OR ".join(tests) + ")"
    if op == "<=":
        return f"(({left}) <= ({right}) OR {close})"
    if op == ">=":
        return f"(({left}) >= ({right}) OR {close})"
    return close


def _term_sql(term: dict, binding: "Binding") -> str:
    """One side of a TOTAL or DIFFERENCE as `SELECT k, v ... GROUP BY k`."""
    obj = term["object"]
    where = ""
    if term.get("filter"):
        f = term["filter"]
        value = binding.parameters[f["parameter"]].replace("'", "''")
        column = binding.sql(obj, f["quantity"])
        compare = "=" if f["op"] == "=" else "IS DISTINCT FROM"
        where = f" WHERE CAST({column} AS VARCHAR) {compare} '{value}'"
    return (f"SELECT CAST({binding.sql(obj, term['key'])} AS VARCHAR) AS k, "
            f"sum({binding.number(obj, term['measure'])}) AS v "
            f"FROM {binding.source(obj)}{where} GROUP BY 1")


def _expression(text: str, obj: str, binding: Binding) -> str:
    return _IDENT.sub(lambda m: binding.number(obj, m.group()), text)


def _compile(rule: Rule, binding: Binding, foundation: Foundation) -> tuple[str, str]:
    """(population SQL, exception SQL). The population SQL returns
    (evaluable, satisfied, not_evaluable); the exception SQL the offenders."""
    p = rule.parts
    tolerance = foundation.tolerances[rule.tolerance]
    if rule.kind == "IDENTITY":
        view = binding.source(p["object"])
        left = _expression(p["left"], p["object"], binding)
        right = _expression(p["right"], p["object"], binding)
        ok = _within(left, right, tolerance, p.get("op", "="))
        evaluable = f"({left}) IS NOT NULL AND ({right}) IS NOT NULL"
        columns = ", ".join(binding.sql(o, q) for o, q in rule.quantities)
        return (
            f"SELECT count(*) FILTER (WHERE {evaluable}), "
            f"count(*) FILTER (WHERE {evaluable} AND {ok}), "
            f"count(*) FILTER (WHERE NOT ({evaluable})) FROM {view}",
            f"SELECT {columns}, round(({left}) - ({right}), 2) AS difference "
            f"FROM {view} WHERE {evaluable} AND NOT {ok} "
            f"ORDER BY abs(({left}) - ({right})) DESC",
        )
    if rule.kind == "UNIQUE":
        view = binding.source(p["object"])
        keys = [binding.sql(p["object"], k) for k in p["keys"]]
        blank = " OR ".join(_blank(binding.sql(p["object"], k))
                            for k in p["keys"])
        key_list = ", ".join(keys)
        counted = (f"SELECT {key_list}, count(*) AS n FROM {view} "
                   f"WHERE NOT ({blank}) GROUP BY {key_list}")
        return (
            f"SELECT coalesce(sum(n), 0), "
            f"coalesce(sum(n) FILTER (WHERE n = 1), 0), "
            f"(SELECT count(*) FROM {view} WHERE {blank}) FROM ({counted})",
            f"SELECT {key_list}, n AS occurrences FROM ({counted}) "
            f"WHERE n > 1 ORDER BY n DESC, {key_list}",
        )
    if rule.kind == "REFERENCE":
        child, parent = binding.source(p["child"]), binding.source(p["parent"])
        ckey = binding.sql(p["child"], p["child_key"])
        pkey = binding.sql(p["parent"], p["parent_key"])
        found = (f"CAST({ckey} AS VARCHAR) IN "
                 f"(SELECT CAST({pkey} AS VARCHAR) FROM {parent})")
        return (
            f"SELECT count(*) FILTER (WHERE NOT {_blank(ckey)}), "
            f"count(*) FILTER (WHERE NOT {_blank(ckey)} AND {found}), "
            f"count(*) FILTER (WHERE {_blank(ckey)}) FROM {child}",
            f"SELECT {ckey}, count(*) AS records FROM {child} "
            f"WHERE NOT {_blank(ckey)} AND NOT {found} GROUP BY 1 ORDER BY 2 DESC",
        )
    if rule.kind == "CONDITION":
        view = binding.source(p["object"])
        status = binding.sql(p["object"], p["status"])
        target = binding.sql(p["object"], p["quantity"])
        value = binding.parameters[p["parameter"]].replace("'", "''")
        applies = f"CAST({status} AS VARCHAR) = '{value}'"
        ok = f"NOT {_blank(target)}" if p["expect"] == "present" else _blank(target)
        return (
            f"SELECT count(*) FILTER (WHERE {applies}), "
            f"count(*) FILTER (WHERE {applies} AND {ok}), 0 FROM {view}",
            f"SELECT {status}, {target} FROM {view} "
            f"WHERE {applies} AND NOT ({ok})",
        )
    if rule.kind in ("TOTAL", "DIFFERENCE"):
        terms = p["terms"]
        names = [f"t{i}" for i in range(len(terms))]
        joined = f"({_term_sql(terms[0], binding)}) t0"
        key = "t0.k"
        for i in range(1, len(terms)):
            joined += (f" FULL JOIN ({_term_sql(terms[i], binding)}) t{i} "
                       f"ON {key} = t{i}.k")
            key = f"coalesce({key}, t{i}.k)"
        # A sum over no records is zero: an order line nobody has received
        # against has received nothing. A *stored* figure that is absent is
        # not zero — there is nothing to compare with.
        values = [f"{n}.v" if t["stored"] else f"coalesce({n}.v, 0)"
                  for n, t in zip(names, terms)]
        columns = ", ".join(f"{v} AS v{i}" for i, v in enumerate(values))
        base = f"SELECT {key} AS key, {columns} FROM {joined}"
        if rule.kind == "DIFFERENCE":
            left, right = "(v0 - v1)", "v2"
        else:
            left, right = "v0", "v1"
        evaluable = " AND ".join(f"v{i} IS NOT NULL" for i in range(len(terms)))
        ok = _within(left, right, tolerance, p["op"])
        shown = ", ".join(f"round(v{i}, 2) AS {t['object']}_{t['measure']}"
                          for i, t in enumerate(terms))
        return (
            f"SELECT count(*) FILTER (WHERE {evaluable}), "
            f"count(*) FILTER (WHERE {evaluable} AND {ok}), "
            f"count(*) FILTER (WHERE NOT ({evaluable})) FROM ({base})",
            f"SELECT key, {shown}, round({left} - {right}, 2) AS difference "
            f"FROM ({base}) WHERE {evaluable} AND NOT {ok} "
            f"ORDER BY abs({left} - {right}) DESC",
        )
    raise ValueError(f"unknown rule kind {rule.kind!r}")


def evaluate(con, foundation: Foundation, binding: Binding) -> list[LawResult]:
    """Measure every rule of the document on the bound data."""
    results = []
    for rule in foundation.rules:
        gaps = binding.missing(rule)
        if gaps:
            results.append(LawResult(
                rule, applicable=False,
                reason="this landscape has no " + ", ".join(gaps)))
            continue
        result = LawResult(rule, applicable=True)
        try:
            population_sql, exception_sql = _compile(rule, binding, foundation)
            result.sql = exception_sql
            evaluable, satisfied, blank = con.execute(population_sql).fetchone()
            result.evaluable = int(evaluable or 0)
            result.satisfied = int(satisfied or 0)
            result.not_evaluable = int(blank or 0)
            cursor = con.execute(exception_sql + f" LIMIT {MAX_SAMPLES}")
            names = [d[0] for d in cursor.description]
            result.samples = [dict(zip(names, (None if v is None else str(v)
                                               for v in row)))
                              for row in cursor.fetchall()]
        except Exception as exc:  # noqa: BLE001 — recorded on the result
            result.error = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"
        results.append(result)
    return results
