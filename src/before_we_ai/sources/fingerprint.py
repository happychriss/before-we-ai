"""Fingerprints: the cheap, deterministic identity of what was ingested.

These are stamped on Source records, on normalization declarations and on
every check result — the seam `before_we_ai.staleness` consumes: same
fingerprint, same data; changed fingerprint, what was read against it is
stale.

Because staleness reads them, a fingerprint that misses a change is worse
than no fingerprint at all: it promises freshness that is not there. Row
count, schema and the latest date catch a table that grew, was reshaped or
was extended — they say nothing about a value edited in place, which is
the ordinary way a bookkeeping correction arrives. ``content_hash`` covers
that, in one pass and without a sort.
"""

import hashlib
from pathlib import Path

_DATE_TYPES = ("DATE", "TIMESTAMP")


def file_fingerprint(path: str | Path) -> dict[str, object]:
    p = Path(path)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"kind": "file", "size": p.stat().st_size, "sha256": digest}


def text_fingerprint(text: str) -> str:
    """The identity of one passage — what an anchor's quote was found in."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def schema_hash(columns: list[tuple[str, str]]) -> str:
    """Stable hash over ordered (name, type) pairs."""
    payload = "\n".join(f"{name}\t{dtype}" for name, dtype in columns)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def content_hash(con, view: str) -> str | None:
    """One digest over every row of a view, order-independent.

    ``md5_number`` rather than DuckDB's own ``hash``: MD5 is specified, so
    the number survives a DuckDB upgrade, and an upgrade must not make the
    whole store look stale. XOR rather than a sorted aggregate: one pass,
    no sort, over tables that can be large.

    The blind spot of XOR, stated rather than hidden: two *identical* rows
    cancel each other. Deleting an exact duplicate pair therefore leaves
    the digest unchanged — but not ``row_count``, which is recorded beside
    it, and staleness compares the whole fingerprint.

    None for an empty view, which is what XOR over no rows means.
    """
    row = con.execute(
        f'SELECT bit_xor(md5_number(t::VARCHAR)) FROM "{view}" AS t'
    ).fetchone()
    return None if row[0] is None else str(row[0])


def table_fingerprint(con, view: str) -> dict[str, object]:
    """Row count, schema hash, content digest and max date of one view."""
    columns = [(r[0], r[1]) for r in con.execute(f'DESCRIBE "{view}"').fetchall()]
    row_count = con.execute(f'SELECT count(*) FROM "{view}"').fetchone()[0]
    date_cols = [
        name for name, dtype in columns
        if dtype.upper().split("(")[0].strip().startswith(_DATE_TYPES)
    ]
    max_date = None
    if date_cols:
        greatest = ", ".join(f'max("{c}")' for c in date_cols)
        values = [v for v in con.execute(f'SELECT {greatest} FROM "{view}"').fetchone()
                  if v is not None]
        if values:
            max_date = max(str(v) for v in values)
    return {
        "kind": "table",
        "row_count": row_count,
        "schema_hash": schema_hash(columns),
        "content_hash": content_hash(con, view),
        "max_date": max_date,
    }
