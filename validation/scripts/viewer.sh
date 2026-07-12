#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_env.sh"
python "$BW_REPO/validation/scripts/_steps.py" viewer "$@"
echo "claim viewer: $BW_REPO/validation/data/report/claims.html"
