"""The two-stage candidate matrix: measured overlap, never judgment.

Stage 1 prefilters column pairs on type/pattern compatibility (with a
hard cap — the pair space is quadratic). Stage 2 counts exact overlap on
distinct canonical values, set-based in one query. The output contains
every pair above the containment threshold, *including* chance overlaps:
the matrix reports what the data shows; rejecting a spurious candidate
is probe/human work (M3+), and nothing in this artifact carries a status.
"""

import json
from pathlib import Path

from before_we_ai.model.objects import ColumnProfile
from before_we_ai.sources.canonical import canonical_sql_expr

MAX_CANDIDATE_PAIRS = 50_000
CONTAINMENT_THRESHOLD = 0.5

_NUMERIC = {"integer_like", "decimal_like"}


def _compatible(class_a: str, class_b: str) -> bool:
    return class_a == class_b or (class_a in _NUMERIC and class_b in _NUMERIC)


def _key(profile: ColumnProfile) -> str:
    return f"{profile.table}.{profile.column}"


def build_matrix(
    con,
    profiles: list[ColumnProfile],
    *,
    threshold: float = CONTAINMENT_THRESHOLD,
    max_pairs: int = MAX_CANDIDATE_PAIRS,
) -> dict:
    usable = sorted(
        (p for p in profiles if (p.stats.get("distinct_count") or 0) >= 2),
        key=_key,
    )
    pairs = [
        (a, b)
        for i, a in enumerate(usable)
        for b in usable[i + 1:]
        if a.table != b.table
        and _compatible(str(a.stats["value_class"]), str(b.stats["value_class"]))
    ]
    cap_hit = len(pairs) > max_pairs
    if cap_hit:
        pairs = pairs[:max_pairs]  # deterministic: already sorted by column key

    needed = {id(p): p for a, b in pairs for p in (a, b)}
    con.execute("CREATE OR REPLACE TEMP TABLE _cand_values (col VARCHAR, val VARCHAR)")
    for p in needed.values():
        expr = canonical_sql_expr(p.column, str(p.stats["duckdb_type"]))
        con.execute(
            f"INSERT INTO _cand_values SELECT DISTINCT ?, c FROM "
            f'(SELECT {expr} AS c FROM "{p.table}") WHERE c IS NOT NULL',
            [_key(p)],
        )
    distinct = dict(con.execute(
        "SELECT col, count(*) FROM _cand_values GROUP BY col"
    ).fetchall())
    overlaps = {
        (a, b): n
        for a, b, n in con.execute(
            "SELECT a.col, b.col, count(*) FROM _cand_values a "
            "JOIN _cand_values b USING (val) WHERE a.col < b.col GROUP BY 1, 2"
        ).fetchall()
    }
    con.execute("DROP TABLE _cand_values")

    candidates = []
    for a, b in pairs:
        ka, kb = sorted((_key(a), _key(b)))
        overlap = overlaps.get((ka, kb), 0)
        da, db = distinct.get(ka, 0), distinct.get(kb, 0)
        if not overlap or not da or not db:
            continue
        containment = overlap / min(da, db)
        if containment < threshold:
            continue
        candidates.append({
            "left": ka,
            "right": kb,
            "overlap": overlap,
            "left_distinct": da,
            "right_distinct": db,
            "containment": round(containment, 4),
            "jaccard": round(overlap / (da + db - overlap), 4),
        })
    candidates.sort(key=lambda c: (-c["containment"], -c["overlap"], c["left"], c["right"]))
    return {
        "threshold": threshold,
        "pair_cap": max_pairs,
        "pairs_examined": len(pairs),
        "cap_hit": cap_hit,
        "warnings": (
            [f"candidate pair space exceeded the hard cap of {max_pairs}; "
             "matrix is TRUNCATED — results are incomplete"] if cap_hit else []
        ),
        "candidates": candidates,
    }


def write_matrix(matrix: dict, profiles_dir: str | Path) -> Path:
    """Persist the matrix as JSON (machine) + Markdown (human) in profiles/."""
    directory = Path(profiles_dir)
    directory.mkdir(exist_ok=True)
    json_path = directory / "candidate_matrix.json"
    json_path.write_text(json.dumps(matrix, indent=1, ensure_ascii=False), encoding="utf-8")

    lines = ["# Candidate matrix", ""]
    for warning in matrix["warnings"]:
        lines += [f"**WARNING: {warning}**", ""]
    lines += [
        f"{len(matrix['candidates'])} value-overlap candidates "
        f"(containment ≥ {matrix['threshold']}, {matrix['pairs_examined']} pairs examined). "
        "Measured overlap only — no candidate carries any epistemic status.",
        "",
        "| left | right | overlap | containment | jaccard |",
        "|---|---|---|---|---|",
    ]
    lines += [
        f"| {c['left']} | {c['right']} | {c['overlap']} "
        f"| {c['containment']} | {c['jaccard']} |"
        for c in matrix["candidates"]
    ]
    (directory / "candidate_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path
