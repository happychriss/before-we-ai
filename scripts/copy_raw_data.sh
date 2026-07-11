#!/usr/bin/env bash
# copy_raw_data.sh
#
# Copies the latest M0 generator output from the raw-training-data workspace into
# corpus/data/ so a fresh validation run can start from the most recent output.
#
# Usage:
#   ./scripts/copy_raw_data.sh
#   ./scripts/copy_raw_data.sh --src /path/to/raw-training-data --dst /path/to/corpus/data
#
# Defaults (matching the workspace layout described in corpus/README.md):
#   SOURCE  = /workspace/raw-training-data
#   DEST    = <repo-root>/corpus/data
#
# The script is self-contained: it only requires bash and rsync (or cp -r as fallback).

set -euo pipefail

# ── resolve repo root (directory that contains this script's parent) ──────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# ── defaults ──────────────────────────────────────────────────────────────────
DEFAULT_SRC="/workspace/raw-training-data"
DEFAULT_DST="${REPO_ROOT}/corpus/data"

# ── argument parsing ──────────────────────────────────────────────────────────
SRC="${DEFAULT_SRC}"
DST="${DEFAULT_DST}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src)  SRC="$2";  shift 2 ;;
    --dst)  DST="$2";  shift 2 ;;
    -h|--help)
      grep '^# ' "$0" | grep -v '^# ──' | sed 's/^# //'
      exit 0 ;;
    *)
      echo "Unknown argument: $1  (use --src or --dst)" >&2
      exit 1 ;;
  esac
done

# ── sanity checks ─────────────────────────────────────────────────────────────
if [[ ! -d "${SRC}" ]]; then
  echo "ERROR: Source directory not found: ${SRC}"
  echo "  Run the M0 generator first, or pass --src <path> to override."
  exit 1
fi

echo "Source : ${SRC}"
echo "Dest   : ${DST}"
echo

# ── create destination if it does not exist ───────────────────────────────────
mkdir -p "${DST}"

# ── copy ──────────────────────────────────────────────────────────────────────
if command -v rsync &>/dev/null; then
  # rsync: preserve timestamps, show progress, skip unchanged files
  rsync -av --checksum "${SRC}/" "${DST}/"
else
  # fallback to cp
  echo "rsync not found — falling back to cp -r"
  cp -r "${SRC}/." "${DST}/"
fi

echo
echo "Done. Raw data copied to ${DST}"
echo "You can now run the validation harness:"
echo "  cd ${REPO_ROOT}/corpus/validation && python report.py"
