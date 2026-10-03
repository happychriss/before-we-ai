"""The check definition registry.

One entry per template, and a new template exists only because a corpus
case forces it (Regel gegen Wildwuchs): anti_join (T1/F1/F5), duplicate/
grain (T11/F2), coverage (T12/F16), cardinality (T6), attribute_
contradiction (F5-continuity), reconciliation (F27), validity_join (F6),
range_join (F9), decode (F7), and the invariants balance (Z4/F22),
subledger_equals_gl (F20), ic_symmetry (F22).

Each spec knows its SQL file, how to build the Jinja context from check
params (``prepare``), its deterministic verdict function, its default
tolerances (overridable ONLY via before-ai.yaml), what it tries to break in
business words (``tests``, rendered in the readiness report), and the
clarification question it drafts on FAIL/INCONCLUSIVE.
"""

import re
from dataclasses import dataclass, field
from typing import Callable

from before_we_ai.checks import verdicts
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


# Four disjoint readings of one text value. Disjoint is the whole point:
# `1.234` matches "a number with a decimal point" AND "a number with a
# thousands group", so a classifier that lets those two overlap counts it
# twice and concludes whatever it happened to test first.
_EUROPEAN = r'^-?[0-9.]*[0-9],[0-9]+$'        # 1234,56 · 1.234.567,89
_GROUPED = r'^-?[0-9]{1,3}(\.[0-9]{3}){2,}$'  # 1.234.567 — two dots settle it
_AMBIGUOUS = r'^-?[0-9]+\.[0-9]{3}$'          # 1.234 — could be either
_PLAIN = r'^-?[0-9]+(\.[0-9]+)?$'             # 304718.22 · 0.5 · 42


def amount_expr(con, view: str, column: str, alias: str | None = None) -> str:
    """A DOUBLE expression for an amount column, whatever it is stored as.

    Exports arrive with money as text more often than not, and a bare
    ``CAST(col AS DOUBLE)`` only survives the Anglo form: ``1.234,56``
    raises, so the check *errors* instead of failing and the claim ends
    up untested for a reason nobody reads.

    The format is decided from the column's own values, never guessed
    per row, and the rule is the one ``documents/figures.py`` already
    follows: **never invent agreement.** A column whose only dotted
    values could be read two ways (``1.234`` — one thousand two hundred
    thirty four, or one point two three four) is refused rather than
    resolved by majority. `run_ready` turns that refusal into a skip
    carrying this sentence, which is a reader's cue to say which it is.
    """
    _ident(view), _ident(column)
    if alias:
        _ident(alias)
    quoted = f'"{alias}"."{column}"' if alias else f'"{column}"'
    dtype = next(
        r[1] for r in con.execute(f'DESCRIBE "{view}"').fetchall() if r[0] == column
    ).upper().split("(")[0].strip()
    if dtype != "VARCHAR":
        return f"CAST({quoted} AS DOUBLE)"

    trimmed = f"trim({quoted})"
    european, grouped, ambiguous, plain, total = con.execute(f'''
        SELECT
          count(*) FILTER (WHERE regexp_matches({trimmed}, '{_EUROPEAN}')),
          count(*) FILTER (WHERE regexp_matches({trimmed}, '{_GROUPED}')),
          count(*) FILTER (WHERE regexp_matches({trimmed}, '{_AMBIGUOUS}')),
          count(*) FILTER (WHERE regexp_matches({trimmed}, '{_PLAIN}')),
          count(*) FILTER (WHERE {trimmed} IS NOT NULL AND {trimmed} <> '')
        FROM "{view}"
    ''').fetchone()
    if total == 0:
        return f"CAST({quoted} AS DOUBLE)"  # nothing to read; let it be empty

    # `_PLAIN` swallows `_AMBIGUOUS`; everything else is already disjoint.
    decisive_european = european + grouped
    decisive_plain = plain - ambiguous
    recognized = decisive_european + plain

    if recognized < total:
        raise ValueError(
            f'"{view}"."{column}" holds {total - recognized} value(s) that '
            f"are not numbers at all; it cannot be summed as an amount."
        )
    if decisive_european and decisive_plain:
        raise ValueError(
            f'"{view}"."{column}" mixes number formats — some values read as '
            f"1234.56 and some as 1.234,56. Which one this column uses is a "
            f"fact about the export, not something a check may decide."
        )
    if decisive_european:
        # Dots are grouping, the comma is the point. An ambiguous `1.234`
        # riding along in this column reads as 1234, which is what the
        # rest of the column says it must be.
        return (f"CAST(replace(replace({trimmed}, '.', ''), ',', '.') "
                f"AS DOUBLE)")
    if not decisive_plain:
        raise ValueError(
            f'"{view}"."{column}" is ambiguous: every dotted value has '
            f"exactly three decimals, so 1.234 could be one thousand two "
            f"hundred thirty four or one point two three four. Nothing in "
            f"the column settles it, so a check may not either."
        )
    return f"CAST({trimmed} AS DOUBLE)"


