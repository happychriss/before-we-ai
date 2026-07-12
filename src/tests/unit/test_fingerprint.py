"""Fingerprints: deterministic identity, sensitive to change."""

import duckdb

from before_we_ai.sources.fingerprint import file_fingerprint, schema_hash, table_fingerprint


def test_file_fingerprint_deterministic_and_sensitive(tmp_path):
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    first = file_fingerprint(f)
    assert file_fingerprint(f) == first
    f.write_text("a,b\n1,2\n3,4\n")
    changed = file_fingerprint(f)
    assert changed["sha256"] != first["sha256"]
    assert changed["size"] > first["size"]


def test_schema_hash_orders_and_types_matter():
    base = schema_hash([("a", "BIGINT"), ("b", "VARCHAR")])
    assert schema_hash([("a", "BIGINT"), ("b", "VARCHAR")]) == base
    assert schema_hash([("b", "VARCHAR"), ("a", "BIGINT")]) != base
    assert schema_hash([("a", "VARCHAR"), ("b", "VARCHAR")]) != base


def test_table_fingerprint():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (id BIGINT, seen DATE)")
    con.execute("INSERT INTO t VALUES (1, DATE '2024-03-01'), (2, DATE '2025-06-30')")
    fp = table_fingerprint(con, "t")
    assert fp["row_count"] == 2
    assert fp["max_date"] == "2025-06-30"
    con.execute("INSERT INTO t VALUES (3, DATE '2025-12-01')")
    fp2 = table_fingerprint(con, "t")
    assert fp2["row_count"] == 3
    assert fp2["max_date"] == "2025-12-01"
    assert fp2["schema_hash"] == fp["schema_hash"]


def test_table_fingerprint_without_date_columns():
    con = duckdb.connect()
    con.execute("CREATE TABLE t (name VARCHAR)")
    assert table_fingerprint(con, "t")["max_date"] is None
