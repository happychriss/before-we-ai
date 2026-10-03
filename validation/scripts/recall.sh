#!/usr/bin/env bash
# Seeded-Recall eval in its own project (validation/data/recall).
# Default: offline replay. Pass --online for real model calls
# (needs ANTHROPIC_API_KEY exported; ~330k tokens per run).
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/_env.sh"
out="$BW_REPO/validation/data/recall"
rm -rf "$out"
cd "$BW_REPO/src"
if [[ "${1:-}" == "--online" ]]; then
  python tests/eval/seeded_recall.py --keep "$out"
else
  python tests/eval/seeded_recall.py --offline --keep "$out"
fi
