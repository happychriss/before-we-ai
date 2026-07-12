#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_env.sh"
rm -rf "$BW_REPO/validation/data"
echo "removed $BW_REPO/validation/data — start fresh with 1-scan.sh"
