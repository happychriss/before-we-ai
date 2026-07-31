# Project Memory — live state only

<!-- Only what changes session to session. Durable facts belong in README.md
     (roadmap + status), docs/ (confirmed design), meta/ (conventions). -->

## Current focus

- **M6 — question flow + ReadinessMap: DONE 2026-07-31.** Suite **349
  green**; prompt bytes of V1/V2 untouched at every commit (drift guard
  green, which is the proof). Built: `AnswerRequest` / `RequiredKnowledge`
  (`answers/` in the store), **V4** (`llm/v4_request.py`, hand-authored
  corpus fixture marked as such), scoped elections (role × scope; a source
  declares whose books it is in `before-ai.yaml`), the **readiness
  evaluator** (`before_we_ai/readiness/`, derived never stored), the
  report's section 6 + real M6 diagram node, and walkthrough step
  **`8-ask.sh`** (collect moved to `9-collect.sh`). Design + the five spec
  updates: `docs/architecture.md` → "Question flow & readiness (M6 — BUILT)".
  Plan file (now historical): `/home/ubuntu/.claude/plans/you-are-in-the-federated-forest.md`.
  - Walkthrough pins after M6: **9** required-knowledge items, 0 skipped;
    verdict **blocked**, naming `journal.entity`, `journal.period`,
    `journal.account`, `intercompany`. Answering the six open cards narrows
    it to `ready_with_limitations` with the three business rules named.
    Unchanged upstream: 52/0/3 · 22 candidates · 42 plans/19 unbindable/6
    semantic-only/7 skipped · 42 executed/35 pass/7 fail · 6 role questions
    / 13 total.
  - **Not built, deliberately:** the small standalone demo dataset
    (findings §12) meant to double as the first user experience. Offline it
    needs its own recorded V1/role/V2 answers, and hand-authoring those
    would mean writing the model's answers and then asserting the system
    found them. The six acceptance behaviours are proved against the frozen
    corpus and its recorded real answers instead. **Needs one live
    recording session — queue it with the key rotation.**
- **NEXT: the owner's validation run using only the readiness report**
  (deferred once already, before M6). Then **M5**.
- **M5 — documents & V3** (spec: docs/spec/ — PDF pipeline, anchors,
  multi-anchor reconciliation; acceptance: T8 negatives, real PDF).
- **M5 kickoff batch** (runs at M5 start; items 3+4+6 touch prompt bytes →
  ONE shared fixture re-record at M5 kickoff, ~5 calls now that V4 rides
  along and gets its first real recording):
  1. E4 noise PDFs blocker (see open items) — decide before anything.
  2. `discover(root)` sources discovery + bundled domain guides
     (architecture.md "Onboarding workflow").
  3. Show the domain tag in V2 template docs (architecture.md "Domain inputs").
  4. Mapping claims binding to *generic* templates where a real data property
     exists (`account` via anti_join against the chart of accounts).
  5. **Concept claims are lost to a redundant field** (found in the
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
  6. **Owner decision: normalize `view.column` given for view params?**
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
- **M4 COMPLETE** — tag `m4-llm-v1`. Seeded-Recall 15/25 baseline, 14/25
  after the terminology rename (flips both ways ⇒ sampling noise; run-to-run
  noise is ±2–3 traps — factor into the recall-bar decision). False-Promotion
  **0**; leakage CLEAN (`docs/seeded-recall-m4.md`). Finding to watch at the
  M5 re-record: the reworded V2 mapping prompt binds invariants more
  hesitantly (19/22 template=null vs 15/23).
- Suite: **349 pass** when fixtures are current (`cd /workspace/src &&
  python -m pytest -q`, venv `/workspace/.venv`).

## Open items

- **Domain-guide acceptance kit — part 3 DONE, parts 1+2 open.** The
  coherence lint shipped with the pre-M6 alignment step. Parts 1+2
  (per new law: one holds-fixture + one violated-fixture; per new role: one
  wrong candidate that must lose) remain an owner decision — they belong
  with guide provenance / the drafting contract (post-M5). This matters
  *more* under readiness framing: a wrong guide now produces a confident,
  product-branded "ready". Full analysis: `docs/architecture.md` → Domain
  inputs.
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
- **Owner: rotate the Anthropic API key** — shared in chat 2026-07-12,
  2026-07-30 and twice 2026-07-31 (never written to any file or commit).
  Two things want a live session afterwards: the M5 fixture re-record, and
  the standalone demo dataset. Rotate after them.
- Remote branch `copilot/create-scripts-folder` (1 unmerged commit:
  `scripts/copy_raw_data.sh`) — owner's delete/merge decision pending.
- M5 will likely unlock three of the walkthrough's untested claims — their
  V2 refusals literally say the rule lives in a document (`decodes` account
  ranges, AR control account, opening-balances coverage; read them in the
  readiness report). It is also what the three unsupported *rules* in the
  M6 readiness map are waiting for: a sign convention lives in a policy.
