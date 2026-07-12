"""Declarations observe, never promote — the ingestion layer's epistemic limit."""

from before_we_ai.model import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    create_claim,
)
from before_we_ai.model.transitions import attach_evidence, resolve_status


def declaration():
    return EvidenceRecord(
        type=EvidenceType.DECLARATION,
        actor=Actor.SYSTEM,
        payload={"source": "s", "table": "t", "column": "c", "rule": "numeric_to_text"},
        source_fingerprints={"s": "abc123"},
    )


def test_system_actor_is_valid_for_declarations():
    record = declaration()
    assert record.actor is Actor.SYSTEM


def test_declarations_never_change_status():
    claim = create_claim("some rule", Actor.AI)
    records = [declaration() for _ in range(3)]
    for record in records:
        claim = attach_evidence(claim, record, [])
    assert claim.status is ClaimStatus.INFERRED
    assert resolve_status(claim, records) is ClaimStatus.INFERRED
