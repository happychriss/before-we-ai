"""Contract V1 — hypotheses from profiles.

One frontier-tier call: the full profile context in, a validated
``HypothesisBatch`` out, every surviving hypothesis mapped to an
``inferred`` claim and saved with claim-key dedup. Hypotheses that fail
the semantic checks even after the retry are skipped individually and
reported — a bad hypothesis never sinks the batch, and a failed call
never raises.

Like ``scan(root)``, ``hypothesize(root)`` is the library seam a later
CLI command will wrap.
"""

from dataclasses import dataclass, field
from pathlib import Path

from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.client import BatchRepair, LLMClient, call_with_retry
from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.inputs import build_profile_context
from before_we_ai.llm.mapping import ProfileIndex, check_hypothesis, hypothesis_to_claim
from before_we_ai.llm.prompts import V1_SYSTEM, with_schema
from before_we_ai.llm.schemas import HypothesisBatch
from before_we_ai.profile.candidates import load_matrix
from before_we_ai.store.repository import ProjectStore

CONTRACT = "v1_hypotheses"


@dataclass
class V1Report:
    claims_created: list[str] = field(default_factory=list)
    claims_deduped: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (statement, reason)
    failure: str | None = None  # both attempts failed — nothing was created
    retries: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    log_ref: str | None = None


def hypothesize(
    root: str | Path,
    *,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    scenario: str = "default",
) -> V1Report:
    root = Path(root)
    store = store or ProjectStore(root)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)

    built = build_profile_context(store, load_matrix(root))
    index = ProfileIndex(store)

    result = call_with_retry(
        client,
        contract=CONTRACT,
        scenario=scenario,
        model=config.models[CONTRACT],
        system=with_schema(V1_SYSTEM, HypothesisBatch),
        built=built,
        schema=HypothesisBatch,
        repair=BatchRepair("hypotheses",
                           lambda h: check_hypothesis(h, index)),
        logger=CallLogger(root),
    )
    report = V1Report(retries=result.retries, usage=result.usage,
                      log_ref=result.log_ref)
    if result.parsed is None:
        report.failure = result.failure
        return report

    for hypothesis in result.parsed.hypotheses:
        errors = check_hypothesis(hypothesis, index)
        if errors:
            report.skipped.append((hypothesis.statement, "; ".join(errors)))
            continue
        claim = hypothesis_to_claim(hypothesis, index)
        kept = store.add_claim(claim)
        if kept.id == claim.id:
            report.claims_created.append(claim.id)
        else:
            report.claims_deduped += 1
    return report
