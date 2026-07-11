"""The project directory contract — the actual data contract on disk.

```
myproject/
  before-ai.yaml   # sources, model tiers, tolerance overrides
  sources/         # dropped files
  claims/          # one YAML per claim
  evidence/        # append-only records
  questions/       # question cards
  profiles/        # column profiles
  reports/         # rendered derivatives
  cache/           # DISPOSABLE — never a source of truth
```
"""

from pathlib import Path

import yaml

CONFIG_FILE = "before-ai.yaml"
PROJECT_DIRS = (
    "sources",
    "claims",
    "evidence",
    "questions",
    "probes",
    "profiles",
    "reports",
    "cache",
)


def init_project(path: str | Path, name: str | None = None) -> Path:
    """Create the project skeleton; idempotent on an existing project."""
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    for d in PROJECT_DIRS:
        (root / d).mkdir(exist_ok=True)
    config = root / CONFIG_FILE
    if not config.exists():
        config.write_text(
            yaml.safe_dump(
                {"name": name or root.name, "sources": [], "tolerances": {}},
                sort_keys=False,
            ),
            encoding="utf-8",
        )
    return root


def is_project(path: str | Path) -> bool:
    return (Path(path) / CONFIG_FILE).is_file()
