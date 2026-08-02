"""Mapping: schema-valid answers become core objects deterministically,
paraphrases dedup, and every path is Actor.AI + proposed."""
import pytest

from before_we_ai.llm.prompts import render_template_docs
from before_we_ai.llm.vocabulary import (
    TEMPLATE_PARAMS,
    VALUE_PARAMS,
    check_template_params,
    normalize_template_params,
)
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


class TestABareColumnNameGrounds:
    """A rule hypothesis has to stand on something real in the landscape.

    `decodes` declares no table param at all, so an unqualified column name
    is the only thing the model *can* write for it — and rejecting that as
    "grounded in no known view or column" says the column does not exist
    when it plainly does. Both V1 skips on the corpus were this. The name
    still has to identify one column and no more.
    """

    def _decodes(self, **params):
        return Hypothesis.model_validate({
            "statement": "name decodes customer_id",
            "predicate": "decodes", "columns": [],
            "rationale": "low-cardinality codes",
            "params": params,
        })

    def test_a_name_only_one_view_carries_is_enough(self, tmp_path):
        _, index = _index(tmp_path)
        h = self._decodes(encoded="customer_id", decode="name",
                          key="customer_id", column="name")
        assert check_hypothesis(h, index) == []
        assert hypothesis_to_claim(h, index).source_ids == ["src_alpha"]

    def test_a_name_two_views_share_grounds_nothing(self, tmp_path):
        """`customer_id` sits in both views, so on its own it names no
        column. That is a real ambiguity, not a majority to pick from."""
        _, index = _index(tmp_path)
        errors = check_hypothesis(
            self._decodes(encoded="customer_id", decode="customer_id",
                          key="customer_id", column="customer_id"), index)
        assert any("grounded in no known view or column" in e for e in errors)

    def test_a_name_no_view_carries_still_grounds_nothing(self, tmp_path):
        _, index = _index(tmp_path)
        errors = check_hypothesis(
            self._decodes(encoded="nonesuch", decode="nonesuch",
                          key="nonesuch", column="nonesuch"), index)
        assert any("grounded in no known view or column" in e for e in errors)


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


def test_a_role_claim_binds_to_a_domain_law(tmp_path):
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


def test_a_role_claim_may_also_bind_to_a_generic_check(tmp_path):
    """Kickoff item 3, 2026-08-02. A role no domain law can reach may
    still have a data property worth testing — `account` against a chart
    of accounts — and V2's own refusals had been saying exactly that.

    This used to be rejected with "cannot test predicate 'role_binding'".
    What keeps the wider menu safe is the *promotion* boundary, not the
    binding one: a generic check over a role refutes but never
    establishes. See `core.transitions.establishing`.
    """
    _, index = _index(tmp_path)
    role_claim = proposal_to_mapping_claim(
        MappingProposal(role="account", binding={"table": "beta__orders"},
                            rationale="r"),
        index,
    )
    generic = CheckPlanProposal(
        claim_id=role_claim.id, template="anti_join", params={
            "child": "beta__orders", "parent": "alpha__customers",
            "child_column": "customer_id", "parent_column": "customer_id",
        })
    assert check_binding(generic, {role_claim.id: role_claim}, index) == []


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


