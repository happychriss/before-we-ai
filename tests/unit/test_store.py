"""File repository: layout, round-trips, append-only, integrity, checkpoints."""

import subprocess

import pytest

from before_we_ai.model import (
    Actor,
    ClaimStatus,
    ColumnProfile,
    ConceptClaim,
    EvidenceRecord,
    EvidenceType,
    ProbeVerdict,
    QuestionCard,
    RoleBindingClaim,
    Source,
    create_claim,
)
from before_we_ai.store import (
    AppendOnlyViolation,
    PROJECT_DIRS,
    ProjectStore,
    check_integrity,
    checkpoint,
    init_project,
    is_project,
)


@pytest.fixture
def store(tmp_path):
    return ProjectStore(tmp_path / "proj", create=True)


class TestLayout:
    def test_init_creates_contract_dirs_and_config(self, tmp_path):
        root = init_project(tmp_path / "proj")
        for d in PROJECT_DIRS:
            assert (root / d).is_dir()
        assert is_project(root)
        assert not is_project(tmp_path)

    def test_init_is_idempotent(self, tmp_path):
        init_project(tmp_path / "proj")
        (tmp_path / "proj" / "claims" / "keep.yaml").write_text("statement: x\n")
        init_project(tmp_path / "proj")
        assert (tmp_path / "proj" / "claims" / "keep.yaml").exists()

    def test_opening_a_non_project_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            ProjectStore(tmp_path / "nowhere")


class TestRoundTrip:
    def test_all_object_types_survive_reload(self, store):
        claim = create_claim("plain claim", Actor.AI)
        concept = ConceptClaim(
            statement="revenue means external revenue",
            created_by=Actor.AI,
            term="revenue",
            definition="external, net, after rebates",
        )
        binding = RoleBindingClaim(
            statement="journal role binds to a postings table",
            created_by=Actor.AI,
            role="journal",
            binding={"table": "postings_x"},
        )
        record = EvidenceRecord(
            type=EvidenceType.PROBE_RESULT,
            actor=Actor.PROBE,
            verdict=ProbeVerdict.PASS,
            claim_id=claim.id,
        )
        card = QuestionCard(question="does it close?", claim_ids=[claim.id])
        source = Source(name="erp", kind="duckdb", location="sources/erp.duckdb")
        profile = ColumnProfile(
            source_id=source.id, table="t", column="c", stats={"cardinality": 42}
        )

        for c in (claim, concept, binding):
            store.save_claim(c)
        store.add_evidence(record)
        store.save_question(card)
        store.save_source(source)
        store.save_profile(profile)

        reloaded = ProjectStore(store.root)
        assert reloaded.claims[claim.id] == claim
        assert type(reloaded.claims[concept.id]) is ConceptClaim
        assert reloaded.claims[concept.id].term == "revenue"
        assert type(reloaded.claims[binding.id]) is RoleBindingClaim
        assert reloaded.claims[binding.id].binding == {"table": "postings_x"}
        assert reloaded.evidence[record.id] == record
        assert reloaded.questions[card.id] == card
        assert reloaded.sources[source.id] == source
        assert reloaded.profiles[profile.id] == profile

    def test_claim_status_persists(self, store):
        claim = create_claim("x", Actor.AI)
        claim.status = ClaimStatus.UNRESOLVED
        store.save_claim(claim)
        assert ProjectStore(store.root).claims[claim.id].status is ClaimStatus.UNRESOLVED


class TestAppendOnly:
    def test_rewriting_evidence_raises(self, store):
        record = EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)
        store.add_evidence(record)
        with pytest.raises(AppendOnlyViolation):
            store.add_evidence(record)

    def test_rewriting_raises_even_after_reload(self, store):
        record = EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)
        store.add_evidence(record)
        reloaded = ProjectStore(store.root)
        with pytest.raises(AppendOnlyViolation):
            reloaded.add_evidence(record)

    def test_mark_stale_is_the_single_permitted_mutation(self, store):
        record = EvidenceRecord(type=EvidenceType.DECLARATION, actor=Actor.AI)
        store.add_evidence(record)
        store.mark_evidence_stale(record.id)
        reloaded = ProjectStore(store.root)
        assert reloaded.evidence[record.id].stale is True


class TestIntegrity:
    def test_clean_project_has_no_findings(self, store):
        claim = create_claim("x", Actor.AI)
        record = EvidenceRecord(
            type=EvidenceType.DECLARATION, actor=Actor.AI, claim_id=claim.id
        )
        claim.evidence_ids = [record.id]
        store.save_claim(claim)
        store.add_evidence(record)
        store.save_question(QuestionCard(question="q", claim_ids=[claim.id]))
        assert check_integrity(store) == []

    def test_dangling_references_are_found(self, store):
        claim = create_claim("x", Actor.AI, depends_on=["01GONE0000000000000000GONE"])
        claim.evidence_ids = ["01GONE0000000000000000GON2"]
        store.save_claim(claim)
        store.save_question(
            QuestionCard(question="q", claim_ids=["01GONE0000000000000000GON3"])
        )
        store.save_profile(
            ColumnProfile(source_id="01GONE0000000000000000GON4", table="t", column="c")
        )
        findings = check_integrity(store)
        assert len(findings) == 4
        assert any("dangling evidence" in f for f in findings)
        assert any("dangling dependency" in f for f in findings)


class TestCheckpoint:
    def test_noop_outside_git(self, store):
        assert checkpoint(store.root, "msg") is False

    def test_commits_inside_git(self, tmp_path):
        root = init_project(tmp_path / "proj")
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
        store = ProjectStore(root)
        store.save_claim(create_claim("x", Actor.AI))
        assert checkpoint(root, "checkpoint: first claim") is True
        assert checkpoint(root, "nothing changed") is False
