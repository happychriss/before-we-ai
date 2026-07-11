"""One canonical text form for every value, used everywhere.

This is the bridge that lets BIGINT ``1101``, DOUBLE ``1101.0``, an Excel
number cell ``1101`` and the text ``'1101'`` meet in the overlap stage.
Two invariants matter more than any cleverness:

* Genuine text is preserved untouched — ``'0001042'`` keeps its leading
  zeros (T1). Canonicalization never guesses that text "is really" a
  number.
* Every kind of rewrite has a name (a rule tag), so the ingestion layer
  can declare what it did. New rules are added here, one function-case
  and one unit test at a time; downstream consumers only ever see the
  output.
"""

import re
from datetime import date, datetime

# Rule tags — the vocabulary of normalization declarations.
RULE_NUMERIC_TO_TEXT = "numeric_to_text"
RULE_INTEGRAL_FLOAT = "integral_float_to_text"
RULE_DATE_TO_ISO = "date_to_iso"
RULE_DATETIME_TO_ISO = "datetime_to_iso"
RULE_DECIMAL_COMMA = "decimal_comma_to_dot"
RULE_TRIMMED = "trimmed_whitespace"

# German-convention numbers in text: optional dot-thousands, comma decimal.
_DECIMAL_COMMA = re.compile(r"^-?\d{1,3}(\.\d{3})*,\d+$|^-?\d+,\d+$")


def canonicalize(value: object) -> tuple[str | None, str | None]:
    """Return ``(canonical_text, rule_tag)``; rule is None when untouched.

    ``None`` and empty/whitespace-only strings canonicalize to ``None``.
    """
    if value is None:
        return None, None
    if isinstance(value, bool):
        return ("true" if value else "false"), RULE_NUMERIC_TO_TEXT
    if isinstance(value, int):
        return str(value), RULE_NUMERIC_TO_TEXT
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value)), RULE_INTEGRAL_FLOAT
        return repr(value), RULE_NUMERIC_TO_TEXT
    if isinstance(value, datetime):
        if (value.hour, value.minute, value.second, value.microsecond) == (0, 0, 0, 0):
            return value.date().isoformat(), RULE_DATE_TO_ISO
        return value.isoformat(sep=" "), RULE_DATETIME_TO_ISO
    if isinstance(value, date):
        return value.isoformat(), RULE_DATE_TO_ISO
    text = str(value)
    stripped = text.strip()
    if not stripped:
        return None, None
    if _DECIMAL_COMMA.match(stripped):
        return stripped.replace(".", "").replace(",", "."), RULE_DECIMAL_COMMA
    if stripped != text:
        return stripped, RULE_TRIMMED
    return text, None


def canonical_text(value: object) -> str | None:
    """The canonical text form alone (see :func:`canonicalize`)."""
    return canonicalize(value)[0]


def canonical_sql_expr(column: str, duckdb_type: str) -> str:
    """The SQL twin of :func:`canonical_text` for a DuckDB column.

    Must agree with the Python side on shared cases (unit-tested), so
    values from attached databases and values from normalized files land
    in the same form.
    """
    quoted = f'"{column}"'
    base = duckdb_type.upper().split("(")[0].strip()
    if base in ("TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
                "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT"):
        return f"CAST({quoted} AS VARCHAR)"
    if base in ("FLOAT", "DOUBLE", "REAL", "DECIMAL", "NUMERIC"):
        return (
            f"CASE WHEN {quoted} = trunc({quoted}) "
            f"THEN CAST(CAST({quoted} AS BIGINT) AS VARCHAR) "
            f"ELSE CAST({quoted} AS VARCHAR) END"
        )
    if base == "DATE":
        return f"strftime({quoted}, '%Y-%m-%d')"
    if base in ("TIMESTAMP", "TIMESTAMP WITH TIME ZONE", "DATETIME", "TIMESTAMPTZ"):
        return (
            f"CASE WHEN {quoted} = date_trunc('day', {quoted}) "
            f"THEN strftime({quoted}, '%Y-%m-%d') "
            f"ELSE strftime({quoted}, '%Y-%m-%d %H:%M:%S') END"
        )
    if base == "BOOLEAN":
        return f"CASE WHEN {quoted} THEN 'true' ELSE 'false' END"
    # Text stays text; NULLIF folds empty-after-trim into NULL like Python.
    return f"NULLIF(trim({quoted}), '')"
