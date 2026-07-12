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


def test_concept_requires_term_and_definition():
    with pytest.raises(ValidationError):
        Hypothesis.model_validate(_hypothesis(kind="concept"))
    ok = Hypothesis.model_validate(
        _hypothesis(kind="concept", predicate="concept_definition", params={},
                    term="revenue", definition="external revenue accounts only")
    )
    assert ok.term == "revenue"


def test_unknown_template_is_rejected():
    with pytest.raises(ValidationError):
        ProbeBinding.model_validate(
            {"claim_id": "c1", "template": "clever_new_probe", "params": {}}
        )


def test_no_template_requires_a_reason_and_vice_versa():
    with pytest.raises(ValidationError):
        ProbeBinding.model_validate({"claim_id": "c1", "template": None})
    with pytest.raises(ValidationError):
        ProbeBinding.model_validate(
            {"claim_id": "c1", "template": "anti_join",
             "params": {}, "no_template_reason": "just in case"}
        )
    ok = ProbeBinding.model_validate(
        {"claim_id": "c1", "template": None,
         "no_template_reason": "semantic-only relationship"}
    )
    assert ok.template is None
    BindingBatch.model_validate({"bindings": [ok.model_dump()]})


def test_role_binding_must_bind_something():
    with pytest.raises(ValidationError):
        RoleBindingProposal.model_validate(
            {"role": "journal", "binding": {}, "rationale": "?"}
        )


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
