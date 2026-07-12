"""Deterministic input builders — profiles in, one reproducible text out.

The contracts never see raw data: their context is built exclusively from
column profiles, the candidate matrix, role definitions, and claims.
Assembly is deterministic (stable ordering and selection everywhere), so
the same project state produces byte-identical input — the foundation for
reproducible online runs and for the fixture drift guard.

There is **no token budget**: the goal is complete, well-structured
context. The only trimming mechanism is the explicit ``max_chars`` escape
hatch (default off); when it ever fires, it cuts the lowest-signal fields
first and records every cut in ``trim_notices`` — which the call logger
persists. Silent truncation is structurally impossible: all rendering
funnels through ``BuiltInput``.
"""

import hashlib
import json

from pydantic import BaseModel

from before_we_ai.llm.roles import RoleSet
from before_we_ai.llm.vocabulary import INVARIANT_TEMPLATES, PREDICATES
from before_we_ai.model.objects import Claim, ColumnProfile, RoleBindingClaim
from before_we_ai.store.repository import ProjectStore


class BuiltInput(BaseModel):
    text: str
    sha256: str
    trim_notices: list[str] = []


def _built(text: str, trim_notices: list[str] | None = None) -> BuiltInput:
    return BuiltInput(
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        trim_notices=trim_notices or [],
    )


def _sorted_profiles(store: ProjectStore) -> list[ColumnProfile]:
    return sorted(store.profiles.values(), key=lambda p: (p.table, p.column))


def _render_profile(p: ColumnProfile, *, top_k: int | None = None,
                    patterns: bool = True) -> str:
    s = p.stats
    lines = [
        f"### {p.table}.{p.column}",
        "type={} class={} rows={} nulls={} distinct={}".format(
            s.get("duckdb_type"), s.get("value_class"), s.get("row_count"),
            s.get("null_count"), s.get("distinct_count"),
        ),
        "min={} max={} len(min/avg/max)={}/{}/{}".format(
            s.get("min"), s.get("max"),
            s.get("len_min"), s.get("len_avg"), s.get("len_max"),
        ),
    ]
    top = list(s.get("top_values") or [])
    if top_k is not None:
        top = top[:top_k]
    if top:
        lines.append("top: " + ", ".join(f"{t['value']!r}×{t['count']}" for t in top))
    if patterns and s.get("patterns"):
        lines.append(
            "patterns: " + ", ".join(f"{m['mask']}×{m['count']}" for m in s["patterns"])
        )
    return "\n".join(lines)


def _render_matrix(matrix: dict) -> str:
    lines = [
        "## Candidate matrix (measured value overlap between columns — "
        f"containment ≥ {matrix['threshold']}; chance overlaps included, "
        "the matrix measures and never judges)",
    ]
    lines += [f"WARNING: {w}" for w in matrix.get("warnings", [])]
    lines.append("left | right | overlap | containment | jaccard")
    lines += [
        f"{c['left']} | {c['right']} | {c['overlap']} "
        f"| {c['containment']} | {c['jaccard']}"
        for c in matrix["candidates"]
    ]
    return "\n".join(lines)


def _profile_body(store: ProjectStore, matrix: dict, *,
                  patterns: bool = True, top_k: int | None = None) -> str:
    blocks = [
        _render_profile(p, patterns=patterns, top_k=top_k)
        for p in _sorted_profiles(store)
    ]
    return "\n\n".join(["## Column profiles"] + blocks + [_render_matrix(matrix)])


def _assemble(render, max_chars: int | None) -> BuiltInput:
    """Render; apply the visible-trim ladder only if ``max_chars`` fires.

    ``render(patterns=..., top_k=...)`` must be a pure function of its
    arguments — determinism lives there; this helper only sequences the
    ladder and records every cut.
    """
    text = render()
    if max_chars is None or len(text) <= max_chars:
        return _built(text)
    notices = []
    text = render(patterns=False)
    notices.append("trimmed: dropped 'patterns' lines from all column profiles")
    if len(text) > max_chars:
        text = render(patterns=False, top_k=3)
        notices.append("trimmed: top_values capped at 3 entries per column")
    if len(text) > max_chars:
        text = text[:max_chars]
        notices.append(f"trimmed: hard cut at {max_chars} characters")
    return _built(text, notices)


