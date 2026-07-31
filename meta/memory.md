# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in README.md
     (roadmap + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **Terminology realignment + documentation restructure — DONE 2026-07-31**
  (code, docs, spec, walkthrough, live fixture re-record, suite 257 green;
  committed). Post-rename Seeded-Recall: **14/25** (−1 vs baseline, flips
  both ways ⇒ sampling noise; run-to-run noise is ±2–3 traps — factor into
  the recall-bar decision); **False-Promotion 0**; leakage CLEAN
  (`docs/seeded-recall-m4.md` "Post-rename re-measurement"). Finding to
  watch at the M5 re-record: the reworded V2 mapping prompt binds
  invariants more hesitantly (19/22 template=null vs 15/23; intercompany +
  amount_local settled via clarification questions in the recording).
- **M5 — documents & V3** (spec: docs/spec/ — PDF pipeline, anchors,
  multi-anchor reconciliation; acceptance: T8 negatives, real PDF). Queued
  behind the re-record above.
- **M5 kickoff batch** (decide/do first; items 3+4 touch prompt bytes →
  ONE shared fixture re-record at M5 kickoff. Deliberately NOT bundled into
  the rename re-record: the rename run must stay a null test — same shape,
  reworded prompts — so the recall delta is attributable; an M5 re-record
  is cheap, ~4 calls):
  1. E4 noise PDFs blocker (see open items) — decide before anything.
  2. `discover(root)` sources discovery + bundled domain guides
     (architecture.md "Onboarding workflow").
  3. Show the domain tag in V2 template docs (architecture.md "Domain inputs").
  4. Mapping claims binding to *generic* templates where a real data property
     exists (`account` via anti_join against the chart of accounts).
  5. Slot-side guide lint: CheckDefinition declares which roles its slots
     consume (architecture.md "Onboarding workflow").
- **M4 COMPLETE** — tag `m4-llm-v1`. Seeded-Recall 15/25, False-Promotion 0
  (`docs/seeded-recall-m4.md`). Step 8 (`8-collect.sh`) + optional online pass
  remain available anytime (`validation/README.md`).
- Suite: **257 pass** when fixtures are current (`cd /workspace/src &&
  python -m pytest -q`, venv `/workspace/.venv`).

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
- **Owner: rotate the Anthropic API key** — shared in chat 2026-07-12 and
  2026-07-30 (neither written to any file or commit); a third share happens
  at the fixture re-record. Rotate all after the re-record.
- Remote branch `copilot/create-scripts-folder` (1 unmerged commit:
  `scripts/copy_raw_data.sh`) — owner's delete/merge decision pending.
- M5 will likely unlock three of the walkthrough's untested claims — their
  V2 refusals literally say the rule lives in a document (`decodes` account
  ranges, AR control account, opening-balances coverage; read them in the
  claim viewer).
