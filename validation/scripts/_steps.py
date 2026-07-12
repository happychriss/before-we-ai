#!/usr/bin/env python3
"""Stage driver behind the numbered validation scripts.

Each stage runs exactly one pipeline step against the walkthrough project
at validation/data/project and prints a human summary of what it produced,
with pointers to the files that hold the full detail. Product code is only
imported, never duplicated; corpus setup comes from tests/eval/_corpus.py.
"""

import argparse
import html
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
VALIDATION = SCRIPTS.parent
REPO = VALIDATION.parent
DATA = VALIDATION / "data"
PROJECT = DATA / "project"
REPORT = DATA / "report"
SCENARIO = "corpus"  # shared with fixtures and the eval tools

sys.path.insert(0, str(REPO / "src" / "tests" / "eval"))  # _corpus (test-side)
import _corpus  # noqa: E402
from _corpus import ROLES_FILE, build_corpus_project  # noqa: E402


def _corpus_file() -> str:
    return _corpus.__file__

from before_we_ai.engine import run_ready  # noqa: E402
from before_we_ai.llm import (  # noqa: E402
    bind_probes,
    hypothesize,
    load_roles,
    propose_role_bindings,
    resolve_roles,
)
from before_we_ai.model import Actor  # noqa: E402
from before_we_ai.model.objects import RoleBindingClaim  # noqa: E402
from before_we_ai.profile.candidates import load_matrix  # noqa: E402
from before_we_ai.sources import open_catalog  # noqa: E402
from before_we_ai.store import ProjectStore  # noqa: E402


def section(title: str) -> None:
    print(f"\n== {title} " + "=" * max(0, 60 - len(title)))


def inputs(*lines: str) -> None:
    """What drove this step — named files, never a summary. Every stage
    opens with this: an output you cannot trace to its input is not
    evidence, it is an assertion."""
    section("INPUT — what this step reads")
    for line in lines:
        print(f"  {line}")


LLM_INPUT_NOTE = (
    "the exact bytes sent to the model are logged verbatim (with their "
    "sha256)\n           -> read them: llm-log.sh <#>")


def need_project() -> ProjectStore:
    if not PROJECT.is_dir():
        sys.exit("no walkthrough project yet — run 1-scan.sh first")
    return ProjectStore(PROJECT)


