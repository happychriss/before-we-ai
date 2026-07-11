"""Source connection & normalization — the tool's senses.

Everything here observes and declares; nothing here can promote a claim.
Normalization decisions are logged as declaration evidence, fingerprints
are computed for later staleness detection, and all values meet the rest
of the system in one canonical text form.
"""

from before_we_ai.sources.attach import SourceSpec, build_catalog
from before_we_ai.sources.canonical import canonical_sql_expr, canonicalize, canonical_text
from before_we_ai.sources.excel import read_workbook, sheet_to_parquet
from before_we_ai.sources.fingerprint import file_fingerprint, schema_hash, table_fingerprint

__all__ = [
    "SourceSpec",
    "build_catalog",
    "canonical_sql_expr",
    "canonical_text",
    "canonicalize",
    "file_fingerprint",
    "read_workbook",
    "schema_hash",
    "sheet_to_parquet",
    "table_fingerprint",
]
