"""Twenty-three open questions, and only some of them are in your way.

The owner's finding (2026-08-02): the work list has no priority. Every
question reads alike, so a reader cannot tell that four of twenty-three
stand between them and their answer and the rest are ordinary data
findings that this question does not wait on.

`gap_load` has ranked unproven claims by the questions resting on them
since M3 and nothing ever called it. What was missing was the other half:
which questions bear on *the question that was asked*. That comes off the
ReadinessMap, and it has to — the wording of a card is stored project
data, while the map is recomputed on every read. Priority derived from
the map goes stale by construction; priority written into a card could
not.
"""

import pytest

from before_we_ai.core import Actor, ClaimStatus
from before_we_ai.core.objects import ClarificationQuestion, Claim
from readiness_report.projection import (
    GuideShape,
    _build_questions,
    _question_bearing,
)

pytestmark = pytest.mark.unit


class _Item:
    def __init__(self, ref, claim_ids, satisfied=False, structural=True):
        self._ref = ref
        self.claim_ids = tuple(claim_ids)
        self.satisfied = satisfied
        self.structural = structural

    @property
    def ref(self):
        return self._ref


class _Map:
    def __init__(self, items):
        self.items = tuple(items)

    def unsupported(self):
        return [i for i in self.items if not i.satisfied]

    def blocking(self):
        return [i for i in self.unsupported() if i.structural]

    def limitations(self):
        return [i for i in self.unsupported() if not i.structural]


def _claim(statement="a claim"):
    return Claim(statement=statement, created_by=Actor.AI,
                 status=ClaimStatus.PROPOSED)


def _card(question, claim_ids):
    return ClarificationQuestion(question=question, claim_ids=list(claim_ids))


class TestWhichBandAQuestionFallsIn:
    def test_a_claim_under_a_blocking_item_blocks(self):
        bands = _question_bearing([_Map([_Item("journal.entity", ["c1"])])])
        rank, label, because = bands["c1"]
        assert rank == 0
        assert label == "blocks the answer"
        assert "journal.entity" in because

    def test_a_claim_under_a_rule_item_only_limits(self):
        """A rule costs the answer its meaning, not its numbers."""
        bands = _question_bearing(
            [_Map([_Item("sign convention", ["c1"], structural=False)])])
        assert bands["c1"][0] == 1
        assert bands["c1"][1] == "limits the answer"

    def test_a_satisfied_item_confers_no_urgency(self):
        bands = _question_bearing(
            [_Map([_Item("journal", ["c1"], satisfied=True)])])
        assert "c1" not in bands

    def test_a_claim_under_two_items_takes_the_worse_one(self):
        bands = _question_bearing([_Map([
            _Item("sign convention", ["c1"], structural=False),
            _Item("journal.entity", ["c1"]),
        ])])
        assert bands["c1"][1] == "blocks the answer"

    def test_a_claim_under_nothing_is_not_on_the_path(self):
        """The default, and the one that matters most: most findings on a
        real landscape have nothing to do with the question asked."""
        bands = _question_bearing([_Map([_Item("journal.entity", ["c1"])])])
        assert "c2" not in bands


class TestTheOrderAReaderGets:
    def _views(self, cards, claims, maps):
        by_id = {c.id: c for c in claims}
        open_views, _ = _build_questions(
            cards, by_id, GuideShape(), _question_bearing(maps))
        return open_views

    def test_blocking_questions_come_first(self):
        blocker, bystander = _claim("blocks"), _claim("bystander")
        cards = [_card("a bystander question", [bystander.id]),
                 _card("a blocking question", [blocker.id])]
        maps = [_Map([_Item("journal.entity", [blocker.id])])]
        views = self._views(cards, [blocker, bystander], maps)
        assert [v.question for v in views] == ["a blocking question",
                                               "a bystander question"]
        assert views[0].rank == 0 and views[1].rank == 3

    def test_within_a_band_the_heavier_question_comes_first(self):
        """gap_load's actual job: of two questions that both block, the one
        holding up more work is the one to answer."""
        heavy, light = _claim("heavy"), _claim("light")
        cards = [
            _card("light question", [light.id]),
            _card("heavy question", [heavy.id]),
            _card("also resting on heavy", [heavy.id]),
        ]
        maps = [_Map([_Item("journal.entity", [heavy.id, light.id])])]
        views = self._views(cards, [heavy, light], maps)
        assert all(v.rank == 0 for v in views)
        assert views[0].load == 2
        assert views[-1].question == "light question"

    def test_nothing_is_dropped(self):
        """The order changes; the list does not."""
        claims = [_claim(f"c{i}") for i in range(4)]
        cards = [_card(f"question {i}", [c.id]) for i, c in enumerate(claims)]
        views = self._views(cards, claims, [_Map([])])
        assert len(views) == len(cards)
        assert {v.question for v in views} == {c.question for c in cards}

    def test_every_question_says_why_it_is_where_it_is(self):
        blocker = _claim("blocks")
        views = self._views([_card("q", [blocker.id])], [blocker],
                            [_Map([_Item("journal.entity", [blocker.id])])])
        assert views[0].because.strip()
        assert views[0].bearing.strip()

