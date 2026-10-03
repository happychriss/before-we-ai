# M0 Fixture Corpus Validation Report

**Generated:** 2026-07-11T20:12:17.822942
**Seed:** 0

## Summary

**Overall Status:** ✅ **PASS**

- **Traps:** 32 (F1-F29 + 3 blind)
- **Trap Classes:** 7 (K1-K7, K8)
- **Recall Set:** 32 claims
- **Deny Set:** 1 claims protected

## Trap Classes

### K1

**Count:** 7

**Traps:** BLIND_1, F14, F19, F22, F27, F5, F6

### K2

**Count:** 4

**Traps:** F2, F20, F3, F4

### K3

**Count:** 8

**Traps:** F14, F15, F17, F18, F19, F21, F25, F27

### K4

**Count:** 9

**Traps:** BLIND_2, F11, F12, F16, F5, F6, F7, F8, F9

### K6

**Count:** 3

**Traps:** F1, F10, F13

### K7

**Count:** 4

**Traps:** BLIND_3, F23, F24, F26

### K8

**Count:** 2

**Traps:** F28, F29

## Trap Inventory

### BLIND_1 ✅

**Category:** K1

**Description:** 3 DE invoices in USD with wrong FX direction (multiplied not divided) - books still close but wrong - K1

**Evidence:** {'count': 3, 'docs': ['DE-INV-0000519', 'DE-INV-0002542', 'DE-INV-0001763']}

### BLIND_2 ✅

**Category:** K4

**Description:** PC_DE_03 profit center has a Q1 2025 validity gap, still referenced by GL postings - K4

**Evidence:** {'row_count': 2}

### BLIND_3 ✅ [DENY_PROMOTION]

**Category:** K7

**Description:** Poisoned acquisition pipeline figure (EUR 1,200,000), no supporting table - K7

### F1 ✅

**Category:** K6

**Description:** Open orders without invoices (legitimate backlog, not an error) - K6 lifecycle

**Evidence:** {'count': 20}

### F10 ✅

**Category:** K6

**Description:** Post-exit CRM activities logged for departed rep R008 - K6 lifecycle

**Evidence:** {'count': 5}

### F11 ✅

**Category:** K4

**Description:** CRM customer_reference containing legacy (pre-migration) IDs - master data drift

**Evidence:** {'count': 68}

### F12 ✅

**Category:** K4

**Description:** CRM customer_reference containing customer name instead of ID

**Evidence:** {'count': 27}

### F13 ✅

**Category:** K6

**Description:** CRM activities referencing prospects not in customer master (PROSPECT_001-005)

**Evidence:** {'count': 5}

### F14 ✅

**Category:** K1,K3

**Description:** Haben (credit) convention stored as negative amounts - documented only in E3 - K1/K3

### F15 ✅

**Category:** K3

**Description:** Revenue definition = 4000-4999 minus 4800-4899 contra accounts - K3 policy

### F16 ✅

**Category:** K4

**Description:** Q3 2025 migration: some GL postings use project_id instead of cost_center_id

**Evidence:** {'count': 1144}

### F17 ✅

**Category:** K3

**Description:** Two FX rate types present: monthly average (M) and spot (B)

### F18 ✅

**Category:** K3

**Description:** Spot (B) rates missing for 2024-03, 2024-09, 2025-06

**Evidence:** {'missing_b_periods': ['2024-03', '2024-09', '2025-06']}

### F19 ✅

**Category:** K1,K3

**Description:** Policy requires monthly average rate (M); M vs B differ 0.5-2% - K1/K3

### F2 ✅

**Category:** K2

**Description:** Partial delivery: one order maps to 2-3 invoices - K2 subledger reconciliation

**Evidence:** {'count': 30}

### F20 ✅

**Category:** K2

**Description:** AR open items with unapplied cash (no invoice ref) or unpaid invoices (no payment ref)

**Evidence:** {'unapplied_cash': 10, 'unpaid_invoices': 655}

### F21 ✅

**Category:** K3

**Description:** IC customers 90001/90002 posted to 4300, excluded from external revenue

**Evidence:** {'count': 201}

### F22 ✅

**Category:** K1

**Description:** Deliberate IC posting break: US 2024-06 missing CR 9002 leg -> imbalance - K1

**Evidence:** {'us_2024_06_sum': 50000.0}

### F23 ✅ [DENY_PROMOTION]

**Category:** K7

**Description:** Q3 2024 revenue figure (EUR 2,847,000) only appears in boxed chart label, not text - K7

### F24 ✅ [DENY_PROMOTION]

**Category:** K7

**Description:** Poisoned prior-year figure (2023 restated revenue) with no supporting table - K7

### F25 ✅

**Category:** K3

**Description:** Rebate accrual: 2% on annual key-account volume > EUR 500,000, posted monthly

