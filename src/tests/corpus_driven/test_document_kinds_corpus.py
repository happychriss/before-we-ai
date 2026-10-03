"""K7 against the real PDFs: origin is derived, not read off the words.

The corpus builds the trap this pins. ``management_report.pdf`` states its
Q3 2024 revenue (EUR 2,847,000) **only** inside a boxed chart label — F23 —
and PyMuPDF extracts that number as text like any other, because that is
what it is on the page. If a model were asked "is this from a chart?", the
whole multi-anchor rule would rest on the model's honesty about a fact it
cannot see.

So the pipeline derives it from geometry, and this test is the proof
against the file that actually sets the trap. When the owner's real public
PDF joins the corpus, it is checked here too.
"""

from pathlib import Path

import pytest

from before_we_ai.documents.chunk import chunk_pdf
from before_we_ai.documents.extract import CHART, TABLE, TEXT

from corpora import load as load_landscape

pytestmark = pytest.mark.acceptance

CORPUS = load_landscape("finance").data

# F23's figure, exactly as it appears on the page.
CHART_ONLY_FIGURE = "EUR 2,847,000"
# F24's poisoned prior-year figure — plain prose, no supporting table.
RESTATED_FIGURE = "EUR 3,200,000"


def _chunks(name: str, subdir: str = ""):
    path = CORPUS / subdir / f"{name}.pdf" if subdir else CORPUS / f"{name}.pdf"
    return chunk_pdf(path, name)


def _carrying(chunks, needle: str):
    return [c for c in chunks if needle in c.text]


def test_f23_chart_only_figure_is_derived_as_chart():
    found = _carrying(_chunks("management_report"), CHART_ONLY_FIGURE)
    assert found, f"{CHART_ONLY_FIGURE} is no longer in the management report"
    assert {c.kind for c in found} == {CHART}


def test_the_quarterly_table_is_derived_as_table():
    found = _carrying(_chunks("management_report"), "8,312,504")
    assert found
    assert {c.kind for c in found} == {TABLE}


def test_f24_restated_figure_is_prose_and_stands_alone():
    """A restatement in running text — one anchor, and it never gets a second."""
    chunks = _chunks("management_report")
    found = _carrying(chunks, RESTATED_FIGURE)
    assert [c.kind for c in found] == [TEXT]
    assert len(found) == 1


def test_the_chart_figure_never_leaks_into_a_text_chunk():
    """Kind purity: no chunk may carry the chart number under a text label."""
    for chunk in _chunks("management_report"):
        if chunk.kind != CHART:
            assert CHART_ONLY_FIGURE not in chunk.text


@pytest.mark.parametrize("name,subdir", [
    ("buchhaltungsrichtlinie", ""),
    ("rabattvertrag", ""),
    ("lieferantenkatalog", "noise"),
    ("pressemitteilung_2022_divested_unit", "noise"),
    ("reisekostenrichtlinie", "noise"),
])
def test_every_corpus_pdf_reads_without_special_casing(name, subdir):
    chunks = _chunks(name, subdir)
    assert chunks, f"{name}.pdf produced no chunks"
    assert all(c.text.strip() for c in chunks)
    assert [c.id for c in chunks] == sorted(c.id for c in chunks)


def test_chunk_ids_are_stable_across_reads():
    """The pin the fixture hashes rest on."""
    assert [c.id for c in _chunks("buchhaltungsrichtlinie")] == \
           [c.id for c in _chunks("buchhaltungsrichtlinie")]
