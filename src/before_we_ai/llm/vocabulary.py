"""The controlled predicate vocabulary — the bridge from language to identity.

An LLM hypothesis becomes a claim only through a predicate from this
closed set: free-form predicate names fail schema validation (one retry,
then skip). This is what makes ``semantics.claim_key`` work for AI-born
claims — the same rule proposed twice, worded differently, lands on one
claim.

Two tables anchor the set to the check library:

* ``PREDICATES`` — per predicate: which templates may test it (empty for
  the two LLM-only forms) and which hypothesis param keys are allowed.
* ``TEMPLATE_PARAMS`` — per template: the param keys its ``prepare``
  function reads. Mirrors ``checks.library`` and is locked against drift
  by a unit test.
"""

import re
from dataclasses import dataclass
from typing import Literal, get_args

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

    templates: tuple[str, ...]  # admissible check definitions; () = LLM-only
    required_params: frozenset[str]
    optional_params: frozenset[str] = frozenset()

    @property
    def allowed_params(self) -> frozenset[str]:
        return self.required_params | self.optional_params


def _spec(templates: tuple[str, ...], required: set[str],
          optional: set[str] | None = None) -> PredicateSpec:
    return PredicateSpec(templates, frozenset(required), frozenset(optional or ()))


# Hypothesis params reference columns as "view.column" and views by their
# catalog name — they describe the RULE, not check mechanics (measure
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
    # proposed until a human or a document weighs in
    "semantic_equivalent": _spec((), {"left", "right"}),
    # a business concept/definition (carried by a ConceptClaim)
    "concept_definition": _spec((), set(), {"term"}),
}

# The invariant templates are bound to roles (MappingClaims), not to
# ordinary hypothesis claims — V2 splits on this.
INVARIANT_TEMPLATES: tuple[str, ...] = ("balance", "subledger_equals_gl", "ic_symmetry")

# What a role binding may be tested by — wider than the invariants since
# 2026-08-02 (kickoff item 3). V2's own refusals had been asking for this
# ("account role implies a referential-integrity invariant (anti_join),
# not any admissible finance invariant"): a role no domain law can reach
# may still have a data property worth testing.
#
# Widening the menu is only safe because of the asymmetry the owner
# decided the same day: a generic check over a role can **refute** the
# binding but never establish it (`core.transitions.establishing`).
# Orphaned account ids prove a column is not the account; full coverage
# proves nothing about meaning — measured, all three corpus candidates
# cover fully, the decoy included. Wide menu, narrow promotion boundary,
# rather than the other way round.
ROLE_TEMPLATES: tuple[str, ...] = tuple(sorted(get_args(TemplateName)))

# Predicate name assigned by the mapping layer to MappingClaims. Not
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


# Mirrors the _prep_* functions in checks/library.py, key for key.
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

# What each list param's elements ARE, which is what lets a *lone element*
# be told apart from a value of the wrong shape entirely. One item written
# without its brackets is unambiguous — `accounts: "1200"` can only mean the
# one account — and reading it as intended is the same deterministic
# leniency the view/column corrections already apply.
#
# The distinction earns its keep on `pairs`, whose elements are objects: a
# lone `{part_expr, decode_column}` is one pair and wraps, a bare string is
# not a pair at all and is refused as before. Wrapping by type rather than
# by "it isn't a list" is what stops a nonsense value from being promoted
# into a well-formed-looking one.
_LIST_ELEMENT: dict[str, tuple[type, ...]] = {
    "key_columns": (str,),
    "expected": (str, int, float),
    "accounts": (str, int),
    "pairs": (dict,),
}

# Params whose values are DATA rather than identifiers, each said in the
# words the model reads (rendered per template into the V2 docs).
#
# Found by the owner reading the store, 2026-08-02, and the fault was ours.
# The template docs ended with one global sentence — "param values are bare
# view/column identifiers unless the param name says expression or filter"
# — and these three are neither `*_expr` nor `*where`, so by our own stated
# rule they had to be identifiers. The model complied exactly:
# `accounts: "de_erp__chart_of_accounts"` and
# `expected: "de_erp__chart_of_accounts.account_range_group"`. That is four
# of the five rejected bindings on the corpus, including all three
# `subledger_equals_gl` ones — so the only law that can settle a
# receivables object never ran, and the reason was a sentence of ours that
# was wrong for three params out of forty.
#
# Stated per param, not as prose in a note, because a rule with exceptions
# has to enumerate them where the exception is used.
VALUE_PARAMS: dict[str, str] = {
    "accounts": (
        "the account NUMBERS that make up the general-ledger side, as a list "
        "of integers, e.g. [1200] — NOT the chart-of-accounts view. Which "
        "numbers those are is domain knowledge; if the profiles do not tell "
        "you, answer template: null and say so"
    ),
    "expected": (
        "the VALUES that must all appear in unit_column, as a list, e.g. "
        "[\"DE\", \"US\"] — NOT the column or view they live in"
    ),
    "pairs": (
        "a list of {part_expr, decode_column} objects, not identifiers"
    ),
}

