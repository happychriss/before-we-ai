# Project Memory — live state and open points

<!-- Forward-looking only: what is in flight, what is undecided, what is
     queued. No history — git has that. Durable facts belong in README.md
     (roadmap + status) and docs/ (confirmed design). -->

## Where we are

- **Built:** M0 corpus · M1 core · M2 ingestion · M3 checks & engine ·
  M4 LLM contracts V1/V2 · readiness report · M6 question flow +
  ReadinessMap · **answer types** (the guide declares what a family of
  question depends on; the model classifies, the engine expands, a human
  confirms) · **the outer-layer refactor** (all seven work packages) · **M5 documents & V3** (PDF pipeline, anchors,
  multi-anchor reconciliation, `tell` + mirror loop; complete 2026-08-02,
  all four finish-line leftovers closed with tests) · **M7.1 staleness**
  (flagging + replay; the store now notices when its data moves —
  `docs/architecture.md` → "Staleness").
- **The road ahead is consolidated** (owner decision 2026-08-02): M7
  makes the engine consumer-ready, M8 builds the end-user GUI on the M7
  projection, M9 computes the answer (V4 + Assumption Capture). Scope per
  milestone: the Next list below. The readiness report stays as the
  debugging surface; the GUI speaks no claim vocabulary.
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
  stage; re-pinned end to end 2026-08-02 after the live re-record): 12 sources
  (6 data, 6 documents) · 260 column profiles · 6 pages / 10 passages, 1 inside
  a chart · 54 hypotheses / 1 deduped / 1 skipped · 22 candidates · 61 plans /
  9 unbindable / 6 semantic-only / **0 skipped** · 4 param normalizations ·
  9 document claims / 9 anchors / 2 links / 5 refusals · 61 executed,
  46 pass / 15 fail · 6 role questions, 24 open in total · 2 statements told
  (1 parked, 1 claim) · 9 required-knowledge items · verdict **blocked**,
  naming `journal.entity`, `journal.period`, `journal.account`,
  `intercompany`. Seeded-Recall unmoved at 14/25. Since M7.2 the guide
  declares **2 answer types** and its fingerprint is `c22ad2e5a8e0`; every
  other pin above survived that change untouched, which is the blast radius
  the guide's shape was designed to have.

## Next

**Consolidated 2026-08-02 (owner decision): two milestones to the GUI, not
one.** M7 prepares the engine for a consumer; M8 builds the end-user GUI on
top of it. Deliberately not merged: a milestone needs one acceptance it can
fail, and a combined one would gate our engine work on the guide builder
(another workstream) and the GUI on both. The readiness report stays as the
debugging/understanding surface; the GUI is end-user facing and speaks no
claim vocabulary.

