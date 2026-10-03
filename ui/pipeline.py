"""The demo run, one step at a time.

The same product calls the validation walkthrough makes
(`validation/scripts/_steps.py`), minus the printing: each step runs one
pipeline function against the demo project and returns one sentence about
what it left behind. Product code is only imported, never duplicated.

The run is offline. Model stages replay the recorded answers, which is why
the question is fixed — a recording answers the input it was recorded for.
"""

import json
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "ui-data"
SCENARIO = "finance"  # shared with the recorded fixtures
# byte-identical to DEMO_QUESTION in validation/scripts/_steps.py — the
# recorded classification belongs to exactly these words
DEMO_QUESTION = "Can these files reliably produce actual P&L by entity and month?"

from validation.support.corpus import (  # noqa: E402
    CORPUS,
    DOMAIN_GUIDE_FILE,
    SOURCES,
    build_corpus_project,
)

from before_we_ai import read_documents, scan  # noqa: E402
from before_we_ai.checks.library import REGISTRY  # noqa: E402
from before_we_ai.core import Actor  # noqa: E402
from before_we_ai.core.objects import MappingClaim  # noqa: E402
from before_we_ai.engine import run_ready  # noqa: E402
from before_we_ai.llm import (  # noqa: E402
    ask,
    hypothesize,
    interpret_documents,
    load_domain_guide,
    plan_checks,
    propose_mappings,
    resolve_mappings,
)
from before_we_ai.profile.candidates import load_matrix  # noqa: E402
from before_we_ai.sources import open_catalog  # noqa: E402
from before_we_ai.statements import tell  # noqa: E402
from before_we_ai.store import ProjectStore  # noqa: E402

TELL_STATEMENTS = CORPUS / "tell_statements.yaml"

from corpora import load as load_landscape  # noqa: E402

VESSEL = load_landscape("vessel")
RECORDED = VESSEL.root / "run-b"

# The two things this app can show. `replay` runs the pipeline step by step
# on recorded model answers; `recorded` loads the store a live run left
# behind and re-judges it — its model stages cannot be replayed, because a
# recording answers the input it was recorded for.
LANDSCAPES = {
    "finance": {
        "label": "Finance — seeded corpus",
        "mode": "replay",
        "blurb": "The landscape the tool grew up on: a two-entity ERP export "
                 "with 32 seeded errors. Model answers are replayed.",
        "pill": "Offline replay",
        "note": "Model answers are recorded, not live. Checks and decisions "
                "run for real.",
    },
    "vessel": {
        "label": "Vessel — Run B, recorded live",
        "mode": "recorded",
        "blurb": "A shipbuilder's ten documents, built by someone else. "
                 "Proposed live on 2026-10-03 by Opus 5.5 and Sonnet 5.5; "
                 "judged here by the current engine.",
        "pill": "Recorded run",
        "note": "Proposals are the live run's, unedited. Checks were re-run "
                "with today's engine; decisions run for real.",
    },
}


def active() -> str:
    marker = DATA / "active"
    name = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    return name if name in LANDSCAPES else "finance"


def set_active(name: str) -> None:
    if name not in LANDSCAPES:
        raise ValueError(f"unknown landscape {name!r}")
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "active").write_text(name, encoding="utf-8")


def landscape() -> dict:
    return LANDSCAPES[active()]


def workdir() -> Path:
    return DATA / active()


def project_dir() -> Path:
    return workdir() / "project"


def run_log() -> Path:
    return workdir() / "run.json"


def guide():
    if active() == "vessel":
        return load_domain_guide(VESSEL.guide_file)
    return load_domain_guide(DOMAIN_GUIDE_FILE)


def sources() -> list[dict]:
    return VESSEL.declarations() if active() == "vessel" else SOURCES


def question() -> str:
    if active() == "vessel":
        return _recorded_summary()["questions"][0]
    return DEMO_QUESTION


def store() -> ProjectStore:
    return ProjectStore(project_dir())


def exists() -> bool:
    return (project_dir() / "before-ai.yaml").is_file()


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# ---------------------------------------------------------------- steps


def _inputs() -> str:
    workdir().mkdir(parents=True, exist_ok=True)
    build_corpus_project(project_dir(), offline=True, scan_now=False)
    g = guide()
    laws = sum(1 for spec in REGISTRY.values() if spec.domain)
    return (f"{_plural(len(SOURCES), 'source')} declared, a domain guide with "
            f"{_plural(len(g.objects), 'business object')} and "
            f"{_plural(len(g.answer_types), 'answer type')}, "
            f"{_plural(laws, 'domain law')}")


