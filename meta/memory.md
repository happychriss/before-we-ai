# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M4 — LLM contracts V1/V2**: in progress. Spec in `docs/requirements.md` §6;
  approved plan: `/home/ubuntu/.claude/plans/humble-moseying-bubble.md`.
- **M4 owner decisions (2026-07-12)**: Anthropic API, key via `ANTHROPIC_API_KEY`
  env var (never committed); models `claude-opus-4-8` (V1 + role binding, frontier)
  and `claude-sonnet-5` (plain V2 binding, mid-tier), overridable in `before-ai.yaml`.
  Seeded-Recall bar: **measure first** — harness reports per-trap hit/miss, numeric
  bar set after the first real online run; fixed acceptance = harness works,
  False-Promotion 0, T7 result explained (hit → leakage check, miss → documented).
- M0–M3 complete and tagged (see `docs/requirements.md`).

## Open items

- Remote branch `copilot/create-scripts-folder` (1 unmerged commit:
  `scripts/copy_raw_data.sh`) — awaiting owner's delete/merge decision; candidate
  seed for the planned `scripts/` folder.
- M4 steps 8–9 (online fixture refresh + first Seeded-Recall run) need the owner's
  `ANTHROPIC_API_KEY` in the environment.
