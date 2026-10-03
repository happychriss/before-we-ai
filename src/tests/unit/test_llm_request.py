"""The request contract: a business question becomes a classified request.

The contract's own guarantee is narrow and worth stating: it creates no
claim, no evidence and no status. It writes down what the question asks for
and which family of questions it belongs to — the rest of the pipeline
decides whether any of it holds. What these tests guard is that neither the
classification nor a drafted item can ever name something the readiness
evaluator would be unable to resolve, because an unresolvable dependency is
a gap that would go quiet.
"""

import json

import pytest

from before_we_ai.domains import packaged
from before_we_ai.llm import load_domain_guide
from before_we_ai.llm.client import Completion
from before_we_ai.llm.domain_guide import (
    AnswerTypeRequire,
    AnswerTypeSpec,
    DomainGuide,
)
from before_we_ai.llm.inputs import build_question_context
from before_we_ai.llm.mapping import (
    check_classification,
    check_knowledge_item,
    draft_to_request,
    item_to_knowledge,
)
from before_we_ai.llm.prompts import REQUEST_SYSTEM
from before_we_ai.llm.schemas import AnswerRequestDraft, KnowledgeItemProposal
from before_we_ai.llm.request import ask
from before_we_ai.core import Actor, KnowledgeKind, Scope
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.contract

QUESTION = "Can these files reliably produce actual P&L by entity and month?"


@pytest.fixture
def guide() -> DomainGuide:
    return DomainGuide.model_validate({
        "domain": "finance",
        "objects": {
            "journal": {
                "decided_by": "balance",
                "definition": "the ledger of record",
                "fields": {
                    "amount_local": {"decided_by": "slot", "fills": "amount",
                                     "definition": "the signed amount"},
                    "entity": {"decided_by": "clarification",
                               "definition": "the legal entity"},
                },
            },
            "intercompany": {
                "decided_by": "ic_symmetry",
                "definition": "paired postings between two entities",
            },
        },
    })


def _item(**overrides) -> KnowledgeItemProposal:
    base = {"kind": "object", "name": "journal", "of_object": None,
            "why": "actuals are summed from it"}
    return KnowledgeItemProposal.model_validate({**base, **overrides})


class TestTheInput:
    def test_the_question_leads_and_the_vocabulary_follows(self, guide):
        text = build_question_context(QUESTION, guide).text
        assert text.index(QUESTION) < text.index("journal")

    def test_fields_are_rendered_under_their_object(self, guide):
        """Unlike the role-binding input, which flattens on purpose: here a
        field is a property *of* something, and the model must be able to
        say which."""
        text = build_question_context(QUESTION, guide).text
        assert "- journal: the ledger of record" in text
        assert "  - amount_local: the signed amount" in text

    def test_no_settlement_machinery_reaches_the_model(self, guide):
        text = build_question_context(QUESTION, guide).text
        for internal in ("decided_by", "fills", "slot", "clarification",
                         "balance", "ic_symmetry"):
            assert internal not in text

    def test_the_same_question_builds_the_same_bytes(self, guide):
        assert (build_question_context(QUESTION, guide).sha256
                == build_question_context(QUESTION, guide).sha256)


class TestSemanticChecks:
    def test_a_clean_item_of_each_kind_passes(self, guide):
        for item in (
            _item(),
            _item(kind="field", name="entity", of_object="journal"),
            _item(kind="rule", name="sign convention", of_object=None),
        ):
            assert check_knowledge_item(item, guide) == []

    def test_an_object_the_vocabulary_lacks_is_rejected(self, guide):
        errors = check_knowledge_item(_item(name="warehouse"), guide)
        assert errors and "no business object" in errors[0]

    def test_a_field_named_as_an_object_is_told_where_it_lives(self, guide):
        errors = check_knowledge_item(_item(name="entity"), guide)
        assert "it is a field of 'journal'" in errors[0]

    def test_a_field_must_name_its_object_and_the_right_one(self, guide):
        assert "must name the object" in \
            check_knowledge_item(_item(kind="field", name="entity"), guide)[0]
        errors = check_knowledge_item(
            _item(kind="field", name="entity", of_object="intercompany"), guide)
        assert "belongs to 'journal'" in errors[0]

    def test_a_rule_may_not_shadow_a_vocabulary_entry(self, guide):
        """A rule exists because the vocabulary has no entry for it. Naming
        one means the item is a mis-kinded object or field."""
        errors = check_knowledge_item(_item(kind="rule", name="journal"), guide)
        assert "kind=object" in errors[0]
        errors = check_knowledge_item(_item(kind="rule", name="entity"), guide)
        assert "kind=field" in errors[0]

    def test_a_rule_the_vocabulary_does_not_contain_is_the_point(self, guide):
        assert check_knowledge_item(
            _item(kind="rule", name="which accounts are profit and loss"),
            guide) == []

    def test_an_item_without_a_why_cannot_be_pruned_so_it_is_rejected(self, guide):
        errors = check_knowledge_item(_item(why="  "), guide)
        assert any("'why' is empty" in e for e in errors)


