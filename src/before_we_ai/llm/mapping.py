"""Deterministic mapping from validated LLM answers to core objects.

Pure functions, no IO, no LLM: given a schema-valid answer and the
project's profile index, produce Claims and Probes via the M1 core — or a
list of error strings. The ``check_*`` functions double as the semantic
half of the retry loop: their errors are fed back to the model verbatim,
so retry feedback and final mapping can never disagree.

Everything created here carries ``Actor.AI`` and therefore starts (and,
without probe/human evidence, stays) ``inferred`` — that is the M1 core's
law, not this module's choice.

Params are canonicalized (stripped strings, sorted string lists) before
they enter a ``Predicate``, so ``semantics.claim_key`` dedups paraphrases
of the same rule.
"""

from before_we_ai.llm.schemas import Hypothesis, ProbeBinding, RoleBindingProposal
from before_we_ai.llm.vocabulary import (
    INVARIANT_TEMPLATES,
    PREDICATES,
    ROLE_BINDING_PREDICATE,
    check_template_params,
)
from before_we_ai.model.enums import Actor
from before_we_ai.model.objects import (
    Claim,
    ConceptClaim,
    Predicate,
    Probe,
    RoleBindingClaim,
    Scope,
    Validity,
)
from before_we_ai.model.transitions import create_claim
from before_we_ai.store.repository import ProjectStore


class ProfileIndex:
    """The ground the answers must stand on: known views and columns."""

    def __init__(self, store: ProjectStore):
        self.columns: dict[str, str] = {}  # "view.column" -> source_id
        self.views: dict[str, str] = {}  # view -> source_id
        for p in store.profiles.values():
            self.columns[f"{p.table}.{p.column}"] = p.source_id
            self.views[p.table] = p.source_id

    def check_ref(self, value: str) -> str | None:
        """Error string if ``value`` looks like a catalog reference but isn't one."""
        if value in self.views or value in self.columns:
            return None
        prefix = value.split(".", 1)[0]
        if prefix in self.views:
            return f"unknown column reference {value!r}"
        return None  # not a reference — plain values pass through unchecked

    def source_ids(self, values: list[str]) -> list[str]:
        ids = {self.columns[v] for v in values if v in self.columns}
        ids |= {self.views[v] for v in values if v in self.views}
        return sorted(ids)


def _canonical_params(params: dict) -> dict:
    canonical = {}
    for key, value in params.items():
        if isinstance(value, str):
            canonical[key] = value.strip()
        elif isinstance(value, list) and all(isinstance(v, str) for v in value):
            canonical[key] = sorted(v.strip() for v in value)
        else:
            canonical[key] = value
    return canonical


def _string_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _string_values(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _string_values(v)]
    return []


# -- V1: hypotheses -------------------------------------------------------

def check_hypothesis(h: Hypothesis, index: ProfileIndex) -> list[str]:
    errors = []
    spec = PREDICATES[h.predicate]
    if (h.kind == "concept") != (h.predicate == "concept_definition"):
        errors.append(
            f"hypothesis {h.statement!r}: kind {h.kind!r} does not fit "
            f"predicate {h.predicate!r} (concepts use concept_definition)"
        )
    keys = set(h.params)
    for missing in sorted(spec.required_params - keys):
        errors.append(
            f"hypothesis {h.statement!r}: predicate {h.predicate!r} "
            f"requires param {missing!r}"
        )
    for unknown in sorted(keys - spec.allowed_params):
        errors.append(
            f"hypothesis {h.statement!r}: param {unknown!r} is not allowed "
            f"for predicate {h.predicate!r}"
        )
    refs = list(h.columns) + _string_values(h.params)
    for ref in refs:
        problem = index.check_ref(ref)
        if problem:
            errors.append(f"hypothesis {h.statement!r}: {problem}")
    for column in h.columns:
        if column not in index.columns:
            errors.append(
                f"hypothesis {h.statement!r}: column {column!r} is not "
                "in the profiles"
            )
    if h.kind == "rule" and not index.source_ids(refs):
        errors.append(
            f"hypothesis {h.statement!r}: grounded in no known view or column"
        )
    return errors


