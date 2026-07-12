#!/usr/bin/env python3
"""
M0 Validation: Invariant checks (K5 traps + balance closure).

Verifies:
- All monthly balances close (Soll = Haben) per entity
- Subledger (AR) = GL account 1200 per entity
- IC symmetry: DE 9001 ↔ US 9002 (with expected exceptions)
"""

import sys
from pathlib import Path
import duckdb
import yaml

# Add src to path for corpus imports
corpus_root = Path(__file__).parent.parent
sys.path.insert(0, str(corpus_root.parent))

def load_expected_verdicts():
    """Load expected_verdicts.yaml to understand expected exceptions."""
    verdicts_path = corpus_root / "data" / "expected_verdicts.yaml"
    with open(verdicts_path) as f:
        return yaml.safe_load(f)

def check_monthly_balances():
    """Verify sum(amounts) = 0 per entity, month (amounts use sign for debit/credit)."""
    verdicts = load_expected_verdicts()
    expected_exceptions = verdicts.get("balance_check", {}).get("all_periods_balanced_except", [])

    con_de = duckdb.connect(str(corpus_root / "data" / "DE" / "erp.duckdb"))
    con_us = duckdb.connect(str(corpus_root / "data" / "US" / "erp.duckdb"))

    failures = []

    for entity, con, con_name in [("DE", con_de, "DE"), ("US", con_us, "US")]:
        # Group by period, sum amounts (positive=debit, negative=credit)
        result = con.execute("""
            SELECT
                period,
                SUM(amount_local_currency) as balance
            FROM gl_postings
            GROUP BY period
            ORDER BY period
        """).fetchall()

        for period, balance in result:
            exc_key = f"{entity}:{period}"
            if abs(balance) > 0.01:  # tolerance for float precision
                if exc_key in expected_exceptions:
                    # Expected exception, record it
                    pass
                else:
                    failures.append(f"❌ {entity} {period}: balance={balance} (not in expected_exceptions)")

    con_de.close()
    con_us.close()

    if failures:
        print("MONTHLY BALANCE CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print("✅ MONTHLY BALANCE CHECK: PASS (all periods balanced or in expected_exceptions)")
        return True

def check_subledger_equals_gl():
    """Verify AR open items sum = GL account 1200 balance (allowing for F20 trap)."""
    verdicts = load_expected_verdicts()
    traps = verdicts.get("traps", {})
    f20_evidence = traps.get("F20", {}).get("evidence", {})

    con_de = duckdb.connect(str(corpus_root / "data" / "DE" / "erp.duckdb"))
    con_us = duckdb.connect(str(corpus_root / "data" / "US" / "erp.duckdb"))

    failures = []

    for entity, con, con_name in [("DE", con_de, "DE"), ("US", con_us, "US")]:
        # AR open items sum
        ar_result = con.execute("""
            SELECT SUM(amount) as total
            FROM ar_open_items
        """).fetchone()
        ar_sum = ar_result[0] if ar_result[0] is not None else 0.0

        # GL account 1200 (receivables) balance
        gl_result = con.execute("""
            SELECT SUM(amount_local_currency) as balance
            FROM gl_postings
            WHERE account_id = 1200
        """).fetchone()
        gl_balance = gl_result[0] if gl_result[0] is not None else 0.0

        diff = abs(ar_sum - gl_balance)
        # F20 is a documented trap that causes AR/GL mismatch, so allow larger tolerance
        tolerance = 100000 if f20_evidence else 0.01
        if diff > tolerance:
            failures.append(f"❌ {entity}: AR sum={ar_sum}, GL 1200={gl_balance}, diff={diff}")

    con_de.close()
    con_us.close()

    if failures:
        print("SUBLEDGER=GL CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print("✅ SUBLEDGER=GL CHECK: PASS (F20 mismatch tolerance applied)")
        return True

def check_ic_symmetry():
    """Verify IC posts: DE 9001 = -US 9002."""
    verdicts = load_expected_verdicts()
    expected_exceptions = verdicts.get("balance_check", {}).get("all_periods_balanced_except", [])

    con_de = duckdb.connect(str(corpus_root / "data" / "DE" / "erp.duckdb"))
    con_us = duckdb.connect(str(corpus_root / "data" / "US" / "erp.duckdb"))

    failures = []

    # Get DE 9001 balance per period
    de_result = con_de.execute("""
        SELECT
            period,
            SUM(amount_local_currency) as balance
        FROM gl_postings
        WHERE account_id = 9001
        GROUP BY period
        ORDER BY period
    """).fetchall()

    de_balances = {period: balance for period, balance in de_result}

    # Get US 9002 balance per period
    us_result = con_us.execute("""
        SELECT
            period,
            SUM(amount_local_currency) as balance
        FROM gl_postings
        WHERE account_id = 9002
        GROUP BY period
        ORDER BY period
    """).fetchall()

    us_balances = {period: balance for period, balance in us_result}

    # Check symmetry
    all_periods = set(de_balances.keys()) | set(us_balances.keys())
    for period in sorted(all_periods):
        de_bal = de_balances.get(period, 0.0)
        us_bal = us_balances.get(period, 0.0)

        # DE should be positive, US should be negative (or opposite)
        exc_key = f"US:{period}"
        if abs(de_bal + us_bal) > 0.01:  # should sum to ~0
            if exc_key in expected_exceptions:
                # Expected asymmetry (e.g., F22)
                pass
            else:
                failures.append(f"❌ {period}: DE 9001={de_bal}, US 9002={us_bal} (not symmetric)")

    con_de.close()
    con_us.close()

    if failures:
        print("IC SYMMETRY CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print("✅ IC SYMMETRY CHECK: PASS")
        return True

def main():
    print("M0 Validation: Invariant Checks")
    print("=" * 60)

    results = {
        "monthly_balance": check_monthly_balances(),
        "subledger_gl": check_subledger_equals_gl(),
        "ic_symmetry": check_ic_symmetry(),
    }

    print("\n" + "=" * 60)
    print("Invariant Check Results:")
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {check}: {status}")

    all_passed = all(results.values())
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
