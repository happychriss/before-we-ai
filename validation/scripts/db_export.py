#!/usr/bin/env python3
"""Export the catalog as a self-contained DuckDB file for external tools.

``cache/analysis.duckdb`` holds only VIEWS: over ATTACHed ERP databases and
over CSV/Parquet files, all referenced by *container* absolute paths
(/workspace/...). A tool on the host (DataGrip) opens the file but cannot
resolve those paths — "No files found that match the pattern ...".

This writes every view out as a real TABLE into one new database with no
external references, so any DuckDB client can browse it anywhere.
It is a snapshot: re-export after a re-scan.
"""

import argparse
from pathlib import Path

import duckdb

from before_we_ai.sources.attach import build_catalog, load_specs

DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "data" / "project"


def export(project: Path, out: Path) -> Path:
    if not (project / "cache" / "analysis.duckdb").is_file():
        raise SystemExit(f"no catalog under {project} — run 1-scan.sh first")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)

    # Build the catalog into a throwaway in-memory connection rather than
    # opening cache/analysis.duckdb: a DuckDB client on the host (DataGrip)
    # holds an exclusive lock on that file, and the build is cheap anyway.
    con = duckdb.connect()
    try:
        build_catalog(project, load_specs(project), con)
        views = [row[0] for row in con.execute(
            "select view_name from duckdb_views() where not internal "
            "order by view_name").fetchall()]
        con.execute(f"ATTACH '{out}' AS export_db")
        for view in views:
            con.execute(f'CREATE TABLE export_db."{view}" AS '
                        f'SELECT * FROM "{view}"')
            count = con.execute(
                f'SELECT count(*) FROM export_db."{view}"').fetchone()[0]
            print(f"  {view:45s} {count:>8,} rows")
        con.execute("DETACH export_db")
    finally:
        con.close()

    # prove it stands alone: open it with a bare connection, no attaches
    check = duckdb.connect(str(out), read_only=True)
    try:
        tables = check.execute("select count(*) from duckdb_tables()").fetchone()[0]
    finally:
        check.close()
    print(f"\n{tables} tables, self-contained: {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("-o", "--output", type=Path,
                        help="default: <project>/cache/export.duckdb")
    args = parser.parse_args()
    out = args.output or args.project / "cache" / "export.duckdb"
    export(args.project, out)


if __name__ == "__main__":
    main()