def clip(text: str, width: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _offline() -> bool:
    import yaml
    config = yaml.safe_load((PROJECT / "before-ai.yaml").read_text(encoding="utf-8"))
    return bool((config.get("llm") or {}).get("offline"))


# ---------------------------------------------------------------- stages


def stage_scan(args) -> None:
    if PROJECT.exists():
        sys.exit(f"{PROJECT} already exists — run 0-reset.sh for a clean start")
    mode = "ONLINE — steps 3-5 will make real model calls (needs " \
        "ANTHROPIC_API_KEY)" if args.online else \
        "OFFLINE — steps 3-5 will replay the recorded real answers"
    print(f"building walkthrough project: {PROJECT}\n"
          f"scan itself is deterministic and never calls an LLM; this run "
          f"writes the\nLLM config for the later steps into before-ai.yaml: "
          f"{mode}")

    from _corpus import SOURCES  # the list that drives everything below
    inputs(
        f"source list ({len(SOURCES)} sources), declared in "
        f"{Path(_corpus_file()).relative_to(REPO)}",
        "  (the product never discovers files: init_project writes "
        "`sources: []` and a\n   human fills it in — here the corpus harness "
        "does that for you)",
        "",
        *[f"  {s['name']:22s} {s['kind']:7s} "
          f"{Path(s['location']).relative_to(REPO)}" for s in SOURCES],
    )
    unlisted = sorted(
        p.name for p in (REPO / "src" / "corpus" / "data").iterdir()
        if p.is_file() and p.suffix in {".pdf", ".csv", ".xlsx"}
        and not any(Path(s["location"]).name == p.name for s in SOURCES))
    if unlisted:
        print(f"\n  NOT listed (present in the corpus, invisible to this run): "
              f"{', '.join(unlisted)}")
        print("  PDFs carry the policy traps; the document pipeline is M5 — a "
              "pdf source is\n  fingerprinted only (sources/attach.py), so it "
              "yields no views and no evidence.")

    build_corpus_project(PROJECT, offline=not args.online)
    store = ProjectStore(PROJECT)
    print(f"\n  resolved config written to: "
          f"{(PROJECT / 'before-ai.yaml').relative_to(REPO)} "
          f"(canonical `sources:` for this project)")

    section("views in the catalog (cache/analysis.duckdb)")
    con = open_catalog(PROJECT)
    try:
        views = [r[0] for r in con.execute(
            "select view_name from duckdb_views() where not internal "
            "order by view_name").fetchall()]
        for view in views:
            count = con.execute(f'select count(*) from "{view}"').fetchone()[0]
            print(f"  {view:45s} {count:>8,} rows")
    finally:
        con.close()

    section("normalization declarations (evidence/, actor=system)")
    by_kind = Counter((e.type.value, e.actor.value) for e in store.evidence.values())
    for (etype, actor), n in sorted(by_kind.items()):
        print(f"  {n:3d} × {etype} by {actor}")
    for e in list(store.evidence.values())[:3]:
        payload = getattr(e, "payload", None)
        print(f"  sample: {clip(json.dumps(payload, ensure_ascii=False, default=str))}")

    section("claims")
    print(f"  {len(store.claims)}  (scan must create ZERO claims — "
          "false promotion impossible by construction)")
    print(f"\nfull detail: {PROJECT}/evidence/  ·  profiles: {PROJECT}/profiles/")
    print("next: 2-matrix.sh")


def stage_matrix(args) -> None:
    need_project()
    inputs(
        "the catalog views built by step 1 (cache/analysis.duckdb) — the scan "
        "already\n  computed this matrix; nothing new is read here",
        f"column profiles: {(PROJECT / 'profiles').relative_to(REPO)}/",
        f"matrix as data: {(PROJECT / 'profiles' / 'candidate_matrix.json').relative_to(REPO)}",
    )
    matrix = load_matrix(PROJECT)
    section("candidate matrix — measured value overlap, table:table")
    print(f"  pairs examined: {matrix['pairs_examined']}   "
          f"candidates kept (containment ≥ {matrix['threshold']}): "
          f"{len(matrix['candidates'])}")
    for warning in matrix["warnings"]:
        print(f"  WARNING: {warning}")
    print("\n  top candidates by containment "
          "(measured overlap only — the matrix never judges):")
    rows = sorted(matrix["candidates"], key=lambda c: -c["containment"])
    print(f"  {'left':42s} {'right':42s} {'overlap':>7s} {'cont.':>6s} {'jacc.':>6s}")
    for c in rows[: args.top]:
        print(f"  {c['left']:42s} {c['right']:42s} {c['overlap']:>7} "
              f"{c['containment']:>6} {c['jaccard']:>6}")
    print(f"\nfull table: {PROJECT}/profiles/candidate_matrix.md "
          f"(+ .json, per-column profiles alongside)")
    print("next: 3-hypotheses.sh")


def _print_call_report(report, store: ProjectStore) -> None:
    if report.failure:
        print(f"  CALL FAILED after retry: {report.failure}")
        return
    print(f"  created: {len(report.claims_created)}   "
          f"deduped: {report.claims_deduped}   skipped: {len(report.skipped)}   "
          f"retries: {report.retries}   usage: {report.usage or 'n/a (stub)'}")
    for statement, reason in report.skipped:
        print(f"  skipped: {clip(statement, 60)}\n           -> {clip(reason)}")
    print(f"  verbatim call log: {report.log_ref}  (read with llm-log.sh)")


def stage_hypotheses(args) -> None:
    store = need_project()
    inputs(
        "column profiles + candidate matrix, rendered deterministically "
        "(llm/inputs.py:\n  build_profile_context) — the model sees measured "
        "statistics, never raw rows",
        "system prompt: llm/prompts.py:V1_SYSTEM + the output schema",
        f"answers: {'recorded fixtures in src/tests/fixtures/llm/' if _offline() else 'live model calls'}",
        LLM_INPUT_NOTE,
    )
    report = hypothesize(PROJECT, store=store, scenario=SCENARIO)
    section("V1 — hypotheses from profiles (frontier tier)")
    _print_call_report(report, store)
    created = [store.claims[cid] for cid in report.claims_created]
    if created:
        section("predicates proposed")
        for name, n in Counter(
                c.predicate.name for c in created if c.predicate).most_common():
            print(f"  {n:3d} × {name}")
        section("sample claims (all must be inferred, created_by=ai)")
        for claim in created[: args.top]:
            print(f"  [{claim.status.value}] ({claim.predicate.name}) "
                  f"{clip(claim.statement, 80)}")
    print(f"\nfull detail: {PROJECT}/claims/")
    print("next: 4-role-proposals.sh")


def stage_role_proposals(args) -> None:
    store = need_project()
    roles = load_roles(ROLES_FILE)
    inputs(
        f"role definitions ({len(roles.names)} roles, domain '{roles.domain}'): "
        f"{ROLES_FILE.relative_to(REPO)}",
        "  (data, not code — the product stays domain-agnostic; this file is "
        "deliberately\n   clean: the corpus generator's roles.yaml names a decoy "
        "and must never be used)",
        "  roles: " + ", ".join(roles.names),
        "profiles + candidate matrix (llm/inputs.py: build_role_context)",
        LLM_INPUT_NOTE,
    )
    report = propose_role_bindings(PROJECT, roles=roles, store=store,
                                   scenario=SCENARIO)
    section("role-binding proposals (frontier tier)")
    _print_call_report(report, store)
    section("candidates per role (competing candidates are wanted — "
            "probes decide, not the model)")
    role_claims = [c for c in store.claims.values()
                   if isinstance(c, RoleBindingClaim)]
    for role in roles.names:
        mine = [c for c in role_claims if c.role == role]
        print(f"  {role:15s} {len(mine)} candidate(s)")
        for c in mine:
            print(f"      [{c.status.value}] {clip(', '.join(c.binding.values()), 75)}")
    print("next: 5-bind-probes.sh")


def stage_bind(args) -> None:
    store = need_project()
    if store.probes:
        # Offline fixture answers are keyed to the FIRST run's claim labels;
        # after binding, the unbound set (and so the labels) shifts and the
        # recorded answers would land on the wrong claims.
        sys.exit(f"{len(store.probes)} probes already exist — binding ran. "
                 "For a fresh pass run 0-reset.sh and start over.")
    unbound = [c for c in store.claims.values() if c.created_by is Actor.AI]
    inputs(
        f"the {len(unbound)} AI claims from steps 3+4 (labelled c1..cN — ULIDs "
        f"never enter\n  a prompt, so the input stays byte-stable)",
        "the probe template catalog: probes/library.py REGISTRY, rendered by "
        "llm/prompts.py:\n  render_template_docs — only templates admissible "
        "for a claim's predicate are offered",
        "view schemas + profile digests (llm/inputs.py: build_binding_context)",
        LLM_INPUT_NOTE,
    )
    report = bind_probes(PROJECT, store=store, scenario=SCENARIO)
    section("V2 — probe binding (roles: frontier · ordinary claims: mid tier)")
    print(f"  probes created: {len(report.probes_created)}   "
          f"deduped: {report.probes_deduped}   retries: {report.retries}   "
          f"usage: {report.usage or 'n/a (stub)'}")
    print(f"  unbindable (honest template=null): {len(report.unbindable)}   "
          f"semantic-only (never sent): {len(report.semantic_only)}   "
          f"skipped (validation): {len(report.skipped)}   "
          f"unanswered: {len(report.unanswered)}   "
          f"call failures: {len(report.failures)}")
    for ref in report.log_refs:
        print(f"  verbatim call log: {ref}")

    section("templates bound")
    probes = [store.probes[pid] for pid in report.probes_created]
    for name, n in Counter(p.template for p in probes).most_common():
        print(f"  {n:3d} × {name}")

    if report.skipped:
        section("skipped bindings (model output rejected by validation)")
        # skipped carries the prompt label (c1..cN), not a store claim id —
        # the label is what the model answered with; see the call log.
        for label, reason in report.skipped:
            print(f"  answer for claim label {label}\n      -> {clip(reason)}")
    if report.unbindable:
        section("unbindable — model answered template=null (stay inferred)")
        for cid, reason in report.unbindable[: args.top]:
            print(f"  {clip(store.claims[cid].statement, 55)}\n"
                  f"      -> {clip(reason or '', 85)}")
        if len(report.unbindable) > args.top:
            print(f"  … {len(report.unbindable) - args.top} more")
    if report.semantic_only:
        section("semantic-only — no admissible template exists (T7 class here)")
        for cid in report.semantic_only:
            print(f"  {clip(store.claims[cid].statement, 85)}")
    print(f"\nfull detail: {PROJECT}/probes/")
    print("next: 6-run-probes.sh")


def stage_run(args) -> None:
    store = need_project()
    inputs(
        f"the {len(store.probes)} probes from step 5: "
        f"{(PROJECT / 'probes').relative_to(REPO)}/ (template + params, as YAML)",
        "their SQL: probes/templates/*.sql.j2 — rendered per probe, the "
        "rendered SQL is\n  kept on the evidence record",
        "the data: cache/analysis.duckdb (browse it with db.sh / db-export.sh)",
        "NO LLM is involved from here on — verdicts are deterministic SQL",
    )
    con = open_catalog(PROJECT)
    try:
        report = run_ready(store, con)
    finally:
        con.close()
    store = ProjectStore(PROJECT)  # reload -> statuses derived from evidence

    section("engine sweep")
    print(f"  probes executed: {len(report.executed)}   "
          f"skipped: {len(report.skipped)}")
    for probe_id, reason in report.skipped:
        print(f"  skipped {probe_id}: {clip(reason)}")
    for verdict, n in Counter(
            e.verdict.value for e in report.executed if e.verdict).most_common():
        print(f"  {n:3d} × verdict {verdict}")

    section("AI claim statuses after the sweep (derived, never set)")
    ai = [c for c in store.claims.values() if c.created_by is Actor.AI]
    for status, n in Counter(c.status.value for c in ai).most_common():
        print(f"  {n:3d} × {status}")

    section("role verdicts — the invariants decided")
    for c in sorted((c for c in ai if isinstance(c, RoleBindingClaim)),
                    key=lambda c: (c.role, c.id)):
        print(f"  {c.role:15s} [{c.status.value:13s}] "
              f"{clip(', '.join(c.binding.values()), 60)}")

    section("false-promotion audit (must always hold)")
    bad = [c for c in ai
           if c.status.value != "inferred"
           and not any(store.evidence[eid].actor is Actor.PROBE
                       for eid in c.evidence_ids if eid in store.evidence)]
    print("  CLEAN — every promoted AI claim traces to probe evidence"
          if not bad else
          "\n".join(f"  !! {c.id} [{c.status.value}] {c.statement}" for c in bad))
    print(f"\nfull detail: {PROJECT}/evidence/  ·  exception sets: "
          f"{PROJECT}/cache/probe_runs/")
    print("next: 7-resolve-roles.sh")


def stage_resolve(args) -> None:
    store = need_project()
    roles = load_roles(ROLES_FILE)
    inputs(
        f"the same role definitions as step 4: {ROLES_FILE.relative_to(REPO)}",
        "the derived statuses of the role claims after step 6 — a role with "
        "candidates but\n  none reaching `tested` has lost, and becomes a "
        "question instead of a silent discard",
        "NO LLM: this is pure bookkeeping over statuses",
    )
    cards = resolve_roles(store, roles)
    section("role resolution — lost roles become Fachfragen, never discards")
    if not cards:
        print("  no new questions (already resolved? resolution is idempotent)")
    for card in cards:
        print(f"  FACHFRAGE: {card.question}")
        for cid in card.claim_ids:
            c = store.claims[cid]
            print(f"    rests on [{c.status.value}] {clip(c.statement, 70)}")
    section("all open questions in the project")
    store = ProjectStore(PROJECT)
    for card in store.questions.values():
        print(f"  - {clip(card.question, 100)}")
    print(f"\nfull detail: {PROJECT}/questions/")
    print("next: 8-collect.sh")


def stage_collect(args) -> None:
    need_project()
    REPORT.mkdir(parents=True, exist_ok=True)

    subprocess.run([sys.executable, "-m", "claim_viewer", str(PROJECT),
                    "-o", str(REPORT / "claims.html")], check=True)

    import llm_log
    llm_log.render_html(PROJECT, REPORT / "llm_calls.html")

    matrix_md = PROJECT / "profiles" / "candidate_matrix.md"
    if matrix_md.is_file():
        shutil.copy2(matrix_md, REPORT / "candidate_matrix.md")
    recall_md = DATA / "recall" / "project" / "cache" / "eval" / "seeded_recall.md"
    if recall_md.is_file():
        shutil.copy2(recall_md, REPORT / "seeded_recall.md")

    links = [
        ("claims.html", "Claim viewer — every claim with status, evidence and questions"),
        ("llm_calls.html", "LLM calls — verbatim prompts, answers, retries, errors"),
        ("candidate_matrix.md", "Candidate matrix — measured table:table value overlap"),
    ]
    if (REPORT / "seeded_recall.md").is_file():
        links.append(("seeded_recall.md",
                      "Seeded-Recall report (from recall.sh)"))
    links.append(("../project/", "Raw project files — claims/ probes/ evidence/ questions/ as YAML"))
    items = "\n".join(
        f'<li><a href="{href}">{href.rstrip("/")}</a> — {html.escape(text)}</li>'
        for href, text in links)
    (REPORT / "index.html").write_text(
        "<meta charset='utf-8'><title>M4 validation</title>"
        "<style>body{font-family:sans-serif;max-width:50em;margin:3em auto;"
        "line-height:1.6}</style>"
        "<h1>M4 validation — collected artifacts</h1>"
        f"<ul>\n{items}\n</ul>"
        "<p>Walkthrough guide: <code>validation/README.md</code></p>\n",
        encoding="utf-8")

    section("collected")
    for path in sorted(REPORT.iterdir()):
        print(f"  {path}")
    print(f"\nopen in a browser / VS Code: {REPORT / 'index.html'}")


def stage_viewer(args) -> None:
    need_project()
    REPORT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "claim_viewer", str(PROJECT),
                    "-o", str(REPORT / "claims.html")], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=[
        "scan", "matrix", "hypotheses", "role-proposals", "bind", "run",
        "resolve", "collect", "viewer"])
    parser.add_argument("--online", action="store_true",
                        help="scan only: configure real model calls "
                             "(needs ANTHROPIC_API_KEY for stages 3-5)")
    parser.add_argument("--top", type=int, default=15,
                        help="how many rows to show in list sections")
    args = parser.parse_args()
    {
        "scan": stage_scan,
        "matrix": stage_matrix,
        "hypotheses": stage_hypotheses,
        "role-proposals": stage_role_proposals,
        "bind": stage_bind,
        "run": stage_run,
        "resolve": stage_resolve,
        "collect": stage_collect,
        "viewer": stage_viewer,
    }[args.stage](args)


if __name__ == "__main__":
    main()
