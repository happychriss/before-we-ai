"""``anchor()`` — the one write V3 gets, and what it structurally cannot do.

The facade was shaped in the refactor to accept exactly one more weak
writer without ever exposing ``add_evidence``. This is that writer, and
these tests pin the three things that make it safe: an anchor promotes
nothing, a quote that is not in the document cannot be stored, and a kind
outside the derived vocabulary is refused.
"""

import pytest

from before_we_ai.core import Actor, ClaimStatus, EvidenceType, resolve_status
from before_we_ai.core.objects import Claim, Predicate
from before_we_ai.store import ProjectStore, ProposalStore, QuoteNotFound, init_project

pytestmark = pytest.mark.unit

CHUNK = "Credit amounts are booked as negative numbers. Revenue is 4000-4999."
QUOTE = "Credit amounts are booked as negative numbers."


@pytest.fixture
def proposals(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    claim = Claim(
        statement="credit amounts are stored negative",
        predicate=Predicate(name="concept_definition",
                            params={"term": "sign_convention"}),
        created_by=Actor.AI,
    )
    store.save_claim(claim)
    return ProposalStore(store), store, claim


def _anchor(proposals, claim, **overrides):
    kwargs = dict(quote=QUOTE, chunk_id="policy:p1:0", chunk_text=CHUNK,
                  kind="text", source="policy", page=1)
    kwargs.update(overrides)
    return proposals.anchor(claim.id, **kwargs)


def test_an_anchor_is_stored_with_where_it_came_from(proposals):
    facade, store, claim = proposals
    record = _anchor(facade, claim)

    assert record.type is EvidenceType.DOCUMENT_ANCHOR
    assert record.actor is Actor.AI
    assert store.evidence[record.id].payload == {
        "quote": QUOTE, "chunk_id": "policy:p1:0", "kind": "text",
        "source": "policy", "page": 1,
    }


def test_an_anchor_promotes_nothing(proposals):
    """The reason V3 may hold this method at all."""
    facade, store, claim = proposals
    record = _anchor(facade, claim)

    assert resolve_status(store.claims[claim.id], [record]) is ClaimStatus.PROPOSED


def test_many_anchors_still_promote_nothing(proposals):
    """Corroboration is reconciliation's business, never the store's."""
    facade, store, claim = proposals
    records = [
        _anchor(facade, claim, chunk_id=f"policy:p1:{i}") for i in range(4)
    ]
    assert resolve_status(store.claims[claim.id], records) is ClaimStatus.PROPOSED


def test_a_quote_that_is_not_in_the_chunk_cannot_be_stored(proposals):
    """A hallucinated citation fails at the write, not at review."""
    facade, store, claim = proposals
    with pytest.raises(QuoteNotFound, match="really there"):
        _anchor(facade, claim, quote="Revenue is recognised on shipment.")
    assert store.evidence == {}


def test_near_misses_are_refused_too(proposals):
    """Verbatim means verbatim — a reworded quote is a different sentence."""
    facade, _store, claim = proposals
    with pytest.raises(QuoteNotFound):
        _anchor(facade, claim, quote="Credit amounts are booked as negatives.")


def test_a_kind_outside_the_derived_vocabulary_is_refused(proposals):
    facade, store, claim = proposals
    with pytest.raises(ValueError, match="derived from page"):
        _anchor(facade, claim, kind="footnote")
    assert store.evidence == {}


def test_the_facade_still_hides_general_evidence_writing(tmp_path):
    """Widening by one narrow method must not widen anything else."""
    store = ProjectStore(init_project(tmp_path / "facade"))
    facade = ProposalStore(store)

    assert not hasattr(facade, "add_evidence")
    assert not hasattr(facade, "mark_evidence_stale")
    assert not hasattr(facade, "attach_evidence")
