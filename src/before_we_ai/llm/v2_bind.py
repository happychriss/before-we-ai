"""Contract V2 — check binding (and the role-binding proposals it needs).

``propose_mappings`` is the frontier-tier search task: candidate
MappingClaims for every entry of the supplied domain guide — its business
objects and their fields, flattened into one list for the prompt —
competing candidates welcome; the invariant checks decide, never the model.

``plan_checks`` turns unbound AI claims into ``CheckPlan`` records: role-
binding claims go to the invariant templates (frontier tier, per the
architecture's exception), ordinary claims to the rest (mid tier). A
claim whose predicate no template can test is reported as
``semantic_only``; a claim the model honestly cannot bind is reported as
``unbindable`` with the model's reason. Nothing is silently dropped: every
claim that ends without a check carries a DECLARATION saying why, so the
refusal survives the disposable call log. No SQL is run and no
status-bearing evidence is written — the engine does that, later.
"""

from dataclasses import dataclass, field
from pathlib import Path

from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.client import BatchRepair, LLMClient, LLMResult, call_with_retry
from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.inputs import (
    build_binding_context,
    build_role_context,
    claim_label_map,
)
from before_we_ai.llm.mapping import (
    ProfileIndex,
    admissible_templates,
    proposal_to_check_plan,
    check_binding,
    check_mapping_proposal,
    proposal_to_mapping_claim,
)
from before_we_ai.llm.prompts import (
    MAPPING_SYSTEM,
    V2_ROLES_SYSTEM,
    V2_SYSTEM,
    render_template_docs,
    with_schema,
)
from before_we_ai.llm.domain_guide import DomainGuide, load_domain_guide
from before_we_ai.llm.schemas import BindingBatch, MappingProposalBatch
from before_we_ai.core.enums import ClaimStatus, EvidenceType
from before_we_ai.core.objects import Claim, MappingClaim
from before_we_ai.profile.candidates import load_matrix
from before_we_ai.store.proposals import ProposalStore
from before_we_ai.store.repository import ProjectStore

CONTRACT_ROLES = "role_binding"
CONTRACT_BIND = "v2_bind"


@dataclass
class MappingProposalReport:
    claims_created: list[str] = field(default_factory=list)
    claims_deduped: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (role, reason)
    failure: str | None = None
    retries: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    log_ref: str | None = None


def propose_mappings(
    root: str | Path,
    *,
    roles: DomainGuide | None = None,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    scenario: str = "default",
) -> MappingProposalReport:
    root = Path(root)
    store = store or ProjectStore(root)
    store = ProposalStore(store)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)
    if roles is None:
        if not config.domain_guide_file:
            raise ValueError(
                "no domain guide: pass roles= or set llm.domain_guide_file "
                "in before-ai.yaml"
            )
        roles = load_domain_guide(root / config.domain_guide_file)

    built = build_role_context(store, load_matrix(root), roles)
    index = ProfileIndex(store)

    result = call_with_retry(
        client,
        contract=CONTRACT_ROLES,
        scenario=scenario,
        model=config.models[CONTRACT_ROLES],
        system=with_schema(MAPPING_SYSTEM, MappingProposalBatch),
        built=built,
        schema=MappingProposalBatch,
        repair=BatchRepair(
            "proposals",
            lambda p: check_mapping_proposal(p, roles.names, index),
        ),
        logger=CallLogger(root),
    )
    report = MappingProposalReport(retries=result.retries, usage=result.usage,
                                log_ref=result.log_ref)
    if result.parsed is None:
        report.failure = result.failure
        return report

    for proposal in result.parsed.proposals:
        errors = check_mapping_proposal(proposal, roles.names, index)
        if errors:
            report.skipped.append((proposal.role, "; ".join(errors)))
            continue
        claim = proposal_to_mapping_claim(proposal, index)
        kept = store.add_claim(claim)
        if kept.id == claim.id:
            report.claims_created.append(claim.id)
        else:
            report.claims_deduped += 1
    return report


@dataclass
class V2Report:
    check_plans_created: list[str] = field(default_factory=list)
    check_plans_deduped: int = 0
    unbindable: list[tuple[str, str]] = field(default_factory=list)  # (claim_id, model's reason)
    semantic_only: list[str] = field(default_factory=list)  # never sent — no admissible template
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (claim_id, validation reason)
    unanswered: list[str] = field(default_factory=list)  # sent but absent from the answer
    # (claim_id, param) for every value read as something other than what
    # the model wrote — visible, never silent.
    corrections: list[tuple[str, str]] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)  # per-call double failures
    retries: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    log_refs: list[str] = field(default_factory=list)


def _untested_claims(store: ProposalStore,
                     claim_ids: list[str] | None) -> list[Claim]:
    """Every parameterised claim that no check has been planned for yet.

    Not "AI claims": **who said it, and whether anyone believes it, are
    both irrelevant to whether it can be tested.** The spec requires that a
    testimonial claim be checkable like any other, and that a contradicting
    check pull it to ``unresolved`` — that is its *only* expiry date, since a
    human statement carries no data fingerprint to go stale. Filtering to
    ``Actor.AI`` and ``proposed`` would make human and document knowledge the
    one kind of claim nothing may question.

    Dormant until the document pipeline produces such claims; it is here so
    that when it does, their output is tested rather than trusted.

    A claim that already has a plan is excluded — that is what "untested"
    means here, and it keeps re-runs from re-planning settled work.
    """
    bound = {p.claim_id for p in store.checks.values() if p.claim_id}
    selected = [
        c for c in store.claims.values()
        if c.predicate is not None
        and c.id not in bound
        and (claim_ids is None or c.id in claim_ids)
    ]
    return sorted(selected, key=lambda c: c.id)


