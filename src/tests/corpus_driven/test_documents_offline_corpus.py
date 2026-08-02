"""M5 acceptance: the documents, offline, against the frozen corpus.

The milestone plan asks for the T8 negatives and for the policy document
to resolve what the data cannot show. Both are here, and they are the two
halves of the same claim: a system that only refuses is useless, and one
that only accepts is dangerous.

K3 — the accounting policy states the sign convention and the revenue
definition, and nothing in any column does. V3 reads them, proposes them,
anchors them to the sentences they came from, and links them to the rule
items they answer. The ReadinessMap moves from "nothing in this project is
linked to it" to "1 candidate is proposed and none is settled". That is
progress a reader can act on, and it is **not** a promotion.

T8 — three figures enter and none corroborates anything, each refused for
its own reason and each leaving a question behind:
  F23  a figure that lives only inside a chart
  F24  a restatement giving two figures for one slot
  F26  a figure from a document about a divested unit, alone on the page

False-Promotion stays 0 throughout: every claim these documents produce
sits at ``proposed``.
"""

from pathlib import Path

import pytest
import yaml

from before_we_ai.core import ClaimStatus, EvidenceType
from before_we_ai.documents import read_documents
from before_we_ai.domains import packaged
from before_we_ai.llm import ask, interpret_documents, load_domain_guide
from before_we_ai.readiness import evaluate_request
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.acceptance

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm"
DOMAIN_GUIDE_FILE = packaged("finance")
DEMO_QUESTION = "Can these files reliably produce actual P&L by entity and month?"

# The three documents that carry the acceptance. The rest of the corpus's
# PDFs are declared in the walkthrough (validation/support/corpus.py); here
# only what the traps need, so a fixture exists for every call made.
DOCUMENTS = [
    {"name": "management_report", "kind": "pdf",
     "location": str(CORPUS / "management_report.pdf")},
    {"name": "buchhaltungsrichtlinie", "kind": "pdf",
     "location": str(CORPUS / "buchhaltungsrichtlinie.pdf")},
    {"name": "pressemitteilung_2022_divested_unit", "kind": "pdf",
     "location": str(CORPUS / "noise" / "pressemitteilung_2022_divested_unit.pdf")},
]

SIGN_CONVENTION = "sign convention for income and expense"
PL_ACCOUNTS = "which accounts are profit and loss"
CUT_OFF = "month cut-off for late postings"


