"""Refresh the stub fixtures from real online runs — the anti-rot loop.

Runs the full contract pipeline against the frozen corpus with the real
Anthropic client (needs ANTHROPIC_API_KEY), then rewrites each fixture in
tests/fixtures/llm/ from the logged call: the recorded raw answer plus
the sha256 of the input it answered. Commit the diff — git shows exactly
what the model's answers became.

Usage (from src/, venv active, key in the environment):

    python tests/eval/refresh_fixtures.py [--keep DIR]
"""

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

from _corpus import FIXTURES, ROLES_FILE, build_corpus_project

from before_we_ai.llm import hypothesize, load_roles, propose_role_bindings
from before_we_ai.llm.client import AnthropicClient
from before_we_ai.llm.v2_bind import bind_probes
from before_we_ai.store import ProjectStore


def write_fixture_from_log(log_ref: str, scenario_override: str | None = None) -> Path:
    entry = json.loads(Path(log_ref).read_text(encoding="utf-8"))
    if entry["outcome"] not in ("ok", "retried_ok"):
        raise SystemExit(
            f"refusing to record a fixture from a {entry['outcome']} call "
            f"({log_ref}) — fix the run first"
        )
    scenario = scenario_override or entry["scenario"]
    path = FIXTURES / f"{entry['contract']}__{scenario}.json"
    path.write_text(json.dumps({
        "contract": entry["contract"],
        "scenario": scenario,
        "input_sha256": entry["input_sha256"],
        "model": entry["model"],
        "recorded_at": Path(log_ref).name,
        "source_log": log_ref,
        "response_text": entry["attempts"][-1]["raw_text"],
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", metavar="DIR",
                        help="build the project here and keep it (default: temp)")
    args = parser.parse_args()

    workdir = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="refresh-"))
    root = build_corpus_project(workdir / "project", offline=False)
    client = AnthropicClient()
    store = ProjectStore(root)
    roles = load_roles(ROLES_FILE)

    print("V1 hypotheses (frontier) ...")
    v1 = hypothesize(root, client=client, store=store, scenario="corpus")
    if v1.failure:
        raise SystemExit(f"V1 failed twice: {v1.failure} (log: {v1.log_ref})")
    print(f"  {len(v1.claims_created)} claims, {len(v1.skipped)} skipped, "
          f"usage {v1.usage}")
    print("  fixture:", write_fixture_from_log(v1.log_ref).name)

    print("role-binding proposals (frontier) ...")
    proposals = propose_role_bindings(root, roles=roles, client=client,
                                      store=store, scenario="corpus")
    if proposals.failure:
        raise SystemExit(f"role proposals failed twice: {proposals.failure}")
    print(f"  {len(proposals.claims_created)} candidates, "
          f"{len(proposals.skipped)} skipped, usage {proposals.usage}")
    print("  fixture:", write_fixture_from_log(proposals.log_ref).name)

    print("V2 probe binding ...")
    v2 = bind_probes(root, client=client, store=store, scenario="corpus")
    if v2.failures:
        raise SystemExit(f"V2 failed twice: {v2.failures}")
    print(f"  {len(v2.probes_created)} probes, {len(v2.unbindable)} unbindable, "
          f"{len(v2.semantic_only)} semantic-only, usage {v2.usage}")
    for log_ref in v2.log_refs:
        print("  fixture:", write_fixture_from_log(log_ref).name)

    if not args.keep:
        shutil.rmtree(workdir)
    print("\nFixtures refreshed. Run the offline suite (python -m pytest -q) —")
    print("the drift guard and the pinned pipeline assertions will tell you")
    print("what the new answers changed; review and commit the diff.")


if __name__ == "__main__":
    sys.exit(main())
