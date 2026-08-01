import os
from html import escape
from pathlib import Path
from typing import Iterable

from readiness_report import projection


STATUS_COLORS = {
    "proposed": "status-proposed",
    "test-supported": "status-test-supported",
    "contradicted": "status-contradicted",
    "unresolved": "status-unresolved",
    "business-confirmed": "status-business-confirmed",
}

VERDICT_COLORS = {
    "pass": "verdict-pass",
    "fail": "verdict-fail",
    "inconclusive": "verdict-inconclusive",
}


def default_output_path(root: Path) -> Path:
    return root.resolve().parent / f"{root.name}-readiness-report.html"


def write_project_view(
    root: str | Path, output: str | Path | None = None
) -> Path:
    root_path = Path(root).resolve()
    out = (
        Path(output).resolve()
        if output
        else default_output_path(root_path)
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        render_project(root_path, out.parent), encoding="utf-8"
    )
    return out


def render_project(
    root: str | Path, out_dir: str | Path | None = None
) -> str:
    root_path = Path(root).resolve()
    store_rel = _relative_prefix(root_path, out_dir)
    view = projection.load_view_model(root_path)

    claim_index = "".join(
        _render_claim_index_card(claim.index)
        for claim in view.claims
    ) or '<p class="empty">No claims yet.</p>'
    claim_sections = "".join(
        _render_claim_section(claim, store_rel)
        for claim in view.claims
    ) or '<p class="empty">No claims yet.</p>'
    question_sections = "".join(
        _render_question_section(card, store_rel)
        for card in view.open_questions
    ) or '<p class="empty">No open questions.</p>'
    answered_sections = (
        "<details><summary>Answered questions "
        f"({len(view.answered_questions)}) — kept, because what settled "
        "them is part of the record</summary>"
        + "".join(
            _render_answered_question(card, store_rel)
            for card in view.answered_questions
        )
        + "</details>"
        if view.answered_questions
        else ""
    )
    source_index = "".join(
        _render_source_index_card(source)
        for source in view.measurement.sources
    )
    source_sections = "".join(
        _render_source_section(source)
        for source in view.measurement.sources
    ) or '<p class="empty">No sources yet.</p>'
    if view.measurement.orphan_tables:
        source_sections += _render_orphan_profiles(
            view.measurement.orphan_tables
        )
    integrity_html = "".join(
        f"<li>{escape(finding)}</li>"
        for finding in view.integrity
    )
    diagram = _render_process_diagram(
        view.stages, view.copy.process_ghost
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Readiness report — {escape(view.project_name)}</title>
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
    /* the process diagram: the whole machine on one line, with live counts */
    .flow {{
      display: flex;
      align-items: stretch;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }}
    .node {{
      flex: 1 1 150px;
      display: flex;
      flex-direction: column;
      gap: 4px;
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 10px 12px;
    }}
    .node-step {{
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .node-title a {{ color: var(--text); font-weight: 700; }}
    .node-counts {{ display: grid; gap: 2px; margin-top: 2px; }}
    .node-count {{ font-size: 12px; color: var(--muted); }}
    .node-count strong {{ color: var(--text); font-size: 14px; }}
    .node-count:hover, .node-count:hover strong {{ color: var(--link); }}
    .node-actor {{
      margin-top: auto;
      padding-top: 6px;
      font-size: 11px;
      color: var(--muted);
      font-style: italic;
    }}
    .arrow {{ align-self: center; color: var(--muted); }}
    .boundary {{
      align-self: stretch;
      border-left: 2px dashed var(--contradicted);
      margin: 0 6px;
      padding-left: 4px;
      display: flex;
      align-items: center;
    }}
    .boundary span {{
      writing-mode: vertical-rl;
      font-size: 11px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .ghosts {{ display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }}
    .ghost {{
      border: 1px dashed var(--line);
      border-radius: 12px;
      padding: 8px 12px;
      color: var(--muted);
      font-size: 12px;
    }}
    .ghost strong {{ color: var(--text); }}
    @media (max-width: 700px) {{
      .arrow {{ display: none; }}
      .boundary {{
        border-left: 0;
        border-top: 2px dashed var(--contradicted);
        width: 100%;
        padding: 6px 0 0;
        margin: 0;
      }}
      .boundary span {{ writing-mode: horizontal-tb; }}
    }}
    .banner {{
      border: 1px solid var(--unresolved);
      background: rgba(217, 119, 6, 0.15);
      border-radius: 10px;
      padding: 10px 12px;
      margin: 10px 0;
    }}
    .headline {{ font-size: 15px; margin: 6px 0 12px; }}
    /* provenance: where a thing came from, what it feeds, the file it is in */
    .prov {{
      font-size: 12px;
      color: var(--muted);
      margin: 8px 0 4px;
      padding-top: 6px;
      border-top: 1px solid var(--line);
    }}
    .prov .yaml {{ font-family: ui-monospace, monospace; }}
    details.tech > summary {{ font-size: 11px; }}
    .picks {{ margin: 4px 0 0; padding-left: 18px; }}
    .picks li {{ margin-bottom: 4px; }}
    .picks .muted {{ font-size: 12px; }}
    /* the derived sentence — the page's own voice, never the model's */
    .derived {{ font-size: 15px; margin: 4px 0 8px; }}
    .quote {{
      border-left: 3px solid var(--line);
      margin: 8px 0;
      padding: 2px 0 2px 10px;
      color: var(--muted);
      font-style: italic;
    }}
    .quote cite {{ display: block; font-style: normal; font-size: 11px; }}
    /* the AI's words: legible, attributed, and never the headline of a status */
    .ai-said {{
      border-left: 3px solid var(--proposed);
      margin: 8px 0;
      padding: 2px 0 2px 10px;
      font-size: 13px;
    }}
    .ai-said cite {{ display: block; font-style: normal; font-size: 11px; color: var(--muted); }}
    /* the readiness map: the verdict leads, each dependency states itself */
    .ready-map {{
      border: 1px solid var(--line);
      border-left-width: 4px;
      border-radius: 8px;
      padding: 12px 14px;
      margin-bottom: 14px;
    }}
    .ready-ready {{ border-left-color: var(--pass); }}
    .ready-ready_with_limitations {{ border-left-color: var(--proposed); }}
    .ready-blocked {{ border-left-color: var(--fail); }}
    .ready-map .verdict {{ font-size: 16px; }}
    .ready-map h4 {{ margin: 14px 0 6px; text-transform: uppercase;
      letter-spacing: .04em; }}
    .ready-item {{
      border-left: 3px solid var(--line);
      padding: 2px 0 2px 10px;
      margin: 8px 0;
    }}
    .ready-item.supported {{ border-left-color: var(--pass); }}
    .ready-item.missing {{ border-left-color: var(--fail); }}
    .ready-item.waived {{ border-left-style: dashed; opacity: .7; }}
    .ready-item.waived h5 code {{ text-decoration: line-through; }}
    .ready-item h5 {{ margin: 0 0 2px; font-size: 13px; }}
    .strip {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }}
    .strip .step {{
      font-size: 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 10px;
      color: var(--muted);
    }}
    .strip .step.done {{ border-color: var(--test-supported); color: var(--text); }}
    .strip .step.stopped {{ border-color: var(--unresolved); color: var(--text); }}
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
    details.sql > summary, #inputs details > summary, #terms details > summary {{
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
      <h1>Readiness report</h1>
      <p class="muted">{escape(view.project_path)}</p>
      <div class="section-links">
        <a href="#process">Process</a>
        <a href="#inputs">0 Inputs</a>
        <a href="#request">1 Request</a>
        <a href="#measured">2 Measured</a>
        <a href="#proposed">3 Proposed</a>
        <a href="#tested">4 Tested</a>
        <a href="#clarification">5 Clarification</a>
        <a href="#readiness">6 Readiness</a>
        <a href="#claims">Claim detail</a>
        <a href="#integrity">Integrity</a>
        <a href="#terms">Core terms</a>
      </div>
      <div class="panel">
        <h2 id="claims-index">Claims ({len(view.claims)})</h2>
        <div class="toolbar">
          <input id="claim-search" type="search" placeholder="Search statement or predicate">
          <select id="status-filter">
            <option value="">All statuses (derived)</option>
            {_render_options(view.status_options)}
          </select>
          <select id="predicate-filter">
            <option value="">All predicates</option>
            {_render_options(view.predicate_options)}
          </select>
          <select id="role-filter">
            <option value="">All roles</option>
            {_render_options(view.role_options)}
          </select>
        </div>
        <p id="filter-note" class="muted"></p>
        <div id="claim-list">{claim_index}</div>
      </div>
    </aside>
    <main class="content">
      <section class="panel" id="process">
        <h2>How this project got from data to knowledge</h2>
        {diagram}
        <p class="muted">{escape(view.copy.reading_guide)}</p>
      </section>
      <section class="panel" id="inputs">
        <h2>0 · Inputs — what a human declared</h2>
        {_render_domain_pack(view.domain_pack)}
      </section>
      <section class="panel" id="request">
        <h2>1 · Request — the question, and what it requires</h2>
        <p class="muted">{view.copy.request_intro}</p>
        {_render_requests(view.requests, store_rel, view.copy.no_request)}
      </section>
      <section class="panel" id="measured">
        <h2>2 · Measured — what the data says about itself ({view.measurement.source_count} sources)</h2>
        <p class="muted">{view.copy.measured_intro}</p>
        <p class="muted">{escape(view.measurement.project_line)}</p>
        {_render_matrix_summary(view.measurement.matrix)}
        {source_index or '<p class="empty">No sources yet.</p>'}
        <details><summary>All profiled tables and columns</summary>
        {source_sections}
        </details>
      </section>
      <section class="panel" id="proposed">
        <h2>3 · Proposed — what the AI guessed, and how far each guess got</h2>
        <p class="muted">{_render_rich(view.copy.proposed_intro)}</p>
        {_render_funnel(view.funnel)}
      </section>
      <section class="panel" id="tested">
        <h2>4 · Tested — what the checks settled</h2>
        <p class="muted">{view.copy.tested_intro}</p>
        {_render_role_elections(view.elections)}
      </section>
      <section class="panel" id="clarification">
        <h2>5 · Clarification — what only a human can answer ({len(view.open_questions)})</h2>
        <p class="muted">{view.copy.clarification_intro}</p>
        {question_sections}
        {answered_sections}
      </section>
      <section class="panel" id="readiness">
        <h2>6 · Readiness — what may be answered</h2>
        <p class="muted">{view.copy.readiness_intro}</p>
        {_render_readiness(view.readiness, store_rel, view.copy.no_request)}
      </section>
      <section class="panel" id="claims">
        <h2>7 · Claim detail — one claim, its whole story</h2>
        <p id="claim-empty" class="muted">Pick a claim on the left.</p>
        {claim_sections}
      </section>
      <section class="panel" id="integrity">
        <h2>Integrity</h2>
        {"<p>No integrity findings.</p>" if not view.integrity else f"<ul class='list'>{integrity_html}</ul>"}
      </section>
      <section class="panel" id="terms">
        <h2>Core terms</h2>
        {_render_core_terms(view.glossary)}
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


def _relative_prefix(
    root: Path, out_dir: str | Path | None
) -> str:
    """How to reach the project store from where the page will be written.

        Falls back to the default output location, which is what the CLI uses
        when no `-o` is given. An unreachable relative path (different drive)
        degrades to an absolute one rather than to a broken link.
    """
    base = (
        Path(out_dir).resolve()
        if out_dir
        else default_output_path(root).parent
    )
    try:
        rel = os.path.relpath(root, base)
    except ValueError:
        rel = str(root)
    return rel.replace(os.sep, "/").rstrip("/") + "/"


def _render_part(part: projection.TextPartView) -> str:
    if part.style == "status":
        rendered = _status_badge(part.text)
    else:
        rendered = escape(
            part.text, quote=part.escape_quotes
        )
        if part.style == "strong":
            rendered = f"<strong>{rendered}</strong>"
        elif part.style == "em":
            rendered = f"<em>{rendered}</em>"
        elif part.style == "code":
            rendered = f"<code>{rendered}</code>"
        elif part.style == "muted":
            rendered = f"<span class='muted'>{rendered}</span>"
    if part.reference is not None:
        rendered = (
            f'<a href="#{escape(part.reference.kind)}-'
            f'{escape(part.reference.id)}">{rendered}</a>'
        )
    return rendered


def _render_rich(text: projection.RichTextView) -> str:
    return "".join(_render_part(part) for part in text.parts)


def _render_quote(quote: projection.QuoteView) -> str:
    return (
        f"<blockquote class='{escape(quote.css)}'>"
        f"{escape(quote.text)}<cite>{_render_rich(quote.cite)}"
        "</cite></blockquote>"
    )


def _render_link(link: projection.LinkView) -> str:
    reference = link.reference
    return (
        f'<a href="#{escape(reference.kind)}-{escape(reference.id)}">'
        f"{escape(link.label)}</a>"
    )


def _render_link_single(link: projection.LinkView) -> str:
    reference = link.reference
    return (
        f"<a href='#{escape(reference.kind)}-"
        f"{escape(reference.id)}'>{escape(link.label)}</a>"
    )


def _table_link(table: str) -> str:
    return (
        f'<a href="#table-{escape(table)}">'
        f"<code>{escape(table)}</code></a>"
    )


def _column_link(column: str) -> str:
    return (
        f'<a href="#column-{escape(column)}">'
        f"<code>{escape(column)}</code></a>"
    )


def _yaml_link(
    rel: str, reference: projection.ReferenceView
) -> str:
    """The page is disposable; this is the file that is not."""
    return (
        f'<a class="yaml" href="{escape(rel)}'
        f'{escape(reference.kind)}/{escape(reference.id)}.yaml">'
        f"{escape(reference.kind)}/"
        f"{escape('…' + reference.id[-6:])}.yaml</a>"
    )


def _provenance(
    rel: str, provenance: projection.ProvenanceView
) -> str:
    """Where a thing came from, what it feeds, and the file it really lives in."""
    shown = " · ".join(
        note for note in provenance.notes if note
    )
    return (
        f"<div class='prov'>{shown}{' · ' if shown else ''}"
        f"{_yaml_link(rel, provenance.reference)}</div>"
    )


def _technical(items: Iterable[tuple[str, str]]) -> str:
    """Ids, timestamps and raw fields — reachable, never in the way."""
    return (
        "<details class='tech'><summary>Technical details</summary>"
        f"{_definition_list(items)}</details>"
    )


def _render_options(values: Iterable[str]) -> str:
    return "".join(
        f'<option value="{escape(value)}">{escape(value)}</option>'
        for value in values
    )


def _render_process_diagram(
    stages: tuple[projection.StageView, ...],
    ghost: projection.RichTextView,
) -> str:
    """The whole machine on one line, with this project's numbers in it.

        Stages, their order, their actors and the boundary all come from
        ``before_we_ai.stages`` — the diagram renders the spine, it does not
        restate it. ``counts`` supplies this project's live numbers per stage
        name; a stage with none still draws, because a stage that has produced
        nothing yet is information.
    """
    arrow = '<div class="arrow" aria-hidden="true">→</div>'
    parts = []
    for stage in stages:
        if stage.boundary_before:
            parts.append(
                f'<div class="boundary"><span>'
                f'{escape(stage.boundary_before)}</span></div>'
            )
        counts = "".join(
            f'<a class="node-count" href="#{escape(stage.name)}">'
            f"<strong>{escape(number)}</strong> "
            f"{escape(label)}</a>"
            for number, label in stage.counts
        )
        parts.append(
            f'<div class="node"><div class="node-step">'
            f"{escape(stage.label)}</div>"
            f'<div class="node-title"><a href="#{escape(stage.name)}">'
            f"{escape(stage.title)}</a></div>"
            f'<div class="node-counts">{counts}</div>'
            f'<div class="node-actor">{escape(stage.actor)}</div></div>'
        )
    flow = arrow.join(parts)
    ghosts = (
        '<div class="ghosts"><div class="ghost">'
        f"{_render_rich(ghost)}</div></div>"
    )
    return f'<div class="flow">{flow}</div>{ghosts}'


def _render_domain_pack(view: projection.DomainPackView) -> str:
    return (
        f"<p class='muted'>{escape(view.intro)}</p>"
        "<h3>1.1 · Raw data — the source list "
        "(human-authored)</h3>"
        f"{_render_declared_sources(view.sources)}"
        "<h3>1.2 · Domain guide — the domain nouns "
        "(data, human-curated)</h3>"
        f"{_render_domain_guide_panel(view.guide)}"
        "<h3>1.3 · Domain-law templates — the guardians "
        "(code, developer-shipped)</h3>"
        f"{_render_domain_law_templates(view.laws)}"
    )


def _render_declared_sources(
    sources: tuple[projection.DeclaredSourceView, ...],
) -> str:
    if not sources:
        return (
            '<p class="empty">No sources declared in '
            "before-ai.yaml.</p>"
        )
    items = "".join(
        f"<li><code>{escape(source.name)}</code> "
        f"({escape(source.kind)}) — {escape(source.location)}</li>"
        for source in sources
    )
    return f"<ul class='list'>{items}</ul>"


def _render_guide_entry(
    entry: projection.GuideEntryView,
) -> str:
    return (
        f"<details><summary><code>{escape(entry.name)}</code> "
        f"<span class='fine'>{escape(entry.decision)}</span>"
        f"</summary><p>{escape(entry.definition)}</p></details>"
    )


def _render_domain_guide_panel(
    guide: projection.DomainGuidePanelView,
) -> str:
    if guide.state == "missing":
        return (
            '<p class="empty">No domain guide declared '
            "(llm.domain_guide_file).</p>"
        )
    if guide.state == "unreadable":
        return (
            '<p class="empty">Domain guide declared but unreadable: '
            f"<code>{escape(guide.path)}</code></p>"
        )
    items = "".join(
        _render_guide_entry(entry)
        + "".join(
            "<div class='guide-field'>"
            f"{_render_guide_entry(field)}</div>"
            for field in entry.fields
        )
        for entry in guide.entries
    )
    return (
        f"<p>domain <strong>{escape(guide.domain)}</strong>, "
        f"{guide.object_count} business objects with "
        f"{guide.field_count} field"
        f"{'s' if guide.field_count != 1 else ''} — human-written "
        "definitions, no system names; each declares its settlement "
        "path (how it can ever stop being a guess), and a field can "
        "never declare a law<br>"
        f"<code>{escape(guide.path)}</code></p>{items}"
    )


def _render_domain_law_templates(
    laws: projection.DomainLawsView,
) -> str:
    """This project's domain pack — not the whole catalog.

        A law of another domain is not an input here: the guide lint refuses to
        let this guide declare one. Listing it under "what this project
        declared" would be a false claim about the project's inputs, so the
        other domains are counted, not enumerated.
    """
    if laws.laws:
        body = "<ul class='list'>" + "".join(
            f"<li><code>{escape(law.name)}</code> "
            '<span class="badge status-business-confirmed">'
            f"{escape(law.domain)} law</span> — "
            f"<code>checks/templates/{escape(law.file)}</code></li>"
            for law in laws.laws
        ) + "</ul>"
    elif laws.domain:
        body = (
            "<p class='empty'>"
            f"{_render_rich(laws.empty_message)}</p>"
        )
    else:
        body = (
            '<p class="empty">'
            f"{_render_rich(laws.empty_message)}</p>"
        )
    return body + f"<p class='fine'>{escape(laws.note)}</p>"


def _render_requests(
    requests: tuple[projection.RequestView, ...],
    rel: str,
    no_request: str,
) -> str:
    if not requests:
        return f'<p class="empty">{escape(no_request)}</p>'
    return "".join(
        _render_request_card(request, rel)
        for request in requests
    )


def _render_request_card(
    request: projection.RequestView, rel: str
) -> str:
    items = "".join(
        f"<li class='{'waived' if item.waived else ''}'>"
        f"<code>{escape(item.ref)}</code> "
        f"<span class='muted'>{escape(item.kind)} · "
        f"{escape(item.provenance)}</span>"
        + (
            f"<p class='fine'>Waived: "
            f"{escape(item.waived_because)}</p>"
            if item.waived
            else ""
        )
        + (
            f"<blockquote class='ai-said'>{escape(item.why)}"
            f"<cite>{escape(item.why_cite)}</cite></blockquote>"
            if item.why
            else ""
        )
        + "</li>"
        for item in request.items
    )
    return (
        f"<div class='ready-map' id='request-{escape(request.id)}'>"
        f"<blockquote class='quote'>{escape(request.question)}"
        "<cite>— the business question, as it was asked</cite>"
        "</blockquote>"
        f"<p class='derived'>{_render_rich(request.treated_as)}</p>"
        f"<blockquote class='ai-said'>"
        f"{escape(request.requested_output)}"
        "<cite>— the AI, on what the answer must deliver</cite>"
        "</blockquote>"
        f"<p class='fine'>{escape(request.scope_line)}</p>"
        f"<h4 class='fine'>{escape(request.dependency_heading)}</h4>"
        f"<ul class='picks'>{items}</ul>"
        f"{_provenance(rel, request.provenance)}</div>"
    )


def _render_readiness(
    maps: tuple[projection.ReadinessView, ...],
    rel: str,
    no_request: str,
) -> str:
    if not maps:
        return f'<p class="empty">{escape(no_request)}</p>'
    return "".join(
        _render_readiness_map(result, rel) for result in maps
    )


def _render_readiness_map(
    result: projection.ReadinessView, rel: str
) -> str:
    scope_line = (
        f"<p class='fine'>{escape(result.scope_line)}</p>"
        if result.scope_line
        else ""
    )
    body = "".join(
        f"<h4 class='fine'>{escape(group.title)}</h4>"
        + "".join(
            _render_readiness_item(item)
            for item in group.items
        )
        for group in result.groups
    )
    return (
        f"<div class='ready-map ready-{escape(result.verdict)}' "
        f"id='readiness-{escape(result.id)}'>"
        f"<p class='fine'><a href='#request-{escape(result.id)}'>"
        f"{escape(result.question)}</a></p>{scope_line}"
        f"<p class='derived verdict'><strong>"
        f"{escape(result.headline)}</strong> "
        f"{escape(result.reason)}</p>"
        f"<p class='muted'>{escape(result.explanation)}</p>"
        f"{body}{_provenance(rel, result.provenance)}</div>"
    )


def _render_readiness_item(
    item: projection.ReadinessItemView,
) -> str:
    """One dependency: the derived sentence first, the AI's reason under it.

        The three-voices rule at its sharpest. The status sentence is derived
        and is the headline; the ``why`` the model wrote when it listed this
        dependency is legible, attributed, and subordinate — it explains why the
        item is on the list, never what became of it.
    """
    links = " ".join(
        _render_link_single(claim) for claim in item.claims
    )
    linked = "".join(
        f"<p class='fine'>{_render_rich(link.sentence)}</p>"
        for link in item.links
    )
    return (
        f"<div class='ready-item {escape(item.mark)}'>"
        f"<h5><code>{escape(item.ref)}</code> "
        f"<span class='muted'>{escape(item.kind)}</span></h5>"
        f"<p class='derived'>{escape(item.because)}</p>"
        f"{linked}"
        + (
            f"<p class='fine'>Claims: {links}</p>"
            if links and not linked
            else ""
        )
        + "</div>"
    )


def _render_funnel(view: projection.FunnelView) -> str:
    if not view.stages:
        return f'<p class="empty">{escape(view.empty)}</p>'
    stages = "".join(
        "<div class='funnel-stage'>"
        f"<span class='step'>{escape(stage.label)}</span>"
        + "".join(_render_chip(chip) for chip in stage.chips)
        + "</div>"
        for stage in view.stages
    )
    return (
        f"<div class='funnel'>{stages}</div>"
        f"<p class='fine'>{_render_rich(view.caveat)}</p>"
    )


def _render_chip(chip: projection.FunnelChipView) -> str:
    status = (
        f' data-status="{escape(chip.status)}"'
        if chip.status
        else ""
    )
    return (
        f'<button type="button" class="chip" '
        f'data-stage-chip="{escape(chip.stage)}"{status}>'
        f"<strong>{chip.count}</strong>"
        f"<span class='label'>{escape(chip.label)}</span></button>"
    )


def _render_role_elections(
    elections: tuple[projection.ElectionView, ...],
) -> str:
    if not elections:
        return (
            '<p class="empty">No role-binding candidates yet.</p>'
        )
    return "".join(
        _render_election(election) for election in elections
    )


def _render_election(election: projection.ElectionView) -> str:
    of_object = (
        " <span class='fine'>field of "
        f"<code>{escape(election.owner)}</code></span>"
        if election.owner
        else ""
    )
    for_scope = (
        f" <span class='fine'>for "
        f"{escape(election.scope)}</span>"
        if election.scope
        else ""
    )
    said = (
        f"<blockquote class='quote'>{escape(election.definition)}"
        "<cite>— what the domain guide says this is</cite>"
        "</blockquote>"
        if election.definition
        else ""
    )
    outcome = "".join(
        f"<p class='{escape(css)}'>{_render_rich(text)}</p>"
        for css, text in election.outcome.paragraphs
    )
    rows = "".join(
        _render_candidate(candidate)
        for candidate in election.candidates
    )
    return (
        f"<div class='election"
        f"{' guide-field' if election.field else ''}'>"
        f"<h3><code>{escape(election.role)}</code>{of_object}"
        f"{for_scope} <span class='muted'>"
        f"{election.candidate_count} candidate"
        f"{'s' if election.candidate_count != 1 else ''}"
        f"{' · ' + escape(election.path_note) if election.path_note else ''}"
        f"</span></h3>{said}{outcome}{rows}</div>"
    )


def _render_candidate(
    candidate: projection.ElectionCandidateView,
) -> str:
    reasons = "".join(
        f"<div class='fine'>{_render_rich(reason)}</div>"
        for reason in candidate.reasons
    )
    return (
        f"<div class='cand {escape(candidate.css)}'>"
        f"<div>{_render_link(candidate.link)} "
        f"{_status_badge(candidate.status)}</div>"
        f"{reasons}</div>"
    )


def _render_question_section(
    card: projection.QuestionView, rel: str
) -> str:
    """A question, then the candidates as a list — never as prose.

        The options used to be flattened into the question text itself; they are
        the claims the card already links, and a list of bindings written out as
        a sentence is the least readable form of that data.

        Whether the list is a *choice* is not read off the question's wording —
        it is read off the guide: only a role the guide sends to the humans
        (`decided_by: clarification`) is answered by picking one. A role whose
        law could never be applied is asking for knowledge, not for a pick.
    """
    if card.mode == "bindings":
        rows = "".join(
            f"<li>{_render_binding(option)} "
            f"{_render_link(option.link)}</li>"
            for option in card.options
        )
        picks = (
            f"<p class='muted'>{escape(card.lead)}</p>"
            f"<ul class='picks'>{rows}</ul>"
        )
    elif card.mode == "claims":
        rows = "".join(
            f"<li>{_render_link(option.link)} "
            f"{_status_badge(option.status)}</li>"
            for option in card.options
        )
        picks = (
            f"<p class='muted'>{escape(card.lead)}</p>"
            f"<ul class='picks'>{rows}</ul>"
        )
    else:
        picks = f"<p class='empty'>{escape(card.lead)}</p>"
    return (
        f'<div class="question-card" id="question-{escape(card.id)}">'
        f"<h3>{escape(card.question)}</h3>{picks}"
        f"{_provenance(rel, card.provenance)}"
        f"{_technical(card.details)}</div>"
    )


def _render_binding(
    option: projection.QuestionOptionView,
) -> str:
    if option.binding_kind == "column":
        return _column_link(option.binding)
    if option.binding_kind == "table":
        return _table_link(option.binding)
    return f"<code>{escape(option.binding)}</code>"


def _render_answered_question(
    card: projection.AnsweredQuestionView, rel: str
) -> str:
    """An answered card, with what settled it.

        Kept rather than dropped, for the same reason a waiver is kept: the
        question that had to be asked, and the answer that closed it, are part
        of how this landscape came to be understood.
    """
    answers = "".join(
        f"<li>{_render_link(item.link)} "
        f"<span class='muted'>{escape(item.status)}</span></li>"
        for item in card.settled
    )
    return (
        f'<div class="question-card answered" '
        f'id="question-{escape(card.id)}">'
        f"<h3>{escape(card.question)}</h3>"
        f"<p class='derived'><strong>"
        f"{escape(card.summary.split('. ', 1)[0] + '.')}</strong> "
        f"{escape(card.summary.split('. ', 1)[1])}</p>"
        f"<ul class='picks'>{answers}</ul>"
        f"{_provenance(rel, card.provenance)}</div>"
    )


def _render_matrix_summary(view: projection.MatrixView) -> str:
    if not view.found:
        return '<p class="muted">No candidate matrix found.</p>'
    warnings = "".join(
        f"<li>{escape(warning)}</li>" for warning in view.warnings
    )
    warning_html = (
        f"<ul class='list'>{warnings}</ul>" if warnings else ""
    )
    return f"<p>{escape(view.summary)}</p>{warning_html}"


def _render_source_index_card(
    source: projection.SourceView,
) -> str:
    return (
        f'<div class="claim-card"><a href="#source-{escape(source.id)}">'
        f"<strong>{escape(source.name)}</strong></a>"
        f"<div class='muted'>{escape(source.kind)} · "
        f"{source.profile_count} columns profiled</div></div>"
    )


def _render_source_section(
    source: projection.SourceView,
) -> str:
    claims = "".join(
        f"<li>{_render_link(item.link)} "
        f"{_status_badge(item.status)}</li>"
        for item in source.claims
    ) or '<li class="empty">No claims attach this source directly.</li>'
    tables = "".join(
        _render_table_section(table) for table in source.tables
    ) or '<p class="empty">No profiled tables for this source.</p>'
    return (
        f'<div class="mini-card" id="source-{escape(source.id)}">'
        f"<h3>{escape(source.name)}</h3>"
        f"{_definition_list(source.details)}"
        f"<h4>Claims touching this source</h4>"
        f"<ul class='list'>{claims}</ul>{tables}</div>"
    )


def _render_orphan_profiles(
    tables: tuple[projection.TableView, ...],
) -> str:
    body = "".join(_render_table_section(table) for table in tables)
    return (
        "<div class='mini-card'><h3>Profiles with missing "
        f"sources</h3>{body}</div>"
    )


def _render_table_section(table: projection.TableView) -> str:
    declarations = "".join(
        f"<li>{_render_link(item.link)} — "
        f"{escape(item.payload)}</li>"
        for item in table.declarations
    ) or '<li class="empty">No table-level declarations.</li>'
    columns = "".join(
        _render_column_card(column) for column in table.columns
    )
    return (
        f'<div class="mini-card" id="table-{escape(table.name)}">'
        f"<h4>{_table_link(table.name)}</h4>"
        f"<ul class='list'>{declarations}</ul>{columns}</div>"
    )


def _render_column_card(column: projection.ColumnView) -> str:
    declarations = "".join(
        f"<li>{_render_link(item.link)} — "
        f"{escape(item.payload)}</li>"
        for item in column.declarations
    ) or '<li class="empty">No column-level declarations.</li>'
    roles = "".join(
        f"<li>{_render_link(item.link)} "
        f"{_status_badge(item.status)}</li>"
        for item in column.role_bindings
    ) or '<li class="empty">No role bindings target this column.</li>'
    candidates = "".join(
        f"<li>{_column_link(item.other)} "
        f"<span class='muted'>containment "
        f"{escape(item.containment)}, overlap "
        f"{escape(item.overlap)}</span></li>"
        for item in column.candidates
    ) or '<li class="empty">No candidate overlaps.</li>'
    return (
        f'<div class="column-card" id="column-{escape(column.key)}">'
        f"<h5>{_column_link(column.key)}</h5>"
        f"{_definition_list(column.details)}"
        f"<h6>Declarations</h6><ul class='list'>"
        f"{declarations}</ul>"
        f"<h6>Candidate overlaps</h6><ul class='list'>"
        f"{candidates}</ul>"
        f"<h6>Role-binding claims</h6><ul class='list'>"
        f"{roles}</ul></div>"
    )


def _render_claim_index_card(
    view: projection.ClaimIndexView,
) -> str:
    return (
        f'<div class="claim-card" data-claim-card '
        f'data-status="{escape(view.derived_status)}" '
        f'data-stage="{escape(view.stage)}" '
        f'data-executed="{"yes" if view.executed else "no"}" '
        f'data-predicate="{escape(view.predicate)}" '
        f'data-role="{escape(view.role)}" '
        f'data-search="{escape(view.search)}">'
        f'<div><a href="#claim-{escape(view.id)}"><strong>'
        f"{escape(view.short_id)}</strong></a> "
        f"{_status_badge(view.derived_status)}</div>"
        f"<div>{escape(view.title)}</div>"
        + (
            f'<div class="muted">{escape(view.hint)}</div>'
            if view.hint
            else ""
        )
        + "</div>"
    )


def _render_claim_section(
    claim: projection.ClaimView, rel: str
) -> str:
    evidence = "".join(
        _render_evidence_card(item, rel) for item in claim.evidence
    ) or '<p class="empty">No evidence attached yet.</p>'
    checks = "".join(
        _render_check_plan_card(check, rel) for check in claim.checks
    )
    if not checks:
        checks = _render_no_check(claim.no_check)
    dependencies = _render_link_status_list(
        claim.dependencies, "No prerequisites."
    )
    reverse_dependencies = _render_link_status_list(
        claim.reverse_dependencies,
        "Nothing depends on this claim.",
    )
    derived_children = _render_link_status_list(
        claim.derived_children, "No escalated child claims."
    )
    questions = "".join(
        f"<li>{_render_link(link)}</li>"
        for link in claim.questions
    ) or '<li class="empty">No questions rest on this claim.</li>'
    sources = "".join(
        _render_claim_source(item) for item in claim.sources
    )
    source_html = (
        f"<ul class='list'>{sources}</ul>"
        if sources
        else '<p class="empty">No sources attached.</p>'
    )
    binding = ""
    if claim.bound_column:
        binding = (
            "<p><strong>Bound column:</strong> "
            f"{_column_link(claim.bound_column)}</p>"
        )
    elif claim.bound_table:
        binding = (
            "<p><strong>Bound table:</strong> "
            f"{_table_link(claim.bound_table)}</p>"
        )
    lineage = _render_lineage(claim.lineage)
    banner = (
        "<div class='banner'><strong>"
        f"{_render_rich(claim.divergence)}</strong></div>"
        if claim.divergence
        else ""
    )
    subtype = (
        _definition_list(claim.subtype_details)
        if claim.subtype_details is not None
        else '<p class="empty">Plain claim.</p>'
    )
    return (
        f'<div class="claim-detail" data-claim-detail '
        f'data-claim-id="{escape(claim.index.id)}" '
        f'id="claim-{escape(claim.index.id)}">'
        f"<h3>{escape(claim.index.title)}</h3>"
        f"<p>{_status_badge(claim.index.derived_status)} "
        f"<span class='muted'>{escape(claim.headline)}</span></p>"
        f"{_render_stage_strip(claim.stage_steps)}"
        f"{_render_rationale(claim.rationale)}"
        f"{_provenance(rel, claim.provenance)}{banner}"
        "<details open><summary>1 · Proposed — what the AI "
        "guessed</summary>"
        f"{_render_quote(claim.proposal)}"
        f"{_definition_list(claim.proposed_details)}"
        f"{subtype}</details>"
        "<details open><summary>2 · Bound — the checks that "
        "were meant to falsify it</summary>"
        f"{checks}</details>"
        "<details open><summary>3 · Judged — what the data "
        f"answered</summary>{evidence}</details>"
        "<details><summary>4 · Context — sources, lineage, "
        "questions</summary><div class='grid'>"
        f"<div class='mini-card'><h4>Sources</h4>{source_html}"
        f"{binding}</div>"
        "<div class='mini-card'><h4>Questions resting on it</h4>"
        f"<ul class='list'>{questions}</ul></div>"
        "<div class='mini-card'><h4>Open assumptions</h4>"
        f"{_render_list(claim.assumptions, empty='No open assumptions.')}"
        "</div>"
        "<div class='mini-card'><h4>Depends on</h4>"
        f"<ul class='list'>{dependencies}</ul></div>"
        "<div class='mini-card'><h4>What depends on me</h4>"
        f"<ul class='list'>{reverse_dependencies}</ul></div>"
        "<div class='mini-card'><h4>Escalated from me</h4>"
        f"<ul class='list'>{derived_children}</ul></div>"
        f"</div>{lineage}</details>"
        "<details><summary>Fine print — ids, timestamps, raw "
        f"fields</summary>{_definition_list(claim.details)}</details>"
        "</div>"
    )


def _render_stage_strip(
    steps: tuple[projection.StageStepView, ...],
) -> str:
    return "<div class='strip'>" + "".join(
        f"<span class='step {escape(step.state)}'>"
        f"{escape(step.label)} — {escape(step.explanation)}</span>"
        for step in steps
    ) + "</div>"


def _render_rationale(
    rationale: projection.QuoteView | str | None,
) -> str:
    if rationale is None:
        return ""
    if isinstance(rationale, str):
        return f"<p class='fine'>{escape(rationale)}</p>"
    return _render_quote(rationale)


def _render_no_check(
    view: projection.NoCheckView | None,
) -> str:
    if view is None:
        return ""
    if not view.stage:
        return f'<p class="empty">{_render_rich(view.explanation)}</p>'
    return (
        f"<div class='banner'><strong>Not bound — "
        f"{escape(view.stage)}.</strong> "
        f"{_render_rich(view.explanation)}"
        f"<blockquote class='fine'>{escape(view.reason)}"
        "</blockquote></div>"
    )


def _render_check_plan_card(
    check: projection.CheckView, rel: str
) -> str:
    domain_badge = (
        '<span class="badge status-business-confirmed">'
        f"{escape(check.domain)} law</span>"
        if check.domain
        else ""
    )
    return (
        f'<div class="evidence-card" id="check-{escape(check.id)}">'
        f'<div><a href="#check-{escape(check.id)}"><strong>'
        f"{escape(check.short_id)}</strong></a> "
        f"<code>{escape(check.template)}</code> {domain_badge}</div>"
        f"<p class='derived'>{escape(check.sentence)}</p>"
        f"{_render_rendered_sql(check.rendered_sql)}"
        f"{_provenance(rel, check.provenance)}"
        f"{_technical(check.details)}</div>"
    )


def _render_rendered_sql(sql: str) -> str:
    """The exact question that was asked of the data — the SQL the engine ran.

        The rendered SQL is not on the CheckPlan; the runner puts it on the payload of the
        check-result evidence it writes (`payload['sql']`). Until a check has run there
        is nothing to show — a check is a question that was asked, not one that could be.
    """
    if not sql:
        return (
            "<p class='fine'>No rendered SQL yet — this check has "
            "not been run, so no question has actually been put to "
            "the data.</p>"
        )
    open_attr = " open" if sql.count("\n") < 12 else ""
    return (
        f"<details class='sql'{open_attr}><summary>Rendered SQL — "
        "the question that was asked of the data</summary>"
        f"<pre><code>{escape(sql)}</code></pre></details>"
    )


def _render_evidence_card(
    record: projection.EvidenceView, rel: str
) -> str:
    badge = (
        _verdict_badge(record.badge_value)
        if record.badge_kind == "verdict"
        else _type_badge(record.badge_value)
    )
    check = ""
    if record.check_link:
        check = (
            "<p><strong>Produced by check:</strong> "
            f"<a href='#check-{escape(record.check_link.reference.id)}'>"
            f"<code>{escape(record.check_template)}</code> "
            f"{escape('…' + record.check_link.reference.id[-6:])}"
            "</a></p>"
        )
    samples = ""
    if record.sample_headers:
        head = "".join(
            f"<th>{escape(value)}</th>"
            for value in record.sample_headers
        )
        rows = "".join(
            "<tr>"
            + "".join(
                f"<td>{escape(value)}</td>" for value in row
            )
            + "</tr>"
            for row in record.sample_rows
        )
        samples = (
            "<div><strong>Exception samples</strong>"
            f"<table><thead><tr>{head}</tr></thead>"
            f"<tbody>{rows}</tbody></table></div>"
        )
    declaration = ""
    if record.touched_table:
        declaration = (
            "<p><strong>Touches:</strong> "
            f"{_table_link(record.touched_table)}"
            + (
                " / "
                f"{_column_link(record.touched_table + '.' + record.touched_column)}"
                if record.touched_column
                and record.touched_column != "*"
                else ""
            )
            + "</p>"
        )
    if record.sibling_declarations:
        declaration += (
            f"<p class='muted'>{record.sibling_declarations} "
            "declaration records exist for this same "
            "source/table/column.</p>"
        )
    return (
        f'<div class="evidence-card" '
        f'id="evidence-{escape(record.id)}">'
        f'<div><a href="#evidence-{escape(record.id)}"><strong>'
        f"{escape(record.short_id)}</strong></a> {badge}</div>"
        f"<p class='derived'>{escape(record.sentence)}</p>"
        f"{_render_quote(record.voice) if record.voice else ''}"
        f"{check}{samples}{declaration}"
        f"{_provenance(rel, record.provenance)}"
        f"{_technical(record.details)}</div>"
    )


def _render_claim_source(
    item: projection.LinkStatusView,
) -> str:
    if item.link.reference.kind:
        link = _render_link(item.link)
    else:
        link = f"<code>{escape(item.link.label)}</code>"
    note = (
        f" <span class='muted'>({escape(item.note)})</span>"
        if item.note
        else ""
    )
    return f"<li>{link}{note}</li>"


def _render_link_status_list(
    items: tuple[projection.LinkStatusView, ...],
    empty: str,
) -> str:
    return "".join(
        f"<li>{_render_link(item.link)} "
        f"{_status_badge(item.status)}</li>"
        for item in items
    ) or f'<li class="empty">{escape(empty)}</li>'


def _render_lineage(
    lineage: projection.LineageView | None,
) -> str:
    if lineage is None:
        return ""
    parent = (
        _render_link(lineage.parent)
        if lineage.parent
        else '<span class="empty">missing</span>'
    )
    evidence = (
        _render_link(lineage.evidence)
        if lineage.evidence
        else '<span class="empty">missing</span>'
    )
    return (
        "<div class='mini-card'><h4>Escalation provenance</h4>"
        f"<p><strong>Parent claim:</strong> {parent}</p>"
        f"<p><strong>Parent evidence:</strong> {evidence}</p>"
        "</div>"
    )


def _render_list(
    values: Iterable[object], *, empty: str
) -> str:
    items = list(values)
    if not items:
        return f'<p class="empty">{escape(empty)}</p>'
    return "<ul class='list'>" + "".join(
        f"<li>{escape(str(value))}</li>" for value in items
    ) + "</ul>"


def _definition_list(
    items: Iterable[tuple[str, str]],
) -> str:
    rows = []
    for key, value in items:
        rendered = (
            f"<pre>{escape(value)}</pre>"
            if "\n" in value
            or value.startswith("{")
            or value.startswith("[")
            else escape(value)
        )
        rows.append(
            f"<dt>{escape(key)}</dt><dd>{rendered}</dd>"
        )
    return "<dl>" + "".join(rows) + "</dl>"


def _status_badge(status: str) -> str:
    return (
        f'<span class="badge '
        f'{STATUS_COLORS.get(status, "status-proposed")}">'
        f"{escape(status)}</span>"
    )


def _verdict_badge(verdict: str) -> str:
    return (
        f'<span class="badge '
        f'{VERDICT_COLORS.get(verdict, "verdict-inconclusive")}">'
        f"{escape(verdict)}</span>"
    )


def _type_badge(kind: str) -> str:
    return (
        f'<span class="badge status-proposed">'
        f"{escape(kind)}</span>"
    )


def _render_core_terms(
    glossary: tuple[tuple[str, str], ...],
) -> str:
    terms = "".join(
        f"<dt>{escape(term)}</dt><dd>{escape(text)}</dd>"
        for term, text in glossary
    )
    return (
        "<details><summary>Core terms — the words this page "
        "uses, and no synonyms</summary>"
        f"<dl>{terms}</dl>"
        "<p class='fine'>Full glossary: "
        "docs/before-ai-concept.md.</p></details>"
    )