class TestWhenTheContractItselfMisleads:
    """The V2 template docs used to close with one sentence: *param values
    are bare view/column identifiers unless the param name says expression
    or filter*. Three params hold data rather than names, and none of them
    is called `*_expr` or `*where` — so by our own rule they had to be
    identifiers, and the model wrote
    `accounts: "de_erp__chart_of_accounts"`.

    Four of the five rejected bindings on the corpus were that sentence,
    including all three `subledger_equals_gl` ones, which is why the only
    law that can settle a receivables object had never run. Found by the
    owner reading the store, 2026-08-02.

    Two changes came out of it and both are tested here: the docs now say
    per param what it holds, and a lone element written without its
    brackets is read as the one-item list it can only have meant.
    """

    def test_the_docs_say_what_a_value_param_holds(self):
        docs = render_template_docs()
        line = next(l for l in docs.splitlines()
                    if l.startswith("- subledger_equals_gl"))
        assert "VALUES: accounts is" in line
        assert "NOT the chart-of-accounts view" in line

    def test_the_closing_rule_no_longer_claims_to_cover_them(self):
        """The sentence that caused it. It may still state the default —
        it may not state it as if there were no exceptions."""
        closing = render_template_docs().splitlines()[-1]
        assert "EXCEPT" in closing and "VALUES" in closing

    def test_every_value_param_is_documented_on_every_template_that_takes_it(self):
        """A param explained on one template and silent on another is the
        same defect again, one template further along."""
        docs = render_template_docs()
        for template, contract in TEMPLATE_PARAMS.items():
            line = next(l for l in docs.splitlines()
                        if l.startswith(f"- {template}:"))
            for param in VALUE_PARAMS:
                if param in contract.allowed:
                    assert f"VALUES: {param} is" in line, (template, param)

    def test_a_lone_account_number_is_read_as_a_one_item_list(self):
        params, corrections = normalize_template_params(
            "subledger_equals_gl", {"accounts": "1200"},
            known_views={"de_erp__gl_postings"},
        )
        assert params["accounts"] == ["1200"]
        assert corrections == [{"param": "accounts", "given": "1200",
                                "read_as": ["1200"]}]

    def test_a_lone_pair_object_is_read_as_a_one_item_list(self):
        pair = {"part_expr": "substr(code, 1, 2)", "decode_column": "region"}
        params, _ = normalize_template_params("decode", {"pairs": pair})
        assert params["pairs"] == [pair]

    def test_a_bare_string_where_objects_belong_is_still_a_confusion(self):
        """The line that keeps the leniency honest. Wrapping by "it isn't a
        list" would turn nonsense into well-formed-looking nonsense; the
        wrap happens only when the value is of the type the list holds."""
        params, corrections = normalize_template_params(
            "decode", {"pairs": "region_code"})
        assert params["pairs"] == "region_code"
        assert corrections == []
        assert any("must be a list" in e for e in
                   check_template_params("decode", params))

    def test_a_view_name_in_accounts_is_refused_and_says_why(self):
        """The actual corpus answer. Wrapping makes it a well-formed list
        of one bad element, and the element check is what catches it —
        naming the value, so a reader can see the model gave a table where
        numbers belong."""
        params, _ = normalize_template_params(
            "subledger_equals_gl", {"accounts": "de_erp__chart_of_accounts"},
            known_views={"de_erp__chart_of_accounts"},
        )
        errors = check_template_params("subledger_equals_gl", params)
        assert any("must contain account numbers" in e for e in errors)
        assert any("de_erp__chart_of_accounts" in e for e in errors)

    def test_a_lone_column_still_gets_its_view_prefix_stripped(self):
        """Order matters: the wrap runs first, so the list branch of the
        column correction can reach a scalar that was written qualified."""
        params, corrections = normalize_template_params(
            "duplicate",
            {"table": "de_erp__invoices",
             "key_columns": "de_erp__invoices.document_number"},
            known_views={"de_erp__invoices"},
        )
        assert params["key_columns"] == ["document_number"]
        assert [c["param"] for c in corrections] == ["key_columns", "key_columns"]


class TestARefusalNamesWhatItRefused:
    """A rejected binding writes its reason into the store as a
    DECLARATION and the readiness report renders it: the message is a
    product surface, not a debugging aid.

    It cost us: "param 'accounts' must be a list, got str" is accurate and
    useless. The value was `de_erp__chart_of_accounts`, and a message
    carrying it would have made the real cause — our own instruction —
    visible on the first read instead of the fiftieth.
    """

    @pytest.mark.parametrize("template, params, offender", [
        ("subledger_equals_gl", {"accounts": "de_erp__chart_of_accounts"},
         "de_erp__chart_of_accounts"),
        ("coverage", {"expected": "de_erp__chart.account_range_group"},
         "de_erp__chart.account_range_group"),
        ("duplicate", {"key_columns": 7}, "7"),
        ("subledger_equals_gl", {"accounts": ["not_a_number"]}, "not_a_number"),
        ("reconciliation", {"left_measure_expr": "sum(amount)"}, "sum(amount)"),
        ("balance", {"amount": "de_erp__gl.amount"}, "de_erp__gl.amount"),
    ])
    def test_the_offending_value_is_in_the_message(self, template, params,
                                                   offender):
        errors = check_template_params(template, params)
        assert any(offender in e for e in errors), (params, errors)

    def test_a_list_refusal_also_says_what_the_list_holds(self):
        """The half that turns a refusal into an instruction."""
        (error,) = [e for e in check_template_params(
            "subledger_equals_gl", {"accounts": "de_erp__chart_of_accounts"})
            if "must be a list" in e]
        assert "account NUMBERS" in error
        assert "NOT the chart-of-accounts view" in error
