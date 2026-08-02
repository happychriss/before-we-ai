# Project Memory — live state and open points

<!-- Forward-looking only: what is in flight, what is undecided, what is
     queued. No history — git has that. Durable facts belong in README.md
     (roadmap + status) and docs/ (confirmed design). -->

## Where we are

- **Built:** M0 corpus · M1 core · M2 ingestion · M3 checks & engine ·
  M4 LLM contracts V1/V2 · readiness report · M6 question flow +
  ReadinessMap · **answer types** (the guide declares what a family of
  question depends on; the model classifies, the engine expands, a human
  confirms) · **the outer-layer refactor** (`meta/refactor-workorder.md`,
  all seven PRs).
- **What the refactor changed for anyone writing code now:** report facts
  live in `readiness_report/projection.py`, HTML in
  `templates/report.html.j2` with CSS/JS as package resources, and
  `render.py` is 98 lines of wiring. Model-facing code receives a
  `ProposalStore` and structurally cannot write promoting evidence. Test
  lanes exist (`pytest -m unit`, ~0.5s); every test module declares one.
  Domain packs ship in `before_we_ai/domains/`.
- **The stage spine is the organising idea** (`before_we_ai/stages.py`, as
  data; `docs/architecture.md` → "The stage spine" for reading). Seven stages,
  one actor each; the walkthrough script number *is* the report section
  number. 0 inputs · 1 request · 2 measured · 3 proposed · 4 tested ·
  5 clarification · 6 readiness. Stage 0 is the precondition; 1 and 6 are the
  frame around the middle.
- **The suite is green and fully offline** (`cd /workspace/src &&
  source /workspace/.venv/bin/activate && python -m pytest -q`); lanes for
  faster feedback in `meta/project-setup.md`. No count is written down
  anywhere, here included — it went stale three times and never once
  changed a decision.
- **Standing measures** (these do change decisions, so they are written
  down): False-Promotion **0** (non-negotiable at every commit) ·
  Seeded-Recall **14–15/25** · prompt-leakage scan CLEAN.
- **Walkthrough pins** (offline; `validation/README.md` carries them per
  stage): 52 hypotheses / 0 deduped / 3 skipped · 22 candidates · 42 plans /
  19 unbindable / 6 semantic-only / 7 skipped · 42 executed, 35 pass / 7 fail ·
  6 role questions, 13 open in total · 9 required-knowledge items · verdict
  **blocked**, naming `journal.entity`, `journal.period`, `journal.account`,
  `intercompany`.

## Next

1. **Owner validation run using only the readiness report.** Deferred twice,
   and the reason to do it is now evidence rather than principle: reading real
   output has found four things the whole green suite did not — a grammar slip
   in a derived sentence, three dead fields, two report surfaces disagreeing
   about one store, and the unconfirmed required-knowledge list below.

   Run it: `cd validation && ./scripts/reset.sh && ./scripts/0-inputs.sh`,
   then follow the `next:` line each stage prints. Every stage rebuilds
   `validation/data/report/index.html` — leave a tab open on it.
   `validation/README.md` says what to look for and the numbers to expect.
