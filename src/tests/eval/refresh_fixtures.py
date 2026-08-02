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

# The corpus project construction is owner-facing support, not test code
# (validation/support/) — this tool is run as a script, so it says where.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from validation.support.corpus import FIXTURES, DOMAIN_GUIDE_FILE, build_corpus_project  # noqa: E402

from before_we_ai.documents import read_documents
from before_we_ai.llm import (
    ask,
    hypothesize,
    interpret_documents,
    load_domain_guide,
    propose_mappings,
)
from before_we_ai.llm.client import AnthropicClient
from before_we_ai.llm.v2_bind import plan_checks
from before_we_ai.store import ProjectStore

# Must stay byte-identical to DEMO_QUESTION in the offline corpus suite —
# the drift guard rebuilds the request input from it.
DEMO_QUESTION = "Can these files reliably produce actual P&L by entity and month?"

# The corpus' K8 statements — the same file the walkthrough's 5b beat reads.
TELL_STATEMENTS = (Path(__file__).resolve().parents[2]
                   / "corpus" / "data" / "tell_statements.yaml")


def still_answers_its_input(entry: dict, scenario: str) -> bool:
    """True when the fixture on disk already answers exactly this call.

    A recorded answer goes stale when its input or its prompt moves, and
    those are the only two reasons to replace it. Rewriting a fixture whose
    hashes both still match swaps a known answer for a fresh one and moves
    the corpus baseline for nothing — and the baseline is what every pinned
    number in the walkthrough is measured against.
    """
    path = FIXTURES / f"{entry['contract']}__{scenario}.json"
    if not path.exists():
        return False
    current = json.loads(path.read_text(encoding="utf-8"))
    return (current.get("input_sha256") == entry["input_sha256"]
            and current.get("system_sha256") == entry["system_sha256"])


def write_fixture_from_log(log_ref: str, scenario_override: str | None = None,
                           only_drifted: bool = False) -> Path | None:
    entry = json.loads(Path(log_ref).read_text(encoding="utf-8"))
    if entry["outcome"] == "failed":
        raise SystemExit(
            f"refusing to record a fixture from a failed call ({log_ref})"
        )
    # The fixture must hold the FULL-batch text. A "repair" attempt is
    # item-scoped (positional splice) and can never stand in for the batch —
    # recording it would replay a 4-item answer as the whole run. So take the
    # last non-repair attempt; the offline replay re-runs the same semantic
    # checks and skips whatever stayed broken.
    full_attempts = [a for a in entry["attempts"] if a.get("kind") != "repair"]
    response_text = full_attempts[-1]["raw_text"]
    if entry["outcome"] == "partial":
        print(f"  NOTE: recording a partial answer — offline replays will "
              f"skip the same items (see {Path(log_ref).name})")
    repair = next((a for a in entry["attempts"] if a.get("kind") == "repair"), None)
    if repair and repair.get("items_accepted"):
        print(f"  WARNING: the live repair spliced "
              f"{repair['items_accepted']} corrected item(s) the offline "
              f"replay cannot reproduce — downstream fixtures may misalign "
              f"(claim labels shift); consider re-running the refresh")
    scenario = scenario_override or entry["scenario"]
    if only_drifted and still_answers_its_input(entry, scenario):
        return None
    path = FIXTURES / f"{entry['contract']}__{scenario}.json"
    path.write_text(json.dumps({
        "contract": entry["contract"],
        "scenario": scenario,
        "input_sha256": entry["input_sha256"],
        "system_sha256": entry["system_sha256"],
        "model": entry["model"],
        "recorded_at": Path(log_ref).name,
        "source_log": log_ref,
        "response_text": response_text,
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", metavar="DIR",
                        help="build the project here and keep it (default: temp)")
    parser.add_argument(
        "--downstream-only", action="store_true",
        help="keep the recorded request/V1/role answers and re-record only "
             "what depends on them (V2, V3). The upstream fixtures are "
             "self-consistent on their own; it is the downstream ones that "
             "go out of alignment, so this is the cheap fix for the usual "
             "case.")
    parser.add_argument(
        "--only-drifted", action="store_true",
        help="write a fixture only where the one on disk no longer answers "
             "its input or its prompt. The call still happens (batches are "
             "not separable), but a fixture that is still valid keeps its "
             "recorded answer instead of being swapped for a fresh one.")
    parser.add_argument(
        "--skip-v3", action="store_true",
        help="do not record the document contract. V3's inputs depend on "
             "which rule items are still open, so they survive most "
             "upstream changes — six calls not worth making blind.")
    args = parser.parse_args()

    workdir = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="refresh-"))
    client = AnthropicClient()
    roles = load_domain_guide(DOMAIN_GUIDE_FILE)

    if args.downstream_only:
        print("keeping the recorded request/V1/role answers")
    else:
        _record_upstream(workdir, client, roles)

    _record_downstream(workdir, client, roles,
                       only_drifted=args.only_drifted, skip_v3=args.skip_v3)
    if not args.keep:
        shutil.rmtree(workdir)


