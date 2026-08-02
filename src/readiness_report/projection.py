"""Project report facts and product wording, independent of HTML output."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

from before_we_ai.checks.library import REGISTRY
from before_we_ai.core import (
    ActKind,
    Actor,
    CheckVerdict,
    ClaimStatus,
    EvidenceType,
    Provenance,
    confirmation_admissible,
    is_answered,
    resolve_status,
    settling_claims,
)
from before_we_ai.core.objects import (
    CheckPlan,
    Claim,
    KnowledgeAct,
    ClarificationQuestion,
    DataProfile,
    EvidenceRecord,
    MappingClaim,
    Scope,
    Source,
)
from before_we_ai.core.semantics import gap_load
from before_we_ai.domains import resolve_guide
from before_we_ai.glossary import GLOSSARY
from before_we_ai.llm.domain_guide import (
    DomainGuide,
    load_domain_guide,
    scopes_of,
    settled_slots,
)
from before_we_ai.llm.mapping import admissible_templates
from before_we_ai.readiness import (
    Ground,
    Readiness,
    evaluate_request,
    guide_label,
)
from before_we_ai.staleness import current_stamps, why_stale
from before_we_ai.stages import (
    BOUNDARY_BEFORE,
    BOUNDARY_TEXT,
    BY_NAME,
    STAGES,
)
from before_we_ai.store import ProjectStore, check_integrity
from before_we_ai.store.layout import CONFIG_FILE


@dataclass(frozen=True)
class ReferenceView:
    kind: str
    id: str


@dataclass(frozen=True)
class LinkView:
    reference: ReferenceView
    label: str


@dataclass(frozen=True)
class TextPartView:
    text: str
    style: str = ""
    reference: ReferenceView | None = None
    escape_quotes: bool = False


@dataclass(frozen=True)
class RichTextView:
    parts: tuple[TextPartView, ...]


@dataclass(frozen=True)
class QuoteView:
    css: str
    text: str
    cite: RichTextView


@dataclass(frozen=True)
class ProvenanceView:
    reference: ReferenceView
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class LinkStatusView:
    link: LinkView
    status: str = ""
    note: str = ""


@dataclass(frozen=True)
class StageStepView:
    label: str
    state: str
    explanation: str


@dataclass(frozen=True)
class StageView:
    name: str
    label: str
    title: str
    actor: str
    counts: tuple[tuple[str, str], ...]
    boundary_before: str = ""


@dataclass(frozen=True)
class FunnelChipView:
    count: int
    label: str
    stage: str
    status: str = ""


@dataclass(frozen=True)
class FunnelStageView:
    label: str
    chips: tuple[FunnelChipView, ...]


@dataclass(frozen=True)
class FunnelView:
    stages: tuple[FunnelStageView, ...] = ()
    empty: str = ""
    caveat: RichTextView | None = None


@dataclass(frozen=True)
class DeclaredSourceView:
    name: str
    kind: str
    location: str


@dataclass(frozen=True)
class GuideEntryView:
    name: str
    decision: str
    definition: str
    fields: tuple[GuideEntryView, ...] = ()


@dataclass(frozen=True)
class AnswerTypeView:
    """One declared answer type, and what it says an answer of its family
    depends on. Section 0 shows these because a reader cannot judge the
    classification in section 1 without seeing what was on offer and what
    the chosen type actually claims."""

    name: str
    definition: str
    requires: tuple[str, ...] = ()


@dataclass(frozen=True)
class DomainGuidePanelView:
    state: str
    path: str = ""
    domain: str = ""
    object_count: int = 0
    field_count: int = 0
    entries: tuple[GuideEntryView, ...] = ()
    answer_types: tuple[AnswerTypeView, ...] = ()


@dataclass(frozen=True)
class DomainLawView:
    name: str
    domain: str
    file: str


@dataclass(frozen=True)
class DomainLawsView:
    domain: str
    laws: tuple[DomainLawView, ...]
    generic_count: int
    foreign_count: int
    empty_message: RichTextView | None = None
    note: str = ""


@dataclass(frozen=True)
class DomainPackView:
    intro: str
    sources: tuple[DeclaredSourceView, ...]
    guide: DomainGuidePanelView
    laws: DomainLawsView


@dataclass(frozen=True)
class MatrixView:
    found: bool
    summary: str = ""
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateOverlapView:
    other: str
    containment: str
    overlap: str


@dataclass(frozen=True)
class EvidenceReferenceView:
    link: LinkView
    payload: str


@dataclass(frozen=True)
class ColumnView:
    key: str
    details: tuple[tuple[str, str], ...]
    declarations: tuple[EvidenceReferenceView, ...]
    candidates: tuple[CandidateOverlapView, ...]
    role_bindings: tuple[LinkStatusView, ...]


@dataclass(frozen=True)
class TableView:
    name: str
    declarations: tuple[EvidenceReferenceView, ...]
    columns: tuple[ColumnView, ...]


@dataclass(frozen=True)
class SourceView:
    id: str
    name: str
    kind: str
    details: tuple[tuple[str, str], ...]
    claims: tuple[LinkStatusView, ...]
    tables: tuple[TableView, ...]
    profile_count: int


@dataclass(frozen=True)
class MeasurementView:
    source_count: int
    project_line: str
    matrix: MatrixView
    sources: tuple[SourceView, ...]
    orphan_tables: tuple[TableView, ...]


@dataclass(frozen=True)
class CheckView:
    id: str
    short_id: str
    template: str
    domain: str
    sentence: str
    rendered_sql: str
    provenance: ProvenanceView
    details: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class EvidenceView:
    id: str
    short_id: str
    type: str
    badge_kind: str
    badge_value: str
    sentence: str
    voice: QuoteView | None
    check_link: LinkView | None
    check_template: str
    sample_headers: tuple[str, ...]
    sample_rows: tuple[tuple[str, ...], ...]
    touched_table: str
    touched_column: str
    sibling_declarations: int
    provenance: ProvenanceView
    details: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class NoCheckView:
    stage: str
    explanation: RichTextView
    reason: str


@dataclass(frozen=True)
class LineageView:
    parent: LinkView | None
    evidence: LinkView | None


@dataclass(frozen=True)
class ClaimIndexView:
    id: str
    short_id: str
    title: str
    derived_status: str
    stage: str
    executed: bool
    predicate: str
    role: str
    search: str
    hint: str


@dataclass(frozen=True)
class ClaimView:
    index: ClaimIndexView
    stored_status: str
    headline: str
    stage_steps: tuple[StageStepView, ...]
    rationale: QuoteView | str | None
    provenance: ProvenanceView
    diverges: bool
    divergence: RichTextView | None
    statement: str
    created_by: str
    proposal: QuoteView
    proposed_details: tuple[tuple[str, str], ...]
    subtype_details: tuple[tuple[str, str], ...] | None
    checks: tuple[CheckView, ...]
    no_check: NoCheckView | None
    evidence: tuple[EvidenceView, ...]
    sources: tuple[LinkStatusView, ...]
    bound_table: str
    bound_column: str
    questions: tuple[LinkView, ...]
    assumptions: tuple[object, ...]
    dependencies: tuple[LinkStatusView, ...]
    reverse_dependencies: tuple[LinkStatusView, ...]
    derived_children: tuple[LinkStatusView, ...]
    lineage: LineageView | None
    details: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class QuestionOptionView:
    link: LinkView
    binding: str = ""
    binding_kind: str = ""
    status: str = ""


@dataclass(frozen=True)
class QuestionView:
    id: str
    question: str
    # How big the finding is. Not part of the question's wording — that is
    # its identity — but shown right beside it, because a reader deciding
    # what to look at first needs to know whether "they do not agree" is
    # one row in twenty-four or two in five.
    finding: str
    mode: str
    lead: str
    options: tuple[QuestionOptionView, ...]
    provenance: ProvenanceView
    details: tuple[tuple[str, str], ...]
    # Why this one is worth answering, and how urgently. A flat list of
    # twenty-three questions tells a reader nothing about where to start —
    # and most of them do not bear on the question that was actually asked.
    # `rank` is the sort key (lower first), `bearing` the badge, `because`
    # the sentence naming what it holds up.
    rank: int = 3
    bearing: str = ""
    because: str = ""
    # How many questions rest on the same claims (core.semantics.gap_load).
    # The tie-breaker within a band: settle the claim that unblocks most.
    load: int = 0


@dataclass(frozen=True)
class AnsweredQuestionView:
    id: str
    question: str
    settled: tuple[LinkStatusView, ...]
    summary: str
    provenance: ProvenanceView


@dataclass(frozen=True)
class QuestionTallyView:
    """How the to-do list divides — and what working it would actually buy.

    Section 5 opened with a single count, and a single count invites the
    wrong inference twice over: a reader seeing twenty-two open questions
    under a blocked verdict reads all twenty-two as the price of an answer,
    and then reads answering the urgent ones as paying it. Most are not on
    the path at all, and a candidate a check *refuted* is not waiting on a
    person — no answer settles it.

    Both facts are derived already (`_question_bearing` for the bands,
    the same Ground split `_build_unblock` routes on); this states them
    where the list is actually read, instead of leaving the reader to
    reconcile section 5 with section 6 themselves.
    """

    total: int
    bands: tuple[tuple[int, int, str], ...] = ()  # count, rank, band label
    urgent: int = 0
    headline: str = ""
    outlook: str = ""


@dataclass(frozen=True)
class RequestItemView:
    ref: str
    kind: str
    provenance: str
    waived: bool
    waived_because: str
    why: str
    why_cite: str


@dataclass(frozen=True)
class RequestView:
    id: str
    question: str
    requested_output: str
    treated_as: RichTextView
    scope_line: str
    dependency_heading: str
    items: tuple[RequestItemView, ...]
    provenance: ProvenanceView


@dataclass(frozen=True)
class ReadinessLinkView:
    sentence: RichTextView


@dataclass(frozen=True)
class ReadinessItemView:
    ref: str
    kind: str
    mark: str
    because: str
    links: tuple[ReadinessLinkView, ...]
    claims: tuple[LinkView, ...]


@dataclass(frozen=True)
class ReadinessGroupView:
    title: str
    items: tuple[ReadinessItemView, ...]


@dataclass(frozen=True)
class ReadinessView:
    id: str
    question: str
    verdict: str
    headline: str
    reason: str
    explanation: str
    scope_line: str
    groups: tuple[ReadinessGroupView, ...]
    provenance: ProvenanceView


@dataclass(frozen=True)
class ElectionCandidateView:
    link: LinkView
    status: str
    css: str
    reasons: tuple[RichTextView, ...]


@dataclass(frozen=True)
class ElectionOutcomeView:
    paragraphs: tuple[tuple[str, RichTextView], ...]


@dataclass(frozen=True)
class ElectionView:
    role: str
    owner: str
    scope: str
    candidate_count: int
    path_note: str
    definition: str
    field: bool
    outcome: ElectionOutcomeView
    candidates: tuple[ElectionCandidateView, ...]


@dataclass(frozen=True)
class ReportCopyView:
    reading_guide: str
    process_ghost: RichTextView
    request_intro: str
    measured_intro: str
    proposed_intro: RichTextView
    tested_intro: str
    clarification_intro: str
    clarification_order: str
    readiness_intro: str
    no_request: str


@dataclass(frozen=True)
class DocumentView:
    """One document that was read, in a reader's terms.

    No chunk ids, no offsets, no fingerprints: what a validator needs to
    know is which document was read, how much of it there was, and
    whether any of it sits somewhere a figure cannot be checked.
    """

    name: str
    pages: str  # "3 pages" — the unit a reader counts in
    passages: str  # "5 passages"
    origins: tuple[str, ...]  # "1 inside a chart", "1 in a ruled table"
    caution: str  # "" when nothing about this document needs care


@dataclass(frozen=True)
class DocumentsView:
    heading: str
    explanation: RichTextView
    documents: tuple[DocumentView, ...]


@dataclass(frozen=True)
class DecisionView:
    """One decision, with who made it and what drove them to it.

    The report's other axis. Reading down the stages tells you what the
    project knows; reading down this tells you *how it came to*, which is
    the question a validator actually has — and the one the stage
    headings answer least well, because a decision made in stage 5 is
    usually driven by something found in stage 3.
    """

    actor: str  # "a human" / "the AI" / "a check" / "the system"
    actor_css: str  # colour by voice, so the pattern is visible before the words
    marker: str  # ● ○ ◆ ▪ — the same distinction without relying on colour
    what: str  # what was decided, in business words
    driver: str  # what drove it — the sentence, the law, the run
    stage: str  # "0".."6" — where in the flow this sits
    stage_label: str
    settles: str  # "" unless this decision changed what is believed
    link: LinkView | None


@dataclass(frozen=True)
class DecisionLogView:
    heading: str
    explanation: RichTextView
    decisions: tuple[DecisionView, ...]
    empty: str


@dataclass(frozen=True)
class RouteView:
    """One way out of a block, and what it costs to take it."""

    heading: str  # the move, in the second person
    css: str
    items: tuple[str, ...]  # the dependencies this route would clear
    explanation: str  # why these are here and not on another route
    where: tuple[str, ...] = ()  # the locus, when a check found one
    alternative: str = ""  # the other move, when there is one


@dataclass(frozen=True)
class UnblockView:
    """What a reader can actually do about a verdict that will not clear.

    The engine already knows which route applies to which dependency —
    ``Ground`` distinguishes "nobody has answered" from "everything was
    tested and refuted", and the item sentences say so. What was missing
    was saying it as an *offer* rather than a diagnosis, in one place,
    with the locus of the failure brought forward from the evidence
    instead of left for the reader to dig out.

    Routes are only ever offered when they work. Fixing the data closes a
    block since staleness landed (a newer reading supersedes the one
    before it); asking a narrower question is deliberately **not** offered,
    because a conservation law that spans entities blocks a narrowed
    question at exactly the same items — an escape that is not one is
    worse than none.
    """

    blocked: bool
    heading: str
    summary: str
    routes: tuple[RouteView, ...]
    settled: str  # what to say when there is nothing to unblock


@dataclass(frozen=True)
class ReportViewModel:
    project_name: str
    project_path: str
    copy: ReportCopyView
    stages: tuple[StageView, ...]
    domain_pack: DomainPackView
    requests: tuple[RequestView, ...]
    measurement: MeasurementView
    documents: DocumentsView
    decisions: DecisionLogView
    unblock: UnblockView
    funnel: FunnelView
    elections: tuple[ElectionView, ...]
    open_questions: tuple[QuestionView, ...]
    question_tally: QuestionTallyView
    answered_questions: tuple[AnsweredQuestionView, ...]
    readiness: tuple[ReadinessView, ...]
    claims: tuple[ClaimView, ...]
    integrity: tuple[str, ...]
    glossary: tuple[tuple[str, str], ...]
    status_options: tuple[str, ...]
    predicate_options: tuple[str, ...]
    role_options: tuple[str, ...]


STAGE_LABELS = {
    "bound": "bound to a check",
    "unbindable": "unbindable — the model gave a reason",
    "semantic_only": "semantic-only — no check definition can test it",
    "skipped": "skipped — validation rejected the binding",
    "unbound": "no check, no recorded reason",
}

READING_GUIDE = (
    "This page is the pipeline itself, rendered from the project store: humans "
    "declare the inputs, measurement describes the data, the AI proposes, the "
    "checks decide, and whatever the data cannot settle becomes a question for a "
    "human. Read it top down, or jump in from the diagram — every number there is "
    "a link into the section that produced it. Then pick one claim on the left and "
    "read its story: 1 proposed → 2 bound → 3 judged → 4 context. Nothing here is "
    "hand-set: every status is derived from the evidence shown next to it, and the "
    "AI cannot author evidence that promotes a claim."
)

DOMAIN_PACK_INTRO = (
    "Everything domain-specific enters through three declared inputs "
    "(docs/architecture.md 'Domain inputs'); the model additionally sees only "
    "measured statistics, never raw rows. The product is a general machine only "
    "together with a domain pack — so what is domain-specific must be declared, "
    "transparent, and logically validated."
)

NOTHING_ASKED = (
    "No business question has been asked of this project yet. Until one is, "
    "this report describes a landscape rather than an answer — and whether a "
    "landscape is generally sound is a question nobody asked."
)

PROVENANCE_LABEL = {
    Provenance.CONTRACT: "from the answer type",
    Provenance.PROPOSED: "drafted for this question",
    Provenance.ADDED: "added by a human",
}

WHY_CITE = {
    Provenance.CONTRACT: "— the domain guide, on why an answer of this kind "
                         "depends on it",
    Provenance.PROPOSED: "— the AI, on why the answer depends on this",
    Provenance.ADDED: "— the human who added it",
}

VERDICT_HEADLINE = {
    Readiness.READY: (
        "Ready.",
        "Every dependency of this answer is supported by evidence.",
    ),
    Readiness.READY_WITH_LIMITATIONS: (
        "Ready, with limitations.",
        "The figures can be produced. What they mean is not fully settled — "
        "the unsupported items below are the qualifications that belong with "
        "any answer given from this data.",
    ),
    Readiness.BLOCKED: (
        "Blocked.",
        "The figures cannot be produced from this data yet. Each unsupported "
        "item below is something the answer is computed from.",
    ),
}


@dataclass
class ClaimFacts:
    """Everything the viewer knows about one claim, computed once."""

    claim: Claim
    evidence: list[EvidenceRecord] = field(default_factory=list)
    checks: list[CheckPlan] = field(default_factory=list)
    derived: ClaimStatus = ClaimStatus.PROPOSED
    stage: str = "unbound"
    executed: bool = False
    no_check_reason: str = ""

    @property
    def diverges(self) -> bool:
        return self.claim.status is not self.derived


@dataclass
class GuideShape:
    """What the report needs from the domain guide, read tolerantly.

        The definitions are the only human-written business vocabulary in the
        project — the report quotes them rather than inventing prose of its own.
        """

    order: list[str] = field(default_factory=list)
    decided_by: dict[str, str] = field(default_factory=dict)
    owner: dict[str, str] = field(default_factory=dict)
    definition: dict[str, str] = field(default_factory=dict)
    fills: dict[str, str] = field(default_factory=dict)


def load_view_model(root: str | Path) -> ReportViewModel:
    root_path = Path(root).resolve()
    store = ProjectStore(root_path)
    config = _project_config(root_path)
    return build_view_model(store, root_path, config)


def _reference(kind: str, ident: str) -> ReferenceView:
    return ReferenceView(kind=kind, id=ident)


def _link(kind: str, ident: str, label: str) -> LinkView:
    return LinkView(reference=_reference(kind, ident), label=label)


def _text(*parts: TextPartView) -> RichTextView:
    return RichTextView(parts=tuple(parts))


def _plain(value: str) -> TextPartView:
    return TextPartView(value)


def _styled(value: str, style: str) -> TextPartView:
    return TextPartView(value, style=style)


def _linked(value: str, kind: str, ident: str, style: str = "") -> TextPartView:
    return TextPartView(
        value,
        style=style,
        reference=_reference(kind, ident),
        escape_quotes=True,
    )


def _claim_facts(store: ProjectStore, claims: list[Claim]) -> dict[str, ClaimFacts]:
    """One pass over the store: evidence, checks, derived status, funnel stage."""
    facts: dict[str, ClaimFacts] = {}
    for claim in claims:
        evidence = store.evidence_for(claim)
        evidence_check_plan_ids = {
            record.check_plan_id for record in evidence if record.check_plan_id
        }
        checks = sorted(
            (
                check
                for check in store.checks.values()
                if check.claim_id == claim.id or check.id in evidence_check_plan_ids
            ),
            key=lambda check: (check.created_at, check.id),
        )
        decision, reason = _no_check_decision(evidence)
        if checks:
            stage = "bound"
        elif decision:
            stage = decision
        elif not admissible_templates(claim):
            stage = "semantic_only"
        else:
            stage = "unbound"
        facts[claim.id] = ClaimFacts(
            claim=claim,
            evidence=evidence,
            checks=checks,
            derived=resolve_status(claim, evidence),
            stage=stage,
            executed=any(
                record.type is EvidenceType.CHECK_RESULT for record in evidence
            ),
            no_check_reason=reason,
        )
    return facts


def _no_check_decision(evidence: list[EvidenceRecord]) -> tuple[str, str]:
    for record in evidence:
        if record.type is not EvidenceType.DECLARATION:
            continue
        decision = str(record.payload.get("decision", ""))
        if decision in STAGE_LABELS:
            return decision, str(record.payload.get("reason", ""))
    return "", ""


def _project_config(root: Path) -> dict:
    """The declared inputs, read straight from before-ai.yaml (read-only)."""
    path = root / CONFIG_FILE
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _guide_path(root: Path, config: dict) -> Path | None:
    declared = (config.get("llm") or {}).get("domain_guide_file")
    if not declared:
        return None
    # A bare name is one of the packs we ship; anything else is the
    # customer's own file. `resolve_guide` owns that distinction so the
    # report and V2 can never disagree about which guide is in play.
    return resolve_guide(declared, root)


def _load_guide_shape(root: Path, config: dict) -> GuideShape:
    """The guide's shape and words — read from the raw YAML, never refused.

        A broken guide is shown as it is; the report does not decline to render
        because one input is wrong.
        """
    shape = GuideShape()
    path = _guide_path(root, config)
    if path is None:
        return shape
    try:
        pack = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return shape
    for name, spec in (pack.get("objects") or {}).items():
        if not isinstance(spec, dict):
            continue
        shape.order.append(name)
        shape.decided_by[name] = spec.get("decided_by", "")
        shape.definition[name] = " ".join(str(spec.get("definition", "")).split())
        for fname, fspec in (spec.get("fields") or {}).items():
            shape.order.append(fname)
            shape.owner[fname] = name
            if isinstance(fspec, dict):
                shape.decided_by[fname] = fspec.get("decided_by", "")
                shape.definition[fname] = " ".join(
                    str(fspec.get("definition", "")).split()
                )
                if fspec.get("fills"):
                    shape.fills[fname] = str(fspec["fills"])
    return shape


def _load_candidate_matrix(root: Path) -> dict:
    path = root / "profiles" / "candidate_matrix.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _rationales(
    root: Path, claims: list[Claim], owner: dict[str, str]
) -> dict[str, str]:
    """claim id → the model's reason for proposing it, best-effort.

        The rationale is logged in ``cache/`` and deliberately never stored on
        the claim: it explains a guess, and a guess is not evidence. So this is
        a *lookup into a disposable file*, and the honest outcomes are three —
        a rationale, an empty string (the log is gone; the page says so), or no
        entry at all (this claim was not proposed by a logged model call).
        """
    log_dir = root / "cache" / "llm_log"
    by_statement: dict[str, str] = {}
    by_role_table: dict[tuple[str, str], str] = {}
    files = sorted(log_dir.glob("*.json")) if log_dir.is_dir() else []
    for path in files:
        for item in _logged_items(path):
            said = str(item.get("rationale", "")).strip()
            if not said:
                continue
            if "statement" in item:
                by_statement[" ".join(str(item["statement"]).split())] = said
            binding = item.get("binding")
            if item.get("role") and isinstance(binding, dict):
                table = str(binding.get("table", ""))
                if table:
                    by_role_table[(str(item["role"]), table)] = said
    found: dict[str, str] = {}
    for claim in claims:
        if claim.created_by is not Actor.AI:
            continue
        said = None
        if isinstance(claim, MappingClaim):
            table = str((claim.binding or {}).get("table", ""))
            said = (
                by_role_table.get((claim.role, table))
                or by_role_table.get((owner.get(claim.role, ""), table))
            )
        else:
            said = by_statement.get(" ".join(claim.statement.split()))
        found[claim.id] = said or ""
    return found


def _logged_items(path: Path) -> list[dict]:
    """The model's answer items from one logged call — tolerant by design.

        A call log holds every attempt including the ones that failed to parse;
        the last attempt that is valid JSON is the answer that counted.
        """
    try:
        call = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    for attempt in reversed(call.get("attempts") or []):
        try:
            answer = json.loads(attempt.get("raw_text") or "")
        except ValueError:
            continue
        if not isinstance(answer, dict):
            continue
        for value in answer.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return [item for item in value if isinstance(item, dict)]
    return []


def _short_id(value: str) -> str:
    return f"…{value[-6:]}"


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _stringify(value: object) -> str:
    if isinstance(value, (dict, list)):
        return _json_text(value)
    return str(value)


def _source_name(source: Source | None) -> str:
    return source.name.lower() if source else ""


def _claim_title(claim: Claim) -> str:
    """A claim named in one readable line.

        A mapping claim's own statement spells out every part of its binding;
        that is the machine's phrasing, kept verbatim where the model's words
        belong, not used as a heading.
        """
    if isinstance(claim, MappingClaim):
        return f"'{claim.role}' is played by {_candidate_name(claim)}"
    return claim.statement


def _candidate_name(claim: Claim) -> str:
    """The one thing a candidate points at — a column, or else its table.

        A mapping claim's statement spells its whole binding out ("role 'journal'
        is played by account=…, amount=…, doc_ref=…"). That is the same wall of
        text as the old question strings; the binding itself is the readable form.
        """
    binding = getattr(claim, "binding", None)
    if not isinstance(binding, dict):
        return claim.statement
    table = str(binding.get("table", ""))
    columns = [
        str(value)
        for key, value in sorted(binding.items())
        if key != "table" and isinstance(value, str) and value
    ]
    if len(columns) == 1:
        return columns[0] if "." in columns[0] else f"{table}.{columns[0]}".strip(".")
    return table or claim.statement


def _binding_name(claim: Claim) -> str:
    """The elected candidate, named as the thing it is."""
    binding = getattr(claim, "binding", None)
    if isinstance(binding, dict) and binding.get("table"):
        return str(binding["table"])
    return _candidate_name(claim)


def _first_sentence(text: str) -> str:
    """The ask, without the explanation that follows it.

        Questions are written ask-first exactly so this is safe: what follows the
        first '?' is the guide's definition and what the machine already tried,
        which belongs on the question card, not in every link to it.
        """
    head, mark, _ = " ".join(text.split()).partition("?")
    return f"{head}{mark}" if mark else head


def _claim_link(claim: Claim, label: str | None = None) -> LinkView:
    return _link(
        "claim",
        claim.id,
        label or f"{_short_id(claim.id)} — {_claim_title(claim)}",
    )


def _evidence_link(record: EvidenceRecord) -> LinkView:
    return _link(
        "evidence",
        record.id,
        f"{_short_id(record.id)} — {record.type.value}",
    )


def _question_link(card: ClarificationQuestion) -> LinkView:
    """Link on the question itself, not on its id and not on its whole body."""
    return _link("question", card.id, _first_sentence(card.question))


def _source_link(source: Source) -> LinkView:
    return _link("source", source.id, source.name)


def _population_text(record: EvidenceRecord) -> str:
    if record.exception_count is None or record.population is None:
        return "check failed"
    return (
        f"{record.exception_count:,} exception"
        f"{'s' if record.exception_count != 1 else ''} in {record.population:,} rows"
    )


def _headline(fact: ClaimFacts) -> str:
    """The one line a validator should be able to stop reading after."""
    if fact.derived is ClaimStatus.PROPOSED and fact.stage != "bound":
        return f"Never tested — {STAGE_LABELS[fact.stage]}."
    return _status_rationale(fact.claim, fact.evidence)


def _status_rationale(claim: Claim, evidence: list[EvidenceRecord]) -> str:
    """Why this claim sits where it does, and what its evidence adds up to.

    The counts here must agree with ``resolve_status``, so admissibility
    is *asked of the law* rather than restated: this function used to
    count every confirmation and could print "1 confirmation" beneath
    "nothing stronger than proposed evidence is live yet" — a
    contradiction with no way for a reader to resolve it. Unreachable
    until M5 built the operations that create confirmations, and then
    exactly the mirror loop's teaching moment, so it says the useful
    thing: the confirmation is there, and it does not count, and why.
    """
    live = [record for record in evidence if not record.stale]
    check_pass = sum(
        1 for record in live
        if record.type is EvidenceType.CHECK_RESULT
        and record.verdict is CheckVerdict.PASS
    )
    check_fail = sum(
        1 for record in live
        if record.type is EvidenceType.CHECK_RESULT
        and record.verdict is CheckVerdict.FAIL
    )
    confirmations = [
        record for record in live if record.type is EvidenceType.CONFIRMATION
    ]
    admissible = sum(
        1 for record in confirmations
        if confirmation_admissible(record, claim, evidence)
    )
    unscoped = len(confirmations) - admissible
    testimonial = sum(
        1 for record in live if record.type is EvidenceType.TESTIMONIAL
    )
    parts = []
    if check_pass:
        parts.append(
            f"{check_pass} passing check result{'s' if check_pass != 1 else ''}"
        )
    if check_fail:
        parts.append(
            f"{check_fail} failing check result{'s' if check_fail != 1 else ''}"
        )
    if admissible:
        parts.append(
            f"{admissible} confirmation{'s' if admissible != 1 else ''}"
        )
    if unscoped:
        parts.append(
            f"{unscoped} confirmation{'s' if unscoped != 1 else ''} that "
            "state no scope, and therefore count for nothing"
        )
    if testimonial:
        parts.append(
            f"{testimonial} testimonial{'s' if testimonial != 1 else ''}"
        )
    trail = ", ".join(parts) if parts else "no live status-bearing evidence"
    if claim.status is ClaimStatus.UNRESOLVED:
        why = "Conflict is present: at least one failing check coexists with supporting evidence."
    elif claim.status is ClaimStatus.CONTRADICTED:
        why = "At least one failing check is present and no competing supporting evidence remains live."
    elif claim.status is ClaimStatus.BUSINESS_CONFIRMED:
        why = "At least one admissible human confirmation is live and no failing check overrides it."
    elif claim.status is ClaimStatus.TEST_SUPPORTED:
        why = "At least one passing check is live and no failing check overrides it."
    elif unscoped:
        why = ("A human confirmed this, but it rests on someone's statement "
               "and the confirmation names no scope — so it cannot say who "
               "the rule holds for, and nothing has been settled.")
    else:
        why = "Nothing stronger than proposed evidence is live yet."
    return f"{why} Live trail: {trail}."



# -- documents (stage 2c) --------------------------------------------------

_ORIGIN_WORDS = {
    "text": "in running text",
    "table": "in a ruled table",
    "chart": "inside a chart",
}


def _build_documents(store: ProjectStore) -> DocumentsView:
    """What was read, in a reader's terms — never chunk ids or offsets."""
    documents = []
    for profile in sorted(store.documents.values(), key=lambda d: d.document):
        origins = []
        for kind in ("text", "table", "chart"):
            count = profile.kinds.get(kind, 0)
            if count:
                origins.append(f"{count} {_ORIGIN_WORDS[kind]}")
        charted = profile.kinds.get("chart", 0)
        caution = ""
        if charted:
            caution = (
                f"{charted} passage{'s' if charted != 1 else ''} of this "
                f"document {'sit' if charted != 1 else 'sits'} inside a "
                "figure. A number printed only in a "
                "chart cannot be checked against anything else on the page, "
                "so it is never allowed to corroborate a claim."
            )
        documents.append(DocumentView(
            name=profile.document,
            pages=f"{profile.pages} page{'s' if profile.pages != 1 else ''}",
            passages=(f"{profile.chunk_count} passage"
                      f"{'s' if profile.chunk_count != 1 else ''}"),
            origins=tuple(origins),
            caution=caution,
        ))
    return DocumentsView(
        heading="Documents read",
        explanation=_text(_plain(
            "Reading a document is measurement, like profiling a column: it "
            "produces a description and no beliefs. Where each passage sits "
            "on the page is worked out here, from the page itself, because "
            "a figure printed inside a chart looks exactly like ordinary "
            "text once it is extracted — and what a number is allowed to "
            "corroborate depends on knowing the difference."
        )),
        documents=tuple(documents),
    )


