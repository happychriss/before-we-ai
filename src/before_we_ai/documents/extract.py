"""PDF → text blocks that know where they live on the page.

The one job here is to answer, for every piece of text, *what kind of
place it came from* — flowing text, a ruled table, or a figure. That is
not a nicety of presentation: the multi-anchor rule refuses to let a
chart-read number corroborate anything (F23), and it can only refuse if
the origin is known independently of what any model claims about it.

So origin is geometry, never wording. PyMuPDF's own table finder gives
the table regions; whatever vector drawings remain outside them are
clustered into graphic regions; a text block is classified by the region
that contains it. The corpus proves why the wording route would fail —
the boxed chart figure extracts as perfectly ordinary text.
"""

from dataclasses import dataclass

import pymupdf

from before_we_ai.core.enums import AnchorKind

# The vocabulary lives in core/enums.py with the rest of the fixed
# vocabulary; these are the plain strings that travel through YAML, DuckDB
# and prompts, so nothing downstream has to know about the enum.
TEXT = AnchorKind.TEXT.value
TABLE = AnchorKind.TABLE.value
CHART = AnchorKind.CHART.value
KINDS = (TEXT, TABLE, CHART)

# A stroke thinner than this is a ruling line, not a region of its own.
_HAIRLINE = 2.0
# Slack when asking "does this region contain that box": generators and
# real writers both let glyphs sit a hair outside their frame.
_TOLERANCE = 2.0


@dataclass(frozen=True)
class Block:
    """One text block with its page position and derived kind."""

    page: int  # 1-based, as a reader counts
    seq: int  # reading order within the page
    kind: str
    text: str
    bbox: tuple[float, float, float, float]


def _contains(outer: tuple[float, float, float, float],
              inner: tuple[float, float, float, float]) -> bool:
    return (
        inner[0] >= outer[0] - _TOLERANCE
        and inner[1] >= outer[1] - _TOLERANCE
        and inner[2] <= outer[2] + _TOLERANCE
        and inner[3] <= outer[3] + _TOLERANCE
    )


def _overlaps(a: tuple[float, float, float, float],
              b: tuple[float, float, float, float]) -> bool:
    return not (
        a[2] < b[0] - _TOLERANCE
        or b[2] < a[0] - _TOLERANCE
        or a[3] < b[1] - _TOLERANCE
        or b[3] < a[1] - _TOLERANCE
    )


def _union(a: tuple[float, float, float, float],
           b: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def graphic_regions(page, table_boxes: list[tuple[float, float, float, float]]
                    ) -> list[tuple[float, float, float, float]]:
    """Bounding boxes of drawing clusters that are not part of a table.

    A chart is rarely one rectangle — it is a frame, an axis, a fill and a
    dozen strokes. Merging everything that touches turns those back into
    the one region a reader sees, which is the region a figure's caption
    and its number both sit in.
    """
    boxes = []
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        box = (rect.x0, rect.y0, rect.x1, rect.y1)
        if any(_contains(table, box) for table in table_boxes):
            continue
        boxes.append(box)

    merged: list[tuple[float, float, float, float]] = []
    for box in boxes:
        pending = box
        rest = []
        for known in merged:
            if _overlaps(known, pending):
                pending = _union(known, pending)
            else:
                rest.append(known)
        rest.append(pending)
        merged = rest

    # A lone hairline is a rule under a heading, not a figure.
    regions = [
        box for box in merged
        if (box[2] - box[0]) > _HAIRLINE and (box[3] - box[1]) > _HAIRLINE
    ]
    return sorted(regions, key=lambda b: (b[1], b[0]))


def read_page(page, number: int) -> list[Block]:
    """Every text block of one page, in reading order, kind derived."""
    tables = [tuple(t.bbox) for t in page.find_tables().tables]
    charts = graphic_regions(page, tables)

    blocks = []
    for seq, raw in enumerate(page.get_text("blocks", sort=True)):
        x0, y0, x1, y1, text, _no, block_type = raw
        if block_type != 0:  # image block — no text to anchor to
            continue
        text = text.strip()
        if not text:
            continue
        box = (x0, y0, x1, y1)
        if any(_contains(table, box) for table in tables):
            kind = TABLE
        elif any(_contains(chart, box) for chart in charts):
            kind = CHART
        else:
            kind = TEXT
        blocks.append(Block(page=number, seq=seq, kind=kind, text=text, bbox=box))
    return blocks


def read_pdf(path) -> list[Block]:
    """Every text block of a document, pages in order."""
    blocks: list[Block] = []
    with pymupdf.open(path) as document:
        for index, page in enumerate(document):
            blocks.extend(read_page(page, index + 1))
    return blocks
