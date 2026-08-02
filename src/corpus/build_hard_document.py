#!/usr/bin/env python3
"""Build the hard document — the one that fights back.

Run: ``python corpus/build_hard_document.py`` (from ``src/``). Writes
``corpus/data/hard/acme_annual_extract.pdf`` and is then not run again:
the output is frozen corpus like everything else, and re-running it would
invalidate every pinned anchor.

**This is not the spec's real public PDF.** The spec makes one genuine
public document a Pflichtbestandteil precisely because a generator writes
the traps it already knows about. This document is the next best thing —
every nastiness here was taken from how published reports actually go
wrong, not from what the pipeline happens to handle — but the honest name
for it is ``hard``, not ``real``, and the spec item stays open.

The traps, each pinned by a test in
``tests/corpus_driven/test_hard_document.py``:

H1  a "EUR thousands" column header, so 8,313 means 8,313,000
H2  thin/non-breaking spaces as thousands separators: 8 312 504
H3  the accounting negative: (1,204,880) is minus 1,204,880
H4  a whitespace-aligned table with no ruling lines at all
H5  a bordered pull-quote that contains no chart
H6  a footnote restating a figure printed elsewhere on the page
H7  a word broken across lines with a hyphen: "intercom-\npany"
H8  a running header and footer repeated on every page
H9  a figure that exists only inside a real chart
"""

from pathlib import Path

import pymupdf

OUT = Path(__file__).resolve().parent / "data" / "hard" / "acme_annual_extract.pdf"

HEADER = "ACME Group SE — Annual Report 2025 (extract)"
# Non-breaking space: the digit grouping published reports actually use,
# and the one the base-14 fonts carry. (U+2009 THIN SPACE is the
# typographer's choice and the reader handles it, but Helvetica
# substitutes a middle dot for it — a generator artefact, not something
# real documents do.)
NBSP = "\u00a0"

BODY = 10
SMALL = 8


def _running(page, number: int, total: int) -> None:
    """H8 — the same two lines on every page, carrying no content."""
    page.insert_text((60, 40), HEADER, fontsize=SMALL, color=(0.4, 0.4, 0.4))
    page.draw_line(pymupdf.Point(60, 48), pymupdf.Point(535, 48))
    page.insert_text((60, 800), f"Page {number} of {total}", fontsize=SMALL,
                     color=(0.4, 0.4, 0.4))
    page.insert_text((420, 800), "Confidential draft", fontsize=SMALL,
                     color=(0.4, 0.4, 0.4))


def _page_one(page) -> None:
    page.insert_text((60, 90), "Segment performance", fontsize=14)

    # H7 — a hyphenated line break inside a word a reader would search for.
    left = [
        "Group revenue grew across all reporting",
        "segments in 2025. Growth was strongest in",
        "the wholesale channel, where volumes rose",
        "by double digits. Revenue from intercom-",
        "pany deliveries is excluded throughout this",
        "extract and reported separately in note 4.",
    ]
    right = [
        "The comparative period has been restated",
        "following the disposal announced in 2022.",
        "Prior year Q1 revenue is reported as EUR",
        "3,200,000 on this basis.¹",
        "",
        "All amounts are shown in euro unless the",
        "column heading states otherwise.",
    ]
    for index, line in enumerate(left):
        page.insert_text((60, 120 + index * 14), line, fontsize=BODY)
    for index, line in enumerate(right):
        page.insert_text((310, 120 + index * 14), line, fontsize=BODY)

    # H6 — the restatement lives in a footnote, printed far from the figure
    # it restates. Nothing in one sentence gives it away.
    page.draw_line(pymupdf.Point(60, 240), pymupdf.Point(220, 240))
    page.insert_text((60, 252),
                     "¹ Restated. Previously reported as EUR 3,050,000.",
                     fontsize=SMALL)

    # H5 — a bordered pull-quote. No chart anywhere near it.
    page.draw_rect(pymupdf.Rect(60, 285, 535, 345), color=(0.2, 0.2, 0.2))
    page.insert_text((75, 310), "“We report intercompany revenue "
                                "separately because", fontsize=11)
    page.insert_text((75, 328), "netting it would flatter the growth rate.”",
                     fontsize=11)

    # H4 — a table held together by spaces alone. No lines to find.
    page.insert_text((60, 390), "Revenue by channel (EUR)", fontsize=11)
    rows = [
        ("Channel", "2024", "2025"),
        ("Wholesale", "5,102,880", "5,884,190"),
        ("Pharmacy", "2,410,004", "2,553,120"),
        ("Direct", "800,000", "847,081"),
    ]
    for index, (channel, prior, current) in enumerate(rows):
        y = 412 + index * 16
        page.insert_text((60, y), channel, fontsize=BODY)
        page.insert_text((240, y), prior, fontsize=BODY)
        page.insert_text((380, y), current, fontsize=BODY)


