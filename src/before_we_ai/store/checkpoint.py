"""Optional git checkpoints — a soft dependency, never a requirement.

If the project directory is inside a git repository, a checkpoint commits
the current state; otherwise it is a silent no-op.
"""

import subprocess
from pathlib import Path


def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
    )


def checkpoint(root: str | Path, message: str) -> bool:
    """Commit the project state if inside a git repo. Returns True on commit."""
    root = Path(root)
    try:
        inside = _git(root, "rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        return False  # git not installed — soft dependency
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return False
    _git(root, "add", "-A")
    committed = _git(root, "commit", "-m", message)
    # returncode 1 with nothing to commit is fine — still not a checkpoint
    return committed.returncode == 0
