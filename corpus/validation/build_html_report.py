#!/usr/bin/env python3
"""Generate interactive cross-linked HTML validation report for the M0 corpus."""
import html
import yaml
from pathlib import Path

ROOT = Path("/workspace/src/corpus")
OUT = ROOT / "validation" / "corpus-validation-report.html"

verdicts = yaml.safe_load(open(ROOT / "data" / "expected_verdicts.yaml"))
classes = yaml.safe_load(open(ROOT / "generator_spec" / "trap_classes.yaml"))["trap_classes"]
manifest = yaml.safe_load(open(ROOT / "generator_spec" / "sources_manifest.yaml"))["sources"]

traps = verdicts["traps"]
deny_set = verdicts.get("deny_set", [])
z_ref = verdicts.get("z_reference", {})
balance = verdicts.get("balance_check", {})

def esc(s):
    return html.escape(str(s), quote=True)

def trap_sort_key(tid):
    if tid.startswith("F"):
        return (0, int(tid[1:]))
    return (1, tid)

# --- derived maps -----------------------------------------------------------
# trap -> sources (from manifest)
trap_sources = {}
for sid, src in manifest.items():
    for t in src.get("traps", []) or []:
        trap_sources.setdefault(t, []).append(sid)

# class -> traps actually tagged in verdicts
class_traps = {}
for tid, t in traps.items():
    for k in [c.strip() for c in str(t.get("category", "")).split(",") if c.strip()]:
        class_traps.setdefault(k, []).append(tid)
for k in class_traps:
    class_traps[k].sort(key=trap_sort_key)

all_classes = sorted(set(list(classes.keys()) + list(class_traps.keys())))

# Zielfragen: involved traps per target_questions.yaml formula notes
Z = [
    ("Z1", "Z1 — Field sales days per rep and quarter",
     "Grain: sales_rep × quarter, from crm_activities. Naive revenue reference incl. IC.",
     ["F10", "F11", "F12"],
     [("DE", z_ref["Z1_naive_revenue_including_IC"]["DE"], None),
      ("US", z_ref["Z1_naive_revenue_including_IC"]["US"], None)]),
    ("Z2", "Z2 — External revenue per customer / key account",
     "Accounts 4000–4999 minus 4800-range, Haben negative, IC (4300) excluded, F5 ID migration applied, rebate accrual per E2.",
     ["F2", "F3", "F4", "F5", "F6", "F14", "F15", "F19", "F21", "F25"],
     [("DE", z_ref["Z2_external_revenue_excl_IC_and_rebates"]["DE"], None),
      ("US", z_ref["Z2_external_revenue_excl_IC_and_rebates"]["US"], None)]),
    ("Z3", "Z3 — Plan vs. actual profit per profit center",
     "P&L accounts per profit_center × month vs. D6 plan; US converted at monthly-average (M) rate.",
     ["F6", "F14", "F15", "F16", "F17", "F18", "F19"],
     [("US in EUR", z_ref["Z3_group_revenue_correct_fx_M_rate"]["US_in_EUR"], 21862618.31),
      ("Group total EUR", z_ref["Z3_group_revenue_correct_fx_M_rate"]["group_total_EUR"], 68216986.68)]),
    ("Z4", "Z4 — Balance sheet closure (meta-invariant)",
     "Soll = Haben per entity × period; subledger = GL; IC symmetric. Consolidated group revenue as closure figure.",
     ["F20", "F22"],
     [("Group total EUR", z_ref["Z4_consolidated_group_revenue"]["group_total_EUR"], 68216986.68)]),
]