2. **M5 — documents & V3. IN PROGRESS since 2026-08-02.** PDF pipeline,
   position anchors, DuckDB FTS, multi-anchor reconciliation, `tell` +
   mirror loop. Acceptance: T8 negatives and a real PDF — every PDF it
   needs is in the frozen corpus (`src/corpus/data/`, including `noise/`).

   **Design settled first** (architecture.md → "Documents & V3"), then
   built. Four things the design doc got wrong and the code corrected —
   each recorded there, listed here because they are the shape of the
   milestone:
   - **`kind` and `match` are derived, not asked for.** The plan had V3
     classify an anchor as text/table/chart. The corpus killed it: F23's
     chart figure extracts as ordinary text, so asking would rest the
     whole rule on the model's word about something it cannot see. Kind
     comes from page geometry (PyMuPDF `find_tables()` + drawing
     clusters), match from reconciliation parsing the quote.
   - **Value corroboration ≠ definitional grounding.** The multi-anchor
     rule as first written required two independent anchors before
     anything could link — which would have made K3 impossible, since the
     accounting policy is the only document stating the sign convention.
     The threshold governs figures; a policy sentence links on its own,
     and costs nothing because a link is not evidence (the claim stays
     `proposed`).
   - **Retrieval bounds, it does not filter.** A document that fits under
     the passage cap is sent whole. Keyword-selecting passages silently
     drops the paragraph that answers a differently-phrased question.
   - **Documents have one owner.** `scan()` used to fingerprint PDFs too;
     both stages then wrote one Source in two fingerprint shapes, and
     staleness compares fingerprints. `scan()` now skips documents.

   **Decisions taken at kickoff (2026-08-02):**
   - **All six corpus PDFs are declared sources — DONE** (was: only
     `management_report.pdf`). Noise presence is the precision test.
     Walkthrough pins still need re-recording (below).
   - **The spec's real public PDF is still missing** (Pflichtbestandteil,
     `fixture-korpus-spezifikation.md:46` — all six corpus PDFs are
     generator-made). OWNER picks the document (a public annual report is
     the spec's own example); it enters additively as
     `src/corpus/data/real/` with hand-annotated expected anchors. Blocks
     final M5 acceptance, not the build.

   **Built so far (2026-08-02), suite 470 → 580 green:**
   `before_we_ai/documents/` — `extract` (geometry → kind), `chunk`
   (deterministic, kind-pure, stable ids), `index` (DuckDB FTS, hard error
   if the extension is missing), `figures` (reads numbers without
   inventing agreement — an ambiguous literal like `500.000` reports both
   readings and never counts), `reconcile` (the multi-anchor rule) ·
   `read_documents(root)`, the stage-2c twin of `scan` — profiles, zero
   claims, zero evidence · `DocumentProfile` sharing `profiles/` with
   `DataProfile` via the `object_type` discriminator ·
   `ProposalStore.anchor()` with the quote string-matched at the write, so
   a hallucinated citation cannot be stored at all · `AnchorKind` /
   `AnchorMatch` in `core/enums.py` · contract **V3** (`llm/v3_documents`,
   `interpret_documents`) — one call per document, findings become
   proposed claims + anchors, refusals become clarification questions.

   **Still open in M5:**
   1. Hand-authored V3 corpus fixtures + wiring into
      `test_llm_offline_corpus.py`; **then** widen the guardrail
      allow-list (`test_llm_guardrail.py`) to admit DOCUMENT_ANCHOR/AI —
      deliberately not widened yet, because nothing writes anchors in that
      fixture until V3 runs there.
   2. Walkthrough scripts `2c-measure-documents` and `3d-propose-documents`;
      re-pin `validation/README.md` end to end (source count 7 → 12).
   3. `tell` + `answer_question` + the `_status_rationale` fix (item below).
   4. Report surfaces: documents `*View` in `projection.py`, anchor-aware
      `EvidenceView`, the "M5 · documents" ghost node becomes real.
   5. Kickoff batch 1–4 + the live re-record session; acceptance run.

   **Unblocked, and the sequencing was deliberate:** the refactor ran first
   so M5 builds its document surfaces into `projection.py` and the template
   rather than into a 2,800-line renderer that no longer exists. Its new
   contract (V3) is born inside `ProposalStore`, and `anchor()` is the
   weak-evidence method that facade was shaped to accept — `DOCUMENT_ANCHOR`
   promotes nothing (`resolve_status` never reads it), so V3 writing anchors
   does not touch the promotion boundary. **`PyMuPDF` is M5's first line of
   code**: the spec names it and it is still undeclared.

   **M5 also builds the missing answer operation.** The *law* exists and is
   tested (a scoped CONFIRMATION makes a claim business-confirmed,
   `core/transitions.py`), but no product code constructs CONFIRMATION or
   TESTIMONIAL evidence — only tests do. `answer_question(store, card,
   answer, by=human)` is the mirror-loop machinery M5 needs anyway, and it
   is the core interaction of the GUI milestone below.

   **And it must fix `_status_rationale`** (found 2026-08-01 pre-flighting
   WP5). That function restates the promotion law in prose inside the
   renderer, and it already disagrees with it: `resolve_status` counts only
   *admissible* confirmations (mirror-loop — a testimonial claim needs an
   explicit scope), while the prose counts every confirmation record and
   then says "admissible" anyway. A claim would read: status `proposed`,
   trail "1 confirmation", why "Nothing stronger than proposed evidence is
   live yet." Unreachable while nothing creates confirmations — **M5 makes
   it reachable**, and the case it garbles is exactly the mirror loop's
   teaching moment ("you did not say for which scope"). The refactor moves
   the function verbatim and does not touch it; the fix belongs here.

   Its target is concrete: the three unsupported **rule** items in the
   ReadinessMap (`which accounts are profit and loss`, `sign convention for
   income and expense`, `month cut-off for late postings`). A sign convention
   lives in a policy, not in a column. V3 must **link** the claims it
   produces to the rules they answer (`readiness.link_claim` — the seam is
   built and tested).

   It also unlocks three walkthrough claims whose V2 refusals literally name
   documents: `decodes` account ranges, the AR control account, and
   opening-balances coverage. Read them in the readiness report.

3. **Confirm the answer-type slice against real output.** Built
   2026-08-01 (`docs/architecture.md` → "Answer types"); the walkthrough now
   classifies, shows the guide fingerprint and per-item provenance, and
   demonstrates the confirmation lifting the cap. What has *not* happened
   is a human reading it end to end — which is the same argument as item 1
   above, applied to the newest surface.

   Two things to judge while reading, both deliberate and both reversible:
   - **The cap is aggressive.** Every project reads
     `ready_with_limitations` until someone confirms the classification.
     True, but it means `ready` is now rare by construction.
   - **Only a confirmation lapses** when the guide moves, not waivers or
     links. A waiver is about one item; a confirmation is about the list.

4. **Confirm the two report fixes while reading** (done 2026-08-01, worth a
   look because both were found by reading and not by testing): section 0
   now lists the guide's answer types with what each one requires — a
   reader cannot judge the classification in section 1 without seeing what
   was on offer — and its subsections read `0.1 / 0.2 / 0.3` instead of the
   pre-spine `1.1 / 1.2 / 1.3`.

## Declared goal — the GUI milestone (after M5; not scheduled)

Owner statement 2026-08-01: a small product for **one question to one
answer**, with a GUI — ask the question, load documents, run, answer the
open questions, see the readiness map. **Computing the result is a further
milestone of its own**, and 2026-08-01 settled what belongs in it:

- the spec's **V4, SQL generation** — the contract number this repo left
  free when the request contract was renamed off it;
- **Assumption Capture** (`docs/spec/before-we-ai-systemarchitektur.md:59`):
  `sqlglot` parses the generated query, checks it against the allowed
  subset, extracts joins and claim-requiring filters, matches them against
  the claim store and **materialises what is missing as `proposed` claims**.
  The query becomes a source of claims — a real epistemic feature, not
  plumbing;
- `sql`/`result_ref` return to `AnswerRequest`, which is why deleting them
  was scaffolding removal rather than a loss.

They are one milestone, not two: Assumption Capture without SQL generation
has nothing to parse. That also fixes when `sqlglot` gets declared — then,
not before.

Design consequences that hold *now*, without building it:

- The GUI is a **loop** (ask → run → see questions → answer → re-run), not
  the walkthrough's linear batch. That is why recommendation A stays
  deferred: an application layer shaped today would be shaped like the
  walkthrough and thrown away.
- Its work-queue primitive half-exists (`gap_load` ranks unproven claims by
  the questions resting on them).
- Its core interaction is the answer operation M5 builds (Next, item 3).
- What it consumes is the report **view model** the refactor extracts —
  HTML report and GUI become two renderings of one projection.
- "Answered — what must now rerun / what is now stale?" is M7, and the GUI
  turns M7 from nice-to-have into required.

### M5 kickoff batch

Runs at M5 start. Items 2–4 change prompt bytes → **one shared fixture
re-record**, ~5 calls now that V4 rides along and gets its first real
recording (its corpus fixture is hand-authored and marked as such).

1. `discover(root)` sources discovery + bundled domain guides
   (architecture.md → "Onboarding workflow").
2. Show the domain tag in the V2 template docs
   (architecture.md → "Domain inputs").
3. Mapping claims binding to *generic* templates where a real data property
   exists (`account` via anti_join against the chart of accounts).
4. **Derive `Hypothesis.kind` from the predicate instead of asking for it.**
   It is a pure function of the predicate (`concept` iff
   `concept_definition`), yet the model must supply it — and when it omits
   it, the `"rule"` default contradicts the predicate *and* triggers a
   second, bogus error ("grounded in no known view or column", which fires
   only for rules). All 3 V1 skips in the walkthrough are this one bug, and
   the retry cannot fix it. Also fall back `definition` → `statement` when
   the model gives only `term`. Schema change ⇒ prompt bytes. The gain is
   admitting the concept class at all, not a recall number: it would not have
   flipped F21, whose matcher also needs a revenue link the claim never
   states.
5. **Decide: normalize `view.column` given for a view param?** Six of the
   seven V2 skips are one shape error — the model answers
   `de_erp__gl_postings.account_id` where the param must name a bare *view*,
   and it cascades across every param of that template. The existing
   normalizer strips `view.` from *column* params only and anchors on the
   view param, so it cannot get a foothold when the view param is itself
   qualified. Mirroring it is deterministic and the VIEW_PARAMS /
   COLUMN_PARAMS checks stay as backstop — **but** leniency means a
   possibly-confused binding executes, and a passing verdict promotes: the
   too-loose-law failure mode in miniature. Decide deliberately. (The seventh
   skip — `accounts` given as a column instead of literal account numbers —
   is a real error and should keep failing.)

## Open decisions (owner)

- **Domain packs live in `before_we_ai/domains/` — decided and done
  2026-08-01.** The finance guide was in `src/tests/fixtures/`, which told
  every reader of the report that the product's critical input is test
  infrastructure. It is now `before_we_ai/domains/finance.yaml`, declared
  package-data and reached through `domains.packaged("finance")`.

  The deciding argument was not tidiness but **shipping**: the M5 item
  `discover(root)` promises "bundled domain guides", and nothing bundles out
  of `tests/fixtures/`. "Data, never code" is a rule about the *format*
  (YAML, not Python), not the location. A customer's own guide stays a
  different thing entirely — their data, in their project, via
  `llm.domain_guide_file`.

  The content did not change, so the fingerprint did not either
  (`0ac5f94b7b63`) and every walkthrough pin held.

- **`sql`/`result_ref` return with the spec's V4.** They were deleted from
  `AnswerRequest` on the stated grounds that "no milestone produces SQL".
  **That reason was wrong** — the spec's V4 (SQL generation) does, and
  `docs/spec/before-we-ai-systemarchitektur.md:59` says its result goes into
  the question card. The deletion stands (nothing set or read them), but they
  are unbuilt scaffolding that comes back, not dead weight. The V4 slot is
  now free: the request contract was renamed off it 2026-08-01.

- **Domain-guide acceptance kit — decided 2026-08-01, half done.** Part 3
  (the coherence lint) was already shipped. Parts 1+2 are now a **standing
  rule** in `meta/conventions.md`: no new domain law without a holds-fixture
  and a violated-fixture, no new role without a wrong candidate that must
  lose. Cheap per law, expensive to backfill — which is exactly why it is a
  rule rather than a task.

  **What remains is the backlog:** the three existing finance laws
  (`balance`, `subledger_equals_gl`, `ic_symmetry`) have no such fixtures.
  One focused session. **Not a Copilot package** — writing a *violating*
  fixture requires knowing what breaks a conservation law, which is domain
  judgement, not execution. Analysis: architecture.md → "The domain pack is
  the critical … input".

- **Seeded-Recall: split the metric first, set the bar after M5** (decided
  2026-08-01). One number today mixes two populations. Relationship-style
  traps are answerable now; definition-style traps need documents (a sign
  convention lives in a policy, not a column), and the misses cluster there.
  A single bar over 25 traps would therefore have to sit below the noise
  floor (±2–3) to be passable, which makes it say nothing.

  So: **count the two classes separately**, then a bar over the
  relationship-style half is meaningful immediately and M5 cannot move it.
  The other half gets its bar when M5 lands. The split is worth more than
  the bar anyway — it says *which kind* of knowledge is missing, which one
  number never could.
- **Evaluate a real layout analyser for the extraction layer (after M5).**
  We write no PDF parsing — PyMuPDF does all of it — but the ~40 lines
  deriving `kind` from geometry are the weakest part of the pipeline, and
  the hard document already measures exactly how weak: it beats us on the
  unruled table (H4) and on two-column reading order. Both are layout
  analysis, and better tools exist.

  Candidates: **`pymupdf4llm`/the layout add-on** (same dependency,
  PyMuPDF recommends it itself — the suggestion message is switched off in
  `documents/__init__.py`) and **Docling** (IBM, MIT: layout model, table
  structure, reading order, bboxes as provenance).

  **Not blocked on taste — blocked on determinism.** Docling ships ML
  models; CI is fully offline and chunk bytes feed fixture hashes, so a
  first-run model download would break both. Evaluate against
  `corpus/data/hard/acme_annual_extract.pdf` as the benchmark; it already
  pins the six behaviours that decide it. The swap is cheap by
  construction: everything downstream sees only `Block` (page, text,
  bbox, kind), so the rule, the figure reader and V3 do not change.

- **Standalone demo dataset** — one correct journal, one attractive wrong
  export, an account master, a sign convention, a non-inferable policy;
  intended as the first user experience. Needs its own recorded V1 / role /
  V2 answers, so it rides the M5 live session.
- **`scripts/` at repo root** is reserved by `CLAUDE.md` (start the process,
  readiness report, cleanup of stale processes) and does not exist yet —
  **deliberately**. An empty reserved directory is a claim with nothing
  behind it; it appears when the first operations tool does.

  The one candidate was deleted with the branch `copilot/create-scripts-folder`
  (commit `4d59382`, recoverable by that SHA): 71 lines copying generator
  output into the corpus, with default paths from before the `src/`
  reorganisation (`/workspace/raw-training-data`, `<root>/corpus/data` — both
  now wrong). And the operation itself is a *re-baselining* of a deliberately
  frozen corpus, which invalidates every pinned number and every fixture. It
  must be rare and deliberate; rewriting it correctly then costs ten minutes,
  merging it stale costs a file that rots further.

## Standing constraints

- **The Anthropic API key is reused, not rotated** (owner decision). Since
  2026-08-02 (owner decision) it lives in `~/.zshenv` — outside the repo,
  chmod 600 — so every shell exports `ANTHROPIC_API_KEY`. It is never
  written to any file inside the repo, never committed, never logged, and
  never pasted into a transcript.
- `docs/spec/` is the owner's authoritative German spec — edit only on an
  explicit owner decision. Everything else is English.
- Prompt bytes change only with a deliberate fixture re-record; the drift
  guard is the proof. **It only became the proof on 2026-08-02** — until
  then the guard hashed the built input and nothing else, so rewording a
  system prompt left every fixture stale and CI green. Found by mutating
  V3_SYSTEM and watching it say nothing. Fixtures now carry
  `system_sha256` alongside `input_sha256`, both are checked, and a second
  guard asserts that no fixture escapes either check.
