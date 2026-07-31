"""The epistemics runtime: run checks, record evidence, gate on dependencies.

Promotion rules themselves live in `model.transitions` — the engine only
executes checks and feeds their records through the state machine.
"""

from before_we_ai.engine.orchestrate import RunReport, run_ready
from before_we_ai.engine.runner import load_tolerances, run_check

__all__ = ["RunReport", "load_tolerances", "run_check", "run_ready"]
