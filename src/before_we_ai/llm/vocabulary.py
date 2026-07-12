"""The controlled predicate vocabulary — the bridge from language to identity.

An LLM hypothesis becomes a claim only through a predicate from this
closed set: free-form predicate names fail schema validation (one retry,
then skip). This is what makes ``semantics.claim_key`` work for AI-born
claims — the same rule proposed twice, worded differently, lands on one
claim.

Two tables anchor the set to the probe library:

* ``PREDICATES`` — per predicate: which templates may test it (empty for
  the two LLM-only forms) and which hypothesis param keys are allowed.
* ``TEMPLATE_PARAMS`` — per template: the param keys its ``prepare``
  function reads. Mirrors ``probes.library`` and is locked against drift
  by a unit test.
"""

import re
from dataclasses import dataclass
from typing import Literal

# The closed set, spelled twice: once as a typing.Literal so the output
# schemas reject unknown names at validation time, once as runtime tables.
# A unit test asserts both spellings agree.
PredicateName = Literal[
    "references",
    "unique_key",
    "covers",
    "consistent_attribute",
    "reconciles",
    "temporal_validity",
    "range_mapping",
    "decodes",
    "balances",
    "subledger_equals_gl",
    "ic_symmetric",
    "semantic_equivalent",
    "concept_definition",
]

TemplateName = Literal[
    "anti_join",
    "duplicate",
    "grain",
    "coverage",
    "cardinality",
    "attribute_contradiction",
    "reconciliation",
    "validity_join",
    "range_join",
    "decode",
    "balance",
    "subledger_equals_gl",
    "ic_symmetry",
]


@dataclass(frozen=True)
class PredicateSpec:
    """What a predicate means operationally: testable-by and param contract."""

    templates: tuple[str, ...]  # admissible probe templates; () = LLM-only
    required_params: frozenset[str]
    optional_params: frozenset[str] = frozenset()

    @property
    def allowed_params(self) -> frozenset[str]:
        return self.required_params | self.optional_params


def _spec(templates: tuple[str, ...], required: set[str],
          optional: set[str] | None = None) -> PredicateSpec:
    return PredicateSpec(templates, frozenset(required), frozenset(optional or ()))


# Hypothesis params reference columns as "view.column" and views by their
# catalog name — they describe the RULE, not probe mechanics (measure
# expressions, SQL snippets and the like are V2/engine territory).
PREDICATES: dict[str, PredicateSpec] = {
    # child rows reference parent rows (FK/containment)
    "references": _spec(("anti_join", "cardinality"),
                        {"child", "parent"}, {"expectation"}),
    # the listed columns identify a row (grain/duplicate freedom)
    "unique_key": _spec(("duplicate", "grain"), {"table", "key_columns"}),
    # a table covers an expected set of units (entities, periods, ...)
    "covers": _spec(("coverage",), {"table", "unit_column", "expected"}),
    # two linked tables agree on an attribute
    "consistent_attribute": _spec(
        ("attribute_contradiction",),
        {"left_key", "right_key", "left_attr", "right_attr"},
    ),
    # two tables reconcile on a grouped measure
    "reconciles": _spec(
        ("reconciliation",),
        {"left", "right"},
        {"left_group", "right_group", "left_measure", "right_measure",
         "left_where", "right_where"},
    ),
    # versioned rows have non-overlapping validity per key
    "temporal_validity": _spec(("validity_join",),
                               {"table", "key_column", "valid_from", "valid_to"}),
    # values map into ranges of a range table (exactly one range each)
    "range_mapping": _spec(("range_join",),
                           {"table", "value_column", "ranges", "range_from", "range_to"},
                           {"where"}),
    # a positional/composite code decodes against a reference table
    "decodes": _spec(("decode",), {"encoded", "decode", "key", "column"}),
    # a journal balances to zero per group (invariant)
    "balances": _spec(("balance",), {"journal", "amount"},
                      {"group_column", "group_expr"}),
    # subledger totals equal the general ledger on control accounts (invariant)
    "subledger_equals_gl": _spec(
        ("subledger_equals_gl",),
        {"subledger", "subledger_amount", "journal", "journal_amount",
         "account", "accounts"},
    ),
    # intercompany postings are symmetric between two entities (invariant)
    "ic_symmetric": _spec(("ic_symmetry",),
                          {"left", "right", "left_period", "right_period"}),
    # two columns/groupings mean the same thing without value overlap —
    # findable only semantically; no template can test it, so it stays
    # inferred until a human or a document weighs in
    "semantic_equivalent": _spec((), {"left", "right"}),
    # a business concept/definition (carried by a ConceptClaim)
    "concept_definition": _spec((), set(), {"term"}),
}