def _request() -> str:
    report = ask(project_dir(), DEMO_QUESTION, guide=guide(), store=store(),
                 scenario=SCENARIO)
    if report.failure:
        raise RuntimeError(report.failure)
    return f"classified as '{report.request.answer_type}'"


def _scan() -> str:
    scan(project_dir())
    s = store()
    tables = {p.table for p in s.profiles.values()}
    matrix = load_matrix(project_dir())
    return (f"{_plural(len(tables), 'table')}, "
            f"{_plural(len(s.profiles), 'column')} profiled, "
            f"{len(matrix['candidates'])} overlaps kept of "
            f"{matrix['pairs_examined']:,} pairs — 0 claims")


def _documents() -> str:
    result = read_documents(project_dir())
    return (f"{_plural(result.profiles_written, 'document')}, "
            f"{_plural(result.pages, 'page')}, "
            f"{_plural(result.chunks, 'passage')} — 0 claims")


def _hypotheses() -> str:
    report = hypothesize(project_dir(), store=store(), scenario=SCENARIO)
    if report.failure:
        raise RuntimeError(report.failure)
    return f"{len(report.claims_created)} hypotheses proposed, none promoted"


def _mappings() -> str:
    report = propose_mappings(project_dir(), roles=guide(), store=store(),
                              scenario=SCENARIO)
    if report.failure:
        raise RuntimeError(report.failure)
    n = sum(isinstance(c, MappingClaim) for c in store().claims.values())
    return f"{_plural(n, 'candidate')} for the guide's roles — rivals wanted"


def _plans() -> str:
    report = plan_checks(project_dir(), store=store(), scenario=SCENARIO)
    return (f"{_plural(len(report.check_plans_created), 'check')} planned, "
            f"{len(report.unbindable)} claims the model said it cannot test")


def _read_documents() -> str:
    report = interpret_documents(project_dir(), guide=guide(), store=store(),
                                 scenario=SCENARIO)
    return (f"{_plural(len(report.claims_created), 'claim')} read from "
            f"documents with {_plural(report.anchors, 'quote')}, "
            f"{len(report.skipped) + len(report.questions)} refused and asked instead")


def _test() -> str:
    s = store()
    con = open_catalog(project_dir())
    try:
        report = run_ready(s, con)
    finally:
        con.close()
    verdicts = Counter(e.verdict.value for e in report.executed if e.verdict)
    return (f"{_plural(len(report.executed), 'check')} run: "
            f"{verdicts.get('pass', 0)} pass, {verdicts.get('fail', 0)} fail, "
            f"{verdicts.get('inconclusive', 0)} inconclusive")


def _clarify() -> str:
    cards = resolve_mappings(store(), guide())
    return (f"{_plural(len(cards), 'role')} nobody won became a question; "
            f"{_plural(len(store().questions), 'question')} open in total")


def _tell() -> str:
    spec = yaml.safe_load(TELL_STATEMENTS.read_text(encoding="utf-8"))
    parked = claims = 0
    for entry in spec["statements"]:
        report = tell(project_dir(), entry["text"], guide=guide(), store=store(),
                      scenario=f"{SCENARIO}_{entry['id'].lower()}")
        if report.failure:
            raise RuntimeError(report.failure)
        parked += bool(report.mirror.parked)
        claims += len(report.claims_created)
    return (f"{_plural(len(spec['statements']), 'statement')} from a colleague: "
            f"{_plural(claims, 'claim')} proposed, {parked} parked as a note")


@dataclass(frozen=True)
class Step:
    key: str
    stage: str  # the stage number in before_we_ai.stages
    title: str
    actor: str  # human | measured | ai | check
    detail: str
    run: Callable[[], str]


