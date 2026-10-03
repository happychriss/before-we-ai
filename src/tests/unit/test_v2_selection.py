"""Which claims V2 will plan a check for.

The selection used to read `created_by is Actor.AI and status is PROPOSED`,
which quietly made human and document knowledge the one kind of claim
nothing could question. The spec says the opposite, and says why: a
testimonial claim carries no data fingerprint, so a contradicting check is
its *only* expiry date. These tests pin the widened rule before M5 starts
producing the claims it applies to.
"""
import pytest

from before_we_ai.llm.v2_bind import _untested_claims
from before_we_ai.core import (
    Actor,
    ClaimStatus,
    Predicate,
    CheckPlan,
    create_claim,
)
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.integration


def _store(tmp_path) -> ProjectStore:
    return ProjectStore(init_project(tmp_path / "p"))


def _claim(store, author=Actor.AI, status=ClaimStatus.PROPOSED,
           predicate="references", statement="x"):
    claim = create_claim(statement, author,
                         predicate=Predicate(name=predicate) if predicate else None)
    if status is not ClaimStatus.PROPOSED:
        claim = claim.model_copy(update={"status": status})
    store.save_claim(claim)
    return claim


def test_a_human_claim_is_testable_like_any_other(tmp_path):
    """The shape M5 produces: a policy read from a document, confirmed by a
    human. It must reach the check planner, or the one claim class nobody
    can question is the one nobody measured."""
    store = _store(tmp_path)
    policy = _claim(store, author=Actor.HUMAN,
                    status=ClaimStatus.BUSINESS_CONFIRMED,
                    statement="revenue excludes contra accounts")
    assert [c.id for c in _untested_claims(store, None)] == [policy.id]


def test_a_test_supported_claim_without_a_plan_is_still_selectable(tmp_path):
    """Status says what is believed, not what has been tried."""
    store = _store(tmp_path)
    claim = _claim(store, status=ClaimStatus.TEST_SUPPORTED)
    assert [c.id for c in _untested_claims(store, None)] == [claim.id]


def test_a_claim_that_already_has_a_plan_is_not_re_planned(tmp_path):
    """What keeps a re-run from re-doing settled work."""
    store = _store(tmp_path)
    claim = _claim(store)
    store.save_check_plan(CheckPlan(template="anti_join", claim_id=claim.id))
    assert _untested_claims(store, None) == []


def test_a_free_text_claim_is_not_selectable(tmp_path):
    """No predicate, nothing to parameterise — the one filter that stayed."""
    store = _store(tmp_path)
    _claim(store, predicate=None)
    assert _untested_claims(store, None) == []


def test_the_explicit_id_list_still_narrows(tmp_path):
    store = _store(tmp_path)
    wanted = _claim(store, statement="a")
    _claim(store, statement="b")
    assert [c.id for c in _untested_claims(store, [wanted.id])] == [wanted.id]


def test_every_author_reaches_the_planner(tmp_path):
    store = _store(tmp_path)
    ids = {_claim(store, author=a, statement=a.value).id
           for a in (Actor.AI, Actor.HUMAN, Actor.SYSTEM)}
    assert {c.id for c in _untested_claims(store, None)} == ids
