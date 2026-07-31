import json
from collections import defaultdict
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from typing import Iterable

import yaml

from before_we_ai.glossary import GLOSSARY
from before_we_ai.llm.domain_guide import load_domain_guide, settled_slots
from before_we_ai.llm.mapping import admissible_templates
from before_we_ai.model import ClaimStatus, EvidenceType, CheckVerdict, resolve_status
from before_we_ai.model.objects import (
    Claim,
    DataProfile,
    EvidenceRecord,
    CheckPlan,
    ClarificationQuestion,
    MappingClaim,
    Source,
)
from before_we_ai.checks.library import REGISTRY
from before_we_ai.store import ProjectStore, check_integrity
from before_we_ai.store.layout import CONFIG_FILE

STATUS_COLORS = {
    ClaimStatus.PROPOSED.value: "status-proposed",
    ClaimStatus.TEST_SUPPORTED.value: "status-test-supported",
    ClaimStatus.CONTRADICTED.value: "status-contradicted",
    ClaimStatus.UNRESOLVED.value: "status-unresolved",
    ClaimStatus.BUSINESS_CONFIRMED.value: "status-business-confirmed",
}

VERDICT_COLORS = {
    CheckVerdict.PASS.value: "verdict-pass",
    CheckVerdict.FAIL.value: "verdict-fail",
    CheckVerdict.INCONCLUSIVE.value: "verdict-inconclusive",
}


STAGE_LABELS = {
    "bound": "bound to a check",
    "unbindable": "unbindable — the model gave a reason",
    "semantic_only": "semantic-only — no check definition can test it",
    "skipped": "skipped — validation rejected the binding",
    "unbound": "no check, no recorded reason",
}




READING_GUIDE = (
    "This page mirrors the pipeline: the AI proposes, the checks decide. Read it "
    "top down — the funnel says how many claims survived each step, the Clarification questions "
    "are what the data could not settle, the role elections show which candidate "
    "won its role and which domain law felled the others. Then pick one claim on "
    "the left and read its story: 1 proposed → 2 bound → 3 judged → 4 context. "
    "Nothing here is hand-set: every status is derived from the evidence shown "
    "with it."
)

DOMAIN_PACK_INTRO = (
    "Everything domain-specific enters through three declared inputs "
    "(docs/architecture.md 'Domain inputs'); the model additionally sees only "
    "measured statistics, never raw rows. The product is a general machine only "
    "together with a domain pack — so what is domain-specific must be declared, "
    "transparent, and logically validated."
)


@dataclass
class ClaimFacts:
    """Everything the viewer knows about one claim, computed once."""

    claim: Claim
    evidence: list[EvidenceRecord] = field(default_factory=list)
    checks: list[CheckPlan] = field(default_factory=list)
    derived: ClaimStatus = ClaimStatus.PROPOSED
    stage: str = "unbound"  # a key of STAGE_LABELS
    executed: bool = False
    no_check_reason: str = ""  # verbatim, from the DECLARATION V2 wrote

    @property
    def diverges(self) -> bool:
        return self.claim.status is not self.derived


def default_output_path(root: Path) -> Path:
    return root.resolve().parent / f"{root.name}-claim-viewer.html"


def write_project_view(root: str | Path, output: str | Path | None = None) -> Path:
    root_path = Path(root).resolve()
    out = Path(output).resolve() if output else default_output_path(root_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_project(root_path), encoding="utf-8")
    return out


