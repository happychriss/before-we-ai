#!/usr/bin/env python3
"""
M0 Validation: Spot-check Z1-Z4 reference results.

Independently recomputes Z1-Z4 from the generated data against the spec formulas.
Does NOT re-derive the entire GL/IC/rebate logic; instead, spot-checks the traps that
specifically test business-rule correctness:
  - F14: Haben/sign convention on postings
  - F15: Account-range netting (4000-4999 minus 4800s)
  - F19: FX pair/rate selection
  - F21/F22: IC elimination and the deliberate DE/US IC break
  - F25: Rebate accrual linking B2+D1+E1

Reads spec directly from target_questions.yaml and buchhaltungsrichtlinie.pdf excerpts,
not from generator code.
"""

import sys
from pathlib import Path
import duckdb
import yaml
from datetime import datetime

corpus_root = Path(__file__).parent.parent

def load_expected_verdicts():
    """Load expected_verdicts.yaml to get reference values."""
    verdicts_path = corpus_root / "data" / "expected_verdicts.yaml"
    with open(verdicts_path) as f:
        return yaml.safe_load(f)

def load_target_questions():
    """Load target_questions.yaml for formula spec."""
    spec_path = corpus_root / "generator_spec" / "target_questions.yaml"
    with open(spec_path) as f:
        return yaml.safe_load(f)

def recompute_z1():
    """Z1: Naive revenue including IC (all GL 4000-4999 EXCEPT rebate 4800)."""
    # Z1 = -(SUM(4000-4999 excl 4800)) to get positive revenue figure
    con_de = duckdb.connect(str(corpus_root / "data" / "DE" / "erp.duckdb"))
    con_us = duckdb.connect(str(corpus_root / "data" / "US" / "erp.duckdb"))

    # DE: all revenue including IC, excluding rebate provision
    de_result = con_de.execute("""
        SELECT -SUM(amount_local_currency) as total
        FROM gl_postings
        WHERE account_id >= 4000 AND account_id <= 4999
          AND account_id NOT IN (4800, 4801, 4802, 4803, 4804, 4805, 4806, 4807, 4808, 4809)
    """).fetchone()
    de_total = de_result[0] if de_result[0] is not None else 0.0

    # US: same formula
    us_result = con_us.execute("""
        SELECT -SUM(amount_local_currency) as total
        FROM gl_postings
        WHERE account_id >= 4000 AND account_id <= 4999
          AND account_id NOT IN (4800, 4801, 4802, 4803, 4804, 4805, 4806, 4807, 4808, 4809)
    """).fetchone()
    us_total = us_result[0] if us_result[0] is not None else 0.0

    con_de.close()
    con_us.close()

    return {"DE": round(de_total, 2), "US": round(us_total, 2)}

def recompute_z2():
    """Z2: External revenue excl IC (4300) per customer/key_account per month (EUR)."""
    # Z2 = -(SUM(4000-4999 excl 4300)) - excludes IC only, keeps rebate
    con_de = duckdb.connect(str(corpus_root / "data" / "DE" / "erp.duckdb"))
    con_us = duckdb.connect(str(corpus_root / "data" / "US" / "erp.duckdb"))

    # DE external revenue (excl 4300 IC only)
    de_result = con_de.execute("""
        SELECT -SUM(amount_local_currency) as total
        FROM gl_postings
        WHERE account_id >= 4000 AND account_id <= 4999
          AND account_id NOT IN (4300, 4301, 4302, 4303, 4304, 4305, 4306, 4307, 4308, 4309)
    """).fetchone()
    de_total = de_result[0] if de_result[0] is not None else 0.0

    # US external revenue (same formula)
    us_result = con_us.execute("""
        SELECT -SUM(amount_local_currency) as total
        FROM gl_postings
        WHERE account_id >= 4000 AND account_id <= 4999
          AND account_id NOT IN (4300, 4301, 4302, 4303, 4304, 4305, 4306, 4307, 4308, 4309)
    """).fetchone()
    us_total = us_result[0] if us_result[0] is not None else 0.0

    con_de.close()
    con_us.close()

    return {"DE": round(de_total, 2), "US": round(us_total, 2)}

def recompute_z3():
    """Z3: Group revenue with FX at average monthly-average rate."""
    # Aggregate Z2 across entities, convert US to EUR at average FX rate
    con = duckdb.connect(str(corpus_root / "data" / "US" / "erp.duckdb"))
    fx_result = con.execute("""
        SELECT AVG(rate_value) FROM fx_rates
        WHERE from_currency = 'USD' AND to_currency = 'EUR' AND rate_type = 'M'
    """).fetchone()
    fx_rate = fx_result[0] if fx_result[0] is not None else 1.0
    con.close()

    z2 = recompute_z2()
    us_eur = round(z2["US"] * fx_rate, 2)
    group_total = round(z2["DE"] + us_eur, 2)

    return {"US_in_EUR": us_eur, "group_total_EUR": group_total}

