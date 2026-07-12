#!/usr/bin/env python3
"""Human-friendly reader for cache/llm_log/*.json.

    llm-log.sh                 list all logged calls of the walkthrough project
    llm-log.sh 2               show call #2 fully formatted (prompt, answer, errors)
    llm-log.sh v1              show the first call whose filename contains "v1"
    llm-log.sh --html out.html render every call into one browsable HTML page
    llm-log.sh --project DIR   read another project's logs (default:
                               validation/data/project)
"""

import argparse
import html
import json
import sys
from pathlib import Path

import yaml

DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "data" / "project"

# --- process guide -----------------------------------------------------------
# One comment per call kind, matching the walkthrough steps and the flow in
# docs/SIMPLE-README.md ("The big picture"): the AI guesses, the probes decide.


def guide_for(contract: str, scenario: str) -> str:
    if contract == "v1_hypotheses":
        return (
            "Walkthrough step 3 (V1) — the model's first job. Input: column "
            "profiles + candidate matrix (measured statistics, never raw rows). "
            "Output: hypotheses — proposed rules about THIS data ('the document "
            "number in the report references the general ledger'). Every "
            "accepted hypothesis becomes a claim with status 'inferred' — "
            "nothing here is verified yet.")
    if contract == "role_binding":
        return (
            "Walkthrough step 4 — casting call for the domain roles. Input: the "
            "role-pack definitions (human-written domain nouns) + profiles. "
            "Output: role-binding candidates ('this table could play the "
            "journal role'), each a claim with status 'inferred'. Competing "
            "candidates are wanted — the domain-law probes decide the election, "
            "not the model.")
    if contract == "v2_bind" and "roles" in scenario:
        return (
            "Walkthrough step 5 (V2), role batch — filling in the free "
            "variables of the domain laws. Each role-binding candidate gets a "
            "binding to its domain-law template (balance / subledger=GL / "
            "IC symmetry): which view, which columns. The model picks "
            "parameters from a closed catalog; it never writes SQL.")
    if contract == "v2_bind":
        return (
            "Walkthrough step 5 (V2), ordinary batch — a binding for each "
            "remaining claim: the fitting generic probe template + parameters "
            "from the closed catalog. 'template: null' answers are honest 'not "
            "testable with the current toolbox' — reported, never hidden.")
    return ""


# Core terms, matching the glossary in docs/SIMPLE-README.md — the guide
# boxes below use exactly these words and no synonyms.
GLOSSARY: list[tuple[str, str]] = [
    ("hypothesis", "one proposed rule, the model's raw output (V1); accepted "
     "ones become claims"),
    ("claim", "a rule about the data, stored with author and evidence — "
     "the 'index card'"),
    ("status", "inferred / tested / contradicted / unresolved / "
     "business-confirmed — always derived from evidence; the model's claims "
     "start at 'inferred' and the model cannot promote them"),
    ("role", "a domain noun a table/column can play (journal, subledger …); "
     "a role-binding candidate is a claim that a view plays a role"),
    ("domain-law template", "a conservation law as code (balance, "
     "subledger=GL, IC symmetry) — decides which candidate wins a role"),
    ("binding", "the assignment claim → probe template + parameters (V2); "
     "strictly validated, 'template: null' = not testable"),
    ("probe", "a deterministic SQL spot-check — with humans, the only path "
     "to a better status; runs in step 6, never inside a model call"),
    ("Fachfrage", "a drafted question to the humans when data alone cannot "
     "decide"),
]


GROWTH_NOTE = (
    "This log grows as the walkthrough progresses: steps 3, 4 and 5 talk to "
    "the model (one entry per call; retries and repairs live inside their "
    "entry as extra attempts). Steps 1–2 and 6–8 are deterministic and add "
    "nothing here — measuring and judging never involve the model.")


