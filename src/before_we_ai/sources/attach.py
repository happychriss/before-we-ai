"""Build the analysis catalog: every source becomes views in one DuckDB.

The cache database (``cache/analysis.duckdb``) is a derivative — always
deletable, always reconstructible from ``before-ai.yaml`` plus the
sources themselves. View naming is uniform: ``<source>__<table>``.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import yaml
from pydantic import BaseModel

from before_we_ai.sources.excel import read_workbook, sheet_to_parquet
from before_we_ai.sources.fingerprint import file_fingerprint, table_fingerprint
from before_we_ai.store.layout import CONFIG_FILE

RULE_CSV_ALL_VARCHAR = "csv_read_all_varchar"

_TABLE_KINDS = ("duckdb", "csv", "xlsx")


class SourceSpec(BaseModel):
    """One entry under ``sources:`` in before-ai.yaml."""

    name: str
    kind: str  # duckdb | csv | xlsx | pdf
    location: str

    def resolve(self, root: Path) -> Path:
        path = Path(self.location)
        return path if path.is_absolute() else root / path


@dataclass
class CatalogEntry:
    spec: SourceSpec
    file_fingerprint: dict
    views: dict[str, dict] = field(default_factory=dict)  # view -> table fingerprint
    decisions: list[dict] = field(default_factory=list)  # each carries a "table" key


def _slug(name: str) -> str:
    return re.sub(r"[^0-9a-zA-Z]+", "_", name.strip()).strip("_").lower()


def load_specs(root: str | Path) -> list[SourceSpec]:
    """The ``sources:`` entries of a project's before-ai.yaml."""
    config = yaml.safe_load((Path(root) / CONFIG_FILE).read_text(encoding="utf-8")) or {}
    return [SourceSpec.model_validate(entry) for entry in config.get("sources", [])]


def open_catalog(root: str | Path):
    """Open the analysis catalog, rebuilding its views.

    Views over ATTACHed databases do not survive a fresh connection, so
    every consumer goes through here: connect to the cache database and
    re-run the (idempotent, cheap) catalog build. The cache stays what it
    is — a derivative.
    """
    root = Path(root)
    (root / "cache").mkdir(exist_ok=True)
    con = duckdb.connect(str(root / "cache" / "analysis.duckdb"))
    build_catalog(root, load_specs(root), con)
    return con


def view_name(source: str, table: str) -> str:
    return f"{_slug(source)}__{_slug(table)}"


def build_catalog(root: str | Path, specs: list[SourceSpec], con) -> list[CatalogEntry]:
    root = Path(root)
    entries = []
    for spec in specs:
        path = spec.resolve(root)
        entry = CatalogEntry(spec=spec, file_fingerprint=file_fingerprint(path))
        if spec.kind == "duckdb":
            alias = f"src_{_slug(spec.name)}"
            con.execute(f"ATTACH IF NOT EXISTS '{path}' AS {alias} (READ_ONLY)")
            tables = [r[0] for r in con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = ? ORDER BY table_name", [alias],
            ).fetchall()]
            for table in tables:
                view = view_name(spec.name, table)
                con.execute(
                    f'CREATE OR REPLACE VIEW "{view}" AS SELECT * FROM {alias}."{table}"'
                )
                entry.views[view] = table_fingerprint(con, view)
        elif spec.kind == "csv":
            view = view_name(spec.name, path.stem)
            con.execute(
                f"CREATE OR REPLACE VIEW \"{view}\" AS "
                f"SELECT * FROM read_csv('{path}', all_varchar=true)"
            )
            entry.views[view] = table_fingerprint(con, view)
            entry.decisions.append({
                "table": view,
                "column": "*",
                "rule": RULE_CSV_ALL_VARCHAR,
                "example": {"before": "sniffed types", "after": "all VARCHAR"},
            })
        elif spec.kind == "xlsx":
            for sheet in read_workbook(path):
                view = view_name(spec.name, sheet.sheet)
                parquet = root / "cache" / "normalized" / f"{view}.parquet"
                sheet_to_parquet(con, sheet, parquet)
                con.execute(
                    f"CREATE OR REPLACE VIEW \"{view}\" AS SELECT * FROM '{parquet}'"
                )
                entry.views[view] = table_fingerprint(con, view)
                entry.decisions.extend({**d, "table": view} for d in sheet.decisions)
        elif spec.kind == "pdf":
            pass  # fingerprinted Source only; the document pipeline is M5
        else:
            raise ValueError(f"unknown source kind: {spec.kind!r} ({spec.name})")
        entries.append(entry)
    return entries
