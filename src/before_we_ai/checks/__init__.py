"""Check definition library: Jinja2 SQL + deterministic verdict functions.

Checks are falsification attempts. A check run never *decides* anything a
human would recognize as judgment — it renders SQL, counts violations,
and applies a fixed rule to map counts to a verdict. Tolerances default
per template and may be overridden only in before-ai.yaml, never on the
claim.
"""

from before_we_ai.checks.library import REGISTRY, CheckDefinition, column_expr
from before_we_ai.checks.verdicts import Assessment

__all__ = ["REGISTRY", "CheckDefinition", "Assessment", "column_expr"]
