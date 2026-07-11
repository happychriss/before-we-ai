"""File repository: YAML objects on disk, in-memory index, integrity check.

Files are the source of truth; ``cache/`` is disposable and never written
here. Evidence is append-only — the store enforces it.
"""

from before_we_ai.store.integrity import check_integrity
from before_we_ai.store.layout import PROJECT_DIRS, init_project, is_project
from before_we_ai.store.repository import AppendOnlyViolation, ProjectStore
from before_we_ai.store.checkpoint import checkpoint

__all__ = [
    "AppendOnlyViolation",
    "PROJECT_DIRS",
    "ProjectStore",
    "check_integrity",
    "checkpoint",
    "init_project",
    "is_project",
]
