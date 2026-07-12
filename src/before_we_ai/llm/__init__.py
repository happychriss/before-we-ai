"""The LLM contract layer — thin, typed, structurally harmless.

Two of the four contract functions live here (M4): V1 proposes claim
hypotheses from column profiles and the candidate matrix, V2 binds claims
to probe templates (including candidate role bindings for invariant
probes). Every call: deterministic input built from profiles (never raw
data), a Pydantic-validated response, exactly one retry, full logging to
``cache/llm_log/``.

The epistemic guarantee is not enforced here — it cannot be. Everything
this package produces is created via the M1 core with ``Actor.AI``, which
structurally caps it at ``inferred``. Promotion stays with probes and
humans.
"""

from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.roles import RoleSet, load_roles, resolve_roles
from before_we_ai.llm.v1_hypotheses import V1Report, hypothesize
from before_we_ai.llm.v2_bind import (
    RoleProposalReport,
    V2Report,
    bind_probes,
    propose_role_bindings,
)

__all__ = [
    "LLMConfig",
    "RoleProposalReport",
    "RoleSet",
    "V1Report",
    "V2Report",
    "bind_probes",
    "build_client",
    "hypothesize",
    "load_roles",
    "propose_role_bindings",
    "resolve_roles",
]
