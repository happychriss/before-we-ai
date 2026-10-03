"""Expanding an answer type: same input, same list, every time.

The determinism is the safety property. A list that is recomputed on every
read cannot go stale against the guide it came from — but only if the
recomputation is a pure function of the answer type and the guide.
"""

import pytest

from before_we_ai.core import KnowledgeKind, Provenance, Scope
from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.readiness.expand import UnknownAnswerType, expand

pytestmark = pytest.mark.unit


@pytest.fixture
def guide() -> DomainGuide:
    return DomainGuide(
        domain="finance",
        objects={
            "journal": {
                "definition": "the ledger of record",
                "decided_by": "balance",
                "fields": {
                    "amount_local": {"definition": "the signed amount",
                                     "decided_by": "slot", "fills": "amount"},
                    "entity": {"definition": "the legal entity",
                               "decided_by": "clarification"},
                },
            },
        },
        answer_types={
            "profit_and_loss": {
                "definition": "the result of a period",
                "requires": [
                    {"object": "journal"},
                    {"field": "journal.amount_local"},
                    {"field": "journal.entity",
                     "why": "the answer is broken out by it"},
                    {"rule": "which accounts are profit and loss"},
                ],
            },
        },
    )


class TestTheExpansion:
    def test_it_produces_one_item_per_requirement_in_guide_order(self, guide):
        items = expand("profit_and_loss", guide, Scope())
        assert [(i.kind, i.ref()) for i in items] == [
            (KnowledgeKind.OBJECT, "journal"),
            (KnowledgeKind.FIELD, "journal.amount_local"),
            (KnowledgeKind.FIELD, "journal.entity"),
            (KnowledgeKind.RULE, "which accounts are profit and loss"),
        ]

    def test_the_same_input_expands_to_the_same_list(self, guide):
        scope = Scope(entity="DE")
        assert expand("profit_and_loss", guide, scope) == \
            expand("profit_and_loss", guide, scope)

    def test_a_field_is_split_into_its_object_and_its_name(self, guide):
        field = expand("profit_and_loss", guide, Scope())[1]
        assert (field.of_object, field.name) == ("journal", "amount_local")

    def test_the_guides_reason_is_carried_and_is_not_the_models(self, guide):
        entity = expand("profit_and_loss", guide, Scope())[2]
        assert entity.why == "the answer is broken out by it"

    def test_every_expanded_item_is_marked_as_coming_from_the_contract(self, guide):
        assert all(i.provenance is Provenance.CONTRACT
                   for i in expand("profit_and_loss", guide, Scope()))


class TestScope:
    def test_objects_and_fields_inherit_the_requests_scope(self, guide):
        items = expand("profit_and_loss", guide, Scope(entity="DE"))
        assert [i.scope.label() for i in items[:3]] == ["entity DE"] * 3

    def test_a_rule_carries_no_scope_because_it_selects_among_nothing(self, guide):
        rule = expand("profit_and_loss", guide, Scope(entity="DE"))[3]
        assert rule.scope.is_explicit() is False


class TestAnUnknownType:
    def test_it_raises_rather_than_expanding_to_nothing(self, guide):
        with pytest.raises(UnknownAnswerType, match="balance_sheet"):
            expand("balance_sheet", guide, Scope())

    def test_the_error_names_what_the_guide_does_have(self, guide):
        with pytest.raises(UnknownAnswerType, match="profit_and_loss"):
            expand("balance_sheet", guide, Scope())
