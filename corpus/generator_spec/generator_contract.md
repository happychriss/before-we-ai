# Generator Contract — Interface and acceptance criteria for the external seeded generator

## Overview

This document specifies the contract between the generator (built externally by the user)
and the M0 validation harness (built by Claude). The generator accepts configuration
and produces a frozen, validated fixture corpus; the harness validates the results.

**This folder (`generator_spec/`) is read-only from the harness's perspective.** The
generator may consult it to understand what data shapes and trap classes are expected,
but the generator's own code and configuration live outside this repository, in
`/workspace/raw-training-data/`.

---

## Generator inputs

### 1. Configuration file (generator config)

**Location:** `/workspace/raw-training-data/generator_config.yaml` (or equivalent,
chosen by the external builder)

**Required sections:**
- **Seed(s)**: integer seed(s) for reproducibility. Defaults to a single seed; may
  define 3+ seeds for stability testing.
- **Trap parameters**: for each trap F1–F29 (and any documented extras), a flag or
  parameter enabling/configuring its behavior. Example: `F5_enable: true`,
  `F6_threshold_date: 2025-07-01`.
- **Blind trap(s)**: 2–3 trap definitions kept here, not in this repo's
  `generator_spec/`. The harness will not read this file and does not know what
  these are. They will appear in `expected_verdicts.yaml` tagged with a trap class
  (K1–K7), and the harness will validate them generically without knowing specifics.

### 2. Reference data (this repo's `generator_spec/`)

- `sources_manifest.yaml`: what data sources must be generated and their properties
- `trap_classes.yaml`: what each trap class means and what tool behavior it forces
- `target_questions.yaml`: Z1–Z4 definitions and reference-outcome contracts
- `roles.yaml`: semantic role definitions for the finance domain

---

## Generator outputs

All outputs go to `/workspace/src/corpus/data/` once curated/accepted by the user.
The generator first produces them in `/workspace/raw-training-data/` for experimentation.

### 1. Data files (one per source in sources_manifest.yaml)

**Per-entity ERP databases:**
- `data/DE/erp.duckdb`: DuckDB file with all A, B, C, D tables for the DE entity (EUR)
- `data/US/erp.duckdb`: DuckDB file with all A, B, C, D tables for the US entity (USD)

**Master data and cross-entity files:**
- `data/kunden_migration.xlsx`: F5 old→new customer ID mapping (DE)
- `data/marketing_grouping.xlsx`: F8 competing product grouping (Excel, as in the source)
- `data/kontakte_aussendienst.xlsx`: B5 rep contact list (Excel, as in the source)
- `data/buchungen_report.csv`: D9 decoy journal export (CSV, UTF-8, as in the source)

**Documents:**
- `data/management_report.pdf`: E1 (real or synthetic; must have quarterly figures + chart)
- `data/rabattvertrag.pdf`: E2 (rebate contract policy)
- `data/buchhaltungsrichtlinie.pdf`: E3 (accounting policy — the key to resolving F14/F15/F19)
- `data/noise/`: E4 folder with non-relevant documents (travel policy, supplier catalog, old press release with divested-unit revenue)

**Tell statements:**
- `data/tell_statements.yaml`: YAML file with a list of scripted domain statements to be played
  via the `tell` mechanism. Example:
  ```yaml
  statements:
    - text: "Wir beliefern nur Apotheken und Großhändler."
      source: sales_team
      trap_id: F28
    - text: "Geschäftsjahr läuft Mai bis April."
      scope: US_entity
      trap_id: F29
  ```

**Ground truth:**
- `data/expected_verdicts.yaml`: See schema below.

### 2. Table layouts (inside DE/erp.duckdb and US/erp.duckdb)

Each entity database must contain these tables (all field names and types per the source spec):

**A. Sales chain:**
- `orders`: order_date, customer_id, sales_rep_id, document_currency, status
- `invoices`: (header) document_number, customer_id, amount_doc_currency, amount_local_currency, document_exchange_rate, order_reference, invoice_date
- `invoices_items`: (line items) invoice_id, material_id, quantity, amount_doc_currency
- `credit_notes_legacy`: (DE only, through 2024-06) document_number, invoice_reference, amount

**B. Master data:**
- `customers`: customer_id, customer_name, postal_code, (duplicate_flag optional)
- `customer_hierarchy`: customer_id, key_account_id, valid_from, valid_to (versioned)
- `materials`: material_id, description_de, description_en, product_hierarchy_string
- `material_hierarchy`: material_id, hierarchy_level_1, hierarchy_level_2, hierarchy_level_3
- `sales_reps`: rep_id, rep_name, territory_id, exit_date
- `territory_plz`: territory_id, plz_from, plz_to

**C. CRM:**
- `crm_activities`: activity_date, rep_id, customer_reference, activity_type
- `crm_notes`: note_text

**D. Finance (per entity):**
- `gl_postings`: account_id, cost_center_id, profit_center_id, document_reference, posting_date, document_date, amount_doc_currency, amount_local_currency (Haben negative)
- `chart_of_accounts`: account_id, account_name_de, pnl_or_balance_sheet, account_range_group
- `cost_centers`: cost_center_id, cost_center_name
- `profit_centers`: profit_center_id, profit_center_name, valid_from, valid_to (versioned)
- `projects`: project_id, project_name, budget_amount, start_date, Q3_2025_migration (optional flag)
- `fx_rates`: rate_date, from_currency, to_currency, rate_type ('M' or 'B'), rate_value
- `plan`: profit_center_id, plan_month, revenue_plan_amount, expense_plan_amount
- `opening_balances`: account_id, period, balance_amount
- `ar_open_items`: open_item_id, invoice_reference, payment_reference, amount

