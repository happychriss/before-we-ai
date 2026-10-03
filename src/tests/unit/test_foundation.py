"""Foundation documents: read from Word, measured by share, applied as evidence.

The document under test is the real one in `foundations/shipbuilding/` —
written by an author who was told what kind of company it is for and
opened no file. Reading it is the test that the format a person can sign
is also one a machine can apply without guessing.
"""

from pathlib import Path

import duckdb
import pytest

from before_we_ai.core import Actor, ClaimStatus
from before_we_ai.core.objects import MappingClaim
from before_we_ai.foundation import (
    Binding,
    apply,
    evaluate,
    read_foundation,
    retire,
)
from before_we_ai.foundation.reader import _parse_formal
from before_we_ai.store import ProjectStore

pytestmark = pytest.mark.integration

DOCUMENT = (Path(__file__).resolve().parents[3]
            / "foundations" / "shipbuilding" / "foundation.docx")


@pytest.fixture(scope="module")
def document():
    return read_foundation(DOCUMENT)


class TestReadingTheDocument:
    def test_every_rule_is_understood_and_none_is_refused(self, document):
        assert len(document.rules) == 32
        assert document.refused == []

    def test_it_carries_what_a_reader_has_to_sign(self, document):
        assert 0 < document.min_share <= 1
        assert "T-EXACT" in document.tolerances
        assert document.parameters  # things only the company can supply
        assert document.open_questions  # what no data check can decide

    def test_a_tolerance_is_a_class_not_a_number_per_rule(self, document):
        used = {rule.tolerance for rule in document.rules}
        assert used <= set(document.tolerances)
        assert len(document.tolerances) < len(document.rules) / 3

    @pytest.mark.parametrize("kind, formal", [
        ("IDENTITY", "ledger: total = price * units; DROP TABLE x"),
        ("IDENTITY", "ledger: total = price * 'x'"),
        ("REFERENCE", "ledger.key = master.key"),
        ("CONDITION", "ledger: when status = delivered then date present"),
        ("NOPE", "ledger: a = b"),
    ])
    def test_a_formal_line_outside_the_syntax_is_refused(self, kind, formal):
        with pytest.raises(ValueError):
            _parse_formal(kind, formal)


@pytest.fixture
def ledger():
    con = duckdb.connect()
    con.execute("CREATE TABLE costs (id VARCHAR, vessel VARCHAR, "
                "local VARCHAR, rate VARCHAR, home VARCHAR)")
    rows = [(f"C{i}", "V1", "100", "4", "25") for i in range(39)]
    rows.append(("C39", "V1", "100", "4", "400"))  # multiplied, not divided
    con.executemany("INSERT INTO costs VALUES (?, ?, ?, ?, ?)", rows)
    con.execute("CREATE TABLE vessels (key VARCHAR)")
    con.execute("INSERT INTO vessels VALUES ('V1')")
    return con


BINDING = Binding.from_dict({
    "objects": {
        "cost_ledger_entry": {"view": "costs", "role": "journal"},
        "vessel_project": {"view": "vessels"},
    },
    "quantities": {
        "cost_ledger_entry.amount_transaction": {"column": "local",
                                                 "role": "amount_local"},
        "cost_ledger_entry.fx_rate": {"column": "rate", "invert": True},
        "cost_ledger_entry.amount_functional": {"column": "home"},
        "cost_ledger_entry.project_id": {"column": "vessel"},
        "vessel_project.project_id": {"column": "key"},
    },
})


def _result(results, rule_id):
    return next(r for r in results if r.rule.id == rule_id)


def test_every_word_in_an_expression_has_to_be_a_defined_quantity():
    """`(select 1)` is made of permitted characters. It is refused one
    step later, where every name in a formula is looked up among the
    quantities the document defines — a formula can only speak of those."""
    parts = _parse_formal("IDENTITY", "ledger: total = (select 1)")
    assert ("ledger", "select") in parts["quantities"]


