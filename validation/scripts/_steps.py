#!/usr/bin/env python3
"""Stage driver behind the numbered validation scripts.

Each stage runs exactly one pipeline step against the walkthrough project
at validation/data/project and prints a human summary of what it produced,
with pointers to the files that hold the full detail. Product code is only
imported, never duplicated; corpus setup comes from validation/support/.
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
SCENARIO = "finance"  # shared with fixtures and the eval tools
# byte-identical to DEMO_QUESTION in the offline corpus suite and in
# tests/eval/refresh_fixtures.py — the drift guard rebuilds its input from it
DEMO_QUESTION = "Can these files reliably produce actual P&L by entity and month?"
_ORIGIN = {"text": "in running text", "table": "in a ruled table",
           "chart": "inside a chart"}

sys.path.insert(0, str(REPO))  # validation.support — owner-facing, not test code
from validation.support import corpus as corpus_support  # noqa: E402
from validation.support.corpus import (  # noqa: E402
    CORPUS,
    DOMAIN_GUIDE_FILE,
    build_corpus_project,
)


def _corpus_file() -> str:
    return corpus_support.__file__

from before_we_ai import read_documents, scan  # noqa: E402
from before_we_ai.engine import run_ready  # noqa: E402
from before_we_ai.llm import (  # noqa: E402
    ask,
    interpret_documents,
    plan_checks,
    hypothesize,
    load_domain_guide,
    propose_mappings,
    resolve_mappings,
)
from before_we_ai.llm.domain_guide import settled_slots  # noqa: E402
from before_we_ai.llm.v3_documents import open_rule_items  # noqa: E402
from before_we_ai.checks.library import REGISTRY  # noqa: E402
from before_we_ai.core import Actor, ClaimStatus, EvidenceType  # noqa: E402
from before_we_ai.core.objects import MappingClaim  # noqa: E402
from before_we_ai.profile.candidates import load_matrix  # noqa: E402
from before_we_ai.readiness import (  # noqa: E402
    assemble,
    confirm_classification,
    evaluate_request,
    guide_label,
)
from before_we_ai.sources import open_catalog  # noqa: E402
from before_we_ai.statements import tell  # noqa: E402
from before_we_ai.store import ProjectStore  # noqa: E402

# The corpus' own K8 statements, read from the frozen file rather than
# retyped here — a walkthrough that quotes its inputs from memory is a
# walkthrough that can drift from them silently.
TELL_STATEMENTS = CORPUS / "tell_statements.yaml"


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
        sys.exit("no walkthrough project yet — run 0-inputs.sh first")
    return ProjectStore(PROJECT)


def collect(next_step: str = "") -> None:
    """Rebuild every artifact and the index — run at the end of every stage.

    Paths are fixed, so a browser tab left open on ``index.html`` shows the
    report growing as you walk. That is the point of running it every time
    rather than once at the end: the interesting thing about this pipeline
    is what each stage adds, and you can only see that if you look between
    the stages.
    """
    REPORT.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "readiness_report", str(PROJECT),
                    "-o", str(REPORT / "readiness.html")],
                   check=True, stdout=subprocess.DEVNULL)

    if (PROJECT / "cache" / "llm_log").is_dir():
        import llm_log
        llm_log.render_html(PROJECT, REPORT / "llm_calls.html")

    matrix_md = PROJECT / "profiles" / "candidate_matrix.md"
    if matrix_md.is_file():
        shutil.copy2(matrix_md, REPORT / "candidate_matrix.md")
    recall_md = DATA / "recall" / "project" / "cache" / "eval" / "seeded_recall.md"
    if recall_md.is_file():
        shutil.copy2(recall_md, REPORT / "seeded_recall.md")

    links = [("readiness.html",
              "Readiness report — the request, the inputs, what was measured, "
              "proposed, tested, still open, and the verdict")]
    if (REPORT / "llm_calls.html").is_file():
        links.append(("llm_calls.html",
                      "LLM calls — verbatim prompts, answers, retries, errors"))
    if (REPORT / "candidate_matrix.md").is_file():
        links.append(("candidate_matrix.md",
                      "Candidate matrix — measured table:table value overlap"))
    if (REPORT / "seeded_recall.md").is_file():
        links.append(("seeded_recall.md", "Seeded-Recall report (from recall.sh)"))
    links.append(("../project/",
                  "Raw project files — answers/ claims/ checks/ evidence/ "
                  "questions/ as YAML"))
    items = "\n".join(
        f'<li><a href="{href}">{href.rstrip("/")}</a> — {html.escape(text)}</li>'
        for href, text in links)
    (REPORT / "index.html").write_text(
        "<meta charset='utf-8'><title>before-we-ai — validation</title>"
        "<style>body{font-family:sans-serif;max-width:50em;margin:3em auto;"
        "line-height:1.6}</style>"
        "<h1>Validation artifacts</h1>"
        "<p>Rebuilt after every stage — reload to watch the report grow.</p>"
        f"<ul>\n{items}\n</ul>"
        "<p>Walkthrough guide: <code>validation/README.md</code></p>\n",
        encoding="utf-8")

    print(f"\nreport rebuilt — reload {REPORT / 'index.html'}")
    if next_step:
        print(f"next: {next_step}")


def clip(text: str, width: int = 90) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def _offline() -> bool:
    import yaml
    config = yaml.safe_load((PROJECT / "before-ai.yaml").read_text(encoding="utf-8"))
    return bool((config.get("llm") or {}).get("offline"))


# ---------------------------------------------------------------- stages


def _staleness(report) -> None:
    """What re-reading the sources cost the readings taken before it.

    Printed on a first run too, saying plainly that there was nothing to
    outrun. A line that only appears when something is wrong teaches a
    reader to skim past the place where it would have appeared.
    """
    section("what moved under us since the last read")
    if not report.flagged:
        print("  nothing — every reading on record still describes the data "
              "it was taken from")
        return
    print(f"  {len(report.flagged)} reading(s) no longer describe the data:")
    for _record_id, reason in report.flagged[:5]:
        print(f"    {reason}")
    if len(report.flagged) > 5:
        print(f"    … and {len(report.flagged) - 5} more")
    if report.claims_rederived:
        print(f"  {len(report.claims_rederived)} claim(s) fell back to what "
              "the remaining evidence supports")
    if report.questions_flagged:
        print(f"  {len(report.questions_flagged)} question card(s) now say "
              "their finding is out of date")
    print("  run the checks again (stage 4) to settle them against the data "
          "as it is now")


def stage_scan(args) -> None:
    """Stage 2a — the data describes itself. No model involved."""
    need_project()
    inputs(
        f"the sources declared in stage 1: "
        f"{(PROJECT / 'before-ai.yaml').relative_to(REPO)}",
        "NO LLM: ingestion, canonicalization and profiling are deterministic",
    )
    result = scan(PROJECT)
    store = ProjectStore(PROJECT)

    _staleness(result.stale)

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
    collect("2b-measure-matrix.sh")


def stage_matrix(args) -> None:
    need_project()
    inputs(
        "the catalog views built by 2a (cache/analysis.duckdb) — the scan "
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
    collect("2c-measure-documents.sh")



def stage_documents(args) -> None:
    """2c — read the declared documents. Measurement, so: no claims."""
    need_project()
    inputs(
        "the documents declared in before-ai.yaml (kind: pdf) — the files "
        "themselves,\n  read page by page",
        f"document profiles land beside the column ones: "
        f"{(PROJECT / 'profiles').relative_to(REPO)}/",
        f"the passage index is disposable cache: "
        f"{(PROJECT / 'cache' / 'analysis.duckdb').relative_to(REPO)}",
    )
    result = read_documents(PROJECT)
    _staleness(result.stale)
    if result.revalidated:
        print(f"  {result.revalidated} quote(s) survived the edit word for word "
              "and were anchored again")
    section("documents read — what is in them, not what they mean")
    if not result.profiles_written:
        print("  no documents declared for this project")
        collect("3a-propose-hypotheses.sh")
        return
    print(f"  documents: {result.profiles_written}   pages: {result.pages}   "
          f"passages: {result.chunks}")
    print("\n  where the passages sit on the page (worked out from the page "
          "itself,\n  never from what the text says):")
    for kind in ("text", "table", "chart"):
        count = result.kinds.get(kind, 0)
        if count:
            print(f"    {count:>3} {_ORIGIN[kind]}")
    store = ProjectStore(PROJECT)
    section("per document")
    for profile in sorted(store.documents.values(), key=lambda d: d.document):
        origins = ", ".join(
            f"{n} {_ORIGIN[k]}" for k, n in sorted(profile.kinds.items()) if n
        )
        noun = "passage " if profile.chunk_count == 1 else "passages"
        print(f"  {profile.document:44s} {profile.pages:>2} p  "
              f"{profile.chunk_count:>3} {noun}   {origins}")
    charted = result.kinds.get("chart", 0)
    if charted:
        verb = "sit" if charted != 1 else "sits"
        print(f"\n  {charted} passage{'s' if charted != 1 else ''} {verb} "
              "inside a figure. A number printed only in a\n  chart cannot be checked "
              "against anything else on the page, so it is never\n  allowed to "
              "corroborate a claim — watch for that in stage 3d.")
    print(f"\n  claims created: {len(store.claims)} — reading a document is "
          "measurement.\n  What it says is proposed one stage later, where "
          "nothing can promote itself.")
    collect("3a-propose-hypotheses.sh")


def stage_read_documents(args) -> None:
    """3d — V3 reads the passages and proposes what it finds."""
    store = need_project()
    guide = load_domain_guide(DOMAIN_GUIDE_FILE)
    open_items = open_rule_items(store, guide)
    inputs(
        "the passages from 2c, one call per document — a document that fits "
        "is sent\n  whole; retrieval bounds the input, it never filters it",
        "the rule items still open, so the model knows what is being looked "
        "for:\n    " + ("\n    ".join(open_items) or "(none)"),
        f"the domain guide: {DOMAIN_GUIDE_FILE}",
    )
    report = interpret_documents(PROJECT, guide=guide, store=store,
                                 scenario=SCENARIO)
    section("what the documents were read to say")
    print(f"  documents read: {len(report.documents_read)}   "
          f"claims proposed: {len(report.claims_created)}   "
          f"anchors: {report.anchors}   deduped: {report.claims_deduped}")
    for document, reason in report.failures:
        print(f"  CALL FAILED for {document}: {clip(reason)}")
    for chunk_id, reason in report.skipped:
        print(f"  refused: {chunk_id}\n           -> {clip(reason)}")
    for note in report.narrowed:
        print(f"  NOTE: {note}")

    after = ProjectStore(PROJECT)
    section("every proposal, and the words it was read from")
    for record in sorted(after.evidence.values(),
                         key=lambda e: (e.created_at, e.id)):
        if record.type is not EvidenceType.DOCUMENT_ANCHOR:
            continue
        payload = record.payload or {}
        claim = after.claims.get(record.claim_id or "")
        print(f"  {clip(claim.statement if claim else '?', 70)}")
        print(f"    read from {payload.get('source')} p.{payload.get('page')}, "
              f"{_ORIGIN.get(str(payload.get('kind')), '?')}")
        print(f"    \u201c{clip(str(payload.get('quote', '')), 76)}\u201d")

    section("what was linked, and what was refused")
    if report.links:
        for ref, claim_id in report.links:
            claim = after.claims.get(claim_id)
            print(f"  linked: {ref}")
            print(f"    -> {clip(claim.statement if claim else claim_id, 70)}")
            print("       the link routes the question; the claim still has "
                  "to earn its status")
    else:
        print("  nothing was linked")
    if report.questions:
        print()
        for question in report.questions:
            print(f"  refused, and asked instead:\n    {clip(question, 76)}")

    promoted = [c for c in after.claims.values()
                if c.status is not ClaimStatus.PROPOSED]
    print(f"\n  claims this stage promoted: {len(promoted)} — documents "
          "propose, they never settle.")
    collect("4-test.sh")


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
        section("sample claims (all must be proposed, created_by=ai)")
        for claim in created[: args.top]:
            print(f"  [{claim.status.value}] ({claim.predicate.name}) "
                  f"{clip(claim.statement, 80)}")
    print(f"\nfull detail: {PROJECT}/claims/")
    collect("3b-propose-mappings.sh")


def stage_mappings(args) -> None:
    store = need_project()
    roles = load_domain_guide(DOMAIN_GUIDE_FILE)
    inputs(
        f"domain guide ({len(roles.objects)} business objects, "
        f"{len(roles.names) - len(roles.objects)} fields, domain "
        f"'{roles.domain}'): {DOMAIN_GUIDE_FILE.relative_to(REPO)}",
        "  (data, not code — the product stays domain-agnostic; this file is "
        "deliberately\n   clean: the corpus generator's roles.yaml names a decoy "
        "and must never be used)",
        "  objects and their fields, flattened for the prompt exactly as the "
        "model sees them:\n   " + ", ".join(roles.names),
        "profiles + candidate matrix (llm/inputs.py: build_role_context)",
        LLM_INPUT_NOTE,
    )
    report = propose_mappings(PROJECT, roles=roles, store=store,
                                   scenario=SCENARIO)
    section("role-binding proposals (frontier tier)")
    _print_call_report(report, store)
    section("candidates per role (competing candidates are wanted — "
            "checks decide, not the model)")
    role_claims = [c for c in store.claims.values()
                   if isinstance(c, MappingClaim)]
    for role in roles.names:
        mine = [c for c in role_claims if c.role == role]
        owner = roles.owner_of(role)
        label = f"  {role}" if owner else role  # fields sit under their object
        print(f"  {label:15s} {len(mine)} candidate(s)")
        for c in mine:
            print(f"      [{c.status.value}] {clip(', '.join(c.binding.values()), 75)}")
    collect("3c-propose-plans.sh")


def stage_plans(args) -> None:
    store = need_project()
    if store.checks:
        # The rule, stated once so it stops being folklore: the stages that
        # only measure or judge (2a, 2c, 4) are re-runnable by design —
        # staleness depends on it. The stages that *propose* are not, when
        # they are replayed offline: a recording answers the input it was
        # recorded for, and after binding the unbound set has shifted, so
        # the recorded answers would land on the wrong claims. This is a
        # property of replay, not of the engine — run online and 3c binds
        # whatever is unbound at the time.
        sys.exit(f"{len(store.checks)} checks already exist — binding ran.\n"
                 "Offline, a proposal stage runs once: its recorded answers "
                 "belong to that\none input. Measurement and checks (2a, 2c, "
                 "4) may be re-run as often as you\nlike — that is the "
                 "staleness loop. For a fresh pass: reset.sh and start over.")
    unbound = [c for c in store.claims.values() if c.created_by is Actor.AI]
    n_roles = sum(isinstance(c, MappingClaim) for c in unbound)
    inputs(
        f"the {len(unbound)} AI claims already in the store: "
        f"{len(unbound) - n_roles} hypotheses from 3a\n  "
        f"+ {n_roles} mapping candidates from 3b "
        f"(labelled c1..cN — ULIDs never enter\n  a prompt, so the input stays "
        f"byte-stable)",
        "the check definition catalog: checks/library.py REGISTRY, rendered by "
        "llm/prompts.py:\n  render_template_docs — only templates admissible "
        "for a claim's predicate are offered",
        "view schemas + profile digests (llm/inputs.py: build_binding_context)",
        LLM_INPUT_NOTE,
    )
    report = plan_checks(PROJECT, store=store, scenario=SCENARIO)
    section("V2 — check binding (roles: frontier · ordinary claims: mid tier)")
    print(f"  checks created: {len(report.check_plans_created)}   "
          f"deduped: {report.check_plans_deduped}   retries: {report.retries}   "
          f"usage: {report.usage or 'n/a (stub)'}")
    print(f"  unbindable (honest template=null): {len(report.unbindable)}   "
          f"semantic-only (never sent): {len(report.semantic_only)}   "
          f"skipped (validation): {len(report.skipped)}   "
          f"unanswered: {len(report.unanswered)}   "
          f"call failures: {len(report.failures)}")
    for ref in report.log_refs:
        print(f"  verbatim call log: {ref}")

    section("templates bound")
    checks = [store.checks[pid] for pid in report.check_plans_created]
    for name, n in Counter(p.template for p in checks).most_common():
        print(f"  {n:3d} × {name}")

    if report.skipped:
        section("skipped bindings (model output rejected by validation)")
        # skipped carries the prompt label (c1..cN), not a store claim id —
        # the label is what the model answered with; see the call log.
        for label, reason in report.skipped:
            print(f"  answer for claim label {label}\n      -> {clip(reason)}")
    if report.unbindable:
        section("unbindable — model answered template=null (stay proposed)")
        for cid, reason in report.unbindable[: args.top]:
            print(f"  {clip(store.claims[cid].statement, 55)}\n"
                  f"      -> {clip(reason or '', 85)}")
        if len(report.unbindable) > args.top:
            print(f"  … {len(report.unbindable) - args.top} more")
    if report.semantic_only:
        section("semantic-only — no admissible template exists (T7 class here)")
        for cid in report.semantic_only:
            print(f"  {clip(store.claims[cid].statement, 85)}")
    print(f"\nfull detail: {PROJECT}/checks/")
    collect("3d-propose-documents.sh")


def stage_test(args) -> None:
    store = need_project()
    inputs(
        f"the {len(store.checks)} checks from 3c: "
        f"{(PROJECT / 'checks').relative_to(REPO)}/ (template + params, as YAML)",
        "their SQL: checks/templates/*.sql.j2 — rendered per check, the "
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
    print(f"  checks executed: {len(report.executed)}   "
          f"skipped: {len(report.skipped)}")
    for check_plan_id, reason in report.skipped:
        print(f"  skipped {check_plan_id}: {clip(reason)}")
    for verdict, n in Counter(
            e.verdict.value for e in report.executed if e.verdict).most_common():
        print(f"  {n:3d} × verdict {verdict}")

    section("AI claim statuses after the sweep (derived, never set)")
    ai = [c for c in store.claims.values() if c.created_by is Actor.AI]
    for status, n in Counter(c.status.value for c in ai).most_common():
        print(f"  {n:3d} × {status}")

    section("role verdicts — the invariants decided")
    for c in sorted((c for c in ai if isinstance(c, MappingClaim)),
                    key=lambda c: (c.role, c.id)):
        print(f"  {c.role:15s} [{c.status.value:13s}] "
              f"{clip(', '.join(c.binding.values()), 60)}")

    section("false-promotion audit (must always hold)")
    bad = [c for c in ai
           if c.status.value != "proposed"
           and not any(store.evidence[eid].actor is Actor.CHECK
                       for eid in c.evidence_ids if eid in store.evidence)]
    print("  CLEAN — every promoted AI claim traces to check evidence"
          if not bad else
          "\n".join(f"  !! {c.id} [{c.status.value}] {c.statement}" for c in bad))
    print(f"\nfull detail: {PROJECT}/evidence/  ·  exception sets: "
          f"{PROJECT}/cache/check_runs/")
    print()
    collect("5a-clarify.sh")


def stage_clarify(args) -> None:
    store = need_project()
    roles = load_domain_guide(DOMAIN_GUIDE_FILE)
    inputs(
        f"the same role definitions as 3b: {DOMAIN_GUIDE_FILE.relative_to(REPO)}",
        "the derived statuses of the role claims after stage 4 — a role with "
        "candidates but\n  none reaching `test-supported` has lost, and becomes a "
        "question instead of a silent discard",
        "NO LLM: this is pure bookkeeping over statuses",
    )
    cards = resolve_mappings(store, roles)
    section("role resolution — lost roles become Clarification questions, never discards")
    if not cards:
        print("  no new questions (already resolved? resolution is idempotent)")
    for card in cards:
        print(f"  CLARIFICATION: {card.question}")
        for cid in card.claim_ids:
            c = store.claims[cid]
            print(f"    rests on [{c.status.value}] {clip(c.statement, 70)}")
    section("slots answered by their object's law — asked nothing, because the "
            "passing check already consumed the column")
    answered = {}
    for name in roles.objects:
        answered.update(settled_slots(store, roles, name))
    if not answered:
        print("  none — no domain law passed on an object with slot fields")
    for field, column in sorted(answered.items()):
        print(f"  {field:15s} {column}  "
              f"(via the {roles.objects[roles.owner_of(field)].decided_by} law)")
    section("all open questions in the project")
    store = ProjectStore(PROJECT)
    for card in store.questions.values():
        print(f"  - {clip(card.question, 100)}")
    print(f"\nfull detail: {PROJECT}/questions/")
    print()
    collect("5b-tell.sh")


def stage_tell(args) -> None:
    """Stage 5b — what a person knows that no file contains.

    The other half of clarification. 5a asks the questions the data
    raises; this takes the answers a person volunteers before being
    asked, and it is the only stage where a human puts *content* in.

    The order inside `tell` is the whole design: the words are stored
    verbatim first, then V3 reads them exactly as it reads a PDF — same
    quote validation, same anchoring, same inability to promote. So a
    statement nothing can be structured from is parked, never lost, and
    a statement that does yield a claim yields a *proposed* one carrying
    a testimonial: somebody said this, which is not the same as it being
    true.
    """
    import yaml

    store = need_project()
    roles = load_domain_guide(DOMAIN_GUIDE_FILE)
    spec = yaml.safe_load(TELL_STATEMENTS.read_text(encoding="utf-8"))
    inputs(
        f"the statements a person volunteered: "
        f"{TELL_STATEMENTS.relative_to(REPO)} (corpus class K8)",
        "the rule items still open — the same list 3d showed the documents,\n"
        "  so a person and a policy are read against the same question",
        "the domain guide, for the vocabulary the statement is read in",
        "answers: recorded fixtures, one per statement "
        "(v3_documents__finance_<id>__statements)",
    )

    section("what was said, and what the system made of it")
    for entry in spec["statements"]:
        scenario = f"{SCENARIO}_{entry['id'].lower()}"
        report = tell(PROJECT, entry["text"], guide=roles,
                      store=ProjectStore(PROJECT), scenario=scenario)
        print(f"\n  {entry['id']} — a person says:")
        print(f"    “{entry['text']}”")
        if report.failure:
            print(f"    !! the contract failed: {report.failure}")
            continue
        mirror = report.mirror
        if mirror.parked:
            print("    nothing could be structured from it — stored verbatim "
                  "as a searchable note,")
            print("    carrying no weight. It stays visible in the decision "
                  "log rather than")
            print("    surviving only as a note nobody thinks to search for.")
        for claim_id in report.claims_created:
            claim = ProjectStore(PROJECT).claims[claim_id]
            print(f"    [{claim.status.value}] {clip(claim.statement, 66)}")
        print("\n    the mirror — what it now asks the person who spoke:")
        for line in _wrap(mirror.question(), 66):
            print(f"      {line}")

    section("why none of this promoted anything")
    print("  A testimonial records that somebody said a thing, not that the")
    print("  thing is true — so every claim above is still `proposed`. The")
    print("  scope question is the mirror loop, and it is not politeness:")
    print("  `confirm_claim` REFUSES a testimonial-backed claim without an")
    print("  explicit scope, because 'this is how it works' without saying")
    print("  for whom is the assumption this product exists to stop.")
    print(f"\nfull detail: {PROJECT}/evidence/  ·  {PROJECT}/questions/")
    print()
    collect("6-readiness.sh")


def _wrap(text: str, width: int) -> list[str]:
    import textwrap

    return textwrap.wrap(text, width) or [""]


def stage_request(args) -> None:
    """Stage 1 — the question, and what it requires.

    The frame opens here: the question bounds discovery, so what it does not
    depend on nobody has to know. Stage 6 closes the frame with the verdict.

    It comes *after* the declared inputs and not before, because the request
    contract reads the domain guide — a question cannot be decomposed
    against a vocabulary nobody has chosen yet.
    """
    store = need_project()
    roles = load_domain_guide(DOMAIN_GUIDE_FILE)
    inputs(
        f"the business question, as a human asked it: {DEMO_QUESTION!r}",
        f"the domain vocabulary: {DOMAIN_GUIDE_FILE.relative_to(REPO)}\n"
        "  (definitions only — the request contract sees no profiles: whether "
        "the data can\n  serve the question is the rest of the pipeline's job, "
        "and answering it here\n  would be the model deciding)",
        "system prompt: llm/prompts.py:REQUEST_SYSTEM + the output schema",
        f"answers: {'recorded fixtures in src/tests/fixtures/llm/' if _offline() else 'live model calls'}",
        LLM_INPUT_NOTE,
    )
    report = ask(PROJECT, DEMO_QUESTION, guide=roles, store=store,
                 scenario=SCENARIO)
    section("the request — one business question, classified")
    if report.failure:
        print(f"  CALL FAILED after retry: {report.failure}\n  nothing was created")
        return
    drafted = len(report.required.items) if report.required else 0
    print(f"  delta drafted: {drafted}   "
          f"skipped: {len(report.skipped)}   retries: {report.retries}   "
          f"usage: {report.usage or 'n/a (stub)'}")
    for name, reason in report.skipped:
        print(f"  skipped: {clip(name, 60)}\n           -> {clip(reason)}")
    print(f"  verbatim call log: {report.log_ref}  (read with llm-log.sh)")
    print(f"  requested output: {report.request.requested_output}")
    scope = report.request.scope
    print(f"  scope: {scope.label() or 'the whole landscape (the question named none)'}")
    others = [name for name in roles.answer_types
              if name != report.request.answer_type]
    print(f"  treated as: {report.request.answer_type or 'no declared answer type'}"
          f"   (guide {guide_label(roles)})")
    if others:
        print(f"  not: {', '.join(others)} — the guide declares "
              f"{len(roles.answer_types)}, and this was a choice")

    built = assemble(store, roles, report.request)
    section(f"what this answer depends on ({len(built.items)} items) — and "
            "nothing else has to be known")
    for item in built.items:
        print(f"  {item.kind.value:7s} {item.ref():24s} "
              f"[{item.provenance.value}] {clip(item.why, 46)}")
    print("\n  The model named the FAMILY, not the list. The list was expanded "
          "from the\n  answer type in the guide — so nothing here rests on what "
          "the model happened\n  to remember, and nothing it forgot is missing "
          "from it. Nobody has confirmed\n  the classification yet, which is "
          "why stage 6 will cap the verdict.")
    print(f"\nfull detail: {PROJECT}/answers/  (and section 1 of the report)")
    collect("2a-measure-scan.sh")


def stage_inputs(args) -> None:
    """Stage 0 — what a human declared, and whether it holds together.

    The precondition, not part of the run: a source list and a domain pack
    are chosen once, and many questions are asked against them. This stage
    creates the project and writes those declarations.

    It is also the only stage that can fail before any data is touched — the
    domain guide's coherence lint runs at load, so a guide that contradicts
    itself is caught here rather than surfacing as a strange question later.
    """
    if PROJECT.exists():
        sys.exit(f"{PROJECT} already exists — run reset.sh for a clean start")
    mode = ("ONLINE — model stages will make real calls (needs "
            "ANTHROPIC_API_KEY)" if args.online else
            "OFFLINE — model stages will replay the recorded real answers")
    print(f"creating walkthrough project: {PROJECT}\n  {mode}")
    build_corpus_project(PROJECT, offline=not args.online, scan_now=False)

    from validation.support.corpus import SOURCES
    inputs(
        f"source list ({len(SOURCES)} sources), declared in "
        f"{Path(_corpus_file()).relative_to(REPO)} and written to "
        f"{(PROJECT / 'before-ai.yaml').relative_to(REPO)}",
        f"domain guide: {DOMAIN_GUIDE_FILE.relative_to(REPO)}",
        "domain laws: checks/REGISTRY entries tagged with a domain",
        "NO LLM, NO DATA: this stage only reads and validates declarations",
    )
    section(f"sources declared by a human ({len(SOURCES)})")
    for s in SOURCES:
        print(f"  {s['name']:22s} {s['kind']:7s} "
              f"{Path(s['location']).relative_to(REPO)}")
        # What the file *is*, in the words of whoever put it there. A
        # filename and a row count do not tell a reader whether this is the
        # production ledger or last year's export somebody kept, and that
        # difference decides how much of the report they should believe.
        print(f"  {'':22s} {clip(s.get('description') or 'nobody has said what this file is', 66)}")
    print("\n  init_project writes an empty `sources: []`; scan then merges "
          "in whatever\n  is dropped under sources/ — never overwriting, so a "
          "hand-written entry\n  wins. These were declared directly, outside "
          "the drop directory.")
    unlisted = sorted(
        f.name for f in CORPUS.iterdir()
        if f.is_file() and f.suffix in {".pdf", ".csv", ".xlsx"}
        and not any(Path(s["location"]).name == f.name for s in SOURCES))
    if unlisted:
        print(f"\n  NOT listed, so invisible to this run: {', '.join(unlisted)}")
        print("  The PDFs carry policy traps; a pdf source is fingerprinted "
              "only until the\n  document pipeline exists, so it yields no "
              "views and no evidence.")

    roles = load_domain_guide(DOMAIN_GUIDE_FILE)   # the coherence lint runs here
    fields = len(roles.names) - len(roles.objects)
    section(f"domain guide — {len(roles.objects)} business objects, "
            f"{fields} fields (lint passed)")
    for name, spec in roles.objects.items():
        print(f"  {name:16s} decided_by {spec.decided_by}")
        for fname, field in spec.fields.items():
            path = field.decided_by + (f" -> {field.fills}" if field.fills else "")
            print(f"    {fname:14s} {path}")

    section(f"answer types this guide declares ({len(roles.answer_types)})")
    for name, spec in roles.answer_types.items():
        print(f"  {name:32s} {len(spec.requires)} dependencies")
        print(f"    {clip(spec.definition, 68)}")
    print("\n  Stage 1 classifies the question to one of these, and the engine\n"
          "  expands *that* list. Which is why there has to be more than one:\n"
          "  with a single type the classification could not be wrong, and\n"
          "  'that is not on this path' described nothing.")

    laws = {n: s for n, s in REGISTRY.items() if s.domain}
    section(f"domain laws shipped for this domain ({len(laws)} of "
            f"{len(REGISTRY)} templates)")
    for name, spec in sorted(laws.items()):
        print(f"  {name:22s} [{spec.domain}] {clip(spec.tests, 60)}")
    print("\n  The other templates are generic data checks — they carry no "
          "domain knowledge.")
    collect("1-request.sh")


def stage_readiness(args) -> None:
    """Stage 6 — the verdict. The frame closes.

    NO LLM: the ReadinessMap is derived from the claims and evidence stages
    2-5 produced, and is never stored.
    """
    store = need_project()
    roles = load_domain_guide(DOMAIN_GUIDE_FILE)
    request = next(iter(sorted(store.requests.values(),
                               key=lambda r: r.created_at)), None)
    if request is None:
        sys.exit("no request in this project — run 1-request.sh first")
    inputs(
        f"the request from stage 0: {PROJECT.name}/answers/",
        "the claims, evidence and statuses stages 2-5 produced",
        f"the domain guide, for slot settlement: "
        f"{DOMAIN_GUIDE_FILE.relative_to(REPO)}",
        "NO LLM, and nothing is written: the map is derived on every read",
    )
    result = evaluate_request(store, roles, request.id)
    section(f"the ReadinessMap — {result.verdict.value.replace('_', ' ')}")
    print(f"  {result.reason()}\n")
    for item in result.items:
        mark = "OK " if item.satisfied else "-- "
        print(f"  {mark}{item.ref:24s} {clip(item.because, 100)}")
    print("\n  Every satisfied item says HOW it is satisfied: by its own "
          "claim's status,\n  or by the derivation a passing law supplies for "
          "a slot field whose own\n  claims are still proposed. Those are "
          "deliberately different things.")

    section("and the list itself — the second question the verdict answers")
    print("  Whether the dependencies hold is one question. Whether anyone has "
          "read the\n  LIST of them is another, and only the second protects "
          "against a list that was\n  short to begin with. So an unconfirmed "
          "list can never read 'ready':\n")
    print(f"  before: {result.verdict.value}   confirmed: {result.confirmed}")
    confirm_classification(store, roles, request.id)
    confirmed = evaluate_request(store, roles, request.id)
    print(f"  after a human confirms the classification: "
          f"{confirmed.verdict.value}   confirmed: {confirmed.confirmed}")
    print(f"\n  {confirmed.reason()}")
    print("\n  Here the verdict does not move: it is blocked on missing "
          "dependencies, and\n  confirming the list does not supply them. On a "
          "landscape where everything\n  held, this is the step between "
          "'with limitations' and 'ready'. Edit the\n  guide's answer type and "
          "the confirmation lapses — it vouched for a list\n  that no longer "
          "exists.")
    print(f"\nfull detail: sections 1 and 6 of the report")
    collect()
    print("\nthe walkthrough is complete — every artifact is in the index above")


def stage_report(args) -> None:
    """Rebuild everything on demand — the same collect every stage runs."""
    need_project()
    collect()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=[
        "request", "inputs", "scan", "matrix", "documents", "hypotheses",
        "mappings", "plans", "read-documents", "test", "clarify",
        "tell", "readiness", "report"])
    parser.add_argument("--online", action="store_true",
                        help="scan only: configure real model calls "
                             "(needs ANTHROPIC_API_KEY for stages 3-5)")
    parser.add_argument("--top", type=int, default=15,
                        help="how many rows to show in list sections")
    args = parser.parse_args()
    {
        "request": stage_request,
        "inputs": stage_inputs,
        "scan": stage_scan,
        "matrix": stage_matrix,
        "documents": stage_documents,
        "hypotheses": stage_hypotheses,
        "mappings": stage_mappings,
        "plans": stage_plans,
        "read-documents": stage_read_documents,
        "test": stage_test,
        "clarify": stage_clarify,
        "tell": stage_tell,
        "readiness": stage_readiness,
        "report": stage_report,
    }[args.stage](args)


if __name__ == "__main__":
    main()
