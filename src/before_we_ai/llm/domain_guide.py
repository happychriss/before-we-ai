"""Domain roles: flat curated YAML in, honest resolution out.

Roles are data, never code — a role file names the semantic slots of a
domain (journal, amount, account, ...) with one definition each, and the
product stays domain-agnostic because that file is supplied per project
(``llm.domain_guide_file`` in before-ai.yaml). Invariant checks are formulated
against roles; the binding of a role to concrete columns is itself a
MappingClaim that must earn its status.

Every role must declare how it can ever be settled (``decided_by``):

- the name of the domain law that can elect it (``balance``, ...) — the
  checks decide;
- ``clarification`` — no arithmetic can decide what a column *means*; the
  candidates go to the humans as a drafted question;
- ``slot`` — only ever carried inside another role's law, never decided
  on its own.

The pack lint rejects a role without a settlement path: silence must be
a declared property, never an accident. (A role can look decidable and
still be beyond any check — a journal balances per period AND per
document AND per year, so a passing law never proves what one slot
*means*.)

``resolve_mappings`` is the honesty valve, completing the rule *every
non-slot role ends in a check verdict or a clarification question — never in
nothing*:

- law-decided role, candidates checked, none stands ≥ test-supported → clarification question;
- law-decided role whose law could never be bound to any candidate
  (all carry V2's no-check declarations) → clarification question — knowledge is
  missing to even apply the law;
- clarification-decided role with candidates → clarification question listing them;
- any non-slot role for which the search proposed no candidate at all
  → clarification question.

The losing candidates keep their derived statuses; nothing is silently
discarded.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from before_we_ai.model.enums import ClaimStatus, EvidenceType
from before_we_ai.model.objects import ClarificationQuestion, MappingClaim
from before_we_ai.checks.library import REGISTRY
from before_we_ai.store.repository import ProjectStore

_SETTLED = (ClaimStatus.TEST_SUPPORTED, ClaimStatus.BUSINESS_CONFIRMED)

DECIDED_BY_CLARIFICATION = "clarification"
DECIDED_BY_SLOT = "slot"

QUESTION_LOST = (
    "Clarification question: for the role '{role}' no proposed binding passed "
    "its invariant check — which source is authoritative?"
)
QUESTION_UNBOUND = (
    "Clarification question: for the role '{role}' no proposed binding could be "
    "bound to its invariant check — what domain knowledge is missing?"
)
QUESTION_CHOOSE = (
    "Clarification question: no check can decide the role '{role}' — which "
    "binding applies: {options}?"
)
QUESTION_EMPTY = (
    "Clarification question: no candidate was proposed for the role '{role}' — "
    "does this role exist in this data landscape?"
)


class RoleSpec(BaseModel):
    """One role: its human-written definition and its settlement path."""

    model_config = ConfigDict(extra="forbid")

    definition: str
    decided_by: str  # a domain-law template name, "clarification", or "slot"


class DomainGuide(BaseModel):
    """A flat per-domain role list, linted on load."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    roles: dict[str, RoleSpec]

    @property
    def names(self) -> list[str]:
        return list(self.roles)

    @model_validator(mode="after")
    def _lint(self) -> "DomainGuide":
        """The pack lint: no role may be silent, no law misassigned."""
        laws = {name for name, spec in REGISTRY.items()
                if spec.domain == self.domain}
        errors = []
        for role, spec in self.roles.items():
            decider = spec.decided_by
            if decider in (DECIDED_BY_CLARIFICATION, DECIDED_BY_SLOT):
                continue
            if decider not in REGISTRY:
                errors.append(
                    f"role {role!r}: decided_by {decider!r} is no check "
                    f"template and not one of "
                    f"({DECIDED_BY_CLARIFICATION!r}, {DECIDED_BY_SLOT!r})"
                )
            elif decider not in laws:
                errors.append(
                    f"role {role!r}: decided_by {decider!r} is not a "
                    f"domain law of {self.domain!r} — a generic template "
                    "cannot elect a role"
                )
        if errors:
            raise ValueError("domain guide lint: " + "; ".join(errors))
        return self


def load_domain_guide(path: str | Path) -> DomainGuide:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return DomainGuide.model_validate(data)


def _binding_text(claim: MappingClaim) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(claim.binding.items()))


def _has_no_check_declaration(store: ProjectStore,
                              claim: MappingClaim) -> bool:
    return any(
        e.type is EvidenceType.DECLARATION and "decision" in e.payload
        for e in store.evidence_for(claim)
    )


def resolve_mappings(store: ProjectStore, roles: DomainGuide) -> list[ClarificationQuestion]:
    """Every non-slot role ends in a check verdict or a clarification question.

    Idempotent: question text is deduped exactly, like the engine's
    Clarification questions. Roles still genuinely in flight (candidates without a
    check result and without a V2 no-check declaration) draft nothing —
    a question about an untried binding would be noise.
    """
    any_candidates = any(
        isinstance(c, MappingClaim) for c in store.claims.values()
    )
    drafted = []
    for role in roles.names:
        spec = roles.roles[role]
        if spec.decided_by == DECIDED_BY_SLOT:
            continue
        candidates = sorted(
            (c for c in store.claims.values()
             if isinstance(c, MappingClaim) and c.role == role),
            key=lambda c: c.id,
        )
        if any(c.status in _SETTLED for c in candidates):
            continue
        if not candidates:
            # only once the search has run at all — an empty store is
            # a project that has not reached the proposal step yet
            if not any_candidates:
                continue
            text = QUESTION_EMPTY.format(role=role)
        elif spec.decided_by == DECIDED_BY_CLARIFICATION:
            options = " | ".join(sorted(_binding_text(c) for c in candidates))
            text = QUESTION_CHOOSE.format(role=role, options=options)
        else:  # a domain law decides — did it get to speak?
            checked = any(
                e.type is EvidenceType.CHECK_RESULT and not e.stale
                for c in candidates
                for e in store.evidence_for(c)
            )
            if checked:
                text = QUESTION_LOST.format(role=role)
            elif all(_has_no_check_declaration(store, c) for c in candidates):
                text = QUESTION_UNBOUND.format(role=role)
            else:
                continue  # binding still pending, not yet a question
        if any(card.question == text for card in store.questions.values()):
            continue
        card = ClarificationQuestion(question=text, claim_ids=[c.id for c in candidates])
        store.save_question(card)
        drafted.append(card)
    return drafted