def hypothesis_to_claim(h: Hypothesis, index: ProfileIndex) -> Claim:
    """Deterministic Hypothesis -> Claim/ConceptClaim; assumes checks passed."""
    predicate = Predicate(name=h.predicate, params=_canonical_params(h.params))
    scope = Scope(**h.scope.model_dump()) if h.scope else None
    validity = (
        Validity(valid_from=h.valid_from, valid_to=h.valid_to)
        if (h.valid_from or h.valid_to) else None
    )
    source_ids = index.source_ids(list(h.columns) + _string_values(h.params))
    if h.kind == "concept":
        return ConceptClaim(
            statement=h.statement,
            created_by=Actor.AI,
            predicate=predicate,
            scope=scope,
            validity=validity,
            source_ids=source_ids,
            term=h.term,
            definition=h.definition,
        )
    return create_claim(
        h.statement,
        Actor.AI,
        predicate=predicate,
        scope=scope,
        validity=validity,
        source_ids=source_ids,
    )


# -- role bindings --------------------------------------------------------

def check_role_proposal(p: RoleBindingProposal, role_names: list[str],
                        index: ProfileIndex) -> list[str]:
    errors = []
    if p.role not in role_names:
        errors.append(f"proposal binds unknown role {p.role!r}")
    for part, value in p.binding.items():
        if value not in index.views and value not in index.columns:
            errors.append(
                f"proposal for role {p.role!r}: binding part {part!r} "
                f"references unknown {value!r}"
            )
    return errors


def proposal_to_role_claim(p: RoleBindingProposal, index: ProfileIndex) -> RoleBindingClaim:
    binding = {k: v.strip() for k, v in sorted(p.binding.items())}
    rendered = ", ".join(f"{k}={v}" for k, v in binding.items())
    return RoleBindingClaim(
        statement=f"role '{p.role}' is played by {rendered}",
        created_by=Actor.AI,
        predicate=Predicate(
            name=ROLE_BINDING_PREDICATE,
            params={"role": p.role, "binding": binding},
        ),
        source_ids=index.source_ids(list(binding.values())),
        role=p.role,
        binding=binding,
    )


# -- V2: probe bindings ---------------------------------------------------

def admissible_templates(claim: Claim) -> tuple[str, ...]:
    if isinstance(claim, RoleBindingClaim):
        return INVARIANT_TEMPLATES
    if claim.predicate and claim.predicate.name in PREDICATES:
        return PREDICATES[claim.predicate.name].templates
    return ()


def check_binding(b: ProbeBinding, claims_by_id: dict[str, Claim],
                  index: ProfileIndex) -> list[str]:
    claim = claims_by_id.get(b.claim_id)
    if claim is None:
        return [f"binding references unknown claim {b.claim_id!r}"]
    if b.template is None:
        return []
    errors = []
    allowed = admissible_templates(claim)
    if b.template not in allowed:
        errors.append(
            f"claim {b.claim_id}: template {b.template!r} cannot test "
            f"predicate {claim.predicate.name if claim.predicate else None!r} "
            f"(admissible: {sorted(allowed) or 'none'})"
        )
    errors += [f"claim {b.claim_id}: {e}"
               for e in check_template_params(b.template, b.params)]
    for ref in _string_values(b.params):
        problem = index.check_ref(ref)
        if problem:
            errors.append(f"claim {b.claim_id}: {problem}")
    return errors


def binding_to_probe(b: ProbeBinding, claim: Claim) -> Probe | None:
    """Deterministic ProbeBinding -> Probe; assumes checks passed."""
    if b.template is None:
        return None
    return Probe(
        template=b.template,
        claim_id=claim.id,
        roles=[claim.role] if isinstance(claim, RoleBindingClaim) else [],
        params=_canonical_params(b.params),
    )