class TestMapping:
    def test_every_item_inherits_the_requests_scope_not_its_own(self):
        draft = AnswerRequestDraft(
            requested_output="P&L per entity per month",
            scope={"entity": "DE"},
            required_knowledge=[_item()],
            rationale="…",
        )
        request = draft_to_request(QUESTION, draft)
        assert request.question == QUESTION
        assert request.scope.entity == "DE"
        item = item_to_knowledge(draft.required_knowledge[0], request.scope)
        assert item.scope == request.scope
        assert item.kind is KnowledgeKind.OBJECT

    def test_no_scope_in_the_question_means_landscape_wide(self):
        draft = AnswerRequestDraft(requested_output="x", required_knowledge=[],
                                   rationale="…")
        assert draft_to_request(QUESTION, draft).scope == Scope()


class TestPrompt:
    def test_it_names_no_domain(self):
        """Same rule as V1/V2: domain knowledge enters through the built
        input, never through the prompt."""
        lowered = REQUEST_SYSTEM.lower()
        for noun in ("journal", "ledger", "account", "invoice", "posting"):
            assert noun not in lowered

    def test_it_tells_the_model_it_decides_nothing(self):
        assert "You decide nothing here." in REQUEST_SYSTEM


class _ScriptedClient:
    """One canned answer, through the real validation and mapping path."""

    name = "scripted"

    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def complete(self, **kwargs) -> Completion:
        self.calls += 1
        return Completion(text=json.dumps(self.payload), usage={}, ms=0)


class TestAsk:
    def _payload(self, items: list[dict]) -> dict:
        return {"requested_output": "P&L per entity per month", "scope": None,
                "required_knowledge": items, "rationale": "…"}

    def _project(self, tmp_path) -> ProjectStore:
        return ProjectStore(init_project(tmp_path / "p"), create=True)

    def test_it_saves_the_request_and_its_knowledge(self, tmp_path, guide):
        store = self._project(tmp_path)
        client = _ScriptedClient(self._payload([
            _item().model_dump(),
            _item(kind="field", name="amount_local",
                  of_object="journal").model_dump(),
        ]))
        report = ask(store.root, QUESTION, guide=guide, client=client, store=store)
        assert report.failure is None and report.skipped == []
        assert [i.ref() for i in report.required.items] == \
            ["journal", "journal.amount_local"]
        reloaded = ProjectStore(store.root)
        assert reloaded.knowledge_for(report.request.id) == report.required

    def test_a_bad_item_is_skipped_and_named_the_rest_survive(self, tmp_path, guide):
        """The V1 discipline: one unresolvable dependency never sinks the
        decomposition, and it is reported rather than dropped."""
        store = self._project(tmp_path)
        client = _ScriptedClient(self._payload([
            _item().model_dump(),
            _item(name="warehouse").model_dump(),
        ]))
        report = ask(store.root, QUESTION, guide=guide, client=client, store=store)
        assert [i.name for i in report.required.items] == ["journal"]
        assert len(report.skipped) == 1
        name, reason = report.skipped[0]
        assert name == "warehouse" and "no business object" in reason

    def test_it_creates_no_claim_and_no_evidence(self, tmp_path, guide):
        store = self._project(tmp_path)
        client = _ScriptedClient(self._payload([_item().model_dump()]))
        ask(store.root, QUESTION, guide=guide, client=client, store=store)
        reloaded = ProjectStore(store.root)
        assert reloaded.claims == {} and reloaded.evidence == {}

    def test_a_call_that_never_validates_creates_nothing(self, tmp_path, guide):
        store = self._project(tmp_path)
        client = _ScriptedClient({"nonsense": True})
        report = ask(store.root, QUESTION, guide=guide, client=client, store=store)
        assert report.failure and report.request is None
        assert client.calls == 2  # exactly one retry, as everywhere
        assert ProjectStore(store.root).requests == {}