1. **M7 — consumer-ready engine.** Everything the GUI needs, proven before
   the first UI commit. Scope:
   - ~~**Staleness, both halves** (flagging + replay).~~ **DONE
     2026-08-02** — `before_we_ai/staleness.py`, design in
     `docs/architecture.md` → "Staleness". Acceptance per spec :69 runs in
     `tests/corpus_driven/test_staleness_replay.py`. What it cost that the
     plan did not foresee: `table_fingerprint` was blind to a value edited
     in place (row count / schema / max date all unchanged), so it gained a
     `content_hash`; and the 3c friction turned out not to be a bug to fix
     but a rule to state — measuring and judging stages are re-runnable,
     offline *proposal* stages are not, and 3c now says so when it refuses.
   - ~~**Second answer type** (receivables).~~ **DONE 2026-08-02** —
     `open_receivables` in `domains/finance.yaml`, design note in
     `docs/architecture.md` → "Answer types", behaviour pinned in
     `test_llm_offline_corpus.py::TestTwoFamiliesInOneLandscape`. Two live
     calls, recorded through `--only request` (a new flag: `--only-drifted`
     protects the fixture, not the wallet). **Left open on purpose**: the
     guide declares no fields under `subledger_ar`, so the type promises a
     total, not a break-out by customer. Adding those fields moves the role
     list and with it the role-binding/V2 recordings and every walkthrough
     pin — do it inside the next full re-record, never as a side effect.
   - ~~**Request lifecycle**: revisions + a request fingerprint on confirm
     acts.~~ **DONE 2026-08-02** — `llm.request.revise()`, design in
     `docs/architecture.md` → "Revising a question", behaviour in
     `tests/unit/test_request_revisions.py`. No new recording: revising the
     P&L question into the receivables one replays the two classifications
     already on disk. **Decided along the way**: a revision keeps the
     request's identity (so waivers and links survive an edited typo) and
     `Review.lapsed_by` distinguishes "guide" from "question", because the
     reader needs to know whether a shared vocabulary moved or they did.
   - **End-user projection + reference resolver**: a second projection over
     the same store, no-claims vocabulary; ULID → user-space location
     (PDF: source/page/quote — already on every anchor; tables:
     source/sheet/column — encoded in every binding). Cell-level provenance
     through the Excel normalization is explicitly OUT (UI phase, if ever).
     **This is also where the two open work-list points land** (from the
     owner's review of what an analyst actually receives): (3) candidates
     expanded in the compact list view, (4) the two directions of one
     `ic_symmetry` law collapsed to one decision — both presentation, so
     they belong to the projection, not the engine. Plus the mockup's tab split (guide
     decision vs answer issue) as a derived field on each question.
   - **Two small acts the mockup demands**: "I don't know" (a defer act, so
     a seen-but-undecidable question stops ranking as unseen) and
     `Source.description` (the human sentence the UI shows per source).
   - **Document screening that reads tables as tables** (owner decision
     2026-08-02, added mid-M7 — "remember the layout drama"). Plain text
     extraction turns a table into a run of loose words, so a figure that
     lives in a cell is either not a passage a quote can anchor to, or
     anchors to a line that means something else. Evaluate pymupdf4llm /
     Docling, decide one, and make table passages first-class: structure
     carried on the chunk, quote validation that works against it, the
     three anchor kinds actually distinguishable.

     The ~40 lines deriving `kind` from page geometry are the weakest part
     of the pipeline, and `corpus/data/hard/acme_annual_extract.pdf`
     already measures how weak: it beats us on the unruled table (H4) and
     on two-column reading order. Candidates: **`pymupdf4llm`** / the
     PyMuPDF layout add-on (same dependency, recommended by PyMuPDF
     itself — its suggestion message is switched off in
     `documents/__init__.py`) and **Docling** (IBM, MIT: layout model,
     table structure, reading order, bboxes as provenance).

     **Not blocked on taste — blocked on determinism.** Docling ships ML
     models; CI is fully offline and chunk bytes feed fixture hashes, so a
     first-run model download breaks both. Offline, pinned, and
     *deterministic chunk ids* are hard constraints: offline replay, the
     drift guard and the staleness chunk digests all rest on identical
     bytes giving identical chunks. The swap is cheap by construction —
     everything downstream sees only `Block` (page, text, bbox, kind), so
     the multi-anchor rule, the figure reader and V3 do not change.
     Acceptance: the hard document's six pinned behaviours, the corpus
     table figures become anchorable, and F23 (chart-only) still refuses.
   - **Guide-builder integration**: their output loads through the existing
     guide seam (schema, lint, fingerprint, confirmation lapse). Integration
     item only — their code stays theirs.

2. **M8 — the end-user GUI.** Consumes the M7 projection and the operation
   verbs, nothing else — no reads past the seam. The blocked→ready loop
   clickable end to end; jump-to via the resolver; packaging + quickstart
   ride along. **Acceptance includes the spec `:42` run**: real data whose
   truth the owner knows, exercised through the finished UI (owner decision
   2026-08-02 — deferred from M5 to here, deliberately).

3. **After M8, unchanged**: computing the answer (V4 SQL generation +
   Assumption Capture) stays one milestone of its own — see "Declared
   goal" below.

   **Backlog check at consolidation (2026-08-02) — every unscheduled item,
   with its landing place, so nothing is lost between here and M7:**
   - work-list points 3 & 4 → **M7** (projection bullet above);
   - `scripts/` ops tools + Typer CLI verbs → **M8** (they ride packaging;
     `with-api-key.sh` exists already);
   - spec `:42` real-data run → **M8 acceptance** (owner decision);
   - layout-analyser evaluation (pymupdf4llm / Docling) → **M7** (owner
     decision 2026-08-02, moved here from unscheduled: extraction quality
     turns out to gate what can be anchored at all, so it is not merely
     downstream polish);
   - Seeded-Recall metric split → unscheduled; eval-script only, do it
     with the next recording session rather than as its own errand;
   - acceptance-kit holds/violated fixtures for the three finance laws →
     unscheduled (conventions.md rule applies to *new* laws; these three
     predate it);
   - standalone demo dataset → **M8** (it is the first-user experience,
     which is what M8 ships);
   - two-sided laws as paired claims → deliberately unscheduled, recorded
     boundary in `docs/architecture.md` (the false-promotion hole is
     closed; only the object model remains);
   - cell-level Excel provenance → OUT until a UI user asks for it.

## Declared goal — computing the answer (after M8; not scheduled)

> Scheduling note 2026-08-02: the *interaction* half of the GUI goal below
> is now scheduled as M7+M8 (Next, items 1–2). What this section keeps is
> the part that stays its own milestone: V4 + Assumption Capture.

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

### M5 kickoff batch — ALL FIVE DONE 2026-08-02

Kept for the reasoning, not as a to-do list.

