"""Where a passage came from is decided by geometry, not by wording.

These tests build their own PDFs so the rule is checked against a shape,
not against the corpus's particular sentences — the corpus then re-checks
the same rule against the real trap in the acceptance lane.
"""

import pymupdf
import pytest

from before_we_ai.documents.chunk import TARGET_CHARS, chunk_blocks, chunk_pdf
from before_we_ai.documents.extract import CHART, TABLE, TEXT, Block, read_pdf

pytestmark = pytest.mark.unit


def _write_pdf(path, draw):
    document = pymupdf.open()
    page = document.new_page()
    draw(page)
    document.save(str(path))
    document.close()
    return path


def test_plain_paragraphs_are_text(tmp_path):
    def draw(page):
        page.insert_text((72, 100), "Credit amounts are stored as negatives.")

    blocks = read_pdf(_write_pdf(tmp_path / "policy.pdf", draw))
    assert [b.kind for b in blocks] == [TEXT]
    assert "Credit amounts" in blocks[0].text


def test_a_figure_boxed_in_a_frame_is_a_chart_not_text(tmp_path):
    """F23 in miniature: the number extracts as ordinary text.

    Nothing in the string says "chart". Only the frame around it does, so
    only geometry can tell the truth here — and the multi-anchor rule
    depends on being told the truth.
    """
    def draw(page):
        page.insert_text((72, 100), "Revenue grew in the third quarter.")
        page.draw_rect(pymupdf.Rect(150, 200, 400, 280))
        page.insert_text((200, 250), "EUR 2,847,000")

    blocks = read_pdf(_write_pdf(tmp_path / "report.pdf", draw))
    by_kind = {b.kind: b.text for b in blocks}
    assert "EUR 2,847,000" in by_kind[CHART]
    assert "Revenue grew" in by_kind[TEXT]


def test_a_ruled_table_is_a_table(tmp_path):
    def draw(page):
        for y in (200, 220, 240, 260):
            page.draw_line(pymupdf.Point(100, y), pymupdf.Point(400, y))
        for x in (100, 250, 400):
            page.draw_line(pymupdf.Point(x, 200), pymupdf.Point(x, 260))
        rows = [("2024 Q1", "8,312,504"), ("2024 Q2", "9,379,575")]
        for index, (quarter, amount) in enumerate(rows):
            y = 235 + index * 20
            page.insert_text((110, y), quarter)
            page.insert_text((260, y), amount)

    blocks = read_pdf(_write_pdf(tmp_path / "figures.pdf", draw))
    assert {b.kind for b in blocks} == {TABLE}


def test_reading_the_same_bytes_twice_gives_identical_chunks(tmp_path):
    """Determinism is a hard requirement: chunks are prompt bytes."""
    def draw(page):
        for index in range(12):
            page.insert_text((72, 100 + index * 18), f"Rule {index}: something holds.")

    path = _write_pdf(tmp_path / "rules.pdf", draw)
    first = chunk_pdf(path, "rules")
    second = chunk_pdf(path, "rules")
    assert [(c.id, c.text, c.kind, c.start, c.end) for c in first] == \
           [(c.id, c.text, c.kind, c.start, c.end) for c in second]


def test_a_chunk_never_mixes_kinds():
    blocks = [
        Block(page=1, seq=0, kind=TEXT, text="See the chart.", bbox=(0, 0, 1, 1)),
        Block(page=1, seq=1, kind=CHART, text="EUR 2,847,000", bbox=(0, 2, 1, 3)),
        Block(page=1, seq=2, kind=TEXT, text="Prior year was lower.", bbox=(0, 4, 1, 5)),
    ]
    chunks = chunk_blocks(blocks, "report")
    assert [c.kind for c in chunks] == [TEXT, CHART, TEXT]
    assert [c.id for c in chunks] == ["report:p1:0", "report:p1:1", "report:p1:2"]


def test_spans_index_into_the_page_text_they_describe():
    blocks = [
        Block(page=1, seq=i, kind=TEXT, text=f"Sentence {i}.", bbox=(0, i, 1, i + 1))
        for i in range(3)
    ]
    chunks = chunk_blocks(blocks, "doc")
    page = "\n".join(c.text for c in chunks)
    for chunk in chunks:
        assert page[chunk.start:chunk.end] == chunk.text


def test_long_runs_are_split_at_the_target_size():
    blocks = [
        Block(page=1, seq=i, kind=TEXT, text="x" * 400, bbox=(0, i, 1, i + 1))
        for i in range(6)
    ]
    chunks = chunk_blocks(blocks, "long")
    assert len(chunks) > 1
    assert all(len(c.text) <= TARGET_CHARS + 400 for c in chunks)


def test_pages_are_numbered_the_way_a_reader_counts(tmp_path):
    document = pymupdf.open()
    for index in range(2):
        page = document.new_page()
        page.insert_text((72, 100), f"Page body {index}")
    path = tmp_path / "two_pages.pdf"
    document.save(str(path))
    document.close()

    chunks = chunk_pdf(path, "two_pages")
    assert sorted({c.page for c in chunks}) == [1, 2]
    assert chunks[0].label == "two_pages p.1"
