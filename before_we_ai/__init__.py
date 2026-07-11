"""before-we-ai — evidence-based context discovery.

The product package is strictly domain-agnostic: domain knowledge (finance
or otherwise) only ever enters as data — claims, evidence, documents —
never as Python code. Test fixtures live in ``corpus/`` and are never
imported from here.
"""

__version__ = "0.1.0"

from before_we_ai.scan import ScanResult, scan  # noqa: E402

__all__ = ["ScanResult", "scan", "__version__"]
