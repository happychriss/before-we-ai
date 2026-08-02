"""The LLM contract layer — thin, typed, structurally harmless.

Three of the four contract functions live here: the request contract turns a business
question into an answer request and the knowledge it requires (M6), V1
proposes claim hypotheses from column profiles and the candidate matrix,
V2 binds claims to check definitions (including candidate role bindings
for invariant checks). Every call: deterministic input built from the
domain vocabulary or from profiles (never raw data), a Pydantic-validated
response, exactly one retry, full logging to ``cache/llm_log/``.

The epistemic guarantee is not enforced here — it cannot be. Everything
this package produces is created via the M1 core with ``Actor.AI``, which
structurally caps it at ``proposed``. Promotion stays with checks and
humans.
"""

from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.domain_guide import DomainGuide, load_domain_guide, resolve_mappings
from before_we_ai.llm.v1_hypotheses import V1Report, hypothesize
from before_we_ai.llm.v2_bind import (
    MappingProposalReport,
    V2Report,
    plan_checks,
    propose_mappings,
)
from before_we_ai.llm.request import RequestReport, UnknownRequest, ask, revise
from before_we_ai.llm.v3_documents import V3Report, interpret_documents

__all__ = [
    "LLMConfig",
    "V3Report",
    "interpret_documents",
    "MappingProposalReport",
    "DomainGuide",
    "V1Report",
    "V2Report",
    "RequestReport",
    "UnknownRequest",
    "ask",
    "revise",
    "plan_checks",
    "build_client",
    "hypothesize",
    "load_domain_guide",
    "propose_mappings",
    "resolve_mappings",
]
