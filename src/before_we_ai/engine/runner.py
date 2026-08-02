"""Execute one check: render, run, judge, record — deterministically.

Every run produces one append-only EvidenceRecord carrying the rendered
SQL, the verdict, aggregate counts, a bounded sample, a cache pointer to
the full exception set, and the fingerprints of every view involved.
Status derivation stays in the M1 core (`attach_evidence`); the runner
never sets a status by hand.
"""

from pathlib import Path

import yaml
from jinja2 import Environment, PackageLoader

from before_we_ai.core.enums import Actor, EvidenceType
from before_we_ai.core.ids import new_id
from before_we_ai.core.objects import MAX_EXCEPTION_SAMPLES, EvidenceRecord, CheckPlan, ClarificationQuestion
from before_we_ai.core.transitions import attach_evidence
from before_we_ai.checks.library import REGISTRY
from before_we_ai.sources.fingerprint import table_fingerprint
from before_we_ai.store.layout import CONFIG_FILE
from before_we_ai.store.repository import ProjectStore

_MARKER = "-- ::exceptions::"
_env = Environment(loader=PackageLoader("before_we_ai.checks", "templates"))


def load_tolerances(root: str | Path) -> dict[str, dict[str, float]]:
    """Tolerance overrides from before-ai.yaml — the only override channel."""
    config = yaml.safe_load((Path(root) / CONFIG_FILE).read_text(encoding="utf-8")) or {}
    overrides = {}
    for template, value in (config.get("tolerances") or {}).items():
        overrides[template] = value if isinstance(value, dict) else {"absolute": value}
    return overrides


def _jsonable(value: object) -> object:
    return value if isinstance(value, (str, int, float, bool, type(None))) else str(value)


def _write_parquet(con, columns: list[str], rows: list[tuple], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ", ".join(f'"{c}" VARCHAR' for c in columns)
    con.execute(f"CREATE OR REPLACE TEMP TABLE _check_exceptions ({cols})")
    con.executemany(
        f"INSERT INTO _check_exceptions VALUES ({', '.join('?' for _ in columns)})",
        [[None if v is None else str(v) for v in row] for row in rows],
    )
    con.execute(f"COPY _check_exceptions TO '{path}' (FORMAT PARQUET)")
    con.execute("DROP TABLE _check_exceptions")


def run_check(
    store: ProjectStore,
    con,
    check: CheckPlan,
    tolerances: dict[str, dict[str, float]] | None = None,
) -> EvidenceRecord:
    if check.template not in REGISTRY:
        raise ValueError(f"unknown check definition: {check.template!r}")
    spec = REGISTRY[check.template]
    tolerance = {**spec.tolerances, **(tolerances or {}).get(check.template, {})}
    ctx = spec.prepare(con, check.params, tolerance)

    rendered = _env.get_template(spec.file).render(**ctx)
    population_sql, exceptions_sql = (part.strip() for part in rendered.split(_MARKER))
    population = con.execute(population_sql).fetchone()[0]
    cursor = con.execute(exceptions_sql)
    columns = [d[0] for d in cursor.description]
    rows = cursor.fetchall()

    assessment = spec.verdict(rows, columns, ctx)

    record_id = new_id()
    result_ref = None
    if assessment.exceptions:
        path = store.root / "cache" / "check_runs" / f"{record_id}.parquet"
        _write_parquet(con, columns, assessment.exceptions, path)
        result_ref = str(path.relative_to(store.root))

    if check.id not in store.checks:
        store.save_check_plan(check)  # evidence must never reference an unpersisted check

    record = EvidenceRecord(
        id=record_id,
        type=EvidenceType.CHECK_RESULT,
        actor=Actor.CHECK,
        claim_id=check.claim_id,
        check_plan_id=check.id,
        verdict=assessment.verdict,
        population=population,
        exception_count=min(len(assessment.exceptions), population),
        exception_samples=[
            {c: _jsonable(v) for c, v in zip(columns, row)}
            for row in assessment.exceptions[:MAX_EXCEPTION_SAMPLES]
        ],
        result_ref=result_ref,
        payload={
            "template": check.template,
            "sql": exceptions_sql,
            "summary": assessment.summary,
        },
        source_fingerprints={view: table_fingerprint(con, view) for view in ctx["views"]},
    )
    _supersede(store, check, record)
    store.add_evidence(record)

    if check.claim_id:
        claim = store.claims[check.claim_id]
        claim = attach_evidence(claim, record, store.evidence_for(claim))
        store.save_claim(claim)

    _draft_question(store, spec, ctx, check, record)
    return record


def _supersede(store, check: CheckPlan, record: EvidenceRecord) -> None:
    """Every earlier run of this plan now describes data that has moved on.

    Evidence is append-only, so an old result is never deleted or edited —
    it is marked stale, which is the one mutation the store permits, and
    ``resolve_status`` stops counting it. Without this a re-run left the
    old FAIL live beside the new PASS and the claim landed on *unresolved*:
    you fixed the data and the system called the result a conflict. Fixing
    your data has to be a way forward, not a new kind of stuck.

    The trail keeps both. What changed is which of them is *live* — the
    reading that describes the data as it is now.
    """
    for known in list(store.evidence.values()):
        if (known.type is EvidenceType.CHECK_RESULT
                and known.check_plan_id == check.id
                and known.id != record.id
                and not known.stale):
            store.mark_evidence_stale(known.id)


def _draft_question(store, spec, ctx, check: CheckPlan, record: EvidenceRecord) -> None:
    """A FAIL or INCONCLUSIVE finding surfaces as a clarification question."""
    if spec.question is None or record.verdict.value == "pass":
        return
    text = spec.question.format_map(
        {k: v for k, v in ctx.items() if isinstance(v, (str, int, float))}
    )
    card = ClarificationQuestion(
        question=text,
        finding=_scale(record),
        scope=record.scope,
        claim_ids=[check.claim_id] if check.claim_id else [],
    )
    known = store.find_question(card)
    if known:
        # Same question, possibly a different size. The card stays the same
        # card — re-asking it under a new id would put one decision in
        # front of the reader twice.
        if known.finding != card.finding:
            store.save_question(known.model_copy(
                update={"finding": card.finding}))
        return
    store.save_question(card)


def _scale(record: EvidenceRecord) -> str:
    """How big the finding is, so a reader can decide what to look at first."""
    if record.exception_count is None or record.population is None:
        return ""
    plural = "s" if record.exception_count != 1 else ""
    scale = (f"{record.exception_count:,} exception{plural} "
             f"in {record.population:,} rows")
    rate = record.exception_rate()
    return f"{scale} ({rate:.1%})" if rate else scale
