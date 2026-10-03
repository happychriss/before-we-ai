"""Turn measured rules into evidence on the claims they speak about.

A rule that holds settles the roles of the quantities in it: the evidence
is written onto every role candidate that sits on the bound column, as a
check result authored by ``Actor.CHECK`` — the same door every promotion
goes through. A rule that does not hold writes its result too, but as a
finding that carries no weight: the object stays open and a person sees
why.

Experimental. The binding is supplied by a person, the rules come from a
document a person signs, and nothing here is reached by a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from before_we_ai.core.enums import Actor, CheckVerdict, EvidenceType
from before_we_ai.core.objects import EvidenceRecord, MappingClaim
from before_we_ai.core.transitions import attach_evidence, resolve_status
from before_we_ai.foundation.laws import Binding, LawResult, evaluate
from before_we_ai.foundation.reader import Foundation
from before_we_ai.store.repository import ProjectStore

PREFIX = "foundation:"


@dataclass
class Applied:
    result: LawResult
    holds: bool
    roles: list[str] = field(default_factory=list)  # roles the rule speaks of
    settled: list[str] = field(default_factory=list)  # roles it wrote a PASS on
    no_candidate: list[str] = field(default_factory=list)


def _roles(result: LawResult, binding: Binding) -> dict[str, tuple[str, str | None]]:
    """role -> (view, column or None for an object role)."""
    rule, out = result.rule, {}
    # Only the object the rule is *about* — the one whose records it runs
    # over. "Every cost line names a known vessel" says something about the
    # cost ledger and about the vessel key; it says nothing about whether
    # the vessel list is a vessel list.
    parts = rule.parts
    subject = parts.get("object") or parts.get("child") or parts.get("detail")
    role = binding.objects[subject].get("role")
    if role:
        out[role] = (binding.view(subject), None)
    for obj, quantity in rule.quantities:
        role = binding.quantities[(obj, quantity)].get("role")
        if role:
            out[role] = (binding.view(obj), binding.column(obj, quantity))
    return out


def _sits_on(claim: MappingClaim, view: str, column: str | None) -> bool:
    values = [str(v) for v in claim.binding.values()]
    if column is None:
        return view in values
    return f"{view}.{column}" in values


def _rederive(store: ProjectStore, claim_id: str) -> None:
    claim = store.claims[claim_id]
    status = resolve_status(claim, store.evidence_for(claim))
    if status is not claim.status:
        store.save_claim(claim.model_copy(update={"status": status}))


def retire(store: ProjectStore, templates: dict[str, str]) -> int:
    """Stop counting the results of laws the document replaces.

    A landscape read under a borrowed guide carries verdicts from laws that
    do not fit it — a balance law over a single-sided cost ledger. They are
    not deleted: evidence is append-only. They are marked out of date,
    which is the one mutation the store permits, and the claims fall back
    to what the remaining evidence supports.
    """
    touched = set()
    for record in list(store.evidence.values()):
        if (record.type is EvidenceType.CHECK_RESULT and not record.stale
                and record.payload.get("template") in templates):
            store.mark_evidence_stale(record.id)
            if record.claim_id:
                touched.add(record.claim_id)
    for claim_id in touched:
        _rederive(store, claim_id)
    return len(touched)


def apply(store: ProjectStore, con, foundation: Foundation,
          binding: Binding) -> list[Applied]:
    out = []
    for result in evaluate(con, foundation, binding):
        holds = result.holds(foundation.min_share)
        applied = Applied(result, holds)
        out.append(applied)
        if not result.applicable or result.error or not result.evaluable:
            continue
        rule = result.rule
        template = f"{PREFIX}{rule.id}"
        summary = (
            f"{rule.name}: holds on {result.satisfied} of {result.evaluable} "
            f"records ({result.share:.1%}); the document asks for "
            f"{foundation.min_share:.0%}"
            + (f"; {result.not_evaluable} records could not be evaluated "
               "(a value is blank)" if result.not_evaluable else ""))
        for role, (view, column) in _roles(result, binding).items():
            applied.roles.append(role)
            candidates = [
                c for c in store.claims.values()
                if isinstance(c, MappingClaim) and c.role == role
                and _sits_on(c, view, column)]
            if not candidates:
                applied.no_candidate.append(role)
                continue
            for claim in candidates:
                for known in store.evidence_for(claim):
                    if known.payload.get("template") == template and not known.stale:
                        store.mark_evidence_stale(known.id)
                record = EvidenceRecord(
                    type=EvidenceType.CHECK_RESULT,
                    actor=Actor.CHECK,
                    claim_id=claim.id,
                    verdict=CheckVerdict.PASS if holds else CheckVerdict.FAIL,
                    population=result.evaluable,
                    exception_count=result.exceptions,
                    exception_samples=result.samples,
                    payload={
                        "template": template,
                        "law": rule.id,
                        "statement": rule.statement,
                        "formal": rule.formal,
                        "tolerance": rule.tolerance,
                        "sql": result.sql,
                        "summary": summary,
                        # a rule that does not hold is a finding on the
                        # object, never a verdict on the column
                        **({} if holds else {"refutes": False}),
                    },
                )
                store.add_evidence(record)
                claim = store.claims[claim.id]
                store.save_claim(attach_evidence(
                    claim, record, store.evidence_for(claim)))
            if holds:
                applied.settled.append(role)
    return out