def build_profile_context(store: ProjectStore, matrix: dict,
                          *, max_chars: int | None = None) -> BuiltInput:
    """V1 input: every column profile + the full candidate matrix."""
    def render(patterns: bool = True, top_k: int | None = None) -> str:
        return _profile_body(store, matrix, patterns=patterns, top_k=top_k)

    return _assemble(render, max_chars)


def build_role_context(store: ProjectStore, matrix: dict, roles: RoleSet,
                       *, max_chars: int | None = None) -> BuiltInput:
    """Role-binding input: the role definitions first, then the V1 context."""
    def render(patterns: bool = True, top_k: int | None = None) -> str:
        # only name + definition enter the prompt — decided_by is lint
        # metadata for the settlement path, never a hint to the model
        role_lines = [f"## Roles to bind (domain: {roles.domain})"]
        role_lines += [f"- {name}: {spec.definition}"
                       for name, spec in roles.roles.items()]
        body = _profile_body(store, matrix, patterns=patterns, top_k=top_k)
        return "\n".join(role_lines) + "\n\n" + body

    return _assemble(render, max_chars)


def _string_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _string_values(v)]
    if isinstance(value, (list, tuple)):
        return [s for v in value for s in _string_values(v)]
    return []


def _param_refs(claim: Claim) -> list[str]:
    return _string_values(claim.predicate.params if claim.predicate else {})


def claim_label_map(claims: list[Claim]) -> dict[str, Claim]:
    """Deterministic labels (c1, c2, ...) for a set of claims.

    Ordered by claim *identity* (predicate, params, scope, validity,
    statement), never by ULID — so the same claim set labels identically
    in every fresh project. The binding contract references claims by
    these labels; ULIDs never enter a prompt.
    """
    def identity(claim: Claim) -> str:
        return json.dumps({
            "predicate": claim.predicate.name if claim.predicate else None,
            "params": claim.predicate.params if claim.predicate else {},
            "scope": claim.scope.model_dump() if claim.scope else None,
            "validity": claim.validity.model_dump() if claim.validity else None,
            "statement": claim.statement,
        }, sort_keys=True, ensure_ascii=False, default=str)

    ordered = sorted(claims, key=identity)
    return {f"c{i}": claim for i, claim in enumerate(ordered, start=1)}


def build_binding_context(store: ProjectStore, labels: dict[str, Claim],
                          template_docs: str,
                          *, max_chars: int | None = None) -> BuiltInput:
    """V2 input: the labelled claims to bind, the profiles of the columns
    they touch, the schemas of the views involved, and the template docs."""
    profile_keys = {f"{p.table}.{p.column}": p for p in _sorted_profiles(store)}
    view_names = {p.table for p in store.profiles.values()}
    claims = list(labels.values())

    def render(patterns: bool = True, top_k: int | None = None) -> str:
        views = sorted({
            ref.split(".", 1)[0] for c in claims for ref in _param_refs(c)
            if ref.split(".", 1)[0] in view_names
        } | {ref for c in claims for ref in _param_refs(c) if ref in view_names})
        schema_lines = ["## View schemas involved"]
        for view in views:
            cols = [p for p in _sorted_profiles(store) if p.table == view]
            schema_lines.append(
                f"- {view}: " + ", ".join(
                    f"{p.column} ({p.stats.get('duckdb_type')})" for p in cols
                )
            )
        claim_blocks = []
        for label, claim in labels.items():
            predicate = claim.predicate
            if isinstance(claim, RoleBindingClaim):
                admissible = INVARIANT_TEMPLATES
            elif predicate and predicate.name in PREDICATES:
                admissible = PREDICATES[predicate.name].templates
            else:
                admissible = ()
            lines = [
                f"### claim {label}",
                f"statement: {claim.statement}",
                f"predicate: {predicate.name if predicate else None}",
                "params: " + json.dumps(
                    predicate.params if predicate else {},
                    sort_keys=True, ensure_ascii=False, default=str,
                ),
                "admissible templates: " + (", ".join(sorted(admissible)) or "none"),
            ]
            for ref in sorted({r for r in _param_refs(claim) if r in profile_keys}):
                lines.append(
                    _render_profile(profile_keys[ref], patterns=patterns, top_k=top_k)
                )
            claim_blocks.append("\n".join(lines))
        return "\n\n".join(
            [template_docs, "\n".join(schema_lines), "## Claims to bind"]
            + claim_blocks
        )

    return _assemble(render, max_chars)
