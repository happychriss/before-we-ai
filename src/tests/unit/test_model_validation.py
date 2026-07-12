"""EvidenceRecord consistency rules enforced at construction time."""

import pytest
from pydantic import ValidationError

from before_we_ai.model import Actor, EvidenceRecord, EvidenceType, ProbeVerdict


def test_probe_result_requires_verdict():
    with pytest.raises(ValidationError):
        EvidenceRecord(type=EvidenceType.PROBE_RESULT, actor=Actor.PROBE)


def test_verdict_only_on_probe_results():
    with pytest.raises(ValidationError):
        EvidenceRecord(
            type=EvidenceType.DOCUMENT_ANCHOR,
            actor=Actor.AI,
            verdict=ProbeVerdict.PASS,
        )


def test_testimonial_requires_verbatim_statement():
    with pytest.raises(ValidationError):
        EvidenceRecord(type=EvidenceType.TESTIMONIAL, actor=Actor.HUMAN)


@pytest.mark.parametrize("actor", [Actor.AI, Actor.PROBE])
def test_confirmation_must_be_human(actor):
    with pytest.raises(ValidationError):
        EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=actor)


def test_valid_records_construct():
    EvidenceRecord(
        type=EvidenceType.PROBE_RESULT, actor=Actor.PROBE, verdict=ProbeVerdict.FAIL
    )
    EvidenceRecord(
        type=EvidenceType.TESTIMONIAL, actor=Actor.HUMAN, statement="GJ Mai–April"
    )
    EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)