**Evidence:** {'accruals': [{'key_account_id': 'KA_001', 'year': 2024, 'annual_revenue': 1490649.16}, {'key_account_id': 'KA_001', 'year': 2025, 'annual_revenue': 1682109.32}, {'key_account_id': 'KA_002', 'year': 2024, 'annual_revenue': 2550465.31}, {'key_account_id': 'KA_002', 'year': 2025, 'annual_revenue': 2242358.24}, {'key_account_id': 'KA_003', 'year': 2024, 'annual_revenue': 1792250.8}, {'key_account_id': 'KA_003', 'year': 2025, 'annual_revenue': 2013447.25}, {'key_account_id': 'KA_004', 'year': 2024, 'annual_revenue': 2114128.26}, {'key_account_id': 'KA_004', 'year': 2025, 'annual_revenue': 2104072.42}, {'key_account_id': 'KA_005', 'year': 2024, 'annual_revenue': 3349507.27}, {'key_account_id': 'KA_005', 'year': 2025, 'annual_revenue': 3100891.91}, {'key_account_id': 'KA_006', 'year': 2024, 'annual_revenue': 1823659.46}, {'key_account_id': 'KA_006', 'year': 2025, 'annual_revenue': 1981598.63}, {'key_account_id': 'KA_007', 'year': 2024, 'annual_revenue': 2675083.61}, {'key_account_id': 'KA_007', 'year': 2025, 'annual_revenue': 3054282.36}, {'key_account_id': 'KA_008', 'year': 2024, 'annual_revenue': 2109972.56}, {'key_account_id': 'KA_008', 'year': 2025, 'annual_revenue': 1897917.08}, {'key_account_id': 'KA_009', 'year': 2024, 'annual_revenue': 3234695.68}, {'key_account_id': 'KA_009', 'year': 2025, 'annual_revenue': 2971678.77}, {'key_account_id': 'KA_010', 'year': 2024, 'annual_revenue': 2557062.66}, {'key_account_id': 'KA_010', 'year': 2025, 'annual_revenue': 2548360.9}]}

### F26 ✅ [DENY_PROMOTION]

**Category:** K7

**Description:** Poisoned anchor: divested-unit press release figure (EUR 8,450,000) - MUST NOT be promoted

**Evidence:** {'deny': True}

### F27 ✅

**Category:** K1,K3

**Description:** buchungen_report.csv decoy: positive amounts + separate S/H indicator, contradicts GL sign convention

### F28 ✅

**Category:** K8

**Description:** Unverifiable tell statement from sales_team re: customer channel restriction

### F29 ✅

**Category:** K8

**Description:** Unverifiable tell statement re: US fiscal year May-April

### F3 ✅

**Category:** K2

**Description:** Reversal pairs: invoice + STORNO with same order reference - K2

**Evidence:** {'count': 15}

### F4 ✅

**Category:** K2

**Description:** Credit note process change: legacy table pre-2024-07, invoice_type=G after - K2

**Evidence:** {'legacy_count': 18, 'new_type_g_count': 63}

### F5 ✅

**Category:** K1,K4

**Description:** Customer ID migration 1101-1105 -> 1201-1205 in 2025 - K1/K4 master data continuity

**Evidence:** {'new_customer_count': 5}

### F6 ✅

**Category:** K1,K4

**Description:** Customer hierarchy versioning for customer 1005 (KA_001 -> KA_002) - K1/K4

**Evidence:** {'rows_for_1005': 2}

### F7 ✅

**Category:** K4

**Description:** Product hierarchy encoded as positional string requiring decode - K4

### F8 ✅

**Category:** K4

**Description:** Competing marketing grouping vs official material hierarchy - K4/K8 grouping conflict

### F9 ✅

**Category:** K4

**Description:** Territory assignment via PLZ range join, not stored directly - K4

## Validation Checks

### Trap-Class Checks

**Status:** ✅ PASS

```
M0 Validation: Trap-Class-Generic Checks
============================================================
✅ DENY SET CHECK: PASS (1 claims protected)
✅ RECALL SET CHECK: PASS (32 claims present)
✅ K6 ORPHANS CHECK: PASS (3 legitimate orphans)
✅ K7 POISONED ANCHORS CHECK: PASS (4 anchors protected)
✅ ALL TRAPS DETECTED CHECK: PASS (32 traps)

============================================================
Trap-Class Check Results:
  deny_set: ✅ PASS
  recall_set: ✅ PASS
  k6_orphans: ✅ PASS
  k7_poisoned: ✅ PASS
  all_detected: ✅ PASS

```

### Invariant Checks

**Status:** ✅ PASS

```
M0 Validation: Invariant Checks
============================================================
✅ MONTHLY BALANCE CHECK: PASS (all periods balanced or in expected_exceptions)
✅ SUBLEDGER=GL CHECK: PASS (F20 mismatch tolerance applied)
✅ IC SYMMETRY CHECK: PASS

============================================================
Invariant Check Results:
  monthly_balance: ✅ PASS
  subledger_gl: ✅ PASS
  ic_symmetry: ✅ PASS

```

### Reference Results Spot-Check

**Status:** ✅ PASS

```
M0 Validation: Reference Results Spot-Check
============================================================
✅ REFERENCE RESULTS SPOT-CHECK: PASS
  Computed Z-values match expected_verdicts.yaml

============================================================
Spot-check result: ✅ PASS

```

## Reference Results (Z1-Z4)

### Z1_naive_revenue_including_IC

```yaml
DE: 50728198.4
US: 25165797.66

```

### Z2_external_revenue_excl_IC_and_rebates

```yaml
DE: 46354368.37
US: 23621377.5

```

### Z3_group_revenue_correct_fx_M_rate

```yaml
US_in_EUR: 21854415.47
group_total_EUR: 68208783.84

```

### Z4_consolidated_group_revenue

```yaml
group_total_EUR: 68208783.84

```

## Balance Verification

**All periods balanced (except expected):** True

**Expected exceptions:** ['US:2024-06']

## Conclusion

✅ **Corpus validation PASSED.** Ready to freeze and tag.

Next steps:
1. Review this report
2. `git tag -a m0-corpus-v1 -m "M0 fixture corpus frozen (seed=0, validated)"`
3. Proceed to M1 development (epistemic core)
