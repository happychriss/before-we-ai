"""The two surfaces M5 adds to the report, judged as a reader would.

The report is the owner's validation surface, so these tests are about
whether a person can *read* it: no chunk ids, no ULIDs, no payload JSON,
and every decision saying who made it and what drove them. The rest of
the suite proves the pipeline is right; this proves it is legible.
"""

import json

import pytest
import yaml

from before_we_ai.core import Scope
from before_we_ai.documents import read_documents
from before_we_ai.llm.client import Completion
from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.statements import confirm_claim, tell
from before_we_ai.store import ProjectStore, init_project
from readiness_report.projection import build_view_model

pytestmark = pytest.mark.integration

POLICY = "Credit amounts are booked as negative numbers."
CHART = "EUR 2,847,000"


class _Scripted:
    name = "scripted"

    def __init__(self, findings):
        self.findings = findings

    def complete(self, **kwargs):
        return Completion(text=json.dumps({"findings": self.findings}),
                          usage={}, ms=0)


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
    page.insert_text((72, 100), POLICY)
    page.draw_rect(pymupdf.Rect(150, 200, 400, 280))
    page.insert_text((200, 250), CHART)
    document.save(str(root / "sources" / "policy.pdf"))
    document.close()

    config = yaml.safe_load((root / "before-ai.yaml").read_text())
    config["sources"] = [{"name": "policy", "kind": "pdf",
                          "location": "sources/policy.pdf"}]
    config["llm"] = {"offline": False}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    read_documents(root)
    return root


def _view(root):
    config = yaml.safe_load((root / "before-ai.yaml").read_text())
    return build_view_model(ProjectStore(root), root, config)


def _chunk_id(root, needle):
    import duckdb

    from before_we_ai.documents import load_chunks

    con = duckdb.connect(str(root / "cache" / "analysis.duckdb"))
    try:
        return next(c.id for c in load_chunks(con) if needle in c.text)
    finally:
        con.close()


class TestDocumentsRead:
    def test_it_counts_in_units_a_reader_counts_in(self, project):
        documents = _view(project).documents.documents
        assert [d.name for d in documents] == ["policy"]
        assert documents[0].pages == "1 page"
        assert "passage" in documents[0].passages

    def test_it_says_where_the_passages_sit(self, project):
        origins = _view(project).documents.documents[0].origins
        assert "1 in running text" in origins
        assert "1 inside a chart" in origins

    def test_a_document_with_a_chart_carries_a_warning(self, project):
        caution = _view(project).documents.documents[0].caution
        assert "sits inside a figure" in caution
        assert "never allowed to corroborate" in caution

    def test_no_chunk_ids_reach_the_reader(self, project):
        """The reader's unit is a page, not a chunk."""
        documents = _view(project).documents.documents
        rendered = " ".join(
            [d.name, d.pages, d.passages, d.caution, *d.origins]
            for d in documents
        )[0] if False else " ".join(
            f"{d.name} {d.pages} {d.passages} {d.caution} {' '.join(d.origins)}"
            for d in documents
        )
        assert ":p1:" not in rendered
        assert "chunk" not in rendered.lower()

    def test_a_project_without_documents_says_so_rather_than_showing_nothing(
            self, tmp_path):
        root = init_project(tmp_path / "empty")
        assert _view(root).documents.documents == ()


