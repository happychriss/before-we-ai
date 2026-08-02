"""The chunk table and its full-text index — retrieval, never judgement.

Lives in the same disposable catalog as everything else measured
(``cache/analysis.duckdb``): delete it, re-read the documents, get the
same table back.

**FTS is required, never quietly replaced.** DuckDB ships full-text search
as an extension, and if it is missing the honest response is to say so.
A ``LIKE`` fallback would keep the suite green while selecting *different
chunks* — and the selected chunks are V3's prompt, so a silent fallback
would mean the same project asking the model a different question
depending on which machine it ran on. That is precisely the class of
invisible drift the fixture pins exist to catch.
"""

from before_we_ai.documents.chunk import Chunk

CHUNK_TABLE = "document_chunks"

# Ordering rule wherever scores tie: the id, so retrieval output cannot
# depend on row order inside DuckDB.
_TIE_BREAK = "score DESC, id ASC"


class FullTextSearchUnavailable(RuntimeError):
    """DuckDB's fts extension is not installed on this machine."""


def load_fts(con) -> None:
    try:
        con.execute("LOAD fts")
    except Exception as exc:  # duckdb raises several types here
        raise FullTextSearchUnavailable(
            "DuckDB's full-text search extension is not available. "
            "Install it once, with network access: "
            "python -c \"import duckdb; duckdb.connect().execute('INSTALL fts')\". "
            "Document retrieval deliberately has no fallback — a substitute "
            "would select different chunks and silently change what the "
            "model is asked."
        ) from exc


def build_chunk_index(con, chunks: list[Chunk]) -> int:
    """(Re)build the chunk table and its FTS index. Idempotent."""
    load_fts(con)
    con.execute(f"""
        CREATE OR REPLACE TABLE {CHUNK_TABLE} (
            id VARCHAR PRIMARY KEY, source VARCHAR, page INTEGER,
            seq INTEGER, kind VARCHAR, text VARCHAR,
            start_char INTEGER, end_char INTEGER
        )
    """)
    if chunks:
        con.executemany(
            f"INSERT INTO {CHUNK_TABLE} VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(c.id, c.source, c.page, c.seq, c.kind, c.text, c.start, c.end)
             for c in sorted(chunks, key=lambda c: c.id)],
        )
    con.execute(
        f"PRAGMA create_fts_index('{CHUNK_TABLE}', 'id', 'text', overwrite=1)"
    )
    return len(chunks)


def search(con, query: str, limit: int = 5) -> list[str]:
    """Chunk ids best matching a query string, best first."""
    rows = con.execute(
        f"SELECT id, score FROM ("
        f"  SELECT id, fts_main_{CHUNK_TABLE}.match_bm25(id, ?) AS score "
        f"  FROM {CHUNK_TABLE}"
        f") WHERE score IS NOT NULL ORDER BY {_TIE_BREAK} LIMIT ?",
        [query, limit],
    ).fetchall()
    return [row[0] for row in rows]


def load_chunks(con, ids: list[str] | None = None) -> list[Chunk]:
    """Chunks back out of the catalog, always in id order."""
    sql = (f"SELECT id, source, page, seq, kind, text, start_char, end_char "
           f"FROM {CHUNK_TABLE}")
    params: list = []
    if ids is not None:
        if not ids:
            return []
        sql += f" WHERE id IN ({', '.join('?' * len(ids))})"
        params = list(ids)
    sql += " ORDER BY id"
    return [
        Chunk(id=r[0], source=r[1], page=r[2], seq=r[3], kind=r[4],
              text=r[5], start=r[6], end=r[7])
        for r in con.execute(sql, params).fetchall()
    ]


def retrieve(con, queries: list[str], per_query: int = 5,
             cap: int = 24) -> list[Chunk]:
    """Chunks for a set of queries, deduplicated and in document order.

    The union is capped and then re-sorted by position, so a marginal
    score change reorders nothing downstream: V3 always reads a document
    the way a human would, top to bottom.
    """
    seen: list[str] = []
    for query in queries:
        for chunk_id in search(con, query, per_query):
            if chunk_id not in seen:
                seen.append(chunk_id)
    chunks = load_chunks(con, seen[:cap])
    return sorted(chunks, key=lambda c: (c.source, c.page, c.seq))