**D (Intercompany):**
- `intercompany`: transaction_id, from_entity, to_entity, customer_id (9xxxx), account_id, amount_local_currency

---

## `expected_verdicts.yaml` schema

```yaml
claims:
  - id: F1                             # trap id, must match sources_manifest.yaml
    trap_class: K6
    sources: [A1_orders]
    expected_status: inferred          # inferred | tested | contradicted | unresolved | business-confirmed
    expected_evidence_types: [probe_result, document_anchor]
    probe_verdicts:
      orphan_probe: has_orphans        # verdict for each probe relevant to this trap
    note: "Open orders (no invoice) are legitimate; fachfrage expected, not error."

recall_set: [F1, F2, F3, ...]          # claims that MUST exist in expected_verdicts
                                        # after generator runs (completeness check)
deny_set: [F26, ...]                   # claims that MUST NOT be promoted past inferred
                                        # (e.g., poisoned anchors, documented orphans)

reference_results:
  Z1:
    value: null                         # will be populated from generated data
    unit: days
    grain: sales_rep_id × quarter
    formula_ref: "target_questions.yaml#Z1"
    
  Z2:
    value: null
    unit: EUR
    grain: customer_id × key_account_id × month
    formula_ref: "target_questions.yaml#Z2"
    
  Z3:
    value: null
    unit: EUR
    grain: profit_center_id × month
    formula_ref: "target_questions.yaml#Z3"
    
  Z4:
    invariant: balance_sheet_closes
    per_entity_period:
      DE: true
      US: true
    formula_ref: "target_questions.yaml#Z4"
```

### Notes on `expected_verdicts.yaml`:
- **Every claim in `recall_set` must have an entry in `claims`.**
- **Every claim in `deny_set` must also have an entry; its `expected_status` should be `inferred`.**
- **Additional traps beyond F1–F29 are welcome** if they improve coverage. Each must have:
  - A unique `id` (e.g., F30, F31)
  - A `trap_class` (K1–K7)
  - All other fields as above
  - An entry in `recall_set` and/or `deny_set` as appropriate
  - **Not an entry in this repo's `sources_manifest.yaml`** (that file is fixed); the extra
    trap should be described in the `note` field of its `expected_verdicts.yaml` claim.
- **Do not hardcode numeric reference results** (e.g., Z1=42, Z2=150000).
  Reference numbers must be recalculated from the actually-generated data as part of the
  generator's own self-validation (balance-closes, subledger=GL checks).

---

## Generator workflow and self-validation

1. **Accept seed and trap parameters.**
2. **Generate only the transaction axis** (orders → invoices → payments → GL ledger entries).
   Do not pre-aggregate. Do not consolidate or normalize.
3. **Derive all financial data via declared posting rules:**
   - For each sales transaction, create a GL posting to the revenue account (sign: Haben negative)
   - Derive IC transactions between entities using the 9xxxx customer range
   - Apply rebate accrual rules per F25 (2% threshold per customer group, monthly accrual)
   - Apply the currency conversion strategy (monthly-average rates per policy)
4. **Run self-checks before freezing:**
   - Verify debits = credits per entity × period (balance sheet closes)
   - Verify subledger AR totals = GL AR control totals
   - Verify IC transactions are symmetric (if DE posts to US, US must have a corresponding entry)
   - Compute Z1–Z4 reference results from the generated data
5. **Emit `expected_verdicts.yaml`** with all claims, verdicts, and reference results populated
   from the data (not hardcoded).
6. **Emit seed-stability report:** if running multiple seeds, verify that trap class verdicts
   and reference results are stable across seed variation (only data grain changes, not verdict).

---

## Acceptance criteria (run by the validation harness)

- **Trap class integrity:** For each K1–K7, all claims tagged with that class pass their class-level
  assertions (e.g., K6 claims must not resolve to `contradicted`).
- **Spot-checks on business-rule correctness (F14/F15/F19/F21/F22/F25):** Recomputed independently
  from the spec's prose, not from the generator's code, to catch semantic errors.
- **Invariant probes (K5):** Z4 balance-sheet-closes must hold per entity × period, or the data
  itself is broken (not a valid corpus).
- **Recall and deny sets:** All claims in `recall_set` exist in `expected_verdicts.yaml`.
  All claims in `deny_set` stay at `inferred` (or lower) status.
- **Seed stability (3+ seeds minimum):** Every trap's verdict and every Z1–Z4 reference result
  must be identical across seeds (only per-record data varies, not aggregate outcomes).

If all checks pass, the corpus is frozen (git tag) and ready for M1.

---

## Blind traps (generator config only, never in this repo)

The generator's own config defines 2–3 traps that are withheld from this specification.
These serve as "unknown unknowns" to test the M1+ implementation itself.

- Location: generator_config.yaml (or equivalent, inside `/workspace/raw-training-data/`)
- Constraint: They must still be tagged with an existing K-class (K1–K7) in
  `expected_verdicts.yaml` so the harness can validate them generically.
- Constraint: This file or any blind-trap reference must **never** appear in this repo's
  `src/corpus/generator_spec/` folder. If the harness reads about a blind trap here, it
  defeats the blind trap's purpose (testing M1+ against unknown traps).
- Example: A blind trap might be a subtle FX or timing issue the owner anticipates the
  M1+ implementation won't catch—or one that tests whether the tool handles a realistic
  but undocumented business rule correctly.

---

## Version history

- v1: Initial contract, based on Korpus v2 spec (before-we-ai-testdatensatz-finance-anforderungen.md)
