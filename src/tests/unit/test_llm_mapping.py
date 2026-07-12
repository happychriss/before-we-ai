"""Mapping: schema-valid answers become core objects deterministically,
paraphrases dedup, and every path is Actor.AI + inferred."""

from before_we_ai.llm.mapping import (
    ProfileIndex,
    binding_to_probe,
    check_binding,
    check_hypothesis,
    check_role_proposal,
    hypothesis_to_claim,
    proposal_to_role_claim,
)
from before_we_ai.llm.schemas import Hypothesis, ProbeBinding, RoleBindingProposal
from before_we_ai.llm.vocabulary import ROLE_BINDING_PREDICATE
from before_we_ai.model import Actor, ClaimStatus
from before_we_ai.model.objects import ColumnProfile, ConceptClaim, RoleBindingClaim
from before_we_ai.model.semantics import claim_key
from before_we_ai.store import ProjectStore, init_project


def _profile(table, column, source_id="src1"):
    return ColumnProfile(
        source_id=source_id, table=table, column=column,
        stats={"duckdb_type": "BIGINT", "value_class": "integer_like",
               "row_count": 10, "null_count": 0, "distinct_count": 5},
    )


def _index(tmp_path) -> tuple[ProjectStore, ProfileIndex]:
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    for p in [
        _profile("beta__orders", "customer_id", "src_beta"),
        _profile("alpha__customers", "customer_id", "src_alpha"),
        _profile("alpha__customers", "name", "src_alpha"),
    ]:
        store.save_profile(p)
    return store, ProfileIndex(store)


def _hypothesis(**overrides) -> Hypothesis:
    base = {
        "statement": "orders reference customers",
        "predicate": "references",
        "params": {"child": "beta__orders.customer_id",
                   "parent": "alpha__customers.customer_id"},
        "columns": ["beta__orders.customer_id"],
        "rationale": "full containment",
    }
    return Hypothesis.model_validate({**base, **overrides})


def test_valid_hypothesis_checks_clean_and_maps(tmp_path):
    _, index = _index(tmp_path)
    h = _hypothesis()
    assert check_hypothesis(h, index) == []
    claim = hypothesis_to_claim(h, index)
    assert claim.created_by is Actor.AI
    assert claim.status is ClaimStatus.INFERRED
    assert claim.predicate.name == "references"
    assert claim.source_ids == ["src_alpha", "src_beta"]


def test_paraphrases_land_on_one_claim(tmp_path):
    store, index = _index(tmp_path)
    first = hypothesis_to_claim(_hypothesis(), index)
    second = hypothesis_to_claim(_hypothesis(
        statement="every order row points at an existing customer",
        params={"child": " beta__orders.customer_id ",  # whitespace jitter
                "parent": "alpha__customers.customer_id"},
    ), index)
    assert claim_key(first) == claim_key(second)
    kept = store.add_claim(first)
    assert store.add_claim(second) is kept
    assert len(store.claims) == 1


def test_check_hypothesis_reports_semantic_errors(tmp_path):
    _, index = _index(tmp_path)
    missing = check_hypothesis(_hypothesis(params={"child": "beta__orders.customer_id"}), index)
    assert any("requires param 'parent'" in e for e in missing)
    unknown_key = check_hypothesis(_hypothesis(
        params={"child": "beta__orders.customer_id",
                "parent": "alpha__customers.customer_id", "confidence": "high"}
    ), index)
    assert any("param 'confidence' is not allowed" in e for e in unknown_key)
    bad_ref = check_hypothesis(_hypothesis(
        params={"child": "beta__orders.customre_id",  # typo in a known view
                "parent": "alpha__customers.customer_id"}
    ), index)
    assert any("unknown column reference 'beta__orders.customre_id'" in e
               for e in bad_ref)
    bad_column = check_hypothesis(_hypothesis(columns=["gamma__x.y"]), index)
    assert any("not in the profiles" in e for e in bad_column)
    mismatch = check_hypothesis(_hypothesis(predicate="concept_definition",
                                            params={}, columns=[]), index)
    assert any("does not fit" in e for e in mismatch)
    incomplete = check_hypothesis(_hypothesis(
        kind="concept", predicate="concept_definition", params={}, columns=[],
        term="revenue",  # definition missing
    ), index)
    assert any("requires term and definition" in e for e in incomplete)
    bad_kind = check_hypothesis(_hypothesis(kind="guess"), index)
    assert any("kind must be 'rule' or 'concept'" in e for e in bad_kind)


def test_concept_hypothesis_becomes_a_concept_claim(tmp_path):
    _, index = _index(tmp_path)
    h = _hypothesis(
        kind="concept", predicate="concept_definition", params={}, columns=[],
        term="active customer", definition="a customer with at least one order",
    )
    assert check_hypothesis(h, index) == []
    claim = hypothesis_to_claim(h, index)
    assert isinstance(claim, ConceptClaim)
    assert claim.created_by is Actor.AI
    assert claim.status is ClaimStatus.INFERRED
    assert claim.term == "active customer"


