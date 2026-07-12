# Shared environment for the validation scripts — source, don't execute.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BW_REPO="$(cd "$here/../.." && pwd)"
source "$BW_REPO/.venv/bin/activate"
