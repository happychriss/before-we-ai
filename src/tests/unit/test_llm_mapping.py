"""Mapping: schema-valid answers become core objects deterministically,
paraphrases dedup, and every path is Actor.AI + proposed."""
import pytest

from before_we_ai.llm.vocabulary import normalize_template_params
from before_we_ai.llm.mapping import (
    ProfileIndex,
    proposal_to_check_plan,
    check_binding,
    check_hypothesis,
    check_mapping_proposal,
    hypothesis_to_claim,
    proposal_to_mapping_claim,
)
from before_we_ai.llm.schemas import Hypothesis, CheckPlanProposal, MappingProposal
from before_we_ai.llm.vocabulary import ROLE_BINDING_PREDICATE
from before_we_ai.core import Actor, ClaimStatus
from before_we_ai.core.objects import DataProfile, ConceptClaim, MappingClaim
from before_we_ai.core.semantics import claim_key
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.integration


def _profile(table, column, source_id="src1"):
    return DataProfile(
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
    assert claim.status is ClaimStatus.PROPOSED
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
    # kind is derived from the predicate now, so it cannot disagree with it
    # and there is nothing left to check about the pair. What survives is
    # the one thing only the model can supply.
    nameless = check_hypothesis(_hypothesis(
        predicate="concept_definition", params={}, columns=[]), index)
    assert any("must name the term it defines" in e for e in nameless)


def test_concept_hypothesis_becomes_a_concept_claim(tmp_path):
    _, index = _index(tmp_path)
    h = _hypothesis(
        predicate="concept_definition", params={}, columns=[],
        term="active customer", definition="a customer with at least one order",
    )
    assert h.kind == "concept"  # derived, not supplied
    assert check_hypothesis(h, index) == []
    claim = hypothesis_to_claim(h, index)
    assert isinstance(claim, ConceptClaim)
    assert claim.created_by is Actor.AI
    assert claim.status is ClaimStatus.PROPOSED
    assert claim.term == "active customer"


def test_role_proposal_checks_and_maps(tmp_path):
    _, index = _index(tmp_path)
    p = MappingProposal(role="journal",
                            binding={"table": "beta__orders",
                                     "amount": "beta__orders.customer_id"},
                            rationale="looks transactional")
    assert check_mapping_proposal(p, ["journal"], index) == []
    assert check_mapping_proposal(p, ["ledger"], index) == ["proposal binds unknown role 'journal'"]
    bad = MappingProposal(role="journal", binding={"table": "nowhere"},
                              rationale="?")
    assert any("unknown 'nowhere'" in e
               for e in check_mapping_proposal(bad, ["journal"], index))
    empty = MappingProposal(role="journal", binding={}, rationale="?")
    assert any("at least one part" in e
               for e in check_mapping_proposal(empty, ["journal"], index))
    claim = proposal_to_mapping_claim(p, index)
    assert isinstance(claim, MappingClaim)
    assert claim.created_by is Actor.AI
    assert claim.status is ClaimStatus.PROPOSED
    assert claim.predicate.name == ROLE_BINDING_PREDICATE
    assert claim.role == "journal"
    assert claim.source_ids == ["src_beta"]
    # binding dicts are key-sorted -> stable claim_key
    again = proposal_to_mapping_claim(
        MappingProposal(role="journal",
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
    good = CheckPlanProposal(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "customer_id", "parent_column": "customer_id",
    })
    assert check_binding(good, claims, index) == []
    check, _ = proposal_to_check_plan(good, claim)
    assert check.claim_id == claim.id and check.roles == []

    assert check_binding(
        CheckPlanProposal(claim_id="ghost", template=None, no_template_reason="x"),
        claims, index,
    ) == ["binding references unknown claim 'ghost'"]

    wrong_template = CheckPlanProposal(claim_id=claim.id, template="balance",
                                  params={"journal": "beta__orders",
                                          "amount": "customer_id",
                                          "group_column": "customer_id"})
    assert any("cannot test predicate 'references'" in e
               for e in check_binding(wrong_template, claims, index))

    missing_param = CheckPlanProposal(claim_id=claim.id, template="anti_join",
                                 params={"child": "beta__orders"})
    assert any("missing required param" in e
               for e in check_binding(missing_param, claims, index))

    ghost_view = CheckPlanProposal(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "gamma__nowhere",
        "child_column": "customer_id", "parent_column": "customer_id",
    })
    assert any("parent='gamma__nowhere' must name a known view" in e
               for e in check_binding(ghost_view, claims, index))

    # a view param that is not even a string (seen live: ranges=[]) is an error
    list_view = CheckPlanProposal(claim_id=claim.id, template="range_join", params={
        "table": "beta__orders", "value_column": "customer_id",
        "ranges": [], "range_from": "lo", "range_to": "hi",
    })
    assert any("ranges=[] must name a known view" in e
               for e in check_binding(list_view, claims, index))

    ghost_column = CheckPlanProposal(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "customer_id", "parent_column": "customer_nr",
    })
    assert any("column 'customer_nr' does not exist on view 'alpha__customers'" in e
               for e in check_binding(ghost_column, claims, index))

    # a column qualified with exactly its own view is unambiguous — accepted
    # and normalized to the bare column (seen in every real run)
    qualified = CheckPlanProposal(claim_id=claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "beta__orders.customer_id",
        "parent_column": "customer_id",
    })
    assert check_binding(qualified, claims, index) == []
    normalized, _ = proposal_to_check_plan(qualified, claim)
    assert normalized.params["child_column"] == "customer_id"

    none_binding = CheckPlanProposal(claim_id=claim.id, template=None,
                                no_template_reason="semantic only")
    assert check_binding(none_binding, claims, index) == []
    assert proposal_to_check_plan(none_binding, claim)[0] is None

    no_reason = CheckPlanProposal(claim_id=claim.id, template=None)
    assert any("requires no_template_reason" in e
               for e in check_binding(no_reason, claims, index))
    stray_reason = CheckPlanProposal(claim_id=claim.id, template="anti_join",
                                params=good.params,
                                no_template_reason="just in case")
    assert any("only valid with template=null" in e
               for e in check_binding(stray_reason, claims, index))


