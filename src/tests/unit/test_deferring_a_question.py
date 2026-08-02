"""*I looked at this and I cannot answer it.*

The work list ranks by what a question holds up, which is right and is
also why it never moves: the reader who cannot answer the top card meets
it again every time they open the page, and the cards behind it — which
somebody else could answer — stay behind it.

Deferring is the smallest honest fix. The danger in it is equally small
and much worse: if "I don't know" quietly took a question out of the way,
it would be the most tempting button on the page, and the verdict would
start reflecting how tired the reader was. So the line these tests hold is
that a deferral moves the *order* and nothing else.

The sibling operation is `waive_item`, and the difference is the whole
design: a waiver says "the answer does not rest on this" and really does
unblock; a deferral says "I do not know", which is the state the answer
was already in.
"""

from pathlib import Path

import pytest
import yaml

from before_we_ai.core import Actor, ClarificationQuestion, Scope
from before_we_ai.core.objects import Claim
from before_we_ai.statements import defer_question, pick_up_question
from before_we_ai.store import ProjectStore, init_project
from readiness_report.projection import build_view_model

pytestmark = pytest.mark.integration


@pytest.fixture
def project(tmp_path):
    """Two questions, so an order exists to be changed."""
    root = init_project(tmp_path / "deferring")
    store = ProjectStore(root, create=False)
    claim = store.add_claim(Claim(statement="a rule", created_by=Actor.AI))
    first = ClarificationQuestion(
        question="Which column carries the account?",
        finding="3 candidates", claim_ids=[claim.id])
    second = ClarificationQuestion(
        question="Which cut-off applies to late postings?",
        claim_ids=[claim.id])
    store.save_question(first)
    store.save_question(second)
    return root, first, second


def _cards(root: Path):
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    return build_view_model(ProjectStore(root), root, config).open_questions


class TestWhatDeferringDoes:
    def test_the_card_records_who_could_not_answer_it(self, project):
        root, first, _second = project
        defer_question(ProjectStore(root), first.id, note="ask the controller")

        card = ProjectStore(root).questions[first.id]
        assert card.deferred is not None
        assert card.deferred.by is Actor.HUMAN
        assert card.deferred.note == "ask the controller"

    def test_the_reader_is_told_who_and_why_not(self, project):
        root, first, _second = project
        defer_question(ProjectStore(root), first.id, note="ask the controller")

        view = next(c for c in _cards(root) if c.id == first.id)
        assert view.deferred == "marked 'I don't know' by you — ask the controller"

    def test_it_sorts_behind_a_card_nobody_has_given_up_on(self, project):
        root, first, second = project
        before = [c.id for c in _cards(root)]
        assert before.index(first.id) < before.index(second.id)

        defer_question(ProjectStore(root), first.id)

        after = [c.id for c in _cards(root)]
        assert after.index(first.id) > after.index(second.id)

    def test_nothing_is_hidden(self, project):
        """The list is the same list. A deferred question a reader cannot
        find is a question that has been answered by attrition."""
        root, first, _second = project
        defer_question(ProjectStore(root), first.id)

        assert {c.id for c in _cards(root)} == {c.id for c in _cards(root)}
        assert len(_cards(root)) == 2

    def test_picking_it_back_up_undoes_it(self, project):
        root, first, second = project
        defer_question(ProjectStore(root), first.id)

        pick_up_question(ProjectStore(root), first.id)

        assert ProjectStore(root).questions[first.id].deferred is None
        order = [c.id for c in _cards(root)]
        assert order.index(first.id) < order.index(second.id)


class TestWhatDeferringMustNotDo:
    """The line. Everything above is convenience; this is the invariant."""

    def test_the_band_does_not_move(self, project):
        root, first, _second = project
        before = next(c for c in _cards(root) if c.id == first.id)

        defer_question(ProjectStore(root), first.id)

        after = next(c for c in _cards(root) if c.id == first.id)
        assert after.rank == before.rank
        assert after.bearing == before.bearing
        assert after.because == before.because

    def test_the_claim_it_rests_on_is_untouched(self, project):
        """No evidence, no status change, nothing a check could disagree
        with. A deferral is a note about a person, not about the data."""
        root, first, _second = project
        store = ProjectStore(root)
        (claim,) = store.claims.values()
        before = claim.status

        defer_question(store, first.id)

        store = ProjectStore(root)
        assert store.claims[claim.id].status is before
        assert store.evidence == {}

    def test_the_finding_is_still_shown(self, project):
        """Deferring says nothing about the measurement, so the measurement
        stays in front of the reader."""
        root, first, _second = project
        defer_question(ProjectStore(root), first.id)

        view = next(c for c in _cards(root) if c.id == first.id)
        assert view.finding == "3 candidates"


def test_a_stuck_queue_says_so_rather_than_looking_untouched(tmp_path):
    """Five open blockers read the same whether nobody has started or
    everybody has already failed. The tally has to tell those apart, or the
    reader's own effort is invisible to them.

    Needs a real request, because "urgent" means "holds up the answer that
    was asked" — a project with no question has no urgent half to stall.
    """
    from before_we_ai.core.objects import MappingClaim
    from before_we_ai.domains import packaged
    from before_we_ai.llm import ask, load_domain_guide

    fixtures = Path(__file__).resolve().parents[1] / "fixtures" / "llm"
    guide_file = packaged("finance")
    root = init_project(tmp_path / "stuck")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["llm"] = {"offline": True, "fixtures_dir": str(fixtures),
                     "domain_guide_file": str(guide_file)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    guide = load_domain_guide(guide_file)
    ask(root, "Can these files reliably produce actual P&L by entity and "
              "month?", guide=guide, store=ProjectStore(root), scenario="corpus")

    store = ProjectStore(root)
    binding = store.add_claim(MappingClaim(
        statement="Rolle journal = ledger", created_by=Actor.AI, role="journal",
        binding={"table": "ledger", "amount_local": "amount"}))
    card = ClarificationQuestion(
        question="Which of the proposed candidates is the 'journal'?",
        claim_ids=[binding.id])
    store.save_question(card)

    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    started = build_view_model(ProjectStore(root), root, config)
    assert started.question_tally.urgent == 1
    assert "I don't know" not in started.question_tally.outlook

    defer_question(ProjectStore(root), card.id)

    stalled = build_view_model(ProjectStore(root), root, config).question_tally
    assert stalled.urgent == 1  # deferring took nothing out of the urgent half
    assert ("1 of the 1 has already been marked \'I don\'t know\'"
            in stalled.outlook)
    assert "need somebody else" in stalled.outlook