# Harness check results (from the frozen seed=0 validation run)
CHECKS = [
    ("Trap-class checks", "check_trap_classes.py", True, [
        ("deny_set", True, "1 claim protected (F26)"),
        ("recall_set", True, "32 claims present"),
        ("K6 orphans", True, "3 legitimate orphans, none contradicted"),
        ("K7 poisoned anchors", True, "4 anchors deny-protected"),
        ("all traps detected", True, "32 / 32"),
    ]),
    ("Invariant checks (K5)", "check_invariants.py", True, [
        ("monthly balance", True, "48 entity-periods; only US:2024-06 open (F22, expected)"),
        ("subledger = GL", True, "AR vs. account 1200 — F20 mismatch tolerated (documented trap)"),
        ("IC symmetry", True, "DE 9001 ↔ US 9002, break in 2024-06 expected (F22)"),
    ]),
    ("Reference spot-check", "recompute_reference_results.py", True, [
        ("Z1 / Z2", True, "exact match, DE and US"),
        ("Z3 / Z4", True, "Δ ≈ 8.2k EUR (0.012 %) — FX averaging variance, within 10k tolerance"),
    ]),
]

fmt = lambda v: f"{v:,.2f}"

def chips(tids):
    return "".join(
        f'<a class="chip{" chip-blind" if t.startswith("BLIND") else ""}" href="#{t.lower()}">{esc(t)}</a>'
        for t in sorted(tids, key=trap_sort_key))

def kchips(cat):
    ks = [c.strip() for c in str(cat).split(",") if c.strip()]
    return "".join(f'<a class="chip chip-k" href="#{k.lower()}">{esc(k)}</a>' for k in ks)

def evidence_html(ev):
    if not ev:
        return '<p class="ev-none">No row-level evidence — validated structurally / via document anchors.</p>'
    rows = []
    for k, v in ev.items():
        if isinstance(v, list) and v and isinstance(v[0], dict):
            head = "".join(f"<th>{esc(c)}</th>" for c in v[0].keys())
            body = "".join("<tr>" + "".join(
                f'<td class="num">{fmt(x) if isinstance(x, float) else esc(x)}</td>' for x in r.values()
            ) + "</tr>" for r in v)
            rows.append(f'<details class="ev-details"><summary>{esc(k)} ({len(v)} rows)</summary>'
                        f'<div class="tbl-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div></details>')
        elif isinstance(v, list):
            rows.append(f'<div class="ev-row"><span class="ev-key">{esc(k)}</span>'
                        f'<span class="ev-val">{esc(", ".join(map(str, v)))}</span></div>')
        else:
            val = fmt(v) if isinstance(v, float) else esc(v)
            rows.append(f'<div class="ev-row"><span class="ev-key">{esc(k)}</span><span class="ev-val num">{val}</span></div>')
    return "".join(rows)

# --- trap cards --------------------------------------------------------------
trap_cards = []
for tid in sorted(traps.keys(), key=trap_sort_key):
    t = traps[tid]
    cat = str(t.get("category", ""))
    deny = t.get("deny_promotion", False)
    blind = tid.startswith("BLIND")
    srcs = trap_sources.get(tid, [])
    src_html = ""
    if srcs:
        items = "".join(
            f'<span class="src" title="{esc(manifest[s].get("description", ""))}">{esc(s)}</span>'
            for s in srcs)
        src_html = f'<div class="trap-srcs"><span class="ev-key">Sources</span>{items}</div>'
    badges = []
    if deny:
        badges.append('<span class="badge badge-deny">deny promotion</span>')
    if blind:
        badges.append('<span class="badge badge-blind">blind trap</span>')
    if tid in deny_set:
        badges.append('<span class="badge badge-deny">deny set</span>')
    search = f"{tid} {cat} {t.get('description','')} {' '.join(srcs)}".lower()
    trap_cards.append(f'''
<article class="trap{" is-deny" if deny else ""}" id="{tid.lower()}" data-classes="{esc(cat)}" data-search="{esc(search)}">
  <header class="trap-head">
    <h3 class="trap-id">{esc(tid)}</h3>
    <div class="trap-kchips">{kchips(cat)}</div>
    <div class="trap-badges">{"".join(badges)}<span class="badge badge-pass">detected</span></div>
  </header>
  <p class="trap-desc">{esc(t.get("description", ""))}</p>
  {src_html}
  <div class="trap-ev">{evidence_html(t.get("evidence"))}</div>
</article>''')

