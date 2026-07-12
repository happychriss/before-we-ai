"""The probe template registry.

One entry per template, and a new template exists only because a corpus
case forces it (Regel gegen Wildwuchs): anti_join (T1/F1/F5), duplicate/
grain (T11/F2), coverage (T12/F16), cardinality (T6), attribute_
contradiction (F5-continuity), reconciliation (F27), validity_join (F6),
range_join (F9), decode (F7), and the invariants balance (Z4/F22),
subledger_equals_gl (F20), ic_symmetry (F22).

Each spec knows its SQL file, how to build the Jinja context from probe
params (``prepare``), its deterministic verdict function, its default
tolerances (overridable ONLY via before-ai.yaml), and the Fachfrage it
drafts on FAIL/INCONCLUSIVE.
"""

from dataclasses import dataclass, field
from typing import Callable

from before_we_ai.probes import verdicts
from before_we_ai.sources.canonical import canonical_sql_expr


def _ident(name: str) -> str:
    if '"' in name:
        raise ValueError(f"illegal identifier: {name!r}")
    return name


def column_expr(con, view: str, column: str, canonical: bool = True,
                alias: str | None = None) -> str:
    """Comparison expression for a column — canonical by default.

    ``canonical=False`` compares the raw text rendering (T1's failure
    mode, kept available so tests can demonstrate WHY normalization is
    part of the claim).
    """
    _ident(view), _ident(column)
    if alias:
        _ident(alias)
    if not canonical:
        prefix = f'"{alias}".' if alias else ""
        return f'CAST({prefix}"{column}" AS VARCHAR)'
    dtype = next(
        r[1] for r in con.execute(f'DESCRIBE "{view}"').fetchall() if r[0] == column
    )
    return canonical_sql_expr(column, dtype, alias=alias)


@dataclass
class TemplateSpec:
    file: str
    prepare: Callable  # (con, params, tolerances) -> jinja context
    verdict: Callable  # (rows, columns, ctx) -> verdicts.Assessment
    tolerances: dict[str, float] = field(default_factory=dict)
    question: str | None = None  # Fachfrage template, formatted with the context


def _prep_anti_join(con, p, tol):
    canonical = p.get("canonical", True)
    return {
        "child": _ident(p["child"]),
        "parent": _ident(p["parent"]),
        "child_expr": column_expr(con, p["child"], p["child_column"], canonical),
        "parent_expr": column_expr(con, p["parent"], p["parent_column"], canonical),
        "expectation": p.get("expectation", "empty"),
        "views": [p["child"], p["parent"]],
    }


def _prep_duplicate(con, p, tol):
    keys = ", ".join(f'"{_ident(c)}"' for c in p["key_columns"])
    return {"table": _ident(p["table"]), "key_list": keys, "views": [p["table"]]}


def _prep_coverage(con, p, tol):
    expected = [str(v).replace("'", "''") for v in p["expected"]]
    return {
        "table": _ident(p["table"]),
        "unit_expr": column_expr(con, p["table"], p["unit_column"], p.get("canonical", True)),
        "expected_values": ", ".join(f"('{v}')" for v in expected),
        "expected_count": len(expected),
        "views": [p["table"]],
    }


def _prep_cardinality(con, p, tol):
    return {
        "child": _ident(p["child"]),
        "parent": _ident(p["parent"]),
        "child_expr": column_expr(con, p["child"], p["child_column"]),
        "parent_expr": column_expr(con, p["parent"], p["parent_column"]),
        "min_containment": tol["min_containment"],
        "min_uniqueness": tol["min_uniqueness"],
        "views": [p["child"], p["parent"]],
    }


def _prep_attribute_contradiction(con, p, tol):
    canonical = p.get("canonical", True)
    return {
        "left": _ident(p["left"]),
        "right": _ident(p["right"]),
        "left_key_expr": column_expr(con, p["left"], p["left_key"], canonical, alias="l"),
        "right_key_expr": column_expr(con, p["right"], p["right_key"], canonical, alias="r"),
        "left_attr_expr": column_expr(con, p["left"], p["left_attr"], canonical, alias="l"),
        "right_attr_expr": column_expr(con, p["right"], p["right_attr"], canonical, alias="r"),
        "views": [p["left"], p["right"]],
    }


def _prep_reconciliation(con, p, tol):
    return {
        "left": _ident(p["left"]),
        "right": _ident(p["right"]),
        "left_group_expr": p["left_group_expr"],
        "right_group_expr": p["right_group_expr"],
        "left_measure_expr": p["left_measure_expr"],
        "right_measure_expr": p["right_measure_expr"],
        "left_where": p.get("left_where"),
        "right_where": p.get("right_where"),
        "tolerance": tol["absolute"],
        "views": [p["left"], p["right"]],
    }


def _prep_validity_join(con, p, tol):
    return {
        "table": _ident(p["table"]),
        "key_expr": column_expr(con, p["table"], p["key_column"]),
        "valid_from": _ident(p["valid_from"]),
        "valid_to": _ident(p["valid_to"]),
        "views": [p["table"]],
    }


def _prep_range_join(con, p, tol):
    return {
        "table": _ident(p["table"]),
        "value_expr": column_expr(con, p["table"], p["value_column"]),
        "ranges": _ident(p["ranges"]),
        "range_from": _ident(p["range_from"]),
        "range_to": _ident(p["range_to"]),
        "where": p.get("where"),  # claim scope, e.g. external customers only
        "views": [p["table"], p["ranges"]],
    }