def domain_header(project: Path) -> str:
    """The declared domain inputs, rendered on top — what knowledge the
    model was given, beyond the measured statistics."""
    try:
        config = yaml.safe_load((project / "before-ai.yaml").read_text(encoding="utf-8"))
    except OSError:
        return "<p class='err'>no before-ai.yaml found — inputs not shown</p>"
    sources = config.get("sources") or []
    source_lines = "".join(
        f"<li><code>{html.escape(s['name'])}</code> ({html.escape(s['kind'])}) — "
        f"{html.escape(s['location'])}</li>" for s in sources)

    roles_html = "<p class='err'>no role pack declared (llm.roles_file)</p>"
    roles_path = (config.get("llm") or {}).get("roles_file")
    if roles_path:
        pack = yaml.safe_load(Path(roles_path).read_text(encoding="utf-8"))

        def _definition(spec) -> str:
            return spec.get("definition", "") if isinstance(spec, dict) else str(spec)

        def _decided(spec) -> str:
            return spec.get("decided_by", "") if isinstance(spec, dict) else ""

        role_items = "".join(
            f"<details><summary><code>{html.escape(name)}</code>"
            + (f" <i>decided_by: {html.escape(_decided(spec))}</i>" if _decided(spec) else "")
            + f"</summary><p>{html.escape(_definition(spec).strip())}</p></details>"
            for name, spec in pack.get("roles", {}).items())
        roles_html = (
            f"<p>domain <b>{html.escape(pack.get('domain', '?'))}</b>, "
            f"{len(pack.get('roles', {}))} roles — human-written definitions, "
            f"no system names; only the definitions enter prompts, decided_by is "
            f"the linted settlement path<br><code>{html.escape(str(roles_path))}</code></p>"
            f"{role_items}")

    try:
        from before_we_ai.probes.library import REGISTRY
        tagged = [(n, s) for n, s in REGISTRY.items() if s.domain]
        generic = len(REGISTRY) - len(tagged)
        law_items = "".join(
            f"<li><code>{html.escape(n)}</code> (domain {html.escape(s.domain)}) — "
            f"<code>probes/templates/{html.escape(s.file)}</code></li>"
            for n, s in tagged)
        laws_html = (
            f"<ul>{law_items}</ul><p>The other {generic} templates in the catalog "
            f"are generic data probes (reference check, duplicates, coverage …) — "
            f"they carry no domain knowledge and work in any domain.</p>")
    except ImportError:
        laws_html = "<p class='err'>probe registry not importable — activate the venv</p>"

    terms = "".join(
        f"<dt>{html.escape(term)}</dt><dd>{html.escape(text)}</dd>"
        for term, text in GLOSSARY)
    return (
        "<section class='domain'><h2>Core terms</h2>"
        "<p>The comments on the calls below use exactly these words "
        "(full glossary: docs/SIMPLE-README.md).</p>"
        f"<dl>{terms}</dl></section>"
        "<section class='domain'><h2>Domain knowledge &amp; declared inputs</h2>"
        "<p>Everything domain-specific enters through three declared inputs "
        "(docs/architecture.md 'Domain inputs'); the model additionally sees "
        "only measured statistics, never raw rows.</p>"
        f"<h3>1 · Raw data — the source list (human-authored)</h3><ul>{source_lines}</ul>"
        f"<h3>2 · Role pack — the domain nouns (data, human-curated)</h3>{roles_html}"
        f"<h3>3 · Domain-law templates — the guardians (code, developer-shipped)</h3>{laws_html}"
        f"<p class='note'>{html.escape(GROWTH_NOTE)}</p></section>")


def load_calls(project: Path) -> list[tuple[Path, dict]]:
    directory = project / "cache" / "llm_log"
    paths = sorted(directory.glob("*.json"))
    if not paths:
        sys.exit(f"no call logs in {directory}")
    return [(p, json.loads(p.read_text(encoding="utf-8"))) for p in paths]


def pretty_response(text: str) -> str:
    stripped = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    try:
        return json.dumps(json.loads(stripped), indent=2, ensure_ascii=False)
    except (json.JSONDecodeError, ValueError):
        return text


def describe_attempt(attempt: dict) -> str:
    """The two-tier retry made attempts unequal: say which kind this is."""
    kind = attempt.get("kind", "answer")
    if kind == "repair":
        sent = attempt.get("items_sent", "?")
        accepted = attempt.get("items_accepted")
        got = "discarded" if accepted is None else f"{accepted} accepted"
        return f"REPAIR of {sent} rejected item(s) — {got}"
    if kind == "retry":
        return "whole-call RETRY (nothing parsed)"
    return "first answer"


def tokens(usage: dict) -> str:
    if not usage:
        return "n/a (stub)"
    return f"{usage.get('input_tokens', 0):,} in / {usage.get('output_tokens', 0):,} out"


def list_calls(calls) -> None:
    print(f"{'#':>2} {'contract':14s} {'scenario':14s} {'outcome':10s} "
          f"{'att':>3s} {'tokens':>20s}  model")
    for i, (path, entry) in enumerate(calls, 1):
        usage: dict[str, int] = {}
        for attempt in entry["attempts"]:
            for k, v in attempt.get("usage", {}).items():
                usage[k] = usage.get(k, 0) + v
        print(f"{i:>2} {entry['contract']:14s} {entry['scenario']:14s} "
              f"{entry['outcome']:10s} {len(entry['attempts']):>3} "
              f"{tokens(usage):>20s}  {entry['model']}")
        print(f"   {path.name}")
    print("\nshow one call: llm-log.sh <#>   ·   all as HTML: llm-log.sh --html FILE")