@dataclass
class CheckDefinition:
    file: str
    prepare: Callable  # (con, params, tolerances) -> jinja context
    verdict: Callable  # (rows, columns, ctx) -> verdicts.Assessment
    tolerances: dict[str, float] = field(default_factory=dict)
    question: str | None = None  # clarification question template, formatted with the context
    # What this check tries to break, in the words a business reader thinks
    # in — rendered in the readiness report so a check plan is legible
    # without reading its SQL. Never enters a prompt: the model is shown
    # `TEMPLATE_PARAMS` / `TEMPLATE_NOTES` from `llm/vocabulary.py`, not this.
    tests: str = ""
    # None = generic data check, works in any domain. A domain name marks a
    # domain law — these templates are part of that domain's pack, and what
    # is domain-specific must always be enumerable (the product is a general
    # machine only together with a domain pack, never on its own).
    domain: str | None = None
    # Slot params of a domain law: {param that takes a column: param that
    # names the view it sits on}. A domain guide's *fields* declare which of
    # these slots they fill (``fills:``), and a passing run of the law settles
    # exactly those fields — with the column the run actually consumed.
    #
    # Only params the law truly *identifies* belong here. A journal balances
    # per document AND per period AND per year, so ``group_column`` is NOT a
    # slot: a pass says nothing about what the grouping column means. The
    # amount is different — conserving to zero is the whole definition of the
    # posting amount, and it is what the run measured.
    slots: dict[str, str] = field(default_factory=dict)


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


_BARE_COLUMN = re.compile(r'^"?([A-Za-z_][A-Za-z0-9_]*)"?$')


def measure_expr(con, view: str, expression: str) -> str:
    """Read a reconciliation measure as an amount when it names a column.

    ``reconciliation`` differs from ``balance`` and ``subledger_equals_gl``
    on purpose: its measures are row-level arithmetic, so the template
    cannot know which column carries the number and the prompt says as
    much. But *most* measures are just a column name, and for those the
    template does know — so those get the same treatment the two amount
    templates get, and a German export stops depending on the model having
    remembered to write the cast.

    Anything with an operator in it is the model's expression and is left
    exactly as written. A bare name that is not a column of the view is
    also left alone: it may be a literal, and inventing a reading for it
    would be the guesswork this function exists to avoid.
    """
    match = _BARE_COLUMN.match(expression.strip())
    if match is None:
        return expression
    column = match.group(1)
    columns = {row[0] for row in con.execute(f'DESCRIBE "{view}"').fetchall()}
    if column not in columns:
        return expression
    return amount_expr(con, view, column)


def _prep_reconciliation(con, p, tol):
    return {
        "left": _ident(p["left"]),
        "right": _ident(p["right"]),
        "left_group_expr": p["left_group_expr"],
        "right_group_expr": p["right_group_expr"],
        "left_measure_expr": measure_expr(con, p["left"],
                                          p["left_measure_expr"]),
        "right_measure_expr": measure_expr(con, p["right"],
                                           p["right_measure_expr"]),
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
        # The amount arrives however the export wrote it; reading it as a
        # number is ours to do, not the model's to phrase.
        "amount_expr": amount_expr(con, p["journal"], p["amount"]),
        "group_expr": f'"{_ident(group)}"' if group else p["group_expr"],
        "tolerance": tol["absolute"],
        "views": [p["journal"]],
    }