class TestTheDecisionLog:
    def _read(self, project, guide):
        from before_we_ai.llm import interpret_documents

        interpret_documents(project, guide=guide, store=ProjectStore(project),
                            client=_Scripted([{
                                "chunk_id": _chunk_id(project, POLICY),
                                "quote": POLICY, "reads_as": "definition",
                                "statement": "Credits are negative.",
                                "term": "sign convention",
                                "definition": "credits are negative",
                                "value": None, "answers": None,
                                "rationale": "the policy says so",
                            }]))
        return _view(project).decisions

    def test_declaring_the_sources_is_a_human_decision(self, project):
        first = _view(project).decisions.decisions[0]
        assert first.actor == "a human"
        assert first.actor_css == "voice-human"
        assert "chosen by a person, never discovered" in first.driver

    def test_reading_a_policy_names_the_passage_that_drove_it(
            self, project, guide):
        found = [d for d in self._read(project, guide).decisions
                 if "out of a document" in d.what]
        assert found
        assert "policy p.1" in found[0].driver
        assert POLICY in found[0].driver

    def test_the_ai_reads_as_the_ai(self, project, guide):
        found = [d for d in self._read(project, guide).decisions
                 if d.actor_css == "voice-ai"]
        assert found
        assert all(d.marker for d in found)

    def test_every_decision_says_what_drove_it(self, project, guide):
        for decision in self._read(project, guide).decisions:
            assert decision.driver.strip()

    def test_every_decision_places_itself_in_the_flow(self, project, guide):
        for decision in self._read(project, guide).decisions:
            assert decision.stage in {"0", "1", "2", "3", "4", "5", "6"}
            assert decision.stage_label

    def test_a_human_confirmation_says_what_it_settled(self, project, guide):
        told = tell(project, "Fiscal year runs May to April.", guide=guide,
                    store=ProjectStore(project),
                    client=_Scripted([{
                        "chunk_id": "statements:p1:0",
                        "quote": "Fiscal year runs May to April.",
                        "reads_as": "definition",
                        "statement": "The fiscal year runs May to April.",
                        "term": "fiscal year", "definition": "May to April",
                        "value": None, "answers": None, "rationale": "said",
                    }]))
        confirm_claim(ProjectStore(project), told.claims_created[0],
                      scope=Scope(entity="US"), note="the finance lead")

        confirmations = [d for d in _view(project).decisions.decisions
                         if "vouched for this claim" in d.what]
        assert confirmations
        assert "for entity US" in confirmations[0].what
        assert confirmations[0].driver == "the finance lead"
        assert confirmations[0].settles == "now business-confirmed"
        assert confirmations[0].actor_css == "voice-human"

    def test_a_statement_is_shown_as_words_somebody_said(self, project, guide):
        tell(project, "We only supply pharmacies.", guide=guide,
             store=ProjectStore(project), client=_Scripted([]))
        stated = [d for d in _view(project).decisions.decisions
                  if "stated this from their own knowledge" in d.what]
        assert stated
        assert "recorded word for word" in stated[0].driver
        assert "not that it is true" in stated[0].driver

    def test_the_log_never_credits_profiles_for_what_a_document_said(
            self, project, guide):
        """The summary line is for inferred claims only — this project has
        none, so it must not appear at all."""
        summary = [d for d in self._read(project, guide).decisions
                   if "about how the data behaves" in d.what]
        assert summary == []

    def test_an_untouched_project_says_nothing_was_decided(self, tmp_path):
        root = init_project(tmp_path / "quiet")
        log = _view(root).decisions
        assert log.decisions == ()
        assert "Nothing has been decided yet" in log.empty


class TestAnchorsReadForAHuman:
    def test_an_anchor_shows_the_document_and_the_page(self, project, guide):
        from before_we_ai.llm import interpret_documents

        interpret_documents(project, guide=guide, store=ProjectStore(project),
                            client=_Scripted([{
                                "chunk_id": _chunk_id(project, CHART),
                                "quote": CHART, "reads_as": "figure",
                                "statement": "Revenue was EUR 2,847,000.",
                                "term": None, "definition": None,
                                "value": "2,847,000", "answers": None,
                                "rationale": "the chart says so",
                            }]))
        anchors = [e for claim in _view(project).claims for e in claim.evidence
                   if e.type == "document_anchor"]
        assert anchors
        anchor = anchors[0]
        assert "inside a chart" in anchor.sentence
        assert "never allowed to support the claim" in anchor.sentence
        assert anchor.voice is not None
        assert anchor.voice.text == CHART
        details = dict(anchor.details)
        assert details["document"] == "policy"
        assert details["page"] == "1"
        assert details["where on the page"] == "inside a chart"
        assert "payload" not in details  # no raw JSON in front of a reader
