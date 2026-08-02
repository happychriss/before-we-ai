"""A question gets edited. What survives that, and what must not.

Nobody asks the right question first. They ask one, read what the machine
says is missing, and ask a better one — and the mockup's "Revision 3" is
that loop made visible. The design question is what an edit costs.

Keeping the request's identity is what makes the loop cheap: the waivers
and links taken on its dependency list are still about this question, and
minting a fresh request over a corrected typo would throw a human's work
away to no purpose.

The confirmation is the exception, and it is not a detail. It said "this
list is complete" about a question that is no longer the one on the page,
so it lapses exactly as it does when the guide moves under it — same
mechanism, and the verdict says which of the two happened, because one is
a change to a shared vocabulary and the other is a change the reader made
themselves.

These run offline against the two recorded classifications: revising the
P&L question into the receivables question is a real re-classification,
replayed, with no call and no new fixture.
"""

from pathlib import Path

import pytest
import yaml

from before_we_ai.core import Actor
from before_we_ai.core.enums import ActKind
from before_we_ai.core.objects import AnswerRequest, KnowledgeItem, RequiredKnowledge
from before_we_ai.core.enums import KnowledgeKind
from before_we_ai.domains import packaged
from before_we_ai.llm import UnknownRequest, ask, load_domain_guide, revise
from before_we_ai.readiness import confirm_classification, evaluate_request, waive_item
from before_we_ai.readiness.assemble import assemble
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.integration

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm"
GUIDE_FILE = packaged("finance")


