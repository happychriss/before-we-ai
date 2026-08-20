# Generator Specification — M0 Corpus

This folder contains the **specification layer** for the M0 fixture corpus: machine-readable contracts that define what the external generator must build and what the validation harness must check.

## Files

- **`agent_task.md`** — START HERE. Complete task specification for the external agent building the generator.
- **`sources_manifest.yaml`** — All 23 sources (A1–E4, D9) with properties, formats, and trap involvement.
- **`trap_classes.yaml`** — K1–K7 epistemic failure patterns and their tool consequences.
- **`target_questions.yaml`** — Z1–Z4 business questions defining correctness; reference-result formulas.
- **`roles.yaml`** — Finance domain role definitions (v1).
- **`generator_contract.md`** — Full interface contract: inputs, outputs, schemas, self-validation requirements.

## Who Reads This

1. **External agent** — reads `agent_task.md` to understand what to build, then references the YAML specs and `generator_contract.md` for exact requirements.
2. **Validation harness** — reads `trap_classes.yaml`, `target_questions.yaml`, and `generator_contract.md` to know what to check.
3. **Corpus curator** — uses this folder to understand what output is expected before moving data to `src/corpus/data/`.

## Output

The external agent produces:
- `/workspace/raw-training-data/data/` — fixture corpus (DuckDB, Excel, CSV, PDF, YAML)
- `/workspace/raw-training-data/generator.py` — seeded CLI generator
- `/workspace/raw-training-data/validation_cross_check.log` — self-validation results
- `/workspace/raw-training-data/seed_stability_report.txt` — seed reproducibility verification

Once curated and validated, the corpus moves to `/workspace/src/corpus/data/` and is git-tagged.

## How to Update This Spec

If you discover a requirement gap or contradiction:
1. Update the YAML files or markdown files here
2. Notify the external agent of the change
3. Re-run the generator against the updated spec
4. Re-validate

**Do NOT add new source entries, trap classes, or target questions without explicit justification.** This spec is locked once the generator starts; mid-build changes create drift and confusion.
