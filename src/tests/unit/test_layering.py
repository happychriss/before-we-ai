"""The product does not know the corpus, the tests or the walkthrough exist.

`before_we_ai` is a general machine; the landscapes in `corpora/` are how *we*
grade it. The day the product imports its own grading fixtures, a landscape
stops being evidence and becomes part of what it was supposed to measure. The
same goes for the walkthrough's support code and for the tests themselves.

`corpora` is in the list for a sharper reason than the rest: it is the module
that can resolve a path to an answer key.

Checked over parsed imports rather than text, because that is what the rule
is actually about — a module reached, not a word written.
"""

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

PRODUCT = Path(__file__).resolve().parents[2] / "before_we_ai"
FORBIDDEN = ("corpus", "corpora", "tests", "validation", "readiness_report")


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_the_product_imports_no_corpus_test_or_validation_code():
    offences = []
    for path in sorted(PRODUCT.rglob("*.py")):
        for root in sorted(_imported_roots(path) & set(FORBIDDEN)):
            offences.append(f"{path.relative_to(PRODUCT.parent)} imports {root!r}")
    assert not offences, (
        "the product must stay independent of how it is graded and shown: "
        + "; ".join(offences)
    )


def test_the_reverse_is_expected_and_not_an_offence():
    """Stated so the rule is not read as symmetric: the support code imports
    the product, which is the whole point of it."""
    support = Path(__file__).resolve().parents[3] / "validation" / "support" / "corpus.py"
    assert "before_we_ai" in _imported_roots(support)