1. `discover(root)` sources discovery + bundled domain guides — **done.**
   Merge never overwrites; `domain_guide_file: finance` resolves to the
   shipped pack.
2. Show the domain tag in the V2 template docs — **done.**
3. Mapping claims binding to *generic* templates — **done**, with the
   refutation-only rule (owner decision): a generic check over a role
   refutes but never establishes, via `establishes: False` on the
   evidence payload. All three `account` candidates pass an anti_join
   and none of them promotes.
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
5. **Normalize `view.column` given for a view param — DECIDED 2026-08-02,
   and done: normalize, but record the correction.** The owner took the
   third option rather than either simple one. The check runs (so a
   binding the model shaped wrongly is no longer lost), *and* every
   corrected param is written to the store as a `param_normalized`
   declaration and rendered at the claim: "the model gave X where a bare
   name belongs; it was read as Y". Leniency without a trace is the
   too-loose-law failure — a misunderstood binding runs, passes, promotes,
   and nothing says we changed it.

   **The number that came out of it is the interesting part: 25
   corrections on this corpus, not one.** Column normalization had been
   happening *silently since M4*; only the view-param case was ever
   visible, and only as a failure. The decision did not add leniency so
   much as reveal how much was already there.

   Effect on the pins: 42 → 43 check plans, 7 → 6 V2 skips, 32 → 31
   claims without a check.

## Open decisions (owner)

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
- **Standalone demo dataset** — one correct journal, one attractive wrong
  export, an account master, a sign convention, a non-inferable policy;
  intended as the first user experience, which is why it rides **M8**. It
  needs its own recorded V1 / role / V2 answers, so it belongs to whichever
  recording session M8 does anyway.
- **`scripts/` at repo root** holds exactly one tool so far:
  `with-api-key.sh`, the only way the Anthropic key reaches a process. The
  rest that `CLAUDE.md` reserves — start the process, readiness report,
  cleanup of stale processes — rides **M8** with packaging. A tool appears
  when something needs it, never as an empty reserved slot.

  The one candidate was deleted with the branch `copilot/create-scripts-folder`
  (commit `4d59382`, recoverable by that SHA): 71 lines copying generator
  output into the corpus, with default paths from before the `src/`
  reorganisation (`/workspace/raw-training-data`, `<root>/corpus/data` — both
  now wrong). And the operation itself is a *re-baselining* of a deliberately
  frozen corpus, which invalidates every pinned number and every fixture. It
  must be rare and deliberate; rewriting it correctly then costs ten minutes,
  merging it stale costs a file that rots further.

## Standing constraints

- **`guide_builder` is somebody else's work in progress — do not touch
  it** (owner instruction 2026-08-02: "ignore the guide-builder and
  corpus-vessel folder, other project"). It lives uncommitted in the
  tree as `src/before_we_ai/guide_builder/`, two `test_guide_builder*`
  files, plus edits to `src/before_we_ai/llm/config.py` (a
  `guide_builder` model tier) and `src/pyproject.toml` (a package
  entry). **Never `git add -A`** — stage your own paths explicitly, or
  you will commit their in-flight work. Note `pyproject.toml` names a
  package that is only partly on disk, so a fresh `pip install -e .`
  may break; the running editable install does not notice, which is why
  the suite stays green.
- **The Anthropic API key is reused, not rotated** (owner decision). It
  lives in `~/.config/before-we-ai/api-key` — outside the repo, chmod 600 —
  and reaches a process **only** through `scripts/with-api-key.sh`, which
  exports it for one command via `exec`. It is never written to any file
  inside the repo, never committed, never logged, and never pasted into a
  transcript.
  **Never put it back into `~/.zshenv` or any shell startup file, and never
  `export` it in a shell you keep working in.** It sat in `~/.zshenv` from
  2026-08-02 07:10 to 16:21, and every zsh loads that file — including the
  one Claude Code starts in. Claude Code takes `ANTHROPIC_API_KEY` from the
  environment and bills the *assistant session* to it, so a 1M-context Opus
  chat was charged to the key the owner had funded for a handful of
  recordings. The owner found it on the bill, not in a log. The recordings
  were never the expensive part. Rule: scope a credential by the **process**
  that may spend it, not by what it was intended for — and when setting a
  credential up, say out loud who else in the room can now see it.
- `docs/spec/` is the owner's authoritative German spec — edit only on an
  explicit owner decision. Everything else is English.
- Prompt bytes change only with a deliberate fixture re-record; the drift
  guard is the proof. **It only became the proof on 2026-08-02** — until
  then the guard hashed the built input and nothing else, so rewording a
  system prompt left every fixture stale and CI green. Found by mutating
  V3_SYSTEM and watching it say nothing. Fixtures now carry
  `system_sha256` alongside `input_sha256`, both are checked, and a second
  guard asserts that no fixture escapes either check.
