"""M4 offline acceptance: the full LLM pipeline against the frozen corpus,
stub-driven, deterministic, no network.

scan -> V1 hypothesize -> role proposals -> V2 bind -> engine run_ready ->
resolve_roles, with every LLM answer replayed from recorded fixtures
through the exact validation/mapping path of the real client. Corpus
knowledge (and the fixtures that encode it) stays test-side.

Also home of the **fixture drift guard**: every fixture pins the sha256
of the input it answered; the guard rebuilds those inputs from the frozen
corpus and compares. A prompt or builder change turns this red loudly —
the fix is re-recording fixtures (tests/eval/refresh_fixtures.py online,
or re-authoring by hand), never loosening the guard.
"""

import json
from pathlib import Path

import pytest
import yaml

from before_we_ai import scan
from before_we_ai.engine import run_ready
from before_we_ai.llm import bind_probes, hypothesize, load_roles, propose_role_bindings, resolve_roles
from before_we_ai.llm.inputs import (
    build_binding_context,
    build_profile_context,
    build_role_context,
    claim_label_map,
)
from before_we_ai.llm.mapping import admissible_templates
from before_we_ai.llm.prompts import render_template_docs
from before_we_ai.llm.v2_bind import _unbound_ai_claims
from before_we_ai.model import Actor, ClaimStatus, EvidenceType
from before_we_ai.model.objects import RoleBindingClaim
from before_we_ai.profile.candidates import load_matrix
from before_we_ai.sources import open_catalog
from before_we_ai.store import ProjectStore, init_project

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm"
ROLES_FILE = Path(__file__).resolve().parents[1] / "fixtures" / "roles_finance.yaml"

SOURCES = [
    {"name": "de_erp", "kind": "duckdb", "location": str(CORPUS / "DE" / "erp.duckdb")},
    {"name": "us_erp", "kind": "duckdb", "location": str(CORPUS / "US" / "erp.duckdb")},
    {"name": "kunden_migration", "kind": "xlsx", "location": str(CORPUS / "kunden_migration.xlsx")},
    {"name": "marketing_grouping", "kind": "xlsx", "location": str(CORPUS / "marketing_grouping.xlsx")},
    {"name": "kontakte_aussendienst", "kind": "xlsx",
     "location": str(CORPUS / "kontakte_aussendienst.xlsx")},
    {"name": "buchungen_report", "kind": "csv", "location": str(CORPUS / "buchungen_report.csv")},
    {"name": "management_report", "kind": "pdf", "location": str(CORPUS / "management_report.pdf")},
]

# Tokens that must never reach a prompt: they exist only in test/corpus
# metadata, so their presence in a built input means corpus knowledge leaked
# into the product.
LEAK_TOKENS = ("trap", "decoy", "BLIND_", "expected_verdicts", "F27", "Seeded")


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    root = init_project(tmp_path_factory.mktemp("llm") / "corpus-llm", name="corpus-llm")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = SOURCES
    config["llm"] = {"offline": True, "fixtures_dir": str(FIXTURES),
                     "roles_file": str(ROLES_FILE)}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    scan(root)
    store = ProjectStore(root)
    roles = load_roles(ROLES_FILE)

    results = {"root": root, "roles": roles}
    results["v1"] = hypothesize(root, store=store, scenario="corpus")
    results["proposals"] = propose_role_bindings(root, roles=roles, store=store,
                                                 scenario="corpus")
    results["v2"] = bind_probes(root, store=store, scenario="corpus")
    con = open_catalog(root)
    try:
        results["engine"] = run_ready(store, con)
    finally:
        con.close()
    results["store"] = ProjectStore(root)  # reload from disk
    results["role_cards"] = resolve_roles(results["store"], roles)
    return results


