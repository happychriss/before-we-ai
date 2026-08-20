# Corpus harness — the code that grades a landscape

The landscapes themselves moved to `corpora/` (a landscape is data). What is
left here is code: the independent checks that say whether a landscape is
internally sound, and the report that shows it.

**Test infrastructure.** `src/before_we_ai/` never imports any of it, and
`src/tests/unit/test_layering.py` fails if it ever does.

```
src/corpus/
├── validation/
│   ├── check_invariants.py            K5: balance closes, subledger = GL, IC symmetry
│   ├── check_trap_classes.py          generic K1–K8 assertions, per class not per trap
│   ├── recompute_reference_results.py Z1–Z4 re-derived from the spec prose
│   ├── report.py                      renders corpus-validation-report.md
│   └── build_html_report.py           renders the cross-linked HTML version
└── build_hard_document.py             builds data/hard/acme_annual_extract.pdf
```

Run them from the clone root, with the venv active:

```bash
python src/corpus/validation/report.py          # all checks + the report
python src/corpus/validation/check_invariants.py
python src/corpus/validation/build_html_report.py
```

Each resolves its landscape through `corpora.load("finance")`, so none of them
holds a path.

## Why the checks are written per trap *class*

The harness asserts "no K6 claim ends up `contradicted`", never "F1 has verdict
X". That is not a style preference: it is what lets the harness grade the
owner's blind traps without anyone seeing them. A blind trap carries a K-class
tag in the answer key and nothing else, so a class-generic check reaches it and
an F-ID-specific check could not.

The same reasoning runs through the spot-checks: `recompute_reference_results.py`
re-derives Z1–Z4 from `corpora/finance/spec/target_questions.yaml` and the
accounting policy PDF, **not** from the generator's logic. A shared misreading
between generator and harness would otherwise pass both undetected.

## What the numbers mean

- Trap catalogue, K-classes, target questions, accepted tolerances:
  `docs/corpus.md`.
- What a landscape is, the reading rule, and how to add a third:
  `corpora/README.md`.
- Milestone status: the roadmap table in the root `README.md`. This file used
  to carry a second copy and it drifted — it still had SQL generation as M6.
