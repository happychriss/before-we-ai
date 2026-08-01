"""The proposed-only guardrail holds structurally through the LLM path.

Nothing here is new enforcement — the M1 core owns the law. These tests
prove the LLM layer rides on it: AI-born claims start proposed, AI cannot
author promoting evidence, and model-facing code receives only proposal
capabilities."""

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

# The one corpus project construction, owner-facing support rather than test
# code (WP3). A test may depend on it; product code may not.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from validation.support.corpus import (  # noqa: E402
    DOMAIN_GUIDE_FILE,
    build_corpus_project,
)

from before_we_ai.llm import (
    ask,
    hypothesize,
    load_domain_guide,
    plan_checks,
    propose_mappings,
)
from before_we_ai.llm.mapping import ProfileIndex, hypothesis_to_claim
from before_we_ai.llm.schemas import Hypothesis
from before_we_ai.core import Actor, ClaimStatus, EvidenceType, resolve_status
from before_we_ai.core.enums import CheckVerdict
from before_we_ai.core.objects import DataProfile, EvidenceRecord
from before_we_ai.store import ProjectStore, ProposalStore, init_project

pytestmark = pytest.mark.contract

DEMO_QUESTION = "Can these files reliably produce actual P&L by entity and month?"

# Everything a promotion needs an author for. Stated as the rule, not as
# today's snapshot: the allow-list below says what the LLM stages happen to
# write now, and this says what they may never write however that changes.
# M5's V3 will add DOCUMENT_ANCHOR to the first list and must not touch this
# one — an anchor is read by nothing and promotes nothing
# (`core/transitions.py::resolve_status`).
PROMOTING = (EvidenceType.CHECK_RESULT, EvidenceType.CONFIRMATION,
             EvidenceType.TESTIMONIAL)


@pytest.fixture()
def hypothesized_claim(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    store.save_profile(DataProfile(
        source_id="s1", table="a__t", column="c",
        stats={"duckdb_type": "BIGINT", "value_class": "integer_like",
               "row_count": 1, "null_count": 0, "distinct_count": 1},
    ))
    hypothesis = Hypothesis(
        statement="t.c is a unique key",
        predicate="unique_key",
        params={"table": "a__t", "key_columns": ["c"]},
        columns=["a__t.c"],
        rationale="distinct == rows",
    )
    return hypothesis_to_claim(hypothesis, ProfileIndex(store))


@pytest.fixture(scope="module")
def llm_stage_evidence(tmp_path_factory):
    """Evidence added by the model-facing stages, excluding scan declarations."""
    root = build_corpus_project(
        tmp_path_factory.mktemp("guardrail") / "corpus", offline=True)
    store = ProjectStore(root)
    evidence_before = set(store.evidence)
    guide = load_domain_guide(DOMAIN_GUIDE_FILE)

    ask(root, DEMO_QUESTION, guide=guide, store=store, scenario="corpus")
    hypothesize(root, store=store, scenario="corpus")
    propose_mappings(root, roles=guide, store=store, scenario="corpus")
    plan_checks(root, store=store, scenario="corpus")

    return [
        record
        for evidence_id, record in store.evidence.items()
        if evidence_id not in evidence_before
    ]


def test_hypothesized_claims_start_and_stay_proposed(hypothesized_claim):
    assert hypothesized_claim.status is ClaimStatus.PROPOSED
    assert resolve_status(hypothesized_claim, []) is ClaimStatus.PROPOSED


def test_ai_cannot_author_promoting_evidence(hypothesized_claim):
    with pytest.raises(ValidationError, match="authored by a check"):
        EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.AI,
                       claim_id=hypothesized_claim.id, verdict=CheckVerdict.PASS)
    with pytest.raises(ValidationError, match="must come from a human"):
        EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=Actor.AI,
                       claim_id=hypothesized_claim.id)
    with pytest.raises(ValidationError, match="must come from a human"):
        EvidenceRecord(type=EvidenceType.TESTIMONIAL, actor=Actor.AI,
                       claim_id=hypothesized_claim.id, statement="trust me")


def test_llm_stages_author_nothing_that_could_promote(llm_stage_evidence):
    """The invariant, and the one that survives the list below changing.

    A stage may start writing a new *weak* record — M5's V3 writes document
    anchors — and that is a widening someone must justify. Writing something
    that can move a status is never a widening; it is the failure this whole
    layer is arranged to prevent.
    """
    assert llm_stage_evidence
    offenders = [r for r in llm_stage_evidence if r.type in PROMOTING]
    assert not offenders, (
        "the LLM stages authored promoting evidence: "
        + ", ".join(f"{r.type.value} by {r.actor.value}" for r in offenders)
    )


def test_llm_stages_write_only_system_declarations(llm_stage_evidence):
    """Today's list, deliberately narrow so a change has to be noticed.

    An allow-list fails loudly when a stage starts writing something new,
    which is exactly when a human should look. Widen it only together with
    the milestone that earns it — and never at the cost of the test above.
    """
    assert all(
        record.type is EvidenceType.DECLARATION
        and record.actor is Actor.SYSTEM
        for record in llm_stage_evidence
    )


def test_proposal_store_hides_general_evidence_writes(tmp_path):
    store = ProjectStore(init_project(tmp_path / "facade"))
    proposals = ProposalStore(store)

    assert not hasattr(proposals, "add_evidence")
    assert not hasattr(proposals, "mark_evidence_stale")
