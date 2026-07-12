"""Fingerprints: the cheap, deterministic identity of what was ingested.

These are stamped on Source records and on normalization declarations —
the seam that staleness detection (M7) will consume: same fingerprint,
same data; changed fingerprint, re-derive.
"""

import hashlib
from pathlib import Path

_DATE_TYPES = ("DATE", "TIMESTAMP")


def file_fingerprint(path: str | Path) -> dict[str, object]:
    p = Path(path)
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    return {"kind": "file", "size": p.stat().st_size, "sha256": digest}


def schema_hash(columns: list[tuple[str, str]]) -> str:
    """Stable hash over ordered (name, type) pairs."""
    payload = "\n".join(f"{name}\t{dtype}" for name, dtype in columns)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def table_fingerprint(con, view: str) -> dict[str, object]:
    """Row count, schema hash and max date/timestamp of one view."""
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
        "max_date": max_date,
    }
