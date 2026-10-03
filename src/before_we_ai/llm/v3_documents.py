"""Contract V3 — what the documents say, proposed and anchored.

One frontier-tier call per document: the passages retrieval selected plus
the questions still open go in, findings come out, and each surviving
finding becomes a **proposed** claim with a document anchor pointing at
the exact words it was read from.

Three things happen after the call, and only the first involves the model:

1. **Every quote is string-matched** against the passage it cites. A
   reworded policy is a policy the document does not contain, and the
   anchor cannot be written at all (``ProposalStore.anchor`` refuses it).
2. **Reconciliation judges**, not the model. Where a passage sits on the
   page was derived when the document was read; whether a figure
   corroborates anything follows the multi-anchor rule
   (``documents.reconcile``). A definition may be linked to the rule item
   it settles; a figure standing alone may not.
3. **What is refused becomes a question**, never silence. A chart-only
   figure, a restatement, a lone number — each leaves a clarification
   question naming what a human would have to decide.

Nothing here can promote anything. Anchors are weak evidence
(``resolve_status`` never reads them) and a link is not evidence at all,
so a document-grounded claim sits at ``proposed`` until a check tests it
or a human confirms it. That is the honest position: a policy stating a
rule is a very good reason to believe it, and still not a measurement.

``interpret_documents(root)`` is the library seam a later CLI command
will wrap.
"""

from dataclasses import dataclass, field
from pathlib import Path

import duckdb

from before_we_ai.core.enums import Actor, KnowledgeKind
from before_we_ai.core.objects import ClarificationQuestion
from before_we_ai.documents.figures import read_figures
from before_we_ai.documents.index import load_chunks, retrieve
from before_we_ai.documents.reconcile import corroborate, ground_definition
from before_we_ai.llm.call_log import CallLogger
from before_we_ai.llm.client import BatchRepair, LLMClient, call_with_retry
from before_we_ai.llm.config import LLMConfig, build_client
from before_we_ai.llm.domain_guide import DomainGuide
from before_we_ai.llm.inputs import build_document_context
from before_we_ai.llm.mapping import check_document_finding, finding_to_claim
from before_we_ai.llm.prompts import V3_SYSTEM, with_schema
from before_we_ai.llm.schemas import DocumentReading
from before_we_ai.store.proposals import ProposalStore, QuoteNotFound
from before_we_ai.store.repository import ProjectStore

CONTRACT = "v3_documents"

# How many passages one call may see. Generous — the documents a finance
# team drops are policies and reports, not corpora — but bounded, because
# an unbounded input is an input nobody can pin.
PASSAGE_CAP = 24


@dataclass
class V3Report:
    documents_read: list[str] = field(default_factory=list)
    claims_created: list[str] = field(default_factory=list)
    claims_deduped: int = 0
    anchors: int = 0
    links: list[tuple[str, str]] = field(default_factory=list)  # (ref, claim_id)
    questions: list[str] = field(default_factory=list)
    # Documents too large to send whole, and therefore read only in part.
    narrowed: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)  # (doc, reason)
    retries: int = 0
    usage: dict[str, int] = field(default_factory=dict)
    log_refs: list[str] = field(default_factory=list)


def open_rule_items(store: ProjectStore, guide: DomainGuide) -> list[str]:
    """The rule items no claim has settled yet, across every request.

    These are what a document is worth reading *for*: a sign convention
    or a cut-off rule that no column layout reveals. Taken from the
    readiness evaluator rather than counted here, so V3 and the
    ReadinessMap can never disagree about what is still open. Sorted,
    because the result goes into a prompt.
    """
    # Imported here, not at module scope: `readiness` reaches back into
    # `llm` for the guide, so a top-level import makes `import
    # before_we_ai.readiness` fail outright depending on who imports first.
    from before_we_ai.readiness import evaluate_request

    names: set[str] = set()
    for request_id in sorted(store.requests):
        readiness = evaluate_request(store, guide, request_id)
        if readiness is None:
            continue
        for item in readiness.items:
            if item.item.kind is KnowledgeKind.RULE and not item.satisfied:
                names.add(item.item.name)
    return sorted(names)


def _ask_question(store: ProposalStore, report: V3Report, text: str,
                  claim_id: str) -> None:
    card = ClarificationQuestion(question=text, claim_ids=[claim_id])
    if store.find_question(card) is not None:
        return
    store.save_question(card)
    report.questions.append(text)


def interpret_documents(
    root: str | Path,
    *,
    guide: DomainGuide,
    client: LLMClient | None = None,
    store: ProjectStore | None = None,
    scenario: str = "default",
) -> V3Report:
    root = Path(root)
    project = store or ProjectStore(root)
    store = ProposalStore(project)
    config = LLMConfig.from_project(root)
    client = client or build_client(config)
    logger = CallLogger(root)
    report = V3Report()

    open_items = open_rule_items(project, guide)
    documents = sorted(project.documents.values(), key=lambda d: d.document)
    if not documents:
        return report

    con = duckdb.connect(str(root / "cache" / "analysis.duckdb"))
    try:
        for profile in documents:
            chunks = select_passages(con, profile.document, open_items, report)
            if not chunks:
                continue
            report.documents_read.append(profile.document)
            read_passages(store, project, guide, client, config, logger,
                          report, profile.document, profile.source_id,
                          chunks, open_items, scenario)
    finally:
        con.close()
    return report


