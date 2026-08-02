"""Reading documents is measurement — it may not believe anything.

``read_documents`` is the document twin of ``scan``, and it inherits the
same law: a document that has been read produces a profile and zero
claims. A policy PDF stating a sign convention does not make the
convention true; it makes it available to be *proposed* one stage later,
where proposals cannot promote themselves.
"""

from pathlib import Path

import duckdb
import pymupdf
import pytest
import yaml

from before_we_ai.documents import CHUNK_TABLE, read_documents
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.integration


def _pdf(path: Path, lines: list[str]) -> Path:
    document = pymupdf.open()
    page = document.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 100 + index * 20), line)
    document.save(str(path))
    document.close()
    return path


@pytest.fixture
def project(tmp_path):
    root = init_project(tmp_path / "proj")
    _pdf(root / "sources" / "policy.pdf",
         ["Accounting Policy", "Credit amounts are booked as negative numbers."])
    _pdf(root / "sources" / "rebates.pdf",
         ["Master Rebate Agreement", "Annual volume above EUR 500,000 earns 2%."])
    config = yaml.safe_load((root / "before-ai.yaml").read_text())
    config["sources"] = [
        {"name": "policy", "kind": "pdf", "location": "sources/policy.pdf"},
        {"name": "rebates", "kind": "pdf", "location": "sources/rebates.pdf"},
    ]
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False))
    return root


def test_reading_documents_creates_no_claims(project):
    read_documents(project)
    assert ProjectStore(project).claims == {}


def test_reading_documents_creates_no_evidence(project):
    """Not even weak evidence: an anchor is V3's to author, not the reader's."""
    read_documents(project)
    assert ProjectStore(project).evidence == {}


def test_every_document_gets_a_profile_and_a_source(project):
    result = read_documents(project)
    store = ProjectStore(project)
    assert result.profiles_written == 2
    assert {p.document for p in store.documents.values()} == {"policy", "rebates"}
    assert {s.name for s in store.sources.values()} == {"policy", "rebates"}


def test_the_profile_counts_what_was_found(project):
    read_documents(project)
    store = ProjectStore(project)
    policy = next(p for p in store.documents.values() if p.document == "policy")
    assert policy.pages == 1
    assert policy.chunk_count >= 1
    assert policy.char_count > 0
    assert sum(policy.kinds.values()) == policy.chunk_count


def test_profiles_and_column_profiles_share_a_directory_without_confusion(project):
    """Both are measurements; the store must read each back as itself."""
    read_documents(project)
    store = ProjectStore(project)
    assert store.profiles == {}  # no columns here — only documents
    assert len(store.documents) == 2


def test_rereading_is_idempotent(project):
    first = read_documents(project)
    ids = {p.document: p.id for p in ProjectStore(project).documents.values()}
    second = read_documents(project)
    again = {p.document: p.id for p in ProjectStore(project).documents.values()}
    assert first.chunks == second.chunks
    assert ids == again  # a re-read keeps identity, it does not pile up


def test_the_chunk_index_is_queryable_after_reading(project):
    read_documents(project)
    con = duckdb.connect(str(project / "cache" / "analysis.duckdb"))
    try:
        rows = con.execute(
            f"SELECT id FROM {CHUNK_TABLE} ORDER BY id"
        ).fetchall()
    finally:
        con.close()
    assert [r[0] for r in rows] == sorted(r[0] for r in rows)
    assert any(r[0].startswith("policy:") for r in rows)


def test_the_cache_is_disposable(project):
    """Delete it, read again, get the same thing back."""
    first = read_documents(project)
    (project / "cache" / "analysis.duckdb").unlink()
    second = read_documents(project)
    assert first.chunks == second.chunks


def test_scan_leaves_documents_to_the_document_pipeline(project):
    """One source, one owner.

    Both stages used to write a Source record for a PDF, in two different
    fingerprint shapes — and staleness compares fingerprints, so whichever
    ran last decided what "unchanged" meant. Documents belong to stage 2c.
    """
    from before_we_ai import scan

    result = scan(project)
    assert result.source_ids == {}
    assert ProjectStore(project).sources == {}

    read_documents(project)
    store = ProjectStore(project)
    assert {s.name for s in store.sources.values()} == {"policy", "rebates"}
    assert set(next(iter(store.sources.values())).fingerprint) == {"file", "chunks"}


def test_a_project_without_documents_reads_cleanly(tmp_path):
    root = init_project(tmp_path / "empty")
    result = read_documents(root)
    assert result.chunks == 0
    assert result.profiles_written == 0
