# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M4 COMPLETE** — tag `m4-llm-v1`. First online run: Seeded-Recall 15/25
  in-scope incl. T7 (leakage clean), False-Promotion 0 (`docs/seeded-recall-m4.md`).
- **NOW: owner tests & validates M4** — stage-by-stage walkthrough with
  runnable scripts: `validation/README.md` (canonical home of the guide,
  incl. the "expected behaviors that are NOT bugs" list).
- After validation: **M5 — documents & V3** (spec: docs/spec/ — PDF pipeline,
  anchors, multi-anchor reconciliation rule; acceptance: T8 negatives, real PDF).

## M4 validation notes (beyond validation/README.md)

- Full offline suite: `cd /workspace/src && python -m pytest -q` → 233 pass
  (venv: `source /workspace/.venv/bin/activate`).
- Refresh stub fixtures only when prompts/builders changed (drift-guard test
  `test_fixtures_match_current_inputs` goes red): from `src/`
  `python tests/eval/refresh_fixtures.py`, then re-pin the counts in
  `tests/corpus_driven/test_llm_offline_corpus.py` and commit the diff.
- Online runs need `export ANTHROPIC_API_KEY=...` — rotate the old key first
  (open items).

## Open items

- **M5 blocker found 2026-07-12 (validation session): the E4 noise PDFs are
  missing from the frozen corpus.** `sources_manifest.yaml` specifies
  `reisekostenrichtlinie.pdf`, `lieferantenkatalog.pdf`,
  `pressemitteilung_2022_divested_unit.pdf` (E4, trap F26 — poisoned anchor,
  `deny_promotion: true`), but `src/corpus/data/` holds only the three
  content PDFs (E1 management_report, E2 rabattvertrag, E3
  buchhaltungsrichtlinie). F26 is in the recall_set and in
  expected_verdicts.yaml, so M5's "T8 negatives" acceptance cannot be met as
  written. Decide at M5 start: generate the missing decoys (corpus is frozen,
  tag m0-corpus-v1 — needs a deliberate re-tag) or re-scope F26.

- **Owner: set the numeric Seeded-Recall bar** now that the first measurement
  exists (15/25; misses mostly K3 definition-style traps F14/F15/F17/F19/F21/F25
  and F3/F4/F7/F11 — see report). Matchers in `tests/eval/seeded_recall.py`
  may be refined alongside.
- **Owner: rotate the Anthropic API key** shared in chat on 2026-07-12 (it is
  in the conversation history; it was never written to any file or commit).
- **Owner direction (2026-07-12, validation session): role packs become a
  product feature.** Two layers: (1) ship curated per-domain packs bundled in
  the package (`before_we_ai/roles/finance.yaml`; `roles_file: finance`
  resolves bundled, path overrides) — the current test fixture
  `roles_finance.yaml` is the finance pack's content; (2) later, an LLM
  contract that *drafts* a role pack for a new domain — the authoring
  questionnaire (conservation laws → extract nouns → structural definitions
  passing the new-hire test → per-role falsifiability → no vendor/system
  tokens) is the system prompt; `RoleSet` is the schema. GUARDRAIL: a
  generated pack is a draft a human curates, never silently consumed — a
  too-loose invariant is the one path to false confidence (promotes bindings
  on evidence that tests nothing); too-strict merely drafts Fachfragen.
  Timing: bundle the pack at M5 kickoff together with sources-discovery
  (both change prompt bytes → one fixture re-record); the drafting contract
  is post-M5 scope.
- Remote branch `copilot/create-scripts-folder` (1 unmerged commit:
  `scripts/copy_raw_data.sh`) — awaiting owner's delete/merge decision; candidate
  seed for the planned `scripts/` folder.