def select_passages(con, document: str, open_items: list[str],
                    report: "V3Report") -> list:
    """Which passages of one document the model gets to see.

    **Retrieval bounds the input; it does not filter it.** A document that
    fits is sent whole, because a keyword search that quietly drops the
    paragraph answering a question phrased differently is the exact
    failure that makes retrieval-shaped systems untrustworthy — and it
    fails invisibly, which is worse. Only when a document is too large to
    send does search decide, and then the narrowing is recorded so a
    reader knows the model saw part of the document rather than all of it.
    """
    whole = [c for c in load_chunks(con) if c.source == document]
    if len(whole) <= PASSAGE_CAP:
        return whole
    selected = [
        chunk for chunk in retrieve(con, open_items or [document],
                                    per_query=5, cap=PASSAGE_CAP)
        if chunk.source == document
    ]
    report.narrowed.append(
        f"{document}: {len(selected)} of {len(whole)} passages selected by "
        f"search — the model did not see the whole document"
    )
    return selected


def read_passages(store, project, guide, client, config, logger, report,
                  document: str, source_id: str, chunks, open_items,
                  scenario: str) -> None:
    """One V3 call over a set of passages, and what becomes of the answer.

    Shared with ``statements.tell``: a sentence somebody said is a passage
    like any other, so it earns the same quote validation, the same
    anchoring and the same refusal to be believed on its own.
    """
    by_id = {chunk.id: chunk for chunk in chunks}
    built = build_document_context(document, chunks, open_items)
    result = call_with_retry(
        client,
        contract=CONTRACT,
        scenario=f"{scenario}__{document}",
        model=config.models[CONTRACT],
        system=with_schema(V3_SYSTEM, DocumentReading),
        built=built,
        schema=DocumentReading,
        repair=BatchRepair(
            "findings",
            lambda f: check_document_finding(f, by_id, set(open_items)),
        ),
        logger=logger,
    )
    report.retries += result.retries
    for key, value in result.usage.items():
        report.usage[key] = report.usage.get(key, 0) + value
    if result.log_ref:
        report.log_refs.append(result.log_ref)
    if result.parsed is None:
        report.failures.append((document, result.failure or "no answer"))
        return

    for finding in result.parsed.findings:
        errors = check_document_finding(finding, by_id, set(open_items))
        if errors:
            report.skipped.append((finding.chunk_id, "; ".join(errors)))
            continue
        _record(store, project, guide, report, finding,
                by_id[finding.chunk_id], source_id)


def _record(store, project, guide, report, finding, chunk, source_id) -> None:
    claim = finding_to_claim(finding, source_id)
    kept = store.add_claim(claim)
    if kept.id == claim.id:
        report.claims_created.append(kept.id)
    else:
        report.claims_deduped += 1

    try:
        store.anchor(
            kept.id,
            quote=finding.quote,
            chunk_id=chunk.id,
            chunk_text=chunk.text,
            kind=chunk.kind,
            source=chunk.source,
            page=chunk.page,
        )
    except QuoteNotFound as refusal:
        # Belt and braces: the semantic check already caught this, so
        # reaching here means the two disagree — report, never swallow.
        report.skipped.append((chunk.id, str(refusal)))
        return
    report.anchors += 1

    anchors = project.evidence_for(project.claims[kept.id])
    if finding.reads_as == "definition":
        outcome = ground_definition(anchors)
    else:
        # The model named the figure and the semantic check confirmed it is
        # in the quote; an ambiguous literal still yields no single value,
        # and then nothing can corroborate it, which is correct.
        stated = _stated_value(finding.value or "")
        outcome = (corroborate(anchors, stated) if stated is not None
                   else ground_definition(anchors))

    for concern in outcome.concerns:
        # Name the subject first. A question that opens "only
        # management_report p.1 carries this figure" tells a reader
        # everything except WHICH figure, and a work list of those is a
        # work list nobody can triage.
        _ask_question(
            store, report,
            f"\u201c{kept.statement}\u201d \u2014 {concern.detail}. Does "
            "this passage settle it, and for which scope?",
            kept.id,
        )
    if outcome.may_link and finding.answers:
        _link(store, project, guide, report, finding.answers, kept.id,
              outcome.reason)


def _stated_value(value: str):
    """The one figure the model pointed at, or None if it is ambiguous.

    The semantic check has already established there is exactly one; an
    ambiguous literal inside it (``500.000``) still yields nothing, and
    then nothing can corroborate it, which is correct.
    """
    figures = [f for f in read_figures(value) if f.readings]
    return figures[0].value if figures else None


def _link(store, project, guide, report, ref, claim_id, note) -> None:
    from before_we_ai.readiness import link_claim  # see open_rule_items
    from before_we_ai.readiness.evaluate import UnlinkableItem

    for request in sorted(project.requests.values(), key=lambda r: r.id):
        try:
            link_claim(project, guide, request.id, ref, claim_id,
                       linked_by=Actor.AI, note=note)
        except UnlinkableItem:
            continue
        report.links.append((ref, claim_id))
        return