def render_project(root: str | Path) -> str:
    root_path = Path(root).resolve()
    store = ProjectStore(root_path)
    config = _project_config(root_path)
    matrix = _load_candidate_matrix(root_path)
    claims = sorted(store.claims.values(), key=lambda claim: (claim.created_at, claim.id))
    questions = sorted(store.questions.values(), key=lambda card: (card.created_at, card.id))
    sources = sorted(store.sources.values(), key=lambda source: (source.name.lower(), source.id))
    profiles = sorted(
        store.profiles.values(),
        key=lambda profile: (
            _source_name(store.sources.get(profile.source_id)),
            profile.table,
            profile.column,
            profile.id,
        ),
    )
    integrity = check_integrity(store)
    guide_order, guide_decided_by, guide_owner = _load_guide_shape(root_path, config)

    questions_by_claim = _questions_by_claim(questions)
    reverse_depends, reverse_derived = _reverse_claim_links(claims)
    declarations_by_key = _declarations_by_key(store.evidence.values())
    claims_by_source = _claims_by_source(claims)
    role_bindings = _role_bindings_by_column(claims)
    candidates_by_column = _candidates_by_column(matrix)
    profiles_by_source = _profiles_by_source(profiles)
    facts = _claim_facts(store, claims)

    claim_index = "".join(
        _render_claim_index_card(facts[claim.id]) for claim in claims
    ) or '<p class="empty">No claims yet.</p>'
    claim_sections = "".join(
        _render_claim_section(
            facts[claim.id],
            store=store,
            questions_by_claim=questions_by_claim,
            reverse_depends=reverse_depends,
            reverse_derived=reverse_derived,
            declarations_by_key=declarations_by_key,
        )
        for claim in claims
    ) or '<p class="empty">No claims yet.</p>'
    question_sections = "".join(
        _render_question_section(card, store.claims) for card in questions
    ) or '<p class="empty">No questions yet.</p>'
    source_index = "".join(_render_source_index_card(source, profiles_by_source) for source in sources)
    source_sections = "".join(
        _render_source_section(
            source,
            profiles_by_source.get(source.id, []),
            claims_by_source.get(source.id, []),
            declarations_by_key,
            role_bindings,
            candidates_by_column,
        )
        for source in sources
    ) or '<p class="empty">No sources yet.</p>'
    orphan_columns = [
        profile for profile in profiles if profile.source_id not in store.sources
    ]
    if orphan_columns:
        source_sections += _render_orphan_profiles(
            orphan_columns, declarations_by_key, role_bindings, candidates_by_column
        )

    candidate_count = len(matrix.get("candidates", []))
    warning_html = "".join(f"<li>{escape(warning)}</li>" for warning in matrix.get("warnings", []))
    integrity_html = "".join(f"<li>{escape(finding)}</li>" for finding in integrity)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Claim Viewer — {escape(root_path.name)}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #0b1020;
      --panel: #141b2d;
      --panel-2: #1b2540;
      --text: #e9edf7;
      --muted: #9eb0d1;
      --line: #33415f;
      --link: #7dd3fc;
      --proposed: #64748b;
      --test-supported: #059669;
      --contradicted: #dc2626;
      --unresolved: #d97706;
      --business-confirmed: #7c3aed;
      --pass: #059669;
      --fail: #dc2626;
      --inconclusive: #d97706;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.5 system-ui, sans-serif;
    }}
    a {{ color: var(--link); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(300px, 360px) 1fr;
      min-height: 100vh;
    }}
    .sidebar {{
      position: sticky;
      top: 0;
      align-self: start;
      height: 100vh;
      overflow: auto;
      border-right: 1px solid var(--line);
      background: rgba(20, 27, 45, 0.98);
      padding: 20px;
    }}
    .content {{
      padding: 20px;
      display: grid;
      gap: 20px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 16px;
    }}
    .panel h2, .panel h3, .panel h4 {{ margin-top: 0; }}
    .claim-card, .mini-card, .evidence-card, .column-card, .question-card {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
    }}
    .grid {{
      display: grid;
      gap: 12px;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    }}
    .dense {{
      display: grid;
      gap: 8px;
    }}
    .muted {{ color: var(--muted); }}
    .empty {{ color: var(--muted); font-style: italic; }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 2px 10px;
      font-size: 12px;
      font-weight: 700;
      text-transform: lowercase;
      border: 1px solid transparent;
    }}
    .status-proposed {{ background: rgba(100, 116, 139, 0.22); color: #d4dbe8; border-color: rgba(100, 116, 139, 0.55); }}
    .status-test-supported {{ background: rgba(5, 150, 105, 0.18); color: #a7f3d0; border-color: rgba(5, 150, 105, 0.55); }}
    .status-contradicted {{ background: rgba(220, 38, 38, 0.18); color: #fecaca; border-color: rgba(220, 38, 38, 0.55); }}
    .status-unresolved {{ background: rgba(217, 119, 6, 0.2); color: #fed7aa; border-color: rgba(217, 119, 6, 0.55); }}
    .status-business-confirmed {{ background: rgba(124, 58, 237, 0.2); color: #ddd6fe; border-color: rgba(124, 58, 237, 0.55); }}
    .verdict-pass {{ background: rgba(5, 150, 105, 0.18); color: #a7f3d0; border-color: rgba(5, 150, 105, 0.55); }}
    .verdict-fail {{ background: rgba(220, 38, 38, 0.18); color: #fecaca; border-color: rgba(220, 38, 38, 0.55); }}
    .verdict-inconclusive {{ background: rgba(217, 119, 6, 0.2); color: #fed7aa; border-color: rgba(217, 119, 6, 0.55); }}
    .toolbar {{
      display: grid;
      gap: 10px;
      margin: 12px 0 16px;
    }}
    .toolbar input, .toolbar select {{
      width: 100%;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #0f172a;
      color: var(--text);
      padding: 9px 10px;
    }}
    code, pre {{
      background: #0f172a;
      border-radius: 8px;
    }}
    code {{ padding: 2px 6px; }}
    pre {{
      padding: 12px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 8px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 8px;
      text-align: left;
      vertical-align: top;
    }}
    dl {{
      margin: 0;
      display: grid;
      grid-template-columns: minmax(120px, 180px) 1fr;
      gap: 6px 12px;
    }}
    dt {{ color: var(--muted); }}
    .section-links {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-bottom: 14px;
    }}
    .list {{
      margin: 0;
      padding-left: 18px;
    }}
    .funnel {{ display: grid; gap: 10px; }}
    .funnel-stage {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex-wrap: wrap;
      padding: 10px 12px;
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 12px;
    }}
    .funnel-stage .step {{
      color: var(--muted);
      min-width: 110px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }}
    .chip {{
      display: inline-flex;
      align-items: baseline;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 12px;
      background: #0f172a;
      cursor: pointer;
      color: var(--text);
      font: inherit;
    }}
    .chip:hover {{ border-color: var(--link); }}
    .chip.active {{ border-color: var(--link); box-shadow: 0 0 0 1px var(--link) inset; }}
    .chip strong {{ font-size: 16px; }}
    .chip .label {{ color: var(--muted); font-size: 12px; }}
    .banner {{
      border: 1px solid var(--unresolved);
      background: rgba(217, 119, 6, 0.15);
      border-radius: 10px;
      padding: 10px 12px;
      margin: 10px 0;
    }}
    .headline {{ font-size: 15px; margin: 6px 0 12px; }}
    details {{ margin-bottom: 10px; }}
    details > summary {{
      cursor: pointer;
      padding: 8px 0;
      color: var(--muted);
      font-weight: 600;
      text-transform: uppercase;
      font-size: 12px;
      letter-spacing: 0.04em;
    }}
    details[open] > summary {{ color: var(--text); }}
    .election {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      margin-bottom: 12px;
    }}
    /* a field belongs to the object above it — the guide's shape, visible */
    .guide-field {{ margin-left: 22px; border-left: 2px solid var(--line); }}
    .cand {{
      border-left: 3px solid var(--line);
      padding: 6px 0 6px 10px;
      margin: 8px 0;
    }}
    .cand.winner {{ border-left-color: var(--test-supported); }}
    .cand.loser {{ border-left-color: var(--contradicted); }}
    .fine {{ font-size: 12px; color: var(--muted); }}
    details.sql > summary, #domain-pack details > summary, #how-to-read details > summary {{
      text-transform: none;
      letter-spacing: 0;
      font-size: 13px;
    }}
    details.sql pre {{ margin: 0; max-height: 460px; }}
    .claim-detail {{ display: none; }}
    .claim-card.selected {{ border-color: var(--link); }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .sidebar {{
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
    }}
  </style>
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <h1>Claim Viewer</h1>
      <p class="muted">{escape(str(root_path))}</p>
      <div class="section-links">
        <a href="#how-to-read">How to read</a>
        <a href="#domain-pack">Domain pack</a>
        <a href="#overview">Funnel</a>
        <a href="#questions">Clarification questions</a>
        <a href="#roles">Role elections</a>
        <a href="#data">Data</a>
        <a href="#integrity">Integrity</a>
      </div>
      <div class="panel">
        <h2 id="claims-index">Claims ({len(claims)})</h2>
        <div class="toolbar">
          <input id="claim-search" type="search" placeholder="Search statement or predicate">
          <select id="status-filter">
            <option value="">All statuses (derived)</option>
            {_status_options()}
          </select>
          <select id="predicate-filter">
            <option value="">All predicates</option>
            {_predicate_options(claims)}
          </select>
          <select id="role-filter">
            <option value="">All roles</option>
            {_role_options(claims)}
          </select>
        </div>
        <p id="filter-note" class="muted"></p>
        <div id="claim-list">{claim_index}</div>
      </div>
    </aside>
    <main class="content">
      <section class="panel" id="how-to-read">
        <h2>How to read this page</h2>
        {_render_core_terms()}
      </section>
      <section class="panel" id="domain-pack">
        <h2>Domain pack — the declared domain inputs</h2>
        {_render_domain_pack(root_path, config)}
      </section>
      <section class="panel" id="overview">
        <h2>The funnel — from guess to verdict</h2>
        <p class="muted">The AI proposes; the checks decide. Click any number to filter the claim list.</p>
        {_render_funnel(facts)}
        <p class="muted">{escape(_project_line(store, sources, profiles, candidate_count))}</p>
        {_render_matrix_summary(matrix, warning_html)}
      </section>
      <section class="panel" id="questions">
        <h2>Clarification questions — open questions ({len(questions)})</h2>
        <p class="muted">What the checks could not settle. This is the human's to-do list.</p>
        {question_sections}
      </section>
      <section class="panel" id="roles">
        <h2>Role elections</h2>
        <p class="muted">Every role the AI proposed candidates for. Each role declares its
        settlement path: a domain law elects the winner, or the humans decide via clarification question —
        never silence.</p>
        {_render_role_elections(facts, questions, guide_decided_by,
                                guide_order, guide_owner,
                                _settled_slot_columns(root_path, config, store))}
      </section>
      <section class="panel" id="claims">
        <h2>Claim detail</h2>
        <p id="claim-empty" class="muted">Pick a claim on the left.</p>
        {claim_sections}
      </section>
      <section class="panel" id="data">
        <h2>Sources &amp; columns ({len(sources)})</h2>
        {source_index or '<p class="empty">No sources yet.</p>'}
        <details><summary>All profiled tables and columns</summary>
        {source_sections}
        </details>
      </section>
      <section class="panel" id="integrity">
        <h2>Integrity</h2>
        {"<p>No integrity findings.</p>" if not integrity else f"<ul class='list'>{integrity_html}</ul>"}
      </section>
    </main>
  </div>
  <script>
    const search = document.getElementById('claim-search');
    const statusFilter = document.getElementById('status-filter');
    const predicateFilter = document.getElementById('predicate-filter');
    const roleFilter = document.getElementById('role-filter');
    const note = document.getElementById('filter-note');
    const cards = Array.from(document.querySelectorAll('[data-claim-card]'));
    const details = Array.from(document.querySelectorAll('[data-claim-detail]'));
    const emptyHint = document.getElementById('claim-empty');
    let stage = '';

    function applyFilter() {{
      const q = (search.value || '').toLowerCase();
      const s = statusFilter.value;
      const p = predicateFilter.value;
      const r = roleFilter.value;
      let shown = 0;
      for (const card of cards) {{
        const d = card.dataset;
        const visible =
          (!q || (d.search || '').includes(q)) &&
          (!s || d.status === s) &&
          (!p || d.predicate === p) &&
          (!r || d.role === r) &&
          (!stage || (d.stage === stage) || (stage === 'executed' && d.executed === 'yes'));
        card.style.display = visible ? '' : 'none';
        if (visible) shown++;
      }}
      note.textContent = shown + ' of ' + cards.length + ' claims shown'
        + (stage ? ' · funnel: ' + stage : '');
    }}

    function setStage(value) {{
      stage = (stage === value) ? '' : value;
      for (const chip of document.querySelectorAll('[data-stage-chip]')) {{
        chip.classList.toggle('active', chip.dataset.stageChip === stage);
      }}
      applyFilter();
    }}

    function showClaim(id) {{
      let found = false;
      for (const section of details) {{
        const match = section.id === 'claim-' + id;
        section.style.display = match ? 'block' : 'none';
        found = found || match;
      }}
      if (emptyHint) emptyHint.style.display = found ? 'none' : '';
    }}

    function reveal(hash) {{
      const target = document.getElementById(hash);
      if (!target) return;
      const section = target.closest('[data-claim-detail]');
      if (section) showClaim(section.dataset.claimId);
      for (let el = target.parentElement; el; el = el.parentElement) {{
        if (el.tagName === 'DETAILS') el.open = true;
      }}
      target.scrollIntoView({{block: 'start'}});
    }}

    search.addEventListener('input', applyFilter);
    for (const select of [statusFilter, predicateFilter, roleFilter]) {{
      select.addEventListener('change', applyFilter);
    }}
    for (const chip of document.querySelectorAll('[data-stage-chip]')) {{
      chip.addEventListener('click', () => {{
        const value = chip.dataset.stageChip;
        if (chip.dataset.status) {{
          statusFilter.value = chip.dataset.status;
          stage = '';
          for (const other of document.querySelectorAll('[data-stage-chip]')) {{
            other.classList.remove('active');
          }}
          applyFilter();
        }} else {{
          setStage(value);
        }}
      }});
    }}
    window.addEventListener('hashchange', () => reveal(location.hash.slice(1)));
    showClaim(null);
    if (location.hash) reveal(location.hash.slice(1));
    applyFilter();
  </script>
</body>
</html>
"""


def _claim_facts(store: ProjectStore, claims: list[Claim]) -> dict[str, ClaimFacts]:
    """One pass over the store: evidence, checks, derived status, funnel stage."""
    facts: dict[str, ClaimFacts] = {}
    for claim in claims:
        evidence = store.evidence_for(claim)
        # Persisted checks: bound directly (claim_id) or — for invariant checks,
        # which are bound to roles, not to one claim — reachable only through the
        # check_plan_id on this claim's evidence records.
        evidence_check_plan_ids = {record.check_plan_id for record in evidence if record.check_plan_id}
        checks = sorted(
            (
                check
                for check in store.checks.values()
                if check.claim_id == claim.id or check.id in evidence_check_plan_ids
            ),
            key=lambda check: (check.created_at, check.id),
        )
        # V2 declares why a claim got no check (unbindable / semantic_only /
        # skipped) — the model's own words, persisted, not left in the cache.
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


def _chip(count: int, label: str, stage: str, *, status: str | None = None) -> str:
    status_attr = f' data-status="{escape(status)}"' if status else ""
    return (
        f'<button type="button" class="chip" data-stage-chip="{escape(stage)}"{status_attr}>'
        f"<strong>{count}</strong><span class='label'>{escape(label)}</span></button>"
    )


def _render_funnel(facts: dict[str, ClaimFacts]) -> str:
    if not facts:
        return '<p class="empty">No claims yet.</p>'
    values = list(facts.values())
    stages = {name: sum(1 for f in values if f.stage == name) for name in STAGE_LABELS}
    executed = sum(1 for f in values if f.executed)
    by_status = defaultdict(int)
    for f in values:
        by_status[f.derived.value] += 1

    proposed = (
        "<div class='funnel-stage'><span class='step'>proposed</span>"
        + _chip(len(values), "claims (all proposed when created)", "")
        + "</div>"
    )
    bound = (
        "<div class='funnel-stage'><span class='step'>bound</span>"
        + "".join(
            _chip(stages[name], STAGE_LABELS[name], name)
            for name in STAGE_LABELS
            if stages[name]
        )
        + "</div>"
    )
    judged = (
        "<div class='funnel-stage'><span class='step'>judged</span>"
        + _chip(executed, "claims a check actually ran against", "executed")
        + "</div>"
    )
    verdicts = "<div class='funnel-stage'><span class='step'>status</span>" + "".join(
        _chip(by_status[status.value], status.value, f"status:{status.value}",
              status=status.value)
        for status in ClaimStatus
        if by_status[status.value]
    ) + "</div>"
    caveat = (
        "<p class='fine'>A claim without a check is not a claim that failed — it is a claim "
        "nobody tested, and it stays <em>proposed</em>. Every one of them carries the reason "
        "it got no check; open the claim to read it in the model's own words.</p>"
    )
    return f"<div class='funnel'>{proposed}{bound}{judged}{verdicts}</div>{caveat}"


def _render_core_terms() -> str:
    terms = "".join(
        f"<dt>{escape(term)}</dt><dd>{escape(text)}</dd>" for term, text in GLOSSARY
    )
    return (
        f"<p>{escape(READING_GUIDE)}</p>"
        "<details><summary>Core terms — the words this page uses, and no synonyms</summary>"
        f"<dl>{terms}</dl>"
        "<p class='fine'>Full glossary: docs/before-ai-concept.md.</p></details>"
    )


def _project_config(root: Path) -> dict:
    """The declared inputs, read straight from before-ai.yaml (read-only)."""
    path = root / CONFIG_FILE
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _render_domain_pack(root: Path, config: dict) -> str:
    return (
        f"<p class='muted'>{escape(DOMAIN_PACK_INTRO)}</p>"
        "<h3>1 · Raw data — the source list (human-authored)</h3>"
        f"{_render_declared_sources(config)}"
        "<h3>2 · Domain guide — the domain nouns (data, human-curated)</h3>"
        f"{_render_role_pack(root, config)}"
        "<h3>3 · Domain-law templates — the guardians (code, developer-shipped)</h3>"
        f"{_render_domain_law_templates()}"
    )


def _render_declared_sources(config: dict) -> str:
    sources = config.get("sources") or []
    if not sources:
        return '<p class="empty">No sources declared in before-ai.yaml.</p>'
    items = "".join(
        f"<li><code>{escape(str(source.get('name', '?')))}</code> "
        f"({escape(str(source.get('kind', '?')))}) — "
        f"{escape(str(source.get('location', '?')))}</li>"
        for source in sources
    )
    return f"<ul class='list'>{items}</ul>"


def _render_role_pack(root: Path, config: dict) -> str:
    path = _guide_path(root, config)
    if path is None:
        return '<p class="empty">No domain guide declared (llm.domain_guide_file).</p>'
    try:
        pack = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return (
            f'<p class="empty">Domain guide declared but unreadable: '
            f"<code>{escape(str(path))}</code></p>"
        )
    objects = pack.get("objects") or {}
    n_fields = sum(len((spec.get("fields") or {})) for spec in objects.values()
                   if isinstance(spec, dict))
    items = "".join(
        _render_guide_entry(name, spec)
        + "".join(f"<div class='guide-field'>{_render_guide_entry(fname, fspec)}</div>"
                  for fname, fspec in ((spec.get("fields") or {}).items()
                                       if isinstance(spec, dict) else ()))
        for name, spec in objects.items()
    )
    return (
        f"<p>domain <strong>{escape(str(pack.get('domain', '?')))}</strong>, "
        f"{len(objects)} business objects with {n_fields} "
        f"field{'s' if n_fields != 1 else ''} — human-written "
        "definitions, no system names; each declares its settlement path (how it "
        "can ever stop being a guess), and a field can never declare a law<br>"
        f"<code>{escape(str(path))}</code></p>{items}"
    )


def _render_guide_entry(name: str, spec) -> str:
    return (
        f"<details><summary><code>{escape(name)}</code> "
        f"<span class='fine'>{escape(_decided_by_label(spec))}</span></summary>"
        f"<p>{escape(str(_role_definition(spec)).strip())}</p></details>"
    )


def _role_definition(spec) -> str:
    if isinstance(spec, dict):
        return str(spec.get("definition", ""))
    return str(spec)


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


def _guide_path(root: Path, config: dict) -> Path | None:
    declared = (config.get("llm") or {}).get("domain_guide_file")
    if not declared:
        return None
    path = Path(declared)
    return path if path.is_absolute() else root / path


def _load_guide_shape(root: Path, config: dict) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """(entry order, entry -> decided_by, field -> its object) from the guide.

    Read tolerantly from the raw YAML: the viewer shows a broken guide, it
    does not refuse to render because of one.
    """
    path = _guide_path(root, config)
    if path is None:
        return [], {}, {}
    try:
        pack = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except OSError:
        return [], {}, {}
    order: list[str] = []
    decided_by: dict[str, str] = {}
    owner: dict[str, str] = {}
    for name, spec in (pack.get("objects") or {}).items():
        if not isinstance(spec, dict):
            continue
        order.append(name)
        decided_by[name] = spec.get("decided_by", "")
        for fname, fspec in (spec.get("fields") or {}).items():
            order.append(fname)
            owner[fname] = name
            if isinstance(fspec, dict):
                decided_by[fname] = fspec.get("decided_by", "")
    return order, decided_by, owner


def _settled_slot_columns(root: Path, config: dict, store: ProjectStore) -> dict[str, str]:
    """field -> the column its object's passing law consumed; empty if the
    guide does not load (the panel above already says so)."""
    path = _guide_path(root, config)
    if path is None:
        return {}
    try:
        guide = load_domain_guide(path)
    except (OSError, ValueError):
        return {}
    answered: dict[str, str] = {}
    for name in guide.objects:
        answered.update(settled_slots(store, guide, name))
    return answered


def _render_domain_law_templates() -> str:
    tagged = [(name, spec) for name, spec in REGISTRY.items() if spec.domain]
    generic = len(REGISTRY) - len(tagged)
    if not tagged:
        return '<p class="empty">No domain-law templates in the registry.</p>'
    items = "".join(
        f"<li><code>{escape(name)}</code> "
        f'<span class="badge status-business-confirmed">{escape(spec.domain)} law</span> — '
        f"<code>checks/templates/{escape(spec.file)}</code></li>"
        for name, spec in tagged
    )
    return (
        f"<ul class='list'>{items}</ul>"
        f"<p class='fine'>The other {generic} templates in the catalog are generic data "
        "checks (reference check, duplicates, coverage …) — they carry no domain "
        "knowledge and work in any domain.</p>"
    )


def _render_role_elections(
    facts: dict[str, ClaimFacts], questions: list[ClarificationQuestion],
    decided_by: dict[str, str], order: list[str] | None = None,
    owner: dict[str, str] | None = None, answered: dict[str, str] | None = None,
) -> str:
    owner = owner or {}
    answered = answered or {}
    by_role: dict[str, list[ClaimFacts]] = defaultdict(list)
    for fact in facts.values():
        if isinstance(fact.claim, MappingClaim):
            by_role[fact.claim.role].append(fact)
    if not by_role:
        return '<p class="empty">No role-binding candidates yet.</p>'
    # guide order — every object followed by its own fields; anything the
    # guide does not name (a stale claim from an older guide) sorts after
    rank_role = {name: i for i, name in enumerate(order or [])}
    ordered_roles = sorted(by_role, key=lambda r: (rank_role.get(r, len(rank_role)), r))

    rank = {
        ClaimStatus.TEST_SUPPORTED: 0,
        ClaimStatus.BUSINESS_CONFIRMED: 0,
        ClaimStatus.UNRESOLVED: 1,
        ClaimStatus.PROPOSED: 2,
        ClaimStatus.CONTRADICTED: 3,
    }
    blocks = []
    for role in ordered_roles:
        candidates = by_role[role]
        candidates.sort(key=lambda f: (rank[f.derived], f.claim.id))
        winners = [f for f in candidates if f.derived in (ClaimStatus.TEST_SUPPORTED, ClaimStatus.BUSINESS_CONFIRMED)]
        rows = "".join(_render_candidate(fact, fact in winners) for fact in candidates)
        claim_ids = {fact.claim.id for fact in candidates}
        cards = [card for card in questions if claim_ids & set(card.claim_ids)]
        if winners:
            outcome = (
                f"<p><strong>Elected:</strong> {_claim_link(winners[0].claim)} "
                f"{_status_badge(winners[0].derived.value)}</p>"
            )
        elif role in answered:
            # a slot needs no election of its own: the object's passing law
            # already consumed a column for it, and that run is the answer
            outcome = (
                f"<p><strong>Answered by the "
                f"{escape(decided_by.get(owner.get(role, ''), 'domain'))} law of "
                f"<code>{escape(owner.get(role, '?'))}</code>:</strong> the passing "
                f"check consumed <code>{escape(answered[role])}</code></p>"
            )
        elif cards:
            # the drafted clarification question is the outcome, whatever kept a law from
            # electing — checked-and-lost, unbindable, or a clarification-decided role
            outcome = "".join(
                f"<p><strong>No winner → clarification question:</strong> {_question_link(card)}</p>"
                for card in cards
            )
        elif not any(fact.checks for fact in candidates):
            outcome = (
                "<p class='muted'><strong>Not decided yet:</strong> no invariant check "
                "bound and no clarification question drafted — binding is still in flight.</p>"
            )
        else:
            outcome = (
                "<p class='muted'>No winner — every tested candidate lost, and no clarification question "
                "is drafted yet (run role resolution).</p>"
            )
        path_note = _decided_by_label({"decided_by": decided_by.get(role, "")})
        of_object = (f" <span class='fine'>field of "
                     f"<code>{escape(owner[role])}</code></span>"
                     if role in owner else "")
        blocks.append(
            f"<div class='election{' guide-field' if role in owner else ''}'>"
            f"<h3><code>{escape(role)}</code>{of_object} "
            f"<span class='muted'>{len(candidates)} candidate"
            f"{'s' if len(candidates) != 1 else ''}"
            f"{' · ' + escape(path_note) if path_note else ''}</span></h3>"
            f"{outcome}{rows}</div>"
        )
    return "".join(blocks)


def _render_candidate(fact: ClaimFacts, won: bool) -> str:
    css = "winner" if won else ("loser" if fact.derived is ClaimStatus.CONTRADICTED else "")
    reasons = "".join(
        f"<div class='fine'>felled by <code>{escape(template)}</code>"
        + (f" <span class='muted'>({escape(domain)} law)</span>" if domain else "")
        + f" — {detail}</div>"
        for template, domain, detail in _defeats(fact)
    )
    if not fact.checks and fact.no_check_reason:
        reasons += (
            f"<div class='fine'>never tested — {escape(fact.stage)}: "
            f"{escape(fact.no_check_reason)}</div>"
        )
    return (
        f"<div class='cand {css}'>"
        f"<div>{_claim_link(fact.claim)} {_status_badge(fact.derived.value)}</div>"
        f"{reasons}</div>"
    )


def _defeats(fact: ClaimFacts) -> list[tuple[str, str, str]]:
    """(template, domain, human detail) for every failing check on this claim."""
    checks = {check.id: check for check in fact.checks}
    out = []
    for record in fact.evidence:
        if record.type is not EvidenceType.CHECK_RESULT or record.verdict is not CheckVerdict.FAIL:
            continue
        check = checks.get(record.check_plan_id or "")
        template = check.template if check else "unknown template"
        spec = REGISTRY.get(template)
        detail = _population_text(record)
        out.append((template, (spec.domain if spec else None) or "", detail))
    return out


def _population_text(record: EvidenceRecord) -> str:
    if record.exception_count is None or record.population is None:
        return "check failed"
    return (
        f"{record.exception_count:,} exception"
        f"{'s' if record.exception_count != 1 else ''} in {record.population:,} rows"
    )


def _project_line(
    store: ProjectStore, sources: list[Source], profiles: list[DataProfile], candidates: int
) -> str:
    return (
        f"{len(sources)} sources · {len(profiles)} column profiles · {candidates} candidate "
        f"overlaps · {len(store.checks)} checks · {len(store.evidence)} evidence records."
    )


def _status_options() -> str:
    return "".join(
        f'<option value="{status.value}">{status.value}</option>'
        for status in ClaimStatus
    )


def _predicate_options(claims: list[Claim]) -> str:
    names = sorted({claim.predicate.name for claim in claims if claim.predicate})
    return "".join(f'<option value="{escape(n)}">{escape(n)}</option>' for n in names)


def _role_options(claims: list[Claim]) -> str:
    roles = sorted(
        {claim.role for claim in claims if isinstance(claim, MappingClaim)}
    )
    return "".join(f'<option value="{escape(r)}">{escape(r)}</option>' for r in roles)




def _render_matrix_summary(matrix: dict, warning_html: str) -> str:
    if not matrix:
        return '<p class="muted">No candidate matrix found.</p>'
    summary = (
        f"{len(matrix.get('candidates', []))} candidate overlaps, "
        f"{matrix.get('pairs_examined', 0)} pairs examined, "
        f"threshold {matrix.get('threshold', 'n/a')}."
    )
    warnings = (
        f"<ul class='list'>{warning_html}</ul>" if warning_html else ""
    )
    return f"<p>{escape(summary)}</p>{warnings}"


def _render_claim_index_card(fact: ClaimFacts) -> str:
    claim = fact.claim
    predicate = claim.predicate.name if claim.predicate else ""
    role = claim.role if isinstance(claim, MappingClaim) else ""
    search = " ".join(
        filter(None, [claim.statement, fact.derived.value, predicate, role])
    ).lower()
    hint = " · ".join(filter(None, [
        f"predicate: {predicate}" if predicate else "",
        f"role: {role}" if role else "",
        STAGE_LABELS[fact.stage] if fact.stage != "bound" else "",
    ]))
    return (
        f'<div class="claim-card" data-claim-card data-status="{escape(fact.derived.value)}" '
        f'data-stage="{escape(fact.stage)}" data-executed="{"yes" if fact.executed else "no"}" '
        f'data-predicate="{escape(predicate)}" data-role="{escape(role)}" '
        f'data-search="{escape(search)}">'
        f'<div><a href="#claim-{escape(claim.id)}"><strong>{escape(_short_id(claim.id))}</strong></a> '
        f'{_status_badge(fact.derived.value)}</div>'
        f'<div>{escape(claim.statement)}</div>'
        f'{f"<div class=\"muted\">{escape(hint)}</div>" if hint else ""}'
        "</div>"
    )


def _render_claim_section(
    fact: ClaimFacts,
    *,
    store: ProjectStore,
    questions_by_claim: dict[str, list[ClarificationQuestion]],
    reverse_depends: dict[str, list[Claim]],
    reverse_derived: dict[str, list[Claim]],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
) -> str:
    claim = fact.claim
    evidence = fact.evidence
    resolved = fact.derived
    checks = fact.checks
    sources = [store.sources[sid] for sid in claim.source_ids if sid in store.sources]
    fingerprints = _source_fingerprint_names(evidence)
    source_links = [f"<li>{_source_link(source)}</li>" for source in sources]
    for name in fingerprints:
        matched = next((source for source in store.sources.values() if source.name == name), None)
        if matched and matched.id not in claim.source_ids:
            source_links.append(
                f"<li>{_source_link(matched)} <span class='muted'>(via evidence fingerprint)</span></li>"
            )
        elif not matched:
            source_links.append(f"<li><code>{escape(name)}</code> <span class='muted'>(fingerprint only)</span></li>")

    binding_links = ""
    if hasattr(claim, "binding") and isinstance(getattr(claim, "binding"), dict):
        table = claim.binding.get("table")
        column = claim.binding.get("column")
        if table and column:
            key = f"{table}.{column}"
            binding_links = (
                f"<p><strong>Bound column:</strong> {_column_link(key)}</p>"
            )
        elif table:
            binding_links = (
                f"<p><strong>Bound table:</strong> {_table_link(table)}</p>"
            )

    evidence_html = "".join(
        _render_evidence_card(record, claim, store.claims, declarations_by_key, store.checks)
        for record in evidence
    ) or '<p class="empty">No evidence attached yet.</p>'
    rendered_sql = _rendered_sql_by_check_plan(evidence)
    check_plans_html = "".join(
        _render_check_plan_card(check, rendered_sql.get(check.id, "")) for check in checks
    ) or _no_check_html(fact)
    dependency_html = "".join(
        f"<li>{_claim_link(dep)} { _status_badge(dep.status.value) }</li>"
        for dep in (store.claims[dep_id] for dep_id in claim.depends_on if dep_id in store.claims)
    ) or '<li class="empty">No prerequisites.</li>'
    reverse_depends_html = "".join(
        f"<li>{_claim_link(other)} { _status_badge(other.status.value) }</li>"
        for other in reverse_depends.get(claim.id, [])
    ) or '<li class="empty">Nothing depends on this claim.</li>'
    reverse_derived_html = "".join(
        f"<li>{_claim_link(other)} { _status_badge(other.status.value) }</li>"
        for other in reverse_derived.get(claim.id, [])
    ) or '<li class="empty">No escalated child claims.</li>'
    questions_html = "".join(
        f"<li>{_question_link(card)}</li>" for card in questions_by_claim.get(claim.id, [])
    ) or '<li class="empty">No questions rest on this claim.</li>'
    subtype = _render_subtype_fields(claim)
    assumptions = _render_list(claim.open_assumptions, empty="No open assumptions.")
    source_html = f"<ul class='list'>{''.join(source_links)}</ul>" if source_links else '<p class="empty">No sources attached.</p>'
    lineage = ""
    if claim.derived_from or claim.derived_from_evidence:
        parent = store.claims.get(claim.derived_from or "")
        parent_evidence = store.evidence.get(claim.derived_from_evidence or "")
        lineage = (
            "<div class='mini-card'><h4>Escalation provenance</h4>"
            f"<p><strong>Parent claim:</strong> {(_claim_link(parent) if parent else '<span class=\"empty\">missing</span>')}</p>"
            f"<p><strong>Parent evidence:</strong> {(_evidence_link(parent_evidence) if parent_evidence else '<span class=\"empty\">missing</span>')}</p>"
            "</div>"
        )

    banner = ""
    if fact.diverges:
        banner = (
            f"<div class='banner'><strong>Stored status "
            f"{_status_badge(claim.status.value)} differs from the status derived "
            f"from live evidence {_status_badge(resolved.value)}.</strong> The derived "
            "status is the truth; the stored one is out of date (re-run the sweep).</div>"
        )
    proposed = _definition_list([
        ("predicate", claim.predicate.name if claim.predicate else "—"),
        ("params", _json_text(claim.predicate.params) if claim.predicate else "—"),
        ("proposed by", claim.created_by.value),
        ("funnel stage", STAGE_LABELS[fact.stage]),
    ])

    return (
        f'<div class="claim-detail" data-claim-detail data-claim-id="{escape(claim.id)}" '
        f'id="claim-{escape(claim.id)}">'
        f"<h3>{escape(claim.statement)}</h3>"
        f"<p>{_status_badge(resolved.value)} "
        f"<span class='muted'>{escape(_headline(fact))}</span></p>"
        f"{banner}"
        "<details open><summary>1 · Proposed — what the AI guessed</summary>"
        f"{proposed}{subtype}</details>"
        f"<details open><summary>2 · Bound — the checks that were meant to falsify it</summary>"
        f"{check_plans_html}</details>"
        f"<details open><summary>3 · Judged — what the data answered</summary>"
        f"{evidence_html}</details>"
        "<details><summary>4 · Context — sources, lineage, questions</summary>"
        "<div class='grid'>"
        f"<div class='mini-card'><h4>Sources</h4>{source_html}{binding_links}</div>"
        f"<div class='mini-card'><h4>Questions resting on it</h4><ul class='list'>{questions_html}</ul></div>"
        f"<div class='mini-card'><h4>Open assumptions</h4>{assumptions}</div>"
        f"<div class='mini-card'><h4>Depends on</h4><ul class='list'>{dependency_html}</ul></div>"
        f"<div class='mini-card'><h4>What depends on me</h4><ul class='list'>{reverse_depends_html}</ul></div>"
        f"<div class='mini-card'><h4>Escalated from me</h4><ul class='list'>{reverse_derived_html}</ul></div>"
        "</div>"
        f"{lineage}</details>"
        "<details><summary>Fine print — ids, timestamps, raw fields</summary>"
        f"{_definition_list(_claim_fields(claim))}</details>"
        "</div>"
    )


def _no_check_html(fact: ClaimFacts) -> str:
    """What stands where the check would have stood: why none was built."""
    if fact.stage == "unbound":
        return (
            '<p class="empty">No check, and no recorded reason — V2 has not run on this '
            "claim yet.</p>"
        )
    who = {
        "unbindable": "The model declined to bind this claim",
        "semantic_only": "No check definition can test this claim",
        "skipped": "Validation rejected the model's binding",
    }[fact.stage]
    reason = escape(fact.no_check_reason) if fact.no_check_reason else "no reason recorded"
    return (
        f"<div class='banner'><strong>Not bound — {escape(fact.stage)}.</strong> {who}, "
        f"so nothing ever tested it and it stays <em>proposed</em>."
        f"<blockquote class='fine'>{reason}</blockquote></div>"
    )


def _render_check_plan_card(check: CheckPlan, rendered_sql: str = "") -> str:
    details = [
        ("id", check.id),
        ("template", check.template),
        ("created_at", check.created_at.isoformat()),
        ("params", _json_text(check.params)),
    ]
    if check.roles:
        details.insert(2, ("roles", ", ".join(check.roles)))
    spec = REGISTRY.get(check.template)
    domain_badge = ""
    if spec is not None:
        if spec.domain:
            domain_badge = (
                f'<span class="badge status-business-confirmed">{escape(spec.domain)} law</span>'
            )
        if spec.tolerances:
            details.append(("default tolerances", _json_text(spec.tolerances)))
    return (
        f'<div class="evidence-card" id="check-{escape(check.id)}">'
        f"<div><a href=\"#check-{escape(check.id)}\"><strong>{escape(_short_id(check.id))}</strong></a> "
        f"<code>{escape(check.template)}</code> {domain_badge}</div>"
        f"{_definition_list(details)}"
        f"{_render_rendered_sql(rendered_sql)}"
        "</div>"
    )


def _render_rendered_sql(sql: str) -> str:
    """The exact question that was asked of the data — the SQL the engine ran.

    The rendered SQL is not on the CheckPlan; the runner puts it on the payload of the
    check-result evidence it writes (`payload['sql']`). Until a check has run there
    is nothing to show — a check is a question that was asked, not one that could be.
    """
    if not sql:
        return (
            "<p class='fine'>No rendered SQL yet — this check has not been run, so no "
            "question has actually been put to the data.</p>"
        )
    open_attr = " open" if sql.count("\n") < 12 else ""
    return (
        f"<details class='sql'{open_attr}><summary>Rendered SQL — the question that was "
        f"asked of the data</summary><pre><code>{escape(sql)}</code></pre></details>"
    )


def _rendered_sql_by_check_plan(evidence: list[EvidenceRecord]) -> dict[str, str]:
    """check id → the rendered SQL its result recorded (latest run wins)."""
    out: dict[str, str] = {}
    for record in evidence:
        if record.type is not EvidenceType.CHECK_RESULT or not record.check_plan_id:
            continue
        sql = str(record.payload.get("sql", "")) if record.payload else ""
        if sql:
            out[record.check_plan_id] = sql
    return out


def _claim_fields(claim: Claim) -> list[tuple[str, str]]:
    return [
        ("id", claim.id),
        ("created_by", claim.created_by.value),
        ("created_at", claim.created_at.isoformat()),
        ("status", claim.status.value),
        ("predicate", _json_text(claim.predicate.model_dump(mode="json")) if claim.predicate else "—"),
        ("scope", _json_text(claim.scope.model_dump(mode="json")) if claim.scope else "—"),
        ("validity", _json_text(claim.validity.model_dump(mode="json")) if claim.validity else "—"),
    ]


def _render_subtype_fields(claim: Claim) -> str:
    items = []
    if hasattr(claim, "term"):
        items.append(("term", getattr(claim, "term")))
    if hasattr(claim, "definition"):
        items.append(("definition", getattr(claim, "definition")))
    if hasattr(claim, "role"):
        items.append(("role", getattr(claim, "role")))
    if hasattr(claim, "binding"):
        items.append(("binding", _json_text(getattr(claim, "binding"))))
    if not items:
        return '<p class="empty">Plain claim.</p>'
    return _definition_list(items)


def _render_evidence_card(
    record: EvidenceRecord,
    claim: Claim,
    claims: dict[str, Claim],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    checks: dict[str, CheckPlan],
) -> str:
    details = [
        ("id", record.id),
        ("type", record.type.value),
        ("actor", record.actor.value),
        ("created_at", record.created_at.isoformat()),
        ("stale", str(record.stale).lower()),
    ]
    if record.claim_id:
        linked = claims.get(record.claim_id)
        details.append(("claim", linked.statement if linked else record.claim_id))
    if record.type is EvidenceType.CHECK_RESULT:
        details.extend([
            ("verdict", record.verdict.value if record.verdict else "—"),
            ("population", str(record.population) if record.population is not None else "—"),
            ("exception_count", str(record.exception_count) if record.exception_count is not None else "—"),
            (
                "exception_rate",
                f"{record.exception_rate():.2%}" if record.exception_rate() is not None else "—",
            ),
            ("result_ref", record.result_ref or "—"),
        ])
    if record.type is EvidenceType.CONFIRMATION:
        details.append(("mirror_loop_scope", "explicit" if record.scope and record.scope.is_explicit() else "not explicit"))
    if record.scope:
        details.append(("scope", _json_text(record.scope.model_dump(mode="json"))))
    if record.statement:
        details.append(("statement", record.statement))
    if record.source_fingerprints:
        details.append(("source_fingerprints", _json_text(record.source_fingerprints)))
    if record.payload:
        details.append(("payload", _json_text(record.payload)))
    samples = ""
    if record.exception_samples:
        rows = "".join(
            "<tr>" + "".join(f"<td>{escape(_stringify(value))}</td>" for value in sample.values()) + "</tr>"
            for sample in record.exception_samples
        )
        head = "".join(f"<th>{escape(key)}</th>" for key in record.exception_samples[0].keys())
        samples = (
            "<div><strong>Exception samples</strong>"
            f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
        )
    check_plan_hint = ""
    if record.check_plan_id:
        check = checks.get(record.check_plan_id)
        if check:
            check_plan_hint = (
                f"<p><strong>Produced by check:</strong> "
                f"<a href='#check-{escape(check.id)}'><code>{escape(check.template)}</code> "
                f"{escape(_short_id(check.id))}</a></p>"
            )
        else:
            details.append(("check_plan_id", f"{record.check_plan_id} (not persisted)"))
    declaration_hint = ""
    if record.type is EvidenceType.DECLARATION:
        source = str(record.payload.get("source", ""))
        table = str(record.payload.get("table", ""))
        column = str(record.payload.get("column", ""))
        key = (source, table, column)
        if table:
            declaration_hint = (
                f"<p><strong>Touches:</strong> {_table_link(table)}"
                + (f" / {_column_link(f'{table}.{column}')}" if column and column != "*" else "")
                + "</p>"
            )
        siblings = declarations_by_key.get(key, [])
        if len(siblings) > 1:
            declaration_hint += (
                f"<p class='muted'>{len(siblings)} declaration records exist for this same source/table/column.</p>"
            )
    verdict_badge = (
        _verdict_badge(record.verdict.value) if record.verdict else _type_badge(record.type.value)
    )
    return (
        f'<div class="evidence-card" id="evidence-{escape(record.id)}">'
        f"<div><a href=\"#evidence-{escape(record.id)}\"><strong>{escape(_short_id(record.id))}</strong></a> {verdict_badge}</div>"
        f"{_definition_list(details)}"
        f"{check_plan_hint}"
        f"{samples}"
        f"{declaration_hint}"
        "</div>"
    )


def _render_question_section(card: ClarificationQuestion, claims: dict[str, Claim]) -> str:
    claims_html = "".join(
        f"<li>{_claim_link(claims[cid])}</li>" for cid in card.claim_ids if cid in claims
    ) or '<li class="empty">No linked claims.</li>'
    return (
        f'<div class="question-card" id="question-{escape(card.id)}">'
        f"<h3>{escape(card.question)}</h3>"
        f"{_definition_list([('id', card.id), ('created_at', card.created_at.isoformat()), ('stale', str(card.stale).lower()), ('sql', card.sql or '—'), ('result_ref', card.result_ref or '—')])}"
        f"<h4>Claims</h4><ul class='list'>{claims_html}</ul>"
        "</div>"
    )


def _render_source_index_card(source: Source, profiles: dict[str, list[DataProfile]]) -> str:
    count = len(profiles.get(source.id, []))
    return (
        f'<div class="claim-card"><a href="#source-{escape(source.id)}"><strong>{escape(source.name)}</strong></a>'
        f"<div class='muted'>{escape(source.kind)} · {count} columns profiled</div></div>"
    )


def _render_source_section(
    source: Source,
    profiles: list[DataProfile],
    claims: list[Claim],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    role_bindings: dict[str, list[Claim]],
    candidates_by_column: dict[str, list[dict]],
) -> str:
    claims_html = "".join(
        f"<li>{_claim_link(claim)} { _status_badge(claim.status.value) }</li>" for claim in claims
    ) or '<li class="empty">No claims attach this source directly.</li>'
    tables: dict[str, list[DataProfile]] = defaultdict(list)
    for profile in profiles:
        tables[profile.table].append(profile)
    table_html = "".join(
        _render_table_section(
            source.name,
            table,
            columns,
            declarations_by_key,
            role_bindings,
            candidates_by_column,
        )
        for table, columns in sorted(tables.items())
    ) or '<p class="empty">No profiled tables for this source.</p>'
    return (
        f'<div class="mini-card" id="source-{escape(source.id)}">'
        f"<h3>{escape(source.name)}</h3>"
        f"{_definition_list([('id', source.id), ('kind', source.kind), ('location', source.location), ('fingerprint', _json_text(source.fingerprint))])}"
        f"<h4>Claims touching this source</h4><ul class='list'>{claims_html}</ul>"
        f"{table_html}"
        "</div>"
    )


def _render_orphan_profiles(
    profiles: list[DataProfile],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    role_bindings: dict[str, list[Claim]],
    candidates_by_column: dict[str, list[dict]],
) -> str:
    tables: dict[str, list[DataProfile]] = defaultdict(list)
    for profile in profiles:
        tables[profile.table].append(profile)
    body = "".join(
        _render_table_section(
            "missing-source",
            table,
            columns,
            declarations_by_key,
            role_bindings,
            candidates_by_column,
        )
        for table, columns in sorted(tables.items())
    )
    return f"<div class='mini-card'><h3>Profiles with missing sources</h3>{body}</div>"


def _render_table_section(
    source_name: str,
    table: str,
    columns: list[DataProfile],
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    role_bindings: dict[str, list[Claim]],
    candidates_by_column: dict[str, list[dict]],
) -> str:
    table_declarations = declarations_by_key.get((source_name, table, "*"), [])
    declarations_html = "".join(
        f"<li>{_evidence_link(record)} — {escape(_json_text(record.payload))}</li>"
        for record in table_declarations
    ) or '<li class="empty">No table-level declarations.</li>'
    columns_html = "".join(
        _render_column_card(
            source_name,
            column,
            declarations_by_key,
            role_bindings,
            candidates_by_column,
        )
        for column in columns
    )
    return (
        f'<div class="mini-card" id="table-{escape(table)}">'
        f"<h4>{_table_link(table)}</h4>"
        f"<ul class='list'>{declarations_html}</ul>"
        f"{columns_html}"
        "</div>"
    )


def _render_column_card(
    source_name: str,
    profile: DataProfile,
    declarations_by_key: dict[tuple[str, str, str], list[EvidenceRecord]],
    role_bindings: dict[str, list[Claim]],
    candidates_by_column: dict[str, list[dict]],
) -> str:
    key = f"{profile.table}.{profile.column}"
    declarations = declarations_by_key.get((source_name, profile.table, profile.column), [])
    declaration_html = "".join(
        f"<li>{_evidence_link(record)} — {escape(_json_text(record.payload))}</li>"
        for record in declarations
    ) or '<li class="empty">No column-level declarations.</li>'
    role_html = "".join(
        f"<li>{_claim_link(claim)} { _status_badge(claim.status.value) }</li>"
        for claim in role_bindings.get(key, [])
    ) or '<li class="empty">No role bindings target this column.</li>'
    candidate_html = "".join(
        f"<li>{_column_link(other['other'])} "
        f"<span class='muted'>containment {escape(str(other['containment']))}, overlap {escape(str(other['overlap']))}</span></li>"
        for other in candidates_by_column.get(key, [])
    ) or '<li class="empty">No candidate overlaps.</li>'
    return (
        f'<div class="column-card" id="column-{escape(key)}">'
        f"<h5>{_column_link(key)}</h5>"
        f"{_definition_list([('profile_id', profile.id), ('stats', _json_text(profile.stats))])}"
        f"<h6>Declarations</h6><ul class='list'>{declaration_html}</ul>"
        f"<h6>Candidate overlaps</h6><ul class='list'>{candidate_html}</ul>"
        f"<h6>Role-binding claims</h6><ul class='list'>{role_html}</ul>"
        "</div>"
    )


def _render_list(values: Iterable[object], *, empty: str) -> str:
    items = list(values)
    if not items:
        return f'<p class="empty">{escape(empty)}</p>'
    return "<ul class='list'>" + "".join(f"<li>{escape(_stringify(v))}</li>" for v in items) + "</ul>"


def _definition_list(items: Iterable[tuple[str, str]]) -> str:
    rows = []
    for key, value in items:
        rendered = (
            f"<pre>{escape(value)}</pre>"
            if "\n" in value or value.startswith("{") or value.startswith("[")
            else escape(value)
        )
        rows.append(f"<dt>{escape(key)}</dt><dd>{rendered}</dd>")
    return "<dl>" + "".join(rows) + "</dl>"


def _status_badge(status: str) -> str:
    return f'<span class="badge {STATUS_COLORS.get(status, "status-proposed")}">{escape(status)}</span>'


def _verdict_badge(verdict: str) -> str:
    return f'<span class="badge {VERDICT_COLORS.get(verdict, "verdict-inconclusive")}">{escape(verdict)}</span>'


def _type_badge(kind: str) -> str:
    return f'<span class="badge status-proposed">{escape(kind)}</span>'


def _claim_link(claim: Claim | None) -> str:
    if claim is None:
        return '<span class="empty">missing claim</span>'
    return f'<a href="#claim-{escape(claim.id)}">{escape(_short_id(claim.id))} — {escape(claim.statement)}</a>'


def _evidence_link(record: EvidenceRecord | None) -> str:
    if record is None:
        return '<span class="empty">missing evidence</span>'
    return f'<a href="#evidence-{escape(record.id)}">{escape(_short_id(record.id))} — {escape(record.type.value)}</a>'


def _source_link(source: Source) -> str:
    return f'<a href="#source-{escape(source.id)}">{escape(source.name)}</a>'


def _question_link(card: ClarificationQuestion) -> str:
    return f'<a href="#question-{escape(card.id)}">{escape(_short_id(card.id))} — {escape(card.question)}</a>'


def _table_link(table: str) -> str:
    return f'<a href="#table-{escape(table)}"><code>{escape(table)}</code></a>'


def _column_link(column: str) -> str:
    return f'<a href="#column-{escape(column)}"><code>{escape(column)}</code></a>'


def _headline(fact: ClaimFacts) -> str:
    """The one line a validator should be able to stop reading after."""
    if fact.derived is ClaimStatus.PROPOSED and fact.stage != "bound":
        return f"Never tested — {STAGE_LABELS[fact.stage]}."
    return _status_rationale(fact.claim, fact.evidence)


def _status_rationale(claim: Claim, evidence: list[EvidenceRecord]) -> str:
    live = [record for record in evidence if not record.stale]
    check_pass = sum(
        1 for record in live
        if record.type is EvidenceType.CHECK_RESULT and record.verdict is CheckVerdict.PASS
    )
    check_fail = sum(
        1 for record in live
        if record.type is EvidenceType.CHECK_RESULT and record.verdict is CheckVerdict.FAIL
    )
    confirmation = sum(1 for record in live if record.type is EvidenceType.CONFIRMATION)
    testimonial = sum(1 for record in live if record.type is EvidenceType.TESTIMONIAL)
    parts = []
    if check_pass:
        parts.append(f"{check_pass} passing check result{'s' if check_pass != 1 else ''}")
    if check_fail:
        parts.append(f"{check_fail} failing check result{'s' if check_fail != 1 else ''}")
    if confirmation:
        parts.append(f"{confirmation} confirmation{'s' if confirmation != 1 else ''}")
    if testimonial:
        parts.append(f"{testimonial} testimonial{'s' if testimonial != 1 else ''}")
    trail = ", ".join(parts) if parts else "no live status-bearing evidence"
    if claim.status is ClaimStatus.UNRESOLVED:
        why = "Conflict is present: at least one failing check coexists with supporting evidence."
    elif claim.status is ClaimStatus.CONTRADICTED:
        why = "At least one failing check is present and no competing supporting evidence remains live."
    elif claim.status is ClaimStatus.BUSINESS_CONFIRMED:
        why = "At least one admissible human confirmation is live and no failing check overrides it."
    elif claim.status is ClaimStatus.TEST_SUPPORTED:
        why = "At least one passing check is live and no failing check overrides it."
    else:
        why = "Nothing stronger than proposed evidence is live yet."
    return f"{why} Live trail: {trail}."


def _short_id(value: str) -> str:
    # ULIDs are timestamp-first: a whole V1 batch is created in the same
    # millisecond and shares its leading characters. Only the tail identifies.
    return f"…{value[-6:]}"


def _json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _stringify(value: object) -> str:
    if isinstance(value, (dict, list)):
        return _json_text(value)
    return str(value)


def _load_candidate_matrix(root: Path) -> dict:
    path = root / "profiles" / "candidate_matrix.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _questions_by_claim(questions: list[ClarificationQuestion]) -> dict[str, list[ClarificationQuestion]]:
    out: dict[str, list[ClarificationQuestion]] = defaultdict(list)
    for card in questions:
        for claim_id in card.claim_ids:
            out[claim_id].append(card)
    return out


def _reverse_claim_links(claims: list[Claim]) -> tuple[dict[str, list[Claim]], dict[str, list[Claim]]]:
    reverse_depends: dict[str, list[Claim]] = defaultdict(list)
    reverse_derived: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        for dep in claim.depends_on:
            reverse_depends[dep].append(claim)
        if claim.derived_from:
            reverse_derived[claim.derived_from].append(claim)
    return reverse_depends, reverse_derived


def _declarations_by_key(records: Iterable[EvidenceRecord]) -> dict[tuple[str, str, str], list[EvidenceRecord]]:
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
        left_data = {
            "other": right,
            "containment": candidate.get("containment"),
            "overlap": candidate.get("overlap"),
        }
        right_data = {
            "other": left,
            "containment": candidate.get("containment"),
            "overlap": candidate.get("overlap"),
        }
        out[left].append(left_data)
        out[right].append(right_data)
    for items in out.values():
        items.sort(key=lambda item: (-float(item["containment"]), -int(item["overlap"]), item["other"]))
    return out


def _profiles_by_source(profiles: list[DataProfile]) -> dict[str, list[DataProfile]]:
    out: dict[str, list[DataProfile]] = defaultdict(list)
    for profile in profiles:
        out[profile.source_id].append(profile)
    return out


def _source_fingerprint_names(records: list[EvidenceRecord]) -> list[str]:
    names = sorted({name for record in records for name in record.source_fingerprints})
    return names


def _source_name(source: Source | None) -> str:
    return source.name.lower() if source else ""