STEPS: tuple[Step, ...] = (
    Step("inputs", "0", "Declare sources and domain guide", "human",
         "A source list and a domain pack, chosen once.", _inputs),
    Step("request", "1", "Ask the business question", "ai",
         "The model names the answer type; the guide expands what it depends on.",
         _request),
    Step("scan", "2", "Profile the data", "measured",
         "Every column counted, every table pair compared. No model.", _scan),
    Step("documents", "2", "Read the documents", "measured",
         "PDFs cut into passages. What they mean comes later.", _documents),
    Step("hypotheses", "3", "Propose hypotheses", "ai",
         "The model guesses relationships from profiles, never raw rows.",
         _hypotheses),
    Step("mappings", "3", "Propose role candidates", "ai",
         "Which table is the journal? Which column is the account?", _mappings),
    Step("plans", "3", "Plan the checks", "ai",
         "Each claim is bound to a check that could refute it.", _plans),
    Step("read_documents", "3", "Interpret the documents", "ai",
         "Rules found in policies, each with a verbatim quote.",
         _read_documents),
    Step("test", "4", "Run the checks", "check",
         "Deterministic SQL decides. This is the only step that promotes.",
         _test),
    Step("clarify", "5", "Turn lost roles into questions", "measured",
         "What no check could settle is asked, never dropped.", _clarify),
    Step("tell", "5", "Take what a colleague volunteers", "human",
         "Two statements no file contains, stored verbatim.", _tell),
)
BY_KEY = {step.key: step for step in STEPS}


# ---------------------------------------------------------------- recorded


def _recorded_summary() -> dict:
    return json.loads((RECORDED / "summary.json").read_text(encoding="utf-8"))


def _tokens(stage: dict) -> str:
    usage = stage.get("usage") or {}
    if not usage:
        return ""
    return (f" · {usage.get('input_tokens', 0):,} tokens in, "
            f"{usage.get('output_tokens', 0):,} out, {stage['seconds']:.0f}s")


def load_recorded() -> dict[str, str]:
    """Copy the store the live run left behind, and judge it again.

    Stages 2 and 4 are re-runnable by design, so the copy is re-read and
    re-checked with the engine as it is now. The proposals — every claim,
    candidate, check plan and quote — are the live run's, untouched.
    """
    if exists():
        raise ValueError("the recorded run is already loaded — reset first")
    recorded = {s["stage"]: s for s in _recorded_summary()["stages"]}
    workdir().mkdir(parents=True, exist_ok=True)
    shutil.copytree(RECORDED / "project", project_dir())
    # the recording carries the paths of the machine it ran on
    config_file = project_dir() / "before-ai.yaml"
    config = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    config["sources"] = VESSEL.declarations()
    config["llm"] = {"domain_guide_file": str(VESSEL.guide_file)}
    config_file.write_text(yaml.safe_dump(config, sort_keys=False),
                           encoding="utf-8")

    before = Counter(c.status.value for c in store().claims.values())
    scan(project_dir())
    read_documents(project_dir())
    s = store()
    con = open_catalog(project_dir())
    try:
        report = run_ready(s, con)
    finally:
        con.close()
    resolve_mappings(store(), guide())
    s = store()
    after = Counter(c.status.value for c in s.claims.values())
    verdicts = Counter(e.verdict.value for e in report.executed if e.verdict)
    g = guide()

    r = recorded
    log = {
        "inputs": (f"{_plural(len(VESSEL.declarations()), 'source')} declared, "
                   f"a guide with {_plural(len(g.objects), 'business object')} "
                   f"and {_plural(len(g.answer_types), 'answer type')}"),
        "request": (f"classified as '{r['request']['answer_type']}'"
                    + _tokens(r["request"])),
        "scan": (f"{r['scan']['tables']} tables, {r['scan']['columns']} "
                 "columns profiled — 0 claims"),
        "documents": (f"{r['documents']['documents']} documents, "
                      f"{r['documents']['pages']} pages, "
                      f"{r['documents']['passages']} passages — 0 claims"),
        "hypotheses": (f"{r['hypotheses']['claims_created']} hypotheses "
                       "proposed, none promoted" + _tokens(r["hypotheses"])),
        "mappings": (f"{r['mappings']['candidates']} candidates for "
                     f"{r['mappings']['roles_with_candidates']} of "
                     f"{r['mappings']['roles_total']} roles"
                     + _tokens(r["mappings"])),
        "plans": (f"{r['plans']['checks_created']} checks planned, "
                  f"{r['plans']['with_filter']} with a filter the model wrote"
                  + _tokens(r["plans"])),
        "read_documents": (f"{r['read_documents']['claims_created']} claims "
                           f"read from documents, each with a validated quote"
                           + _tokens(r["read_documents"])),
        "test": (f"on the day: {r['test']['verdicts'].get('pass', 0)} pass, "
                 f"{r['test']['verdicts'].get('fail', 0)} fail, "
                 f"{r['test']['statuses'].get('contradicted', 0)} claims "
                 f"contradicted. Re-judged now: {verdicts.get('pass', 0)} pass, "
                 f"{verdicts.get('fail', 0)} fail, "
                 f"{verdicts.get('inconclusive', 0)} inconclusive, "
                 f"{after.get('contradicted', 0)} contradicted"),
        "clarify": f"{_plural(len(s.questions), 'question')} open",
    }
    assert before  # the recording is never empty
    run_log().write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log


