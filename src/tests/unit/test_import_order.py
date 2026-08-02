"""Every package must import on its own, in a fresh interpreter.

This exists because a cycle can hide from a whole green suite. `readiness`
reaches into `llm` for the guide, and `llm` reached back into `readiness`
at module scope — so `import before_we_ai.readiness` failed outright while
every test passed, because something always imported `llm` first. The suite
proved the modules work together and said nothing about whether they load.

A subprocess per package is the only honest way to ask: inside one process
the first successful import poisons the answer for all the others.
"""

import subprocess
import sys

import pytest

pytestmark = pytest.mark.unit

PACKAGES = [
    "before_we_ai",
    "before_we_ai.checks",
    "before_we_ai.core",
    "before_we_ai.documents",
    "before_we_ai.domains",
    "before_we_ai.engine",
    "before_we_ai.llm",
    "before_we_ai.profile",
    "before_we_ai.readiness",
    "before_we_ai.sources",
    "before_we_ai.statements",
    "before_we_ai.store",
    "readiness_report",
    "readiness_report.projection",
]


@pytest.mark.parametrize("package", PACKAGES)
def test_it_imports_first(package):
    """Nothing may depend on another package having been imported already."""
    result = subprocess.run([sys.executable, "-c", f"import {package}"],
                            capture_output=True, text=True)
    assert result.returncode == 0, (
        f"`import {package}` fails when it goes first:\n{result.stderr}"
    )
