"""Column statistics via SQL — the LLM later sees profiles, never rows.

Everything is measured on the canonical text form, so a BIGINT column
and a text column holding the same values profile alike.
"""

import re

from before_we_ai.model.objects import ColumnProfile
from before_we_ai.sources.canonical import canonical_sql_expr

TOP_K = 10
SAMPLE_LIMIT = 200

_INTEGER = re.compile(r"^-?\d+$")
_DECIMAL = re.compile(r"^-?\d+\.\d+$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T].*)?$")


def value_class(samples: list[str]) -> str:
    if not samples:
        return "empty"
    if all(_INTEGER.match(s) for s in samples):
        return "integer_like"
    if all(_INTEGER.match(s) or _DECIMAL.match(s) for s in samples):
        return "decimal_like"
    if all(_DATE.match(s) for s in samples):
        return "date_like"
    return "text"


def pattern_mask(value: str) -> str:
    mask = re.sub(r"\d", "9", value)
    return re.sub(r"[^\W\d_]", "A", mask)


def profile_view(con, view: str, source_id: str) -> list[ColumnProfile]:
    columns = [(r[0], r[1]) for r in con.execute(f'DESCRIBE "{view}"').fetchall()]
    profiles = []
    for column, dtype in columns:
        expr = canonical_sql_expr(column, dtype)
        row_count, non_null, distinct, vmin, vmax, len_min, len_avg, len_max = con.execute(
            f"SELECT count(*), count(c), count(DISTINCT c), min(c), max(c), "
            f"min(length(c)), round(avg(length(c)), 1), max(length(c)) "
            f'FROM (SELECT {expr} AS c FROM "{view}")'
        ).fetchone()
        top = con.execute(
            f'SELECT c, count(*) FROM (SELECT {expr} AS c FROM "{view}") '
            f"WHERE c IS NOT NULL GROUP BY c ORDER BY count(*) DESC, c LIMIT {TOP_K}"
        ).fetchall()
        samples = [r[0] for r in con.execute(
            f'SELECT DISTINCT c FROM (SELECT {expr} AS c FROM "{view}") '
            f"WHERE c IS NOT NULL ORDER BY c LIMIT {SAMPLE_LIMIT}"
        ).fetchall()]
        masks: dict[str, int] = {}
        for s in samples:
            masks[pattern_mask(s)] = masks.get(pattern_mask(s), 0) + 1
        top_masks = sorted(masks.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
        profiles.append(ColumnProfile(
            source_id=source_id,
            table=view,
            column=column,
            stats={
                "duckdb_type": dtype,
                "row_count": row_count,
                "null_count": row_count - non_null,
                "distinct_count": distinct,
                "min": vmin,
                "max": vmax,
                "len_min": len_min,
                "len_avg": len_avg,
                "len_max": len_max,
                "top_values": [{"value": v, "count": n} for v, n in top],
                "value_class": value_class(samples),
                "patterns": [{"mask": m, "count": n} for m, n in top_masks],
            },
        ))
    return profiles
