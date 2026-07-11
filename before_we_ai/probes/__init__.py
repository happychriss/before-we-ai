"""Probe template library: Jinja2 SQL + deterministic verdict functions.

Probes are falsification attempts. A probe run never *decides* anything a
human would recognize as judgment — it renders SQL, counts violations,
and applies a fixed rule to map counts to a verdict. Tolerances default
per template and may be overridden only in before-ai.yaml, never on the
claim.
"""

from before_we_ai.probes.library import REGISTRY, TemplateSpec, column_expr
from before_we_ai.probes.verdicts import Assessment

__all__ = ["REGISTRY", "TemplateSpec", "Assessment", "column_expr"]
