"""Contract V3: what the documents say, proposed and anchored.

The contract's guarantee is the same shape as every other one here, and
worth stating plainly: it creates nothing but proposals. What is special
is where the epistemic work happens — outside the model. The quote is
string-matched, the passage's origin was derived when the document was
read, and whether a figure corroborates anything follows the multi-anchor
rule. These tests hold that line: no finding, however confidently
phrased, may promote a claim or link a figure nothing else supports.
"""

import json

import pytest
import yaml

from before_we_ai.core import Actor, ClaimStatus, EvidenceType
from before_we_ai.core.objects import ConceptClaim
from before_we_ai.documents import read_documents
from before_we_ai.llm.client import Completion
from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.llm.inputs import build_document_context
from before_we_ai.llm.mapping import check_document_finding, finding_to_claim
from before_we_ai.llm.prompts import V3_SYSTEM
from before_we_ai.llm.schemas import DocumentFinding
from before_we_ai.llm.v3_documents import interpret_documents, open_rule_items
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.contract

POLICY_LINE = "Credit amounts are booked as negative numbers."
CHART_LINE = "EUR 2,847,000"


class _Chunk:
    """Just enough of a chunk for the pure checks."""

    def __init__(self, cid, text, page=1, kind="text", source="policy"):
        self.id, self.text, self.page = cid, text, page
        self.kind, self.source = kind, source


def _finding(**overrides):
    payload = dict(chunk_id="policy:p1:0", quote=POLICY_LINE,
                   reads_as="definition", statement="Credits are negative.",
                   term="sign_convention", definition="credits are negative",
                   value=None, answers=None, rationale="stated in the policy")
    payload.update(overrides)
    return DocumentFinding(**payload)


CHUNKS = {"policy:p1:0": _Chunk("policy:p1:0", f"Accounting Policy\n{POLICY_LINE}")}


class TestQuoteValidation:
    """The spec's string match — the check that matters most here."""

    def test_a_verbatim_quote_passes(self):
        assert check_document_finding(_finding(), CHUNKS, set()) == []

    def test_a_reworded_quote_is_refused(self):
        errors = check_document_finding(
            _finding(quote="Credit amounts are booked as negatives."),
            CHUNKS, set())
        assert any("verbatim" in e for e in errors)

    def test_a_quote_from_a_passage_not_supplied_is_refused(self):
        errors = check_document_finding(
            _finding(chunk_id="other:p9:3"), CHUNKS, set())
        assert any("not in this document's input" in e for e in errors)

    def test_an_empty_quote_is_refused(self):
        assert check_document_finding(_finding(quote="  "), CHUNKS, set())

    def test_the_error_shows_the_model_what_it_wrote(self):
        errors = check_document_finding(_finding(quote="invented"), CHUNKS, set())
        assert "'invented'" in " ".join(errors)


class TestFindingShape:
    def test_a_definition_needs_its_term(self):
        errors = check_document_finding(_finding(term=None), CHUNKS, set())
        assert any("needs the term" in e for e in errors)

    def test_a_figure_may_not_carry_a_definition(self):
        errors = check_document_finding(
            _finding(reads_as="figure", term="x", definition="y",
                     value="2020"), CHUNKS, set())
        assert any("belong to reads_as=definition" in e for e in errors)

    def test_a_figure_must_name_the_number_it_is_about(self):
        """The engine used to guess this and took the year out of
        "Prior year Q1 2023 revenue: EUR 3,200,000"."""
        errors = check_document_finding(
            _finding(reads_as="figure", term=None, definition=None,
                     value=None), CHUNKS, set())
        assert any("needs the number it is about" in e for e in errors)

    def test_a_named_number_that_is_not_in_the_quote_is_refused(self):
        """Naming it is allowed precisely because naming it is checkable."""
        chunks = {"policy:p1:0": _Chunk("policy:p1:0",
                                        "Revenue was EUR 4,598,231 last year.")}
        errors = check_document_finding(
            _finding(reads_as="figure", term=None, definition=None,
                     quote="Revenue was EUR 4,598,231 last year.",
                     value="9,999,999"), chunks, set())
        assert any("is not in the quote" in e for e in errors)

    def test_a_named_number_that_is_no_number_is_refused(self):
        chunks = {"policy:p1:0": _Chunk("policy:p1:0", "Revenue was strong.")}
        errors = check_document_finding(
            _finding(reads_as="figure", term=None, definition=None,
                     quote="Revenue was strong.", value="strong"),
            chunks, set())
        assert any("cannot be read as a number" in e for e in errors)

    def test_the_named_number_may_be_any_of_the_ones_in_the_quote(self):
        """Which one a sentence is about is a reading, not a computation:
        here the smaller figure is the subject and the larger is context."""
        text = "Earnings per share of 4.12 on 8,312,504 shares."
        chunks = {"policy:p1:0": _Chunk("policy:p1:0", text)}
        assert check_document_finding(
            _finding(reads_as="figure", term=None, definition=None,
                     quote=text, value="4.12"), chunks, set()) == []

    def test_a_definition_may_not_name_a_number(self):
        errors = check_document_finding(_finding(value="4,000"), CHUNKS, set())
        assert any("belongs to reads_as=figure" in e for e in errors)

    def test_answering_an_unlisted_question_is_refused(self):
        errors = check_document_finding(
            _finding(answers="something nobody asked"), CHUNKS, set())
        assert any("not one of the open questions" in e for e in errors)

    def test_answering_a_listed_question_passes(self):
        assert check_document_finding(
            _finding(answers="sign convention"), CHUNKS,
            {"sign convention"}) == []