def test_role_claim_binds_to_invariants_only(tmp_path):
    _, index = _index(tmp_path)
    role_claim = proposal_to_mapping_claim(
        MappingProposal(role="journal", binding={"table": "beta__orders"},
                            rationale="r"),
        index,
    )
    claims = {role_claim.id: role_claim}
    invariant = CheckPlanProposal(claim_id=role_claim.id, template="balance", params={
        "journal": "beta__orders", "amount": "customer_id",
        "group_column": "customer_id",
    })
    assert check_binding(invariant, claims, index) == []
    check, _ = proposal_to_check_plan(invariant, role_claim)
    assert check.roles == ["journal"]
    ordinary = CheckPlanProposal(claim_id=role_claim.id, template="anti_join", params={
        "child": "beta__orders", "parent": "alpha__customers",
        "child_column": "customer_id", "parent_column": "customer_id",
    })
    assert any("cannot test predicate 'role_binding'" in e
               for e in check_binding(ordinary, claims, index))


def test_a_qualified_view_param_is_read_as_its_view():
    """Owner decision 2026-08-02. Six of seven V2 skips were this shape:
    the model answers `view.column` where a bare view belongs, and because
    the column params anchor on the view param, one mistake takes the whole
    binding with it."""
    params, corrections = normalize_template_params(
        "anti_join",
        {"child": "de_erp__gl_postings.account_id",
         "child_column": "account_id",
         "parent": "de_erp__accounts", "parent_column": "account_id"},
        known_views={"de_erp__gl_postings", "de_erp__accounts"},
    )
    assert params["child"] == "de_erp__gl_postings"
    assert [c["param"] for c in corrections] == ["child"]
    assert corrections[0]["given"] == "de_erp__gl_postings.account_id"


def test_an_unknown_view_is_left_alone():
    """Leniency only where the shape error is unambiguous. If the head is
    no view we know, guessing would be inventing."""
    params, corrections = normalize_template_params(
        "anti_join", {"child": "something.else"}, known_views={"de_erp__x"})
    assert params["child"] == "something.else"
    assert corrections == []


def test_every_correction_is_reported_not_only_applied():
    """The whole point of the decision: the check runs AND the reader can
    see that we read something other than what was written."""
    _params, corrections = normalize_template_params(
        "duplicate",
        {"table": "de_erp__invoices",
         "key_columns": ["de_erp__invoices.document_number"]},
        known_views={"de_erp__invoices"},
    )
    assert corrections == [{
        "param": "key_columns",
        "given": ["de_erp__invoices.document_number"],
        "read_as": ["document_number"],
    }]


def test_a_missing_view_param_is_recovered_from_the_columns_that_name_it():
    """Owner decision 2026-08-02, the second of two: flexibility, recorded.

    The model writes `amount: de_erp__gl_postings.amount_local_currency`
    and omits `journal` entirely. Because the column normalization anchors
    on the view param, one omission used to take every column with it and
    all three balance bindings were lost — with them the journal election,
    and with that the verdict.
    """
    params, corrections = normalize_template_params(
        "balance",
        {"amount": "de_erp__gl_postings.amount_local_currency",
         "group_column": "de_erp__gl_postings.period"},
        known_views={"de_erp__gl_postings", "us_erp__gl_postings"},
    )
    assert params == {"amount": "amount_local_currency",
                      "group_column": "period",
                      "journal": "de_erp__gl_postings"}
    supplied = [c for c in corrections if c["param"] == "journal"]
    assert supplied == [{"param": "journal", "given": None,
                         "read_as": "de_erp__gl_postings"}]


def test_columns_that_disagree_are_a_confusion_not_a_majority():
    """The line that keeps the recovery honest. Two views named, so the
    model does not know which table it meant — and neither do we."""
    params, corrections = normalize_template_params(
        "balance",
        {"amount": "de_erp__gl_postings.amount_local_currency",
         "group_column": "us_erp__gl_postings.period"},
        known_views={"de_erp__gl_postings", "us_erp__gl_postings"},
    )
    assert "journal" not in params
    assert corrections == []


def test_nothing_is_recovered_from_unqualified_columns():
    """Bare columns name no view, so there is nothing to recover from."""
    params, _ = normalize_template_params(
        "balance", {"amount": "amount_local_currency", "group_column": "period"},
        known_views={"de_erp__gl_postings"})
    assert "journal" not in params


def test_a_view_param_the_model_supplied_is_never_overwritten():
    params, corrections = normalize_template_params(
        "balance",
        {"journal": "us_erp__gl_postings",
         "amount": "us_erp__gl_postings.amount_local_currency"},
        known_views={"de_erp__gl_postings", "us_erp__gl_postings"},
    )
    assert params["journal"] == "us_erp__gl_postings"
    assert [c["param"] for c in corrections] == ["amount"]
