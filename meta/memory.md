# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M4 COMPLETE** — tag `m4-llm-v1`. First online run: Seeded-Recall 15/25
  in-scope incl. T7 (leakage clean), False-Promotion 0 (`docs/seeded-recall-m4.md`).
- **NOW: owner tests & validates M4** — quick guide below.
- After validation: **M5 — documents & V3** (spec: docs/spec/ — PDF pipeline,
  anchors, multi-anchor reconciliation rule; acceptance: T8 negatives, real PDF).

## M4 validation quick guide (owner session)

All commands from `/workspace/src` with `source /workspace/.venv/bin/activate`
(the venv has the `anthropic` SDK; online runs additionally need
`export ANTHROPIC_API_KEY=...` — rotate the old key first, see open items).

- **Full offline suite** (no network, no key): `python -m pytest -q` → 233 pass.
  LLM-specific: `-k llm`; corpus pipeline: `tests/corpus_driven/test_llm_offline_corpus.py`.
- **Offline pipeline replay + kept project for inspection**:
  `python tests/eval/seeded_recall.py --offline --keep /tmp/m4check`
  → project at `/tmp/m4check/project` (claims/, probes/, evidence/, questions/
  as YAML; report `cache/eval/seeded_recall.md`; every LLM call verbatim in
  `cache/llm_log/*.json` — audit prompts there).
- **Visual inspection**: `python -m claim_viewer /tmp/m4check/project -o /tmp/claims.html`
  (known gap: viewer doesn't link persisted probes/probe_id — docs/claim-viewer.md).
- **Online eval (fresh model calls, ~330k tokens/run)**:
  `python tests/eval/seeded_recall.py --keep DIR`.
- **Refresh stub fixtures from real runs** (only when prompts/builders changed —
  the drift-guard test `test_fixtures_match_current_inputs` goes red then):
  `python tests/eval/refresh_fixtures.py`, then re-pin the counts in
  `tests/corpus_driven/test_llm_offline_corpus.py` and commit the diff.

Expected behaviors that are NOT bugs:
- Two V1 hypotheses and one V2 binding are skipped on every offline replay
  (recorded "partial" answers; skips are per-item, visible in the logs).
- Role claim `us_erp__gl_postings` is CONTRADICTED — data-honest (F22 missing
  IC leg breaks per-period balance); the intercompany role loses everywhere
  → exactly one Fachfrage. The journal role: GL tested, F27 decoy contradicted.
- Online runs sample differently each time (~50–62 hypotheses, recall 14–15/25);
  only the recorded fixtures are frozen. Claim statements are model-worded —
  identity/dedup lives in predicate+params, never wording.
- A probe that cannot execute lands in RunReport.skipped("execution error…"),
  writes no evidence, and does not stop the sweep.

## Open items

- **Owner: set the numeric Seeded-Recall bar** now that the first measurement
  exists (15/25; misses mostly K3 definition-style traps F14/F15/F17/F19/F21/F25
  and F3/F4/F7/F11 — see report). Matchers in `tests/eval/seeded_recall.py`
  may be refined alongside.
- **Owner: rotate the Anthropic API key** shared in chat on 2026-07-12 (it is
  in the conversation history; it was never written to any file or commit).
- Remote branch `copilot/create-scripts-folder` (1 unmerged commit:
  `scripts/copy_raw_data.sh`) — awaiting owner's delete/merge decision; candidate
  seed for the planned `scripts/` folder.