@pytest.fixture
def project(tmp_path):
    root = init_project(tmp_path / "revisions")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["llm"] = {"offline": True, "fixtures_dir": str(FIXTURES),
                     "domain_guide_file": str(GUIDE_FILE)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    guide = load_domain_guide(GUIDE_FILE)
    store = ProjectStore(root)
    report = ask(root, "Can these files reliably produce actual P&L by entity "
                       "and month?", guide=guide, store=store, scenario="corpus")
    return root, guide, report.request


def _revise_to_receivables(root, guide, request_id):
    return revise(root, request_id, "What is still outstanding from our customers?",
                  guide=guide, store=ProjectStore(root),
                  scenario="corpus_receivables")


class TestWhatARevisionKeeps:
    def test_the_request_keeps_its_identity(self, project):
        root, guide, request = project
        revised = _revise_to_receivables(root, guide, request.id).request

        assert revised.id == request.id
        assert len(ProjectStore(root).requests) == 1

    def test_the_revision_is_counted_and_the_old_wording_kept(self, project):
        root, guide, request = project
        revised = _revise_to_receivables(root, guide, request.id).request

        assert revised.revision == 2
        assert [e.question for e in revised.earlier] == [request.question]
        assert revised.earlier[0].answer_type == "profit_and_loss_by_dimension"

    def test_a_waiver_survives_the_edit(self, project):
        """The reason identity is kept. A waiver is about one item, and the
        item is still on the list — losing it would make every edit cost a
        human's work over again."""
        root, guide, request = project
        waive_item(ProjectStore(root), guide, request.id, "journal.account",
                   "not needed for this cut")

        _revise_to_receivables(root, guide, request.id)

        acts = ProjectStore(root).acts_for(request.id)
        assert [a.kind for a in acts] == [ActKind.WAIVE]

    def test_re_classification_really_happens(self, project):
        """A revised question may belong to another family, and assuming it
        does not is the silent under-listing this design exists to stop."""
        root, guide, request = project
        revised = _revise_to_receivables(root, guide, request.id).request

        assert request.answer_type == "profit_and_loss_by_dimension"
        assert revised.answer_type == "open_receivables"

    def test_the_dependency_list_follows_the_new_question(self, project):
        root, guide, request = project
        _revise_to_receivables(root, guide, request.id)

        store = ProjectStore(root)
        refs = {i.ref() for i in assemble(store, guide,
                                          store.requests[request.id]).items}
        assert "subledger_ar" in refs
        assert "journal.entity" not in refs


class TestWhatARevisionCosts:
    def test_a_confirmation_does_not_survive_the_edit(self, project):
        root, guide, request = project
        confirm_classification(ProjectStore(root), guide, request.id)
        assert evaluate_request(ProjectStore(root), guide, request.id).confirmed

        _revise_to_receivables(root, guide, request.id)

        assert not evaluate_request(ProjectStore(root), guide, request.id).confirmed

    def test_the_verdict_says_the_question_moved_not_the_guide(self, project):
        """Which of the two happened is the reader's business: one is a
        change to a vocabulary everybody shares, the other is a change they
        made themselves a minute ago."""
        root, guide, request = project
        confirm_classification(ProjectStore(root), guide, request.id)
        _revise_to_receivables(root, guide, request.id)

        store = ProjectStore(root)
        review = assemble(store, guide, store.requests[request.id]).review
        assert review.lapsed_by == "question"
        assert "the question has been revised since" in review.note()

    def test_confirming_again_settles_it(self, project):
        """The loop has to close, or lapsing is just a way of being stuck."""
        root, guide, request = project
        confirm_classification(ProjectStore(root), guide, request.id)
        _revise_to_receivables(root, guide, request.id)

        confirm_classification(ProjectStore(root), guide, request.id)

        assert evaluate_request(ProjectStore(root), guide, request.id).confirmed

    def test_an_edit_that_changes_nothing_does_not_lapse_anything(self, project):
        """Re-asking the same question is not an edit. The fingerprint is
        over what the human read, so an idempotent re-ask has to be free —
        otherwise every re-run would demand a signature."""
        root, guide, request = project
        confirm_classification(ProjectStore(root), guide, request.id)

        revise(root, request.id, request.question, guide=guide,
               store=ProjectStore(root), scenario="corpus")

        assert evaluate_request(ProjectStore(root), guide, request.id).confirmed


class TestTheStaleDeltaProblem:
    """A revision that needs no extra items must not leave the previous
    revision's ones on the list — that would be the model's answer to a
    question nobody is asking any more."""

    def test_an_earlier_delta_is_emptied_rather_than_left_behind(self, project):
        root, guide, request = project
        store = ProjectStore(root)
        store.save_required_knowledge(RequiredKnowledge(
            request_id=request.id,
            items=[KnowledgeItem(kind=KnowledgeKind.RULE,
                                 name="a rule the first wording needed",
                                 why="drafted for revision 1")],
        ))
        assert store.knowledge_for(request.id).items

        _revise_to_receivables(root, guide, request.id)

        store = ProjectStore(root)
        assert store.knowledge_for(request.id).items == []
        assert len([r for r in store.required.values()
                    if r.request_id == request.id]) == 1


def test_revising_a_request_that_does_not_exist_is_refused(project):
    root, guide, _request = project
    with pytest.raises(UnknownRequest):
        revise(root, "01NOPE", "anything", guide=guide, store=ProjectStore(root),
               scenario="corpus")


def test_the_fingerprint_covers_what_a_human_read():
    """Not the id, not the timestamp: the four things on the page when
    somebody signed off the list."""
    base = AnswerRequest(question="q", requested_output="o", answer_type="t")
    assert base.fingerprint() == base.model_copy(
        update={"id": "01OTHER"}).fingerprint()
    for field, value in [("question", "q2"), ("requested_output", "o2"),
                         ("answer_type", "t2")]:
        assert base.model_copy(update={field: value}).fingerprint() != \
            base.fingerprint()


class TestWhatTheReaderSees:
    """A revision count on its own reads as a reason to distrust the page.
    Beside it has to stand what the edit cost, or the reader has to guess."""

    def _model(self, root):
        from readiness_report.projection import build_view_model
        config = yaml.safe_load((root / "before-ai.yaml").read_text())
        return build_view_model(ProjectStore(root), root, config)

    def test_a_first_wording_carries_no_version_line(self, project):
        """Most questions are never edited, and a "Revision 1" on every one
        of them is noise that teaches the reader to skip the line."""
        root, _guide, _request = project
        (view,) = self._model(root).requests
        assert view.revision_line == ""
        assert view.earlier == ()

    def test_a_revised_question_says_what_the_edit_cost(self, project):
        root, guide, request = project
        confirm_classification(ProjectStore(root), guide, request.id)
        _revise_to_receivables(root, guide, request.id)

        (view,) = self._model(root).requests
        assert view.revision_line.startswith("Revision 2")
        assert "a confirmation of the list was not" in view.revision_line
        assert view.earlier == (
            f"Revision 1: {request.question} — treated as "
            "'profit_and_loss_by_dimension'",
        )