class TestARuleHoldsByShare:
    def test_one_wrong_row_is_a_finding_not_a_verdict(self, document, ledger):
        fx = _result(evaluate(ledger, document, BINDING), "R15")
        assert (fx.satisfied, fx.evaluable) == (39, 40)
        assert fx.holds(document.min_share)
        assert [s["home"] for s in fx.samples] == ["400"]

    def test_a_rule_about_data_the_landscape_lacks_says_so(self, document, ledger):
        missing = _result(evaluate(ledger, document, BINDING), "R28")
        assert not missing.applicable
        assert "journal_voucher" in missing.reason

    def test_below_the_share_it_does_not_hold(self, document, ledger):
        ledger.execute("UPDATE costs SET home = '400' WHERE id < 'C2'")
        fx = _result(evaluate(ledger, document, BINDING), "R15")
        assert not fx.holds(document.min_share)


class TestWhatAHoldingRuleSettles:
    def _store(self, tmp_path):
        store = ProjectStore(tmp_path / "p", create=True)
        journal = store.add_claim(MappingClaim(
            statement="costs plays journal", created_by=Actor.AI,
            role="journal", binding={"table": "costs"}))
        amount = store.add_claim(MappingClaim(
            statement="costs.local plays amount_local", created_by=Actor.AI,
            role="amount_local", binding={"table": "costs",
                                          "amount": "costs.local"}))
        return store, journal.id, amount.id

    def test_it_settles_the_roles_on_the_bound_columns(self, document, ledger,
                                                       tmp_path):
        store, journal, amount = self._store(tmp_path)
        apply(store, ledger, document, BINDING)
        store = ProjectStore(store.root)
        assert store.claims[journal].status is ClaimStatus.TEST_SUPPORTED
        assert store.claims[amount].status is ClaimStatus.TEST_SUPPORTED
        # through the same door as every promotion: a check, never the AI
        for claim_id in (journal, amount):
            assert all(e.actor is Actor.CHECK
                       for e in store.evidence_for(store.claims[claim_id]))

    def test_a_rule_that_does_not_hold_leaves_the_role_open(self, document,
                                                           ledger, tmp_path):
        ledger.execute("UPDATE costs SET home = '400'")
        store, journal, amount = self._store(tmp_path)
        apply(store, ledger, document, BINDING)
        store = ProjectStore(store.root)
        # R16 (every cost line names a known vessel) still holds, so the
        # ledger is settled; the amount, which only R15 speaks of, is not —
        # and it is not struck out either
        assert store.claims[journal].status is ClaimStatus.TEST_SUPPORTED
        assert store.claims[amount].status is ClaimStatus.PROPOSED
        [finding] = store.evidence_for(store.claims[amount])
        assert finding.payload["refutes"] is False

    def test_retiring_a_borrowed_law_lets_the_claim_fall_back(self, document,
                                                             ledger, tmp_path):
        from before_we_ai.core import CheckVerdict, EvidenceRecord, EvidenceType
        from before_we_ai.core.transitions import attach_evidence

        store, journal, _ = self._store(tmp_path)
        borrowed = EvidenceRecord(
            type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK, claim_id=journal,
            verdict=CheckVerdict.FAIL, payload={"template": "balance"})
        store.add_evidence(borrowed)
        claim = store.claims[journal]
        store.save_claim(attach_evidence(claim, borrowed, []))
        assert store.claims[journal].status is ClaimStatus.CONTRADICTED
        assert retire(store, {"balance": "does not fit a cost ledger"}) == 1
        assert store.claims[journal].status is ClaimStatus.PROPOSED


# ---------------------------------------------------------------- discovery

from before_we_ai.foundation.discover import discover  # noqa: E402
from before_we_ai.foundation.match import (  # noqa: E402
    ARITHMETIC,
    propose,
    rule_shape,
    similarity,
)