class TestClassification:
    """The one claim the call exists to make.

    Everything the answer depends on follows from it, so unlike a delta item
    it is not skippable: a request classified to a family the guide cannot
    expand is worse than no request at all.
    """

    def _typed(self, guide) -> DomainGuide:
        return guide.model_copy(update={"answer_types": {
            "profit_and_loss": AnswerTypeSpec(
                definition="the result of a period",
                requires=[AnswerTypeRequire(object="journal")]),
        }})

    def test_the_answer_types_reach_the_model_with_what_they_require(self, guide):
        """A definition alone does not let the model judge coverage."""
        text = build_question_context(QUESTION, self._typed(guide)).text
        assert "- profit_and_loss: the result of a period" in text
        assert "  - requires object: journal" in text

    def test_no_settlement_machinery_leaks_through_the_new_section(self, guide):
        text = build_question_context(QUESTION, self._typed(guide)).text
        for internal in ("decided_by", "fills", "slot", "clarification",
                         "balance", "ic_symmetry"):
            assert internal not in text

    def test_a_guide_without_answer_types_renders_no_section(self, guide):
        assert "answer type" not in build_question_context(QUESTION, guide).text

    def test_naming_no_type_is_allowed_because_forcing_a_fit_is_worse(self, guide):
        draft = AnswerRequestDraft(requested_output="o", answer_type=None,
                                   rationale="r")
        assert check_classification(draft, self._typed(guide)) is None

    def test_a_type_the_guide_does_not_declare_is_an_error(self, guide):
        draft = AnswerRequestDraft(requested_output="o",
                                   answer_type="balance_sheet", rationale="r")
        error = check_classification(draft, self._typed(guide))
        assert "balance_sheet" in error and "profit_and_loss" in error

    def test_a_bad_classification_fails_the_whole_call(self, tmp_path, guide):
        store = ProjectStore(init_project(tmp_path / "p"), create=True)
        client = _ScriptedClient({"requested_output": "o",
                                  "answer_type": "balance_sheet",
                                  "required_knowledge": [], "rationale": "r"})
        report = ask(store.root, QUESTION, guide=self._typed(guide),
                     client=client, store=store)
        assert report.failure and "balance_sheet" in report.failure
        assert report.request is None
        assert client.calls == 2  # one retry, as everywhere
        assert ProjectStore(store.root).requests == {}

    def test_a_covered_question_stores_a_request_and_no_list(self, tmp_path, guide):
        """Nothing to store: the list is expanded from the guide on read."""
        store = ProjectStore(init_project(tmp_path / "p"), create=True)
        client = _ScriptedClient({"requested_output": "o",
                                  "answer_type": "profit_and_loss",
                                  "required_knowledge": [], "rationale": "r"})
        report = ask(store.root, QUESTION, guide=self._typed(guide),
                     client=client, store=store)
        assert report.failure is None
        assert report.request.answer_type == "profit_and_loss"
        assert report.required is None
        reloaded = ProjectStore(store.root)
        assert reloaded.knowledge_for(report.request.id) is None

    def test_a_delta_is_stored_alongside_the_classification(self, tmp_path, guide):
        store = ProjectStore(init_project(tmp_path / "p"), create=True)
        client = _ScriptedClient({
            "requested_output": "o", "answer_type": "profit_and_loss",
            "required_knowledge": [_item(kind="rule", name="in USD at which rate",
                                         of_object=None).model_dump()],
            "rationale": "r"})
        report = ask(store.root, QUESTION, guide=self._typed(guide),
                     client=client, store=store)
        assert [i.name for i in report.required.items] == \
            ["in USD at which rate"]


def test_the_shipped_fixture_matches_the_shipped_guide():
    """The corpus fixture is only as good as its input hash; the drift
    guard in the corpus suite owns that. Here: it is well-formed, and it
    is a real recording — this contract answered a live model for the
    first time on 2026-08-02, so the hand-authored placeholder is gone and
    must not come back without someone saying why."""
    from pathlib import Path

    path = (Path(__file__).resolve().parents[1] / "fixtures" / "llm"
            / "request__finance.json")
    entry = json.loads(path.read_text(encoding="utf-8"))
    assert entry["recorded_at"] != "hand-authored"
    assert entry["source_log"].endswith(".json")
    guide = load_domain_guide(packaged("finance"))
    draft = AnswerRequestDraft.model_validate_json(entry["response_text"])
    assert check_classification(draft, guide) is None
    for item in draft.required_knowledge:
        assert check_knowledge_item(item, guide) == []