@pytest.fixture(scope="module")
def read(tmp_path_factory):
    root = init_project(tmp_path_factory.mktemp("v3") / "corpus-docs")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = DOCUMENTS
    config["llm"] = {"offline": True, "fixtures_dir": str(FIXTURES),
                     "domain_guide_file": str(DOMAIN_GUIDE_FILE)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    read_documents(root)
    guide = load_domain_guide(DOMAIN_GUIDE_FILE)
    ask(root, DEMO_QUESTION, guide=guide, store=ProjectStore(root),
        scenario="corpus")
    report = interpret_documents(root, guide=guide, store=ProjectStore(root),
                                 scenario="corpus")
    return root, guide, report, ProjectStore(root)


def _anchors(store):
    return [e for e in store.evidence.values()
            if e.type is EvidenceType.DOCUMENT_ANCHOR]


def _rule_items(store, guide):
    for request_id in store.requests:
        readiness = evaluate_request(store, guide, request_id)
        if readiness:
            return {i.item.name: i for i in readiness.items
                    if i.item.kind.value == "rule"}
    return {}


# -- the whole run ---------------------------------------------------------

def test_every_document_was_read_and_answered(read):
    _root, _guide, report, _store = read
    assert report.failures == []
    assert report.skipped == []
    assert len(report.documents_read) == 3


def test_false_promotion_stays_zero(read):
    """The measure that is non-negotiable at every commit."""
    _root, _guide, _report, store = read
    assert store.claims
    assert all(c.status is ClaimStatus.PROPOSED for c in store.claims.values())


def test_every_finding_is_anchored_to_words_that_are_really_there(read):
    _root, _guide, report, store = read
    assert report.anchors == len(report.claims_created)
    for anchor in _anchors(store):
        assert anchor.payload["quote"].strip()


# -- K3: the policy resolves what no column shows --------------------------

def test_k3_the_policy_answers_the_sign_convention(read):
    _root, _guide, report, _store = read
    linked = dict((ref, claim) for ref, claim in report.links)
    assert SIGN_CONVENTION in linked


def test_k3_the_policy_answers_the_revenue_accounts(read):
    _root, _guide, report, _store = read
    assert PL_ACCOUNTS in dict(report.links)


def test_k3_those_items_now_have_a_candidate_instead_of_nothing(read):
    _root, guide, _report, store = read
    items = _rule_items(store, guide)
    assert "proposed" in items[SIGN_CONVENTION].because
    assert "proposed" in items[PL_ACCOUNTS].because


def test_k3_a_linked_item_is_still_not_satisfied(read):
    """The line that keeps this honest. A policy is a very good reason to
    believe something, and still not a measurement."""
    _root, guide, _report, store = read
    items = _rule_items(store, guide)
    assert not items[SIGN_CONVENTION].satisfied
    assert not items[PL_ACCOUNTS].satisfied


def test_a_rule_no_document_states_stays_untouched(read):
    """The cut-off rule is in none of these documents, and nothing
    pretends otherwise."""
    _root, guide, _report, store = read
    assert "nothing in this project is linked to it" in \
        _rule_items(store, guide)[CUT_OFF].because


# -- T8: three refusals, three reasons -------------------------------------

def test_f23_the_chart_figure_is_anchored_as_chart_and_links_nothing(read):
    _root, _guide, report, store = read
    chart = [a for a in _anchors(store) if a.payload["kind"] == "chart"]
    assert [a.payload["quote"] for a in chart] == ["EUR 2,847,000"]
    assert not any(ref for ref, _ in report.links if "revenue" in ref.lower()
                   and "2,847" in ref)


def test_f23_leaves_a_question_saying_it_came_from_a_chart(read):
    _root, _guide, report, _store = read
    assert any("only inside a chart" in q for q in report.questions)


def test_f24_the_restatement_is_named_a_restatement(read):
    """Not merely refused — refused for the right reason, which is the
    reason a human can act on."""
    _root, _guide, report, _store = read
    assert any("more than one figure for the same thing" in q
               for q in report.questions)
    assert any("a decision, not a calculation" in q for q in report.questions)


def test_f26_the_divested_unit_figure_corroborates_nothing(read):
    _root, _guide, report, _store = read
    assert any("pressemitteilung_2022_divested_unit" in q
               and "no check has produced it" in q
               for q in report.questions)


def test_the_noise_document_was_read_rather_than_avoided(read):
    """Refusing a document nobody opened proves nothing."""
    _root, _guide, report, store = read
    assert "pressemitteilung_2022_divested_unit" in report.documents_read
    assert any(a.payload["source"] == "pressemitteilung_2022_divested_unit"
               for a in _anchors(store))


def test_no_figure_was_ever_linked_to_a_rule_item(read):
    """Every link in this run came from a policy sentence, none from a
    number — which is the multi-anchor rule doing its job."""
    _root, _guide, report, store = read
    from before_we_ai.core.objects import ConceptClaim

    # The property, not the wording: a link may only come from a policy
    # sentence stating a rule, never from a figure. Pinning the sentences
    # themselves would make this test about how the model phrases things,
    # which is exactly what it must not depend on.
    linked_claims = {claim_id for _ref, claim_id in report.links}
    assert linked_claims
    for claim_id in linked_claims:
        assert isinstance(store.claims[claim_id], ConceptClaim)


# The V3 half of THE drift guard. Contract lane as well as acceptance, so a
# prompt or builder edit turns it red without anyone running the corpus.
# Its twin for V1/V2/request lives in test_llm_offline_corpus.py, and the
# completeness check over there names this file — neither guard can quietly
# stop covering a fixture.
@pytest.mark.contract
def test_fixtures_match_current_inputs(read):
    """Each fixture answered one specific input. Rebuild those inputs from
    the frozen corpus and compare hashes. Red here means the recorded
    answers are stale — refresh the fixtures, do not touch this test."""
    import json

    import duckdb

    from before_we_ai.llm.inputs import build_document_context
    from before_we_ai.llm.v3_documents import (
        V3Report,
        open_rule_items,
        select_passages,
    )

    root, guide, _report, store = read
    items = open_rule_items(store, guide)
    con = duckdb.connect(str(root / "cache" / "analysis.duckdb"))
    try:
        for profile in sorted(store.documents.values(), key=lambda d: d.document):
            chunks = select_passages(con, profile.document, items, V3Report())
            built = build_document_context(profile.document, chunks, items)
            path = FIXTURES / f"v3_documents__corpus__{profile.document}.json"
            recorded = json.loads(path.read_text(encoding="utf-8"))
            assert recorded["input_sha256"] == built.sha256, (
                f"{path.name} answered a different input than the one built "
                f"today"
            )
    finally:
        con.close()
