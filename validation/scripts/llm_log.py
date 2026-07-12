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

DEFAULT_PROJECT = Path(__file__).resolve().parents[1] / "data" / "project"


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
        blocks.append(
            f"<section><h2>{i}. {html.escape(entry['contract'])} · "
            f"{html.escape(entry['scenario'])} · "
            f"<span class='{entry['outcome']}'>{entry['outcome'].upper()}</span></h2>"
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
        ".ok,.retried_ok{color:#080}section{border-bottom:1px solid #ddd;"
        "padding-bottom:1em}</style>"
        "<h1>LLM calls — verbatim requests & answers</h1>"
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
