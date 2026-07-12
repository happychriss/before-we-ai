"""Acceptance challenge: rules scale as claims, rows do not.

> Demonstrate that a rule applied to 100,000 rows creates one claim with
> evidence and exceptions, not 100,000 claims, while still allowing a
> materially different exception to become its own claim when required.

Runs end-to-end through the store so the file counts on disk — the thing
a human would actually have to review — are what gets asserted.
"""

import random

import pytest

from before_we_ai.model import (
    MAX_EXCEPTION_SAMPLES,
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    Predicate,
    ProbeVerdict,
    QuestionCard,
    Scope,
    Validity,
    create_claim,
    escalate_exception,
    gap_load,
)
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.store import ProjectStore

N_ROWS = 100_000


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "proj", create=True)


def files_in(store, dirname):
    return len(list((store.root / dirname).glob("*.yaml")))


def test_one_rule_over_100k_rows_is_one_claim(store):
    rng = random.Random(0)

    # The semantic rule — one claim, scoped and parameterised.
    rule = create_claim(
        "every open AR item references an existing GL posting",
        Actor.AI,
        predicate=Predicate(
            name="anti_join",
            params={"child": "ar_open_items", "parent": "gl_postings", "on": "document_reference"},
        ),
        scope=Scope(entity="DE"),
        validity=Validity(valid_from="2024-01", valid_to="2025-12"),
    )
    rule = store.add_claim(rule)

    # Deduplication: the same rule proposed again — different session,
    # different wording — lands on the SAME claim, no new file.
    duplicate = create_claim(
        "AR items always have a GL counterpart (rephrased hypothesis)",
        Actor.AI,
        predicate=Predicate(
            name="anti_join",
            params={"child": "ar_open_items", "parent": "gl_postings", "on": "document_reference"},
        ),
        scope=Scope(entity="DE"),
        validity=Validity(valid_from="2024-01", valid_to="2025-12"),
    )
    assert store.add_claim(duplicate).id == rule.id
    assert files_in(store, "claims") == 1

    # The probe sweeps 100,000 rows and finds 37 violations. Row-level
    # observations enter as ONE aggregate evidence record: counts, a
    # bounded representative sample, and a cache pointer to the full set.
    violations = [
        {"row_id": rng.randrange(N_ROWS), "document_reference": f"DOC{rng.randrange(99999):05d}"}
        for _ in range(37)
    ]
    probe_record = EvidenceRecord(
        type=EvidenceType.PROBE_RESULT,
        actor=Actor.PROBE,
        verdict=ProbeVerdict.FAIL,
        claim_id=rule.id,
        population=N_ROWS,
        exception_count=len(violations),
        exception_samples=violations[:MAX_EXCEPTION_SAMPLES],
        result_ref="cache/probe_runs/anti_join_ar_gl.parquet",
    )
    store.add_evidence(probe_record)
    rule = attach_evidence(rule, probe_record, [])
    store.save_claim(rule)

    # THE claim count: 100,000 rows -> 1 claim, 1 evidence file.
    assert files_in(store, "claims") == 1
    assert files_in(store, "evidence") == 1
    assert rule.status is ClaimStatus.CONTRADICTED  # loud, but singular

    # The truth file stays reviewable: bounded, small, human-readable.
    evidence_file = store.root / "evidence" / f"{probe_record.id}.yaml"
    assert evidence_file.stat().st_size < 10_000
    assert len(store.evidence[probe_record.id].exception_samples) <= MAX_EXCEPTION_SAMPLES

    # A materially different exception: review shows 30 of the 37 misses
    # share the pre-migration ID pattern — that is a rule of its own.
    child = escalate_exception(
        rule,
        probe_record,
        statement="pre-2025 documents reference GL through the legacy numbering",
        created_by=Actor.HUMAN,
        predicate=Predicate(
            name="anti_join",
            params={"child": "ar_open_items", "parent": "gl_postings", "on": "legacy_reference"},
        ),
        validity=Validity(valid_to="2024-12"),
    )
    child = store.add_claim(child)

    # Exactly one more claim — and it must earn its own status from scratch.
    assert files_in(store, "claims") == 2
    assert child.status is ClaimStatus.INFERRED
    assert child.derived_from == rule.id
    assert child.derived_from_evidence == probe_record.id
    assert child.evidence_ids == []

    # Question dependency and impact survive the round-trip: the open
    # child claim carries the question load, the answered world sees it.
    store.save_question(
        QuestionCard(question="Z2: external revenue per customer", claim_ids=[rule.id, child.id])
    )
    reloaded = ProjectStore(store.root)
    assert len(reloaded.claims) == 2
    ranked = gap_load(reloaded.claims.values(), reloaded.questions.values())
    assert {c.id for c, _ in ranked} == {rule.id, child.id}
    assert all(n == 1 for _, n in ranked)

    # And dedup still holds after reload: the same rule cannot re-enter.
    assert reloaded.add_claim(duplicate).id == rule.id
    assert files_in(reloaded, "claims") == 2
