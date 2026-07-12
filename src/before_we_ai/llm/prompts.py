"""The contract prompts — part of the product, reviewed like code.

Strictly generic data-profiling language: no domain vocabulary, no hints
about any particular dataset. Domain knowledge enters a call exclusively
through the built input (profiles, matrix, role definitions, claims).
A test-side tripwire scans these strings and every built input for
corpus-trap tokens.

Each system prompt ends with the JSON schema the answer must satisfy;
the response is parsed and Pydantic-validated locally, with exactly one
retry that feeds the validation errors back.
"""

import json

from pydantic import BaseModel

from before_we_ai.llm.vocabulary import PREDICATES, TEMPLATE_NOTES, TEMPLATE_PARAMS

_JSON_RULES = (
    "Respond with a single JSON object that validates against this JSON "
    "schema — no prose before or after, no markdown fences, no fields "
    "beyond the schema:\n\n{schema}"
)


def with_schema(system: str, schema: type[BaseModel]) -> str:
    rendered = json.dumps(schema.model_json_schema(), sort_keys=True,
                          ensure_ascii=False)
    return system + "\n\n" + _JSON_RULES.format(schema=rendered)


def render_predicate_docs() -> str:
    """The controlled predicate vocabulary, rendered for the V1 prompt."""
    lines = ["Available predicates (use no others):"]
    for name in sorted(PREDICATES):
        spec = PREDICATES[name]
        params = ", ".join(sorted(spec.required_params)) or "none"
        optional = ", ".join(sorted(spec.optional_params))
        suffix = f" (optional: {optional})" if optional else ""
        lines.append(f"- {name}: required params [{params}]{suffix}")
    return "\n".join(lines)


def render_template_docs() -> str:
    """Generic documentation of the probe templates, for the V2 prompt."""
    lines = [
        "## Probe templates",
        "Each template is a falsification attempt rendered as SQL. "
        "Params reference views and columns by their catalog names.",
    ]
    for name in sorted(TEMPLATE_PARAMS):
        contract = TEMPLATE_PARAMS[name]
        parts = [f"required [{', '.join(sorted(contract.required))}]"]
        if contract.exactly_one_of:
            for group in contract.exactly_one_of:
                parts.append(f"exactly one of [{', '.join(sorted(group))}]")
        if contract.optional:
            parts.append(f"optional [{', '.join(sorted(contract.optional))}]")
        if name in TEMPLATE_NOTES:
            parts.append(f"NOTE: {TEMPLATE_NOTES[name]}")
        lines.append(f"- {name}: " + "; ".join(parts))
    lines.append(
        "Param values are bare view/column identifiers unless the param name "
        "says expression (*_expr) or filter (*where)."
    )
    return "\n".join(lines)


V1_SYSTEM = (
    "You are the hypothesis stage of an evidence-based data-discovery "
    "tool. You receive column profiles (measured statistics, never raw "
    "data) and a candidate matrix of value overlaps between columns from "
    "a data landscape you have never seen.\n\n"
    "Propose claim hypotheses: reusable semantic rules about how the "
    "tables relate and what constraints the data appears to obey. Every "
    "hypothesis you produce starts as an unverified inference and will be "
    "tested by deterministic probes or reviewed by a human — you cannot "
    "confirm anything, so propose freely but ground every hypothesis in "
    "the supplied profiles.\n\n"
    "Guidance:\n"
    "- Derive rules only from what the profiles and matrix show: value "
    "overlaps suggest references; low distinct-count columns suggest "
    "units or codes; per-key version columns suggest temporal validity; "
    "matching row counts and amount-like columns suggest reconciliation.\n"
    "- The candidate matrix includes chance overlaps; a high containment "
    "is a reason to hypothesize, not to believe.\n"
    "- Also propose relationships the matrix CANNOT see: columns or "
    "groupings in different tables or languages whose names, described "
    "meanings, or value shapes indicate they express the same concept "
    "without sharing values (predicate semantic_equivalent).\n"
    "- Name business concepts that the landscape implies but does not "
    "define (kind=concept, predicate concept_definition) when a "
    "definition is genuinely in question.\n"
    "- Reference columns strictly as view.column exactly as they appear "
    "in the profiles.\n"
    "- One rule per hypothesis; keep statements to one sentence; put the "
    "grounding in the rationale.\n\n"
    + render_predicate_docs()
)

ROLE_BINDING_SYSTEM = (
    "You are the role-binding stage of an evidence-based data-discovery "
    "tool. You receive a flat list of domain roles with definitions, plus "
    "column profiles and a candidate matrix from a data landscape you "
    "have never seen.\n\n"
    "Propose candidate bindings: for each role, which view (and columns) "
    "most plausibly plays that role. Propose multiple competing "
    "candidates for a role when the landscape offers more than one "
    "plausible occupant — an invariant probe will decide, not you. "
    "Binding parts use keys named after the role's aspects (for example "
    "table, column, amount, key) with values that are view or "
    "view.column references exactly as profiled. It is better to propose "
    "a losing candidate than to omit a plausible one silently."
)

V2_SYSTEM = (
    "You are the probe-binding stage of an evidence-based data-discovery "
    "tool. You receive claims (each with a predicate and params), the "
    "profiles of the columns they touch, the schemas of the views "
    "involved, and the documentation of the available probe templates.\n\n"
    "For every claim (answer with its claim id exactly as given in the "
    "input), either instantiate the most suitable template — filling "
    "every required param with concrete view/column names from the "
    "supplied schemas — or answer template=null with a short "
    "no_template_reason when no template can test the claim. Every claim "
    "lists its admissible templates; choose among those only. Never force "
    "a fit: an honest null keeps the claim visible as untested, which is "
    "the correct outcome for rules that only a human or a document can "
    "settle."
)

V2_ROLES_SYSTEM = V2_SYSTEM + (
    "\n\nThe claims in this batch are role bindings: each asserts that "
    "specific views/columns play a domain role. A role binding IS "
    "falsifiable — by instantiating the conservation law implied by the "
    "role's definition against the bound columns (its admissible "
    "templates are the invariant probes). A binding whose invariant holds "
    "is supported; one whose invariant fails is refuted — that is how "
    "competing candidates for the same role are decided. Bind each "
    "role-binding claim to the invariant template its role definition "
    "implies, taking params from the claim's binding; answer "
    "template=null only when the role's definition genuinely implies no "
    "testable invariant."
)
