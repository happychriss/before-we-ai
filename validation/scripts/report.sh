#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_env.sh"
python "$BW_REPO/validation/scripts/_steps.py" report "$@"
echo "readiness report: $BW_REPO/validation/data/report/readiness.html"
