#!/usr/bin/env python3
"""
M0 Validation: Trap-class-generic checks (K1-K7).

Validates claims by their trap_class:
- K1 (green-but-wrong): Z1-Z4 must match expected values OR have documented assumption
- K2 (double-counting): subledger complications (not structurally checked here)
- K3 (convention): convention-dependent (not structurally checked here)
- K4 (non-value joins): structural validity (not data-checked here; harness validates via probes)
- K5 (invariants): landscape-bound conditions must hold (checked via invariants harness)
- K6 (legitimate orphans): orphan ≠ error; expect some unresolved claims
- K7 (poisoned anchors): deny_promotion=true, must NOT be promoted past inferred
"""

import sys
from pathlib import Path
import yaml

corpus_root = Path(__file__).parent.parent

def load_expected_verdicts():
    """Load expected_verdicts.yaml."""
    verdicts_path = corpus_root / "data" / "expected_verdicts.yaml"
    with open(verdicts_path) as f:
        return yaml.safe_load(f)

def check_deny_set():
    """Verify claims in deny_set are not promoted past 'inferred'."""
    verdicts = load_expected_verdicts()
    deny_set = verdicts.get("deny_set", [])
    traps = verdicts.get("traps", {})

    failures = []
    for trap_id in deny_set:
        trap = traps.get(trap_id, {})
        if not trap:
            failures.append(f"❌ {trap_id}: in deny_set but not in traps")
            continue

        # deny_promotion should be true
        if not trap.get("deny_promotion", False):
            failures.append(f"❌ {trap_id}: in deny_set but deny_promotion != true")

    if failures:
        print("DENY SET CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print(f"✅ DENY SET CHECK: PASS ({len(deny_set)} claims protected)")
        return True

def check_recall_set():
    """Verify all claims in recall_set are detected."""
    verdicts = load_expected_verdicts()
    recall_set = verdicts.get("recall_set", [])
    traps = verdicts.get("traps", {})

    failures = []
    for trap_id in recall_set:
        trap = traps.get(trap_id, {})
        if not trap:
            failures.append(f"❌ {trap_id}: in recall_set but not in traps")
            continue

        if not trap.get("detected", False):
            failures.append(f"❌ {trap_id}: in recall_set but detected=false")

    if failures:
        print("RECALL SET CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print(f"✅ RECALL SET CHECK: PASS ({len(recall_set)} claims present)")
        return True

def check_k6_orphans():
    """K6 traps (legitimate orphans) should have deny_promotion=false."""
    verdicts = load_expected_verdicts()
    traps = verdicts.get("traps", {})

    failures = []
    k6_count = 0
    for trap_id, trap in traps.items():
        category = trap.get("category", "")
        if "K6" in str(category):
            k6_count += 1
            if trap.get("deny_promotion", False):
                failures.append(f"❌ {trap_id}: K6 orphan but deny_promotion=true (orphans are allowed, should not be denied)")

    if failures:
        print("K6 ORPHANS CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print(f"✅ K6 ORPHANS CHECK: PASS ({k6_count} legitimate orphans)")
        return True

def check_k7_poisoned():
    """K7 traps (poisoned anchors) should have deny_promotion=true."""
    verdicts = load_expected_verdicts()
    traps = verdicts.get("traps", {})

    failures = []
    k7_count = 0
    for trap_id, trap in traps.items():
        category = trap.get("category", "")
        if "K7" in str(category):
            k7_count += 1
            if not trap.get("deny_promotion", False):
                failures.append(f"❌ {trap_id}: K7 poisoned anchor but deny_promotion=false (should protect from promotion)")

    if failures:
        print("K7 POISONED ANCHORS CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print(f"✅ K7 POISONED ANCHORS CHECK: PASS ({k7_count} anchors protected)")
        return True

def check_all_traps_detected():
    """All traps should be detected."""
    verdicts = load_expected_verdicts()
    traps = verdicts.get("traps", {})

    failures = []
    for trap_id, trap in traps.items():
        if not trap.get("detected", False):
            failures.append(f"❌ {trap_id}: detected=false")

    if failures:
        print("ALL TRAPS DETECTED CHECK: FAIL")
        for f in failures:
            print(f"  {f}")
        return False
    else:
        print(f"✅ ALL TRAPS DETECTED CHECK: PASS ({len(traps)} traps)")
        return True

def main():
    print("M0 Validation: Trap-Class-Generic Checks")
    print("=" * 60)

    results = {
        "deny_set": check_deny_set(),
        "recall_set": check_recall_set(),
        "k6_orphans": check_k6_orphans(),
        "k7_poisoned": check_k7_poisoned(),
        "all_detected": check_all_traps_detected(),
    }

    print("\n" + "=" * 60)
    print("Trap-Class Check Results:")
    for check, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {check}: {status}")

    all_passed = all(results.values())
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
