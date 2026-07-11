"""Semantic-rule claims: identity/dedup, bounded evidence, escalation, impact."""

import pytest
from pydantic import ValidationError

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
    claim_key,
    create_claim,
    escalate_exception,
    gap_load,
    questions_resting_on,
    resolve_status,
)


def rule_claim(**overrides):
    kw = dict(
        predicate=Predicate(
            name="range_membership", params={"column": "account_id", "low": 4000, "high": 4999}
        ),
        scope=Scope(entity="DE"),
        validity=Validity(valid_from="2024-01", valid_to="2025-12"),
        source_ids=["SRC1"],
    )
    kw.update(overrides)
    return create_claim("accounts 4000-4999 are revenue", Actor.AI, **kw)


class TestClaimKey:
    def test_same_rule_different_wording_is_one_identity(self):
        a = rule_claim()
        b = rule_claim()
        b = b.model_copy(update={"statement": "Umsatzerlöse liegen in 4000–4999"})
        assert claim_key(a) == claim_key(b)

    @pytest.mark.parametrize(
        "override",
        [
            {"predicate": Predicate(name="other_rule", params={})},
            {"predicate": Predicate(name="range_membership", params={"column": "x"})},
            {"scope": Scope(entity="US")},
            {"validity": Validity(valid_from="2026-01")},
            {"source_ids": ["SRC2"]},
        ],
    )
    def test_material_difference_changes_identity(self, override):
        assert claim_key(rule_claim()) != claim_key(rule_claim(**override))

    def test_source_order_is_immaterial(self):
        a = rule_claim(source_ids=["S1", "S2"])
        b = rule_claim(source_ids=["S2", "S1"])
        assert claim_key(a) == claim_key(b)

    def test_free_text_claims_have_no_key(self):
        assert claim_key(create_claim("just a hunch", Actor.AI)) is None


class TestBoundedEvidence:
    def test_aggregate_probe_record(self):
        record = EvidenceRecord(
            type=EvidenceType.PROBE_RESULT,
            actor=Actor.PROBE,
            verdict=ProbeVerdict.FAIL,
            population=100_000,
            exception_count=42,
            exception_samples=[{"row_id": i} for i in range(10)],
            result_ref="cache/probe_runs/xyz.parquet",
        )
        assert record.exception_rate() == pytest.approx(0.00042)

    def test_sample_cap_is_enforced(self):
        with pytest.raises(ValidationError):
            EvidenceRecord(
                type=EvidenceType.PROBE_RESULT,
                actor=Actor.PROBE,
                verdict=ProbeVerdict.FAIL,
                exception_samples=[{"row_id": i} for i in range(MAX_EXCEPTION_SAMPLES + 1)],
            )

    def test_exceptions_cannot_exceed_population(self):
        with pytest.raises(ValidationError):
            EvidenceRecord(
                type=EvidenceType.PROBE_RESULT,
                actor=Actor.PROBE,
                verdict=ProbeVerdict.FAIL,
                population=10,
                exception_count=11,
            )

    def test_exception_rate_undefined_without_population(self):
        record = EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)
        assert record.exception_rate() is None


class TestEscalation:
    def _parent_with_evidence(self):
        parent = rule_claim()
        record = EvidenceRecord(
            type=EvidenceType.PROBE_RESULT,
            actor=Actor.PROBE,
            verdict=ProbeVerdict.FAIL,
            claim_id=parent.id,
            population=100_000,
            exception_count=42,
            exception_samples=[{"account_id": 4805}],
        )
        parent = parent.model_copy(update={"evidence_ids": [record.id]})
        return parent, record

    def test_escalated_exception_becomes_own_inferred_claim(self):
        parent, record = self._parent_with_evidence()
        child = escalate_exception(
            parent,
            record,
            statement="4800-range accounts are rebates, not revenue",
            created_by=Actor.HUMAN,
            predicate=Predicate(name="range_membership", params={"low": 4800, "high": 4809}),
        )
        assert child.status is ClaimStatus.INFERRED
        assert child.derived_from == parent.id
        assert child.derived_from_evidence == record.id
        assert child.id != parent.id
        assert child.source_ids == parent.source_ids

    def test_provenance_is_not_status_bearing_evidence(self):
        # the parent's failing probe must not contradict the child rule
        parent, record = self._parent_with_evidence()
        child = escalate_exception(
            parent, record, statement="exception rule", created_by=Actor.AI
        )
        assert child.evidence_ids == []
        assert resolve_status(child, [record]) is ClaimStatus.INFERRED

    def test_escalation_requires_attached_evidence(self):
        parent, _ = self._parent_with_evidence()
        stranger = EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)
        with pytest.raises(ValueError):
            escalate_exception(
                parent, stranger, statement="x", created_by=Actor.AI
            )


class TestImpact:
    def test_questions_resting_on(self):
        claim = rule_claim()
        q1 = QuestionCard(question="Z2?", claim_ids=[claim.id])
        q2 = QuestionCard(question="unrelated", claim_ids=[])
        assert questions_resting_on(claim.id, [q1, q2]) == [q1]

    def test_gap_load_ranks_unproven_claims_by_dependent_questions(self):
        heavy, light, proven = rule_claim(), rule_claim(scope=Scope(entity="US")), rule_claim(scope=Scope(entity="CH"))
        proven.status = ClaimStatus.TESTED
        questions = [
            QuestionCard(question=f"q{i}", claim_ids=[heavy.id]) for i in range(3)
        ] + [
            QuestionCard(question="q_light", claim_ids=[light.id]),
            QuestionCard(question="q_proven", claim_ids=[proven.id]),
        ]
        ranked = gap_load([light, heavy, proven], questions)
        assert [(c.id, n) for c, n in ranked] == [(heavy.id, 3), (light.id, 1)]
