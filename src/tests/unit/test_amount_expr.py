"""Money arrives as text more often than not, and in more than one format.

`balance` and `subledger_equals_gl` used to sum `CAST(col AS DOUBLE)`,
which survives only the Anglo form. A German export writes `1.234,56`
and the cast *raises* — so the check errors rather than fails, and the
claim ends up untested for a reason nobody reads.

The rule is the one `documents/figures.py` already follows: **never
invent agreement.** The format is decided from the column's own values,
and a column that could be read two ways is refused rather than
resolved by majority — `run_ready` turns that into a skip carrying the
sentence, which is a reader's cue to say which it is.

The frozen corpus stores its amounts in the plain form, so none of this
is exercised there. That is exactly why it is unit-tested here.
"""

import duckdb
import pytest

from before_we_ai.checks.library import amount_expr

pytestmark = pytest.mark.unit


@pytest.fixture
def con():
    return duckdb.connect(":memory:")


def _view(con, values, dtype="VARCHAR"):
    con.execute(f"CREATE TABLE t (amount {dtype})")
    con.executemany("INSERT INTO t VALUES (?)", [[v] for v in values])
    con.execute('CREATE VIEW "v" AS SELECT * FROM t')
    return "v"


def _total(con, view, expr):
    return con.execute(f'SELECT sum({expr}) FROM "{view}"').fetchone()[0]


class TestFormatsItReads:
    def test_a_real_numeric_column_is_left_alone(self, con):
        view = _view(con, [10.5, 20.25], dtype="DOUBLE")
        assert _total(con, view, amount_expr(con, view, "amount")) == 30.75

    def test_plain_text_decimals(self, con):
        """The corpus form — and the one the old cast already handled."""
        view = _view(con, ["304718.22", "-4718.22"])
        assert _total(con, view, amount_expr(con, view, "amount")) == 300000.0

    def test_german_grouped_with_comma_decimals(self, con):
        """The case that used to make the whole check error out."""
        view = _view(con, ["1.234.567,89", "-1.234.567,89", "1.000,11"])
        assert _total(con, view, amount_expr(con, view, "amount")) == \
            pytest.approx(1000.11)

    def test_comma_decimals_without_grouping(self, con):
        view = _view(con, ["1234,56", "-1234,56", "10,00"])
        assert _total(con, view, amount_expr(con, view, "amount")) == \
            pytest.approx(10.0)

    def test_surrounding_whitespace_is_not_a_format(self, con):
        view = _view(con, ["  10.50 ", "20.50"])
        assert _total(con, view, amount_expr(con, view, "amount")) == 31.0

    def test_an_empty_column_is_not_an_error(self, con):
        view = _view(con, [None, None])
        assert _total(con, view, amount_expr(con, view, "amount")) is None


class TestWhatItRefuses:
    """Refusing is the feature. A wrong total is worse than no total,
    because a wrong total passes."""

    def test_two_formats_in_one_column(self, con):
        view = _view(con, ["1.234,56", "9876.54"])
        with pytest.raises(ValueError, match="mixes number formats"):
            amount_expr(con, view, "amount")

    def test_a_column_where_every_dot_could_be_either(self, con):
        """`1.234` is one thousand two hundred thirty four, or it is one
        point two three four. Nothing in the column decides it, so the
        check does not either."""
        view = _view(con, ["1.234", "5.678"])
        with pytest.raises(ValueError, match="ambiguous"):
            amount_expr(con, view, "amount")

    def test_a_column_that_is_not_numbers(self, con):
        view = _view(con, ["10.00", "n/a"])
        with pytest.raises(ValueError, match="not numbers at all"):
            amount_expr(con, view, "amount")

    def test_the_refusal_names_the_column(self, con):
        view = _view(con, ["1.234", "5.678"])
        with pytest.raises(ValueError, match='"v"."amount"'):
            amount_expr(con, view, "amount")


def test_three_decimals_are_fine_when_the_column_settles_it(con):
    """A single unambiguous value is enough to decide the whole column:
    `0.5` cannot be a thousands group, so the dots are decimal points and
    `1.234` is one point two three four."""
    view = _view(con, ["1.234", "0.5"])
    assert _total(con, view, amount_expr(con, view, "amount")) == \
        pytest.approx(1.734)