def _record_upstream(workdir: Path, client, roles) -> None:
    root = build_corpus_project(workdir / "project", offline=False)
    store = ProjectStore(root)

    print("request (frontier) ...")
    drafted = ask(root, DEMO_QUESTION, guide=roles, client=client, store=store,
             scenario="corpus")
    if drafted.failure:
        raise SystemExit(f"request failed twice: {drafted.failure} "
                         f"(log: {drafted.log_ref})")
    # No delta is the good answer: it means the guide's answer type already
    # carries what this question depends on.
    delta = len(drafted.required.items) if drafted.required else 0
    print(f"  answer type {drafted.request.answer_type!r}, {delta} delta "
          f"item{'s' if delta != 1 else ''}, {len(drafted.skipped)} skipped, "
          f"usage {drafted.usage}")
    print("  fixture:", write_fixture_from_log(drafted.log_ref).name)

    print("V1 hypotheses (frontier) ...")
    v1 = hypothesize(root, client=client, store=store, scenario="corpus")
    if v1.failure:
        raise SystemExit(f"V1 failed twice: {v1.failure} (log: {v1.log_ref})")
    print(f"  {len(v1.claims_created)} claims, {len(v1.skipped)} skipped, "
          f"usage {v1.usage}")
    print("  fixture:", write_fixture_from_log(v1.log_ref).name)

    print("role-binding proposals (frontier) ...")
    proposals = propose_mappings(root, roles=roles, client=client,
                                      store=store, scenario="corpus")
    if proposals.failure:
        raise SystemExit(f"role proposals failed twice: {proposals.failure}")
    print(f"  {len(proposals.claims_created)} candidates, "
          f"{len(proposals.skipped)} skipped, usage {proposals.usage}")
    print("  fixture:", write_fixture_from_log(proposals.log_ref).name)

    shutil.rmtree(root)


def _record_downstream(workdir: Path, client, roles, only_drifted: bool = False,
                       skip_v3: bool = False) -> None:
    """Record against the state the OFFLINE replay produces, not the
    state the live run happens to be in.

    They differ whenever an upstream call needed an item-scoped repair:
    the repair is spliced live, while the replay re-runs the semantic
    checks on the full recorded batch instead, and the claim set comes
    out different. Every downstream input is built from that claim set,
    so a V2 fixture recorded against the live store answers an input the
    replay can never rebuild — which is the drift the guard then reports
    for ever, with no way to fix it but this.
    """
    print("replaying the recorded answers offline, to record the rest "
          "against what CI will see ...")
    root = build_corpus_project(workdir / "project", offline=True)
    store = ProjectStore(root)
    ask(root, DEMO_QUESTION, guide=roles, store=store, scenario="corpus")
    hypothesize(root, store=store, scenario="corpus")
    propose_mappings(root, roles=roles, store=store, scenario="corpus")
    store = ProjectStore(root)

    print("V2 check binding ...")
    v2 = plan_checks(root, client=client, store=store, scenario="corpus")
    if v2.failures:
        raise SystemExit(f"V2 failed twice: {v2.failures}")
    print(f"  {len(v2.check_plans_created)} checks, {len(v2.unbindable)} unbindable, "
          f"{len(v2.semantic_only)} semantic-only, usage {v2.usage}")
    for log_ref in v2.log_refs:
        written = write_fixture_from_log(log_ref, only_drifted=only_drifted)
        print("  fixture:", written.name if written
              else "unchanged — the recorded answer still fits its input")

    if skip_v3:
        print("skipping V3 (--skip-v3): its fixtures are pinned in "
              "test_documents_offline_corpus.py — run the suite to confirm "
              "they still hold")
        _closing_note()
        return

    # V3 last: it asks what rule items are still open, and that answer is
    # only right once the stages above have run. One call per document, so
    # one fixture per document — six of them on this corpus.
    print("V3 documents (frontier) ...")
    read_documents(root)
    v3 = interpret_documents(root, guide=roles, client=client,
                             store=ProjectStore(root), scenario="corpus")
    if v3.failures:
        raise SystemExit(f"V3 failed for {[d for d, _ in v3.failures]}")
    print(f"  {len(v3.documents_read)} documents, "
          f"{len(v3.claims_created)} claims, {v3.anchors} anchors, "
          f"{len(v3.links)} links, {len(v3.skipped)} refused, "
          f"usage {v3.usage}")
    for log_ref in v3.log_refs:
        written = write_fixture_from_log(log_ref, only_drifted=only_drifted)
        print("  fixture:", written.name if written
              else "unchanged — the recorded answer still fits its input")

    _record_statements(root, client, roles, only_drifted)
    _closing_note()


def _record_statements(root: Path, client, roles, only_drifted: bool) -> None:
    """The K8 statements — a person's knowledge, read like a document.

    Last, and after V3, because `tell` sends the rule items still open and
    that list is only right once everything that could settle one has run.
    One call per statement, and each gets its own scenario: the fixture key
    is contract + scenario + document, and every statement is the same
    "document", so a shared scenario would have them overwrite each other.
    """
    import yaml

    from before_we_ai.statements import tell
    from before_we_ai.store import ProjectStore

    spec = yaml.safe_load(TELL_STATEMENTS.read_text(encoding="utf-8"))
    print("tell statements (frontier) ...")
    for entry in spec["statements"]:
        report = tell(root, entry["text"], guide=roles, client=client,
                      store=ProjectStore(root),
                      scenario=f"corpus_{entry['id'].lower()}")
        if report.failure:
            raise SystemExit(f"tell failed for {entry['id']}: {report.failure}")
        print(f"  {entry['id']}: {len(report.claims_created)} claim(s), "
              f"parked={report.mirror.parked}")
        for log_ref in report.log_refs:
            written = write_fixture_from_log(log_ref, only_drifted=only_drifted)
            print("  fixture:", written.name if written
                  else "unchanged — the recorded answer still fits its input")


def _closing_note() -> None:
    print("\nFixtures refreshed. Run the offline suite (python -m pytest -q) —")
    print("the drift guard and the pinned pipeline assertions will tell you")
    print("what the new answers changed; review and commit the diff.")


if __name__ == "__main__":
    sys.exit(main())
