#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_env.sh"
python "$BW_REPO/validation/scripts/db_export.py" "$@"
