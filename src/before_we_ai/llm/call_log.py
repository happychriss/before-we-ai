"""Full call logging to ``cache/llm_log/`` — one JSON file per contract call.

The log carries the verbatim request (system + user), every attempt's raw
answer with its validation errors, token usage, timing, the input hash,
and any trim notices. Two consumers depend on the verbatim request: the
fixture refresh (stub answers are recorded real answers) and prompt-
leakage audits (diff exactly what the model saw).

``cache/`` is disposable by contract — logs are derivative, never truth.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from before_we_ai.model.ids import new_id


class CallLogger:
    def __init__(self, root: str | Path):
        self.directory = Path(root) / "cache" / "llm_log"

    def write(self, entry: dict) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.directory / f"{stamp}_{entry['contract']}_{new_id()}.json"
        path.write_text(
            json.dumps(entry, indent=1, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return path
