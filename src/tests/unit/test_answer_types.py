"""Answer types: the reviewed dependency list, and why a broken one must not load.

An answer type names what an answer to one family of questions depends on.
The model classifies a question to a type; the engine expands the type. The
whole point is that the list is no longer invented per question — so the one
failure this schema may never survive is a **dead reference**, which would
expand to a silently *shorter* list. That is a load error, not a skip.
"""

import pytest

from before_we_ai.llm.domain_guide import (
    DomainGuide,
    load_domain_guide,
    short_fingerprint,
)

pytestmark = pytest.mark.unit


def _guide(answer_types: dict) -> DomainGuide:
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
        answer_types=answer_types,
    )


_ONE_TYPE = {
    "profit_and_loss": {
        "definition": "the result of a period, by whatever dimension is asked",
        "requires": [
            {"object": "journal"},
            {"field": "journal.amount_local"},
            {"field": "journal.entity", "why": "the answer is broken out by it"},
            {"rule": "which accounts are profit and loss"},
        ],
    },
}


class TestTheShape:
    def test_a_requirement_names_exactly_one_thing(self):
        with pytest.raises(ValueError, match="exactly one"):
            _guide({"t": {"definition": "d",
                          "requires": [{"object": "journal",
                                        "rule": "some rule"}]}})

    def test_a_requirement_naming_nothing_is_refused(self):
        with pytest.raises(ValueError, match="exactly one"):
            _guide({"t": {"definition": "d", "requires": [{"why": "because"}]}})

    def test_kind_and_ref_read_the_one_that_was_given(self):
        guide = _guide(_ONE_TYPE)
        requires = guide.answer_types["profit_and_loss"].requires
        assert [(r.kind, r.ref) for r in requires] == [
            ("object", "journal"),
            ("field", "journal.amount_local"),
            ("field", "journal.entity"),
            ("rule", "which accounts are profit and loss"),
        ]


class TestABrokenContractDoesNotLoad:
    def test_an_unknown_object_refuses_to_load(self):
        with pytest.raises(ValueError, match="no business object"):
            _guide({"t": {"definition": "d",
                          "requires": [{"object": "ledger"}]}})

    def test_an_unknown_field_refuses_to_load(self):
        with pytest.raises(ValueError, match="no field of 'journal'"):
            _guide({"t": {"definition": "d",
                          "requires": [{"field": "journal.currency"}]}})

    def test_a_field_of_an_unknown_object_refuses_to_load(self):
        with pytest.raises(ValueError, match="names no business object"):
            _guide({"t": {"definition": "d",
                          "requires": [{"field": "ledger.amount"}]}})

    def test_a_field_must_be_addressed_object_dot_field(self):
        with pytest.raises(ValueError, match="object.field"):
            _guide({"t": {"definition": "d",
                          "requires": [{"field": "amount_local"}]}})

    def test_a_rule_may_not_shadow_a_vocabulary_entry(self):
        with pytest.raises(ValueError, match="names a guide entry"):
            _guide({"t": {"definition": "d",
                          "requires": [{"rule": "journal"}]}})
        with pytest.raises(ValueError, match="names a guide entry"):
            _guide({"t": {"definition": "d",
                          "requires": [{"rule": "entity"}]}})

    def test_a_rule_the_vocabulary_does_not_have_is_the_normal_case(self):
        guide = _guide({"t": {"definition": "d",
                              "requires": [{"rule": "sign convention"}]}})
        assert guide.answer_types["t"].requires[0].ref == "sign convention"

    def test_requiring_nothing_is_refused(self):
        with pytest.raises(ValueError, match="requires nothing"):
            _guide({"t": {"definition": "d", "requires": []}})

    def test_requiring_the_same_thing_twice_is_refused(self):
        with pytest.raises(ValueError, match="required twice"):
            _guide({"t": {"definition": "d",
                          "requires": [{"object": "journal"},
                                       {"object": "journal"}]}})

    def test_an_answer_type_may_not_take_an_entry_name(self):
        with pytest.raises(ValueError, match="already taken"):
            _guide({"journal": {"definition": "d",
                                "requires": [{"object": "journal"}]}})

    def test_every_error_of_a_broken_guide_is_reported_at_once(self):
        with pytest.raises(ValueError) as caught:
            _guide({"t": {"definition": "d",
                          "requires": [{"object": "ledger"},
                                       {"field": "journal.currency"}]}})
        assert "ledger" in str(caught.value)
        assert "currency" in str(caught.value)


class TestAGuideWithoutAnswerTypes:
    def test_stays_valid_because_the_fallback_still_exists(self):
        assert _guide({}).answer_types == {}


class TestTheFingerprint:
    def test_a_guide_loaded_twice_fingerprints_the_same(self, tmp_path):
        path = tmp_path / "guide.yaml"
        path.write_text(_YAML, encoding="utf-8")
        assert load_domain_guide(path).fingerprint == \
            load_domain_guide(path).fingerprint

    def test_one_changed_byte_changes_it(self, tmp_path):
        path = tmp_path / "guide.yaml"
        path.write_text(_YAML, encoding="utf-8")
        before = load_domain_guide(path).fingerprint
        path.write_text(_YAML.replace("the ledger", "the ledger of record"),
                        encoding="utf-8")
        assert load_domain_guide(path).fingerprint != before

    def test_a_guide_built_in_memory_has_none_to_record(self):
        assert _guide(_ONE_TYPE).fingerprint == ""

    def test_the_display_form_is_short_enough_to_read(self, tmp_path):
        path = tmp_path / "guide.yaml"
        path.write_text(_YAML, encoding="utf-8")
        guide = load_domain_guide(path)
        assert short_fingerprint(guide.fingerprint) == guide.fingerprint[:12]
        assert len(short_fingerprint(guide.fingerprint)) == 12


_YAML = """\
domain: finance
objects:
  journal:
    decided_by: balance
    definition: the ledger
    fields:
      amount_local:
        decided_by: slot
        fills: amount
        definition: the signed amount
answer_types:
  profit_and_loss:
    definition: the result of a period
    requires:
      - object: journal
      - field: journal.amount_local
      - rule: which accounts are profit and loss
"""
