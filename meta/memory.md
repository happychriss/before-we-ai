# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M4 COMPLETE** — tag `m4-llm-v1`. First online run: Seeded-Recall 15/25
  in-scope incl. T7 (leakage clean), False-Promotion 0 (`docs/seeded-recall-m4.md`).
- **NOW: owner walks through M4 validation** — guide + runnable scripts:
  `validation/README.md`. Session 2026-07-12 reached step 7 (roles resolved);
  remaining: step 8 + optional online pass. Suite: 241 pass
  (`cd /workspace/src && python -m pytest -q`, venv `/workspace/.venv`).
- **Claim-viewer redesign SHIPPED** (2026-07-12, all six approved items) — the
  page now mirrors the pipeline: funnel → Fachfragen inbox → role elections →
  master–detail claim-as-story, single derived badge. See
  `docs/claim-viewer.md`. It also forced a core improvement: **V2 now persists
  its refusals** as DECLARATION evidence (unbindable / semantic-only / skipped +
  verbatim reason), so "why was this never tested" survives a cache wipe
  (architecture.md "A refusal is a result"). Walkthrough data re-generated
  offline (steps 0–7) so the report shows them.
- **Open finding for the owner** (surfaced by the role elections): the roles
  `account`, `doc_ref`, `entity` can never be elected — they appear only as
  *slots* inside the invariants, so V2 honestly answers `template=null` for all
  their candidates and they stay `inferred` with no Fachfrage. The role-pack
  lint (M5 kickoff) must force each declared role to name the invariant that
  elects it, or be declared slot-only.
- Shipped mid-validation: **two-tier retry** (item-scoped repair; see
  architecture.md "Retry contract, two-tier"). Offline replays unchanged;
  real effect only measurable on the next online run — watch for
  `repaired_ok` outcomes there.
- Also shipped mid-validation: domain-law templates now carry
  `TemplateSpec.domain` (test-locked — what is domain-specific must be
  enumerable; see architecture.md "Domain inputs"); claim viewer links
  persisted probes; walkthrough steps 3–7 auto-refresh both HTML pages
  (`validation/data/report/{claims,llm_calls}.html`) — the LLM-call log
  opens with the declared domain inputs + core terms.
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
