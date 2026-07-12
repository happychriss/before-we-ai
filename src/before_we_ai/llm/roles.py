"""Domain roles: flat curated YAML in, honest resolution out.

Roles are data, never code — a role file names the semantic slots of a
domain (journal, amount, account, ...) with one definition each, and the
product stays domain-agnostic because that file is supplied per project
(``llm.roles_file`` in before-ai.yaml). Invariant probes are formulated
against roles; the binding of a role to concrete columns is itself a
RoleBindingClaim that must earn its status.

Every role must declare how it can ever be settled (``decided_by``):

- the name of the domain law that can elect it (``balance``, ...) — the
  probes decide;
- ``fachfrage`` — no arithmetic can decide what a column *means*; the
  candidates go to the humans as a drafted question;
- ``slot`` — only ever carried inside another role's law, never decided
  on its own.

The pack lint rejects a role without a settlement path: silence must be
a declared property, never an accident. (A role can look decidable and
still be beyond any probe — a journal balances per period AND per
document AND per year, so a passing law never proves what one slot
*means*.)

``resolve_roles`` is the honesty valve, completing the rule *every
non-slot role ends in a probe verdict or a Fachfrage — never in
nothing*:

- law-decided role, candidates probed, none stands ≥ tested → Fachfrage;
- law-decided role whose law could never be bound to any candidate
  (all carry V2's no-probe declarations) → Fachfrage — knowledge is
  missing to even apply the law;
- fachfrage-decided role with candidates → Fachfrage listing them;
- any non-slot role for which the search proposed no candidate at all
  → Fachfrage.

The losing candidates keep their derived statuses; nothing is silently
discarded.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from before_we_ai.model.enums import ClaimStatus, EvidenceType
from before_we_ai.model.objects import QuestionCard, RoleBindingClaim
from before_we_ai.probes.library import REGISTRY
from before_we_ai.store.repository import ProjectStore

_SETTLED = (ClaimStatus.TESTED, ClaimStatus.BUSINESS_CONFIRMED)

DECIDED_BY_FACHFRAGE = "fachfrage"
DECIDED_BY_SLOT = "slot"

QUESTION_LOST = (
    "Fachfrage: Für die Rolle '{role}' hat keine vorgeschlagene Bindung ihre "
    "Invarianten-Sonde bestanden — welche Quelle ist führend?"
)
QUESTION_UNBOUND = (
    "Fachfrage: Für die Rolle '{role}' konnte keine vorgeschlagene Bindung an "
    "ihre Invarianten-Sonde gebunden werden — welches Fachwissen fehlt?"
)
QUESTION_CHOOSE = (
    "Fachfrage: Die Rolle '{role}' kann keine Sonde entscheiden — welche "
    "Bindung gilt: {options}?"
)
QUESTION_EMPTY = (
    "Fachfrage: Für die Rolle '{role}' wurde kein Kandidat vorgeschlagen — "
    "gibt es diese Rolle in dieser Datenlandschaft?"
)


class RoleSpec(BaseModel):
    """One role: its human-written definition and its settlement path."""

    model_config = ConfigDict(extra="forbid")

    definition: str
    decided_by: str  # a domain-law template name, "fachfrage", or "slot"


class RoleSet(BaseModel):
    """A flat per-domain role list, linted on load."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    roles: dict[str, RoleSpec]

    @property
    def names(self) -> list[str]:
        return list(self.roles)

    @model_validator(mode="after")
    def _lint(self) -> "RoleSet":
        """The pack lint: no role may be silent, no law misassigned."""
        laws = {name for name, spec in REGISTRY.items()
                if spec.domain == self.domain}
        errors = []
        for role, spec in self.roles.items():
            decider = spec.decided_by
            if decider in (DECIDED_BY_FACHFRAGE, DECIDED_BY_SLOT):
                continue
            if decider not in REGISTRY:
                errors.append(
                    f"role {role!r}: decided_by {decider!r} is no probe "
                    f"template and not one of "
                    f"({DECIDED_BY_FACHFRAGE!r}, {DECIDED_BY_SLOT!r})"
                )
            elif decider not in laws:
                errors.append(
                    f"role {role!r}: decided_by {decider!r} is not a "
                    f"domain law of {self.domain!r} — a generic template "
                    "cannot elect a role"
                )
        if errors:
            raise ValueError("role pack lint: " + "; ".join(errors))
        return self


def load_roles(path: str | Path) -> RoleSet:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return RoleSet.model_validate(data)


def _binding_text(claim: RoleBindingClaim) -> str:
    return ", ".join(f"{k}={v}" for k, v in sorted(claim.binding.items()))


def _has_no_probe_declaration(store: ProjectStore,
                              claim: RoleBindingClaim) -> bool:
    return any(
        e.type is EvidenceType.DECLARATION and "decision" in e.payload
        for e in store.evidence_for(claim)
    )


def resolve_roles(store: ProjectStore, roles: RoleSet) -> list[QuestionCard]:
    """Every non-slot role ends in a probe verdict or a Fachfrage.

    Idempotent: question text is deduped exactly, like the engine's
    Fachfragen. Roles still genuinely in flight (candidates without a
    probe result and without a V2 no-probe declaration) draft nothing —
    a question about an untried binding would be noise.
    """
    any_candidates = any(
        isinstance(c, RoleBindingClaim) for c in store.claims.values()
    )
    drafted = []
    for role in roles.names:
        spec = roles.roles[role]
        if spec.decided_by == DECIDED_BY_SLOT:
            continue
        candidates = sorted(
            (c for c in store.claims.values()
             if isinstance(c, RoleBindingClaim) and c.role == role),
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
        elif spec.decided_by == DECIDED_BY_FACHFRAGE:
            options = " | ".join(sorted(_binding_text(c) for c in candidates))
            text = QUESTION_CHOOSE.format(role=role, options=options)
        else:  # a domain law decides — did it get to speak?
            probed = any(
                e.type is EvidenceType.PROBE_RESULT and not e.stale
                for c in candidates
                for e in store.evidence_for(c)
            )
            if probed:
                text = QUESTION_LOST.format(role=role)
            elif all(_has_no_probe_declaration(store, c) for c in candidates):
                text = QUESTION_UNBOUND.format(role=role)
            else:
                continue  # binding still pending, not yet a question
        if any(card.question == text for card in store.questions.values()):
            continue
        card = QuestionCard(question=text, claim_ids=[c.id for c in candidates])
        store.save_question(card)
        drafted.append(card)
    return drafted
