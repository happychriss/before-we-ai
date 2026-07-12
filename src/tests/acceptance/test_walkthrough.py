"""The guided scenario "Der Umsatz-Claim" as an executable acceptance test.

Nine steps through every M1 mechanism, following the corpus story of
F15 (account-range netting) and F29 (fiscal-year scope): project init,
rule claim, dedup, aggregate contradiction, exception escalation,
dependency gating and gap load, mirror-loop, contradiction of a
confirmed claim, staleness, integrity, checkpoint.

Each step reloads the store from disk — persistence is part of what is
being demonstrated, not an implementation detail.
"""

import subprocess

import pytest

from before_we_ai.model import (
    Actor,
    ClaimStatus,
    EvidenceRecord,
    EvidenceType,
    Predicate,
    ProbeVerdict,
    PromotionError,
    QuestionCard,
    Scope,
    Validity,
    create_claim,
    escalate_exception,
    gap_load,
    ready_for_probe,
)
from before_we_ai.model.transitions import attach_evidence, resolve_status
from before_we_ai.store import ProjectStore, check_integrity, checkpoint, init_project


def revenue_rule(statement: str):
    return create_claim(
        statement,
        Actor.AI,
        predicate=Predicate(
            name="range_membership",
            params={"column": "account_id", "low": 4000, "high": 4999},
        ),
        scope=Scope(entity="DE"),
        validity=Validity(valid_from="2024-01", valid_to="2025-12"),
    )


