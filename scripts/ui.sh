#!/usr/bin/env bash
# Start the demo web app on http://127.0.0.1:8787 — offline, no API key.
#
#     ./scripts/ui.sh              # default port
#     ./scripts/ui.sh --port 9000
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
[ -f .venv/bin/activate ] || { echo "no .venv — run scripts/bootstrap.sh first" >&2; exit 1; }
# shellcheck disable=SC1091
source .venv/bin/activate
python -c "import fastapi, uvicorn, multipart" 2>/dev/null \
  || python -m pip install --quiet -e ".[ui]"
# $REPO for `ui`, `corpora` and `validation.support`; $REPO/src to run against
# the working tree rather than whatever the last install froze.
export PYTHONPATH="$REPO:$REPO/src${PYTHONPATH:+:$PYTHONPATH}"
exec python -m ui "$@"
