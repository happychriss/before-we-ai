# Corpus — confirmed facts

The finance landscape specifically. What a landscape *is*, the reading rule for
answer keys, and how to add a third: `corpora/README.md`.

**Frozen.** Never regenerate or edit: the corpus is the fixed answer key
every later measurement is scored against, so changing it invalidates the
comparison. Enforced by sha256 per file in `corpora/finance/manifest.yaml` and
`src/tests/corpus_driven/test_corpus_is_frozen.py`. Test infrastructure only —
`src/before_we_ai/` never imports it.

## Layout

- Data: `corpora/finance/data/` — DE/US `erp.duckdb` (per entity), real `.xlsx`
  (merged headers, German decimal commas), Latin-1 `.csv`, `.pdf`, text notes
- Answer key: `corpora/finance/answer-key/expected_verdicts.yaml` — **not read**
- Spec the generator and the harness both build against:
  `corpora/finance/spec/` (sources manifest, trap classes, target questions,
  role definitions)
- Generator archive: `corpora/finance/generator/` — the generator, its
  seed-stability report, and `output-seed-0/`, the raw output before curation.
  **Not read**: it holds the blind traps' definitions.
- Grading harness (code, so it stays in `src/`): `src/corpus/validation/`;
  interactive HTML report via `build_html_report.py`
- Resolve any of it with `corpora.load("finance")` — nothing hardcodes a path.

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
- US:2024-06 imbalance is F22's intentional IC break (check finds doc `IC-2024-06`,
  50k)
