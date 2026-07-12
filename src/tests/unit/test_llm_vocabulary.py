"""The controlled vocabulary is locked to the probe library and the schemas
reject anything outside it — this is what keeps LLM output dedupable and
bindable without trusting the model."""

from typing import get_args

import pytest
from pydantic import ValidationError

from before_we_ai.llm.schemas import (
    BindingBatch,
    Hypothesis,
    HypothesisBatch,
    ProbeBinding,
    RoleBindingProposal,
)
from before_we_ai.llm.vocabulary import (
    COLUMN_PARAMS,
    INVARIANT_TEMPLATES,
    PREDICATES,
    PredicateName,
    TEMPLATE_PARAMS,
    TemplateName,
    check_template_params,
)
from before_we_ai.probes.library import REGISTRY


def test_template_params_mirror_the_registry_exactly():
    assert set(TEMPLATE_PARAMS) == set(REGISTRY)


def test_every_predicate_template_is_a_registry_key():
    for name, spec in PREDICATES.items():
        for template in spec.templates:
            assert template in REGISTRY, f"{name} points at unknown template {template}"


def test_invariant_templates_are_registry_keys():
    assert set(INVARIANT_TEMPLATES) <= set(REGISTRY)


def test_domain_specific_templates_are_explicitly_tagged():
    # The product is a general machine only together with a domain pack —
    # what is domain-specific must be enumerable, never implicit. Today
    # that is exactly the three finance invariants; a new domain-tagged
    # template must consciously extend this lock.
    tagged = {name for name, spec in REGISTRY.items() if spec.domain}
    assert tagged == set(INVARIANT_TEMPLATES)
    assert {REGISTRY[name].domain for name in tagged} == {"finance"}


def test_column_params_cover_the_registry_and_name_real_params():
    assert set(COLUMN_PARAMS) == set(REGISTRY)
    for template, pairs in COLUMN_PARAMS.items():
        allowed = TEMPLATE_PARAMS[template].allowed
        for column_param, view_param in pairs:
            assert column_param in allowed, (template, column_param)
            assert view_param in allowed, (template, view_param)


def test_literals_agree_with_runtime_tables():
    assert set(get_args(PredicateName)) == set(PREDICATES)
    assert set(get_args(TemplateName)) == set(REGISTRY)


def _hypothesis(**overrides) -> dict:
    base = {
        "statement": "every invoice references a customer",
        "predicate": "references",
        "params": {"child": "a.customer_id", "parent": "b.customer_id"},
        "columns": ["a.customer_id", "b.customer_id"],
        "rationale": "full containment in the candidate matrix",
    }
    return {**base, **overrides}


def test_free_form_predicate_is_rejected():
    with pytest.raises(ValidationError):
        Hypothesis.model_validate(_hypothesis(predicate="is_probably_a_key"))


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        Hypothesis.model_validate(_hypothesis(confidence=0.9))
    with pytest.raises(ValidationError):
        HypothesisBatch.model_validate(
            {"hypotheses": [], "commentary": "great dataset!"}
        )


def test_cross_field_rules_are_semantic_not_schema():
    """Item-level cross-field consistency must NOT fail schema validation —
    a schema failure kills the whole batch, and one item may never sink it
    (learned from the first real run). The rules live in mapping.check_*."""
    incomplete_concept = Hypothesis.model_validate(_hypothesis(kind="concept"))
    assert incomplete_concept.term is None  # schema-valid; semantically skipped
    no_reason = ProbeBinding.model_validate({"claim_id": "c1", "template": None})
    assert no_reason.no_template_reason is None
    empty_binding = RoleBindingProposal.model_validate(
        {"role": "journal", "binding": {}, "rationale": "?"}
    )
    assert empty_binding.binding == {}


def test_unknown_template_is_rejected():
    with pytest.raises(ValidationError):
        ProbeBinding.model_validate(
            {"claim_id": "c1", "template": "clever_new_probe", "params": {}}
        )


def test_valid_none_binding_round_trips():
    ok = ProbeBinding.model_validate(
        {"claim_id": "c1", "template": None,
         "no_template_reason": "semantic-only relationship"}
    )
    assert ok.template is None
    BindingBatch.model_validate({"bindings": [ok.model_dump()]})


def test_check_template_params_missing_unknown_and_choice():
    assert check_template_params("anti_join", {
        "child": "a", "parent": "b", "child_column": "x", "parent_column": "y",
    }) == []
    errors = check_template_params("anti_join", {"child": "a", "typo": 1})
    assert any("missing required param 'parent'" in e for e in errors)
    assert any("unknown param 'typo'" in e for e in errors)
    # balance: exactly one of group_column/group_expr
    assert check_template_params(
        "balance", {"journal": "j", "amount": "a", "group_column": "g"}
    ) == []
    both = check_template_params(
        "balance",
        {"journal": "j", "amount": "a", "group_column": "g", "group_expr": "e"},
    )
    assert any("exactly one of" in e for e in both)
    neither = check_template_params("balance", {"journal": "j", "amount": "a"})
    assert any("exactly one of" in e for e in neither)
    assert check_template_params("no_such_template", {}) == [
        "unknown template 'no_such_template'"
    ]


def test_check_template_params_value_shapes():
    """Params the prepare functions iterate must be lists with sane items —
    a scalar would crash the engine sweep (seen in the first real run)."""
    scalar = check_template_params("subledger_equals_gl", {
        "subledger": "a", "subledger_amount": "x", "journal": "b",
        "journal_amount": "y", "account": "k",
        "accounts": "de_erp__chart_of_accounts",
    })
    assert any("'accounts' must be a list" in e for e in scalar)
    not_numbers = check_template_params("subledger_equals_gl", {
        "subledger": "a", "subledger_amount": "x", "journal": "b",
        "journal_amount": "y", "account": "k", "accounts": ["1200", "abc"],
    })
    assert any("account numbers (integers), got 'abc'" in e for e in not_numbers)
    scalar_keys = check_template_params("duplicate",
                                        {"table": "t", "key_columns": "id"})
    assert any("'key_columns' must be a list" in e for e in scalar_keys)
    # expression params are row-level; the templates aggregate for themselves
    nested = check_template_params("reconciliation", {
        "left": "a", "right": "b",
        "left_group_expr": "doc_ref", "right_group_expr": "doc_no",
        "left_measure_expr": "sum(amount)", "right_measure_expr": "amount",
    })
    assert any("row-level expression" in e and "'left_measure_expr'" in e
               for e in nested)
    # identifier params must be bare identifiers, never expressions
    expression = check_template_params("balance", {
        "journal": "j", "amount": "sum(amount_local)", "group_column": "doc",
    })
    assert any("bare view/column identifier" in e for e in expression)
