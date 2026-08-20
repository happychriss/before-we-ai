# Shared environment for the validation scripts — source, don't execute.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BW_REPO="$(cd "$here/../.." && pwd)"
# Find the venv rather than assume one: an already-active venv wins, then the
# clone-local .venv that scripts/bootstrap.sh creates. A visitor who installed
# the package some other way is not forced into our layout.
if [ -z "${VIRTUAL_ENV:-}" ]; then
  if [ -f "$BW_REPO/.venv/bin/activate" ]; then
    source "$BW_REPO/.venv/bin/activate"
  else
    echo "no virtualenv active and no $BW_REPO/.venv — run scripts/bootstrap.sh" >&2
    return 1 2>/dev/null || exit 1
  fi
fi
# $BW_REPO for `corpora` (the landscapes) and `validation.support`;
# $BW_REPO/src to run against the working tree rather than whatever the
# last `pip install -e` froze — a renamed package must not break the
# walkthrough.
export PYTHONPATH="$BW_REPO:$BW_REPO/src${PYTHONPATH:+:$PYTHONPATH}"
