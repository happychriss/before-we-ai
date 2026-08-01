# Project Memory — live state and open points

<!-- Forward-looking only: what is in flight, what is undecided, what is
     queued. No history — git has that. Durable facts belong in README.md
     (roadmap + status) and docs/ (confirmed design). -->

## Where we are

- **Built:** M0 corpus · M1 core · M2 ingestion · M3 checks & engine ·
  M4 LLM contracts V1/V2 · readiness report · M6 question flow + ReadinessMap.
- **Suite: 391 pass**, fully offline (`cd /workspace/src &&
  source /workspace/.venv/bin/activate && python -m pytest -q`).
- **Standing measures:** False-Promotion **0** (non-negotiable at every
  commit) · Seeded-Recall **14–15/25** · prompt-leakage scan CLEAN.
- **Walkthrough pins** (offline; `validation/README.md` carries them per
  stage): 52 hypotheses / 0 deduped / 3 skipped · 22 candidates · 42 plans /
  19 unbindable / 6 semantic-only / 7 skipped · 42 executed, 35 pass / 7 fail ·
  6 role questions, 13 open in total · 9 required-knowledge items · verdict
  **blocked**, naming `journal.entity`, `journal.period`, `journal.account`,
  `intercompany`.

## Next

1. **Owner validation run using only the readiness report.** Deferred twice.
   Reading real output has found things the suite did not, repeatedly.
2. **M5 — documents & V3.** PDF pipeline, position anchors, DuckDB FTS,
   multi-anchor reconciliation, `tell` + mirror loop. Acceptance: T8
   negatives and a real PDF — every PDF it needs is in the frozen corpus
   (`src/corpus/data/`, including `noise/`).

   Its target is concrete: the three unsupported **rule** items in the
   ReadinessMap (`which accounts are profit and loss`, `sign convention for
   income and expense`, `month cut-off for late postings`). A sign convention
   lives in a policy, not in a column. V3 must **link** the claims it
   produces to the rules they answer (`readiness.link_claim` — the seam is
   built and tested).

   It also unlocks three walkthrough claims whose V2 refusals literally name
   documents: `decodes` account ranges, the AR control account, and
   opening-balances coverage. Read them in the readiness report.

   One design question to settle at the start: **the request's scope is
   inferred by V4 from prose and never confirmed.** "P&L for Germany" — scope
   or break-out? That single inference decides which elections run, which
   cards are drafted and which claims count, so a wrong scope yields a
   confident, fully-reasoned, wrong verdict. The spec's mirror loop already
   demands scope confirmation for `tell` statements; M5 builds that machinery
   anyway, so the AnswerRequest's scope should ride it.

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

- **The request contract sits on the spec's V4 slot, which belongs to SQL
  generation.** `docs/spec/before-we-ai-systemarchitektur.md:53` assigns the
  four contract numbers: V1 hypotheses, V2 check binding, V3 document
  interpretation, **V4 SQL generation**. What is built and called V4 is the
  *request* contract (business question → `AnswerRequest` +
  `RequiredKnowledge`), which the spec does not number at all — and the
  built-but-unnumbered `role_binding` already proves five contracts do not fit
  four slots.

  Rename `llm/v4_request.py`, `CONTRACT = "v4_request"`, the fixture filename
  and the `DEFAULT_MODELS` key to **`request`**, leaving V4 free. Mechanical:
  no prompt bytes move, and fixture lookup is by contract+scenario, so only
  the filename changes. Do it before the M5 live recording, or the recorded
  fixture lands under the wrong name too.

  Related and already acted on: `sql`/`result_ref` were deleted from
  `AnswerRequest` on the stated grounds that "no milestone produces SQL".
  **That reason was wrong** — the spec's V4 does, and `:59` says its result
  goes into the question card. The deletion still stands (nothing set or read
  them), but they are unbuilt scaffolding that returns with V4, not dead
  weight.

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