# -- the decision log ------------------------------------------------------

_VOICE = {
    Actor.HUMAN: ("a human", "voice-human", "\u25cf"),
    Actor.AI: ("the AI", "voice-ai", "\u25cb"),
    Actor.CHECK: ("a check", "voice-check", "\u25c6"),
    Actor.SYSTEM: ("the system", "voice-system", "\u25aa"),
}

_ACT_WORDS = {
    ActKind.WAIVE: "Decided this is not needed for the answer",
    ActKind.REQUIRE_AGAIN: "Put this back on the list",
    ActKind.LINK: "Pointed a required rule at the claim that states it",
    ActKind.ADD: "Added something the contract had missed",
    ActKind.CONFIRM: "Vouched for the whole dependency list",
}


def _decision(actor: Actor, what: str, driver: str, stage: str,
              settles: str = "", link: LinkView | None = None) -> DecisionView:
    label, css, marker = _VOICE.get(
        actor, (actor.value, "voice-system", "\u25aa"))
    return DecisionView(
        actor=label, actor_css=css, marker=marker, what=what, driver=driver,
        stage=stage, stage_label=BY_NAME[STAGE_ORDER[stage]].name,
        settles=settles, link=link,
    )


STAGE_ORDER = {stage.number: stage.name for stage in STAGES}


