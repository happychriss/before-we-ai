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
PROJECT = DATA / "project"
RUN_LOG = DATA / "run.json"
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


def guide():
    return load_domain_guide(DOMAIN_GUIDE_FILE)


def store() -> ProjectStore:
    return ProjectStore(PROJECT)


def exists() -> bool:
    return (PROJECT / "before-ai.yaml").is_file()


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


# ---------------------------------------------------------------- steps


def _inputs() -> str:
    DATA.mkdir(parents=True, exist_ok=True)
    build_corpus_project(PROJECT, offline=True, scan_now=False)
    g = guide()
    laws = sum(1 for spec in REGISTRY.values() if spec.domain)
    return (f"{_plural(len(SOURCES), 'source')} declared, a domain guide with "
            f"{_plural(len(g.objects), 'business object')} and "
            f"{_plural(len(g.answer_types), 'answer type')}, "
            f"{_plural(laws, 'domain law')}")


def _request() -> str:
    report = ask(PROJECT, DEMO_QUESTION, guide=guide(), store=store(),
                 scenario=SCENARIO)
    if report.failure:
        raise RuntimeError(report.failure)
    return f"classified as '{report.request.answer_type}'"


def _scan() -> str:
    scan(PROJECT)
    s = store()
    tables = {p.table for p in s.profiles.values()}
    matrix = load_matrix(PROJECT)
    return (f"{_plural(len(tables), 'table')}, "
            f"{_plural(len(s.profiles), 'column')} profiled, "
            f"{len(matrix['candidates'])} overlaps kept of "
            f"{matrix['pairs_examined']:,} pairs — 0 claims")


def _documents() -> str:
    result = read_documents(PROJECT)
    return (f"{_plural(result.profiles_written, 'document')}, "
            f"{_plural(result.pages, 'page')}, "
            f"{_plural(result.chunks, 'passage')} — 0 claims")


def _hypotheses() -> str:
    report = hypothesize(PROJECT, store=store(), scenario=SCENARIO)
    if report.failure:
        raise RuntimeError(report.failure)
    return f"{len(report.claims_created)} hypotheses proposed, none promoted"


def _mappings() -> str:
    report = propose_mappings(PROJECT, roles=guide(), store=store(),
                              scenario=SCENARIO)
    if report.failure:
        raise RuntimeError(report.failure)
    n = sum(isinstance(c, MappingClaim) for c in store().claims.values())
    return f"{_plural(n, 'candidate')} for the guide's roles — rivals wanted"


def _plans() -> str:
    report = plan_checks(PROJECT, store=store(), scenario=SCENARIO)
    return (f"{_plural(len(report.check_plans_created), 'check')} planned, "
            f"{len(report.unbindable)} claims the model said it cannot test")


def _read_documents() -> str:
    report = interpret_documents(PROJECT, guide=guide(), store=store(),
                                 scenario=SCENARIO)
    return (f"{_plural(len(report.claims_created), 'claim')} read from "
            f"documents with {_plural(report.anchors, 'quote')}, "
            f"{len(report.skipped) + len(report.questions)} refused and asked instead")


def _test() -> str:
    s = store()
    con = open_catalog(PROJECT)
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
        report = tell(PROJECT, entry["text"], guide=guide(), store=store(),
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


# ---------------------------------------------------------------- run log


def done() -> dict[str, str]:
    """step key -> the sentence it left behind, for the steps already run."""
    if not exists() or not RUN_LOG.is_file():
        return {}
    return json.loads(RUN_LOG.read_text(encoding="utf-8"))


def next_step() -> Step | None:
    finished = done()
    return next((step for step in STEPS if step.key not in finished), None)


def run_step(key: str) -> str:
    """Run exactly the next step. Offline, a proposal step runs once: its
    recorded answers belong to that one input."""
    step = next_step()
    if step is None:
        raise ValueError("the run is complete — reset to start over")
    if step.key != key:
        raise ValueError(f"the next step is '{step.key}', not '{key}'")
    summary = step.run()
    log = done() | {key: summary}
    RUN_LOG.write_text(json.dumps(log, indent=2), encoding="utf-8")
    return summary


def reset() -> None:
    if DATA.is_dir():
        shutil.rmtree(DATA)


def ai_claims(s: ProjectStore) -> list:
    return [c for c in s.claims.values() if c.created_by is Actor.AI]
