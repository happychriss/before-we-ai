"""Contract V2 — probe binding (and the role-binding proposals it needs).

``propose_role_bindings`` is the frontier-tier search task: candidate
RoleBindingClaims for the supplied domain roles, competing candidates
welcome — the invariant probes decide, never the model.

``bind_probes`` turns unbound AI claims into ``Probe`` records: role-
binding claims go to the invariant templates (frontier tier, per the
architecture's exception), ordinary claims to the rest (mid tier). A
claim whose predicate no template can test is reported as
``semantic_only``; a claim the model honestly cannot bind is reported as
``unbindable`` with the model's reason. Nothing is silently dropped, no
SQL is run, no evidence is written — the engine does that, later.
"""

from dataclasses import dataclass, field
from pathlib import Path

from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.client import LLMClient, LLMResult, call_with_retry
from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.inputs import (
    build_binding_context,
    build_role_context,
    claim_label_map,
)
from before_we_ai.llm.mapping import (
    ProfileIndex,
    admissible_templates,
    binding_to_probe,
    check_binding,
    check_role_proposal,
    proposal_to_role_claim,
)
from before_we_ai.llm.prompts import (
    ROLE_BINDING_SYSTEM,
    V2_SYSTEM,
    render_template_docs,
    with_schema,
)
from before_we_ai.llm.roles import RoleSet, load_roles
from before_we_ai.llm.schemas import BindingBatch, RoleBindingBatch
from before_we_ai.model.enums import Actor, ClaimStatus
from before_we_ai.model.objects import Claim, RoleBindingClaim
from before_we_ai.profile.candidates import load_matrix
from before_we_ai.store.repository import ProjectStore

CONTRACT_ROLES = "role_binding"
CONTRACT_BIND = "v2_bind"


@dataclass
class RoleProposalReport:
    claims_created: list[str] = field(default_factory=list)
    claims_deduped: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (role, reason)
    failure: str | None = None
    retries: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    log_ref: str | None = None


def propose_role_bindings(
    root: str | Path,
    *,
    roles: RoleSet | None = None,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    scenario: str = "default",
) -> RoleProposalReport:
    root = Path(root)
    store = store or ProjectStore(root)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)
    if roles is None:
        if not config.roles_file:
            raise ValueError(
                "no role set: pass roles= or set llm.roles_file in before-ai.yaml"
            )
        roles = load_roles(root / config.roles_file)

    built = build_role_context(store, load_matrix(root), roles)
    index = ProfileIndex(store)

    def semantic_check(batch: RoleBindingBatch) -> list[str]:
        return [
            e for p in batch.proposals
            for e in check_role_proposal(p, roles.names, index)
        ]

    result = call_with_retry(
        client,
        contract=CONTRACT_ROLES,
        scenario=scenario,
        model=config.models[CONTRACT_ROLES],
        system=with_schema(ROLE_BINDING_SYSTEM, RoleBindingBatch),
        built=built,
        schema=RoleBindingBatch,
        semantic_check=semantic_check,
        logger=CallLogger(root),
    )
    report = RoleProposalReport(retries=result.retries, usage=result.usage,
                                log_ref=result.log_ref)
    if result.parsed is None:
        report.failure = result.failure
        return report

    for proposal in result.parsed.proposals:
        errors = check_role_proposal(proposal, roles.names, index)
        if errors:
            report.skipped.append((proposal.role, "; ".join(errors)))
            continue
        claim = proposal_to_role_claim(proposal, index)
        kept = store.add_claim(claim)
        if kept.id == claim.id:
            report.claims_created.append(claim.id)
        else:
            report.claims_deduped += 1
    return report


@dataclass
class V2Report:
    probes_created: list[str] = field(default_factory=list)
    probes_deduped: int = 0
    unbindable: list[tuple[str, str]] = field(default_factory=list)  # (claim_id, model's reason)
    semantic_only: list[str] = field(default_factory=list)  # never sent — no admissible template
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (claim_id, validation reason)
    unanswered: list[str] = field(default_factory=list)  # sent but absent from the answer
    failures: list[str] = field(default_factory=list)  # per-call double failures
    retries: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    log_refs: list[str] = field(default_factory=list)


def _unbound_ai_claims(store: ProjectStore,
                       claim_ids: list[str] | None) -> list[Claim]:
    bound = {p.claim_id for p in store.probes.values() if p.claim_id}
    selected = [
        c for c in store.claims.values()
        if c.created_by is Actor.AI
        and c.status is ClaimStatus.INFERRED
        and c.predicate is not None
        and c.id not in bound
        and (claim_ids is None or c.id in claim_ids)
    ]
    return sorted(selected, key=lambda c: c.id)


def _existing_probe(store: ProjectStore, probe) -> bool:
    return any(
        p.template == probe.template
        and p.claim_id == probe.claim_id
        and p.params == probe.params
        for p in store.probes.values()
    )


def bind_probes(
    root: str | Path,
    *,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    claim_ids: list[str] | None = None,
    scenario: str = "default",
) -> V2Report:
    root = Path(root)
    store = store or ProjectStore(root)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)
    index = ProfileIndex(store)
    report = V2Report()

    candidates = _unbound_ai_claims(store, claim_ids)
    role_claims, ordinary = [], []
    for claim in candidates:
        if isinstance(claim, RoleBindingClaim):
            role_claims.append(claim)
        elif admissible_templates(claim):
            ordinary.append(claim)
        else:
            report.semantic_only.append(claim.id)

    # Role bindings are a search task with domain judgment — frontier tier;
    # plain template binding runs mid-tier (architecture spec).
    batches = [
        (role_claims, CONTRACT_ROLES, f"{scenario}_roles"),
        (ordinary, CONTRACT_BIND, f"{scenario}_claims"),
    ]
    for claims, model_key, batch_scenario in batches:
        if not claims:
            continue
        labels = claim_label_map(claims)
        result = _bind_batch(
            root, store, index, labels, client,
            model=config.models[model_key], scenario=batch_scenario,
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
                continue
            claim = labels[binding.claim_id]
            probe = binding_to_probe(binding, claim)
            if probe is None:
                report.unbindable.append((claim.id, binding.no_template_reason))
                continue
            if _existing_probe(store, probe):
                report.probes_deduped += 1
                continue
            store.save_probe(probe)
            report.probes_created.append(probe.id)
        report.unanswered += [
            labels[label].id for label in labels if label not in answered
        ]
    return report


def _bind_batch(root: Path, store: ProjectStore, index: ProfileIndex,
                labels: dict[str, Claim], client: LLMClient,
                *, model: str, scenario: str) -> LLMResult:
    built = build_binding_context(store, labels, render_template_docs())

    def semantic_check(batch: BindingBatch) -> list[str]:
        return [
            e for b in batch.bindings
            for e in check_binding(b, labels, index)
        ]

    return call_with_retry(
        client,
        contract=CONTRACT_BIND,
        scenario=scenario,
        model=model,
        system=with_schema(V2_SYSTEM, BindingBatch),
        built=built,
        schema=BindingBatch,
        semantic_check=semantic_check,
        logger=CallLogger(root),
    )