def show_call(path: Path, entry: dict) -> None:
    bar = "─" * 78
    print(bar)
    print(f"{entry['contract']}  ·  scenario {entry['scenario']}  ·  "
          f"{entry['model']}  ·  provider {entry['provider']}")
    guide = guide_for(entry["contract"], entry["scenario"])
    if guide:
        print(f"WHAT THIS IS: {guide}")
    print(f"outcome: {entry['outcome'].upper()}"
          + (f"  ·  FAILURE: {entry['failure']}" if entry.get("failure") else ""))
    print(f"input sha256: {entry['input_sha256']}")
    print(f"trim notices: {entry.get('trim_notices') or 'none (nothing trimmed)'}")
    print(f"file: {path}")
    print(f"\n{bar}\nSYSTEM PROMPT ({len(entry['request']['system']):,} chars)\n{bar}")
    print(entry["request"]["system"])
    print(f"\n{bar}\nUSER INPUT ({len(entry['request']['user']):,} chars)\n{bar}")
    print(entry["request"]["user"])
    for i, attempt in enumerate(entry["attempts"], 1):
        print(f"\n{bar}\nATTEMPT {i}/{len(entry['attempts'])}  ·  "
              f"{describe_attempt(attempt)}  ·  "
              f"{tokens(attempt.get('usage', {}))}  ·  {attempt.get('ms', 0)} ms\n{bar}")
        errors = attempt.get("validation_errors") or []
        if errors:
            print(f"validation errors ({len(errors)}) — "
                  "fed back verbatim to the model:")
            for e in errors:
                print(f"  - {e}")
            print()
        print(pretty_response(attempt["raw_text"]))


def render_html(project: Path, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    calls = load_calls(project)
    blocks = []
    for i, (path, entry) in enumerate(calls, 1):
        attempts = []
        for j, attempt in enumerate(entry["attempts"], 1):
            errors = attempt.get("validation_errors") or []
            error_html = ("<p class='err'>validation errors:</p><ul>"
                          + "".join(f"<li>{html.escape(e)}</li>" for e in errors)
                          + "</ul>") if errors else ""
            attempts.append(
                f"<details><summary>attempt {j}/{len(entry['attempts'])}: "
                f"{html.escape(describe_attempt(attempt))} — "
                f"{html.escape(tokens(attempt.get('usage', {})))}"
                f"{' — HAD ERRORS' if errors else ''}</summary>"
                f"{error_html}<pre>{html.escape(pretty_response(attempt['raw_text']))}"
                f"</pre></details>")
        guide = guide_for(entry["contract"], entry["scenario"])
        guide_html = f"<p class='guide'>{html.escape(guide)}</p>" if guide else ""
        blocks.append(
            f"<section><h2>{i}. {html.escape(entry['contract'])} · "
            f"{html.escape(entry['scenario'])} · "
            f"<span class='{entry['outcome']}'>{entry['outcome'].upper()}</span></h2>"
            f"{guide_html}"
            f"<p>{html.escape(entry['model'])} · provider {entry['provider']} · "
            f"input sha <code>{entry['input_sha256'][:16]}…</code> · "
            f"trim: {html.escape(str(entry.get('trim_notices') or 'none'))}<br>"
            f"<code>{html.escape(path.name)}</code></p>"
            f"<details><summary>system prompt "
            f"({len(entry['request']['system']):,} chars)</summary>"
            f"<pre>{html.escape(entry['request']['system'])}</pre></details>"
            f"<details><summary>user input "
            f"({len(entry['request']['user']):,} chars)</summary>"
            f"<pre>{html.escape(entry['request']['user'])}</pre></details>"
            + "".join(attempts) + "</section>")
    out.write_text(
        "<meta charset='utf-8'><title>LLM calls</title><style>"
        "body{font-family:sans-serif;max-width:75em;margin:2em auto;line-height:1.5}"
        "pre{background:#f4f4f4;padding:1em;overflow-x:auto;white-space:pre-wrap}"
        "details{margin:.4em 0;border-left:3px solid #ccc;padding-left:1em}"
        "summary{cursor:pointer;font-weight:600}"
        ".err{color:#b00}.partial{color:#b60}.failed{color:#b00}"
        ".ok,.retried_ok,.repaired_ok{color:#080}section{border-bottom:1px solid #ddd;"
        "padding-bottom:1em}"
        ".guide{background:#eef4fb;border-left:3px solid #4a7db5;padding:.6em 1em}"
        ".domain{background:#fbf8ee;border:1px solid #e0d9b8;padding:0 1em 1em}"
        ".domain h3{margin-bottom:.2em}.note{color:#666;font-style:italic}"
        "dt{font-weight:600;margin-top:.4em}dd{margin-left:1.5em}</style>"
        "<h1>LLM calls — verbatim requests & answers</h1>"
        + domain_header(project)
        + "\n".join(blocks) + "\n",
        encoding="utf-8")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("call", nargs="?",
                        help="call number from the list, or a filename substring")
    parser.add_argument("--project", type=Path, default=DEFAULT_PROJECT)
    parser.add_argument("--html", metavar="FILE", type=Path,
                        help="render all calls into one HTML page")
    args = parser.parse_args()

    if args.html:
        print(render_html(args.project, args.html))
        return
    calls = load_calls(args.project)
    if args.call is None:
        list_calls(calls)
        return
    if args.call.isdigit():
        index = int(args.call)
        if not 1 <= index <= len(calls):
            sys.exit(f"call #{index} does not exist — there are {len(calls)} calls")
        show_call(*calls[index - 1])
        return
    for path, entry in calls:
        if args.call in path.name:
            show_call(path, entry)
            return
    sys.exit(f"no logged call matching {args.call!r}")


if __name__ == "__main__":
    main()
