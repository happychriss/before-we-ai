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

from before_we_ai.checks.library import REGISTRY
from before_we_ai.llm.vocabulary import (
    PREDICATES,
    TEMPLATE_NOTES,
    TEMPLATE_PARAMS,
    VALUE_PARAMS,
)

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
    """Documentation of the check definitions, for the V2 prompt.

    Each entry says whether it is a generic data check or a **domain law**,
    because the two are different kinds of thing and the model was being
    asked to choose between them blind. A domain law is a conservation law
    of its domain: it is what elects the occupant of a business object, so
    binding one is a stronger move than binding a generic check, and worth
    being deliberate about. What is domain-specific must always be
    enumerable — that is the rule the tag makes visible here.
    """
    lines = [
        "## Check definitions",
        "Each template is a falsification attempt rendered as SQL. "
        "Params reference views and columns by their catalog names. A "
        "template marked [domain law: X] encodes a conservation law of "
        "domain X and decides which candidate occupies a business object; "
        "the rest are generic data checks that hold in any domain.",
    ]
    for name in sorted(TEMPLATE_PARAMS):
        contract = TEMPLATE_PARAMS[name]
        definition = REGISTRY.get(name)
        domain = getattr(definition, "domain", None) if definition else None
        parts = [f"[domain law: {domain}]"] if domain else []
        parts.append(f"required [{', '.join(sorted(contract.required))}]")
        if contract.exactly_one_of:
            for group in contract.exactly_one_of:
                parts.append(f"exactly one of [{', '.join(sorted(group))}]")
        if contract.optional:
            parts.append(f"optional [{', '.join(sorted(contract.optional))}]")
        if name in TEMPLATE_NOTES:
            parts.append(f"NOTE: {TEMPLATE_NOTES[name]}")
        # The exceptions to the closing rule, stated on the template that has
        # them. A global "unless the param name says so" cannot cover a param
        # whose name says nothing — and `accounts` reads like a table.
        for param, meaning in VALUE_PARAMS.items():
            if param in contract.allowed:
                parts.append(f"VALUES: {param} is {meaning}")
        lines.append(f"- {name}: " + "; ".join(parts))
    lines.append(
        "Param values are bare view/column identifiers, EXCEPT where a "
        "template above marks a param VALUES (it holds data, not names) and "
        "except params whose name says expression (*_expr) or filter (*where)."
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
    "tested by deterministic checks or reviewed by a human — you cannot "
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
    "define (predicate concept_definition, with the term it defines) when "
    "a definition is genuinely in question.\n"
    "- Reference columns strictly as view.column exactly as they appear "
    "in the profiles.\n"
    "- One rule per hypothesis; keep statements to one sentence; put the "
    "grounding in the rationale.\n\n"
    + render_predicate_docs()
)

MAPPING_SYSTEM = (
    "You are the mapping stage of an evidence-based data-discovery "
    "tool. You receive a flat list of domain roles with definitions, plus "
    "column profiles and a candidate matrix from a data landscape you "
    "have never seen.\n\n"
    "Propose candidate bindings: for each role, which view (and columns) "
    "most plausibly plays that role. Propose multiple competing "
    "candidates for a role when the landscape offers more than one "
    "plausible occupant — an invariant check will decide, not you. "
    "Binding parts use keys named after the role's aspects (for example "
    "table, column, amount, key) with values that are view or "
    "view.column references exactly as profiled. It is better to propose "
    "a losing candidate than to omit a plausible one silently."
)

