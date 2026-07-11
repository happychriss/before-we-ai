#!/usr/bin/env python3
"""
M0 Validation: Render comprehensive Markdown report.

Runs all validation checks and produces corpus-validation-report.md.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
import yaml

corpus_root = Path(__file__).parent.parent

def run_check(script_name):
    """Run a validation script and return (passed, output)."""
    script_path = corpus_root / "validation" / f"{script_name}.py"
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60
        )
        output = result.stdout + result.stderr
        passed = result.returncode == 0
        return passed, output
    except subprocess.TimeoutExpired:
        return False, f"⏱ TIMEOUT: {script_name}"
    except Exception as e:
        return False, f"❌ ERROR: {e}"

def load_expected_verdicts():
    """Load expected_verdicts.yaml."""
    verdicts_path = corpus_root / "data" / "expected_verdicts.yaml"
    with open(verdicts_path) as f:
        return yaml.safe_load(f)

def count_traps_by_class():
    """Count traps by K-class."""
    verdicts = load_expected_verdicts()
    traps = verdicts.get("traps", {})

    by_class = {}
    for trap_id, trap_info in traps.items():
        category = trap_info.get("category", "")
        classes = [c.strip() for c in str(category).split(",")]
        for kclass in classes:
            if kclass not in by_class:
                by_class[kclass] = []
            by_class[kclass].append(trap_id)

    return by_class

def main():
    print("Generating M0 Corpus Validation Report...")

    # Run all checks
    print("  Running check_trap_classes.py...")
    trap_pass, trap_output = run_check("check_trap_classes")

    print("  Running check_invariants.py...")
    inv_pass, inv_output = run_check("check_invariants")

    print("  Running recompute_reference_results.py...")
    ref_pass, ref_output = run_check("recompute_reference_results")

    # Generate report
    report_path = corpus_root / "validation" / "corpus-validation-report.md"
    verdicts = load_expected_verdicts()
    traps = verdicts.get("traps", {})
    by_class = count_traps_by_class()

    with open(report_path, "w") as f:
        f.write("# M0 Fixture Corpus Validation Report\n\n")
        f.write(f"**Generated:** {datetime.now().isoformat()}\n")
        f.write(f"**Seed:** {verdicts.get('seed', 0)}\n\n")

        # Summary
        f.write("## Summary\n\n")
        all_pass = trap_pass and inv_pass and ref_pass
        status = "✅ **PASS**" if all_pass else "❌ **FAIL**"
        f.write(f"**Overall Status:** {status}\n\n")

        f.write(f"- **Traps:** {len(traps)} (F1-F29 + {len([t for t in traps if t.startswith('BLIND')])} blind)\n")
        f.write(f"- **Trap Classes:** {len(by_class)} (K1-K7, K8)\n")
        f.write(f"- **Recall Set:** {len(verdicts.get('recall_set', []))} claims\n")
        f.write(f"- **Deny Set:** {len(verdicts.get('deny_set', []))} claims protected\n\n")

        # Trap Classes
        f.write("## Trap Classes\n\n")
        for kclass in sorted(by_class.keys()):
            trap_ids = sorted(by_class[kclass])
            f.write(f"### {kclass}\n\n")
            f.write(f"**Count:** {len(trap_ids)}\n\n")
            f.write(f"**Traps:** {', '.join(trap_ids)}\n\n")

        # Trap Details
        f.write("## Trap Inventory\n\n")
        for trap_id in sorted(traps.keys()):
            trap_info = traps[trap_id]
            category = trap_info.get("category", "")
            description = trap_info.get("description", "")
            detected = trap_info.get("detected", False)
            deny = trap_info.get("deny_promotion", False)
            evidence = trap_info.get("evidence", {})

            status = "✅" if detected else "❌"
            deny_mark = " [DENY_PROMOTION]" if deny else ""
            f.write(f"### {trap_id} {status}{deny_mark}\n\n")
            f.write(f"**Category:** {category}\n\n")
            f.write(f"**Description:** {description}\n\n")
            if evidence:
                f.write(f"**Evidence:** {evidence}\n\n")

        # Check Results
        f.write("## Validation Checks\n\n")

        f.write("### Trap-Class Checks\n\n")
        f.write(f"**Status:** {'✅ PASS' if trap_pass else '❌ FAIL'}\n\n")
        f.write("```\n")
        f.write(trap_output)
        f.write("\n```\n\n")

        f.write("### Invariant Checks\n\n")
        f.write(f"**Status:** {'✅ PASS' if inv_pass else '❌ FAIL'}\n\n")
        f.write("```\n")
        f.write(inv_output)
        f.write("\n```\n\n")

        f.write("### Reference Results Spot-Check\n\n")
        f.write(f"**Status:** {'✅ PASS' if ref_pass else '❌ FAIL'}\n\n")
        f.write("```\n")
        f.write(ref_output)
        f.write("\n```\n\n")

        # Z Reference Results
        f.write("## Reference Results (Z1-Z4)\n\n")
        z_ref = verdicts.get("z_reference", {})
        for z_key in ["Z1_naive_revenue_including_IC", "Z2_external_revenue_excl_IC_and_rebates",
                      "Z3_group_revenue_correct_fx_M_rate", "Z4_consolidated_group_revenue"]:
            z_val = z_ref.get(z_key, {})
            f.write(f"### {z_key}\n\n")
            f.write(f"```yaml\n{yaml.dump(z_val, default_flow_style=False)}\n```\n\n")

        # Balance Check
        f.write("## Balance Verification\n\n")
        balance_check = verdicts.get("balance_check", {})
        f.write(f"**All periods balanced (except expected):** {balance_check.get('all_balanced_as_expected', False)}\n\n")
        if balance_check.get("all_periods_balanced_except"):
            f.write(f"**Expected exceptions:** {balance_check['all_periods_balanced_except']}\n\n")

        # Conclusion
        f.write("## Conclusion\n\n")
        if all_pass:
            f.write("✅ **Corpus validation PASSED.** Ready to freeze and tag.\n\n")
            f.write("Next steps:\n")
            f.write("1. Review this report\n")
            f.write("2. `git tag -a m0-corpus-v1 -m \"M0 fixture corpus frozen (seed=0, validated)\"`\n")
            f.write("3. Proceed to M1 development (epistemic core)\n")
        else:
            f.write("❌ **Corpus validation FAILED.** Review checks above and regenerate.\n\n")
            f.write("Issues to address:\n")
            if not trap_pass:
                f.write("- Trap-class checks: review deny_set and K6/K7 logic\n")
            if not inv_pass:
                f.write("- Invariants: balance closes, subledger=GL, IC symmetry\n")
            if not ref_pass:
                f.write("- Reference results: Z1-Z4 spot-checks\n")

    print(f"\n✅ Report generated: {report_path}")
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
