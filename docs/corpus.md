# Corpus — confirmed facts (M0, frozen)

Frozen 2026-07-11, git tag `m0-corpus-v1`. Never regenerate or edit; the corpus is
the fixed answer key for all later milestones.

## Layout

- Data: `src/corpus/data/` — DE/US `erp.duckdb` (per entity), real `.xlsx` (merged
  headers, German decimal commas), Latin-1 `.csv`, `.pdf`, text notes,
  `expected_verdicts.yaml`
- Validation harness: `src/corpus/validation/` (all checks pass); interactive HTML
  report via `build_html_report.py`
- Generator archive: `src/raw-training-data/` (generator.py, seed-stability report)

## Traps

32 traps: F1–F29 + BLIND_1/2/3 (owner-held). Classes K1–K8; K8 = tell statements,
generator-added, not in the spec catalog.

## Schema gotchas

- GL uses **signed amounts**: `amount_local_currency`, negative = Haben — no
  separate S/H column. Account column is `account_id` (BIGINT), not `account`.

## Z-formulas (target questions)

- Z1 = -(SUM accounts 4000–4999 excl 4800)
- Z2 = -(SUM accounts 4000–4999 excl 4300 IC)
- Z3/Z4 = Z2 in EUR

## Accepted tolerances & expected exceptions (documented, not bugs)

- F20 causes AR≠GL — 100k tolerance on subledger_equals_gl
- Z3/Z4 FX-averaging variance ~8.2k EUR (0.012%) vs generator — 10k tolerance
  (generator's FX method not exactly reproduced; accepted as spot-check)
- US:2024-06 imbalance is F22's intentional IC break (probe finds doc `IC-2024-06`,
  50k)