def _page_two(page) -> None:
    page.insert_text((60, 90), "Consolidated figures", fontsize=14)

    # H1 — the scale is in the column heading, not with the number, and
    # H3 — the loss is in parentheses, not signed.
    page.insert_text((60, 115), "All figures in EUR thousands unless stated.",
                     fontsize=SMALL)
    top, left, right = 135, 60, 400
    for index in range(5):
        page.draw_line(pymupdf.Point(left, top + index * 20),
                       pymupdf.Point(right, top + index * 20))
    page.draw_line(pymupdf.Point(left, top), pymupdf.Point(left, top + 80))
    page.draw_line(pymupdf.Point(right, top), pymupdf.Point(right, top + 80))
    page.draw_line(pymupdf.Point(260, top), pymupdf.Point(260, top + 80))
    ruled = [
        ("Line item", "Amount"),
        ("Revenue", "8,313"),
        ("Cost of sales", "(1,204,880)"),
        ("Result before tax", "1,918"),
    ]
    for index, (label, amount) in enumerate(ruled):
        y = top + 14 + index * 20
        page.insert_text((left + 8, y), label, fontsize=BODY)
        page.insert_text((268, y), amount, fontsize=BODY)

    # H2 — the same revenue again, grouped with thin spaces, in full euro.
    page.insert_text((60, 245),
                     f"In full euro, revenue for the year was "
                     f"8{NBSP}312{NBSP}504 (2024: 7{NBSP}954{NBSP}118).",
                     fontsize=BODY)

    # H9 — a genuine chart. Its figure appears nowhere else.
    page.insert_text((60, 300), "Q3 revenue by region", fontsize=11)
    page.draw_rect(pymupdf.Rect(60, 315, 400, 460))
    for index, height in enumerate((60, 95, 40)):
        x = 90 + index * 100
        page.draw_rect(pymupdf.Rect(x, 440 - height, x + 55, 440),
                       fill=(0.6, 0.6, 0.75))
    page.insert_text((150, 335), "Total EUR 2,847,000", fontsize=BODY)
    page.insert_text((95, 455), "EU", fontsize=SMALL)
    page.insert_text((195, 455), "UK", fontsize=SMALL)
    page.insert_text((295, 455), "US", fontsize=SMALL)


def _page_three(page) -> None:
    page.insert_text((60, 90), "Note 4 — Accounting policies", fontsize=14)
    lines = [
        "Credit amounts are recorded as negative values in the general ledger.",
        "Revenue comprises accounts 4000 to 4999 less contra accounts 4800 to 4899.",
        "Foreign currency is translated at monthly average rates (rate type M).",
        "Intercompany revenue (accounts 4300 to 4399) is excluded from external",
        "revenue in all segment disclosures.",
        "",
        "Late postings are recognised in the period in which the goods were",
        "delivered, provided they are booked before the tenth working day of the",
        "following month.",
    ]
    for index, line in enumerate(lines):
        page.insert_text((60, 120 + index * 15), line, fontsize=BODY)


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    builders = (_page_one, _page_two, _page_three)
    for number, builder in enumerate(builders, start=1):
        page = document.new_page()
        _running(page, number, len(builders))
        builder(page)
    document.save(str(OUT), garbage=4, deflate=True)
    document.close()
    return OUT


if __name__ == "__main__":
    print(build())