def _anchor_driver(record: EvidenceRecord) -> str:
    payload = record.payload or {}
    where = f"{payload.get('source', 'a document')} p.{payload.get('page', '?')}"
    quote = str(payload.get("quote", "")).strip()
    origin = _ORIGIN_WORDS.get(str(payload.get("kind", "")), "in the document")
    short = quote if len(quote) <= 110 else quote[:107] + "\u2026"
    return f"{where}, {origin}: \u201c{short}\u201d"


def _act_stage(act: KnowledgeAct) -> str:
    """Where an act sits in the flow — which depends on who made it.

    The AI linking a claim it read out of a policy is part of proposing;
    a human doing the same is part of clarification. Same act, different
    stage, because the stage spine is organised by whose move it is.
    """
    if act.kind is ActKind.ADD:
        return "1"
    if act.actor is Actor.AI:
        return "3"
    return "5"


def _act_driver(act: KnowledgeAct, linked: Claim | None) -> str:
    """What stood behind an act when nobody wrote a reason down."""
    if act.kind is ActKind.CONFIRM:
        return ("read the whole dependency list and vouched for it as it "
                "stood \u2014 a later change to the domain guide undoes this")
    if act.kind is ActKind.LINK and linked is not None:
        return (f"the claim \u201c{linked.statement[:90]}\u201d states this "
                "rule; the link routes the question, it does not vouch")
    return "no reason was recorded"


def _build_decisions(store: ProjectStore, claims: list[Claim],
                     facts: dict) -> DecisionLogView:
    """Every decision that changed what is believed, or that a human made.

    Deliberately not every event. Measurement decides nothing and a
    proposal decides nothing either, so the seventy-odd claims the model
    offered appear here as one line rather than seventy — otherwise the
    handful of moments that actually moved the project would be buried in
    them, which is the opposite of what this section is for.
    """
    by_id = {claim.id: claim for claim in claims}
    entries: list[tuple[object, DecisionView]] = []

    sources = sorted(store.sources.values(), key=lambda s: (s.created_at, s.id))
    if sources:
        named = ", ".join(s.name for s in sources[:4])
        more = f" and {len(sources) - 4} more" if len(sources) > 4 else ""
        entries.append((sources[0].created_at, _decision(
            Actor.HUMAN,
            f"Declared {len(sources)} source{'s' if len(sources) != 1 else ''} "
            "as the ground this project stands on",
            f"{named}{more} \u2014 chosen by a person, never discovered",
            "0",
        )))

    anchored = {
        record.claim_id for record in store.evidence.values()
        if record.type is EvidenceType.DOCUMENT_ANCHOR and record.claim_id
    }
    # Claims read out of a document get their own entry below, naming the
    # passage. Only the ones the model inferred from measurements are
    # summarised here, or the summary would credit profiles for something
    # a policy said.
    from_profiles = [c for c in claims
                     if c.created_by is Actor.AI and c.id not in anchored]
    if from_profiles:
        entries.append((from_profiles[0].created_at, _decision(
            Actor.AI,
            f"Proposed {len(from_profiles)} claim"
            f"{'s' if len(from_profiles) != 1 else ''} about how the data "
            "behaves",
            "measured column statistics and value overlaps \u2014 every one "
            "of them starts unproven, and the AI cannot change that",
            "3",
        )))

    for record in sorted(store.evidence.values(),
                         key=lambda e: (e.created_at, e.id)):
        claim = by_id.get(record.claim_id or "")
        subject = claim.statement if claim else "a claim"
        short = subject if len(subject) <= 90 else subject[:87] + "\u2026"
        link = _claim_link(claim, short) if claim else None

        if record.type is EvidenceType.CHECK_RESULT:
            if record.verdict is CheckVerdict.PASS:
                what = "A check ran and found nothing to refute it"
                settles = "now test-supported"
            elif record.verdict is CheckVerdict.FAIL:
                what = "A check refuted it"
                settles = "now contradicted, or unresolved if anything supports it"
            else:
                what = "A check ran and could not decide"
                settles = ""
            entries.append((record.created_at, _decision(
                Actor.CHECK, what, _population_text(record), "4",
                settles=settles, link=link,
            )))
        elif record.type is EvidenceType.CONFIRMATION:
            scope = record.scope.label() if record.scope else ""
            entries.append((record.created_at, _decision(
                Actor.HUMAN,
                "A person vouched for this claim"
                + (f", for {scope}" if scope else ""),
                str((record.payload or {}).get("note")
                    or "answered a clarification question"),
                "5",
                settles=("now business-confirmed" if scope else
                         "counts for nothing \u2014 no scope was stated"),
                link=link,
            )))
        elif record.type is EvidenceType.TESTIMONIAL:
            said = (record.statement or "").strip()
            entries.append((record.created_at, _decision(
                Actor.HUMAN,
                "A person stated this from their own knowledge",
                f"\u201c{said}\u201d \u2014 recorded word for word, which "
                "records that it was said and not that it is true",
                "5",
                link=link,
            )))
        elif record.type is EvidenceType.DOCUMENT_ANCHOR:
            entries.append((record.created_at, _decision(
                Actor.AI,
                "Read this out of a document and proposed it",
                _anchor_driver(record), "3",
                link=link,
            )))

    corrected = [
        record for record in store.evidence.values()
        if record.type is EvidenceType.DECLARATION
        and (record.payload or {}).get("decision") == "param_normalized"
    ]
    if corrected:
        params = sorted({str(r.payload.get("param")) for r in corrected})
        entries.append((min(r.created_at for r in corrected), _decision(
            Actor.SYSTEM,
            f"Read {len(corrected)} check parameter"
            f"{'s' if len(corrected) != 1 else ''} as something other than "
            "what the model wrote",
            "an unambiguous shape error (a qualified name where a bare one "
            f"belongs), in {', '.join(params)} \u2014 the check runs, and "
            "the correction is on each claim so it can be disagreed with",
            "3",
        )))

    for act in sorted(store.acts.values(), key=lambda a: (a.created_at, a.id)):
        target = act.ref or (act.item.name if act.item else act.answer_type)
        linked = by_id.get(act.claim_id or "")
        entries.append((act.created_at, _decision(
            act.actor,
            _ACT_WORDS.get(act.kind, act.kind.value)
            + (f": {target}" if target else ""),
            act.reason or act.note or _act_driver(act, linked),
            _act_stage(act),
            link=(_claim_link(linked, linked.statement[:90])
                  if linked else None),
        )))

    entries.sort(key=lambda pair: str(pair[0]))
    return DecisionLogView(
        heading="Decisions \u2014 who decided what, and what drove them",
        explanation=_text(_plain(
            "The other way to read this page. The sections below are the "
            "state of knowledge; this is how it got there. Only decisions "
            "appear \u2014 measuring something decides nothing, and neither "
            "does proposing it, so the AI's proposals are one line rather "
            "than one line each. What is left is the handful of moments that "
            "moved the project, each with the voice that made it and the "
            "thing that drove it."
        )),
        decisions=tuple(view for _when, view in entries),
        empty="Nothing has been decided yet \u2014 the project has only been declared.",
    )


def _locus(store: ProjectStore, claim_ids) -> tuple[str, ...]:
    """Where a check actually found the problem, in a reader's words.

    The exception samples have always held this — one period, one missing
    leg — and it has always been three clicks away. A reader told "the
    data must change" needs to know *which* data before that sentence is
    an instruction rather than a verdict.
    """
    found: list[str] = []
    for claim_id in claim_ids:
        claim = store.claims.get(claim_id)
        if claim is None:
            continue
        for record in store.evidence_for(claim):
            if (record.type is not EvidenceType.CHECK_RESULT
                    or record.verdict is not CheckVerdict.FAIL
                    or record.stale):
                continue
            where = ", ".join(
                f"{key} {value}"
                for sample in record.exception_samples[:2]
                for key, value in sample.items()
            )
            counted = _population_text(record)
            line = f"{_claim_title(claim)} — {counted}"
            found.append(f"{line}: {where}" if where else line)
    return tuple(dict.fromkeys(found))


