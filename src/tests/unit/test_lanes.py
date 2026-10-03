"""Every test module declares which lane it belongs to.

Lanes only help if they are complete. A module that declares none is not in
any lane, so `pytest -m unit` skips it silently and the developer who runs
the fast lane before pushing gets a green they did not earn — the same
silence this product forbids everywhere else. This test is the guard: add a
test module, and you must say what class of thing it tests.
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

TESTS = Path(__file__).resolve().parents[1]
LANES = {"unit", "integration", "contract", "acceptance"}

_DECLARED = re.compile(r"^pytestmark = pytest\.mark\.(\w+)$", re.MULTILINE)


def _modules() -> list[Path]:
    return sorted(p for p in TESTS.rglob("test_*.py"))


def test_every_test_module_declares_exactly_one_lane():
    undeclared = []
    for path in _modules():
        found = _DECLARED.findall(path.read_text(encoding="utf-8"))
        if len(found) != 1:
            undeclared.append(f"{path.relative_to(TESTS)}: {found or 'none'}")
    assert not undeclared, (
        "these modules declare no single lane — add "
        "`pytestmark = pytest.mark.<lane>` below the imports: "
        + "; ".join(undeclared)
    )


def test_no_module_invents_a_lane():
    """The four lanes are registered in pyproject; --strict-markers rejects a
    typo at collection, and this says the same thing with a readable error."""
    for path in _modules():
        for lane in _DECLARED.findall(path.read_text(encoding="utf-8")):
            assert lane in LANES, f"{path.relative_to(TESTS)}: unknown lane {lane!r}"


def test_the_eval_tools_are_not_collected_as_tests():
    """`tests/eval/` holds runnable tools (fixture refresh, seeded recall),
    not tests — they talk to a live model and cost money. They carry no
    `test_` prefix, and that is what keeps them out of every lane."""
    assert not [p for p in (TESTS / "eval").glob("test_*.py")]
