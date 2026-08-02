"""The real annual report — the one document nobody wrote for us.

The spec makes a genuine public PDF a Pflichtbestandteil because a
generator only builds the traps it already knows about
(``fixture-korpus-spezifikation.md``). This is that document: 146 pages of
published Bosch annual report, designed in InDesign, encrypted, bilingual.

These tests are slower than the rest of the suite and worth it. Everything
they pin was learned from the document rather than designed before it, and
the three named ``R`` findings below are the ones that changed code or
would change it next.

The document is deliberately **not** a walkthrough source: 539 passages
would make one V3 call the size of the whole rest of the corpus. It is
read here, end to end, to prove the pipeline survives a real page.
"""

import unicodedata
from collections import Counter
from pathlib import Path

import pytest

from before_we_ai.documents.chunk import chunk_pdf
from before_we_ai.documents.extract import CHART, TABLE, TEXT, readable
from before_we_ai.documents.figures import distinct_values

pytestmark = pytest.mark.acceptance

DOCUMENT = (Path(__file__).resolve().parents[2] / "corpus" / "data" / "real"
            / "bosch-geschaeftsbericht-2025.pdf")


@pytest.fixture(scope="module")
def chunks():
    return chunk_pdf(DOCUMENT, "bosch")


def test_a_real_report_reads_end_to_end(chunks):
    assert len(chunks) > 300
    assert len({c.page for c in chunks}) > 100
    assert all(c.text.strip() for c in chunks)


def test_it_reads_identically_twice(chunks):
    """Determinism at 146 pages, not just at one."""
    again = chunk_pdf(DOCUMENT, "bosch")
    assert [(c.id, c.text, c.kind) for c in chunks] == \
           [(c.id, c.text, c.kind) for c in again]


def test_chunk_ids_stay_in_reading_order(chunks):
    pages = [c.page for c in chunks]
    assert pages == sorted(pages)


# -- R1: invisible characters, and why they had to go ----------------------

def test_r1_no_invisible_character_survives_into_a_chunk(chunks):
    """The finding that changed the code.

    The report carries 3,081 soft hyphens and six kinds of exotic space
    across 512 of its 539 passages. A quote is matched character for
    character, so every one of them was a way for a *correct* finding to be
    thrown away: the page reads "Verlustrechnung" and the extraction held
    "Verlust\\u00adrechnung".
    """
    leftovers = Counter(
        f"U+{ord(ch):04X}"
        for chunk in chunks for ch in chunk.text
        if ch not in "\n\t " and unicodedata.category(ch) in ("Cf", "Zs")
    )
    assert not leftovers, f"invisible characters survived extraction: {leftovers}"


def test_r1_a_word_broken_by_a_soft_hyphen_can_be_quoted(chunks):
    """The concrete case, before and after."""
    assert any("Verlustrechnung" in c.text for c in chunks)
    assert not any("Verlust­rechnung" in c.text for c in chunks)


def test_r1_normalising_the_text_is_not_loosening_the_match():
    """It happens once, at extraction. What a chunk holds is what a reader
    sees, and matching against it stays exact."""
    assert readable("Verlust­rechnung") == "Verlustrechnung"
    assert readable("8 312 504") == "8 312 504"
    assert readable("plain text") == "plain text"


def test_r1_german_figures_read_correctly_off_a_real_page(chunks):
    """91,0 Milliarden and 116,3 Mrd. are the report's own numbers."""
    found = [c for c in chunks if "116,3" in c.text]
    assert found
    from decimal import Decimal
    assert Decimal("116.3") in distinct_values(found[0].text)


# -- R2 and R3: what the real page defeats ---------------------------------

def test_r2_almost_no_table_is_detected_in_a_financial_report(chunks):
    """KNOWN LIMITATION, at full scale, and the strongest argument for
    replacing the extraction layer.

    A 146-page annual report is mostly financial statements, and PyMuPDF's
    line-based table finder sees essentially none of them: a designed
    report rules its tables with whitespace and colour, not strokes. Their
    rows arrive as `text`, which is the permissive direction — a figure
    from a balance sheet could corroborate. Defensible (the numbers really
    are stated) but not what a reader would call the passage, and the
    reason `meta/memory.md` carries an evaluation of a real layout
    analyser as the next step.
    """
    kinds = Counter(c.kind for c in chunks)
    assert kinds[TABLE] <= 5, (
        "table detection improved — good, but re-read this test and the "
        "backlog item it points at before changing the number"
    )
    assert kinds[TEXT] > 400


def test_r3_design_elements_are_labelled_chart(chunks):
    """KNOWN LIMITATION, conservative in the safe direction.

    On a designed page the geometry cannot tell a figure from a cover
    title or a coloured navigation bar; anything inside a drawn region
    reads as `chart`. The consequence is a *false refusal* — such a
    passage may never corroborate a figure — which is the right way round
    for this system to be wrong, and it is why the count matters less than
    the direction.
    """
    charts = [c for c in chunks if c.kind == CHART]
    assert charts
    assert len(charts) < len(chunks) * 0.1  # a minority, not the document


def test_a_kpi_inside_an_infographic_is_refused_like_any_chart_figure(chunks):
    """The real version of F23, found on a real page: the headline revenue
    figure is set inside a designed block, so it cannot corroborate."""
    found = [c for c in chunks if "91,0" in c.text and c.kind == CHART]
    assert found, "the headline KPI is no longer read as a chart figure"
