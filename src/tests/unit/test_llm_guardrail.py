"""The inferred-only guardrail holds structurally through the LLM path.

Nothing here is new enforcement — the M1 core owns the law. These tests
prove the LLM layer rides on it: AI-born claims start inferred, AI cannot
author promoting evidence, and the contract modules do not even contain
the calls that write evidence."""

import inspect

import pytest
from pydantic import ValidationError

from before_we_ai.llm import call_log, client, config, inputs, mapping, prompts
from before_we_ai.llm import roles as roles_module
from before_we_ai.llm import schemas, stub, v1_hypotheses, v2_bind, vocabulary
from before_we_ai.llm.mapping import ProfileIndex, hypothesis_to_claim
from before_we_ai.llm.schemas import Hypothesis
from before_we_ai.model import Actor, ClaimStatus, EvidenceType, resolve_status
from before_we_ai.model.enums import ProbeVerdict
from before_we_ai.model.objects import ColumnProfile, EvidenceRecord
from before_we_ai.store import ProjectStore, init_project


@pytest.fixture()
def hypothesized_claim(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    store.save_profile(ColumnProfile(
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


def test_hypothesized_claims_start_and_stay_inferred(hypothesized_claim):
    assert hypothesized_claim.status is ClaimStatus.INFERRED
    assert resolve_status(hypothesized_claim, []) is ClaimStatus.INFERRED


def test_ai_cannot_author_promoting_evidence(hypothesized_claim):
    with pytest.raises(ValidationError, match="authored by a probe"):
        EvidenceRecord(type=EvidenceType.PROBE_RESULT, actor=Actor.AI,
                       claim_id=hypothesized_claim.id, verdict=ProbeVerdict.PASS)
    with pytest.raises(ValidationError, match="must come from a human"):
        EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=Actor.AI,
                       claim_id=hypothesized_claim.id)
    with pytest.raises(ValidationError, match="must come from a human"):
        EvidenceRecord(type=EvidenceType.TESTIMONIAL, actor=Actor.AI,
                       claim_id=hypothesized_claim.id, statement="trust me")


def test_llm_modules_never_write_evidence():
    """The contract layer creates claims and probes — evidence writes do not
    appear anywhere in its source. Probes produce evidence when the ENGINE
    runs them; the LLM layer only files the falsification requests.

    The one exception is ``v2_bind``, covered by the next test."""
    forbidden = ("add_evidence", "attach_evidence", "mark_evidence_stale")
    modules = [call_log, client, config, inputs, mapping, prompts,
               roles_module, schemas, stub, v1_hypotheses, vocabulary]
    for module in modules:
        source = inspect.getsource(module)
        for call in forbidden:
            assert call not in source, f"{module.__name__} contains {call}"


def test_v2_writes_only_declarations_and_they_cannot_promote(hypothesized_claim):
    """V2's single evidence write: a DECLARATION saying why a claim got no
    probe (unbindable / semantic-only / skipped). It is process metadata, the
    same class as a normalization declaration — authored by the SYSTEM, never
    by the AI, and structurally unable to move a status. Without it the
    model's reason would live only in the disposable call log."""
    source = inspect.getsource(v2_bind)
    assert "mark_evidence_stale" not in source
    assert source.count("EvidenceRecord(") == 1  # exactly one, the declaration
    assert "type=EvidenceType.DECLARATION" in source
    assert "actor=Actor.SYSTEM" in source
    for promoting in ("PROBE_RESULT", "CONFIRMATION", "TESTIMONIAL", "DOCUMENT_ANCHOR"):
        assert promoting not in source, f"v2_bind names {promoting}"

    declaration = EvidenceRecord(
        type=EvidenceType.DECLARATION,
        actor=Actor.SYSTEM,
        claim_id=hypothesized_claim.id,
        payload={"decision": "unbindable", "reason": "no pairs available"},
    )
    assert resolve_status(hypothesized_claim, [declaration]) is ClaimStatus.INFERRED