@pytest.fixture
def warehouse():
    """Three tables as views, the way the catalog presents them."""
    con = duckdb.connect()
    con.execute("CREATE TABLE cost_ledger_t (cost_entry VARCHAR, loc VARCHAR, "
                "kurs VARCHAR, eur VARCHAR, proj VARCHAR)")
    con.executemany(
        "INSERT INTO cost_ledger_t VALUES (?, ?, ?, ?, ?)",
        [(f"C{i}", str(400 + 13 * i), str(rate),
          str(round((400 + 13 * i) / rate)), "V1")
         for i, rate in enumerate([4.21, 4.25, 4.31, 4.38] * 10)]
        + [("C99", "500", "4.25", "2125", "V1")])  # multiplied, not divided
    con.execute("CREATE VIEW cost_ledger AS SELECT * FROM cost_ledger_t")
    con.execute("CREATE TABLE invoices_t (inv VARCHAR, net VARCHAR, "
                "vat VARCHAR, gross VARCHAR, rate VARCHAR)")
    con.executemany(
        "INSERT INTO invoices_t VALUES (?, ?, ?, ?, ?)",
        [(f"I{i}", str(1000 + 37 * i), str(round((1000 + 37 * i) * r, 2)),
          str(round((1000 + 37 * i) * (1 + r), 2)), str(r))
         for i, r in enumerate([0.19, 0.07, 0.2] * 10)])
    con.execute("CREATE VIEW sales_invoice AS SELECT * FROM invoices_t")
    con.execute("CREATE TABLE tiny_t (a VARCHAR, b VARCHAR, c VARCHAR)")
    con.executemany("INSERT INTO tiny_t VALUES (?, ?, ?)",
                    [("6", "2", "3"), ("8", "2", "4"), ("10", "2", "5")])
    con.execute("CREATE VIEW tiny AS SELECT * FROM tiny_t")
    return con


class TestTheDataSaysWhatIsTied:
    def test_it_finds_the_conversion_and_which_way_the_rate_runs(self, warehouse):
        found = discover(warehouse)
        [fx] = [t for t in found.ties if t.view == "cost_ledger"]
        # local = rate * eur — the rate divides, whatever a rule may assume
        assert (fx.shape, fx.a, {fx.b, fx.c}) == ("product", "loc",
                                                  {"kurs", "eur"})
        assert (fx.satisfied, fx.evaluable) == (40, 41)

    def test_one_relation_is_reported_once(self, warehouse):
        formulas = [t.formula() for t in discover(warehouse).ties
                    if t.view == "sales_invoice"]
        assert sorted(formulas) == ["gross = net * (1 + rate)",
                                    "gross = net + vat", "vat = net * rate"]

    def test_a_table_too_small_to_tell_is_not_searched(self, warehouse):
        found = discover(warehouse)
        assert "tiny" in found.skipped
        assert not [t for t in found.ties if t.view == "tiny"]


class TestProposingABinding:
    def test_a_rule_is_recognised_by_shape(self, document):
        shapes = {r.id: rule_shape(r) for r in document.rules}
        assert shapes["R15"] == ("product", "amount_functional",
                                 "amount_transaction", "fx_rate")
        assert shapes["R05"] == ("sum", "gross_amount", "net_amount",
                                 "tax_amount")
        assert shapes["R07"] is None  # a key, not an identity

    def test_a_shared_ordinary_word_is_weak_evidence(self):
        assert similarity("gross_amount", "gross_amount") == 1.0
        assert similarity("amount_functional", "vat_amount") < 0.3
        assert similarity("ordered_quantity", "ord_qty") > 0.9

    def test_arithmetic_places_the_object_and_its_columns(self, document,
                                                          warehouse):
        found = discover(warehouse)
        proposal = propose(warehouse, document, found)
        lines = {(l.object, l.quantity): l for l in proposal.lines}
        assert lines[("cost_ledger_entry", None)].view == "cost_ledger"
        assert lines[("cost_ledger_entry", "fx_rate")].column == "kurs"
        assert lines[("cost_ledger_entry", "fx_rate")].reason == ARITHMETIC
        assert lines[("sales_invoice", "gross_amount")].column == "gross"

    def test_which_amount_is_which_is_left_as_a_choice(self, document,
                                                       warehouse):
        """`home = foreign x rate` and `foreign = home x rate` are the same
        tie. Arithmetic cannot say which column is the home amount, so the
        proposal names the other one as a rival instead of guessing
        silently."""
        proposal = propose(warehouse, document, discover(warehouse))
        line = next(l for l in proposal.lines
                    if (l.object, l.quantity) == ("cost_ledger_entry",
                                                  "amount_functional"))
        assert {line.column, *line.rivals} == {"loc", "eur"}

    def test_a_shape_alone_names_nothing(self, document, warehouse):
        """Every `a = b * c` fits every product. A rule about contract
        prices must not land on an invoice's net and VAT because both are
        sums — tried on the vessel data, it did, and then "held"."""
        proposal = propose(warehouse, document, discover(warehouse))
        placed = {l.object for l in proposal.lines if l.reason == ARITHMETIC}
        assert "shipbuilding_contract" not in placed
        assert "project_cost_summary" not in placed
