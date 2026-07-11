# M0 — Corpus: logic, validation, and ground truth

This module is the **M0 milestone deliverable** for before-we-ai: a frozen, validated
fixture corpus for the finance domain, with explicit trap catalogues, target questions,
and independent validation that everything works correctly.

**What is not here:** The generator itself (external agent's work), the source data
(external generator's output, moved here once curated). **What is here:** The spec
that both build against, and the validation harness that grades the results.

---

## Folder structure

```
corpus/
├── generator_spec/              # Specifications (logic layer) — read by both generator and harness
│   ├── sources_manifest.yaml    # A1-E4 + D9: sources, properties, traps
│   ├── trap_classes.yaml        # K1-K7: epistemic failure patterns
│   ├── target_questions.yaml    # Z1-Z4: business questions defining correctness
│   ├── roles.yaml               # Domain role definitions (finance v1)
│   ├── generator_contract.md    # Interface contract for the external generator
│   └── README.md                # (This file)
│
├── data/                        # Fixture corpus — curated, frozen, version-controlled
│   ├── DE/erp.duckdb            # Entity DE (EUR) with all tables
│   ├── US/erp.duckdb            # Entity US (USD) with all tables
│   ├── *.xlsx, *.csv, *.pdf     # Excel, CSV, documents (as per sources_manifest)
│   ├── noise/                   # E4: non-relevant documents
│   ├── tell_statements.yaml     # F28/F29: scripted domain statements
│   └── expected_verdicts.yaml   # Ground truth — computed, not authored
│
└── validation/                  # Harness — independent validation of the corpus
    ├── recompute_reference_results.py  # Spot-checks Z1-Z4 vs ground truth
    ├── check_trap_classes.py           # Generic K1-K7 assertions
    ├── check_invariants.py             # K5: balance-closes, subledger=GL, IC symmetry
    ├── seed_stability.py               # Re-run generator across seeds, diff results
    ├── report.py                       # Render Markdown validation report
    └── __init__.py
```

---

## What to do now

### 1. External agent builds the generator

Location: `/workspace/raw-training-data/`

- Build a seeded Python script that reads `generator_spec/` (this repo's files)
  and generates a fixture corpus following the interface in `generator_contract.md`.
- Experiment/iterate in `raw-training-data/`; commit nothing there.
- When the generator is ready, run it with seed=0 to produce the first corpus output.

### 2. Curator reviews and moves data to `corpus/data/`

Once the external agent's first-cut output is ready:
- Run all generators output to `/workspace/raw-training-data/` first
- Copy/move the output to `/workspace/src/corpus/data/` once you've reviewed it
- Verify that `expected_verdicts.yaml` is present and conforms to the schema

### 3. Validation harness runs

The harness will:
- Load `generator_spec/*.yaml` to understand what to expect
- Query `data/DE/erp.duckdb` and `data/US/erp.duckdb` using DuckDB SQL
- Read `.xlsx` and `.csv` files in place (no pre-consolidation)
- Spot-check F14/F15/F19/F21/F22/F25 business rules against the spec prose
- Verify K1-K7 trap classes are handled correctly
- Verify K5 invariants hold
- Run `seed_stability.py` across 3+ seeds to ensure verdicts are stable
- Render `corpus-validation-report.md`

All validation output goes to `validation/`.

### 4. Git-tag the corpus

Once validation is green:
```bash
cd /workspace/src
git add corpus/
git commit -m "M0: freeze fixture corpus (seed=0, traps F1-F29 + [blindtraps])"
git tag -a m0-corpus-v1 -m "M0 fixture corpus frozen for M1-M8 validation"
```

---

## How to run the validation harness

```bash
cd /workspace/src/corpus/validation

# Run all checks and generate report
python report.py

# Or run individual checks
python recompute_reference_results.py
python check_trap_classes.py
python check_invariants.py
python seed_stability.py
```

Output: `validation/corpus-validation-report.md` — human-readable pass/fail per trap class,
Z1-Z4 spot-check results, seed stability report.

---

## Design principles

1. **Logic is domain-agnostic, data is domain-specific.** K1-K7 trap classes and the validation
   methodology are reusable for any future domain; Z1-Z4 are finance-specific "what correctness means"
   and would be redefined for a logistics or healthcare corpus.

2. **Validation is trap-class-generic, not F-ID-specific.** The harness checks "do all K6 claims
   avoid `contradicted`" rather than "does F1 specifically have verdict X"—this automatically
   validates the owner's blind traps without ever seeing what they are.

3. **Spot-checks read the spec prose, not the generator code.** F14/F15/F19/F21/F22/F25 are
   re-derived directly from `target_questions.yaml` and `buchhaltungsrichtlinie.pdf`, not from
   the generator's internal logic, so a shared misreading between harness and generator won't
   pass both undetected.

4. **DuckDB is the execution engine, not the storage format.** `data/` stays heterogeneous
   (native DuckDB per entity, real `.xlsx`/`.csv`, real PDFs)—the harness queries these sources
   the same way the M1+ tool will, exercising the same read-paths and normalization concerns.

---

## Key files to understand the corpus

- **sources_manifest.yaml**: Start here to understand what data is generated and where.
- **trap_classes.yaml**: Read this to understand the seven epistemic failure patterns and their
  tool consequences.
- **target_questions.yaml**: Defines Z1-Z4 and the business rules (F14/F15/F19/etc.) that matter most.
- **generator_contract.md**: The interface between external build and harness; all requirements.
- **expected_verdicts.yaml** (once populated by the generator): Ground truth—the answer key against
  which M1+ will be validated.

---

## Traps: known vs. blind

**F1-F29 + documented extras:** Listed in `sources_manifest.yaml`, discoverable in this repo,
validated by the harness generically per trap class. The external agent may add more documented
traps for extra coverage; each must have an id, trap_class (K1-K7), and an entry in
`expected_verdicts.yaml`.

**Blind traps (2-3, withheld):** Defined in the generator's own config (inside
`/workspace/raw-training-data/`), not in this repo. They're tagged with a K-class in
`expected_verdicts.yaml` so the harness checks them, but the harness never sees the specifics.
This is the mechanism by which the corpus tests whether M1+ implementation handles *unexpected*
traps correctly, not just the known ones.

---

## Next steps (M1-M8)

Once this corpus is frozen and validated:
- **M1**: Build the epistemic core (model, state machine, promotion rules)
- **M2**: Ingestion & profiling — test against T1/T9 (normalization), candidate matrix
- **M3**: Probe engine — validate without any LLM (T1-T6, T11, T12)
- **M4**: LLM contracts V1/V2 — hypothesis generation, probe binding (with offline stub mode)
- **M5**: Document pipeline V3 — interpretation with anchor validation (T8 negative cases, real PDF)
- **M6**: Question flow V4 — SQL generation, assumption capture, gap report (T5, T10, gap-list content)
- **M7**: Staleness & replay — M0 corpus frozen, future runs against live data with version tracking
- **M8**: Packaging — `pipx install before-we-ai`, 10-minute quickstart

All M1+ acceptance criteria reference this corpus's traps and reference results.
