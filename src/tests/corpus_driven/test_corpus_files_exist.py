"""Every file the manifest promises is actually in the frozen corpus.

Written after a false blocker: "the E4 noise PDFs are missing, so M5's T8
acceptance cannot be met" was recorded and planned around for weeks. The
files were there the whole time, one directory down in ``noise/``. A wrong
answer about what the corpus contains is expensive in a different way from a
wrong answer about the data — it redirects a milestone.

So the manifest and the directory are compared, both ways, by a test.
"""

from pathlib import Path

import pytest
import yaml

from corpora import load as load_landscape

pytestmark = pytest.mark.acceptance

FINANCE = load_landscape("finance")
CORPUS = FINANCE.data
MANIFEST = FINANCE.root / "spec" / "sources_manifest.yaml"

_SOURCES = yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["sources"]


def _promised() -> dict[str, str]:
    """{filename: the manifest entry that promises it}."""
    promised = {}
    for name, spec in _SOURCES.items():
        for key in ("filename", "filenames"):
            value = spec.get(key)
            if isinstance(value, str):
                promised[value] = name
            elif isinstance(value, list):
                promised.update({f: name for f in value})
    return promised


PROMISED = _promised()
# Databases are directories of their own (DE/, US/); everything else is a
# file the manifest names one by one.
DB_DIRS = ("DE", "US")


@pytest.mark.parametrize("filename", sorted(PROMISED))
def test_every_promised_file_is_present(filename):
    """Anywhere under corpus/data/ — the layout has subdirectories
    (``noise/``), and looking only at the top level is exactly the mistake
    this test exists to prevent."""
    matches = list(CORPUS.rglob(filename))
    assert matches, (
        f"{filename} is promised by manifest entry {PROMISED[filename]!r} but "
        f"is nowhere under {CORPUS}. Either the corpus is incomplete or the "
        "manifest is lying; both are blockers, and which one it is decides "
        "the fix."
    )
    assert matches[0].stat().st_size > 0, f"{filename} is empty"


def test_no_shipped_file_is_absent_from_the_manifest():
    """The other direction: a file nobody declared is a file nobody can
    reason about."""
    shipped = {
        p.name for p in CORPUS.rglob("*")
        if p.is_file() and not any(d in p.parts for d in DB_DIRS)
    }
    undeclared = shipped - set(PROMISED) - {
        "expected_verdicts.yaml",  # ground truth, not a source
    }
    assert not undeclared, (
        f"shipped but not in the manifest: {sorted(undeclared)}"
    )


def test_the_e4_noise_pdfs_are_present():
    """Named explicitly because a milestone was re-planned around their
    supposed absence. F26's poisoned anchor — the divested-unit revenue
    figure that exists in no table — lives in the press release, and M5's
    T8-negatives acceptance rests on it."""
    noise = CORPUS / "noise"
    assert sorted(p.name for p in noise.glob("*.pdf")) == [
        "lieferantenkatalog.pdf",
        "pressemitteilung_2022_divested_unit.pdf",
        "reisekostenrichtlinie.pdf",
    ]
