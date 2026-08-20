"""Repository root on the path, so the tests can see the landscapes.

`corpora/` is grading data, not part of the installed package — it is never
shipped and `before_we_ai` must never import it. But the corpus-driven tests
and the walkthrough's support code both need to resolve a landscape by name,
and neither should hardcode a path to do it.

pytest already prepends this directory because this file lives here; the
explicit insert is for the case where a tool imports a test module without
pytest driving collection.
"""

import sys
from pathlib import Path

ROOT = str(Path(__file__).resolve().parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
