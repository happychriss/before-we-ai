"""The multi-anchor rule, branch by branch.

T8's negatives are the point of this module, so each of them gets a test
that says which trap it is: a chart-only figure (F23), a restatement
(F24/K7), a coincidental match from a noise document (F26). K3 — the
accounting policy resolving a rule the data cannot show — is the positive
case the rule must *not* block.
"""

from decimal import Decimal

import pytest

from before_we_ai.core import Actor, EvidenceType
from before_we_ai.core.objects import EvidenceRecord
from before_we_ai.documents.reconcile import (
    CHART_ONLY,
    NO_AGREEMENT,
    RESTATEMENT,
    SINGLE_ANCHOR,
    corroborate,
    ground_definition,
)

pytestmark = pytest.mark.unit

Q3_ACTUAL = Decimal("2847000")


def anchor(quote, *, source="management_report", page=1, kind="text"):
    return EvidenceRecord(
        type=EvidenceType.DOCUMENT_ANCHOR,
        actor=Actor.AI,
        claim_id="c1",
        payload={"quote": quote, "chunk_id": f"{source}:p{page}:0",
                 "kind": kind, "source": source, "page": page},
    )


def codes(result):
    return {concern.code for concern in result.concerns}


# -- value corroboration ---------------------------------------------------

def test_two_independent_documents_agreeing_may_link():
    result = corroborate([
        anchor("Q3 revenue was EUR 2,847,000."),
        anchor("Third quarter revenue: 2,847,000", source="board_pack"),
    ], Q3_ACTUAL)
    assert result.may_link
    assert "2 independent documents agree" in result.reason


def test_one_document_plus_the_data_may_link():
    result = corroborate([anchor("Q3 revenue was EUR 2,847,000.")],
                         Q3_ACTUAL, check_supported=True)
    assert result.may_link
    assert "agrees with what the data produces" in result.reason


def test_one_document_alone_may_not_link():
    result = corroborate([anchor("Q3 revenue was EUR 2,847,000.")], Q3_ACTUAL)
    assert not result.may_link
    assert SINGLE_ANCHOR in codes(result)


def test_two_anchors_on_the_same_page_are_one_witness():
    """Independence is about documents, not about how often one repeats."""
    result = corroborate([
        anchor("Q3 revenue was EUR 2,847,000."),
        anchor("As stated, EUR 2,847,000 for the quarter."),
    ], Q3_ACTUAL)
    assert not result.may_link
    assert SINGLE_ANCHOR in codes(result)


def test_f23_a_chart_only_figure_never_corroborates():
    """Two anchors, but both are pictures of a number."""
    result = corroborate([
        anchor("[Chart: Q3 Revenue by Region]\nEUR 2,847,000", kind="chart"),
        anchor("EUR 2,847,000", source="board_pack", kind="chart"),
    ], Q3_ACTUAL)
    assert not result.may_link
    assert codes(result) == {CHART_ONLY}


def test_f23_a_chart_cannot_be_the_second_witness_for_a_text_anchor():
    result = corroborate([
        anchor("Q3 revenue was EUR 2,847,000."),
        anchor("EUR 2,847,000", source="board_pack", kind="chart"),
    ], Q3_ACTUAL)
    assert not result.may_link
    assert CHART_ONLY in codes(result)


def test_f24_a_restatement_is_never_reconciled_to_one_of_its_figures():
    result = corroborate([
        anchor("Prior year Q1 2023 revenue: EUR 3,200,000 "
               "(restated from EUR 3,050,000)."),
        anchor("Q1 2023 revenue 3,200,000", source="board_pack"),
    ], Decimal("3200000"))
    assert not result.may_link
    assert RESTATEMENT in codes(result)
    assert "a decision, not a calculation" in result.reason or any(
        "decision" in c.detail for c in result.concerns)


def test_f24_a_restatement_beats_otherwise_sufficient_agreement():
    """Even two independent documents cannot settle which figure applies."""
    result = corroborate([
        anchor("Revenue 3,200,000 (restated from 3,050,000)."),
        anchor("Revenue 3,200,000 (restated from 3,050,000).", source="other"),
    ], Decimal("3200000"))
    assert not result.may_link


def test_f26_a_coincidental_figure_from_a_noise_document_is_refused():
    """The divested-unit press release must be present and refused."""
    result = corroborate([
        anchor("Mit dem Verkauf unserer Industriesparte erzielte die Gruppe "
               "einen Erloes von EUR 8.450.000",
               source="pressemitteilung_2022_divested_unit"),
    ], Q3_ACTUAL)
    assert not result.may_link
    assert NO_AGREEMENT in codes(result)


def test_many_coincidental_figures_still_corroborate_nothing():
    result = corroborate([
        anchor("EUR 8.450.000", source="press"),
        anchor("EUR 1,200,000", source="pipeline"),
        anchor("EUR 500.000", source="rebates"),
    ], Q3_ACTUAL)
    assert not result.may_link
    assert codes(result) == {NO_AGREEMENT}


def test_an_ambiguous_figure_does_not_become_a_witness():
    """500.000 matches only if we assume a locale — so it does not match."""
    result = corroborate([
        anchor("Volume above EUR 500.000 earns 2%.", source="rebates"),
        anchor("Threshold is 500,000", source="board_pack"),
    ], Decimal("500000"))
    assert not result.may_link


def test_a_rounded_figure_is_a_witness():
    result = corroborate([
        anchor("Revenue of about 2,850,000 in the quarter."),
        anchor("Roughly 2,850,000", source="board_pack"),
    ], Q3_ACTUAL)
    assert result.may_link


def test_no_anchors_at_all_says_so_plainly():
    result = corroborate([], Q3_ACTUAL)
    assert not result.may_link
    assert "nothing found" in result.reason


def test_non_anchor_evidence_is_ignored(tmp_path):
    declaration = EvidenceRecord(
        type=EvidenceType.DECLARATION, actor=Actor.SYSTEM, claim_id="c1",
        payload={"rule": "csv_read_all_varchar"},
    )
    result = corroborate([declaration, anchor("EUR 2,847,000")], Q3_ACTUAL)
    assert len(result.assessed) == 1


def test_the_trail_shows_what_counted_and_what_did_not():
    result = corroborate([
        anchor("Q3 revenue was EUR 2,847,000."),
        anchor("EUR 2,847,000", source="board_pack", kind="chart"),
    ], Q3_ACTUAL)
    assert [a.source for a in result.counting] == ["management_report"]
    assert [a.source for a in result.disregarded] == ["board_pack"]


# -- definitional grounding ------------------------------------------------

def test_k3_one_policy_stating_a_rule_may_link():
    """The positive case. A sign convention lives in a policy, not a column."""
    result = ground_definition([
        anchor("Haben-Betraege werden als negative Zahlen gebucht "
               "(Haben-Konvention).", source="buchhaltungsrichtlinie"),
    ])
    assert result.may_link
    assert "buchhaltungsrichtlinie p.1" in result.reason


def test_k3_linking_does_not_pretend_the_claim_is_settled():
    """A link is not evidence — the reason must say what still has to happen."""
    result = ground_definition([
        anchor("Umsatzerloese = Konten 4000-4999.", source="policy"),
    ])
    assert "stays proposed" in result.reason


def test_a_rule_read_off_a_chart_is_not_a_rule():
    result = ground_definition([anchor("Revenue = 4000-4999", kind="chart")])
    assert not result.may_link
    assert CHART_ONLY in codes(result)


def test_a_definition_with_no_passage_at_all_may_not_link():
    result = ground_definition([])
    assert not result.may_link