# ---------------------------------------------------------------- foundation

FOUNDATION_DOC = REPO / "foundations" / "shipbuilding" / "foundation.docx"
FOUNDATION_BINDING = VESSEL.root / "foundation-binding.yaml"
# the vessel guide borrowed finance's balance law for a single-sided cost
# ledger; the foundation document replaces it
RETIRED_LAWS = {"balance": "a ledger law borrowed from finance"}


def foundation_available() -> bool:
    return active() == "vessel" and FOUNDATION_DOC.is_file()


def foundation_log() -> Path:
    return workdir() / "foundation.json"


def apply_foundation() -> dict:
    """Read the Word document, measure its rules, write what they settle."""
    from before_we_ai.foundation import Binding, apply, read_foundation, retire

    if not foundation_available():
        raise ValueError("no foundation document for this landscape")
    document = read_foundation(FOUNDATION_DOC)
    binding = Binding.from_dict(
        yaml.safe_load(FOUNDATION_BINDING.read_text(encoding="utf-8")))
    retire(store(), RETIRED_LAWS)
    con = open_catalog(project_dir())
    try:
        applied = apply(store(), con, document, binding)
    finally:
        con.close()
    rules = []
    for a in applied:
        r, rule = a.result, a.result.rule
        if not r.applicable:
            state = "not_applicable"
        elif r.error:
            state = "error"
        elif not r.evaluable:
            state = "not_evaluable"
        else:
            state = "holds" if a.holds else "fails"
        rules.append({
            "id": rule.id, "name": rule.name, "statement": rule.statement,
            "kind": rule.kind, "formal": rule.formal,
            "tolerance": rule.tolerance, "why": rule.why,
            "exception_means": rule.exception_means, "state": state,
            "reason": r.reason or r.error,
            "satisfied": r.satisfied, "evaluable": r.evaluable,
            "blank": r.not_evaluable, "share": round(100 * r.share, 1),
            "samples": r.samples, "sql": r.sql,
            "settled": a.settled, "no_candidate": a.no_candidate,
        })
    log = {
        "document": str(FOUNDATION_DOC.relative_to(REPO)),
        "binding": str(FOUNDATION_BINDING.relative_to(REPO)),
        "min_share": document.min_share,
        "objects": len(document.objects),
        "quantities": len(document.quantities),
        "tolerances": [{"name": t.name, "absolute": t.absolute,
                        "relative": t.relative, "applies_to": t.applies_to}
                       for t in document.tolerances.values()],
        "open_questions": document.open_questions,
        "refused": document.refused,
        "rules": rules,
    }
    foundation_log().write_text(json.dumps(log, indent=2), encoding="utf-8")
    return log


def foundation_result() -> dict | None:
    if not foundation_log().is_file():
        return None
    return json.loads(foundation_log().read_text(encoding="utf-8"))


# ---------------------------------------------------------------- run log


def steps() -> tuple[Step, ...]:
    """Nobody has volunteered anything about the vessel landscape."""
    if active() == "vessel":
        return tuple(step for step in STEPS if step.key != "tell")
    return STEPS


def done() -> dict[str, str]:
    """step key -> the sentence it left behind, for the steps already run."""
    if not exists() or not run_log().is_file():
        return {}
    return json.loads(run_log().read_text(encoding="utf-8"))


def next_step() -> Step | None:
    finished = done()
    return next((step for step in steps() if step.key not in finished), None)


def run_step(key: str) -> str:
    """Run exactly the next step. Offline, a proposal step runs once: its
    recorded answers belong to that one input."""
    if landscape()["mode"] != "replay":
        raise ValueError("a recorded run is loaded whole, not stepped through")
    step = next_step()
    if step is None:
        raise ValueError("the run is complete — reset to start over")
    if step.key != key:
        raise ValueError(f"the next step is '{step.key}', not '{key}'")
    summary = step.run()
    log = done() | {key: summary}
    run_log().write_text(json.dumps(log, indent=2), encoding="utf-8")
    return summary


def reset() -> None:
    """Delete the active landscape's project and every decision made in it."""
    if workdir().is_dir():
        shutil.rmtree(workdir())


def ai_claims(s: ProjectStore) -> list:
    return [c for c in s.claims.values() if c.created_by is Actor.AI]