def _build_unblock(store: ProjectStore,
                   readiness_maps: list) -> UnblockView:
    blocking = [
        item for readiness in readiness_maps if readiness
        for item in readiness.blocking()
    ]
    if not blocking:
        return UnblockView(
            blocked=False,
            heading="Nothing is blocked",
            summary="",
            routes=(),
            settled="Every dependency this answer rests on is either "
                    "satisfied or a named limitation. There is nothing here "
                    "to clear.",
        )

    answerable = [i for i in blocking if i.ground is not Ground.ALL_CONTRADICTED]
    refuted = [i for i in blocking if i.ground is Ground.ALL_CONTRADICTED]

    routes = []
    if answerable:
        routes.append(RouteView(
            heading="You answer",
            css="route-human",
            items=tuple(i.ref for i in answerable),
            explanation=(
                "Candidates exist and no check can choose between them. "
                "These are waiting on a person, and each one has a "
                "clarification question in section 5 with the candidates "
                "side by side."
            ),
            alternative=(
                "Or, if the answer genuinely does not rest on one of them, "
                "waive it with a reason: the item stays in the map, struck "
                "through, and the verdict carries it as a stated limitation "
                "rather than a silent omission."
            ),
        ))
    if refuted:
        routes.append(RouteView(
            heading="The data has to change",
            css="route-data",
            items=tuple(i.ref for i in refuted),
            explanation=(
                "Every candidate was tested and refuted. This is not a "
                "missing answer but a wrong one, so no amount of answering "
                "will settle it — correct the data and run the checks "
                "again. The new reading supersedes the old one and the "
                "claim settles."
            ),
            where=_locus(store, [cid for i in refuted for cid in i.claim_ids]),
            alternative=(
                "Or waive it with a reason, if you accept the discrepancy "
                "and want the answer anyway — recorded as your decision, "
                "visible beside the verdict."
            ),
        ))

    counts = " and ".join(
        f"{len(group)} {word}"
        for group, word in ((answerable, "waiting on you"),
                            (refuted, "waiting on the data"))
        if group
    )
    return UnblockView(
        blocked=True,
        heading="What would move this forward",
        summary=(
            f"{len(blocking)} dependenc"
            f"{'ies' if len(blocking) != 1 else 'y'} block the answer — "
            f"{counts}."
        ),
        routes=tuple(routes),
        settled="",
    )


def _answer_type_views(declared) -> tuple[AnswerTypeView, ...]:
    """The guide's answer types, in the order it declares them.

    Read from the raw YAML like the rest of this panel, not from a loaded
    `DomainGuide`: section 0 must still describe a guide that fails the
    coherence lint, and that is exactly when a reader most needs to see it.
    """
    if not isinstance(declared, dict):
        return ()
    views = []
    for name, spec in declared.items():
        spec = spec if isinstance(spec, dict) else {}
        requires = []
        for item in spec.get("requires") or ():
            if not isinstance(item, dict):
                continue
            for kind in ("object", "field", "rule"):
                if item.get(kind) is not None:
                    requires.append(f"{kind}: {item[kind]}")
                    break
        views.append(AnswerTypeView(
            name=str(name),
            definition=str(spec.get("definition", "")).strip(),
            requires=tuple(requires),
        ))
    return tuple(views)


def _decided_by_label(spec) -> str:
    decided_by = spec.get("decided_by", "") if isinstance(spec, dict) else ""
    if not decided_by:
        return ""
    if decided_by == "clarification":
        return "decided by humans (clarification question)"
    if decided_by == "slot":
        fills = spec.get("fills") or "?"
        return f"slot — elected as the '{fills}' of its object's law"
    return f"elected by the {decided_by} law"


def _build_domain_pack(root: Path, config: dict) -> DomainPackView:
    """This project's domain pack — not the whole catalog.

        A law of another domain is not an input here: the guide lint refuses to
        let this guide declare one. Listing it under "what this project
        declared" would be a false claim about the project's inputs, so the
        other domains are counted, not enumerated.
        """
    declared_sources = tuple(
        DeclaredSourceView(
            name=str(source.get("name", "?")),
            kind=str(source.get("kind", "?")),
            location=str(source.get("location", "?")),
        )
        for source in (config.get("sources") or [])
    )
    path = _guide_path(root, config)
    if path is None:
        panel = DomainGuidePanelView(state="missing")
        domain = ""
    else:
        try:
            pack = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except OSError:
            panel = DomainGuidePanelView(state="unreadable", path=str(path))
            domain = ""
        else:
            objects = pack.get("objects") or {}
            entries = []
            field_count = 0
            for name, spec in objects.items():
                fields = tuple(
                    GuideEntryView(
                        name=str(field_name),
                        decision=_decided_by_label(field_spec),
                        definition=str(
                            field_spec.get("definition", "")
                            if isinstance(field_spec, dict)
                            else field_spec
                        ).strip(),
                    )
                    for field_name, field_spec in (
                        (spec.get("fields") or {}).items()
                        if isinstance(spec, dict)
                        else ()
                    )
                )
                field_count += len(fields)
                entries.append(
                    GuideEntryView(
                        name=str(name),
                        decision=_decided_by_label(spec),
                        definition=str(
                            spec.get("definition", "")
                            if isinstance(spec, dict)
                            else spec
                        ).strip(),
                        fields=fields,
                    )
                )
            domain = str(pack.get("domain", ""))
            panel = DomainGuidePanelView(
                state="loaded",
                path=str(path),
                domain=str(pack.get("domain", "?")),
                object_count=len(objects),
                field_count=field_count,
                entries=tuple(entries),
                answer_types=_answer_type_views(pack.get("answer_types") or {}),
            )
    tagged = [(name, spec) for name, spec in REGISTRY.items() if spec.domain]
    generic = len(REGISTRY) - len(tagged)
    mine = (
        [(name, spec) for name, spec in tagged if spec.domain == domain]
        if domain
        else tagged
    )
    foreign = len(tagged) - len(mine)
    laws = tuple(
        DomainLawView(name=name, domain=spec.domain or "", file=spec.file)
        for name, spec in mine
    )
    if laws:
        empty_message = None
    elif domain:
        empty_message = _text(
            _plain("No domain law is shipped for "),
            _styled(domain, "strong"),
            _plain(
                ". Every business object in this guide must therefore be "
                "settled by a human ("
            ),
            _styled("decided_by: clarification", "code"),
            _plain(
                ") — nothing here can be promoted by a check."
            ),
        )
    else:
        empty_message = _text(_plain("No domain-law templates in the registry."))
    other = (
        f" A further {foreign} domain law{'s' if foreign != 1 else ''} in the "
        f"catalog belong{'' if foreign != 1 else 's'} to other domains and "
        "cannot be used here — the guide lint rejects a law from a foreign "
        "domain."
        if foreign
        else ""
    )
    note = (
        f"The other {generic} templates in the catalog are generic data "
        "checks (reference check, duplicates, coverage …) — they carry no "
        f"domain knowledge and work in any domain.{other}"
    )
    return DomainPackView(
        intro=DOMAIN_PACK_INTRO,
        sources=declared_sources,
        guide=panel,
        laws=DomainLawsView(
            domain=domain,
            laws=laws,
            generic_count=generic,
            foreign_count=foreign,
            empty_message=empty_message,
            note=note,
        ),
    )


def _stale_reasons(store: ProjectStore) -> dict[str, str]:
    """One sentence per stale record, derived once for the whole report.

    "stale: true" is a fact about our bookkeeping; *why* is the fact about
    the reader's data. The two are told apart in `staleness.why_stale` —
    a later run replaced this reading, or the data it read moved — and
    neither is stored, so the report is where the distinction has to be
    made legible.
    """
    stamps = current_stamps(store.sources.values())
    return {
        record.id: why_stale(record, store, stamps)
        for record in store.evidence.values()
        if record.stale
    }


def _declarations_by_key(
    records: Iterable[EvidenceRecord],
) -> dict[tuple[str, str, str], list[EvidenceRecord]]:
    out: dict[tuple[str, str, str], list[EvidenceRecord]] = defaultdict(list)
    for record in records:
        if record.type is not EvidenceType.DECLARATION:
            continue
        payload = record.payload or {}
        key = (
            str(payload.get("source", "")),
            str(payload.get("table", "")),
            str(payload.get("column", "")),
        )
        out[key].append(record)
    return out


def _claims_by_source(claims: list[Claim]) -> dict[str, list[Claim]]:
    out: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        for source_id in claim.source_ids:
            out[source_id].append(claim)
    return out


def _role_bindings_by_column(claims: list[Claim]) -> dict[str, list[Claim]]:
    out: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        binding = getattr(claim, "binding", None)
        if not isinstance(binding, dict):
            continue
        table = binding.get("table")
        column = binding.get("column")
        if table and column:
            out[f"{table}.{column}"].append(claim)
    return out


def _candidates_by_column(matrix: dict) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for candidate in matrix.get("candidates", []):
        left = str(candidate.get("left", ""))
        right = str(candidate.get("right", ""))
        if not left or not right:
            continue
        shared = {
            "containment": candidate.get("containment"),
            "overlap": candidate.get("overlap"),
        }
        out[left].append({"other": right, **shared})
        out[right].append({"other": left, **shared})
    for items in out.values():
        items.sort(
            key=lambda item: (
                -float(item["containment"]),
                -int(item["overlap"]),
                item["other"],
            )
        )
    return out


def _profiles_by_source(
    profiles: list[DataProfile],
) -> dict[str, list[DataProfile]]:
    out: dict[str, list[DataProfile]] = defaultdict(list)
    for profile in profiles:
        out[profile.source_id].append(profile)
    return out


def _build_column(
    source_name: str,
    profile: DataProfile,
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    role_bindings: dict[str, list[Claim]],
    candidates_by_column: dict[str, list[dict]],
) -> ColumnView:
    key = f"{profile.table}.{profile.column}"
    declarations = tuple(
        EvidenceReferenceView(_evidence_link(record), _json_text(record.payload))
        for record in declarations_by_key.get(
            (source_name, profile.table, profile.column), []
        )
    )
    candidates = tuple(
        CandidateOverlapView(
            other=str(item["other"]),
            containment=str(item["containment"]),
            overlap=str(item["overlap"]),
        )
        for item in candidates_by_column.get(key, [])
    )
    bindings = tuple(
        LinkStatusView(_claim_link(claim), status=claim.status.value)
        for claim in role_bindings.get(key, [])
    )
    return ColumnView(
        key=key,
        details=(
            ("profile_id", profile.id),
            ("stats", _json_text(profile.stats)),
        ),
        declarations=declarations,
        candidates=candidates,
        role_bindings=bindings,
    )


def _build_tables(
    source_name: str,
    profiles: list[DataProfile],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    role_bindings: dict[str, list[Claim]],
    candidates_by_column: dict[str, list[dict]],
) -> tuple[TableView, ...]:
    tables: dict[str, list[DataProfile]] = defaultdict(list)
    for profile in profiles:
        tables[profile.table].append(profile)
    return tuple(
        TableView(
            name=table,
            declarations=tuple(
                EvidenceReferenceView(
                    _evidence_link(record), _json_text(record.payload)
                )
                for record in declarations_by_key.get(
                    (source_name, table, "*"), []
                )
            ),
            columns=tuple(
                _build_column(
                    source_name,
                    profile,
                    declarations_by_key,
                    role_bindings,
                    candidates_by_column,
                )
                for profile in columns
            ),
        )
        for table, columns in sorted(tables.items())
    )


def _build_measurement(
    store: ProjectStore,
    sources: list[Source],
    profiles: list[DataProfile],
    claims: list[Claim],
    matrix: dict,
) -> MeasurementView:
    declarations = _declarations_by_key(store.evidence.values())
    claims_by_source = _claims_by_source(claims)
    role_bindings = _role_bindings_by_column(claims)
    candidates = _candidates_by_column(matrix)
    profiles_by_source = _profiles_by_source(profiles)
    source_views = tuple(
        SourceView(
            id=source.id,
            name=source.name,
            kind=source.kind,
            details=(
                ("id", source.id),
                ("kind", source.kind),
                ("location", source.location),
                ("fingerprint", _json_text(source.fingerprint)),
            ),
            claims=tuple(
                LinkStatusView(_claim_link(claim), status=claim.status.value)
                for claim in claims_by_source.get(source.id, [])
            ),
            tables=_build_tables(
                source.name,
                profiles_by_source.get(source.id, []),
                declarations,
                role_bindings,
                candidates,
            ),
            profile_count=len(profiles_by_source.get(source.id, [])),
        )
        for source in sources
    )
    orphan_profiles = [
        profile for profile in profiles if profile.source_id not in store.sources
    ]
    candidate_count = len(matrix.get("candidates", []))
    matrix_view = MatrixView(
        found=bool(matrix),
        summary=(
            f"{candidate_count} candidate overlaps, "
            f"{matrix.get('pairs_examined', 0)} pairs examined, "
            f"threshold {matrix.get('threshold', 'n/a')}."
            if matrix
            else ""
        ),
        warnings=tuple(str(warning) for warning in matrix.get("warnings", [])),
    )
    return MeasurementView(
        source_count=len(sources),
        project_line=(
            f"{len(sources)} sources · {len(profiles)} column profiles · "
            f"{candidate_count} candidate overlaps · {len(store.checks)} checks · "
            f"{len(store.evidence)} evidence records."
        ),
        matrix=matrix_view,
        sources=source_views,
        orphan_tables=_build_tables(
            "missing-source",
            orphan_profiles,
            declarations,
            role_bindings,
            candidates,
        ),
    )


def _check_sentence(check: CheckPlan, spec) -> str:
    """What this check tries to break — the definition's own words."""
    if spec is not None and spec.tests:
        return " ".join(spec.tests.split())
    return (
        f"A test of type '{check.template}': if the data breaks it, the rows "
        "that break it are the refutation."
    )


