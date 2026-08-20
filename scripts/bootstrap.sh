#!/usr/bin/env bash
# One command to go from a fresh clone to a green suite. Idempotent — run it
# again after a pull and it repairs whatever drifted.
#
#     ./scripts/bootstrap.sh            # venv + deps + fts + verify
#     ./scripts/bootstrap.sh --locked   # exact pins from requirements.lock
#
# Needs network once, for pip and for DuckDB's full-text-search extension.
# Everything after that — the whole test suite, the validation walkthrough —
# runs offline and needs no API key.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

LOCKED=0
[ "${1:-}" = "--locked" ] && LOCKED=1

PY="${PYTHON:-python3}"
"$PY" - <<'CHECK' || { echo "bootstrap: need Python 3.11 or newer" >&2; exit 1; }
import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)
CHECK

echo "==> venv at $REPO/.venv"
[ -d .venv ] || "$PY" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

echo "==> dependencies"
if [ "$LOCKED" = "1" ]; then
    python -m pip install --quiet -r requirements.lock
    python -m pip install --quiet --no-deps -e .
else
    python -m pip install --quiet -e ".[dev]"
fi

# DuckDB's FTS extension is per DuckDB version and lives in the *user's* home
# (~/.duckdb/extensions/<version>/), not in the venv — so a new venv can still
# find an already-installed one, and a duckdb bump silently loses it.
echo "==> DuckDB full-text search extension"
python - <<'FTS'
import sys, duckdb
con = duckdb.connect()
try:
    con.execute("LOAD fts")
    print(f"    already installed for duckdb {duckdb.__version__}")
except Exception:
    try:
        con.execute("INSTALL fts")
        con.execute("LOAD fts")
        print(f"    installed for duckdb {duckdb.__version__}")
    except Exception as exc:
        sys.exit(
            "\n"
            "    FAILED to install DuckDB's full-text search extension.\n"
            f"    duckdb {duckdb.__version__}: {exc}\n\n"
            "    This needs network access once. It is not optional and there is\n"
            "    no fallback on purpose: a LIKE-based substitute would select\n"
            "    different document chunks, and the selected chunks are what the\n"
            "    model is asked about (src/before_we_ai/documents/index.py).\n\n"
            "    Fix, in order of likelihood:\n"
            "      1. no network / proxy — retry with access to extensions.duckdb.org\n"
            "      2. behind a proxy — export HTTPS_PROXY and re-run\n"
            "      3. fully offline machine — use the Docker image instead:\n"
            "           docker compose run --rm suite\n"
            "         it bakes the extension in at build time.\n"
        )
FTS

echo "==> verifying (unit lane)"
python -m pytest -q -m unit

cat <<'DONE'

Ready. From here:

    source .venv/bin/activate
    python -m pytest -q            # the gate — everything must pass, offline
    validation/README.md           # the guided tour of a seeded landscape

DONE
