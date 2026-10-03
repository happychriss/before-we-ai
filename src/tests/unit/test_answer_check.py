"""Checking an answer somebody else computed, claim by claim.

Each kind of correction has a part the data can show and a part it cannot.
These tests pin which is which — and that an answer whose figures do not
come out of the ledger and its own corrections is not reproduced, however
well it reads.
"""

import duckdb
import pymupdf
import pytest

from before_we_ai.answer_check import (
    DOCUMENT,
    REFUTED,
    UNSUPPORTED,
    VERIFIED,
    check_answer,
)

pytestmark = pytest.mark.integration

LEDGER = {"view": "costs", "key": "id", "measure": "eur", "group": "project"}
NOTE = ("Email from project controls. The pump invoice was charged to P2 "
        "by mistake and belongs to P1. The crane hire has no project yet; "
        "it belongs to P1 as well. A labour batch of EUR 500 is missing.")


@pytest.fixture
def con():
    con = duckdb.connect()
    con.execute("CREATE TABLE costs (id VARCHAR, project VARCHAR, "
                "invoice VARCHAR, po VARCHAR, local VARCHAR, rate VARCHAR, "
                "eur VARCHAR)")
    rows = [(f"C{i:02d}", "P1", f"INV-{i}", f"PO-{i}", "400", "4", "100")
            for i in range(20)]
    rows += [
        ("D01", "P1", "INV-5", "PO-5", "400", "4", "100"),   # repeats C05
        ("X01", "P2", "INV-90", "PO-90", "400", "4", "1600"),  # multiplied
        ("M01", "P2", "INV-91", "PO-91", "800", "4", "200"),  # belongs to P1
        ("B01", None, "INV-92", "PO-92", "1200", "4", "300"),  # no project
    ]
    con.executemany("INSERT INTO costs VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
    return con


@pytest.fixture
def documents(tmp_path):
    path = tmp_path / "notes.pdf"
    pdf = pymupdf.open()
    pdf.new_page().insert_textbox(pymupdf.Rect(40, 40, 550, 300), NOTE)
    pdf.save(path)
    return {"notes": path}


def _check(con, documents, claims, figures=()):
    return check_answer(con, {"ledger": LEDGER, "claims": claims,
                              "figures": list(figures)}, documents)


def _status(con, documents, claim):
    [checked] = _check(con, documents, [{"id": "c", **claim}]).claims
    return checked.status, checked.found


class TestWhatTheDataCanShow:
    def test_a_duplicate_is_shown_by_the_rows_themselves(self, con, documents):
        status, found = _status(con, documents, {
            "kind": "duplicate", "row": "D01", "of": "C05",
            "same": ["invoice", "po", "eur"]})
        assert status == VERIFIED and "agree on invoice, po, eur" in found

    def test_rows_that_differ_are_not_a_duplicate(self, con, documents):
        status, found = _status(con, documents, {
            "kind": "duplicate", "row": "D01", "of": "C06",
            "same": ["invoice", "po", "eur"]})
        assert status == REFUTED and "differ on invoice, po" in found

    def test_a_recomputed_row_needs_the_formula_to_fit_the_others(
            self, con, documents):
        status, found = _status(con, documents, {
            "kind": "recompute", "row": "X01", "expression": "local / rate"})
        assert status == VERIFIED and "fits 23 of the 23 other rows" in found

    def test_a_formula_that_fits_nothing_else_proves_nothing(self, con, documents):
        status, _ = _status(con, documents, {
            "kind": "recompute", "row": "X01", "expression": "local * 2"})
        assert status == UNSUPPORTED

    def test_a_formula_may_not_carry_a_query(self, con, documents):
        status, found = _status(con, documents, {
            "kind": "recompute", "row": "X01",
            "expression": "(select 1 from costs)"})
        assert status == UNSUPPORTED and "not a column" in found


class TestWhatOnlySomebodysWordCanShow:
    QUOTE = "The pump invoice was charged to P2 by mistake and belongs to P1."

    def test_a_reassignment_rests_on_a_quote_that_exists(self, con, documents):
        status, found = _status(con, documents, {
            "kind": "reassign", "row": "M01", "from": "P2", "to": "P1",
            "document": "notes", "quote": self.QUOTE})
        assert status == DOCUMENT and "word for word" in found

    def test_an_invented_quote_supports_nothing(self, con, documents):
        status, _ = _status(con, documents, {
            "kind": "reassign", "row": "M01", "from": "P2", "to": "P1",
            "document": "notes",
            "quote": "Finance confirmed the pump invoice belongs to P1."})
        assert status == UNSUPPORTED

    def test_a_row_claimed_to_be_elsewhere_is_refuted(self, con, documents):
        status, _ = _status(con, documents, {
            "kind": "reassign", "row": "M01", "from": "P3", "to": "P1",
            "document": "notes", "quote": self.QUOTE})
        assert status == REFUTED

    def test_assigning_a_row_that_already_has_a_group_is_refuted(
            self, con, documents):
        status, _ = _status(con, documents, {
            "kind": "assign", "row": "M01", "to": "P1",
            "document": "notes", "quote": self.QUOTE})
        assert status == REFUTED


class TestAFigureHasToComeOut:
    CLAIMS = [
        {"id": "dup", "kind": "duplicate", "row": "D01", "of": "C05",
         "same": ["invoice", "po", "eur"]},
        {"id": "pump", "kind": "reassign", "row": "M01", "from": "P2",
         "to": "P1", "document": "notes",
         "quote": "The pump invoice was charged to P2 by mistake and "
                  "belongs to P1."},
        {"id": "crane", "kind": "assign", "row": "B01", "to": "P1",
         "document": "notes",
         "quote": "The crane hire has no project yet; it belongs to P1 as "
                  "well."},
        {"id": "labour", "kind": "add", "group": "P1", "amount": 500,
         "document": "notes", "quote": "A labour batch of EUR 500 is missing."},
        {"id": "fx", "kind": "recompute", "row": "X01",
         "expression": "local / rate"},
    ]

    def test_ledger_plus_corrections_reproduces_the_stated_figure(
            self, con, documents):
        result = _check(con, documents, self.CLAIMS, [
            # 21 rows of 100, less the duplicate, plus pump, crane, labour
            {"label": "P1", "group": "P1", "stated": 3000,
             "claims": ["dup", "pump", "crane", "labour"]},
            # 1600 + 200, less the pump, the FX row corrected to 100
            {"label": "P2", "group": "P2", "stated": 100,
             "claims": ["pump", "fx"]},
        ])
        p1, p2 = result.figures
        assert p1.base == 2100 and p1.reproduced
        assert p1.rests_on == {VERIFIED: 1, DOCUMENT: 3}
        assert p2.base == 1800 and p2.reproduced

    def test_a_figure_that_does_not_come_out_is_not_reproduced(
            self, con, documents):
        [figure] = _check(con, documents, self.CLAIMS, [
            {"label": "P1", "group": "P1", "stated": 3100,
             "claims": ["dup", "pump", "crane", "labour"]}]).figures
        assert not figure.reproduced
        assert figure.computed == 3000