def test_umsatz_claim_walkthrough(tmp_path):
    project = tmp_path / "umsatz-demo"

    # Step 1 — der Aktenschrank
    root = init_project(project, name="umsatz-demo")
    assert (root / "before-ai.yaml").is_file()

    # Step 2 — die KI vermutet eine Regel (nur inferred, mehr kann sie nicht)
    store = ProjectStore(root)
    rule = store.add_claim(revenue_rule("Umsatzerlöse sind die Konten 4000-4999"))
    assert rule.status is ClaimStatus.INFERRED

    # Step 3 — Dedup: dieselbe Regel, anders formuliert, bleibt EINE Karte
    again = store.add_claim(revenue_rule("Revenue lives in the 4xxx account range"))
    assert again.id == rule.id
    assert len(list((root / "claims").glob("*.yaml"))) == 1

    # Step 4 — Sonde über 40.000 Zeilen widerspricht: EIN Aggregat-Beweis
    store = ProjectStore(root)
    rule = store.claims[rule.id]
    probe = EvidenceRecord(
        type=EvidenceType.PROBE_RESULT,
        actor=Actor.PROBE,
        verdict=ProbeVerdict.FAIL,
        claim_id=rule.id,
        population=40_000,
        exception_count=576,
        exception_samples=[
            {"account_id": 4800, "text": "Erlösschmälerung Rabatt"},
            {"account_id": 4805, "text": "Rückstellung Retro-Rabatt"},
        ],
        result_ref="cache/probe_runs/reconcile_e1_q3.parquet",
    )
    store.add_evidence(probe)
    rule = attach_evidence(rule, probe, [])
    store.save_claim(rule)
    assert rule.status is ClaimStatus.CONTRADICTED
    assert probe.exception_rate() == pytest.approx(576 / 40_000)
    assert len(list((root / "evidence").glob("*.yaml"))) == 1

    # Step 5 — Eskalation: das Ausnahme-Muster (F15) wird eine eigene Karte
    child = escalate_exception(
        rule,
        probe,
        statement="Konten 4800-4809 sind Erlösschmälerungen, kein Umsatz",
        created_by=Actor.HUMAN,
        predicate=Predicate(
            name="range_membership",
            params={"column": "account_id", "low": 4800, "high": 4809},
        ),
        scope=Scope(entity="DE"),
    )
    store.add_claim(child)
    assert child.status is ClaimStatus.INFERRED
    assert child.evidence_ids == []  # Provenienz ist keine Evidenz
    assert child.derived_from == rule.id
    assert child.derived_from_evidence == probe.id

    # Step 6 — Abhängigkeit gated die Sonde; Gap-Lastliste zeigt den Impact
    store = ProjectStore(root)
    child = store.claims[child.id]
    refined = create_claim(
        "Umsatz = 4000-4999 abzüglich 4800-4809",
        Actor.AI,
        predicate=Predicate(
            name="range_membership_with_exclusion",
            params={"low": 4000, "high": 4999, "excl": [4800, 4809]},
        ),
        scope=Scope(entity="DE"),
        depends_on=[child.id],
    )
    store.add_claim(refined)
    store.save_question(
        QuestionCard(
            question="Z2: externer Umsatz je Kunde (netto, EUR)",
            claim_ids=[refined.id, child.id],
        )
    )
    assert ready_for_probe(refined, store.claims) is False
    load = dict((c.id, n) for c, n in gap_load(store.claims.values(), store.questions.values()))
    assert load[refined.id] == 1 and load[child.id] == 1

    ok = EvidenceRecord(
        type=EvidenceType.PROBE_RESULT,
        actor=Actor.PROBE,
        verdict=ProbeVerdict.PASS,
        claim_id=child.id,
        population=576,
        exception_count=0,
    )
    store.add_evidence(ok)
    child = attach_evidence(child, ok, [])
    store.save_claim(child)
    assert child.status is ClaimStatus.TESTED
    assert ready_for_probe(refined, store.claims) is True

    # Step 7 — Spiegel-Schleife (F29): Bestätigung braucht den Geltungsbereich
    store = ProjectStore(root)
    tell = EvidenceRecord(
        type=EvidenceType.TESTIMONIAL,
        actor=Actor.HUMAN,
        statement="Unser Geschäftsjahr läuft Mai bis April.",
    )
    store.add_evidence(tell)
    fiscal = attach_evidence(create_claim("Geschäftsjahr = Mai bis April", Actor.AI), tell, [])
    store.save_claim(fiscal)
    with pytest.raises(PromotionError):
        attach_evidence(
            fiscal,
            EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN),
            store.evidence_for(fiscal),
        )
    scoped = EvidenceRecord(
        type=EvidenceType.CONFIRMATION, actor=Actor.HUMAN, scope=Scope(entity="US")
    )
    store.add_evidence(scoped)
    fiscal = attach_evidence(fiscal, scoped, store.evidence_for(fiscal))
    store.save_claim(fiscal)
    assert fiscal.status is ClaimStatus.BUSINESS_CONFIRMED

    # Step 8 — Gegenbefund macht auch die bestätigte Karte laut; stale heilt
    store = ProjectStore(root)
    fiscal = store.claims[fiscal.id]
    contra = EvidenceRecord(
        type=EvidenceType.PROBE_RESULT,
        actor=Actor.PROBE,
        verdict=ProbeVerdict.FAIL,
        claim_id=fiscal.id,
        population=24,
        exception_count=12,
    )
    store.add_evidence(contra)
    fiscal = attach_evidence(fiscal, contra, store.evidence_for(fiscal))
    store.save_claim(fiscal)
    assert fiscal.status is ClaimStatus.UNRESOLVED

    store.mark_evidence_stale(contra.id)
    fiscal.status = resolve_status(fiscal, store.evidence_for(fiscal))
    store.save_claim(fiscal)
    assert fiscal.status is ClaimStatus.BUSINESS_CONFIRMED

    # Step 9 — Integrität und Checkpoint; Endbestand bleibt menschenklein
    store = ProjectStore(root)
    assert check_integrity(store) == []
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "demo@local"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "demo"], cwd=root, check=True)
    assert checkpoint(root, "szenario: umsatz-demo") is True
    assert len(store.claims) == 4
    assert len(store.evidence) == 5
    assert len(store.questions) == 1
