"""Execute one probe: render, run, judge, record — deterministically.

Every run produces one append-only EvidenceRecord carrying the rendered
SQL, the verdict, aggregate counts, a bounded sample, a cache pointer to
the full exception set, and the fingerprints of every view involved.
Status derivation stays in the M1 core (`attach_evidence`); the runner
never sets a status by hand.
"""

from pathlib import Path

import yaml
from jinja2 import Environment, PackageLoader

from before_we_ai.model.enums import Actor, EvidenceType
from before_we_ai.model.ids import new_id
from before_we_ai.model.objects import MAX_EXCEPTION_SAMPLES, EvidenceRecord, Probe, QuestionCard
from before_we_ai.model.transitions import attach_evidence
from before_we_ai.probes.library import REGISTRY
from before_we_ai.sources.fingerprint import table_fingerprint
from before_we_ai.store.layout import CONFIG_FILE
from before_we_ai.store.repository import ProjectStore

_MARKER = "-- ::exceptions::"
_env = Environment(loader=PackageLoader("before_we_ai.probes", "templates"))


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
    con.execute(f"CREATE OR REPLACE TEMP TABLE _probe_exceptions ({cols})")
    con.executemany(
        f"INSERT INTO _probe_exceptions VALUES ({', '.join('?' for _ in columns)})",
        [[None if v is None else str(v) for v in row] for row in rows],
    )
    con.execute(f"COPY _probe_exceptions TO '{path}' (FORMAT PARQUET)")
    con.execute("DROP TABLE _probe_exceptions")


def run_probe(
    store: ProjectStore,
    con,
    probe: Probe,
    tolerances: dict[str, dict[str, float]] | None = None,
) -> EvidenceRecord:
    if probe.template not in REGISTRY:
        raise ValueError(f"unknown probe template: {probe.template!r}")
    spec = REGISTRY[probe.template]
    tolerance = {**spec.tolerances, **(tolerances or {}).get(probe.template, {})}
    ctx = spec.prepare(con, probe.params, tolerance)

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
        path = store.root / "cache" / "probe_runs" / f"{record_id}.parquet"
        _write_parquet(con, columns, assessment.exceptions, path)
        result_ref = str(path.relative_to(store.root))

    if probe.id not in store.probes:
        store.save_probe(probe)  # evidence must never reference an unpersisted probe

    record = EvidenceRecord(
        id=record_id,
        type=EvidenceType.PROBE_RESULT,
        actor=Actor.PROBE,
        claim_id=probe.claim_id,
        probe_id=probe.id,
        verdict=assessment.verdict,
        population=population,
        exception_count=min(len(assessment.exceptions), population),
        exception_samples=[
            {c: _jsonable(v) for c, v in zip(columns, row)}
            for row in assessment.exceptions[:MAX_EXCEPTION_SAMPLES]
        ],
        result_ref=result_ref,
        payload={
            "template": probe.template,
            "sql": exceptions_sql,
            "summary": assessment.summary,
        },
        source_fingerprints={view: table_fingerprint(con, view) for view in ctx["views"]},
    )
    store.add_evidence(record)

    if probe.claim_id:
        claim = store.claims[probe.claim_id]
        claim = attach_evidence(claim, record, store.evidence_for(claim))
        store.save_claim(claim)

    _draft_question(store, spec, ctx, probe, record)
    return record


def _draft_question(store, spec, ctx, probe: Probe, record: EvidenceRecord) -> None:
    """FAIL/INCONCLUSIVE findings surface as a Fachfrage (Fragen-Ausbeute)."""
    if spec.question is None or record.verdict.value == "pass":
        return
    text = spec.question.format_map(
        {k: v for k, v in ctx.items() if isinstance(v, (str, int, float))}
    )
    if any(card.question == text for card in store.questions.values()):
        return
    store.save_question(
        QuestionCard(question=text, claim_ids=[probe.claim_id] if probe.claim_id else [])
    )
