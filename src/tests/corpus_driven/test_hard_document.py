"""The hard document — including, deliberately, where it wins.

``acme_annual_extract.pdf`` collects the ways published reports actually
defeat a document pipeline. Half of these tests pin behaviour that works;
the other half pin behaviour that **does not**, and those are the more
valuable ones. A limitation with a test against it is a known limitation:
it has a name, a failing case, and it turns red the day someone fixes it
by accident. A limitation without a test is just something we have not
noticed yet.

Nothing here is a promotion path, which is why the defeats are survivable:
an anchor is weak evidence and a misread figure cannot move a status. The
cost of each one is a worse proposal or a missed link, never a wrong
answer presented as right.

This document is NOT the spec's real public PDF (see
``corpus/build_hard_document.py``); that item stays open.
"""

from decimal import Decimal
from pathlib import Path

import pytest

from before_we_ai.documents.chunk import chunk_pdf
from before_we_ai.documents.extract import CHART, TABLE, TEXT
from before_we_ai.documents.figures import distinct_values

pytestmark = pytest.mark.acceptance

DOCUMENT = (Path(__file__).resolve().parents[2] / "corpus" / "data" / "hard"
            / "acme_annual_extract.pdf")
NAME = "acme_annual_extract"


@pytest.fixture(scope="module")
def chunks():
    return chunk_pdf(DOCUMENT, NAME)


def carrying(chunks, needle):
    return [c for c in chunks if needle in c.text]


def only(chunks, needle):
    found = carrying(chunks, needle)
    assert len(found) == 1, f"expected one chunk carrying {needle!r}, got {len(found)}"
    return found[0]


# -- what holds ------------------------------------------------------------

def test_it_reads_at_all(chunks):
    assert len({c.page for c in chunks}) == 3
    assert [c.id for c in chunks] == sorted(c.id for c in chunks)


def test_h9_a_real_charts_figure_is_derived_as_chart(chunks):
    """The figure exists nowhere else in the document, so this is the
    only thing standing between it and a corroboration it never earned."""
    assert only(chunks, "2,847,000").kind == CHART


def test_h2_thin_space_grouping_reads_as_one_number(chunks):
    """8 312 504 is one figure. Read as three, it is not wrong — it is noise."""
    chunk = only(chunks, "312")
    assert Decimal("8312504") in distinct_values(chunk.text)


def test_h3_an_accounting_negative_keeps_its_sign(chunks):
    """(1,204,880) is a cost. Read as positive it is a windfall."""
    chunk = only(chunks, "1,204,880")
    assert Decimal("-1204880") in distinct_values(chunk.text)


def test_a_ruled_table_is_still_found_among_the_noise(chunks):
    assert only(chunks, "Result before tax").kind == TABLE


def test_the_policy_page_reads_as_plain_text(chunks):
    """The three rules M5 exists to reach are ordinary prose, as they
    always are in real documents."""
    page = only(chunks, "monthly average rates")
    assert page.kind == TEXT
    assert "Credit amounts are recorded as negative values" in page.text


def test_chunk_ids_are_stable_across_reads():
    assert [c.id for c in chunk_pdf(DOCUMENT, NAME)] == \
           [c.id for c in chunk_pdf(DOCUMENT, NAME)]


# -- what defeats it, on purpose and on the record -------------------------

def test_h1_a_scale_heading_away_from_its_figures_is_not_applied(chunks):
    """KNOWN LIMITATION. "All figures in EUR thousands" sits in one chunk
    and 8,313 in another, and nothing connects them.

    Deliberately not fixed. Carrying a scale across chunks means inferring
    that a heading governs a number some distance away — and an inference
    that silently multiplies a figure by a thousand is exactly the kind
    that must never be made quietly. The figure stays as written; a reader
    sees the heading in the anchor's neighbourhood.
    """
    table = only(chunks, "Result before tax")
    assert "8,313" in table.text
    assert "thousands" not in table.text  # the scale is on another chunk
    assert Decimal("8313000") not in distinct_values(table.text)


def test_h4_a_table_without_ruling_lines_is_read_as_prose(chunks):
    """KNOWN LIMITATION, and a conservative one.

    PyMuPDF finds tables by their lines; a whitespace-aligned table has
    none. Its rows arrive labelled `text`, which is the *permissive*
    direction — a figure from it could corroborate. That is defensible
    (the numbers really are stated in the document) but it is not what a
    reader would call the passage, and it is the first thing a better
    layout analyser would fix.
    """
    assert only(chunks, "5,884,190").kind == TEXT


def test_h5_a_bordered_pull_quote_is_called_a_chart(chunks):
    """KNOWN LIMITATION, conservative in the safe direction.

    A box is a box; the geometry cannot tell a figure from a callout. The
    consequence is that a quotable sentence inside a border can never
    corroborate a figure — a false refusal, never a false promotion, which
    is the right way round for this system to be wrong.
    """
    assert only(chunks, "flatter the growth rate").kind == CHART


def test_h6_a_footnote_restatement_is_caught_only_when_it_shares_a_chunk(chunks):
    """Half a win. The footnote and the figure it restates land in one
    chunk here, so the restatement is visible. Had the page been longer
    they would not have, and only the cross-anchor path would catch it."""
    from before_we_ai.documents.figures import restated_values

    chunk = only(chunks, "3,050,000")
    assert restated_values(chunk.text, Decimal("3200000")) == [
        Decimal("3200000"), Decimal("3050000")]


def test_h7_a_hyphenated_word_break_survives_in_the_text(chunks):
    """KNOWN LIMITATION. "intercom-\\npany" is how the document prints it,
    so that is what a quote of it must contain. De-hyphenating would make
    the stored quote differ from the page, and the anchor's whole value is
    that it points at words that are really there."""
    assert any("intercom-" in c.text for c in chunks)


def test_h8_running_headers_land_in_content_chunks(chunks):
    """KNOWN LIMITATION. The header and footer are just text blocks in the
    same positions as any other, so they ride along in whichever chunk
    they fall into. Harmless for anchoring — a quote is matched against
    the chunk, and no model will quote a page number as a policy — but it
    inflates the passages the model reads."""
    assert any("Page 1 of 3" in c.text for c in chunks)