def _prep_subledger(con, p, tol):
    accounts = ", ".join(str(int(a)) for a in p["accounts"])
    return {
        "subledger": _ident(p["subledger"]),
        "subledger_amount": _ident(p["subledger_amount"]),
        "subledger_amount_expr": amount_expr(
            con, p["subledger"], p["subledger_amount"]),
        "journal": _ident(p["journal"]),
        "journal_amount": _ident(p["journal_amount"]),
        "journal_amount_expr": amount_expr(
            con, p["journal"], p["journal_amount"]),
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


REGISTRY: dict[str, CheckDefinition] = {
    "anti_join": CheckDefinition(
        file="anti_join.sql.j2",
        prepare=_prep_anti_join,
        verdict=verdicts.anti_join_verdict,
        tests="Every entry on one side must have a counterpart on the other. It looks for the ones that do not.",
        question="{child} has entries with no counterpart in {parent} — is that a legitimate data cut, a pending state, or an error?",
    ),
    "duplicate": CheckDefinition(
        file="duplicate.sql.j2",
        prepare=_prep_duplicate,
        verdict=verdicts.empty_expected,
        tests="The named columns should identify a record once. It looks for records that appear more than once.",
        question="{table} contains duplicates over ({key_list}) — which records are authoritative?",
    ),
    "grain": CheckDefinition(
        file="duplicate.sql.j2",
        prepare=_prep_duplicate,
        verdict=verdicts.empty_expected,
        tests="One row should mean one thing. It looks for the key that was assumed to identify a row failing to do so.",
        question="{table} is not unique on the assumed grain ({key_list}) — what identifies exactly one row?",
    ),
    "coverage": CheckDefinition(
        file="coverage.sql.j2",
        prepare=_prep_coverage,
        verdict=verdicts.coverage_verdict,
        tests="All the units that were expected should be present. It looks for the ones that are missing.",
        question="{table} does not cover all the units that were expected — is that a legitimate data cut, or a gap?",
    ),
    "cardinality": CheckDefinition(
        file="cardinality.sql.j2",
        prepare=_prep_cardinality,
        verdict=verdicts.cardinality_verdict,
        tests="A link between two columns should hold for nearly every value, and point at one record. It measures how far short it falls.",
        tolerances={"min_containment": 0.95, "min_uniqueness": 0.99},
    ),
    "attribute_contradiction": CheckDefinition(
        file="attribute_contradiction.sql.j2",
        prepare=_prep_attribute_contradiction,
        verdict=verdicts.empty_expected,
        tests="Two sources describing the same thing should agree about it. It looks for the records where they say different things.",
        question="{left} and {right} contradict each other on linked attributes — which source leads?",
    ),
    "reconciliation": CheckDefinition(
        file="reconciliation.sql.j2",
        prepare=_prep_reconciliation,
        verdict=verdicts.empty_expected,
        tests="Two sets of figures that describe the same thing should add up to the same total per group. It looks for the groups where they do not.",
        tolerances={"absolute": 0.01},
        question="{left} and {right} do not agree per group — which cutoff or accrual is missing?",
    ),
    "validity_join": CheckDefinition(
        file="validity_join.sql.j2",
        prepare=_prep_validity_join,
        verdict=verdicts.empty_expected,
        tests="Only one version of a record should be valid at any moment. It looks for validity periods that overlap.",
        question="{table} has overlapping validity periods — which version applies?",
    ),
    "range_join": CheckDefinition(
        file="range_join.sql.j2",
        prepare=_prep_range_join,
        verdict=verdicts.empty_expected,
        tests="Every value should fall into exactly one of the declared ranges. It looks for values that fall into none, or into several.",
        question="values from {table} fall into no range or several ranges of {ranges} — how is the assignment meant?",
    ),
    "decode": CheckDefinition(
        file="decode.sql.j2",
        prepare=_prep_decode,
        verdict=verdicts.empty_expected,
        tests="A code built from positions should resolve to exactly one meaning. It looks for codes that do not.",
        question="positional codes in {encoded} do not decode uniquely against {decode} — is the positional logic right?",
    ),
    "balance": CheckDefinition(
        file="balance.sql.j2",
        prepare=_prep_balance,
        verdict=verdicts.empty_expected,
        tests="Debits and credits must cancel out within every group of postings. It looks for groups where money appears or disappears.",
        tolerances={"absolute": 0.01},
        question="{journal} does not balance per group — is an offsetting entry missing?",
        domain="finance",
        slots={"amount": "journal"},
    ),
    "subledger_equals_gl": CheckDefinition(
        file="subledger_equals_gl.sql.j2",
        prepare=_prep_subledger,
        verdict=verdicts.empty_expected,
        tests="A subledger must add up to the general-ledger account it belongs to. It looks for the amounts that are in one and not the other.",
        tolerances={"absolute": 0.01},
        question="subledger {subledger} deviates from the general ledger {journal} — which items are missing?",
        domain="finance",
        slots={"subledger_amount": "subledger"},
    ),
    "ic_symmetry": CheckDefinition(
        file="ic_symmetry.sql.j2",
        prepare=_prep_ic_symmetry,
        verdict=verdicts.empty_expected,
        tests="A posting between two entities must appear on both sides, with opposite signs. It looks for the legs that have no counterpart.",
        question="intercompany postings are not symmetric between {left} and {right} — where is the counterpart missing?",
        domain="finance",
    ),
}