def test_contracts_ran_clean_offline(pipeline):
    """Pinned against the recorded real answers (Opus 4.8 / Sonnet 5,
    refreshed 2026-07-12). A red here after a fixture refresh is the guard
    working: review the new numbers and re-pin deliberately."""
    v1, proposals, v2 = pipeline["v1"], pipeline["proposals"], pipeline["v2"]
    assert v1.failure is None
    assert len(v1.claims_created) == 62
    assert v1.claims_deduped == 1  # the real batch contains one paraphrase pair
    assert len(v1.skipped) == 2  # residual bad items skipped, batch survived
    assert proposals.failure is None and len(proposals.claims_created) == 23
    assert v2.failures == [] and v2.unanswered == []
    assert len(v2.probes_created) == 58
    assert len(v2.skipped) == 1  # the ranges=[] binding — skipped, not crashed
    assert len(v2.semantic_only) == 8  # no admissible template — never sent
    assert len(v2.unbindable) == 18  # honest template=null answers
    assert len(pipeline["engine"].executed) == 58
    assert pipeline["engine"].skipped == []

    # every claim that ends without a probe says why, in the store — the reason
    # must outlive the disposable call log
    store = pipeline["store"]
    reasons = {
        record.claim_id: record.payload
        for record in store.evidence.values()
        if record.type is EvidenceType.DECLARATION and "decision" in record.payload
    }
    assert len(reasons) == 27  # 18 unbindable + 8 semantic-only + 1 skipped
    assert sorted(p["decision"] for p in reasons.values()) == (
        ["semantic_only"] * 8 + ["skipped"] + ["unbindable"] * 18
    )
    assert all(p["reason"] for p in reasons.values())  # never an empty reason
    for claim_id in reasons:
        assert store.claims[claim_id].status is ClaimStatus.INFERRED


def test_llm_path_cannot_promote(pipeline):
    """False-Promotion = 0 on the LLM path: every AI-created object was an
    inferred claim or a probe; status changes came from probe evidence only."""
    store = pipeline["store"]
    ai_claims = [c for c in store.claims.values() if c.created_by is Actor.AI]
    assert len(ai_claims) == 85  # 62 hypotheses + 23 role candidates
    for evidence in store.evidence.values():
        assert evidence.actor is not Actor.AI
    # promotions happened, but only through probe evidence
    for claim in ai_claims:
        if claim.status is not ClaimStatus.INFERRED:
            assert any(
                store.evidence[eid].actor is Actor.PROBE
                for eid in claim.evidence_ids
            )


def test_verdicts_land_on_the_corpus_ground_truth(pipeline):
    """The invariants decided the roles — the epistemic heart of M4: the
    real ledger wins, the F27 decoy loses, the US ledger honestly fails on
    the F22 imbalance, and untestable claims stay inferred."""
    store = pipeline["store"]

    def role_claims(role: str, token: str):
        return [c for c in store.claims.values()
                if isinstance(c, RoleBindingClaim) and c.role == role
                and any(token in v for v in c.binding.values())]

    (gl,) = role_claims("journal", "de_erp__gl_postings")
    assert gl.status is ClaimStatus.TESTED
    (decoy,) = role_claims("journal", "buchungen_report")
    assert decoy.status is ClaimStatus.CONTRADICTED  # F27
    (us_gl,) = role_claims("journal", "us_erp__gl_postings")
    assert us_gl.status is ClaimStatus.CONTRADICTED  # F22 missing IC leg
    ic = [c for c in store.claims.values()
          if isinstance(c, RoleBindingClaim) and c.role == "intercompany"]
    assert ic and all(c.status is ClaimStatus.CONTRADICTED for c in ic)  # F22
    # claims V2 could not bind stay inferred — visible, never promoted
    unbound_ids = {cid for cid, _ in pipeline["v2"].unbindable}
    assert all(store.claims[cid].status is ClaimStatus.INFERRED
               for cid in unbound_ids)
    # semantic-only claims (T7 class among them) stay inferred
    for cid in pipeline["v2"].semantic_only:
        assert store.claims[cid].status is ClaimStatus.INFERRED