def _rendered_sql_by_check_plan(
    evidence: list[EvidenceRecord],
) -> dict[str, str]:
    """check id → the rendered SQL its result recorded (latest run wins)."""
    out: dict[str, str] = {}
    for record in evidence:
        if (
            record.type is not EvidenceType.CHECK_RESULT
            or not record.check_plan_id
        ):
            continue
        sql = str(record.payload.get("sql", "")) if record.payload else ""
        if sql:
            out[record.check_plan_id] = sql
    return out


def _build_check(check: CheckPlan, rendered_sql: str) -> CheckView:
    details = [
        ("id", check.id),
        ("template", check.template),
        ("created_at", check.created_at.isoformat()),
        ("params", _json_text(check.params)),
    ]
    if check.roles:
        details.insert(2, ("roles", ", ".join(check.roles)))
    spec = REGISTRY.get(check.template)
    domain = ""
    if spec is not None:
        domain = spec.domain or ""
        if spec.tolerances:
            details.append(("default tolerances", _json_text(spec.tolerances)))
    return CheckView(
        id=check.id,
        short_id=_short_id(check.id),
        template=check.template,
        domain=domain,
        sentence=_check_sentence(check, spec),
        rendered_sql=rendered_sql,
        provenance=ProvenanceView(
            _reference("checks", check.id),
            ("planned by the AI, run by the engine",),
        ),
        details=tuple(details),
    )


def _evidence_sentence(record: EvidenceRecord) -> str:
    """What this record says, derived from what it holds — never from prose."""
    if record.type is EvidenceType.CHECK_RESULT:
        counted = _population_text(record)
        rate = record.exception_rate()
        share = f" ({rate:.2%} of the rows)" if rate else ""
        if record.verdict is CheckVerdict.PASS:
            rows = (
                f"{record.population:,} rows"
                if record.population is not None
                else "the rows it read"
            )
            return (
                "The check ran and found nothing to refute the claim — "
                f"{rows} examined, no exceptions."
            )
        if record.verdict is CheckVerdict.FAIL:
            return f"The check refuted the claim: {counted}{share}."
        return f"The check could not decide: {counted}."
    if record.type is EvidenceType.CONFIRMATION:
        return (
            "A human confirmed this claim. Human confirmation can promote a "
            "claim; that is why it is recorded with its scope."
        )
    if record.type is EvidenceType.TESTIMONIAL:
        return (
            "A human stated this, in their own words. It is recorded verbatim, "
            "as evidence — not rewritten."
        )
    if record.type is EvidenceType.DOCUMENT_ANCHOR:
        payload = record.payload or {}
        where = (f"{payload.get('source', 'a document')}, "
                 f"page {payload.get('page', '?')}")
        origin = str(payload.get("kind", "text"))
        if origin == "chart":
            return (
                f"Read inside a chart in {where}. A number printed only in a "
                "figure cannot be checked against anything else on the page, "
                "so it is recorded and never allowed to support the claim."
            )
        if origin == "table":
            return (
                f"Read from a ruled table in {where}. It shows where the "
                "wording comes from; on its own it settles nothing."
            )
        return (
            f"Read from the running text of {where}. It shows where the "
            "wording comes from; on its own it settles nothing."
        )
    payload = record.payload or {}
    if payload.get("decision") == "param_normalized":
        if payload.get("given") is None:
            return (
                f"The check's {payload.get('param')!r} was missing, and every "
                f"column the model named sat on {payload.get('read_as')!r}, so "
                "that is what it was read as. Supplied here, not by the model, "
                "and only because the columns agreed — where they disagree "
                "nothing is guessed."
            )
        return (
            f"The model gave {payload.get('given')!r} for the check's "
            f"{payload.get('param')!r}, where a bare name belongs. It was "
            f"read as {payload.get('read_as')!r} and the check ran. Recorded "
            "because a correction nobody can see is a correction nobody can "
            "disagree with."
        )
    return (
        "A recorded processing decision. It carries no verdict and promotes "
        "nothing — it exists so that nothing happens silently."
    )


def _evidence_voice(record: EvidenceRecord) -> QuoteView | None:
    """The human's words verbatim; the machine's words attributed to it.

        A statement is shown because it is legible, never because it decides:
        the derived sentence above already said what this record does.
        """
    said = (record.statement or "").strip()
    payload = record.payload or {}
    if not said and record.type is EvidenceType.DECLARATION:
        said = str(payload.get("reason", "")).strip()
    if record.type is EvidenceType.DOCUMENT_ANCHOR:
        # The document's own voice. Shown verbatim because that is the
        # anchor's entire value: it points at words somebody really wrote,
        # and a reader can go to the page and find them.
        quoted = str(payload.get("quote", "")).strip()
        if not quoted:
            return None
        origin = _ORIGIN_WORDS.get(str(payload.get("kind", "")), "in the document")
        return QuoteView(
            css="document-said",
            text=quoted,
            cite=_text(
                _plain("— "),
                _styled(str(payload.get("source", "a document")), "strong"),
                _plain(f", page {payload.get('page', '?')}, {origin}"),
            ),
        )
    if not said:
        return None
    if record.actor is Actor.HUMAN:
        return QuoteView(
            css="quote",
            text=said,
            cite=_text(_plain("— stated by a human, verbatim")),
        )
    return QuoteView(
        css="ai-said",
        text=said,
        cite=_text(
            _plain("— recorded by "),
            _styled(record.actor.value, "code"),
            _plain(", unverified: it explains, it does not decide"),
        ),
    )


def _evidence_author(record: EvidenceRecord) -> str:
    who = {
        Actor.AI: "written by the AI — structurally unable to promote a claim",
        Actor.CHECK: "written by the engine that ran the check",
        Actor.HUMAN: "written by a human",
        Actor.SYSTEM: "written by the system",
    }
    return who.get(record.actor, f"written by {record.actor.value}")


def _build_evidence(
    record: EvidenceRecord,
    claims: dict[str, Claim],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    checks: dict[str, CheckPlan],
    stale_reasons: dict[str, str],
) -> EvidenceView:
    details = [
        ("id", record.id),
        ("type", record.type.value),
        ("actor", record.actor.value),
        ("created_at", record.created_at.isoformat()),
        ("stale", str(record.stale).lower()),
    ]
    if record.stale and stale_reasons.get(record.id):
        details.append(("why stale", stale_reasons[record.id]))
    if record.claim_id:
        linked = claims.get(record.claim_id)
        details.append(
            ("claim", linked.statement if linked else record.claim_id)
        )
    if record.type is EvidenceType.CHECK_RESULT:
        details.extend(
            [
                ("verdict", record.verdict.value if record.verdict else "—"),
                (
                    "population",
                    str(record.population)
                    if record.population is not None
                    else "—",
                ),
                (
                    "exception_count",
                    str(record.exception_count)
                    if record.exception_count is not None
                    else "—",
                ),
                (
                    "exception_rate",
                    f"{record.exception_rate():.2%}"
                    if record.exception_rate() is not None
                    else "—",
                ),
                ("result_ref", record.result_ref or "—"),
            ]
        )
    if record.type is EvidenceType.CONFIRMATION:
        details.append(
            (
                "mirror_loop_scope",
                "explicit"
                if record.scope and record.scope.is_explicit()
                else "not explicit",
            )
        )
    if record.scope:
        details.append(("scope", _json_text(record.scope.model_dump(mode="json"))))
    if record.statement:
        details.append(("statement", record.statement))
    if record.source_fingerprints:
        details.append(
            ("source_fingerprints", _json_text(record.source_fingerprints))
        )
    if record.type is EvidenceType.DOCUMENT_ANCHOR:
        payload = record.payload or {}
        details.append(("document", str(payload.get("source", ""))))
        details.append(("page", str(payload.get("page", ""))))
        details.append((
            "where on the page",
            _ORIGIN_WORDS.get(str(payload.get("kind", "")), "unknown"),
        ))
    elif record.payload:
        details.append(("payload", _json_text(record.payload)))
    check_link = None
    check_template = ""
    if record.check_plan_id:
        check = checks.get(record.check_plan_id)
        if check:
            check_link = _link(
                "check",
                check.id,
                f"{check.template} {_short_id(check.id)}",
            )
            check_template = check.template
        else:
            details.append(
                (
                    "check_plan_id",
                    f"{record.check_plan_id} (not persisted)",
                )
            )
    touched_table = ""
    touched_column = ""
    sibling_declarations = 0
    if record.type is EvidenceType.DECLARATION:
        source = str(record.payload.get("source", ""))
        touched_table = str(record.payload.get("table", ""))
        touched_column = str(record.payload.get("column", ""))
        siblings = declarations_by_key.get(
            (source, touched_table, touched_column), []
        )
        sibling_declarations = len(siblings) if len(siblings) > 1 else 0
    samples = record.exception_samples or []
    return EvidenceView(
        id=record.id,
        short_id=_short_id(record.id),
        type=record.type.value,
        badge_kind="verdict" if record.verdict else "type",
        badge_value=(
            record.verdict.value if record.verdict else record.type.value
        ),
        sentence=_evidence_sentence(record),
        voice=_evidence_voice(record),
        check_link=check_link,
        check_template=check_template,
        sample_headers=tuple(str(key) for key in samples[0].keys())
        if samples
        else (),
        sample_rows=tuple(
            tuple(_stringify(value) for value in sample.values())
            for sample in samples
        ),
        touched_table=touched_table,
        touched_column=touched_column,
        sibling_declarations=sibling_declarations,
        provenance=ProvenanceView(
            _reference("evidence", record.id),
            (_evidence_author(record),),
        ),
        details=tuple(details),
    )


def _questions_by_claim(
    questions: list[ClarificationQuestion],
) -> dict[str, list[ClarificationQuestion]]:
    out: dict[str, list[ClarificationQuestion]] = defaultdict(list)
    for card in questions:
        for claim_id in card.claim_ids:
            out[claim_id].append(card)
    return out


def _reverse_claim_links(
    claims: list[Claim],
) -> tuple[dict[str, list[Claim]], dict[str, list[Claim]]]:
    reverse_depends: dict[str, list[Claim]] = defaultdict(list)
    reverse_derived: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        for dependency in claim.depends_on:
            reverse_depends[dependency].append(claim)
        if claim.derived_from:
            reverse_derived[claim.derived_from].append(claim)
    return reverse_depends, reverse_derived


def _source_fingerprint_names(
    records: list[EvidenceRecord],
) -> list[str]:
    return sorted(
        {
            name
            for record in records
            for name in record.source_fingerprints
        }
    )


def _claim_fields(claim: Claim) -> tuple[tuple[str, str], ...]:
    return (
        ("id", claim.id),
        ("created_by", claim.created_by.value),
        ("created_at", claim.created_at.isoformat()),
        ("status", claim.status.value),
        (
            "predicate",
            _json_text(claim.predicate.model_dump(mode="json"))
            if claim.predicate
            else "—",
        ),
        (
            "scope",
            _json_text(claim.scope.model_dump(mode="json"))
            if claim.scope
            else "—",
        ),
        (
            "validity",
            _json_text(claim.validity.model_dump(mode="json"))
            if claim.validity
            else "—",
        ),
    )


def _subtype_fields(
    claim: Claim,
) -> tuple[tuple[str, str], ...] | None:
    items = []
    if hasattr(claim, "term"):
        items.append(("term", getattr(claim, "term")))
    if hasattr(claim, "definition"):
        items.append(("definition", getattr(claim, "definition")))
    if hasattr(claim, "role"):
        items.append(("role", getattr(claim, "role")))
    if hasattr(claim, "binding"):
        items.append(("binding", _json_text(getattr(claim, "binding"))))
    return tuple(items) if items else None


def _stage_steps(fact: ClaimFacts) -> tuple[StageStepView, ...]:
    """How far this claim got, and which step stopped it.

        Four steps, always all four shown: a claim that never reached a step is
        more informative than one whose missing steps are simply absent.
        """
    bound = bool(fact.checks)
    settled = fact.derived is not ClaimStatus.PROPOSED
    return (
        StageStepView("1 proposed", "done", "the AI wrote it"),
        StageStepView(
            "2 planned",
            "done" if bound else "stopped",
            "bound to a check" if bound else STAGE_LABELS[fact.stage],
        ),
        StageStepView(
            "3 judged",
            "done" if fact.executed else "stopped",
            "a check ran" if fact.executed else "no check ran",
        ),
        StageStepView(
            "4 settled",
            "done" if settled else "stopped",
            (
                f"status {fact.derived.value}"
                if settled
                else "still proposed — nothing has spoken for or against it"
            ),
        ),
    )


def _feeds_text(
    fact: ClaimFacts,
    questions_by_claim: dict[str, list[ClarificationQuestion]],
    reverse_depends: dict[str, list[Claim]],
) -> str:
    """What rests on this claim — the reason a wrong one is expensive."""
    cards = len(questions_by_claim.get(fact.claim.id, []))
    dependants = len(reverse_depends.get(fact.claim.id, []))
    parts = []
    if cards:
        parts.append(
            f"{cards} open question{'s' if cards != 1 else ''} rest"
            f"{'' if cards != 1 else 's'} on it"
        )
    if dependants:
        parts.append(
            f"{dependants} claim{'s' if dependants != 1 else ''} depend"
            f"{'' if dependants != 1 else 's'} on it"
        )
    return ", ".join(parts) or "nothing rests on it yet"


def _rationale_view(rationale: str | None) -> QuoteView | str | None:
    """The model's reason for proposing this — read from the disposable call
        log, never stored on the claim.

        Why it may be missing is the point, not an accident: a proposal's
        rationale is not evidence, so it is allowed to fade. What survives is
        what the checks did with the proposal.
        """
    if rationale is None:
        return None
    if not rationale:
        return (
            "The AI's reason for proposing this is not in the call log. A "
            "rationale explains a guess, and a guess is not evidence — so "
            "nothing stores it, and it is allowed to disappear. What survives "
            "is what the checks did with the proposal."
        )
    return QuoteView(
        css="ai-said",
        text=rationale,
        cite=_text(
            _plain(
                "— the AI's reason for proposing this, unverified; read from "
                "the call log, never stored on the claim"
            )
        ),
    )


