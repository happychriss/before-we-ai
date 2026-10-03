"""Frozen means frozen — every landscape's bytes, pinned by sha256.

Every recorded number in this repository is scored against these files. If one
byte changes, every pinned figure silently stops meaning what it says, and
nothing else in the suite would necessarily notice: a re-generated corpus is
still a valid corpus, just a different one.

This test exists because Phase 2 moved both landscapes into `corpora/`, and a
move is exactly the operation that can change bytes without anybody intending
it — a text file rewritten with different line endings, a binary passed through
a tool that helpfully normalised it. The hashes were taken before the move and
are unchanged after it.

Both directions are checked. A file whose hash drifted is the obvious failure;
a file in `data/` that no manifest mentions is the quieter one — it means the
landscape grew something nobody declared, and the freeze does not cover it.
"""

import hashlib

import pytest
import yaml

from corpora import ROOT as CORPORA_ROOT, load as load_landscape, names

pytestmark = pytest.mark.acceptance

LANDSCAPES = names()


def _pinned(landscape_name: str) -> dict[str, str]:
    """{path relative to data/: sha256}, declared sources plus the extras."""
    manifest = yaml.safe_load(
        (CORPORA_ROOT / landscape_name / "manifest.yaml").read_text(encoding="utf-8"))
    pinned = {}
    for entry in list(manifest.get("sources", [])) + list(manifest.get("undeclared", [])):
        pinned[entry["path"]] = entry["sha256"]
    return pinned


@pytest.mark.parametrize("landscape_name", LANDSCAPES)
def test_every_pinned_file_still_has_its_bytes(landscape_name):
    landscape = load_landscape(landscape_name)
    drifted = []
    for relative, expected in sorted(_pinned(landscape_name).items()):
        path = landscape.data / relative
        assert path.exists(), f"{landscape_name}: {relative} is pinned but missing"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            drifted.append(f"{relative}: pinned {expected[:12]}…, found {actual[:12]}…")
    assert not drifted, (
        f"{landscape_name} is declared frozen and its bytes changed. Every "
        f"recorded number was scored against the old ones:\n  "
        + "\n  ".join(drifted))


@pytest.mark.parametrize("landscape_name", LANDSCAPES)
def test_nothing_in_the_landscape_is_unpinned(landscape_name):
    landscape = load_landscape(landscape_name)
    pinned = set(_pinned(landscape_name))
    present = {str(p.relative_to(landscape.data))
               for p in landscape.data.rglob("*") if p.is_file()}
    unpinned = sorted(present - pinned)
    assert not unpinned, (
        f"{landscape_name}/data holds files no manifest pins, so the freeze "
        f"does not cover them — declare them as sources or list them under "
        f"`undeclared`: {unpinned}")
    missing = sorted(pinned - present)
    assert not missing, f"{landscape_name}: pinned but not on disk: {missing}"


@pytest.mark.parametrize("landscape_name", LANDSCAPES)
def test_the_answer_key_and_the_generator_are_where_the_manifest_says(landscape_name):
    """Not read — only proved to exist. A manifest that points at a missing
    answer key would let a landscape look gradeable when it is not."""
    landscape = load_landscape(landscape_name)
    assert landscape.answer_key is not None and landscape.answer_key.exists()
    assert landscape.generator is not None and landscape.generator.exists()