class TestFindingToClaim:
    def test_a_definition_becomes_a_proposed_concept_claim(self):
        claim = finding_to_claim(_finding(), source_id="s1")
        assert isinstance(claim, ConceptClaim)
        assert claim.status is ClaimStatus.PROPOSED
        assert claim.created_by is Actor.AI
        assert claim.term == "sign_convention"

    def test_a_figure_becomes_a_plain_proposed_claim(self):
        claim = finding_to_claim(
            _finding(reads_as="figure", term=None, definition=None,
                     quote="Q3 revenue was EUR 2,847,000.",
                     value="2,847,000",
                     statement="Q3 revenue was EUR 2,847,000."),
            source_id="s1")
        assert not isinstance(claim, ConceptClaim)
        assert claim.status is ClaimStatus.PROPOSED


class TestInput:
    def test_it_is_deterministic(self):
        chunks = [_Chunk("d:p1:0", "one"), _Chunk("d:p1:1", "two")]
        first = build_document_context("d", chunks, ["a rule"])
        second = build_document_context("d", chunks, ["a rule"])
        assert first.sha256 == second.sha256

    def test_it_names_the_open_questions(self):
        built = build_document_context("d", [_Chunk("d:p1:0", "x")],
                                       ["month cut-off"])
        assert "month cut-off" in built.text

    def test_it_does_not_tell_the_model_where_a_passage_sits(self):
        """Kind is derived. Showing it would invite the model to argue."""
        built = build_document_context(
            "d", [_Chunk("d:p1:0", "EUR 1", kind="chart")], [])
        assert "chart" not in built.text


class TestPrompt:
    def test_it_demands_verbatim_quotes(self):
        assert "VERBATIM" in V3_SYSTEM

    def test_it_forbids_judging_trustworthiness(self):
        assert "Do not judge whether a figure is trustworthy" in V3_SYSTEM

    def test_it_tells_the_model_it_confirms_nothing(self):
        assert "You confirm nothing." in V3_SYSTEM


class _ScriptedClient:
    name = "scripted"

    def __init__(self, findings):
        self.payload = {"findings": findings}
        self.calls = 0

    def complete(self, **kwargs) -> Completion:
        self.calls += 1
        return Completion(text=json.dumps(self.payload), usage={}, ms=0)


@pytest.fixture
def guide() -> DomainGuide:
    return DomainGuide.model_validate({
        "domain": "finance",
        "objects": {"journal": {"decided_by": "balance",
                                "definition": "the ledger of record"}},
    })


@pytest.fixture
def project(tmp_path):
    import pymupdf

    root = init_project(tmp_path / "p")
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 100), "Accounting Policy")
    page.insert_text((72, 120), POLICY_LINE)
    page.draw_rect(pymupdf.Rect(150, 200, 400, 280))
    page.insert_text((200, 250), CHART_LINE)
    document.save(str(root / "sources" / "policy.pdf"))
    document.close()

    config = yaml.safe_load((root / "before-ai.yaml").read_text())
    config["sources"] = [{"name": "policy", "kind": "pdf",
                          "location": "sources/policy.pdf"}]
    config["llm"] = {"offline": False}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    read_documents(root)
    return root


