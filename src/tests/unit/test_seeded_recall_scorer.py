"""The Seeded-Recall scorer, measured — a negative control it never had.

The project's own rule is *test a heuristic by mutation*: build the case that
should fail and check that it does. That rule was applied to the checks, to the
domain laws and to the document pipeline. It was never applied to the thing
that produces the headline number.

These tests are therefore **written to pass against the defect**, and to turn
red the day it is fixed. That is deliberate. A limitation with a test against
it has a name and a failing case; a limitation without one is just something
nobody has noticed yet. When the scorer is rewritten (see
`docs/seeded-recall.md` → "What the number does not measure"), this file is
expected to fail — update it in the same change, and update the doc with it.

Nothing here calls a model, reads the corpus, or costs anything.
"""

import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# tests/eval/ holds runnable tools rather than importable modules, so it is not
# on the path by default. Importing it here is the point: the tool that reports
# the number is the thing under test.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
import seeded_recall as scorer  # noqa: E402

from before_we_ai.core import Actor  # noqa: E402
from before_we_ai.core.objects import Claim  # noqa: E402

IN_SCOPE = {trap: m for trap, m in scorer.MATCHERS.items() if m.scope == "v1"}


class _Predicate:
    """Just enough of a predicate for the matcher to accept it."""

    def __init__(self, name):
        self.name = name
        self.params = {}


def _claim(statement: str, predicate: str | None) -> Claim:
    claim = Claim.__new__(Claim)
    object.__setattr__(claim, "statement", statement)
    object.__setattr__(claim, "predicate", _Predicate(predicate) if predicate else None)
    object.__setattr__(claim, "created_by", Actor.AI)
    return claim


def _fabricated() -> list[Claim]:
    """One claim per matcher whose statement is false, carrying the tokens the
    matcher greps for."""
    claims = []
    for matcher in IN_SCOPE.values():
        tokens = [group[0] for group in matcher.groups if group]
        statement = ("Nothing whatsoever is true about " + " and ".join(tokens) + "."
                     if tokens else "This sentence asserts nothing.")
        claims.append(_claim(statement,
                             matcher.predicates[0] if matcher.predicates else None))
    return claims


def test_false_claims_score_full_marks():
    """The defect, stated as a number.

    Every statement below is false. The scorer awards all 25 in-scope traps,
    because `matches()` is a lowercased substring test over the statement, the
    predicate params and the binding — it never reads what a claim asserts.
    """
    fabricated = _fabricated()
    scored = [trap for trap, matcher in IN_SCOPE.items()
              if scorer.matches(matcher, fabricated)]
    assert len(scored) == len(IN_SCOPE) == 25, (
        "if this fails the scorer changed — re-measure and update "
        "docs/seeded-recall.md")


def test_negation_does_not_change_the_verdict():
    """Sharper still: a claim and its exact negation score identically."""
    trap, matcher = "F1", IN_SCOPE["F1"]
    asserted = _claim("de_erp__invoices.order_reference references "
                      "de_erp__orders.order_id.", None)
    denied = _claim("de_erp__invoices.order_reference does NOT reference "
                    "de_erp__orders.order_id, and never did.", None)
    assert scorer.matches(matcher, [asserted]) is not None
    assert scorer.matches(matcher, [denied]) is not None, (
        f"{trap}: the negation scores too — the matcher reads tokens, not claims")


def test_most_matchers_cannot_survive_a_change_of_landscape():
    """21 of 25 fire only on a token naming a table or column in *this* corpus.

    Point the pipeline at `corpora/vessel/` and the number falls because the
    words changed, not because the machine got worse. That is why a second
    landscape needs behaviour-class scoring before its recall figure means
    anything.
    """
    keyed = [trap for trap, matcher in IN_SCOPE.items()
             if any("_" in token for group in matcher.groups for token in group)]
    assert len(keyed) == 21, sorted(keyed)


def test_the_blind_traps_are_in_no_automated_measurement():
    """BLIND_1/2/3 carry an empty matcher and `scope="blind"`, so the report
    always prints "out of scope" for them. The traps the owner held back to
    catch what the implementer did not anticipate are scored by nobody."""
    blind = {trap: m for trap, m in scorer.MATCHERS.items() if m.scope == "blind"}
    assert set(blind) == {"BLIND_1", "BLIND_2", "BLIND_3"}
    assert all(m.groups == ((),) for m in blind.values())
