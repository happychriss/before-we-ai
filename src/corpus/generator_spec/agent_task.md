# M0 Corpus Generator — Task for External Agent

## Context

You are building the **M0 milestone** for `before-we-ai`: a frozen, seeded fixture corpus for the finance domain with 29 intentional traps (F1–F29, grouped into 7 trap classes K1–K7) that a downstream tool must handle correctly.

**Your deliverable:**
- A seeded Python generator that reads the spec layer (`generator_spec/*.yaml` in this folder) and produces a fixture corpus
- First-cut output with seed=0 in `/workspace/raw-training-data/`
- `expected_verdicts.yaml` (ground truth) computed from the actual generated data, never hand-written
- Cross-validation: self-tests (balance-closes, subledger=GL, IC symmetry) before freezing
- Seed stability testing across 3+ seeds to prove verdicts are deterministic

## Inputs (read from this folder: `generator_spec/`)

1. **`sources_manifest.yaml`** — all 23 sources (A1–E4, D9) with properties and trap involvement
2. **`trap_classes.yaml`** — K1–K7 definitions and tool consequences
3. **`target_questions.yaml`** — Z1–Z4 business questions and reference-result formulas
4. **`roles.yaml`** — finance role definitions
5. **`generator_contract.md`** — the full interface contract (read this carefully)

## What to Generate

**Data layout** (per `generator_contract.md`):
```
/workspace/raw-training-data/
├── data/
│   ├── DE/erp.duckdb          # Entity DE (EUR), 24 months, ~4,000 invoices, seeded traps
│   ├── US/erp.duckdb          # Entity US (USD), parallel structure
│   ├── *.xlsx, *.csv, *.pdf    # Master data, documents, decoys (per sources_manifest)
│   ├── noise/                  # E4 non-relevant documents
│   ├── tell_statements.yaml    # F28/F29 domain statements
│   └── expected_verdicts.yaml  # GROUND TRUTH — computed, not authored
├── generator_seed_0.py         # your generator code with seed=0 hardcoded (for reproducibility)
├── generator.py                # your generator as a parameterized CLI: `python generator.py --seed=<N>`
└── validation_cross_check.log  # output of your self-validation
```

## Generator Workflow (Seeded, Deterministic)

### 1. Accept seed parameter
Integer (0, 1, 2, …) to control randomness and ensure reproducibility.