def _chunk_id(root, needle):
    store = ProjectStore(root)
    from before_we_ai.documents import load_chunks
    import duckdb

    con = duckdb.connect(str(root / "cache" / "analysis.duckdb"))
    try:
        return next(c.id for c in load_chunks(con) if needle in c.text)
    finally:
        con.close()


class TestInterpretDocuments:
    def test_a_definition_is_stored_as_a_proposed_claim_with_an_anchor(
            self, project, guide):
        client = _ScriptedClient([{
            "chunk_id": _chunk_id(project, POLICY_LINE), "quote": POLICY_LINE,
            "reads_as": "definition", "statement": "Credits are negative.",
            "term": "sign_convention", "definition": "credits are negative",
            "answers": None, "rationale": "the policy says so",
        }])
        report = interpret_documents(project, guide=guide, client=client)

        store = ProjectStore(project)
        assert len(report.claims_created) == 1
        claim = store.claims[report.claims_created[0]]
        assert claim.status is ClaimStatus.PROPOSED
        anchors = [e for e in store.evidence.values()
                   if e.type is EvidenceType.DOCUMENT_ANCHOR]
        assert len(anchors) == 1
        assert anchors[0].payload["quote"] == POLICY_LINE
        assert anchors[0].payload["kind"] == "text"

    def test_the_anchor_does_not_promote_the_claim(self, project, guide):
        client = _ScriptedClient([{
            "chunk_id": _chunk_id(project, POLICY_LINE), "quote": POLICY_LINE,
            "reads_as": "definition", "statement": "Credits are negative.",
            "term": "sign_convention", "definition": "credits are negative",
            "answers": None, "rationale": "…",
        }])
        interpret_documents(project, guide=guide, client=client)
        store = ProjectStore(project)
        assert all(c.status is ClaimStatus.PROPOSED for c in store.claims.values())

    def test_an_invented_quote_creates_nothing(self, project, guide):
        client = _ScriptedClient([{
            "chunk_id": _chunk_id(project, POLICY_LINE),
            "quote": "Revenue is recognised on shipment.",
            "reads_as": "definition", "statement": "…", "term": "revenue",
            "definition": "on shipment", "answers": None, "rationale": "…",
        }])
        report = interpret_documents(project, guide=guide, client=client)

        assert report.claims_created == []
        assert report.skipped
        assert ProjectStore(project).evidence == {}

    def test_a_chart_figure_is_anchored_and_questioned_never_linked(
            self, project, guide):
        """F23 end to end: the number enters, and it enters as a problem."""
        client = _ScriptedClient([{
            "chunk_id": _chunk_id(project, CHART_LINE), "quote": CHART_LINE,
            "reads_as": "figure", "statement": "Q3 revenue was EUR 2,847,000.",
            "term": None, "definition": None, "value": "2,847,000",
            "answers": None, "rationale": "the chart says so",
        }])
        report = interpret_documents(project, guide=guide, client=client)

        store = ProjectStore(project)
        anchor = next(e for e in store.evidence.values()
                      if e.type is EvidenceType.DOCUMENT_ANCHOR)
        assert anchor.payload["kind"] == "chart"
        assert report.links == []
        assert any("chart" in q for q in report.questions)

    def test_a_refusal_always_leaves_a_question_behind(self, project, guide):
        """Never silence: what was refused is a question a human can answer."""
        client = _ScriptedClient([{
            "chunk_id": _chunk_id(project, CHART_LINE), "quote": CHART_LINE,
            "reads_as": "figure", "statement": "Q3 revenue.", "term": None,
            "definition": None, "value": "2,847,000", "answers": None,
            "rationale": "…",
        }])
        interpret_documents(project, guide=guide, client=client)
        assert ProjectStore(project).questions

    def test_a_document_yielding_nothing_is_a_valid_answer(self, project, guide):
        report = interpret_documents(project, guide=guide,
                                     client=_ScriptedClient([]))
        assert report.claims_created == []
        assert report.failures == []

    def test_a_project_without_documents_does_nothing(self, tmp_path, guide):
        root = init_project(tmp_path / "empty")
        report = interpret_documents(root, guide=guide,
                                     client=_ScriptedClient([]))
        assert report.documents_read == []

    def test_open_rule_items_are_empty_without_a_request(self, project, guide):
        assert open_rule_items(ProjectStore(project), guide) == []