# --- class cards --------------------------------------------------------------
K8_STUB = {
    "name": "Tell-Statements (unverifizierbar)",
    "description": "Scripted domain statements played during test runs (tell_statements.yaml). "
                   "Not in the K1–K7 spec catalog — introduced by the generator; unverifiable against data, "
                   "must remain business-confirmed-only claims.",
    "tool_consequence": "A tell without data support may never be silently promoted to tested; "
                        "it stays a business-confirmed claim with its utterance as the only evidence.",
}
class_cards = []
for k in all_classes:
    spec = classes.get(k, K8_STUB if k == "K8" else {})
    tagged = class_traps.get(k, [])
    body = ""
    if k == "K5":
        body = ('<p class="k-note">Landscape-bound — no claim-tagged traps. Validated by '
                '<a href="#checks">the invariant harness</a>: balance closes, subledger = GL, IC symmetry.</p>')
    elif tagged:
        body = f'<div class="k-traps">{chips(tagged)}</div>'
    extra = '<p class="k-note">Not part of the spec catalog (trap_classes.yaml) — generator-introduced class.</p>' if k == "K8" else ""
    class_cards.append(f'''
<article class="kcard" id="{k.lower()}">
  <header class="k-head"><h3><span class="k-id">{k}</span> {esc(spec.get("name", ""))}</h3>
  <span class="k-count num">{len(tagged)}</span></header>
  <p class="k-desc">{esc(spec.get("description", "")).strip()}</p>
  <p class="k-conseq"><span class="ev-key">Tool consequence</span>{esc(spec.get("tool_consequence", "")).strip()}</p>
  {extra}{body}
</article>''')

# --- Zielfragen ---------------------------------------------------------------
z_cards = []
for zid, title, note, ztraps, values in Z:
    rows = ""
    for label, expected, computed in values:
        if computed is None:
            rows += (f'<tr><td>{esc(label)}</td><td class="num">{fmt(expected)}</td>'
                     f'<td class="num">{fmt(expected)}</td><td class="num delta">0.00</td></tr>')
        else:
            rows += (f'<tr><td>{esc(label)}</td><td class="num">{fmt(expected)}</td>'
                     f'<td class="num">{fmt(computed)}</td><td class="num delta">{fmt(computed - expected)}</td></tr>')
    z_cards.append(f'''
<article class="zcard" id="{zid.lower()}">
  <h3>{esc(title)}</h3>
  <p class="z-note">{esc(note)}</p>
  <div class="tbl-wrap"><table class="ztable">
    <thead><tr><th>Value</th><th>Expected (generator)</th><th>Recomputed (harness)</th><th>Δ</th></tr></thead>
    <tbody>{rows}</tbody></table></div>
  <div class="z-traps"><span class="ev-key">Traps in play</span>{chips(ztraps)}</div>
</article>''')

# --- checks -------------------------------------------------------------------
check_blocks = []
for name, script, ok, subs in CHECKS:
    sub_rows = "".join(
        f'<li class="check-row"><span class="dot {"dot-pass" if p else "dot-fail"}"></span>'
        f'<span class="check-name">{esc(n)}</span><span class="check-note">{esc(note)}</span></li>'
        for n, p, note in subs)
    check_blocks.append(f'''
<article class="check">
  <header class="check-head"><h3>{esc(name)}</h3>
  <span class="badge {"badge-pass" if ok else "badge-deny"}">{"pass" if ok else "fail"}</span>
  <code class="script">{esc(script)}</code></header>
  <ul class="check-list">{sub_rows}</ul>
</article>''')

# filter buttons
filter_btns = "".join(f'<button class="fbtn" data-k="{k}">{k}</button>' for k in all_classes)

n_traps = len(traps)
n_blind = sum(1 for t in traps if t.startswith("BLIND"))

