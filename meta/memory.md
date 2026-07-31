# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in README.md
     (roadmap + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **Order decided 2026-07-31 (owner): pre-M6 alignment → M6 (question flow,
  narrow demo) → M5 (documents).** Plan:
  `/home/ubuntu/.claude/plans/guide-hierarchy-then-m6.md`. Spec + rationale:
  `docs/architecture.md` ("Guide by construction", "Question flow &
  readiness"); owner discussion record:
  `docs/before-we-ai-key-findings-and-conclusions.md`.
- **NEXT: pre-M6 alignment step** — DomainGuide restructured to business
  objects + fields (a field can never declare a law → `amount_local` bug
  class inexpressible), coherence lint against the new shape (absorbs former
  M5 kickoff item 5), slot metadata on CheckDefinition. **Hard constraint:
  prompt bytes stay identical** (drift-guard test proves it offline); if
  flat rendering can't be preserved byte-identically, fold the change into
  the M5 re-record batch and re-plan.
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
  after the M6 demo (owner decision 2026-07-31).
- **M5 kickoff batch** (runs at M5 start, i.e. after M6; items 3+4+6 touch
  prompt bytes → ONE shared fixture re-record at M5 kickoff; ~4 calls.
  **Item 5 moved out**: it is now the pre-M6 alignment step above):
  1. E4 noise PDFs blocker (see open items) — decide before anything.
  2. `discover(root)` sources discovery + bundled domain guides
     (architecture.md "Onboarding workflow").
  3. Show the domain tag in V2 template docs (architecture.md "Domain inputs").
  4. Mapping claims binding to *generic* templates where a real data property
     exists (`account` via anti_join against the chart of accounts).
  5. ~~Slot-side guide lint~~ — **moved to the pre-M6 alignment step**
     (2026-07-31): CheckDefinition declares which roles its slots
     consume (architecture.md "Guide by construction"). **Concrete case found
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

- ~~Decide before M6: scope-aware role elections~~ — **DECIDED 2026-07-31:
  resolved by design in M6.** AnswerRequest carries scope → RequiredKnowledge
  inherits it → elections run per scope. No interim fix on the flat model.
  See architecture.md → "Question flow & readiness (M6)".
- **Domain-guide acceptance kit — part 3 scheduled, parts 1+2 open.** The
  coherence lint is now the pre-M6 alignment step (Current focus). Parts 1+2
  (per new law: one holds-fixture + one violated-fixture; per new role: one
  wrong candidate that must lose) remain an owner decision — they belong
  with guide provenance / the drafting contract (post-M5). Full analysis:
  `docs/architecture.md` → Domain inputs.
- **Owner: fate of `docs/before-we-ai-key-findings-and-conclusions.md`.**
  Its decisions are absorbed into architecture.md (2026-07-31: "Guide by
  construction" + "Question flow & readiness"); the file also restates the
  terminology table glossary.py owns. Keep it as a discussion record, or
  delete per one-fact-one-home — owner's call, not deleted unilaterally.
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