def _declare_correction(store: ProposalStore, claim: Claim,
                        correction: dict) -> None:
    """Record that we read a param as something other than what was written.

    Owner decision 2026-08-02: normalize the unambiguous shape errors so
    the check runs, **and** leave the correction on the record. Leniency
    without a trace is the too-loose-law failure — a binding the model may
    have misunderstood runs, passes, and promotes, with nothing anywhere
    saying we changed it. A declaration promotes nothing and makes the
    change readable at the claim.
    """
    existing = store.evidence_for(claim)
    if any(
        record.type is EvidenceType.DECLARATION
        and record.payload.get("decision") == "param_normalized"
        and record.payload.get("param") == correction["param"]
        for record in existing
    ):
        return
    store.declare(claim.id, {
        "decision": "param_normalized",
        "param": correction["param"],
        "given": correction["given"],
        "read_as": correction["read_as"],
    })


def _declare_no_check(store: ProposalStore, claim: Claim, decision: str,
                      reason: str) -> None:
    """Record in the store why this claim got no check.

    The refusal is as much a result as a check is — but it lived only in the
    disposable call log. A DECLARATION is the canonical home: a declared
    processing decision, weak evidence that can never promote. The SYSTEM
    authors it (the AI never authors evidence); the model's verbatim reason
    travels in the payload as data.
    """
    existing = store.evidence_for(claim)
    if any(
        record.type is EvidenceType.DECLARATION
        and record.payload.get("decision") == decision
        for record in existing
    ):
        return
    store.declare(
        claim.id,
        {"decision": decision, "reason": reason},
    )


def _existing_check_plan(store: ProposalStore, check) -> bool:
    return any(
        p.template == check.template
        and p.claim_id == check.claim_id
        and p.params == check.params
        for p in store.checks.values()
    )


def plan_checks(
    root: str | Path,
    *,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    claim_ids: list[str] | None = None,
    scenario: str = "default",
) -> V2Report:
    root = Path(root)
    store = store or ProjectStore(root)
    store = ProposalStore(store)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)
    index = ProfileIndex(store)
    report = V2Report()

    candidates = _untested_claims(store, claim_ids)
    role_claims, ordinary = [], []
    for claim in candidates:
        if isinstance(claim, MappingClaim):
            role_claims.append(claim)
        elif admissible_templates(claim):
            ordinary.append(claim)
        else:
            report.semantic_only.append(claim.id)
            _declare_no_check(
                store, claim, "semantic_only",
                f"no check definition can test predicate "
                f"{claim.predicate.name!r} — this claim is decided by a human, "
                "not by SQL",
            )

    # Role bindings are a search task with domain judgment — frontier tier
    # and a system prompt that explains the invariant mechanism; plain
    # template binding runs mid-tier (architecture spec).
    batches = [
        (role_claims, CONTRACT_ROLES, f"{scenario}_roles", V2_ROLES_SYSTEM),
        (ordinary, CONTRACT_BIND, f"{scenario}_claims", V2_SYSTEM),
    ]
    for claims, model_key, batch_scenario, system in batches:
        if not claims:
            continue
        labels = claim_label_map(claims)
        result = _bind_batch(
            root, store, index, labels, client,
            model=config.models[model_key], scenario=batch_scenario,
            system=system,
        )
        report.retries += result.retries
        for key, value in result.usage.items():
            report.usage[key] = report.usage.get(key, 0) + value
        report.log_refs.append(result.log_ref)
        if result.parsed is None:
            report.failures.append(result.failure)
            continue
        answered = set()
        for binding in result.parsed.bindings:
            answered.add(binding.claim_id)
            errors = check_binding(binding, labels, index)
            if errors:
                report.skipped.append((binding.claim_id, "; ".join(errors)))
                if binding.claim_id in labels:
                    _declare_no_check(store, labels[binding.claim_id], "skipped",
                                      "; ".join(errors))
                continue
            claim = labels[binding.claim_id]
            check, corrections = proposal_to_check_plan(binding, claim, index)
            for correction in corrections:
                _declare_correction(store, claim, correction)
                report.corrections.append((claim.id, correction["param"]))
            if check is None:
                report.unbindable.append((claim.id, binding.no_template_reason))
                _declare_no_check(store, claim, "unbindable",
                                  binding.no_template_reason or "")
                continue
            if _existing_check_plan(store, check):
                report.check_plans_deduped += 1
                continue
            store.save_check_plan(check)
            report.check_plans_created.append(check.id)
        report.unanswered += [
            labels[label].id for label in labels if label not in answered
        ]
    return report


def _bind_batch(root: Path, store: ProposalStore, index: ProfileIndex,
                labels: dict[str, Claim], client: LLMClient,
                *, model: str, scenario: str, system: str) -> LLMResult:
    built = build_binding_context(store, labels, render_template_docs())

    return call_with_retry(
        client,
        contract=CONTRACT_BIND,
        scenario=scenario,
        model=model,
        system=with_schema(system, BindingBatch),
        built=built,
        schema=BindingBatch,
        repair=BatchRepair("bindings",
                           lambda b: check_binding(b, labels, index)),
        logger=CallLogger(root),
    )