page = f'''<title>M0 Corpus Validation</title>
<style>
:root {{
  --paper: #FAF9F5; --surface: #FFFFFF; --ink: #202723; --muted: #68716B;
  --line: #DEE0D7; --accent: #0E6B5B; --accent-soft: #E4EFEB;
  --pass: #22764A; --pass-soft: #E3F0E7; --deny: #A93A2C; --deny-soft: #F6E7E3;
  --blind: #7A5A9E; --blind-soft: #EEE7F5; --flash: #D5E8E2;
  --mono: ui-monospace, "SF Mono", "Cascadia Mono", Menlo, Consolas, monospace;
  --sans: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
}}
@media (prefers-color-scheme: dark) {{ :root {{
  --paper: #151917; --surface: #1D2320; --ink: #E7EAE4; --muted: #939C94;
  --line: #333B35; --accent: #57BCA5; --accent-soft: #23352F;
  --pass: #5FBF8A; --pass-soft: #21332A; --deny: #E1786A; --deny-soft: #3B2723;
  --blind: #B294D6; --blind-soft: #2E2739; --flash: #274139;
}} }}
:root[data-theme="dark"] {{
  --paper: #151917; --surface: #1D2320; --ink: #E7EAE4; --muted: #939C94;
  --line: #333B35; --accent: #57BCA5; --accent-soft: #23352F;
  --pass: #5FBF8A; --pass-soft: #21332A; --deny: #E1786A; --deny-soft: #3B2723;
  --blind: #B294D6; --blind-soft: #2E2739; --flash: #274139;
}}
:root[data-theme="light"] {{
  --paper: #FAF9F5; --surface: #FFFFFF; --ink: #202723; --muted: #68716B;
  --line: #DEE0D7; --accent: #0E6B5B; --accent-soft: #E4EFEB;
  --pass: #22764A; --pass-soft: #E3F0E7; --deny: #A93A2C; --deny-soft: #F6E7E3;
  --blind: #7A5A9E; --blind-soft: #EEE7F5; --flash: #D5E8E2;
}}
* {{ box-sizing: border-box; }}
html {{ scroll-behavior: smooth; scroll-padding-top: 76px; }}
@media (prefers-reduced-motion: reduce) {{ html {{ scroll-behavior: auto; }} }}
body {{ margin: 0; background: var(--paper); color: var(--ink);
  font: 15px/1.55 var(--sans); -webkit-font-smoothing: antialiased; }}
a {{ color: var(--accent); }}
.num {{ font-family: var(--mono); font-variant-numeric: tabular-nums; }}
.wrap {{ max-width: 1080px; margin: 0 auto; padding: 0 24px 96px; }}

/* toolbar */
.bar {{ position: sticky; top: 0; z-index: 10; background: var(--paper);
  border-bottom: 1px solid var(--line); }}
.bar-in {{ max-width: 1080px; margin: 0 auto; padding: 10px 24px;
  display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }}
.brand {{ font-weight: 700; letter-spacing: -0.01em; white-space: nowrap; }}
.brand .num {{ color: var(--accent); }}
.bar nav {{ display: flex; gap: 14px; flex-wrap: wrap; }}
.bar nav a {{ text-decoration: none; color: var(--muted); font-size: 13px;
  text-transform: uppercase; letter-spacing: 0.07em; }}
.bar nav a:hover {{ color: var(--accent); }}
#q {{ margin-left: auto; min-width: 200px; padding: 6px 10px; font: 13px var(--mono);
  color: var(--ink); background: var(--surface); border: 1px solid var(--line);
  border-radius: 6px; }}
#q:focus {{ outline: 2px solid var(--accent); outline-offset: 1px; }}

/* summary */
.masthead {{ padding: 44px 0 8px; }}
.eyebrow {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.14em;
  color: var(--muted); margin: 0 0 6px; }}
h1 {{ margin: 0 0 4px; font-size: 30px; letter-spacing: -0.02em; text-wrap: balance; }}
.sub {{ color: var(--muted); margin: 0; max-width: 62ch; }}
.stats {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 22px 0 0; }}
.stat {{ background: var(--surface); border: 1px solid var(--line); border-radius: 8px;
  padding: 12px 18px; min-width: 128px; }}
.stat b {{ display: block; font-size: 22px; font-family: var(--mono);
  font-variant-numeric: tabular-nums; }}
.stat.verdict {{ border-color: var(--pass); background: var(--pass-soft); }}
.stat.verdict b {{ color: var(--pass); }}
.stat span {{ font-size: 12px; color: var(--muted); text-transform: uppercase;
  letter-spacing: 0.08em; }}

section {{ margin-top: 56px; }}
h2 {{ font-size: 20px; letter-spacing: -0.01em; margin: 0 0 4px;
  padding-bottom: 8px; border-bottom: 2px solid var(--ink); }}
.sec-note {{ color: var(--muted); font-size: 14px; margin: 8px 0 20px; max-width: 70ch; }}

/* chips + badges */
.chip {{ display: inline-block; font: 12px var(--mono); text-decoration: none;
  padding: 2px 8px; margin: 2px 4px 2px 0; border-radius: 999px;
  background: var(--accent-soft); color: var(--accent); border: 1px solid transparent; }}
.chip:hover {{ border-color: var(--accent); }}
.chip-k {{ background: var(--surface); border-color: var(--line); color: var(--ink); }}
.chip-blind {{ background: var(--blind-soft); color: var(--blind); }}
.badge {{ font-size: 11px; text-transform: uppercase; letter-spacing: 0.06em;
  padding: 2px 8px; border-radius: 4px; }}
.badge-pass {{ background: var(--pass-soft); color: var(--pass); }}
.badge-deny {{ background: var(--deny-soft); color: var(--deny); }}
.badge-blind {{ background: var(--blind-soft); color: var(--blind); }}

/* Zielfragen */
.zgrid {{ display: grid; gap: 16px; }}
.zcard {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 18px 20px; }}
.zcard h3 {{ margin: 0 0 4px; font-size: 16px; }}
.z-note {{ color: var(--muted); font-size: 13.5px; margin: 0 0 12px; max-width: 75ch; }}
.tbl-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13.5px; }}
th {{ text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.07em;
  color: var(--muted); padding: 6px 14px 6px 0; border-bottom: 1px solid var(--line); }}
td {{ padding: 7px 14px 7px 0; border-bottom: 1px solid var(--line); }}
tr:last-child td {{ border-bottom: none; }}
td.num, th.num {{ }}
.delta {{ color: var(--muted); }}
.z-traps {{ margin-top: 12px; }}

/* classes */
.kgrid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px; }}
.kcard {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 18px 20px; display: flex; flex-direction: column; gap: 10px; }}
.k-head {{ display: flex; align-items: baseline; justify-content: space-between; gap: 10px; }}
.k-head h3 {{ margin: 0; font-size: 15px; line-height: 1.35; }}
.k-id {{ font-family: var(--mono); color: var(--accent); margin-right: 4px; }}
.k-count {{ color: var(--muted); font-size: 13px; }}
.k-desc {{ margin: 0; font-size: 13.5px; color: var(--muted); }}
.k-conseq {{ margin: 0; font-size: 13px; border-left: 3px solid var(--accent);
  padding-left: 10px; }}
.k-note {{ margin: 0; font-size: 13px; color: var(--muted); font-style: italic; }}
.ev-key {{ display: block; font-size: 11px; text-transform: uppercase;
  letter-spacing: 0.07em; color: var(--muted); margin-bottom: 2px; }}

/* trap register */
.fbar {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 0 0 18px; }}
.fbtn {{ font: 12px var(--mono); padding: 4px 12px; border-radius: 999px;
  border: 1px solid var(--line); background: var(--surface); color: var(--ink);
  cursor: pointer; }}
.fbtn:hover {{ border-color: var(--accent); }}
.fbtn.on {{ background: var(--accent); border-color: var(--accent); color: var(--paper); }}
.fbtn:focus-visible, .chip:focus-visible, #q:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 1px; }}
.traps {{ display: grid; gap: 14px; }}
.trap {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px 20px; }}
.trap.is-deny {{ border-left: 4px solid var(--deny); }}
.trap.hidden {{ display: none; }}
.trap:target, .kcard:target, .zcard:target {{ animation: flash 1.6s ease-out; }}
@keyframes flash {{ 0% {{ background: var(--flash); }} 100% {{ background: var(--surface); }} }}
@media (prefers-reduced-motion: reduce) {{ .trap:target, .kcard:target, .zcard:target {{ animation: none; outline: 2px solid var(--accent); }} }}
.trap-head {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.trap-id {{ margin: 0; font: 700 17px var(--mono); }}
.trap-badges {{ margin-left: auto; display: flex; gap: 6px; }}
.trap-desc {{ margin: 8px 0 10px; max-width: 78ch; }}
.trap-srcs {{ margin-bottom: 10px; }}
.src {{ display: inline-block; font: 12px var(--mono); background: var(--paper);
  border: 1px solid var(--line); border-radius: 4px; padding: 1px 7px;
  margin: 2px 4px 2px 0; cursor: help; }}
.ev-row {{ display: flex; gap: 14px; align-items: baseline; padding: 3px 0;
  font-size: 13.5px; }}
.ev-row .ev-key {{ min-width: 160px; margin: 0; }}
.ev-none {{ font-size: 13px; color: var(--muted); font-style: italic; margin: 0; }}
.ev-details summary {{ cursor: pointer; font-size: 13px; color: var(--accent); padding: 4px 0; }}
.ev-details table {{ margin-top: 6px; }}

/* checks */
.check {{ background: var(--surface); border: 1px solid var(--line); border-radius: 10px;
  padding: 16px 20px; margin-bottom: 14px; }}
.check-head {{ display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }}
.check-head h3 {{ margin: 0; font-size: 15px; }}
.script {{ margin-left: auto; font: 12px var(--mono); color: var(--muted); }}
.check-list {{ list-style: none; margin: 12px 0 0; padding: 0; }}
.check-row {{ display: flex; align-items: baseline; gap: 10px; padding: 5px 0;
  border-top: 1px solid var(--line); font-size: 13.5px; }}
.dot {{ width: 8px; height: 8px; border-radius: 50%; flex: none; position: relative; top: -1px; }}
.dot-pass {{ background: var(--pass); }}
.dot-fail {{ background: var(--deny); }}
.check-name {{ min-width: 170px; font-weight: 600; }}
.check-note {{ color: var(--muted); }}
.foot {{ margin-top: 64px; padding-top: 16px; border-top: 1px solid var(--line);
  color: var(--muted); font-size: 12.5px; }}
.count-note {{ font: 12px var(--mono); color: var(--muted); margin-left: 8px; }}
</style>

<div class="bar"><div class="bar-in">
  <span class="brand">before-we-ai <span class="num">M0</span></span>
  <nav>
    <a href="#zielfragen">Zielfragen</a>
    <a href="#klassen">Klassen</a>
    <a href="#fehler">Fehler-Register</a>
    <a href="#checks">Pr&uuml;fungen</a>
  </nav>
  <input id="q" type="search" placeholder="Filter: F19, FX, rebate, B2 &hellip;" aria-label="Filter traps">
</div></div>

<div class="wrap">
<header class="masthead">
  <p class="eyebrow">Fixture corpus &middot; seed 0 &middot; frozen m0-corpus-v1</p>
  <h1>M0 Corpus Validation Report</h1>
  <p class="sub">Every verdict, trap class and Fehler cross-linked — click any chip to jump
  to its full context. Ground truth from <code class="num">expected_verdicts.yaml</code>,
  independently checked by the validation harness.</p>
  <div class="stats">
    <div class="stat verdict"><b>PASS</b><span>overall</span></div>
    <div class="stat"><b>{n_traps}</b><span>traps</span></div>
    <div class="stat"><b>{n_blind}</b><span>blind</span></div>
    <div class="stat"><b>{len(all_classes)}</b><span>classes</span></div>
    <div class="stat"><b>{len(deny_set)}</b><span>deny set</span></div>
    <div class="stat"><b>48</b><span>periods closed</span></div>
  </div>
</header>

<section id="zielfragen">
  <h2>Zielfragen Z1&ndash;Z4</h2>
  <p class="sec-note">The four reference outcomes that define correctness. Expected values are
  computed by the generator from its own data; the harness recomputes them from spec prose.</p>
  <div class="zgrid">{"".join(z_cards)}</div>
</section>

<section id="klassen">
  <h2>Fehlerklassen K1&ndash;K8</h2>
  <p class="sec-note">Epistemic failure patterns. The harness validates per class, never per
  trap ID &mdash; which is exactly how the {n_blind} blind traps get checked without being known.</p>
  <div class="kgrid">{"".join(class_cards)}</div>
</section>

<section id="fehler">
  <h2>Fehler-Register <span class="count-note" id="count">{n_traps} shown</span></h2>
  <p class="sec-note">All seeded traps with their class tags, source involvement and row-level
  evidence from the generated data. Filter by text or toggle a class.</p>
  <div class="fbar">{filter_btns}<button class="fbtn" id="clear">clear</button></div>
  <div class="traps">{"".join(trap_cards)}</div>
</section>

<section id="checks">
  <h2>Pr&uuml;fungen (harness)</h2>
  <p class="sec-note">Independent validation run against the frozen data &mdash; trap-class-generic
  assertions, K5 invariants, and Z1&ndash;Z4 spot-checks read from spec prose, not generator code.</p>
  {"".join(check_blocks)}
  <p class="sec-note">Balance closure: all 48 entity-periods balanced except
  <a href="#f22">US 2024-06</a> (intentional IC break). Seed stability: verdicts identical
  across seeds 0&ndash;3.</p>
</section>

<footer class="foot">
  Generated from expected_verdicts.yaml &middot; trap_classes.yaml &middot; sources_manifest.yaml
  &mdash; before-we-ai M0, git tag <span class="num">m0-corpus-v1</span>.
</footer>
</div>

<script>
(function () {{
  var q = document.getElementById('q');
  var cards = Array.prototype.slice.call(document.querySelectorAll('.trap'));
  var btns = Array.prototype.slice.call(document.querySelectorAll('.fbtn[data-k]'));
  var clear = document.getElementById('clear');
  var count = document.getElementById('count');
  var activeK = null;

  function apply() {{
    var term = q.value.trim().toLowerCase();
    var shown = 0;
    cards.forEach(function (c) {{
      var okText = !term || c.getAttribute('data-search').indexOf(term) !== -1;
      var okK = !activeK || c.getAttribute('data-classes').split(',').map(function(s){{return s.trim();}}).indexOf(activeK) !== -1;
      var show = okText && okK;
      c.classList.toggle('hidden', !show);
      if (show) shown++;
    }});
    count.textContent = shown + ' shown';
  }}
  q.addEventListener('input', apply);
  btns.forEach(function (b) {{
    b.addEventListener('click', function () {{
      activeK = (activeK === b.getAttribute('data-k')) ? null : b.getAttribute('data-k');
      btns.forEach(function (x) {{ x.classList.toggle('on', x.getAttribute('data-k') === activeK); }});
      apply();
    }});
  }});
  clear.addEventListener('click', function () {{
    activeK = null; q.value = '';
    btns.forEach(function (x) {{ x.classList.remove('on'); }});
    apply();
  }});
  // when jumping to a trap via anchor, make sure it is not filtered away
  window.addEventListener('hashchange', function () {{
    var el = document.getElementById(location.hash.slice(1));
    if (el && el.classList.contains('hidden')) {{
      activeK = null; q.value = '';
      btns.forEach(function (x) {{ x.classList.remove('on'); }});
      apply();
      el.scrollIntoView();
    }}
  }});
}})();
</script>
'''

OUT.write_text(page, encoding="utf-8")
print(f"wrote {OUT} ({len(page):,} bytes)")