def test_role_proposal_checks_and_maps(tmp_path):
    _, index = _index(tmp_path)
    p = RoleBindingProposal(role="journal",
                            binding={"table": "beta__orders",
                                     "amount": "beta__orders.customer_id"},
                            rationale="looks transactional")
    assert check_role_proposal(p, ["journal"], index) == []
    assert check_role_proposal(p, ["ledger"], index) == ["proposal binds unknown role 'journal'"]
    bad = RoleBindingProposal(role="journal", binding={"table": "nowhere"},
                              rationale="?")
    assert any("unknown 'nowhere'" in e
               for e in check_role_proposal(bad, ["journal"], index))
    empty = RoleBindingProposal(role="journal", binding={}, rationale="?")
    assert any("at least one part" in e
               for e in check_role_proposal(empty, ["journal"], index))
    claim = proposal_to_role_claim(p, index)
    assert isinstance(claim, RoleBindingClaim)
    assert claim.created_by is Actor.AI
    assert claim.status is ClaimStatus.INFERRED
    assert claim.predicate.name == ROLE_BINDING_PREDICATE
    assert claim.role == "journal"
    assert claim.source_ids == ["src_beta"]
    # binding dicts are key-sorted -> stable claim_key
    again = proposal_to_role_claim(
        RoleBindingProposal(role="journal",
                            binding={"amount": "beta__orders.customer_id",
                                     "table": "beta__orders"},
                            rationale="other wording"),
        index,
    )
    assert claim_key(claim) == claim_key(again)


def test_binding_checks_and_maps(tmp_path):
    _, index = _index(tmp_path)
    claim = hypothesis_to_claim(_hypothesis(), index)
    claims = {claim.id: claim}
    good = ProbeBinding(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "customer_id", "parent_column": "customer_id",
    })
    assert check_binding(good, claims, index) == []
    probe = binding_to_probe(good, claim)
    assert probe.claim_id == claim.id and probe.roles == []

    assert check_binding(
        ProbeBinding(claim_id="ghost", template=None, no_template_reason="x"),
        claims, index,
    ) == ["binding references unknown claim 'ghost'"]

    wrong_template = ProbeBinding(claim_id=claim.id, template="balance",
                                  params={"journal": "beta__orders",
                                          "amount": "customer_id",
                                          "group_column": "customer_id"})
    assert any("cannot test predicate 'references'" in e
               for e in check_binding(wrong_template, claims, index))

    missing_param = ProbeBinding(claim_id=claim.id, template="anti_join",
                                 params={"child": "beta__orders"})
    assert any("missing required param" in e
               for e in check_binding(missing_param, claims, index))

    ghost_view = ProbeBinding(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "gamma__nowhere",
        "child_column": "customer_id", "parent_column": "customer_id",
    })
    assert any("parent='gamma__nowhere' must name a known view" in e
               for e in check_binding(ghost_view, claims, index))

    # a view param that is not even a string (seen live: ranges=[]) is an error
    list_view = ProbeBinding(claim_id=claim.id, template="range_join", params={
        "table": "beta__orders", "value_column": "customer_id",
        "ranges": [], "range_from": "lo", "range_to": "hi",
    })
    assert any("ranges=[] must name a known view" in e
               for e in check_binding(list_view, claims, index))

    ghost_column = ProbeBinding(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "customer_id", "parent_column": "customer_nr",
    })
    assert any("column 'customer_nr' does not exist on view 'alpha__customers'" in e
               for e in check_binding(ghost_column, claims, index))

    # a column qualified with exactly its own view is unambiguous — accepted
    # and normalized to the bare column (seen in every real run)
    qualified = ProbeBinding(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "beta__orders.customer_id",
        "parent_column": "customer_id",
    })
    assert check_binding(qualified, claims, index) == []
    normalized = binding_to_probe(qualified, claim)
    assert normalized.params["child_column"] == "customer_id"

    none_binding = ProbeBinding(claim_id=claim.id, template=None,
                                no_template_reason="semantic only")
    assert check_binding(none_binding, claims, index) == []
    assert binding_to_probe(none_binding, claim) is None

    no_reason = ProbeBinding(claim_id=claim.id, template=None)
    assert any("requires no_template_reason" in e
               for e in check_binding(no_reason, claims, index))
    stray_reason = ProbeBinding(claim_id=claim.id, template="anti_join",
                                params=good.params,
                                no_template_reason="just in case")
    assert any("only valid with template=null" in e
               for e in check_binding(stray_reason, claims, index))


def test_role_claim_binds_to_invariants_only(tmp_path):
    _, index = _index(tmp_path)
    role_claim = proposal_to_role_claim(
        RoleBindingProposal(role="journal", binding={"table": "beta__orders"},
                            rationale="r"),
        index,
    )
    claims = {role_claim.id: role_claim}
    invariant = ProbeBinding(claim_id=role_claim.id, template="balance", params={
        "journal": "beta__orders", "amount": "customer_id",
        "group_column": "customer_id",
    })
    assert check_binding(invariant, claims, index) == []
    probe = binding_to_probe(invariant, role_claim)
    assert probe.roles == ["journal"]
    ordinary = ProbeBinding(claim_id=role_claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "customer_id", "parent_column": "customer_id",
    })
    assert any("cannot test predicate 'role_binding'" in e
               for e in check_binding(ordinary, claims, index))