def _prep_decode(con, p, tol):
    return {
        "encoded": _ident(p["encoded"]),
        "decode": _ident(p["decode"]),
        "key": _ident(p["key"]),
        "column": _ident(p["column"]),
        "pairs": p["pairs"],  # [{part_expr, decode_column}] — data-side SQL snippets
        "views": [p["encoded"], p["decode"]],
    }


def _prep_balance(con, p, tol):
    group = p.get("group_column")
    return {
        "journal": _ident(p["journal"]),
        "amount": _ident(p["amount"]),
        "group_expr": f'"{_ident(group)}"' if group else p["group_expr"],
        "tolerance": tol["absolute"],
        "views": [p["journal"]],
    }


def _prep_subledger(con, p, tol):
    accounts = ", ".join(str(int(a)) for a in p["accounts"])
    return {
        "subledger": _ident(p["subledger"]),
        "subledger_amount": _ident(p["subledger_amount"]),
        "journal": _ident(p["journal"]),
        "journal_amount": _ident(p["journal_amount"]),
        "account": _ident(p["account"]),
        "account_list": accounts,
        "tolerance": tol["absolute"],
        "views": [p["subledger"], p["journal"]],
    }


def _prep_ic_symmetry(con, p, tol):
    return {
        "left": _ident(p["left"]),
        "right": _ident(p["right"]),
        "left_period_expr": column_expr(con, p["left"], p["left_period"]),
        "right_period_expr": column_expr(con, p["right"], p["right_period"]),
        "views": [p["left"], p["right"]],
    }


REGISTRY: dict[str, TemplateSpec] = {
    "anti_join": TemplateSpec(
        file="anti_join.sql.j2",
        prepare=_prep_anti_join,
        verdict=verdicts.anti_join_verdict,
        question="Fachfrage: {child} hat Einträge ohne Gegenstück in {parent} — Datenschnitt, Wartezustand oder Fehler?",
    ),
    "duplicate": TemplateSpec(
        file="duplicate.sql.j2",
        prepare=_prep_duplicate,
        verdict=verdicts.empty_expected,
        question="Fachfrage: {table} enthält Dubletten über ({key_list}) — welche Sätze sind führend?",
    ),
    "grain": TemplateSpec(
        file="duplicate.sql.j2",
        prepare=_prep_duplicate,
        verdict=verdicts.empty_expected,
        question="Fachfrage: {table} ist nicht eindeutig auf der angenommenen Körnung ({key_list}) — was ist die echte Körnung?",
    ),
    "coverage": TemplateSpec(
        file="coverage.sql.j2",
        prepare=_prep_coverage,
        verdict=verdicts.coverage_verdict,
        question="Fachfrage: {table} deckt erwartete Einheiten nicht vollständig ab — Datenschnitt oder Lücke?",
    ),
    "cardinality": TemplateSpec(
        file="cardinality.sql.j2",
        prepare=_prep_cardinality,
        verdict=verdicts.cardinality_verdict,
        tolerances={"min_containment": 0.95, "min_uniqueness": 0.99},
    ),
    "attribute_contradiction": TemplateSpec(
        file="attribute_contradiction.sql.j2",
        prepare=_prep_attribute_contradiction,
        verdict=verdicts.empty_expected,
        question="Fachfrage: {left} und {right} widersprechen sich in verknüpften Attributen — welche Quelle führt?",
    ),
    "reconciliation": TemplateSpec(
        file="reconciliation.sql.j2",
        prepare=_prep_reconciliation,
        verdict=verdicts.empty_expected,
        tolerances={"absolute": 0.01},
        question="Fachfrage: {left} und {right} stimmen je Gruppe nicht überein — welche Abgrenzung fehlt?",
    ),
    "validity_join": TemplateSpec(
        file="validity_join.sql.j2",
        prepare=_prep_validity_join,
        verdict=verdicts.empty_expected,
        question="Fachfrage: {table} hat überlappende Gültigkeitszeiträume — welche Version gilt?",
    ),
    "range_join": TemplateSpec(
        file="range_join.sql.j2",
        prepare=_prep_range_join,
        verdict=verdicts.empty_expected,
        question="Fachfrage: Werte aus {table} fallen in keinen oder mehrere Bereiche von {ranges} — wie ist die Zuordnung gemeint?",
    ),
    "decode": TemplateSpec(
        file="decode.sql.j2",
        prepare=_prep_decode,
        verdict=verdicts.empty_expected,
        question="Fachfrage: Positionscodes in {encoded} decodieren nicht eindeutig gegen {decode} — stimmt die Positionslogik?",
    ),
    "balance": TemplateSpec(
        file="balance.sql.j2",
        prepare=_prep_balance,
        verdict=verdicts.empty_expected,
        tolerances={"absolute": 0.01},
        question="Fachfrage: {journal} ist je Gruppe nicht ausgeglichen — fehlt eine Gegenbuchung?",
    ),
    "subledger_equals_gl": TemplateSpec(
        file="subledger_equals_gl.sql.j2",
        prepare=_prep_subledger,
        verdict=verdicts.empty_expected,
        tolerances={"absolute": 0.01},
        question="Fachfrage: Nebenbuch {subledger} weicht vom Hauptbuch {journal} ab — welche Posten fehlen?",
    ),
    "ic_symmetry": TemplateSpec(
        file="ic_symmetry.sql.j2",
        prepare=_prep_ic_symmetry,
        verdict=verdicts.empty_expected,
        question="Fachfrage: Intercompany-Buchungen sind zwischen {left} und {right} nicht symmetrisch — wo fehlt die Gegenseite?",
    ),
}
