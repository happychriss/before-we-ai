"""Domain roles: flat curated YAML in, honest resolution out.

Roles are data, never code — a role file names the semantic slots of a
domain (journal, amount, account, ...) with one definition each, and the
product stays domain-agnostic because that file is supplied per project
(``llm.roles_file`` in before-ai.yaml). Invariant probes are formulated
against roles; the binding of a role to concrete columns is itself a
RoleBindingClaim that must earn its status.

``resolve_roles`` is the honesty valve: when a role has candidate
bindings, probing has been attempted, and still no candidate stands at
least ``tested``, that is not a silent discard — it becomes a Fachfrage.
The losing candidates keep their derived statuses; what is unresolved is
the *role*, and the QuestionCard is where that lives.
"""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict

from before_we_ai.model.enums import ClaimStatus, EvidenceType
from before_we_ai.model.objects import QuestionCard, RoleBindingClaim
from before_we_ai.store.repository import ProjectStore

_SETTLED = (ClaimStatus.TESTED, ClaimStatus.BUSINESS_CONFIRMED)

QUESTION = (
    "Fachfrage: Für die Rolle '{role}' hat keine vorgeschlagene Bindung ihre "
    "Invarianten-Sonde bestanden — welche Quelle ist führend?"
)


class RoleSet(BaseModel):
    """A flat per-domain role list: name -> one-paragraph definition."""

    model_config = ConfigDict(extra="forbid")

    domain: str
    roles: dict[str, str]

    @property
    def names(self) -> list[str]:
        return list(self.roles)


def load_roles(path: str | Path) -> RoleSet:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    return RoleSet.model_validate(data)


def resolve_roles(store: ProjectStore, roles: RoleSet) -> list[QuestionCard]:
    """Draft a Fachfrage for every role whose candidates were probed and all lost.

    Skips roles without candidates (nothing proposed yet) and roles where
    no candidate has probe evidence (nothing decided yet) — a question
    about an untried binding would be noise. Idempotent: question text is
    deduped exactly, like the engine's Fachfragen.
    """
    drafted = []
    for role in roles.names:
        candidates = sorted(
            (c for c in store.claims.values()
             if isinstance(c, RoleBindingClaim) and c.role == role),
            key=lambda c: c.id,
        )
        if not candidates:
            continue
        if any(c.status in _SETTLED for c in candidates):
            continue
        probed = any(
            e.type is EvidenceType.PROBE_RESULT and not e.stale
            for c in candidates
            for e in store.evidence_for(c)
        )
        if not probed:
            continue
        text = QUESTION.format(role=role)
        if any(card.question == text for card in store.questions.values()):
            continue
        card = QuestionCard(question=text, claim_ids=[c.id for c in candidates])
        store.save_question(card)
        drafted.append(card)
    return drafted
