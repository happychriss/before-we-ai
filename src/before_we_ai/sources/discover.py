"""Drop files in, press scan — the half that was missing.

`init_project()` writes `sources: []` and every entry has been
hand-authored since M2, so the `sources/` drop directory the layout
reserves was never read by anything. `discover(root)` walks it, infers
`kind` from the suffix, and merges what it finds into `before-ai.yaml`.

The whole design is in one word: **merge**. Discovery proposes entries;
it never edits or removes one. That is the same shape as everything else
here — a machine may propose, a human decides — and it has three
consequences worth stating, because each is a rule rather than a
nicety:

* **A hand-tuned entry always wins.** Somebody who set a `scope:` or a
  non-obvious `name:` did so deliberately. Re-running adds only what is
  new, which is the idempotence contract `scan` already keeps.
* **An entry pointing outside `sources/` is never touched.** Those are
  connected databases, and their location is the thing a person got
  right. Discovery has nothing to say about them.
* **Nothing is skipped silently.** A file with an unknown suffix is
  reported, not ignored. The alternative is a project that quietly
  measures less than the directory contains, which is the failure this
  product exists to prevent.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from before_we_ai.store.layout import CONFIG_FILE

#: Suffix -> the `kind` the rest of the pipeline understands. Exactly the
#: four `build_catalog` has a reader for, and no more: `kind` selects the
#: reader, so inferring one nothing implements turns a clear "no reader
#: for .xls" here into an obscure parse failure three stages later. A
#: legacy `.xls` and a bare `.db` are the tempting cases, and both are
#: guesses — openpyxl does not read `.xls`, and a `.db` is as likely to be
#: SQLite as DuckDB.
KINDS = {
    ".duckdb": "duckdb",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".pdf": "pdf",
}

#: Never a source, never a complaint. Editor litter and OS droppings are
#: noise a person did not put there, so reporting them as "skipped" would
#: train the reader to ignore the skipped list — which is the one part of
#: this that has to stay worth reading.
_IGNORED_NAMES = {".DS_Store", "Thumbs.db", ".gitkeep", ".gitignore"}
_IGNORED_SUFFIXES = {".tmp", ".swp", ".part", ".crdownload"}


@dataclass
class DiscoveryResult:
    added: list[dict] = field(default_factory=list)
    #: (path, why) — an unknown suffix, or a name already declared.
    skipped: list[tuple[str, str]] = field(default_factory=list)
    #: Entries already in the config that discovery deliberately left be.
    kept: list[str] = field(default_factory=list)

    def summary(self) -> str:
        added = f"{len(self.added)} new source{'s' if len(self.added) != 1 else ''}"
        if not self.skipped:
            return added
        return f"{added}, {len(self.skipped)} skipped"


def source_name(path: Path, root: Path) -> str:
    """A stable name from the file's place in the drop directory.

    Subdirectories become part of the name (`noise/x.pdf` -> `noise__x`)
    so two files with the same stem in different folders do not collide,
    and so the name says where the file actually is.
    """
    relative = path.relative_to(root / "sources")
    parts = [*relative.parts[:-1], relative.stem]
    return "__".join(_slug(part) for part in parts)


def _slug(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text.strip().lower())


def _is_litter(path: Path) -> bool:
    return (path.name in _IGNORED_NAMES
            or path.suffix.lower() in _IGNORED_SUFFIXES
            or path.name.startswith("~$"))  # Excel lock files


def discover(root: str | Path, *, write: bool = True) -> DiscoveryResult:
    """Find droppable files under ``sources/`` and merge them into the config.

    Pass ``write=False`` to see what it would do without touching the
    file — the same courtesy `scan` owes a reader before it changes a
    project.
    """
    root = Path(root)
    config_path = root / CONFIG_FILE
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    declared = list(config.get("sources") or [])
    result = DiscoveryResult()

    taken_names = {entry.get("name") for entry in declared}
    # Compare resolved paths, not the strings: the same file written as
    # `sources/x.csv` and as an absolute path is one source, and declaring
    # it twice would profile it twice under two names.
    taken_paths = {
        _resolve(root, entry.get("location", "")) for entry in declared
    }
    result.kept = sorted(n for n in taken_names if n)

    drop = root / "sources"
    if not drop.is_dir():
        return result

    for path in sorted(p for p in drop.rglob("*") if p.is_file()):
        if _is_litter(path):
            continue
        kind = KINDS.get(path.suffix.lower())
        relative = path.relative_to(root).as_posix()
        if kind is None:
            what = path.suffix or "a name with no suffix"
            result.skipped.append((relative, f"no reader for {what}"))
            continue
        if path.resolve() in taken_paths:
            continue  # already declared, by whatever name a person gave it
        name = source_name(path, root)
        if name in taken_names:
            result.skipped.append(
                (relative, f"the name {name!r} is already declared for a "
                           f"different file — rename one of them"))
            continue
        entry = {"name": name, "kind": kind, "location": relative}
        result.added.append(entry)
        taken_names.add(name)
        taken_paths.add(path.resolve())

    if result.added and write:
        config["sources"] = declared + result.added
        config_path.write_text(yaml.safe_dump(config, sort_keys=False),
                               encoding="utf-8")
    return result


def _resolve(root: Path, location: str) -> Path:
    path = Path(location)
    return (path if path.is_absolute() else root / path).resolve()
