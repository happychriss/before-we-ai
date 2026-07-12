# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M4 COMPLETE** — tag `m4-llm-v1`. First online run: Seeded-Recall 15/25
  in-scope incl. T7 (leakage clean), False-Promotion 0 (`docs/seeded-recall-m4.md`).
- **M5 — documents & V3** is next (spec: docs/spec/ — PDF pipeline, anchors,
  multi-anchor reconciliation rule; acceptance: T8 negative cases, real PDF).

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
