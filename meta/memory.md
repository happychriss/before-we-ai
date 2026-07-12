# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in docs/requirements.md
     (what + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **NOW: M5 — documents & V3** (spec: docs/spec/ — PDF pipeline, anchors,
  multi-anchor reconciliation; acceptance: T8 negatives, real PDF). Owner
  moved here 2026-07-12 after validating M4 through step 7.
- **M5 kickoff batch** (decide/do first, ONE shared fixture re-record since
  they all touch prompt bytes — procedure below):
  1. E4 noise PDFs blocker (see open items) — decide before anything.
  2. `discover(root)` sources discovery + bundled role packs
     (docs/onboarding-workflow.md).
  3. Show the domain tag in V2 template docs (architecture.md "Domain inputs").
  4. Role claims binding to *generic* templates where a real data property
     exists (`account` via anti_join against the chart of accounts).
  5. Slot-side pack lint: TemplateSpec declares which roles its slots
     consume (docs/onboarding-workflow.md "Logical pack validation").
- **M4 COMPLETE** — tag `m4-llm-v1`. Seeded-Recall 15/25, False-Promotion 0
  (`docs/seeded-recall-m4.md`). Validation walkthrough done through step 7
  with the final data; step 8 (`8-collect.sh`) + optional online pass remain
  available anytime (`validation/README.md`). The online pass would also show
  whether the two-tier retry turns `partial` into `repaired_ok` (architecture.md
  "Retry contract, two-tier").
- Suite: **257 pass** (`cd /workspace/src && python -m pytest -q`,
  venv `/workspace/.venv`).
- Shipped during validation, all durable in docs now: claim-viewer redesign
  (docs/claim-viewer.md), V2 persists refusals as DECLARATIONs + role
  settlement paths `decided_by:` with pack lint — every non-slot role ends in
  a probe verdict or a Fachfrage, step 7 pins 6 Fachfragen
  (architecture.md "A refusal is a result" / "Every role declares its
  settlement path"); `TemplateSpec.domain` tags; core-terms glossary has one
  home (`before_we_ai/glossary.py`).

## Open items

- **M5 blocker: E4 noise PDFs missing from the frozen corpus**
  (`reisekostenrichtlinie.pdf`, `lieferantenkatalog.pdf`,
  `pressemitteilung_2022_divested_unit.pdf` — trap F26 poisoned anchor,
  `deny_promotion: true`). They're in `sources_manifest.yaml` and the
  recall_set but not in `src/corpus/data/`, so M5's "T8 negatives"
  acceptance can't be met as written. Decide at M5 start: generate + re-tag
  the frozen corpus, or re-scope F26.
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
- M5 will likely unlock three of the walkthrough's untested claims — their
  V2 refusals literally say the rule lives in a document (`decodes` account
  ranges, AR control account, opening-balances coverage; read them in the
  claim viewer).
