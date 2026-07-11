"""Canonicalization: the one value bridge — and the thing T1 attacks."""

from datetime import date, datetime

import duckdb
import pytest

from before_we_ai.sources.canonical import (
    RULE_DATE_TO_ISO,
    RULE_DECIMAL_COMMA,
    RULE_INTEGRAL_FLOAT,
    RULE_NUMERIC_TO_TEXT,
    RULE_TRIMMED,
    canonical_sql_expr,
    canonical_text,
    canonicalize,
)


class TestCanonicalText:
    def test_leading_zeros_in_text_are_sacred(self):
        # T1: genuine text keeps its zeros — canonicalization never
        # guesses that text "is really" a number.
        assert canonicalize("0001042") == ("0001042", None)
        assert canonicalize("DE-INV-0000001") == ("DE-INV-0000001", None)

    def test_integral_float_loses_artifact(self):
        assert canonicalize(1101.0) == ("1101", RULE_INTEGRAL_FLOAT)
        assert canonicalize(-7.0) == ("-7", RULE_INTEGRAL_FLOAT)

    def test_plain_numbers_become_text(self):
        assert canonicalize(1101) == ("1101", RULE_NUMERIC_TO_TEXT)
        assert canonicalize(3.14) == ("3.14", RULE_NUMERIC_TO_TEXT)

    def test_dates_become_iso(self):
        assert canonicalize(date(2025, 1, 15)) == ("2025-01-15", RULE_DATE_TO_ISO)
        # Excel loves midnight datetimes for pure dates.
        assert canonicalize(datetime(2025, 1, 15)) == ("2025-01-15", RULE_DATE_TO_ISO)
        canon, _ = canonicalize(datetime(2025, 1, 15, 9, 30))
        assert canon == "2025-01-15 09:30:00"

    def test_decimal_comma_text(self):
        assert canonicalize("1.234,56") == ("1234.56", RULE_DECIMAL_COMMA)
        assert canonicalize("-12,5") == ("-12.5", RULE_DECIMAL_COMMA)
        # A dot-decimal or plain integer text is NOT rewritten.
        assert canonicalize("1234.56") == ("1234.56", None)
        assert canonicalize("1101") == ("1101", None)

    def test_whitespace(self):
        assert canonicalize("  x ") == ("x", RULE_TRIMMED)
        assert canonicalize("   ") == (None, None)
        assert canonicalize(None) == (None, None)

    def test_idempotent(self):
        for value in ("0001042", 1101.0, "1.234,56", date(2025, 1, 15), " x "):
            once = canonical_text(value)
            assert canonical_text(once) == once


class TestSqlTwin:
    """canonical_sql_expr must agree with canonical_text on shared cases."""

    @pytest.mark.parametrize(
        ("duckdb_type", "literal", "python_value"),
        [
            ("BIGINT", "1101", 1101),
            ("DOUBLE", "1101.0", 1101.0),
            ("DOUBLE", "3.14", 3.14),
            ("DATE", "DATE '2025-01-15'", date(2025, 1, 15)),
            ("TIMESTAMP", "TIMESTAMP '2025-01-15 00:00:00'", datetime(2025, 1, 15)),
            ("TIMESTAMP", "TIMESTAMP '2025-01-15 09:30:00'", datetime(2025, 1, 15, 9, 30)),
            ("VARCHAR", "'0001042'", "0001042"),
            ("VARCHAR", "'  x '", "  x "),
            ("VARCHAR", "'   '", "   "),
            ("BOOLEAN", "true", True),
        ],
    )
    def test_agreement(self, duckdb_type, literal, python_value):
        con = duckdb.connect()
        expr = canonical_sql_expr("v", duckdb_type)
        got = con.execute(f"SELECT {expr} FROM (SELECT {literal} AS v)").fetchone()[0]
        assert got == canonical_text(python_value)
