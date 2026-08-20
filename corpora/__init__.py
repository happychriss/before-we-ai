"""Landscapes, held as data — one manifest each, no paths hardcoded anywhere.

A **landscape** is a body of business data with a known answer: the files, what
each one is, which domain guide reads it, and where the answer key lives. The
finance landscape is the frozen one every recorded number is scored against;
the vessel landscape is a second, independent one, built by someone who was
not writing the tool.

Why a manifest and not a constant: the same facts used to be written down in
four places — the source list the walkthrough declares, the PDF list the drift
guard iterates, a `parents[2] / "corpus" / "data"` in every corpus test, and
the walkthrough's own `before-ai.yaml`. Four copies of one fact is three
chances to disagree, and adding a third landscape meant editing all four.

    from corpora import load
    finance = load("finance")
    finance.declarations()                  # ready for before-ai.yaml
    finance.path("DE/erp.duckdb")           # inside data/
    finance.answer_key                      # ... which you do not read

**This is grading infrastructure.** `before_we_ai` never imports it — the day
the product can reach its own answer key, the corpus stops being evidence
(`src/tests/unit/test_layering.py` enforces that).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Source:
    """One declared file in a landscape, with its location already resolved."""

    name: str
    kind: str
    location: Path
    description: str = ""
    sha256: str | None = None

    def declaration(self) -> dict:
        """The shape `before-ai.yaml` wants. Absolute, because a project
        directory lives wherever the caller put it."""
        declared = {"name": self.name}
        if self.description:
            declared["description"] = self.description
        declared |= {"kind": self.kind, "location": str(self.location)}
        return declared


@dataclass(frozen=True)
class Landscape:
    name: str
    domain: str
    frozen: bool
    root: Path
    sources: tuple[Source, ...]
    seed: int | None = None
    guide_packaged: str | None = None
    guide_file: Path | None = None
    answer_key: Path | None = None
    generator: Path | None = None
    held_out: tuple[str, ...] = ()
    questions: tuple[str, ...] = ()

    @property
    def data(self) -> Path:
        return self.root / "data"

    def path(self, relative: str) -> Path:
        """A file inside the landscape's ``data/``."""
        return self.data / relative

    def source(self, name: str) -> Source:
        for source in self.sources:
            if source.name == name:
                return source
        raise KeyError(f"{self.name}: no source named {name!r} "
                       f"(have: {', '.join(s.name for s in self.sources)})")

    def of_kind(self, *kinds: str) -> tuple[Source, ...]:
        return tuple(s for s in self.sources if s.kind in kinds)

    def declarations(self, *names: str) -> list[dict]:
        """Source declarations, all of them or the named subset in order."""
        chosen = [self.source(n) for n in names] if names else list(self.sources)
        return [s.declaration() for s in chosen]


def _landscape(name: str) -> Landscape:
    root = ROOT / name
    manifest_file = root / "manifest.yaml"
    if not manifest_file.exists():
        raise FileNotFoundError(
            f"no landscape {name!r} — expected {manifest_file}. "
            f"Known: {', '.join(names())}")
    manifest = yaml.safe_load(manifest_file.read_text(encoding="utf-8"))

    guide = manifest.get("domain_guide") or {}
    data = root / "data"
    sources = tuple(
        Source(name=entry["name"],
               kind=entry["kind"],
               location=data / entry["path"],
               description=entry.get("description", ""),
               sha256=entry.get("sha256"))
        for entry in manifest.get("sources", []))

    def resolved(key: str) -> Path | None:
        value = manifest.get(key)
        return root / value if value else None

    return Landscape(
        name=manifest["name"],
        domain=manifest["domain"],
        frozen=bool(manifest.get("frozen", True)),
        root=root,
        sources=sources,
        seed=manifest.get("seed"),
        guide_packaged=guide.get("packaged"),
        guide_file=(root / guide["file"]) if guide.get("file") else None,
        answer_key=resolved("answer_key"),
        generator=resolved("generator"),
        held_out=tuple(manifest.get("held_out", [])),
        questions=tuple(manifest.get("questions", [])),
    )


_CACHE: dict[str, Landscape] = {}


def load(name: str) -> Landscape:
    if name not in _CACHE:
        _CACHE[name] = _landscape(name)
    return _CACHE[name]


def names() -> list[str]:
    return sorted(p.parent.name for p in ROOT.glob("*/manifest.yaml"))