def _no_check_view(fact: ClaimFacts) -> NoCheckView:
    """What stands where the check would have stood: why none was built."""
    if fact.stage == "unbound":
        return NoCheckView(
            stage="",
            explanation=_text(
                _plain(
                    "No check, and no recorded reason — V2 has not run on this "
                    "claim yet."
                )
            ),
            reason="",
        )
    who = {
        "unbindable": "The model declined to bind this claim",
        "semantic_only": "No check definition can test this claim",
        "skipped": "Validation rejected the model's binding",
    }[fact.stage]
    return NoCheckView(
        stage=fact.stage,
        explanation=_text(
            _plain(f"{who}, so nothing ever tested it and it stays "),
            _styled("proposed", "em"),
            _plain("."),
        ),
        reason=fact.no_check_reason or "no reason recorded",
    )


def _build_claim(
    fact: ClaimFacts,
    store: ProjectStore,
    questions_by_claim: dict[str, list[ClarificationQuestion]],
    reverse_depends: dict[str, list[Claim]],
    reverse_derived: dict[str, list[Claim]],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    rationale: str | None,
    stale_reasons: dict[str, str],
) -> ClaimView:
    claim = fact.claim
    predicate = claim.predicate.name if claim.predicate else ""
    role = claim.role if isinstance(claim, MappingClaim) else ""
    title = _claim_title(claim)
    search = " ".join(
        filter(None, [claim.statement, fact.derived.value, predicate, role])
    ).lower()
    hint = " · ".join(
        filter(
            None,
            [
                f"predicate: {predicate}" if predicate else "",
                f"role: {role}" if role else "",
                STAGE_LABELS[fact.stage] if fact.stage != "bound" else "",
            ],
        )
    )
    index = ClaimIndexView(
        id=claim.id,
        short_id=_short_id(claim.id),
        title=title,
        derived_status=fact.derived.value,
        stage=fact.stage,
        executed=fact.executed,
        predicate=predicate,
        role=role,
        search=search,
        hint=hint,
    )
    sources = []
    for source_id in claim.source_ids:
        if source_id in store.sources:
            sources.append(LinkStatusView(_source_link(store.sources[source_id])))
    fingerprints = _source_fingerprint_names(fact.evidence)
    for name in fingerprints:
        matched = next(
            (
                source
                for source in store.sources.values()
                if source.name == name
            ),
            None,
        )
        if matched and matched.id not in claim.source_ids:
            sources.append(
                LinkStatusView(
                    _source_link(matched),
                    note="via evidence fingerprint",
                )
            )
        elif not matched:
            sources.append(
                LinkStatusView(
                    _link("", "", name),
                    note="fingerprint only",
                )
            )
    binding = getattr(claim, "binding", None)
    bound_table = ""
    bound_column = ""
    if isinstance(binding, dict):
        table = binding.get("table")
        column = binding.get("column")
        if table and column:
            bound_column = f"{table}.{column}"
        elif table:
            bound_table = str(table)
    rendered_sql = _rendered_sql_by_check_plan(fact.evidence)
    checks = tuple(
        _build_check(check, rendered_sql.get(check.id, ""))
        for check in fact.checks
    )
    evidence = tuple(
        _build_evidence(
            record,
            store.claims,
            declarations_by_key,
            store.checks,
            stale_reasons,
        )
        for record in fact.evidence
    )
    dependencies = tuple(
        LinkStatusView(_claim_link(store.claims[claim_id]), store.claims[claim_id].status.value)
        for claim_id in claim.depends_on
        if claim_id in store.claims
    )
    reverse_dependencies = tuple(
        LinkStatusView(_claim_link(other), other.status.value)
        for other in reverse_depends.get(claim.id, [])
    )
    derived_children = tuple(
        LinkStatusView(_claim_link(other), other.status.value)
        for other in reverse_derived.get(claim.id, [])
    )
    questions = tuple(
        _question_link(card)
        for card in questions_by_claim.get(claim.id, [])
    )
    lineage = None
    if claim.derived_from or claim.derived_from_evidence:
        parent = store.claims.get(claim.derived_from or "")
        parent_evidence = store.evidence.get(
            claim.derived_from_evidence or ""
        )
        lineage = LineageView(
            parent=_claim_link(parent) if parent else None,
            evidence=_evidence_link(parent_evidence)
            if parent_evidence
            else None,
        )
    divergence = None
    if fact.diverges:
        divergence = _text(
            _plain("Stored status "),
            _styled(claim.status.value, "status"),
            _plain(" differs from the status derived from live evidence "),
            _styled(fact.derived.value, "status"),
            _plain(
                ". The derived status is the truth; the stored one is out of "
                "date (re-run the sweep)."
            ),
        )
    proposal = QuoteView(
        css="ai-said",
        text=claim.statement,
        cite=_text(
            _plain("— as "),
            _styled(claim.created_by.value, "code"),
            _plain(
                " wrote it, verbatim; a proposal, not a finding"
            ),
        ),
    )
    return ClaimView(
        index=index,
        stored_status=claim.status.value,
        headline=_headline(fact),
        stage_steps=_stage_steps(fact),
        rationale=_rationale_view(rationale),
        provenance=ProvenanceView(
            _reference("claims", claim.id),
            (
                f"proposed by {claim.created_by.value}",
                _feeds_text(fact, questions_by_claim, reverse_depends),
            ),
        ),
        diverges=fact.diverges,
        divergence=divergence,
        statement=claim.statement,
        created_by=claim.created_by.value,
        proposal=proposal,
        proposed_details=(
            ("predicate", predicate or "—"),
            (
                "params",
                _json_text(claim.predicate.params)
                if claim.predicate
                else "—",
            ),
            ("proposed by", claim.created_by.value),
            ("funnel stage", STAGE_LABELS[fact.stage]),
        ),
        subtype_details=_subtype_fields(claim),
        checks=checks,
        no_check=None if checks else _no_check_view(fact),
        evidence=evidence,
        sources=tuple(sources),
        bound_table=bound_table,
        bound_column=bound_column,
        questions=questions,
        assumptions=tuple(claim.open_assumptions),
        dependencies=dependencies,
        reverse_dependencies=reverse_dependencies,
        derived_children=derived_children,
        lineage=lineage,
        details=_claim_fields(claim),
    )


#: The bands a question falls into, best first. The distinction that
#: matters is the first one: a reader with twenty-three open questions is
#: not asking "which are hard" but "which of these is between me and my
#: answer". Everything below `blocks` is real work that this particular
#: question does not wait for.
_BANDS = (
    (0, "blocks the answer",
     "the answer cannot be produced until this is settled"),
    (1, "limits the answer",
     "the answer can be produced, but with this named as a limitation"),
    (2, "bears on the answer",
     "it touches what the answer is computed from"),
    (3, "not on this path",
     "nothing this question holds up is required by the question that "
     "was asked"),
)


def _question_bearing(maps) -> dict[str, tuple[int, str, str]]:
    """claim id -> the best band any readiness item puts it in.

    Derived from the ReadinessMap rather than from the question's wording,
    because the wording is stored project data and the map is recomputed
    on every read. A question is urgent for as long as the item resting on
    it is unsatisfied, and stops being urgent the moment that changes —
    with nothing to migrate.
    """
    bands: dict[str, tuple[int, str, str]] = {}
    for readiness in maps:
        blocking = {item.ref for item in readiness.blocking()}
        limiting = {item.ref for item in readiness.limitations()}
        for item in readiness.items:
            if item.ref in blocking:
                band = _BANDS[0]
            elif item.ref in limiting:
                band = _BANDS[1]
            elif not item.satisfied:
                band = _BANDS[2]
            else:
                continue
            for claim_id in item.claim_ids:
                current = bands.get(claim_id)
                if current is None or band[0] < current[0]:
                    bands[claim_id] = (band[0], band[1],
                                       f"{item.ref} — {band[2]}")
    return bands


def _quoted(refs: Iterable[str]) -> str:
    values = [f"'{ref}'" for ref in refs]
    if len(values) <= 1:
        return "".join(values)
    return f"{', '.join(values[:-1])} and {values[-1]}"


def _build_question_tally(open_questions: tuple[QuestionView, ...],
                          questions: list[ClarificationQuestion],
                          readiness_maps: list) -> QuestionTallyView:
    """Count the list by band, then say what clearing the urgent part leaves.

    The outlook is derived from the same ReadinessMap the bands are, and it
    is deliberately pessimistic in exactly one direction: it promises a
    cleared verdict only when nothing is left to qualify it. Over-promising
    here is the failure mode that matters — a reader who works the list and
    finds the verdict unmoved has been told something untrue by the product,
    which is the one thing it may not do.
    """
    total = len(open_questions)
    counts: dict[int, int] = defaultdict(int)
    for view in open_questions:
        counts[view.rank] += 1
    bands = tuple(
        (counts[rank], rank, label)
        for rank, label, _ in _BANDS if counts[rank]
    )
    urgent = counts[_BANDS[0][0]]
    if not urgent:
        return QuestionTallyView(
            total=total, bands=bands, urgent=0,
            headline=(
                "No open question holds up the answer that was asked."
                if total else "No open questions."
            ),
            outlook=(
                "Every one of these was raised about the landscape, not "
                "about the path to this answer. Section 6 says what the "
                "verdict rests on."
            ) if total else "",
        )

    blocking = [item for readiness in readiness_maps if readiness
                for item in readiness.blocking()]
    limits = [item for readiness in readiness_maps if readiness
              for item in readiness.limitations()]
    refuted = [item.ref for item in blocking
               if item.ground is Ground.ALL_CONTRADICTED]

    headline = (
        f"{urgent} of these {total} hold up the answer"
        f"{f'; the other {total - urgent} do not' if total > urgent else ''}."
    )

    if refuted:
        one = len(refuted) == 1
        outlook = (
            f"Answering all {urgent} would not clear the verdict: "
            f"{_quoted(refuted)} {'was' if one else 'were'} refuted by a "
            f"check, so a confirmation collides with that evidence instead "
            f"of settling it. Section 6 names the route that does apply."
        )
    else:
        outlook = (
            f"Answering all {urgent} would make the figures computable."
        )
    if limits:
        # A limitation nothing on this list covers is the second way the
        # count misleads: the reader would work section 5 to the end and
        # still not have touched it.
        open_ids = {view.id for view in open_questions}
        on_list = {claim_id for card in questions if card.id in open_ids
                   for claim_id in card.claim_ids}
        uncovered = [item for item in limits
                     if not set(item.claim_ids) & on_list]
        one = len(limits) == 1
        clause = (
            f" {len(limits)} dependenc{'y' if one else 'ies'} would remain "
            f"as {'a ' if one else ''}named limitation{'' if one else 's'}"
        )
        if len(uncovered) == len(limits):
            clause += (
                f", and no question on this list covers "
                f"{'it' if one else 'them'}"
            )
        elif uncovered:
            clause += (
                f", and {len(uncovered)} of them are covered by no question "
                "on this list"
            )
        outlook += f"{clause}."
    elif not refuted:
        outlook = (
            f"Answering all {urgent} would clear the verdict: nothing else "
            "this answer depends on is unsettled."
        )
    return QuestionTallyView(total=total, bands=bands, urgent=urgent,
                             headline=headline, outlook=outlook)


def _build_questions(
    questions: list[ClarificationQuestion],
    claims: dict[str, Claim],
    guide: GuideShape,
    bearing: dict[str, tuple[int, str, str]] | None = None,
) -> tuple[tuple[QuestionView, ...], tuple[AnsweredQuestionView, ...]]:
    """A question, then the candidates as a list — never as prose.

        The options used to be flattened into the question text itself; they are
        the claims the card already links, and a list of bindings written out as
        a sentence is the least readable form of that data.

        Whether the list is a *choice* is not read off the question's wording —
        it is read off the guide: only a role the guide sends to the humans
        (`decided_by: clarification`) is answered by picking one. A role whose
        law could never be applied is asking for knowledge, not for a pick.
        """
    bearing = bearing or {}
    # gap_load is the product's own impact measure and has been built and
    # tested since M3 with nothing calling it. It ranks unproven claims by
    # how many questions rest on them; here it breaks ties inside a band,
    # so of two questions that both block, the one holding up more work
    # comes first.
    load_by_claim = {
        claim.id: count
        for claim, count in gap_load(claims.values(), questions)
    }
    open_views = []
    answered_views = []
    for card in questions:
        if is_answered(card, claims):
            settled = settling_claims(card, claims)
            answered_views.append(
                AnsweredQuestionView(
                    id=card.id,
                    question=card.question,
                    settled=tuple(
                        LinkStatusView(
                            _claim_link(claim, _claim_title(claim)),
                            claim.status.value,
                        )
                        for claim in settled
                    ),
                    summary=(
                        f"Answered. Settled by {len(settled)} claim"
                        f"{'s' if len(settled) != 1 else ''}:"
                    ),
                    provenance=ProvenanceView(
                        _reference("questions", card.id),
                        ("no longer open",),
                    ),
                )
            )
            continue
        options = [
            claims[claim_id]
            for claim_id in card.claim_ids
            if claim_id in claims
        ]
        competing = [
            claim for claim in options if isinstance(claim, MappingClaim)
        ]
        roles = {claim.role for claim in competing}
        if len(options) > 1 and len(competing) == len(options):
            sorted_options = sorted(options, key=_candidate_name)
            a_choice = (
                len(roles) == 1
                and guide.decided_by.get(next(iter(roles)))
                == "clarification"
            )
            mode = "bindings"
            lead = (
                f"Pick one — {len(options)} candidates were proposed:"
                if a_choice
                else f"The {len(options)} candidates that were proposed for "
                "it — no law could be applied to any of them:"
            )
            option_views = tuple(
                QuestionOptionView(
                    link=_claim_link(claim, "why this one?"),
                    binding=_candidate_name(claim),
                    binding_kind=(
                        "column"
                        if "." in _candidate_name(claim)
                        else "table"
                        if _candidate_name(claim) != claim.statement
                        else "code"
                    ),
                )
                for claim in sorted_options
            )
        elif options:
            mode = "claims"
            lead = (
                f"It is about {len(options)} claim"
                f"{'s' if len(options) != 1 else ''}:"
            )
            option_views = tuple(
                QuestionOptionView(
                    link=_claim_link(claim),
                    status=claim.status.value,
                )
                for claim in options
            )
        else:
            mode = "empty"
            lead = (
                "No claim is attached to this question — it asks about "
                "something nothing in the data was proposed for."
            )
            option_views = ()
        rank, label, because = min(
            (bearing[cid] for cid in card.claim_ids if cid in bearing),
            default=(_BANDS[3][0], _BANDS[3][1], _BANDS[3][2]),
        )
        open_views.append(
            QuestionView(
                id=card.id,
                question=card.question,
                # A size is a measurement, and a measurement of data that
                # has since moved must not be shown as if it still held.
                # The card keeps its number — the reader is told what the
                # number is worth.
                finding=(f"{card.finding} — measured before the data moved; "
                         "nobody has re-run the check since"
                         if card.stale and card.finding else card.finding),
                mode=mode,
                lead=lead,
                rank=rank,
                bearing=label,
                because=because,
                load=max((load_by_claim.get(cid, 0)
                          for cid in card.claim_ids), default=0),
                options=option_views,
                provenance=ProvenanceView(
                    _reference("questions", card.id),
                    ("asked of a human", "nobody has answered it yet"),
                ),
                details=(
                    ("id", card.id),
                    ("created_at", card.created_at.isoformat()),
                    ("stale", str(card.stale).lower()),
                    (
                        "scope",
                        card.scope.label()
                        if card.scope and card.scope.is_explicit()
                        else "whole landscape",
                    ),
                ),
            )
        )
    # Band first, then how much rests on it, then the wording so the order
    # is stable between renders. Nothing is hidden and nothing is dropped:
    # the list is the same list, put in the order a person would work it.
    open_views.sort(key=lambda view: (view.rank, -view.load, view.question))
    return tuple(open_views), tuple(answered_views)