# The invariant templates are bound to roles (RoleBindingClaims), not to
# ordinary hypothesis claims — V2 splits on this.
INVARIANT_TEMPLATES: tuple[str, ...] = ("balance", "subledger_equals_gl", "ic_symmetry")

# Predicate name assigned by the mapping layer to RoleBindingClaims. Not
# part of the hypothesis vocabulary (V1 cannot choose it) — it exists so
# role-binding claims have a claim_key and dedup like everything else.
ROLE_BINDING_PREDICATE = "role_binding"


@dataclass(frozen=True)
class TemplateParams:
    """The param keys a template's ``prepare`` function reads."""

    required: frozenset[str]
    optional: frozenset[str] = frozenset()
    # groups of keys of which exactly one must be present
    exactly_one_of: tuple[frozenset[str], ...] = ()

    @property
    def allowed(self) -> frozenset[str]:
        extra = frozenset().union(*self.exactly_one_of) if self.exactly_one_of else frozenset()
        return self.required | self.optional | extra


def _params(required: set[str], optional: set[str] | None = None,
            exactly_one_of: tuple[set[str], ...] = ()) -> TemplateParams:
    return TemplateParams(
        frozenset(required),
        frozenset(optional or ()),
        tuple(frozenset(g) for g in exactly_one_of),
    )


# Mirrors the _prep_* functions in probes/library.py, key for key.
TEMPLATE_PARAMS: dict[str, TemplateParams] = {
    "anti_join": _params({"child", "parent", "child_column", "parent_column"},
                         {"canonical", "expectation"}),
    "duplicate": _params({"table", "key_columns"}),
    "grain": _params({"table", "key_columns"}),
    "coverage": _params({"table", "unit_column", "expected"}, {"canonical"}),
    "cardinality": _params({"child", "parent", "child_column", "parent_column"}),
    "attribute_contradiction": _params(
        {"left", "right", "left_key", "right_key", "left_attr", "right_attr"},
        {"canonical"},
    ),
    "reconciliation": _params(
        {"left", "right", "left_group_expr", "right_group_expr",
         "left_measure_expr", "right_measure_expr"},
        {"left_where", "right_where"},
    ),
    "validity_join": _params({"table", "key_column", "valid_from", "valid_to"}),
    "range_join": _params({"table", "value_column", "ranges", "range_from", "range_to"},
                          {"where"}),
    "decode": _params({"encoded", "decode", "key", "column", "pairs"}),
    "balance": _params({"journal", "amount"},
                       exactly_one_of=({"group_column", "group_expr"},)),
    "subledger_equals_gl": _params(
        {"subledger", "subledger_amount", "journal", "journal_amount",
         "account", "accounts"},
    ),
    "ic_symmetry": _params({"left", "right", "left_period", "right_period"}),
}


# Params whose values the prepare functions iterate — a scalar here would
# crash the engine sweep, so the shape is part of the binding contract.
_LIST_PARAMS = ("key_columns", "expected", "accounts", "pairs")

# The templates aggregate for themselves (e.g. reconciliation wraps every
# measure in SUM); an expression param carrying its own aggregate renders
# into nested aggregates and crashes the sweep.
_AGGREGATES = ("sum(", "count(", "avg(", "min(", "max(")

_IDENTIFIER = re.compile(r"\w+")

# Param names that must name a catalog view.
VIEW_PARAMS = frozenset({"child", "parent", "table", "left", "right",
                         "encoded", "decode", "ranges", "journal", "subledger"})

