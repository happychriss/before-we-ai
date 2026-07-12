# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M4 COMPLETE** — tag `m4-llm-v1`. First online run: Seeded-Recall 15/25
  in-scope incl. T7 (leakage clean), False-Promotion 0 (`docs/seeded-recall-m4.md`).
- **NOW: owner walks through M4 validation** — guide + runnable scripts:
  `validation/README.md`. Session 2026-07-12 reached step 3 (V1 hypotheses);
  remaining: steps 4–8 + optional online pass. Suite: 237 pass
  (`cd /workspace/src && python -m pytest -q`, venv `/workspace/.venv`).
- Shipped mid-validation: **two-tier retry** (item-scoped repair; see
  architecture.md "Retry contract, two-tier"). Offline replays unchanged;
  real effect only measurable on the next online run — watch for
  `repaired_ok` outcomes there.
- After validation: **M5 — documents & V3** (spec: docs/spec/ — PDF pipeline,
  anchors, multi-anchor reconciliation; acceptance: T8 negatives, real PDF).

## Open items

- **M5 blocker: E4 noise PDFs missing from the frozen corpus**
  (`reisekostenrichtlinie.pdf`, `lieferantenkatalog.pdf`,
  `pressemitteilung_2022_divested_unit.pdf` — trap F26 poisoned anchor,
  `deny_promotion: true`). They're in `sources_manifest.yaml` and the
  recall_set but not in `src/corpus/data/`, so M5's "T8 negatives"
  acceptance can't be met as written. Decide at M5 start: generate + re-tag
  the frozen corpus, or re-scope F26.
- **Onboarding workflow** (owner-aligned 2026-07-12): sources discovery +
  bundled role packs at **M5 kickoff** (one shared fixture re-record),
  LLM pack-drafting post-M5, assembled quickstart at M8. Full design:
  `docs/onboarding-workflow.md`.
- **Owner: set the numeric Seeded-Recall bar** (first measurement 15/25;
  misses cluster in K3 definition-style traps — they need the M5 document
  pipeline; consider a bar over relationship-style traps only).
- **Owner: rotate the Anthropic API key** shared in chat 2026-07-12 (never
  written to any file or commit).
- Fixture refresh procedure (only when prompts/builders change and the
  drift guard goes red): from `src/` run
  `python tests/eval/refresh_fixtures.py`, re-pin counts in
  `tests/corpus_driven/test_llm_offline_corpus.py`, commit.
- Remote branch `copilot/create-scripts-folder` (1 unmerged commit:
  `scripts/copy_raw_data.sh`) — owner's delete/merge decision pending.