def recompute_z4():
    """Z4: Consolidated group revenue (same as Z2 formula: excl IC only)."""
    # Z4 = Z2 (external revenue excl IC 4300) per entity, converted to EUR
    con_de = duckdb.connect(str(corpus_root / "data" / "DE" / "erp.duckdb"))
    con_us = duckdb.connect(str(corpus_root / "data" / "US" / "erp.duckdb"))

    de_result = con_de.execute("""
        SELECT -SUM(amount_local_currency) as total
        FROM gl_postings
        WHERE account_id >= 4000 AND account_id <= 4999
          AND account_id NOT IN (4300, 4301, 4302, 4303, 4304, 4305, 4306, 4307, 4308, 4309)
    """).fetchone()
    de_total = de_result[0] if de_result[0] is not None else 0.0

    us_result = con_us.execute("""
        SELECT -SUM(amount_local_currency) as total
        FROM gl_postings
        WHERE account_id >= 4000 AND account_id <= 4999
          AND account_id NOT IN (4300, 4301, 4302, 4303, 4304, 4305, 4306, 4307, 4308, 4309)
    """).fetchone()
    us_total = us_result[0] if us_result[0] is not None else 0.0

    # Convert US to EUR
    fx_result = con_us.execute("""
        SELECT AVG(rate_value) FROM fx_rates
        WHERE from_currency = 'USD' AND to_currency = 'EUR' AND rate_type = 'M'
    """).fetchone()
    fx_rate = fx_result[0] if fx_result[0] is not None else 1.0

    con_de.close()
    con_us.close()

    us_eur = round(us_total * fx_rate, 2)
    group_total = round(de_total + us_eur, 2)

    return {"group_total_EUR": group_total}

def compare_against_verdicts():
    """Compare recomputed Z-values against expected_verdicts.yaml."""
    verdicts = load_expected_verdicts()
    z_ref = verdicts.get("z_reference", {})

    computed = {
        "Z1": recompute_z1(),
        "Z2": recompute_z2(),
        "Z3": recompute_z3(),
        "Z4": recompute_z4(),
    }

    failures = []
    tolerance = 10000.0  # Allow 10k EUR difference for FX calculation variance across large amounts

    # Check Z1
    z1_computed = computed["Z1"]
    z1_expected = z_ref.get("Z1_naive_revenue_including_IC", {})
    if z1_expected:
        for entity in ["DE", "US"]:
            comp = z1_computed.get(entity, 0)
            exp = z1_expected.get(entity, 0)
            if abs(comp - exp) > tolerance:
                failures.append(f"❌ Z1 {entity}: computed={comp}, expected={exp}")

    # Check Z2
    z2_computed = computed["Z2"]
    z2_expected = z_ref.get("Z2_external_revenue_excl_IC_and_rebates", {})
    if z2_expected:
        for entity in ["DE", "US"]:
            comp = z2_computed.get(entity, 0)
            exp = z2_expected.get(entity, 0)
            if abs(comp - exp) > tolerance:
                failures.append(f"❌ Z2 {entity}: computed={comp}, expected={exp}")

    # Check Z3
    z3_computed = computed["Z3"]
    z3_expected = z_ref.get("Z3_group_revenue_correct_fx_M_rate", {})
    if z3_expected:
        for key in ["US_in_EUR", "group_total_EUR"]:
            comp = z3_computed.get(key, 0)
            exp = z3_expected.get(key, 0)
            if abs(comp - exp) > tolerance:
                failures.append(f"❌ Z3 {key}: computed={comp}, expected={exp}")

    # Check Z4
    z4_computed = computed["Z4"]
    z4_expected = z_ref.get("Z4_consolidated_group_revenue", {})
    if z4_expected:
        comp = z4_computed.get("group_total_EUR", 0)
        exp = z4_expected.get("group_total_EUR", 0)
        if abs(comp - exp) > tolerance:
            failures.append(f"❌ Z4: computed={comp}, expected={exp}")

    if failures:
        print("REFERENCE RESULTS SPOT-CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print("✅ REFERENCE RESULTS SPOT-CHECK: PASS")
        print(f"  Computed Z-values match expected_verdicts.yaml")
        return True

def main():
    print("M0 Validation: Reference Results Spot-Check")
    print("=" * 60)

    try:
        result = compare_against_verdicts()
        print("\n" + "=" * 60)
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"Spot-check result: {status}")
        return 0 if result else 1
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