# Which bare-column params must exist on which view param — template-level
# referential integrity, checked at binding time so a hallucinated column
# is retry feedback instead of an engine crash.
COLUMN_PARAMS: dict[str, tuple[tuple[str, str], ...]] = {
    "anti_join": (("child_column", "child"), ("parent_column", "parent")),
    "duplicate": (("key_columns", "table"),),
    "grain": (("key_columns", "table"),),
    "coverage": (("unit_column", "table"),),
    "cardinality": (("child_column", "child"), ("parent_column", "parent")),
    "attribute_contradiction": (("left_key", "left"), ("left_attr", "left"),
                                ("right_key", "right"), ("right_attr", "right")),
    "reconciliation": (),
    "validity_join": (("key_column", "table"), ("valid_from", "table"),
                      ("valid_to", "table")),
    "range_join": (("value_column", "table"), ("range_from", "ranges"),
                   ("range_to", "ranges")),
    "decode": (("key", "encoded"), ("key", "decode")),
    "balance": (("amount", "journal"), ("group_column", "journal")),
    "subledger_equals_gl": (("subledger_amount", "subledger"),
                            ("journal_amount", "journal"),
                            ("account", "journal")),
    "ic_symmetry": (("left_period", "left"), ("right_period", "right")),
}

def normalize_template_params(template: str, params: dict) -> dict:
    """Deterministic normalization of an unambiguous formatting variant:
    a column param qualified with exactly its own view ("view.column")
    reduces to the bare column. Anything else is left for the checks —
    lenient in what we accept, strict in what we store."""
    normalized = dict(params)
    for column_param, view_param in COLUMN_PARAMS.get(template, ()):
        view = normalized.get(view_param)
        value = normalized.get(column_param)
        if not isinstance(view, str):
            continue
        prefix = view + "."
        if isinstance(value, str) and value.startswith(prefix):
            normalized[column_param] = value[len(prefix):]
        elif isinstance(value, list):
            normalized[column_param] = [
                v[len(prefix):] if isinstance(v, str) and v.startswith(prefix) else v
                for v in value
            ]
    return normalized


# Free-text contract notes rendered into the V2 template docs — the model
# reads these; keep them generic.
TEMPLATE_NOTES: dict[str, str] = {
    "reconciliation": ("group/measure params are row-level SQL expressions "
                       "over the named view; the template applies SUM itself "
                       "— never pre-aggregate. Check the column types in the "
                       "view schemas: text-typed numeric columns must be cast "
                       "in the expression, e.g. CAST(col AS DOUBLE)"),
    "balance": ("amount is a plain column summed by the template; group_expr, "
                "if used, is a row-level expression"),
}


def check_template_params(template: str, params: dict) -> list[str]:
    """Validate a param dict against a template's contract; returns errors."""
    contract = TEMPLATE_PARAMS.get(template)
    if contract is None:
        return [f"unknown template {template!r}"]
    errors = []
    keys = set(params)
    for missing in sorted(contract.required - keys):
        errors.append(f"template {template!r}: missing required param {missing!r}")
    for group in contract.exactly_one_of:
        hits = sorted(group & keys)
        if len(hits) != 1:
            errors.append(
                f"template {template!r}: exactly one of {sorted(group)} required, "
                f"got {hits or 'none'}"
            )
    for unknown in sorted(keys - contract.allowed):
        errors.append(f"template {template!r}: unknown param {unknown!r}")
    for key in _LIST_PARAMS:
        if key in keys and key in contract.allowed and not isinstance(params[key], list):
            errors.append(
                f"template {template!r}: param {key!r} must be a list, "
                f"got {type(params[key]).__name__}"
            )
    accounts = params.get("accounts")
    if template == "subledger_equals_gl" and isinstance(accounts, list):
        for item in accounts:
            try:
                int(item)
            except (TypeError, ValueError):
                errors.append(
                    f"template {template!r}: 'accounts' must contain account "
                    f"numbers (integers), got {item!r}"
                )
    for key in sorted(keys & contract.allowed):
        value = params[key]
        if not isinstance(value, str):
            continue
        if key.endswith("_expr"):
            lowered = value.lower()
            for aggregate in _AGGREGATES:
                if aggregate in lowered:
                    errors.append(
                        f"template {template!r}: param {key!r} must be a "
                        f"row-level expression — the template aggregates for "
                        f"itself, got {value!r}"
                    )
        elif not key.endswith("where") and not _IDENTIFIER.fullmatch(value):
            errors.append(
                f"template {template!r}: param {key!r} must be a bare "
                f"view/column identifier, got {value!r}"
            )
    return errors
