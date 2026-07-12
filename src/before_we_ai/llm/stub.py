"""The fixture-driven offline client — CI's model.

A fixture is a *recorded real answer* (or, before the first online run, a
hand-authored one, marked as such): raw response text plus the sha256 of
the input it answered. Lookup is by contract + scenario name, never by
input hash — a builder change must not make fixtures unfindable for
anyone without an API key. Drift protection is a separate offline test
that rebuilds each fixture's input and compares hashes, so a builder or
prompt change turns CI red loudly instead of letting stale answers drift
green.

The stub returns the recorded text through the exact same validation,
retry, mapping, and logging path as the real client.
"""

import json
from pathlib import Path

from before_we_ai.llm.client import Completion


class FixtureMissing(Exception):
    pass


def fixture_path(fixtures_dir: str | Path, contract: str, scenario: str) -> Path:
    return Path(fixtures_dir) / f"{contract}__{scenario}.json"


class StubClient:
    name = "stub"

    def __init__(self, fixtures_dir: str | Path):
        self.fixtures_dir = Path(fixtures_dir)
        if not self.fixtures_dir.is_dir():
            raise FixtureMissing(
                f"offline mode has no fixture source: {self.fixtures_dir} "
                "is not a directory"
            )

    def load(self, contract: str, scenario: str) -> dict:
        path = fixture_path(self.fixtures_dir, contract, scenario)
        if not path.is_file():
            raise FixtureMissing(
                f"no fixture for contract {contract!r}, scenario {scenario!r} "
                f"(expected {path}) — record one online or author it by hand"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def complete(self, *, contract: str, scenario: str, model: str,
                 system: str, messages: list[dict[str, str]]) -> Completion:
        fixture = self.load(contract, scenario)
        return Completion(text=fixture["response_text"], usage={}, ms=0)
