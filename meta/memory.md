# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M4 — LLM contracts V1/V2**: offline path COMPLETE (230 tests green; contracts,
  stub mode, guardrail + corpus acceptance, drift guard, eval harness). Confirmed
  design → `docs/architecture.md` "LLM contracts"; status → `docs/requirements.md` §6.
- **Remaining for M4 close-out** (needs owner's `ANTHROPIC_API_KEY` exported):
  1. `cd src && python tests/eval/refresh_fixtures.py` — record real fixtures,
     re-pin the offline corpus test's expectations to the new answers, commit.
  2. `python tests/eval/seeded_recall.py` — first real recall report; review
     together, set the numeric bar (owner decision, deferred by design);
     matchers in `tests/eval/seeded_recall.py` may need refinement then.
  3. Milestone duties: SIMPLE-README German M4 section, slim this file,
     tag `m4-llm-v1`, push.
- Seeded-Recall bar: **measure first** (owner 2026-07-12); fixed acceptance =
  harness works, False-Promotion 0, T7/F8 result explained (hit → leakage
  check first, miss → documented).

## Open items

- Remote branch `copilot/create-scripts-folder` (1 unmerged commit:
  `scripts/copy_raw_data.sh`) — awaiting owner's delete/merge decision; candidate
  seed for the planned `scripts/` folder.