### 2. Generate transaction axis only:
- **Orders (A1):** random customers, sales reps, materials, quantities, dates
- **Invoices (A2):** partial deliveries, reversals per trap specs
- **Credit notes (A3):** legacy 2024-Q1, future 2024-Q3 per F4
- **Customer master (B1):** DE/US split, hierarchy per F6
- **Materials (B2):** hierarchy-as-positional-string per F7
- **Sales reps (B5):** territory via PLZ ranges per F9, contacts
- **CRM activities (C1):** post-exit activities per F10, customer ref inconsistencies per F11/F12
- **GL postings (D2–D4, D6):** generated via posting rules (see #3)
- **FX rates (D5), IC entries (D8):** generated via posting rules
- **Rebate accrual (B2+E1):** per F25 complexity
- **Open items (AR, D10):** aging per F24

### 3. Derive GL/IC/rebate/FX via declared posting rules
Do NOT manually code GL balances; derive them from transaction rules:

- **For every invoice:** post to revenue account (4000–4999, exclude 4800s per Z2), AR
- **For every credit note:** post to contra-revenue, post to F4 legacy credit location
- **For every rebate:** post accrual (4800, Haben = negative per F15), AR adjustment
- **For every IC transaction:** post to revenue 4000–4999 AND IC 9xxxx per F21/F22
- **For every FX revaluation:** post unrealized gain/loss, F5 account mapping per Z2
- **Balance sheet at month-end:** opening_balances + postings + closing
- **Chart of accounts (D7):** D0-D1, includes 4000–4999 (revenue), 4800 (rebate), 9xxxx (IC)

### 4. Self-validate before freezing:
- ✅ Balance closes per entity/period (Soll = Haben)
- ✅ Subledger (AR) = GL (account 1200)
- ✅ IC symmetry: DE posts to 9999 must equal US posts to 9999 with inverse sign
- ✅ All traps F1–F29 are present in the data (coded as metadata tags, not as bugs in the SQL)
- If any check fails, stop and report the failure clearly

### 5. Compute `expected_verdicts.yaml` from the actual data:
- Iterate over every trap ID (F1–F29, plus any extras you add)
- For each trap: extract the actual records involved, classify the expected claim status (inferred | tested | contradicted | unresolved | business-confirmed)
- For Z1–Z4: compute actual values from the generated GL/AR/plan data using the formulas in `target_questions.yaml`
- Document any assumptions (e.g., "Z2 assumes postings on document_date, not posting_date") in `expected_verdicts.yaml`
- **Do NOT hand-write verdicts; derive them programmatically**

### 6. Output a log of all self-checks
Save to `validation_cross_check.log` with:
- ✅/❌ for each check
- Sample row counts per table
- Balance-close details (per-entity, per-period diffs if any)
- Z1–Z4 computed values

## Seed Stability (Critical)

**After generating with seed=0 and validating:**

1. Re-run the generator with seeds 1, 2, 3 (can be the same data structure, different random numbers for customer IDs, quantities, dates within the same logical structure)
2. For each seed, verify:
   - ✅ All trap verdicts remain identical (same F-ID → same expected_status)
   - ✅ All Z1–Z4 reference_results remain identical (or document why they differ)
   - If verdicts change, the traps are not stable; document and fix
3. Produce `seed_stability_report.txt` showing all 3 runs' verdicts and their identity

## Extra Traps & Documentation (Optional, but Encouraged)

The harness is trap-class-generic (K1–K7), so **additional traps beyond F1–F29 are welcome** if documented with the same rigor:

- Invent F30, F31, etc. if you see a useful variant of K1–K7
- For each: document the trap ID, trap_class (K1–K7), sources involved, and the expected_verdicts entry
- Add it to your generated `expected_verdicts.yaml` with full metadata
- Document why this trap adds value (e.g., "F30: K1 variant—invoice with matching GL posting but wrong account range")
- The validation harness will automatically check your new traps alongside the official ones

## Blind Traps Configuration (Internal to Generator)

- Define 2–3 blind traps in your generator's own config (a separate YAML or dict, NOT in `expected_verdicts.yaml` and NOT in this repo)
- Tag them with a K-class (K1–K7) in `expected_verdicts.yaml` so the harness can validate them, but do NOT describe what makes them traps
- This is how the downstream M1+ tool gets tested on *unexpected* trap patterns
- Example: `{id: "BLIND_1", trap_class: K4, sources: ["B2", "D9"], expected_status: "inferred"}` — the harness checks it, you know what it is, but the M1+ implementation won't

## Output Checklist

```
/workspace/raw-training-data/
├── data/
│   ├── DE/erp.duckdb          ✅ All tables per sources_manifest
│   ├── US/erp.duckdb          ✅ All tables per sources_manifest
│   ├── kunden_migration.xlsx   ✅ F5 old→new mapping
│   ├── marketing_grouping.xlsx ✅ F8 grouping
│   ├── kontakte_aussendienst.xlsx ✅ B5 rep contacts
│   ├── buchungen_report.csv    ✅ D9 decoy journal
│   ├── management_report.pdf   ✅ E1
│   ├── rabattvertrag.pdf       ✅ E2
│   ├── buchhaltungsrichtlinie.pdf ✅ E3
│   ├── noise/                  ✅ E4 docs
│   ├── tell_statements.yaml    ✅ F28/F29
│   └── expected_verdicts.yaml  ✅ Computed ground truth (schema per contract)
├── generator.py                ✅ CLI: python generator.py --seed=<N> --output-dir=<path>
├── generator_seed_0.py         ✅ Snapshot with seed=0 for reproducibility
├── validation_cross_check.log  ✅ Self-validation results
└── seed_stability_report.txt   ✅ Seeds 1, 2, 3 verdicts vs. seed 0
```

## Criteria for "Done"

- [ ] All 23 sources present with correct schema per `generator_contract.md`
- [ ] All traps F1–F29 are present and triggered in the data
- [ ] `expected_verdicts.yaml` is fully populated, computed (not hand-written), and conforms to schema
- [ ] Self-validation log shows ✅ for balance-closes, subledger=GL, IC symmetry
- [ ] Seed stability report shows all verdicts identical across seeds 0, 1, 2, 3
- [ ] Any extra traps (F30+) or blind traps are documented per the contract
- [ ] Generator CLI runs: `python generator.py --seed=1 --output-dir=/tmp/test` and produces identical verdicts to seed=0

## When Done

1. Commit your generator code to `/workspace/raw-training-data/` (or keep it separate — this is your sandbox)
2. Place the first-cut output (seed=0) in `/workspace/raw-training-data/data/` with all validation logs
3. Notify: "M0 generator complete. Seed=0 ready. Seed stability report attached. Extra traps: [list]. Blind traps: [count]."
4. The corpus curator will review and move validated output to `/workspace/src/corpus/data/` for freezing

## References

- `generator_contract.md` — full interface specification
- `sources_manifest.yaml` — source definitions and trap involvement
- `trap_classes.yaml` — K1–K7 patterns
- `target_questions.yaml` — Z1–Z4 formulas
- `roles.yaml` — domain role semantics
- `/workspace/README.md` — M0 workflow and architecture
- External spec docs in `/workspace/external-docs/` for domain rules (Testdatensatz v2, Spezifikation v1, etc.)