def _readiness_maps(
    store: ProjectStore, root: Path, config: dict
) -> tuple[DomainGuide | None, list]:
    """Every asked question, judged, and the guide they were judged against.

        Derived on this render, never read from a file — a stored verdict could
        drift away from the evidence beneath it, and a drifted verdict is worse
        than none. The guide comes back with them because the report names which
        one a dependency list was expanded from.
        """
    path = _guide_path(root, config)
    if path is None or not store.requests:
        return None, []
    try:
        guide = load_domain_guide(path)
    except (OSError, ValueError):
        return None, []
    maps = []
    for request in sorted(
        store.requests.values(), key=lambda request: request.created_at
    ):
        result = evaluate_request(store, guide, request.id)
        if result is not None:
            maps.append(result)
    return guide, maps


def _treated_as(result, guide: DomainGuide) -> RichTextView:
    """The classification, in the derived voice — the line the cap asks about.

        It headlines the request card because it is the single claim everything
        below it rests on: name the wrong family and the whole list is wrong,
        quietly. The AI's own words for the question stay quoted underneath,
        subordinate to this, as the three-voices rule requires.
        """
    if result.answer_type is None:
        return _text(
            _styled("Treated as: no declared answer type.", "strong"),
            _plain(
                " The list below was drafted for this question alone — "
                "nobody has reviewed it as a whole."
            ),
        )
    state = (
        "confirmed by a human"
        if result.confirmed
        else "confirmed against an earlier guide"
        if result.review.lapsed
        else "not confirmed by anyone yet"
    )
    return _text(
        _styled(f"Treated as: {result.answer_type}", "strong"),
        _plain(" "),
        _styled(f"(guide {guide_label(guide)})", "muted"),
        _plain(f" — {state}."),
    )


def _build_requests(
    maps: list, guide: DomainGuide | None
) -> tuple[RequestView, ...]:
    """Stage 0 — what was asked, and what the answer therefore depends on.

        Separate from the verdict on purpose: this is the frame opening. A
        reader should see what the question is and what it requires *before*
        the pipeline, and the verdict only after.
        """
    if not maps or guide is None:
        return ()
    views = []
    for result in maps:
        scope = result.request.scope
        scope_line = (
            f"Asked for {scope.label()}."
            if scope.is_explicit()
            else "No scope named, so the whole landscape."
        )
        items = tuple(
            RequestItemView(
                ref=item.ref,
                kind=item.item.kind.value,
                provenance=PROVENANCE_LABEL[item.item.provenance],
                waived=item.item.waived,
                waived_because=item.item.waived_because,
                why=item.item.why,
                why_cite=WHY_CITE[item.item.provenance],
            )
            for item in result.items
        )
        views.append(
            RequestView(
                id=result.request.id,
                question=result.request.question,
                requested_output=result.request.requested_output,
                treated_as=_treated_as(result, guide),
                scope_line=scope_line,
                dependency_heading=(
                    f"What this answer depends on ({len(result.items)}) — "
                    "and nothing else has to be known"
                ),
                items=items,
                provenance=ProvenanceView(
                    _reference("answers", result.request.id),
                    ("asked by a human", "expanded on this render"),
                ),
            )
        )
    return tuple(views)


def _build_readiness(maps: list) -> tuple[ReadinessView, ...]:
    """One dependency: the derived sentence first, the AI's reason under it.

        The three-voices rule at its sharpest. The status sentence is derived
        and is the headline; the ``why`` the model wrote when it listed this
        dependency is legible, attributed, and subordinate — it explains why the
        item is on the list, never what became of it.
        """
    views = []
    for result in maps:
        headline, explanation = VERDICT_HEADLINE[result.verdict]
        groups = []
        for title, items in (
            (
                "What the figures are computed from",
                [item for item in result.items if item.structural],
            ),
            (
                "What the figures mean",
                [item for item in result.items if not item.structural],
            ),
        ):
            if not items:
                continue
            groups.append(
                ReadinessGroupView(
                    title=title,
                    items=tuple(
                        ReadinessItemView(
                            ref=item.ref,
                            kind=item.item.kind.value,
                            mark=(
                                "waived"
                                if item.item.waived
                                else "supported"
                                if item.satisfied
                                else "missing"
                            ),
                            because=item.because,
                            links=tuple(
                                ReadinessLinkView(
                                    sentence=_text(
                                        TextPartView(
                                            "Linked by the "
                                            f"{link.linked_by.value}"
                                            f"{' — ' + link.note if link.note else ''} "
                                            "→ ",
                                            escape_quotes=True,
                                        ),
                                        _linked(
                                            link.claim_id[-6:],
                                            "claim",
                                            link.claim_id,
                                        ),
                                    )
                                )
                                for link in item.item.satisfied_by
                            ),
                            claims=tuple(
                                _link("claim", claim_id, claim_id[-6:])
                                for claim_id in item.claim_ids
                            ),
                        )
                        for item in items
                    ),
                )
            )
        views.append(
            ReadinessView(
                id=result.request.id,
                question=result.request.question,
                verdict=result.verdict.value,
                headline=headline,
                reason=result.reason(),
                explanation=explanation,
                scope_line=(
                    f"Asked for {result.request.scope.label()}."
                    if result.request.scope.is_explicit()
                    else ""
                ),
                groups=tuple(groups),
                provenance=ProvenanceView(
                    _reference("answers", result.request.id),
                    ("derived on this render", "never stored"),
                ),
            )
        )
    return tuple(views)


def _settled_slot_columns(
    root: Path,
    config: dict,
    store: ProjectStore,
) -> dict[tuple[str, Scope | None], str]:
    """(field, scope) -> the column that scope's passing law consumed.

        Scoped, because each entity's ledger consumed its own amount column and
        one entity's run answers nothing for another. Empty if the guide does
        not load (the panel above already says so).
        """
    path = _guide_path(root, config)
    if path is None:
        return {}
    try:
        guide = load_domain_guide(path)
    except (OSError, ValueError):
        return {}
    answered: dict[tuple[str, Scope | None], str] = {}
    for name in guide.objects:
        for scope in scopes_of(store, name) or [None]:
            for field, column in settled_slots(
                store, guide, name, scope
            ).items():
                answered[(field, scope)] = column
    return answered


def _by_election(
    facts: dict[str, ClaimFacts],
) -> dict[tuple[str, Scope | None], list[ClaimFacts]]:
    """Candidates grouped by the election they are in: role within scope.

        Two entities each own a journal, and neither competes with the other —
        so the unit here is never the bare role.
        """
    grouped: dict[
        tuple[str, Scope | None], list[ClaimFacts]
    ] = defaultdict(list)
    for fact in facts.values():
        if isinstance(fact.claim, MappingClaim):
            grouped[(fact.claim.role, fact.claim.scope)].append(fact)
    return grouped


def _election_tally(
    facts: dict[str, ClaimFacts],
    answered: dict[tuple[str, Scope | None], str],
) -> tuple[int, int]:
    """(elections settled, elections held), counting role x scope. A slot
        answered by its object's passing law counts as settled even though its
        own claims stay proposed."""
    grouped = _by_election(facts)
    settled = sum(
        1
        for key, candidates in grouped.items()
        if key in answered
        or any(
            fact.derived
            in (
                ClaimStatus.TEST_SUPPORTED,
                ClaimStatus.BUSINESS_CONFIRMED,
            )
            for fact in candidates
        )
    )
    return settled, len(grouped)


def _passing_template(fact: ClaimFacts) -> str:
    """The template of the check that actually passed on this candidate."""
    plans = {check.id: check for check in fact.checks}
    for record in fact.evidence:
        if (
            record.type is EvidenceType.CHECK_RESULT
            and record.verdict is CheckVerdict.PASS
            and not record.stale
        ):
            plan = plans.get(record.check_plan_id or "")
            if plan:
                return plan.template
    return ""


def _defeats(fact: ClaimFacts) -> list[tuple[str, str, str]]:
    """(template, domain, human detail) for every failing check on this claim."""
    checks = {check.id: check for check in fact.checks}
    out = []
    for record in fact.evidence:
        if (
            record.type is not EvidenceType.CHECK_RESULT
            or record.verdict is not CheckVerdict.FAIL
        ):
            continue
        check = checks.get(record.check_plan_id or "")
        template = check.template if check else "unknown template"
        spec = REGISTRY.get(template)
        out.append(
            (
                template,
                (spec.domain if spec else None) or "",
                _population_text(record),
            )
        )
    return out


def _election_outcome(
    role: str,
    candidates: list[ClaimFacts],
    winners: list[ClaimFacts],
    cards: list[ClarificationQuestion],
    column: str,
    owner: str,
    decided_by: dict[str, str],
    total: int,
) -> ElectionOutcomeView:
    """What became of this role, as one sentence a business reader can act on."""
    law = decided_by.get(owner or role, "") or "domain"
    others = total - 1
    if winners:
        beaten = sum(
            1
            for fact in candidates
            if fact.derived is ClaimStatus.CONTRADICTED
        )
        if not beaten:
            felled = ""
        elif beaten == others:
            felled = (
                " and felled the other candidate"
                if others == 1
                else f" and felled all {others} of its competitors"
            )
        else:
            felled = (
                f" and felled {beaten} of the {others} other candidate"
                f"{'s' if others != 1 else ''}"
            )
        won_by = _passing_template(winners[0]) or law
        return ElectionOutcomeView(
            paragraphs=(
                (
                    "derived",
                    _text(
                        _styled("Identified.", "strong"),
                        _plain(f" The {won_by} law passed on "),
                        _linked(
                            _binding_name(winners[0].claim),
                            "claim",
                            winners[0].claim.id,
                        ),
                        _plain(f"{felled}."),
                    ),
                ),
            )
        )
    if column:
        return ElectionOutcomeView(
            paragraphs=(
                (
                    "derived",
                    _text(
                        _styled(
                            "Answered — without anyone being asked.",
                            "strong",
                        ),
                        _plain(f" The {law} law of "),
                        _styled(owner, "code"),
                        _plain(" passed while reading "),
                        _styled(column, "code"),
                        _plain(", and that run is the answer."),
                    ),
                ),
                (
                    "fine",
                    _text(
                        _plain(
                            "No check tests this field on its own, so its "
                            "candidates below all still read "
                        ),
                        _styled("proposed", "em"),
                        _plain(
                            " — nothing can prove by arithmetic what a single "
                            "column "
                        ),
                        _styled("means", "em"),
                        _plain(
                            ". What settles it is that the law judging the "
                            "whole object consumed this column and held."
                        ),
                    ),
                ),
            )
        )
    if cards:
        return ElectionOutcomeView(
            paragraphs=tuple(
                (
                    "derived",
                    _text(
                        _styled(
                            "Open — a human has to answer it.",
                            "strong",
                        ),
                        _plain(" "),
                        _linked(
                            _first_sentence(card.question),
                            "question",
                            card.id,
                        ),
                    ),
                )
                for card in cards
            )
        )
    if not any(fact.checks for fact in candidates):
        return ElectionOutcomeView(
            paragraphs=(
                (
                    "muted",
                    _text(
                        _styled("Not decided yet:", "strong"),
                        _plain(
                            " no invariant check bound and no clarification "
                            "question drafted — binding is still in flight."
                        ),
                    ),
                ),
            )
        )
    return ElectionOutcomeView(
        paragraphs=(
            (
                "muted",
                _text(
                    _plain(
                        "No winner — every tested candidate lost, and no "
                        "clarification question is drafted yet (run role "
                        "resolution)."
                    )
                ),
            ),
        )
    )


