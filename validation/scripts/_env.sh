# Shared environment for the validation scripts — source, don't execute.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BW_REPO="$(cd "$here/../.." && pwd)"
source "$BW_REPO/.venv/bin/activate"
# Run against the working tree, not whatever package list the last
# `pip install -e` froze — a renamed package must not break the walkthrough.
export PYTHONPATH="$BW_REPO/src${PYTHONPATH:+:$PYTHONPATH}"