def test_lost_role_becomes_a_fachfrage_not_a_silent_discard(pipeline):
    cards = pipeline["role_cards"]
    assert len(cards) == 1
    assert "'intercompany'" in cards[0].question
    assert len(cards[0].claim_ids) == 2  # both losing candidates attached
    # the settled journal role drafts no question, and resolution is idempotent
    assert resolve_roles(pipeline["store"], pipeline["roles"]) == []


def test_call_logs_are_complete(pipeline):
    logs = sorted((pipeline["root"] / "cache" / "llm_log").glob("*.json"))
    assert len(logs) == 4  # v1, role proposals, v2 role batch, v2 claim batch
    outcomes = []
    for path in logs:
        entry = json.loads(path.read_text(encoding="utf-8"))
        assert entry["provider"] == "stub"
        assert entry["input_sha256"]
        assert entry["request"]["system"] and entry["request"]["user"]
        outcomes.append(entry["outcome"])
        if entry["outcome"] == "partial":
            assert entry["attempts"][-1]["validation_errors"]  # skips are visible
    # the recorded V1 and V2-claims answers keep a few bad items even after
    # their retry — replayed as "partial", same items skipped every run
    assert sorted(outcomes) == ["ok", "ok", "partial", "partial"]


def test_pipeline_is_idempotent(pipeline):
    """Re-running the contracts creates nothing new — claim-key dedup for
    claims; bound claims drop out of the V2 selection entirely."""
    root, store = pipeline["root"], pipeline["store"]
    again = hypothesize(root, store=store, scenario="corpus")
    assert again.claims_created == [] and again.claims_deduped == 63
    proposals = propose_role_bindings(root, roles=pipeline["roles"], store=store,
                                      scenario="corpus")
    assert proposals.claims_created == [] and proposals.claims_deduped == 23
    # only the honestly unbound claims are still selectable for V2:
    # 18 unbindable + 8 semantic-only + 1 skipped binding
    assert len(_unbound_ai_claims(store, None)) == 27


def test_built_inputs_leak_no_corpus_hints(pipeline):
    store, root = pipeline["store"], pipeline["root"]
    matrix = load_matrix(root)
    built = build_profile_context(store, matrix)
    role_built = build_role_context(store, matrix, pipeline["roles"])
    for text in (built.text, role_built.text):
        lowered = text.lower()
        for token in LEAK_TOKENS:
            assert token.lower() not in lowered, f"built input leaks {token!r}"


def test_fixtures_match_current_inputs(pipeline):
    """THE drift guard: each fixture answered a specific input; rebuild those
    inputs from the frozen corpus and compare hashes. Red here means a
    builder/prompt/profile change made the recorded answers stale — refresh
    the fixtures, do not touch this test."""
    store, root = pipeline["store"], pipeline["root"]
    matrix = load_matrix(root)

    def fixture(name: str) -> dict:
        return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))

    assert fixture("v1_hypotheses__corpus")["input_sha256"] == \
        build_profile_context(store, matrix).sha256
    assert fixture("role_binding__corpus")["input_sha256"] == \
        build_role_context(store, matrix, pipeline["roles"]).sha256

    # reconstruct the V2 batches exactly as bind_probes selects them, from a
    # claim set as it stood before binding (probes exclude claims, so take
    # all AI claims and ignore the bound-filter)
    ai_claims = sorted(
        (c for c in store.claims.values()
         if c.created_by is Actor.AI and c.predicate is not None),
        key=lambda c: c.id,
    )
    role_claims = [c for c in ai_claims if isinstance(c, RoleBindingClaim)]
    ordinary = [c for c in ai_claims
                if not isinstance(c, RoleBindingClaim) and admissible_templates(c)]
    docs = render_template_docs()
    assert fixture("v2_bind__corpus_roles")["input_sha256"] == \
        build_binding_context(store, claim_label_map(role_claims), docs).sha256
    assert fixture("v2_bind__corpus_claims")["input_sha256"] == \
        build_binding_context(store, claim_label_map(ordinary), docs).sha256