# The templates aggregate for themselves (e.g. reconciliation wraps every
# measure in SUM); an expression param carrying its own aggregate renders
# into nested aggregates and crashes the sweep.
_AGGREGATES = ("sum(", "count(", "avg(", "min(", "max(")

_IDENTIFIER = re.compile(r"\w+")

# Param names that must name a catalog view.
# The one predicate that makes a hypothesis a concept claim. A
# hypothesis's kind is derived from this and never asked for.
CONCEPT_PREDICATE = "concept_definition"

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

# The two sides of a two-sided check, as the params that make each side up.
#
# A law that relates two sides tests nothing when both sides are the same
# rows read the same way: `ic_symmetry` compares a view's leg counts to its
# own and finds no difference, `reconciliation` sums identical rows twice
# and finds no gap. They **pass**, and a passing domain law elects the
# candidate that carries it — so this is a false-promotion path, not a
# cosmetic slip. Nothing else catches it: every param is individually
# valid, every view exists, every column is real.
#
# Compared as tuples rather than by view alone, because two sides of one
# view is a legitimate check — "these two columns of the same export must
# agree" — and only sides identical in *every* distinguishing param are
# self-comparisons. `decode` shares its `key` param, so its sides differ
# exactly when its two views do.
TWO_SIDED: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "ic_symmetry": (("left", "left_period"), ("right", "right_period")),
    "reconciliation": (
        ("left", "left_group_expr", "left_measure_expr", "left_where"),
        ("right", "right_group_expr", "right_measure_expr", "right_where"),
    ),
    "attribute_contradiction": (("left", "left_key", "left_attr"),
                                ("right", "right_key", "right_attr")),
    "anti_join": (("child", "child_column"), ("parent", "parent_column")),
    "cardinality": (("child", "child_column"), ("parent", "parent_column")),
    "decode": (("encoded", "key"), ("decode", "key")),
    "subledger_equals_gl": (("subledger", "subledger_amount"),
                            ("journal", "journal_amount")),
}

def _required(template: str) -> frozenset:
    contract = TEMPLATE_PARAMS.get(template)
    return contract.required if contract else frozenset()


def _view_heads(value, views: set) -> list[str]:
    """The known views named by a (possibly qualified) param value."""
    candidates = value if isinstance(value, list) else [value]
    heads = []
    for item in candidates:
        if isinstance(item, str) and "." in item:
            head = item.split(".", 1)[0]
            if head in views:
                heads.append(head)
    return heads


