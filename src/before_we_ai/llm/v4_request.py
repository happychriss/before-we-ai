"""Contract V4 — a business question becomes a request and its dependencies.

One call: the question plus the domain vocabulary in, a validated
``AnswerRequestDraft`` out, saved as an ``AnswerRequest`` and the
``RequiredKnowledge`` drafted for it. Items that fail the semantic checks
even after the retry are skipped individually and reported — the same
discipline as V1: a bad item never sinks the batch, and a failed call
never raises.

This is the top of the machine, and it decides nothing. The request
*bounds* discovery — what the answer depends on must be known, nothing
else has to be — and every item it lists is a proposal a human may strike
before anything is measured. ``ask(root, question)`` is the library seam a
later CLI command will wrap.
"""

from dataclasses import dataclass, field
from pathlib import Path

from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.client import BatchRepair, LLMClient, call_with_retry
from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.llm.inputs import build_question_context
from before_we_ai.llm.mapping import (
    check_knowledge_item,
    draft_to_request,
    item_to_knowledge,
)
from before_we_ai.llm.prompts import V4_SYSTEM, with_schema
from before_we_ai.llm.schemas import AnswerRequestDraft
from before_we_ai.core.objects import AnswerRequest, RequiredKnowledge
from before_we_ai.store.repository import ProjectStore

CONTRACT = "v4_request"


@dataclass
class V4Report:
    request: AnswerRequest | None = None
    required: RequiredKnowledge | None = None
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (item, reason)
    failure: str | None = None  # both attempts failed — nothing was created
    retries: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    log_ref: str | None = None


def ask(
    root: str | Path,
    question: str,
    *,
    guide: DomainGuide,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    scenario: str = "default",
) -> V4Report:
    root = Path(root)
    store = store or ProjectStore(root)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)

    built = build_question_context(question, guide)

    result = call_with_retry(
        client,
        contract=CONTRACT,
        scenario=scenario,
        model=config.models[CONTRACT],
        system=with_schema(V4_SYSTEM, AnswerRequestDraft),
        built=built,
        schema=AnswerRequestDraft,
        repair=BatchRepair("required_knowledge",
                           lambda i: check_knowledge_item(i, guide)),
        logger=CallLogger(root),
    )
    report = V4Report(retries=result.retries, usage=result.usage,
                      log_ref=result.log_ref)
    if result.parsed is None:
        report.failure = result.failure
        return report

    request = draft_to_request(question, result.parsed)
    items = []
    for proposal in result.parsed.required_knowledge:
        errors = check_knowledge_item(proposal, guide)
        if errors:
            report.skipped.append((proposal.name, "; ".join(errors)))
            continue
        items.append(item_to_knowledge(proposal, request.scope))

    store.save_request(request)
    required = RequiredKnowledge(request_id=request.id, items=items)
    store.save_required_knowledge(required)
    report.request, report.required = request, required
    return report
