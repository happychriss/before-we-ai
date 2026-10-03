"""The request contract — a business question becomes a classified request.

One call: the question, the domain vocabulary and the answer types the
domain declares go in; a validated ``AnswerRequestDraft`` comes out, saved
as an ``AnswerRequest``. What the answer depends on is then expanded from
the answer type on every read (``readiness.assemble``) — the model does not
write that list, and what it cannot forget it cannot silently omit.

Two tiers of failure, and the difference is the design:

- a **delta item** that fails its semantic check is skipped and reported,
  the same discipline as V1 — a bad item never sinks the call;
- a **classification** naming an answer type the guide does not declare
  fails the whole call, retry included. It is the one claim the call exists
  to make, and a request classified to a family that cannot be expanded is
  worse than no request at all.

This is the top of the machine, and it decides nothing: the classification
is a proposal, and it stays capped at ``ready_with_limitations`` until a
human confirms it. ``ask(root, question)`` is the library seam a later CLI
command will wrap.

Not numbered. The spec's four contract numbers are V1 hypotheses, V2 check
binding, V3 document interpretation and V4 SQL generation; this is none of
them, and the built-but-unnumbered ``role_binding`` already showed that
five contracts do not fit four slots.
"""

from dataclasses import dataclass, field
from pathlib import Path

from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.client import BatchRepair, LLMClient, call_with_retry
from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.llm.inputs import build_question_context
from before_we_ai.llm.mapping import (
    check_classification,
    check_knowledge_item,
    draft_to_request,
    item_to_knowledge,
)
from before_we_ai.llm.prompts import REQUEST_SYSTEM, with_schema
from before_we_ai.llm.schemas import AnswerRequestDraft
from before_we_ai.core.objects import AnswerRequest, RequiredKnowledge
from before_we_ai.store.proposals import ProposalStore
from before_we_ai.store.repository import ProjectStore

CONTRACT = "request"


class UnknownRequest(Exception):
    """A revision was asked for a request this project does not hold."""


@dataclass
class RequestReport:
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
) -> RequestReport:
    """Classify one question and store it as a new request."""
    return _classify(root, question, guide=guide, client=client, store=store,
                     scenario=scenario, revising=None)


def revise(
    root: str | Path,
    request_id: str,
    question: str,
    *,
    guide: DomainGuide,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    scenario: str = "default",
) -> RequestReport:
    """Re-ask an existing request with a new wording.

    A question gets edited: a typo, a narrower period, or a different thing
    entirely. The request keeps its **identity** through that, and the
    reasons are practical rather than tidy. Every act taken on its list —
    "this does not matter here", "this claim speaks to that" — is still
    about this question, and minting a fresh request over a corrected typo
    would throw all of them away. The clarification questions the pipeline
    drafted are not addressed to the request at all; they would survive
    either way.

    What does **not** survive is the confirmation. It said "this list is
    complete" about a question that is no longer the one being asked, so
    the request fingerprint moves and `assemble` stops counting it — the
    same mechanism, and the same wording in the verdict, as a guide that
    has changed underneath one.

    Re-classification is a real call: a revised question may belong to a
    different family, and assuming it does not would be the silent
    under-listing this whole design exists to prevent.
    """
    root = Path(root)
    store = store or ProjectStore(root)
    existing = store.requests.get(request_id)
    if existing is None:
        raise UnknownRequest(f"no request {request_id} in this project")
    return _classify(root, question, guide=guide, client=client, store=store,
                     scenario=scenario, revising=existing)


def _classify(
    root: str | Path,
    question: str,
    *,
    guide: DomainGuide,
    client: LLMClient | None,
    store: ProjectStore | None,
    scenario: str,
    revising: AnswerRequest | None,
) -> RequestReport:
    root = Path(root)
    store = store or ProjectStore(root)
    plain = store
    store = ProposalStore(store)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)

    built = build_question_context(question, guide)

    result = call_with_retry(
        client,
        contract=CONTRACT,
        scenario=scenario,
        model=config.models[CONTRACT],
        system=with_schema(REQUEST_SYSTEM, AnswerRequestDraft),
        built=built,
        schema=AnswerRequestDraft,
        # The classification is checked as a whole answer, the delta items
        # one by one. A bad item is skipped; a bad classification fails the
        # call, because everything the answer depends on follows from it.
        semantic_check=lambda draft: [e for e in
                                      [check_classification(draft, guide)] if e],
        repair=BatchRepair("required_knowledge",
                           lambda i: check_knowledge_item(i, guide)),
        logger=CallLogger(root),
    )
    report = RequestReport(retries=result.retries, usage=result.usage,
                           log_ref=result.log_ref)
    if result.parsed is None:
        report.failure = result.failure
        return report
    broken = check_classification(result.parsed, guide)
    if broken:
        # Surviving the retry: better no request at all than one classified
        # to a family the guide cannot expand.
        report.failure = broken
        return report

    request = draft_to_request(question, result.parsed)
    if revising is not None:
        # Same id, next revision, previous wording kept beside it.
        request = revising.revised(
            question=request.question,
            requested_output=request.requested_output,
            answer_type=request.answer_type,
            scope=request.scope,
        )
    items = []
    for proposal in result.parsed.required_knowledge:
        errors = check_knowledge_item(proposal, guide)
        if errors:
            report.skipped.append((proposal.name, "; ".join(errors)))
            continue
        items.append(item_to_knowledge(proposal, request.scope))

    store.save_request(request)
    report.request = request
    # Only a delta is stored. When the answer type covers the question there
    # is nothing to store: the list is expanded from the guide on every read.
    known = plain.knowledge_for(request.id)
    if items or known is not None:
        required = RequiredKnowledge(request_id=request.id, items=items)
        if known is not None:
            # Reuse the identity rather than adding a second delta for one
            # request: `knowledge_for` returns the first match, so two would
            # make which one applies a matter of dict order. A revision that
            # drafts nothing empties the list — visibly, rather than by
            # deleting the file behind the reader.
            required = required.model_copy(update={"id": known.id})
        store.save_required_knowledge(required)
        report.required = required if items else None
    return report