def normalize_template_params(template: str, params: dict,
                              known_views=()) -> tuple[dict, list[dict]]:
    """Deterministic normalization of unambiguous formatting variants.

    Three of them, each an owner decision (2026-08-02) rather than a
    tidy-up:

    * a **column** param qualified with exactly its own view
      (``view.column``) reduces to the bare column;
    * a **view** param that names a column of a real view
      (``de_erp__gl_postings.account_id`` where a view belongs) reduces to
      that view. Six of the seven V2 skips in the walkthrough are this one
      shape, and it cascades: the column params anchor on the view param,
      so a qualified view param leaves them with nothing to strip.
    * a **list param given one element** (``accounts: "1200"``) becomes the
      one-item list it can only have meant — but only when the value is of
      the type that list holds, so a bare string where objects belong is
      still a confusion and still refused.

    Leniency here has a cost the owner weighed explicitly. A binding the
    model may have misunderstood now *runs*, and a passing run promotes —
    which is the too-loose-law failure in miniature. So every correction is
    **returned**, and the caller records it: the run happens, and a reader
    can still see that we read something other than what was written.

    Returns ``(normalized_params, corrections)``.
    """
    normalized = dict(params)
    corrections: list[dict] = []

    def correct(param: str, before, after) -> None:
        normalized[param] = after
        corrections.append({"param": param, "given": before, "read_as": after})

    # VIEW_PARAMS is the set of param NAMES that must hold a bare view,
    # shared by every template — not a per-template mapping.
    views = set(known_views)

    # A lone element where a list belongs. First, because the corrections
    # below have a list branch, and a scalar written as `view.column` needs
    # to be a list before that branch can reach it.
    #
    # This one was found by the owner reading the store, not by a test:
    # `accounts: "1200"` cost all three `subledger_equals_gl` bindings on
    # the corpus, so the AR-to-GL reconciliation — the only law that can
    # settle the receivables object at all — never ran once. Nothing was
    # wrong with the binding; one pair of brackets was missing from it.
    for param in _LIST_PARAMS:
        value = normalized.get(param)
        if param not in normalized or isinstance(value, list):
            continue
        elements = _LIST_ELEMENT[param]
        if isinstance(value, bool) or not isinstance(value, elements):
            continue  # not a lone element either — refused downstream
        correct(param, value, [value])

    # An absent view param, recovered from the columns that name it. The
    # model writes `amount: de_erp__gl_postings.amount_local_currency` and
    # then leaves `journal` out — and because the column normalization
    # anchors on the view param, one omission takes every column with it.
    # The information is unambiguously there: the qualified columns name
    # the view. Recovering it is deterministic and **requires unanimity**;
    # where the columns disagree about which view they sit on, that is a
    # confusion to report, not a majority to follow (owner decision
    # 2026-08-02, the second of two — flexibility, with every case on the
    # record).
    for column_param, view_param in COLUMN_PARAMS.get(template, ()):
        if normalized.get(view_param) or view_param not in _required(template):
            continue
        named = {
            head for param, owner in COLUMN_PARAMS.get(template, ())
            if owner == view_param
            for head in _view_heads(normalized.get(param), views)
        }
        if len(named) == 1:
            correct(view_param, None, named.pop())

    for view_param in sorted(VIEW_PARAMS & set(normalized)):
        value = normalized.get(view_param)
        if not isinstance(value, str) or value in views or "." not in value:
            continue
        head = value.split(".", 1)[0]
        if head in views:
            correct(view_param, value, head)

    for column_param, view_param in COLUMN_PARAMS.get(template, ()):
        view = normalized.get(view_param)
        value = normalized.get(column_param)
        if not isinstance(view, str):
            continue
        prefix = view + "."
        if isinstance(value, str) and value.startswith(prefix):
            correct(column_param, value, value[len(prefix):])
        elif isinstance(value, list) and any(
            isinstance(v, str) and v.startswith(prefix) for v in value
        ):
            correct(column_param, list(value), [
                v[len(prefix):] if isinstance(v, str) and v.startswith(prefix) else v
                for v in value
            ])
    return normalized, corrections


# Free-text contract notes rendered into the V2 template docs — the model
# reads these; keep them generic.
TEMPLATE_NOTES: dict[str, str] = {
    "reconciliation": ("group/measure params are row-level SQL expressions "
                       "over the named view; the template applies SUM itself "
                       "— never pre-aggregate. This one differs from balance "
                       "and subledger_equals_gl on purpose: a measure here "
                       "may be any row-level arithmetic, so the template "
                       "cannot know which column carries the number and "
                       "cannot convert it for you. Check the column types in "
                       "the view schemas: text-typed numeric columns must be "
                       "cast in the expression, e.g. CAST(col AS DOUBLE)"),
    "balance": ("amount is a BARE COLUMN NAME, never an expression — the "
                "template reads it as a number and sums it itself, so a "
                "text-typed amount column needs no cast from you; "
                "group_expr, if used, is a row-level expression"),
    "subledger_equals_gl": ("subledger_amount and journal_amount are BARE "
                            "COLUMN NAMES, never expressions — the template "
                            "reads each as a number and sums it itself, so a "
                            "text-typed amount column needs no cast from you. "
                            "`account` and `accounts` are different kinds of "
                            "thing and easy to swap: `account` is the COLUMN "
                            "on the journal carrying the account identifier, "
                            "`accounts` the account numbers to filter it to"),
}


def _self_comparison(template: str, params: dict) -> list[str]:
    """Refuse a two-sided check whose two sides are the same thing.

    The verdict such a check produces is PASS, and it is not a measurement
    of anything — the rows are compared to themselves. On a domain law that
    PASS elects the candidate, which makes this the cheapest false
    promotion available and the only one no other validation sees.
    """
    sides = TWO_SIDED.get(template)
    if sides is None:
        return []
    left, right = ([params.get(name) for name in side] for side in sides)
    if left != right:
        return []
    named = " and ".join(f"{a}/{b}" for a, b in zip(*sides))
    return [
        f"template {template!r}: {named} are identical, so this check "
        f"would compare rows to themselves and pass without testing "
        f"anything. Name the two sides it is meant to relate."
    ]


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
    errors += _self_comparison(template, params)
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
