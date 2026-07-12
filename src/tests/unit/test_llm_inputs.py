"""Input builders: byte-deterministic, order-independent, and any trim is
loud. Plus the prompt-leakage tripwire on the frozen prompt strings."""

import pytest

from before_we_ai.llm import inputs, prompts
from before_we_ai.llm.roles import RoleSet
from before_we_ai.model import Actor, Predicate, create_claim
from before_we_ai.model.objects import ColumnProfile
from before_we_ai.store import ProjectStore, init_project


def _profile(table: str, column: str, **stats) -> ColumnProfile:
    base = {
        "duckdb_type": "BIGINT", "value_class": "integer_like",
        "row_count": 100, "null_count": 0, "distinct_count": 40,
        "min": 1, "max": 40, "len_min": 1, "len_avg": 1.6, "len_max": 2,
        "top_values": [{"value": "1", "count": 5}, {"value": "2", "count": 4}],
        "patterns": [{"mask": "9", "count": 60}, {"mask": "99", "count": 40}],
    }
    return ColumnProfile(source_id="src1", table=table, column=column,
                         stats={**base, **stats})


PROFILES = [
    _profile("beta__orders", "customer_id"),
    _profile("alpha__customers", "customer_id"),
    _profile("alpha__customers", "name", duckdb_type="VARCHAR",
             value_class="text", patterns=[]),
]

MATRIX = {
    "threshold": 0.5,
    "warnings": [],
    "candidates": [
        {"left": "alpha__customers.customer_id", "right": "beta__orders.customer_id",
         "overlap": 40, "left_distinct": 40, "right_distinct": 40,
         "containment": 1.0, "jaccard": 1.0},
    ],
}


def _store(tmp_path, order=None) -> ProjectStore:
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    for profile in (order or PROFILES):
        store.save_profile(profile)
    return store


def test_building_twice_is_byte_identical(tmp_path):
    store = _store(tmp_path)
    a = inputs.build_profile_context(store, MATRIX)
    b = inputs.build_profile_context(store, MATRIX)
    assert a.text == b.text and a.sha256 == b.sha256
    assert a.trim_notices == []


def test_profile_insertion_order_does_not_matter(tmp_path):
    one = _store(tmp_path / "a")
    other = _store(tmp_path / "b", order=list(reversed(PROFILES)))
    assert (inputs.build_profile_context(one, MATRIX).text
            == inputs.build_profile_context(other, MATRIX).text)


def test_forced_trim_is_loud_and_names_the_cut(tmp_path):
    store = _store(tmp_path)
    full = inputs.build_profile_context(store, MATRIX)
    trimmed = inputs.build_profile_context(store, MATRIX,
                                           max_chars=len(full.text) - 50)
    assert trimmed.trim_notices, "a trim without a notice is a silent trim"
    assert "patterns" in trimmed.trim_notices[0]
    hard = inputs.build_profile_context(store, MATRIX, max_chars=80)
    assert len(hard.text) <= 80
    assert any("hard cut" in n for n in hard.trim_notices)


def test_role_context_leads_with_the_role_definitions(tmp_path):
    store = _store(tmp_path)
    roles = RoleSet(domain="testing", roles={"ledger": "the journal of record"})
    built = inputs.build_role_context(store, MATRIX, roles)
    assert built.text.startswith("## Roles to bind (domain: testing)")
    assert "- ledger: the journal of record" in built.text
    assert "## Column profiles" in built.text


def test_binding_context_carries_claim_columns_and_template_docs(tmp_path):
    store = _store(tmp_path)
    claim = create_claim(
        "orders reference customers", Actor.AI,
        predicate=Predicate(name="references", params={
            "child": "beta__orders.customer_id",
            "parent": "alpha__customers.customer_id",
        }),
    )
    labels = inputs.claim_label_map([claim])
    assert labels == {"c1": claim}
    built = inputs.build_binding_context(
        store, labels, prompts.render_template_docs()
    )
    assert "### claim c1" in built.text
    assert claim.id not in built.text  # ULIDs never enter a prompt
    assert "### beta__orders.customer_id" in built.text  # profile digest inlined
    assert "- alpha__customers: " in built.text  # view schema line
    assert "## Probe templates" in built.text
    assert "- anti_join: required [child, child_column, parent, parent_column]" in built.text


# Corpus knowledge must never leak into the product's prompts. The denylist
# is test-side by design; the builders are covered again corpus-side in the
# offline pipeline test.
_DENYLIST = ("trap", "decoy", "corpus", "expected_verdicts", "BLIND_",
             "F27", "F7/", "Seeded", "Zubehör", "Accessories")


@pytest.mark.parametrize("text", [
    prompts.V1_SYSTEM, prompts.ROLE_BINDING_SYSTEM, prompts.V2_SYSTEM,
    prompts.render_template_docs(), prompts.render_predicate_docs(),
], ids=["v1", "roles", "v2", "template_docs", "predicate_docs"])
def test_prompts_contain_no_corpus_hints(text):
    lowered = text.lower()
    for token in _DENYLIST:
        assert token.lower() not in lowered, f"prompt leaks {token!r}"
