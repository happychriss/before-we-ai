# Project Memory — live state and open points

<!-- Forward-looking only: what is in flight, what is undecided, what is
     queued. No history — git has that. Durable facts belong in README.md
     (roadmap + status) and docs/ (confirmed design). -->

## Where we are

- **Built:** M0 corpus · M1 core · M2 ingestion · M3 checks & engine ·
  M4 LLM contracts V1/V2 · readiness report · M6 question flow + ReadinessMap.
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
2. **The refactor work order — external agent (Copilot), before M5.**
   `meta/refactor-workorder.md`: five packages (test lanes · counts out of
   durable docs · corpus construction out of tests/ · capability boundary
   replacing the source-inspection guardrail · report view-model extraction
   in three phases), each one PR under hard gates — suite green without
   deleting tests, fixtures byte-identical, wording moved never reworded,
   stop-and-report on any pinned-test conflict. Owner reviews each PR with
   `/code-review ultra <PR#>` and re-runs the walkthrough. **Must finish
   before M5 starts** so M5 builds its document sections into the view
   model, not into the old 2,800-line renderer. Recommendation A
   (application layer) is explicitly out of scope — see the GUI milestone
   below. Source paper: `docs/draft-thoughts/`.

3. **M5 — documents & V3.** PDF pipeline, position anchors, DuckDB FTS,
   multi-anchor reconciliation, `tell` + mirror loop. Acceptance: T8
   negatives and a real PDF — every PDF it needs is in the frozen corpus
   (`src/corpus/data/`, including `noise/`).

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

4. **Confirm the answer-type slice against real output.** Built
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

5. **Two small report fixes** (found 2026-08-01 while answering "where does
   the guide live in the process?"):
   - Section 0 does not show the guide's `answer_types:` — so the reader
     sees *that* the question was treated as `profit_and_loss_by_dimension`
     but nowhere what that type declares or what else was on offer, which is
     exactly what judging the classification needs.
   - Section 0's subsections still read `1.1 / 1.2 / 1.3` — pre-spine
     numbering inside a section called 0.

## Declared goal — the GUI milestone (after M5; not scheduled)

Owner statement 2026-08-01: a small product for **one question to one
answer**, with a GUI — ask the question, load documents, run, answer the
open questions, see the readiness map; computing the result is a further
milestone of its own (that one is the spec's V4 SQL generation + Assumption
Capture, where `sql`/`result_ref` return to `AnswerRequest`).

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

- **The finance guide lives in `src/tests/fixtures/` — the wrong home.**
  It is the domain pack, the product artifact the architecture calls "the
  critical input", and the report prints that path prominently, telling the
  reader it is test infrastructure. Decide the real home before a second
  domain copies the mistake: `src/before_we_ai/domains/` (shipped,
  importable) or a top-level `domains/` (data, never code — matches the
  guide's own rule). Mechanical move either way; the fingerprint does not
  change, the printed path does.

- **`sql`/`result_ref` return with the spec's V4.** They were deleted from
  `AnswerRequest` on the stated grounds that "no milestone produces SQL".
  **That reason was wrong** — the spec's V4 (SQL generation) does, and
  `docs/spec/before-we-ai-systemarchitektur.md:59` says its result goes into
  the question card. The deletion stands (nothing set or read them), but they
  are unbuilt scaffolding that comes back, not dead weight. The V4 slot is
  now free: the request contract was renamed off it 2026-08-01.

- **Assumption Capture is unbuilt, unlisted, and its dependency undeclared.**
  `docs/spec/before-we-ai-systemarchitektur.md:59` (`sql` — Fragenfluss):
  sqlglot parses the generated query, checks it against the allowed subset,
  extracts joins and claim-requiring filters, matches them against the claim
  store, and **materialises what is missing as `proposed` claims**. The query
  itself becomes a source of claims — a real epistemic feature, not plumbing.

  It appears in no roadmap row in `README.md`, in no milestone here, and
  `sqlglot` is not in `src/pyproject.toml`. Decide where it belongs: with V4
  (they are the same spec paragraph) or as its own milestone.

- **Domain-guide acceptance kit, parts 1 + 2.** Part 3 (the coherence lint)
  is shipped. Per new law: one holds-fixture and one violated-fixture. Per
  new role: one wrong candidate that must lose. This is the only protection
  against a too-loose law, and it matters more under readiness framing — a
  wrong guide now produces a confident, product-branded "ready". Analysis:
  architecture.md → "The domain pack is the critical … input".
- **The numeric Seeded-Recall bar.** Run-to-run noise is ±2–3 traps, so a bar
  must sit outside it. Misses cluster in definition-style traps that need M5;
  a bar over relationship-style traps only is worth considering.
- **Standalone demo dataset** — one correct journal, one attractive wrong
  export, an account master, a sign convention, a non-inferable policy;
  intended as the first user experience. Needs its own recorded V1 / role /
  V2 answers, so it rides the M5 live session.
- **Remote branch `copilot/create-scripts-folder`** (1 unmerged commit,
  `scripts/copy_raw_data.sh`) — merge or delete.
- **`scripts/` at repo root** is reserved by `CLAUDE.md` (start the process,
  readiness report, cleanup of stale processes) and does not exist yet.
- **PyMuPDF is not a declared dependency.** The spec names it and M5 needs
  it; adding it to `pyproject.toml` is M5's first line of code.

## Standing constraints

- **The Anthropic API key is reused, not rotated** (owner decision). It is
  never written to any file, commit or log; live runs read it from
  `ANTHROPIC_API_KEY` in the shell only, and it is never pasted into a
  transcript.
- `docs/spec/` is the owner's authoritative German spec — edit only on an
  explicit owner decision. Everything else is English.
- Prompt bytes change only with a deliberate fixture re-record; the drift
  guard is the proof.
