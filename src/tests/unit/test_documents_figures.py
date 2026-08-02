"""Reading numbers must never manufacture the agreement it reports."""

from decimal import Decimal

import pytest

from before_we_ai.documents.figures import (
    compare,
    distinct_values,
    match_quote,
    read_figure,
    read_figures,
    restated_values,
)

pytestmark = pytest.mark.unit

EXACT = "exact"
ROUNDED = "rounded"
COINCIDENTAL = "coincidental_candidate"


def test_a_comma_grouped_integer_reads_one_way_only():
    figure = read_figure("2,847,000")
    assert figure.readings == (Decimal("2847000"),)
    assert not figure.ambiguous


def test_a_dot_grouped_integer_reads_one_way_only():
    figure = read_figure("8.450.000")
    assert figure.readings == (Decimal("8450000"),)


def test_a_single_separated_group_is_ambiguous():
    """500.000 is half a million, or five hundred. The document does not say."""
    figure = read_figure("500.000")
    assert set(figure.readings) == {Decimal("500000"), Decimal("500.000")}
    assert figure.ambiguous
    assert figure.value is None


def test_a_plain_integer_is_never_ambiguous():
    assert read_figure("2847000").readings == (Decimal("2847000"),)


def test_a_two_digit_tail_cannot_be_a_thousands_group():
    """Grouping means groups of three, so 1,25 has only one reading."""
    assert read_figure("1,25").readings == (Decimal("1.25"),)


def test_a_three_digit_tail_is_genuinely_ambiguous():
    figure = read_figure("-1,500")
    assert set(figure.readings) == {Decimal("-1500"), Decimal("-1.500")}
    assert figure.ambiguous


def test_irregular_grouping_is_not_a_number_we_pretend_to_understand():
    assert read_figure("1,23,456").readings == ()


def test_figures_come_back_in_writing_order():
    figures = read_figures("Revenue 3,200,000 restated from 3,050,000.")
    assert [f.value for f in figures] == [Decimal("3200000"), Decimal("3050000")]


def test_an_exact_hit_is_exact():
    assert compare(read_figure("2,847,000"), Decimal("2847000")) == EXACT


def test_a_document_rounding_of_the_real_number_is_rounded():
    assert compare(read_figure("2,850,000"), Decimal("2847000")) == ROUNDED


def test_a_number_that_simply_differs_is_a_coincidence_candidate():
    assert compare(read_figure("8,450,000"), Decimal("2847000")) == COINCIDENTAL


def test_an_ambiguous_literal_never_reports_agreement():
    """The heart of it: one reading matches, so agreement is our assumption."""
    assert compare(read_figure("500.000"), Decimal("500000")) == COINCIDENTAL
    assert compare(read_figure("500.000"), Decimal("500")) == COINCIDENTAL


def test_the_best_figure_in_a_quote_wins():
    quote = "Prior year 3,200,000 (restated from 3,050,000)."
    match, figure = match_quote(quote, Decimal("3050000"))
    assert match == EXACT
    assert figure.literal == "3,050,000"


def test_a_quote_with_no_matching_figure_matches_nothing():
    match, _ = match_quote("Revenue rose in the third quarter.", Decimal("1"))
    assert match == COINCIDENTAL


def test_a_period_label_is_not_a_figure():
    """"Q3" is a quarter. Reading it as the number 3 would make every
    heading look like data."""
    assert distinct_values("Q3 revenue was EUR 2,847,000.") == [Decimal("2847000")]


def test_ambiguous_literals_are_not_offered_as_stated_values():
    assert distinct_values("Volume above EUR 500.000 earns 2%.") == [Decimal("2")]


def test_a_restatement_offers_two_figures_for_one_slot():
    """F24's shape — this is what marks the quote as needing a human."""
    assert restated_values(
        "Prior year Q1 2023 revenue: EUR 3,200,000 (restated from EUR 3,050,000)."
    ) == [Decimal("3200000"), Decimal("3050000")]


def test_a_year_beside_an_amount_is_not_a_restatement():
    """Two numbers in a sentence prove nothing; two of a size do."""
    assert restated_values("In 2024 revenue was EUR 8,312,504.") == []


def test_a_clean_citation_restates_nothing():
    assert restated_values("Q3 revenue was EUR 2,847,000.") == []


def test_rounding_respects_the_precision_the_document_chose():
    assert compare(read_figure("8,3"), Decimal("8.31")) == ROUNDED
    assert compare(read_figure("2850000"), Decimal("2847000")) == ROUNDED
    assert compare(read_figure("2800000"), Decimal("2847000")) == ROUNDED
    assert compare(read_figure("3000000"), Decimal("2847000")) == ROUNDED
    # Rounding must agree at the document's own precision, not merely be
    # nearby: 2,847,000 to two significant digits is 2.8 million.
    assert compare(read_figure("2900000"), Decimal("2847000")) == COINCIDENTAL
