"""EvidenceRecord consistency rules enforced at construction time."""

import pytest
from pydantic import ValidationError

from before_we_ai.model import Actor, EvidenceRecord, EvidenceType, CheckVerdict


def test_check_result_requires_verdict():
    with pytest.raises(ValidationError):
        EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK)


def test_verdict_only_on_check_results():
    with pytest.raises(ValidationError):
        EvidenceRecord(
            type=EvidenceType.DOCUMENT_ANCHOR,
            actor=Actor.AI,
            verdict=CheckVerdict.PASS,
        )


def test_testimonial_requires_verbatim_statement():
    with pytest.raises(ValidationError):
        EvidenceRecord(type=EvidenceType.TESTIMONIAL, actor=Actor.HUMAN)


@pytest.mark.parametrize("actor", [Actor.AI, Actor.CHECK])
def test_confirmation_must_be_human(actor):
    with pytest.raises(ValidationError):
        EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=actor)


def test_valid_records_construct():
    EvidenceRecord(
        type=EvidenceType.CHECK_RESULT, actor=Actor.CHECK, verdict=CheckVerdict.FAIL
    )
    EvidenceRecord(
        type=EvidenceType.TESTIMONIAL, actor=Actor.HUMAN, statement="GJ Mai–April"
    )
    EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)
