"""Profiling and the candidate matrix on small synthetic tables."""

import duckdb
import pytest

from before_we_ai.profile.candidates import build_matrix
from before_we_ai.profile.columns import pattern_mask, profile_view, value_class


@pytest.fixture
def con():
    con = duckdb.connect()
    con.execute("CREATE TABLE t_customers (customer_id BIGINT, name VARCHAR)")
    con.executemany(
        "INSERT INTO t_customers VALUES (?, ?)",
        [(i, f"Kunde {i}") for i in range(1001, 1011)],
    )
    # References the customers — but as text, and one with legacy DOUBLE form.
    con.execute("CREATE TABLE t_invoices (ref VARCHAR, amount DOUBLE)")
    con.executemany(
        "INSERT INTO t_invoices VALUES (?, ?)",
        [(str(i), i * 1.5) for i in range(1001, 1009)],
    )
    con.execute("CREATE TABLE t_noise (code VARCHAR)")
    con.executemany("INSERT INTO t_noise VALUES (?)", [("A",), ("B",), ("C",)])
    return con


def profiles_for(con, tables):
    out = []
    for t in tables:
        out.extend(profile_view(con, t, source_id="src"))
    return out


class TestColumnProfiles:
    def test_stats(self, con):
        by_col = {p.column: p for p in profile_view(con, "t_customers", "src")}
        stats = by_col["customer_id"].stats
        assert stats["row_count"] == 10
        assert stats["distinct_count"] == 10
        assert stats["null_count"] == 0
        assert stats["value_class"] == "integer_like"
        assert stats["min"] == "1001"
        assert by_col["name"].stats["value_class"] == "text"
        assert {"mask": "AAAAA 9999", "count": 10} in by_col["name"].stats["patterns"]

    def test_value_class(self):
        assert value_class(["1", "-2"]) == "integer_like"
        assert value_class(["1.5", "2"]) == "decimal_like"
        assert value_class(["2024-01-01", "2025-12-31"]) == "date_like"
        assert value_class(["1", "x"]) == "text"
        assert value_class([]) == "empty"

    def test_pattern_mask(self):
        assert pattern_mask("DE-INV-0000001") == "AA-AAA-9999999"
        assert pattern_mask("Köln 42") == "AAAA 99"


class TestCandidateMatrix:
    def test_cross_type_seed_is_found(self, con):
        matrix = build_matrix(con, profiles_for(con, ["t_customers", "t_invoices", "t_noise"]))
        pairs = {(c["left"], c["right"]): c for c in matrix["candidates"]}
        # BIGINT ids and VARCHAR refs meet in canonical text form.
        hit = pairs[("t_customers.customer_id", "t_invoices.ref")]
        assert hit["overlap"] == 8
        assert hit["containment"] == 1.0
        assert hit["jaccard"] == 0.8

    def test_no_pair_below_threshold_or_within_table(self, con):
        matrix = build_matrix(con, profiles_for(con, ["t_customers", "t_invoices", "t_noise"]))
        for c in matrix["candidates"]:
            assert c["containment"] >= matrix["threshold"]
            assert c["left"].split(".")[0] != c["right"].split(".")[0]

    def test_single_valued_columns_are_floored(self, con):
        con.execute("CREATE TABLE t_flag (f BIGINT)")
        con.execute("INSERT INTO t_flag VALUES (1001), (1001)")
        matrix = build_matrix(con, profiles_for(con, ["t_customers", "t_flag"]))
        assert matrix["candidates"] == []

    def test_hard_cap_warns_and_truncates(self, con):
        matrix = build_matrix(
            con,
            profiles_for(con, ["t_customers", "t_invoices", "t_noise"]),
            max_pairs=1,
        )
        assert matrix["cap_hit"] is True
        assert matrix["pairs_examined"] == 1
        assert any("TRUNCATED" in w for w in matrix["warnings"])

    def test_deterministic(self, con):
        profiles = profiles_for(con, ["t_customers", "t_invoices", "t_noise"])
        assert build_matrix(con, profiles) == build_matrix(con, list(reversed(profiles)))