def _build_elections(
    facts: dict[str, ClaimFacts],
    questions: list[ClarificationQuestion],
    guide: GuideShape,
    answered: dict[tuple[str, Scope | None], str],
) -> tuple[ElectionView, ...]:
    grouped = _by_election(facts)
    if not grouped:
        return ()
    rank_role = {name: index for index, name in enumerate(guide.order)}
    ordered = sorted(
        grouped,
        key=lambda key: (
            rank_role.get(key[0], len(rank_role)),
            key[0],
            key[1].label() if key[1] else "",
        ),
    )
    rank = {
        ClaimStatus.TEST_SUPPORTED: 0,
        ClaimStatus.BUSINESS_CONFIRMED: 0,
        ClaimStatus.UNRESOLVED: 1,
        ClaimStatus.PROPOSED: 2,
        ClaimStatus.CONTRADICTED: 3,
    }
    views = []
    for role, scope in ordered:
        candidates = grouped[(role, scope)]
        candidates.sort(
            key=lambda fact: (rank[fact.derived], fact.claim.id)
        )
        winners = [
            fact
            for fact in candidates
            if fact.derived
            in (
                ClaimStatus.TEST_SUPPORTED,
                ClaimStatus.BUSINESS_CONFIRMED,
            )
        ]
        column = answered.get((role, scope), "")
        claim_ids = {fact.claim.id for fact in candidates}
        cards = [
            card
            for card in questions
            if claim_ids & set(card.claim_ids)
        ]
        candidate_views = []
        for fact in candidates:
            won = fact in winners
            css = (
                "winner"
                if won
                else "loser"
                if fact.derived is ClaimStatus.CONTRADICTED
                else ""
            )
            reasons = []
            for template, domain, detail in _defeats(fact):
                parts = [
                    _plain("felled by "),
                    _styled(template, "code"),
                ]
                if domain:
                    parts.extend(
                        [
                            _plain(" "),
                            _styled(f"({domain} law)", "muted"),
                        ]
                    )
                parts.append(_plain(f" — {detail}"))
                reasons.append(_text(*parts))
            if not fact.checks and fact.no_check_reason:
                reasons.append(
                    _text(
                        _plain(
                            f"never tested — {fact.stage}: "
                            f"{fact.no_check_reason}"
                        )
                    )
                )
            binding = getattr(fact.claim, "binding", None)
            if (
                column
                and isinstance(binding, dict)
                and column in binding.values()
            ):
                css = css or "winner"
                reasons.insert(
                    0,
                    _text(
                        _styled(
                            "The passing run consumed this column",
                            "strong",
                        ),
                        _plain(
                            " — the object's law held while reading it."
                        ),
                    ),
                )
            candidate_views.append(
                ElectionCandidateView(
                    link=_claim_link(
                        fact.claim, _candidate_name(fact.claim)
                    ),
                    status=fact.derived.value,
                    css=css,
                    reasons=tuple(reasons),
                )
            )
        decision = guide.decided_by.get(role, "")
        fills = guide.fills.get(role, "")
        path_note = _decided_by_label(
            {"decided_by": decision, "fills": fills}
        )
        views.append(
            ElectionView(
                role=role,
                owner=guide.owner.get(role, ""),
                scope=(
                    scope.label()
                    if scope and scope.is_explicit()
                    else ""
                ),
                candidate_count=len(candidates),
                path_note=path_note,
                definition=guide.definition.get(role, ""),
                field=role in guide.owner,
                outcome=_election_outcome(
                    role,
                    candidates,
                    winners,
                    cards,
                    column,
                    guide.owner.get(role, ""),
                    guide.decided_by,
                    len(candidates),
                ),
                candidates=tuple(candidate_views),
            )
        )
    return tuple(views)


def _build_funnel(facts: dict[str, ClaimFacts]) -> FunnelView:
    if not facts:
        return FunnelView(empty="No claims yet.")
    values = list(facts.values())
    stages = {
        name: sum(1 for fact in values if fact.stage == name)
        for name in STAGE_LABELS
    }
    executed = sum(1 for fact in values if fact.executed)
    by_status: dict[str, int] = defaultdict(int)
    for fact in values:
        by_status[fact.derived.value] += 1
    return FunnelView(
        stages=(
            FunnelStageView(
                "proposed",
                (
                    FunnelChipView(
                        len(values),
                        "claims (all proposed when created)",
                        "",
                    ),
                ),
            ),
            FunnelStageView(
                "bound",
                tuple(
                    FunnelChipView(
                        stages[name], STAGE_LABELS[name], name
                    )
                    for name in STAGE_LABELS
                    if stages[name]
                ),
            ),
            FunnelStageView(
                "judged",
                (
                    FunnelChipView(
                        executed,
                        "claims a check actually ran against",
                        "executed",
                    ),
                ),
            ),
            FunnelStageView(
                "status",
                tuple(
                    FunnelChipView(
                        by_status[status.value],
                        status.value,
                        f"status:{status.value}",
                        status.value,
                    )
                    for status in ClaimStatus
                    if by_status[status.value]
                ),
            ),
        ),
        caveat=_text(
            _plain(
                "A claim without a check is not a claim that failed — it is a "
                "claim nobody tested, and it stays "
            ),
            _styled("proposed", "em"),
            _plain(
                ". Every one of them carries the reason it got no check; open "
                "the claim to read it in the model's own words."
            ),
        ),
    )


def _readiness_counts(maps: list) -> list[tuple[str, str]]:
    """The diagram's live numbers for stage 6."""
    if not maps:
        return [("—", "no question asked")]
    supported = sum(
        1 for result in maps for item in result.items if item.satisfied
    )
    total = sum(len(result.items) for result in maps)
    worst = next(
        (
            result.verdict
            for result in maps
            if result.verdict is Readiness.BLOCKED
        ),
        None,
    ) or next(
        (
            result.verdict
            for result in maps
            if result.verdict is Readiness.READY_WITH_LIMITATIONS
        ),
        Readiness.READY,
    )
    return [
        (f"{supported}/{total}", "dependencies supported"),
        (worst.value.replace("_", " "), "verdict"),
    ]


def _stage_counts(
    *,
    readiness,
    required,
    declared_sources,
    guide_objects,
    guide_fields,
    domain_laws,
    profiles,
    candidates,
    claims,
    runs,
    elected,
    elections,
    questions,
) -> dict[str, list[tuple[str, str]]]:
    """This project's live numbers, per stage of the spine."""
    def plural(number: int, word: str) -> str:
        return f"{word}{'s' if number != 1 else ''}"

    return {
        "request": (
            [(str(required), "things it depends on")]
            if required
            else [("—", "no question asked")]
        ),
        "inputs": [
            (
                str(declared_sources),
                plural(declared_sources, "source"),
            ),
            (
                f"{guide_objects}+{guide_fields}",
                "objects + fields",
            ),
            (
                str(domain_laws),
                plural(domain_laws, "domain law"),
            ),
        ],
        "measured": [
            (str(profiles), "column profiles"),
            (str(candidates), "candidate overlaps"),
        ],
        "proposed": [(str(claims), plural(claims, "claim"))],
        "tested": [
            (str(runs), plural(runs, "check run")),
            (f"{elected}/{elections}", "elections settled"),
        ],
        "clarification": [
            (str(questions), plural(questions, "open question"))
        ],
        "readiness": readiness,
    }


def _report_copy() -> ReportCopyView:
    return ReportCopyView(
        reading_guide=READING_GUIDE,
        process_ghost=_text(
            _styled("Documents", "strong"),
            _plain(
                " — policies, manuals and contracts are read alongside the "
                "data. Some rules an answer needs are written down nowhere "
                "else: a sign convention lives in an accounting policy, not "
                "in a column. What a document says is proposed like anything "
                "else, and every proposal points back at the passage it was "
                "read from, so it can be checked against the page."
            ),
        ),
        request_intro=(
            "The frame opens here. The question bounds the work: it\n"
            "        defines what must be known, and nothing else has to be. "
            "Section 6 closes\n"
            "        the frame with the verdict those dependencies earn. It "
            "comes after the\n"
            "        declared inputs because it is decomposed against the "
            "domain guide —\n"
            "        a vocabulary someone had to choose first."
        ),
        measured_intro=(
            "No model has seen anything yet. These are counted facts:\n"
            "        every column profiled, every value overlap between tables "
            "measured."
        ),
        proposed_intro=_text(
            _plain(
                "Everything the model writes enters as "
            ),
            _styled("proposed", "em"),
            _plain(
                " and\n        nothing it writes can change that. Click any "
                "number to filter the claim list."
            ),
        ),
        tested_intro=(
            "Every role the AI proposed candidates for. Each role declares "
            "its\n        settlement path: a domain law elects the winner, or "
            "the humans decide via clarification question —\n        never "
            "silence."
        ),
        clarification_intro=(
            "What the checks could not settle. This is the human's to-do "
            "list.\n        A question leaves it the moment a claim it rests "
            "on settles — derived from the\n        same evidence the "
            "readiness map reads, so the two can never disagree."
        ),
        clarification_order=(
            "Ordered by what each one holds up, not by when it was asked. "
            "The\n        badge says whether the question you asked waits "
            "on this one — most do\n        not, and a flat list hides that. "
            "Within a band, the question carrying\n        the most other "
            "work comes first. Nothing is hidden; the order is the\n        "
            "only thing that changes, and it is recomputed on every render."
        ),
        readiness_intro=(
            "The frame closes. Every dependency listed in section 0\n"
            "        is traced to its claim and evidence, and the verdict is "
            "what they add up\n        to. Derived on every render, never "
            "stored — a verdict that has drifted\n        from its evidence "
            "is worse than none."
        ),
        no_request=NOTHING_ASKED,
    )


def build_view_model(
    store: ProjectStore,
    root: Path,
    config: dict,
) -> ReportViewModel:
    """Project every report fact and sentence once, without HTML concerns."""
    root_path = Path(root).resolve()
    matrix = _load_candidate_matrix(root_path)
    claims = sorted(
        store.claims.values(),
        key=lambda claim: (claim.created_at, claim.id),
    )
    questions = sorted(
        store.questions.values(),
        key=lambda card: (card.created_at, card.id),
    )
    sources = sorted(
        store.sources.values(),
        key=lambda source: (source.name.lower(), source.id),
    )
    profiles = sorted(
        store.profiles.values(),
        key=lambda profile: (
            _source_name(store.sources.get(profile.source_id)),
            profile.table,
            profile.column,
            profile.id,
        ),
    )
    guide = _load_guide_shape(root_path, config)
    facts = _claim_facts(store, claims)
    questions_by_claim = _questions_by_claim(questions)
    reverse_depends, reverse_derived = _reverse_claim_links(claims)
    declarations = _declarations_by_key(store.evidence.values())
    rationales = _rationales(root_path, claims, guide.owner)
    stale_reasons = _stale_reasons(store)
    claim_views = tuple(
        _build_claim(
            facts[claim.id],
            store,
            questions_by_claim,
            reverse_depends,
            reverse_derived,
            declarations,
            rationales.get(claim.id),
            stale_reasons,
        )
        for claim in claims
    )
    # The maps come first now: a question's priority is read off them, and
    # it has to be, because the wording is stored project data while the
    # map is recomputed on every read. Rank the cards by what they hold up
    # today, not by what they held up when they were written.
    readiness_guide, readiness_maps = _readiness_maps(
        store, root_path, config
    )
    open_questions, answered_questions = _build_questions(
        questions, store.claims, guide, _question_bearing(readiness_maps)
    )
    answered_slots = _settled_slot_columns(
        root_path, config, store
    )
    elected, elections = _election_tally(facts, answered_slots)
    guide_fields = len(guide.owner)
    counts = _stage_counts(
        readiness=_readiness_counts(readiness_maps),
        required=sum(
            len(result.items) for result in readiness_maps
        ),
        declared_sources=len(config.get("sources") or []),
        guide_objects=len(guide.order) - guide_fields,
        guide_fields=guide_fields,
        domain_laws=sum(
            1 for spec in REGISTRY.values() if spec.domain
        ),
        profiles=len(profiles),
        candidates=len(matrix.get("candidates", [])),
        claims=len(claims),
        runs=sum(
            1
            for record in store.evidence.values()
            if record.type is EvidenceType.CHECK_RESULT
        ),
        elected=elected,
        elections=elections,
        questions=len(questions),
    )
    stages = tuple(
        StageView(
            name=stage.name,
            label=stage.label,
            title=stage.title,
            actor=stage.actor,
            counts=tuple(counts.get(stage.name, [])),
            boundary_before=(
                BOUNDARY_TEXT
                if stage.name == BOUNDARY_BEFORE
                else ""
            ),
        )
        for stage in STAGES
    )
    return ReportViewModel(
        project_name=root_path.name,
        project_path=str(root_path),
        copy=_report_copy(),
        stages=stages,
        domain_pack=_build_domain_pack(root_path, config),
        requests=_build_requests(readiness_maps, readiness_guide),
        measurement=_build_measurement(
            store, sources, profiles, claims, matrix
        ),
        documents=_build_documents(store),
        decisions=_build_decisions(store, claims, facts),
        unblock=_build_unblock(store, readiness_maps),
        funnel=_build_funnel(facts),
        elections=_build_elections(
            facts, questions, guide, answered_slots
        ),
        open_questions=open_questions,
        question_tally=_build_question_tally(
            open_questions, questions, readiness_maps
        ),
        answered_questions=answered_questions,
        readiness=_build_readiness(readiness_maps),
        claims=claim_views,
        integrity=tuple(check_integrity(store)),
        glossary=tuple(GLOSSARY),
        status_options=tuple(
            status.value for status in ClaimStatus
        ),
        predicate_options=tuple(
            sorted(
                {
                    claim.predicate.name
                    for claim in claims
                    if claim.predicate
                }
            )
        ),
        role_options=tuple(
            sorted(
                {
                    claim.role
                    for claim in claims
                    if isinstance(claim, MappingClaim)
                }
            )
        ),
    )
