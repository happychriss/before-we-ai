"""The proposed-only guardrail holds structurally through the LLM path.

Nothing here is new enforcement — the M1 core owns the law. These tests
prove the LLM layer rides on it: AI-born claims start proposed, AI cannot
author promoting evidence, and model-facing code receives only proposal
capabilities."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from before_we_ai import scan
from before_we_ai.llm import (
    ask,
    hypothesize,
    load_domain_guide,
    plan_checks,
    propose_mappings,
)
from before_we_ai.llm.mapping import ProfileIndex, hypothesis_to_claim
from before_we_ai.llm.schemas import Hypothesis
from before_we_ai.core import Actor, ClaimStatus, EvidenceType, resolve_status
from before_we_ai.core.enums import CheckVerdict
from before_we_ai.core.objects import DataProfile, EvidenceRecord
from before_we_ai.store import ProjectStore, ProposalStore, init_project

pytestmark = pytest.mark.contract

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm"
DOMAIN_GUIDE_FILE = (
    Path(__file__).resolve().parents[1] / "fixtures" / "domain_guide_finance.yaml"
)

SOURCES = [
    {
        "name": "de_erp",
        "kind": "duckdb",
        "location": str(CORPUS / "DE" / "erp.duckdb"),
    },
    {
        "name": "us_erp",
        "kind": "duckdb",
        "location": str(CORPUS / "US" / "erp.duckdb"),
    },
    {
        "name": "kunden_migration",
        "kind": "xlsx",
        "location": str(CORPUS / "kunden_migration.xlsx"),
    },
    {
        "name": "marketing_grouping",
        "kind": "xlsx",
        "location": str(CORPUS / "marketing_grouping.xlsx"),
    },
    {
        "name": "kontakte_aussendienst",
        "kind": "xlsx",
        "location": str(CORPUS / "kontakte_aussendienst.xlsx"),
    },
    {
        "name": "buchungen_report",
        "kind": "csv",
        "location": str(CORPUS / "buchungen_report.csv"),
    },
    {
        "name": "management_report",
        "kind": "pdf",
        "location": str(CORPUS / "management_report.pdf"),
    },
]

DEMO_QUESTION = "Can these files reliably produce actual P&L by entity and month?"


@pytest.fixture()
def hypothesized_claim(tmp_path):
    store = ProjectStore(init_project(tmp_path / "p"), create=True)
    store.save_profile(DataProfile(
        source_id="s1", table="a__t", column="c",
        stats={"duckdb_type": "BIGINT", "value_class": "integer_like",
               "row_count": 1, "null_count": 0, "distinct_count": 1},
    ))
    hypothesis = Hypothesis(
        statement="t.c is a unique key",
        predicate="unique_key",
        params={"table": "a__t", "key_columns": ["c"]},
        columns=["a__t.c"],
        rationale="distinct == rows",
    )
    return hypothesis_to_claim(hypothesis, ProfileIndex(store))


@pytest.fixture(scope="module")
def llm_stage_evidence(tmp_path_factory):
    """Evidence added by the model-facing stages, excluding scan declarations."""
    root = init_project(tmp_path_factory.mktemp("guardrail") / "corpus")
    config_data = yaml.safe_load(
        (root / "before-ai.yaml").read_text(encoding="utf-8")
    )
    config_data["sources"] = SOURCES
    config_data["llm"] = {
        "offline": True,
        "fixtures_dir": str(FIXTURES),
        "domain_guide_file": str(DOMAIN_GUIDE_FILE),
    }
    (root / "before-ai.yaml").write_text(
        yaml.safe_dump(config_data, sort_keys=False), encoding="utf-8"
    )

    scan(root)
    store = ProjectStore(root)
    evidence_before = set(store.evidence)
    guide = load_domain_guide(DOMAIN_GUIDE_FILE)

    ask(root, DEMO_QUESTION, guide=guide, store=store, scenario="corpus")
    hypothesize(root, store=store, scenario="corpus")
    propose_mappings(root, roles=guide, store=store, scenario="corpus")
    plan_checks(root, store=store, scenario="corpus")

    return [
        record
        for evidence_id, record in store.evidence.items()
        if evidence_id not in evidence_before
    ]


def test_hypothesized_claims_start_and_stay_proposed(hypothesized_claim):
    assert hypothesized_claim.status is ClaimStatus.PROPOSED
    assert resolve_status(hypothesized_claim, []) is ClaimStatus.PROPOSED


def test_ai_cannot_author_promoting_evidence(hypothesized_claim):
    with pytest.raises(ValidationError, match="authored by a check"):
        EvidenceRecord(type=EvidenceType.CHECK_RESULT, actor=Actor.AI,
                       claim_id=hypothesized_claim.id, verdict=CheckVerdict.PASS)
    with pytest.raises(ValidationError, match="must come from a human"):
        EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=Actor.AI,
                       claim_id=hypothesized_claim.id)
    with pytest.raises(ValidationError, match="must come from a human"):
        EvidenceRecord(type=EvidenceType.TESTIMONIAL, actor=Actor.AI,
                       claim_id=hypothesized_claim.id, statement="trust me")


def test_llm_stages_write_only_system_declarations(llm_stage_evidence):
    assert llm_stage_evidence
    assert all(
        record.type is EvidenceType.DECLARATION
        and record.actor is Actor.SYSTEM
        for record in llm_stage_evidence
    )


def test_proposal_store_hides_general_evidence_writes(tmp_path):
    store = ProjectStore(init_project(tmp_path / "facade"))
    proposals = ProposalStore(store)

    assert not hasattr(proposals, "add_evidence")
    assert not hasattr(proposals, "mark_evidence_stale")
