"""Retrieval must be repeatable, because retrieval is part of the prompt.

Which chunks come back decides what V3 is shown. If that set could shift
between two runs over the same documents, the fixture hash would pin
nothing and offline replay would drift while staying green.
"""

import duckdb
import pytest

from before_we_ai.documents.chunk import Chunk
from before_we_ai.documents.index import (
    CHUNK_TABLE,
    FullTextSearchUnavailable,
    build_chunk_index,
    load_chunks,
    load_fts,
    retrieve,
    search,
)

pytestmark = pytest.mark.unit


def _chunk(cid, source, page, seq, text, kind="text"):
    return Chunk(id=cid, source=source, page=page, seq=seq, kind=kind,
                 text=text, start=0, end=len(text))


@pytest.fixture
def con():
    connection = duckdb.connect()
    yield connection
    connection.close()


@pytest.fixture
def indexed(con):
    chunks = [
        _chunk("policy:p1:0", "policy", 1, 0,
               "Credit amounts are booked as negative numbers."),
        _chunk("policy:p1:1", "policy", 1, 1,
               "Revenue equals accounts 4000 to 4999 less contra accounts."),
        _chunk("report:p1:0", "report", 1, 0,
               "Quarterly revenue performance across all entities."),
        _chunk("report:p1:1", "report", 1, 1,
               "EUR 2,847,000", kind="chart"),
    ]
    build_chunk_index(con, chunks)
    return chunks


def test_fts_is_available_in_this_environment(con):
    """The pipeline depends on it, so the suite states the dependency."""
    load_fts(con)


def test_search_finds_the_chunk_that_carries_the_words(con, indexed):
    assert search(con, "credit amounts negative") == ["policy:p1:0"]


def test_search_is_repeatable(con, indexed):
    assert search(con, "revenue", 5) == search(con, "revenue", 5)


def test_ties_break_on_id_so_row_order_cannot_leak_in(con):
    """Two identical texts score identically — the id decides, not DuckDB."""
    build_chunk_index(con, [
        _chunk("b:p1:0", "b", 1, 0, "identical wording here"),
        _chunk("a:p1:0", "a", 1, 0, "identical wording here"),
    ])
    assert search(con, "identical wording") == ["a:p1:0", "b:p1:0"]


def test_retrieval_returns_document_order_not_score_order(con, indexed):
    """A reader reads top to bottom; a marginal score must not reshuffle."""
    chunks = retrieve(con, ["revenue", "credit amounts"], per_query=5)
    assert [c.id for c in chunks] == sorted(c.id for c in chunks)


def test_retrieval_deduplicates_across_queries(con, indexed):
    chunks = retrieve(con, ["revenue", "revenue accounts", "revenue"], per_query=5)
    assert len({c.id for c in chunks}) == len(chunks)


def test_retrieval_respects_the_cap(con, indexed):
    assert len(retrieve(con, ["revenue", "credit"], per_query=5, cap=1)) == 1


def test_chunks_survive_the_round_trip_including_their_kind(con, indexed):
    stored = {c.id: c for c in load_chunks(con)}
    assert stored["report:p1:1"].kind == "chart"
    assert stored["report:p1:1"].text == "EUR 2,847,000"


def test_rebuilding_the_index_replaces_rather_than_appends(con, indexed):
    build_chunk_index(con, indexed)
    assert con.execute(f"SELECT count(*) FROM {CHUNK_TABLE}").fetchone()[0] == len(indexed)


def test_an_empty_project_indexes_cleanly(con):
    assert build_chunk_index(con, []) == 0
    assert search(con, "anything") == []


def test_missing_fts_is_an_error_that_says_what_to_do():
    """No silent fallback: a substitute would change the prompt invisibly."""
    class Unequipped:
        def execute(self, sql, *args, **kwargs):
            raise RuntimeError("Extension 'fts' not found")

    with pytest.raises(FullTextSearchUnavailable) as caught:
        load_fts(Unequipped())
    assert "INSTALL fts" in str(caught.value)
