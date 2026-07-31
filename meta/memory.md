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
     consume (architecture.md "Onboarding workflow"). **Concrete case found
     2026-07-31:** the finance guide declares BOTH `journal` and
     `amount_local` as `decided_by: balance`, but balance's *subject* is the
     journal — the amount is one of its slots. Consequences: (a)
     `amount_local` draws a spurious "what domain knowledge is missing?"
     question when nothing is missing; (b) the outcome is sample-dependent —
     the M4 fixtures bound balance to it and it passed (listed as settled),
     the 2026-07-31 fixtures refused it ("a bare amount_local column carries
     no self-contained conservation invariant"), so a coin flip decides
     whether the role settles. Likely fix: `amount_local: decided_by: slot`
     (data, one line) + extend the lint to reject a role declaring a law it
     can only be a slot of. Note the evidence already exists but is
     unconnected: the passing journal balance check ran with
     `amount=amount_local_currency`.
  6. **Concept claims are lost to a redundant field** (found in the
     2026-07-31 validation walkthrough). `Hypothesis.kind` is a pure
     function of the predicate (`concept` iff `concept_definition`), yet the
     model must supply it — and when it omits it, the `"rule"` default
     contradicts the predicate AND triggers a second, bogus error
     ("grounded in no known view or column", which only fires for rules).
     All 3 V1 skips in the walkthrough are this one bug; the retry cannot
     fix it (0 of 3 accepted live). Fix: derive `kind` from the predicate
     instead of asking, and fall back `definition` → `statement` when the
     model gives only `term`. Schema change ⇒ prompt bytes ⇒ rides this
     batch's re-record. Note: it would NOT have flipped F21 (that matcher
     also needs the revenue link, which the claim never states) — the gain
     is admitting the K3 concept class at all, not a recall number.
  7. **Owner decision: normalize `view.column` given for view params?**
     (same walkthrough). 6 of the 7 V2 skips are one shape error — the model
     answers `de_erp__gl_postings.account_id` where the param must name a
     bare *view*; it cascades across every param of that template. The
     existing normalizer only strips `view.` from *column* params and
     anchors on the view param, so it cannot get a foothold when the view
     param is itself qualified. Mirroring it for view params is
     deterministic, and the VIEW_PARAMS/COLUMN_PARAMS integrity checks stay
     as backstop — but leniency means a possibly-confused binding *executes*,
     and a passing verdict promotes: the too-loose-law failure mode in
     miniature. Decide deliberately. (The 7th skip — `accounts` given as a
     column instead of literal account numbers — is a real error and should
     keep failing.)
- **M4 COMPLETE** — tag `m4-llm-v1`. Seeded-Recall 15/25, False-Promotion 0
  (`docs/seeded-recall-m4.md`). Step 8 (`8-collect.sh`) + optional online pass
  remain available anytime (`validation/README.md`).
- Suite: **257 pass** when fixtures are current (`cd /workspace/src &&
  python -m pytest -q`, venv `/workspace/.venv`).

## Open items

- **Decide before M6: scope-aware role elections.** Full analysis and
  evidence: `docs/architecture.md` → LLM contracts → "KNOWN GAP — elections
  are scope-blind". Short version: one role elects one winner project-wide,
  but DE and US each legitimately own a journal/account/period/doc_ref, so
  four clarification questions currently ask the owner to pick one of three
  correct answers, and the US ledger reads as "not the journal" when it is
  the US journal with a €50k defect. `Scope` already exists on `Claim` and
  is simply not consulted by elections. The ReadinessMap will inherit
  whatever scoping roles have — hence the M6 deadline. Not a quick fix.
- **Decide: build the domain-guide acceptance kit.** Full analysis:
  `docs/architecture.md` → Domain inputs → "The domain pack is the critical
  — and currently unverified — input". Short version: 57 lines of guide
  control what is searched for, which candidates compete, which law judges
  which role, and which questions reach the owner — and **none of the 257
  tests checks it**. Part 3 of the kit (the coherence lint) is cheap, needs
  no data, catches the `amount_local` bug class automatically, and shares a
  mechanism with M5 kickoff item 5 — build them together.
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
