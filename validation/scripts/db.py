#!/usr/bin/env python3
"""Interactive SQL shell over the walkthrough project's DuckDB catalog.

The catalog's de_erp__*/us_erp__* views sit over ATTACHed databases which
a raw connection does not re-attach — this shell opens the catalog through
sources.open_catalog(), so every view works.

    db.sh                          interactive shell (quit with \\q or Ctrl-D)
    db.sh "select ..."             run one query and exit
    db.sh --project DIR ...        another project (default: validation/data/project)
"""

import argparse
import sys
from pathlib import Path

from before_we_ai.sources import open_catalog

DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "data" / "project"


def run(con, query: str) -> None:
    try:
        relation = con.sql(query)
        if relation is not None:
            relation.show(max_rows=50)
    except Exception as exc:  # keep the shell alive on bad SQL
        print(f"error: {exc}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query", nargs="?", help="one-shot SQL; omit for a shell")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    args = parser.parse_args()

    if not (args.project / "cache" / "analysis.duckdb").is_file():
        sys.exit(f"no catalog under {args.project} — run 1-scan.sh first")
    con = open_catalog(args.project)
    try:
        if args.query:
            run(con, args.query)
            return
        print(f"catalog: {args.project / 'cache' / 'analysis.duckdb'}\n"
              "list views:  select view_name from duckdb_views() where not internal;\n"
              "quit:        \\q or Ctrl-D")
        while True:
            try:
                query = input("sql> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not query:
                continue
            if query in (r"\q", "exit", "quit"):
                break
            run(con, query)
    finally:
        con.close()


if __name__ == "__main__":
    main()
