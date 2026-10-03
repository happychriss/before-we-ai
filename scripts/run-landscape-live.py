#!/usr/bin/env python3
"""Run a landscape through the model stages, live, and keep what happened.

    scripts/with-api-key.sh python scripts/run-landscape-live.py vessel \\
        --arm main --question "What is the cost of building a vessel?" \\
        --out runs/vessel-b1

**This spends the API key.** `scripts/run-landscape.py` is the free half
(stage 0 and stage 2); this is everything after it. Three arms:

    main      every stage, one question, through to the readiness verdict
    request   the request contract only — how one question is classified
    control   role candidates, check plans and checks against another guide
              (--guide finance): nothing should win a role it does not fit

The project is kept under --out, including `cache/llm_log/` with every prompt
and answer verbatim. A summary of each stage — what it produced, token usage,
wall time, refusals — is written to `<out>/summary.json` as the run goes, so a
stage that fails still leaves the ones before it on record.

The answer key is never opened. Neither is the generator.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

import yaml  # noqa: E402

from corpora import load as load_landscape, names as landscape_names  # noqa: E402
from before_we_ai import read_documents, scan  # noqa: E402
from before_we_ai.core import Actor, ClaimStatus  # noqa: E402
from before_we_ai.core.objects import MappingClaim  # noqa: E402
from before_we_ai.domains import packaged  # noqa: E402
from before_we_ai.engine import run_ready  # noqa: E402
from before_we_ai.llm import (  # noqa: E402
    LLMConfig,
    ask,
    hypothesize,
    interpret_documents,
    load_domain_guide,
    plan_checks,
    propose_mappings,
    resolve_mappings,
)
from before_we_ai.readiness import evaluate_request  # noqa: E402
from before_we_ai.sources import open_catalog  # noqa: E402
from before_we_ai.store import ProjectStore, init_project  # noqa: E402

SCENARIO = "live"


class Run:
    def __init__(self, root: Path, summary_path: Path, header: dict):
        self.root = root
        self.summary_path = summary_path
        self.summary = {**header, "stages": []}
        self._write()

    def _write(self) -> None:
        self.summary_path.write_text(
            json.dumps(self.summary, indent=2, default=str), encoding="utf-8")

    def stage(self, name: str, fn) -> dict:
        print(f"\n== {name} " + "=" * max(0, 64 - len(name)), flush=True)
        started = time.monotonic()
        entry = {"stage": name}
        try:
            entry.update(fn() or {})
        except Exception as exc:  # noqa: BLE001 — recorded, then re-raised
            entry["crashed"] = f"{type(exc).__name__}: {exc}"
            entry["seconds"] = round(time.monotonic() - started, 1)
            self.summary["stages"].append(entry)
            self._write()
            print(f"  CRASHED: {entry['crashed']}")
            raise
        entry["seconds"] = round(time.monotonic() - started, 1)
        self.summary["stages"].append(entry)
        self._write()
        for key, value in entry.items():
            if key != "stage":
                print(f"  {key}: {value}")
        return entry

    def store(self) -> ProjectStore:
        return ProjectStore(self.root)


def _call(report) -> dict:
    """The fields every contract report shares."""
    out = {}
    for name in ("failure", "retries", "usage"):
        if getattr(report, name, None):
            out[name] = getattr(report, name)
    return out


def _status_counts(store: ProjectStore) -> dict:
    return dict(Counter(c.status.value for c in store.claims.values()))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("landscape", choices=landscape_names())
    parser.add_argument("--arm", choices=("main", "request", "control"),
                        required=True)
    parser.add_argument("--question", action="append", default=[],
                        help="the business question, verbatim (repeatable "
                             "for --arm request)")
    parser.add_argument("--guide", metavar="PACK",
                        help="a packaged domain pack instead of the "
                             "landscape's own guide (the control arm)")
    parser.add_argument("--frontier", metavar="MODEL",
                        help="model for request, hypotheses, role binding "
                             "and documents (default: the configured tier)")
    parser.add_argument("--mid", metavar="MODEL",
                        help="model for plain check binding")
    parser.add_argument("--out", metavar="DIR", required=True)
    args = parser.parse_args()
    if args.arm != "control" and not args.question:
        parser.error(f"--arm {args.arm} needs --question")

    landscape = load_landscape(args.landscape)
    guide_file = (packaged(args.guide) if args.guide
                  else landscape.guide_file or packaged(landscape.guide_packaged))
    out = Path(args.out).resolve()
    root = out / "project"
    if out.exists():
        sys.exit(f"{out} exists — a live run is never overwritten; pick "
                 "another --out or remove it yourself")
    out.mkdir(parents=True)

    init_project(root, name=f"{landscape.name}-{args.arm}")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = landscape.declarations()
    config["llm"] = {"domain_guide_file": str(guide_file)}  # online: no fixtures
    overrides = {}
    if args.frontier:
        overrides |= dict.fromkeys(
            ("request", "v1_hypotheses", "role_binding", "v3_documents"),
            args.frontier)
    if args.mid:
        overrides["v2_bind"] = args.mid
    if overrides:
        config["llm"]["models"] = overrides
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    guide = load_domain_guide(guide_file)
    models = LLMConfig.from_project(root).models

    run = Run(root, out / "summary.json", {
        "landscape": landscape.name, "arm": args.arm,
        "guide": str(Path(guide_file).name), "questions": args.question,
        "models": models,
        "roles": len(guide.names), "objects": len(guide.objects),
        "answer_types": list(guide.answer_types),
    })
    print(f"{landscape.name} · arm {args.arm} · guide {Path(guide_file).name} "
          f"({len(guide.objects)} objects, {len(guide.names)} roles)")
    print(f"models: {models}")

    # ---------------------------------------------------------- request
    def request_stage(question: str):
        def fn():
            report = ask(root, question, guide=guide, store=run.store(),
                         scenario=SCENARIO)
            request = report.request
            return {
                "question": question,
                "answer_type": request.answer_type if request else None,
                "requested_output": request.requested_output if request else None,
                "scope": request.scope.label() if request else None,
                "items_drafted": len(report.required.items) if report.required else 0,
                "skipped": report.skipped,
                **_call(report),
            }
        return fn

    if args.arm == "request":
        for question in args.question:
            run.stage("request", request_stage(question))
        print(f"\nkept at {out}")
        return 0

    if args.arm == "main":
        run.stage("request", request_stage(args.question[0]))

    # ---------------------------------------------------------- measured
    def scan_stage():
        scan(root)
        store = run.store()
        return {"tables": len({p.table for p in store.profiles.values()}),
                "columns": len(store.profiles), "claims": len(store.claims)}
    run.stage("scan", scan_stage)

    if args.arm == "main":
        def documents_stage():
            result = read_documents(root)
            return {"documents": result.profiles_written, "pages": result.pages,
                    "passages": result.chunks, "kinds": dict(result.kinds)}
        run.stage("documents", documents_stage)

        # ------------------------------------------------------ proposed
        def hypotheses_stage():
            report = hypothesize(root, store=run.store(), scenario=SCENARIO)
            store = run.store()
            created = [store.claims[cid] for cid in report.claims_created]
            return {
                "claims_created": len(created),
                "deduped": report.claims_deduped,
                "skipped": report.skipped,
                "predicates": dict(Counter(
                    c.predicate.name for c in created if c.predicate)),
                **_call(report),
            }
        run.stage("hypotheses", hypotheses_stage)

    def mappings_stage():
        report = propose_mappings(root, roles=guide, store=run.store(),
                                  scenario=SCENARIO)
        store = run.store()
        by_role: dict[str, list[str]] = {}
        for claim in store.claims.values():
            if isinstance(claim, MappingClaim):
                by_role.setdefault(claim.role, []).append(
                    ", ".join(f"{k}={v}" for k, v in sorted(claim.binding.items())))
        return {
            "roles_with_candidates": len(by_role),
            "roles_total": len(guide.names),
            "candidates": sum(len(v) for v in by_role.values()),
            "by_role": by_role,
            "skipped": report.skipped,
            **_call(report),
        }
    run.stage("mappings", mappings_stage)

    def plans_stage():
        report = plan_checks(root, store=run.store(), scenario=SCENARIO)
        store = run.store()
        checks = [store.checks[pid] for pid in report.check_plans_created]
        return {
            "checks_created": len(checks),
            "templates": dict(Counter(c.template for c in checks)),
            "with_filter": sum(
                1 for c in checks
                if any(k.endswith("where") and v for k, v in c.params.items())),
            "unbindable": [(store.claims[cid].statement, reason)
                           for cid, reason in report.unbindable],
            "semantic_only": len(report.semantic_only),
            "skipped": report.skipped,
            "unanswered": len(report.unanswered),
            "failures": report.failures,
            "retries": report.retries,
            "usage": report.usage,
        }
    run.stage("plans", plans_stage)

    if args.arm == "main":
        def read_documents_stage():
            report = interpret_documents(root, guide=guide, store=run.store(),
                                         scenario=SCENARIO)
            return {
                "documents_read": len(report.documents_read),
                "claims_created": len(report.claims_created),
                "anchors": report.anchors,
                "deduped": report.claims_deduped,
                "links": len(report.links),
                "refused": report.skipped,
                "asked_instead": report.questions,
                "narrowed": report.narrowed,
                "failures": report.failures,
                "usage": getattr(report, "usage", None),
            }
        run.stage("read_documents", read_documents_stage)

    # ---------------------------------------------------------- tested
    def test_stage():
        store = run.store()
        con = open_catalog(root)
        try:
            report = run_ready(store, con)
        finally:
            con.close()
        store = run.store()
        ai = [c for c in store.claims.values() if c.created_by is Actor.AI]
        unbacked = [
            c.id for c in ai if c.status is not ClaimStatus.PROPOSED
            and not any(e.actor in (Actor.CHECK, Actor.HUMAN)
                        for e in store.evidence_for(c))]
        ai_promoting = [
            e.id for e in store.evidence.values()
            if e.actor is Actor.AI and e.verdict is not None]
        return {
            "executed": len(report.executed),
            "verdicts": dict(Counter(
                e.verdict.value for e in report.executed if e.verdict)),
            "nothing_tested": [
                e.payload.get("summary") for e in report.executed
                if "nothing was tested" in str(e.payload.get("summary", ""))],
            "skipped": report.skipped,
            "statuses": _status_counts(store),
            "role_statuses": {
                f"{c.role}: {', '.join(sorted(c.binding.values()))}": c.status.value
                for c in ai if isinstance(c, MappingClaim)},
            "promoted_without_check_or_human": unbacked,
            "ai_authored_verdicts": ai_promoting,
        }
    run.stage("test", test_stage)

    def clarify_stage():
        cards = resolve_mappings(run.store(), guide)
        store = run.store()
        return {"role_cards": len(cards), "questions_total": len(store.questions),
                "questions": [c.question for c in store.questions.values()]}
    run.stage("clarify", clarify_stage)

    if args.arm == "main":
        def readiness_stage():
            store = run.store()
            request = sorted(store.requests.values(),
                             key=lambda r: r.created_at)[0]
            result = evaluate_request(store, guide, request.id)
            return {
                "verdict": result.verdict.value,
                "reason": result.reason(),
                "satisfied": sum(1 for i in result.items if i.satisfied),
                "total": len(result.items),
                "items": [{"ref": i.ref, "satisfied": i.satisfied,
                           "ground": i.ground.value, "because": i.because}
                          for i in result.items],
            }
        run.stage("readiness", readiness_stage)

    print(f"\nkept at {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