V2_SYSTEM = (
    "You are the check-planning stage of an evidence-based data-discovery "
    "tool. You receive claims (each with a predicate and params), the "
    "profiles of the columns they touch, the schemas of the views "
    "involved, and the documentation of the available check definitions.\n\n"
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

REQUEST_SYSTEM = (
    "You are the request stage of an evidence-based data-discovery tool. "
    "You receive one business question, the vocabulary of the domain "
    "(business objects, their fields, and what each one means) and the "
    "answer types the domain declares. You have never seen the data.\n\n"
    "Do two things. State in one line what output the answer must deliver. "
    "Then classify the question: name the one answer type it belongs to, or "
    "null if none fits.\n\n"
    "Guidance:\n"
    "- The classification is the important part. Each answer type already "
    "lists what an answer of that family depends on, reviewed by a human, "
    "so naming the right one is worth far more than any list you could "
    "write.\n"
    "- Never force a fit. An answer type whose definition does not cover "
    "the question is the wrong one, and null is the honest answer — it "
    "costs the reader a review, while a wrong type costs them the truth.\n"
    "- required_knowledge is only the DELTA. Leave it empty when the answer "
    "type covers the question. List an item when the question asks for "
    "something the type does not carry, or fill the whole list when "
    "answer_type is null.\n"
    "- The question BOUNDS the work. List what the answer genuinely rests "
    "on and nothing else: an item nobody needs costs a human a question.\n"
    "- kind=object and kind=field must name entries of the supplied "
    "vocabulary, spelled exactly; a field also names its object in "
    "of_object.\n"
    "- kind=rule is for what the vocabulary does NOT contain: a business "
    "rule, convention or policy the answer depends on and that no column "
    "layout reveals — sign conventions, inclusion rules, cut-off rules. "
    "Name it in short business words; leave of_object empty.\n"
    "- Every item needs a 'why' that a business reader can prune on: what "
    "goes wrong in the answer if this is unknown.\n"
    "- Fill scope only when the question names one (a specific entity, "
    "period or segment). A grouping the answer must break out by is part "
    "of requested_output, not a scope.\n"
    "- You decide nothing here. Everything you name will be checked "
    "against measured evidence, or put to a human for confirmation."
)

V3_SYSTEM = (
    "You are the document stage of an evidence-based data-discovery tool. "
    "You receive passages from one document, each with an id, and a list "
    "of open questions the project is trying to settle. You have never "
    "seen the data itself.\n\n"
    "Report the passages that carry something the project needs. For each, "
    "quote the exact words from the passage and say what they assert.\n\n"
    "Guidance:\n"
    "- Quote VERBATIM. The quote is checked character by character against "
    "the passage you cite; a paraphrase is rejected, and so is a quote "
    "attributed to the wrong passage id.\n"
    "- reads_as=definition is for a stated rule, convention or policy — "
    "what something means, how it is booked, which items are included. "
    "Give the term and the definition in the document's own terms.\n"
    "- reads_as=figure is for a stated number. Quote the sentence or row "
    "that carries it, and put the number itself in 'value', written "
    "exactly as the document writes it (grouping separators and all). "
    "Sentences carry several numbers and only you can tell which one the "
    "statement is about; the one you name is checked against the quote.\n"
    "- Set 'answers' to the open question this passage settles, spelled "
    "exactly as listed, or null. Only claim it when the passage really "
    "states that rule; a wrong link is worse than none.\n"
    "- Report nothing for passages that carry no rule and no figure "
    "relevant to the open questions. A document may yield nothing, and "
    "saying so is a correct answer.\n"
    "- Do not judge whether a figure is trustworthy or whether it agrees "
    "with anything. Where the passage sits on the page and what its "
    "number corroborates are determined outside this call.\n"
    "- You confirm nothing. Everything you report enters as a proposal "
    "with a pointer to where you read it."
)

V2_ROLES_SYSTEM = V2_SYSTEM + (
    "\n\nThe claims in this batch are role bindings: each asserts that "
    "specific views/columns play a domain role. A role binding IS "
    "falsifiable — by instantiating the conservation law implied by the "
    "role's definition against the bound columns (its admissible "
    "templates are the invariant checks). A binding whose invariant holds "
    "is supported; one whose invariant fails is refuted — that is how "
    "competing candidates for the same role are decided. Bind each "
    "role-binding claim to the invariant template its role definition "
    "implies, taking params from the claim's binding; answer "
    "template=null only when the role's definition genuinely implies no "
    "testable invariant.\n\n"
    "Some invariants are relations and need more views than the claim "
    "you are binding names on its own — a symmetry law compares two "
    "sides against each other, a subledger law compares a subledger "
    "against the ledger it belongs to. Where that is so, take the "
    "missing params from the OTHER role-binding claims in this batch, "
    "or from the view schemas above, and name in the rationale where "
    "each side came from. template=null is for a role whose definition "
    "implies no testable invariant — not for one whose invariant needs "
    "a counterpart that is in front of you."
)
