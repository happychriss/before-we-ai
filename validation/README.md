# Validation walkthrough — owner's guide

You drive the pipeline **one stage at a time** with the scripts in
`validation/scripts/` and inspect what each stage produced before moving on.
Everything lands in `validation/data/` (git-ignored, disposable — `reset.sh`
wipes it). The scripts activate the venv themselves; run them from anywhere.

New to the flow or the terminology? `docs/before-ai-concept.md` walks the whole
flow in plain language and ends with a glossary — the walkthrough below is that
flow, one stage per script.

Default mode is **offline**: recorded real answers (Opus 4.8 / Sonnet 5) are
replayed through the full validation path, so every run is deterministic and
needs no API key.
For live calls run `0-inputs.sh --online` and `export ANTHROPIC_API_KEY=...`
first — expect different numbers (the model samples).

## The stages

**One spine.** A stage is a change in what is known, with one actor
responsible — *what each stage is, who is responsible, what it reads and
produces*: `docs/architecture.md` → **The stage spine** (held as data in
`before_we_ai/stages.py`). This page is the same seven stages as commands, and
what to look for when you run them.

**The script number is the report section number** — run `3b`, read section 3.
A stage needing several runs, so you can inspect one model call at a time, gets
letters rather than new numbers.

| § | stage | script |
|---|-------|--------|
| 0 | Inputs | `0-inputs.sh` |
| **1** | Request | `1-request.sh` |
| 2 | Measured | `2a-measure-scan.sh` · `2b-measure-matrix.sh` |
| 3 | Proposed | `3a-propose-hypotheses.sh` · `3b-propose-mappings.sh` · `3c-propose-plans.sh` |
| 4 | Tested | `4-test.sh` |
| 5 | Clarification | `5-clarify.sh` |
| **6** | Readiness | `6-readiness.sh` |

**Every stage rebuilds the report when it finishes.** Paths are fixed, so
leave a browser tab open on `validation/data/report/index.html` and reload
after each stage — the interesting thing about this pipeline is what each
stage *adds*, and you can only see that by looking between them.

Tools, not stages, so they carry no number: `reset.sh` (wipe
`validation/data/`), `report.sh` (rebuild on demand — the same rebuild every
stage runs), `llm-log.sh`, `db.sh`, `db-export.sh`, `recall.sh`,
`two-entities.sh`.

Every step opens with an **INPUT** block naming the files that drove it — the
source list, the domain guide, the profiles, the check-definition catalog, the
prompts. An output you cannot trace back to its input is an assertion, not
evidence; for LLM steps the exact bytes sent are in the call log with their
sha256 (`llm-log.sh <#>`).

Rerunning `3a` and `3b` is safe (claim-key dedup catches everything), and `5`
is idempotent. `3c` refuses to run twice: the offline replay answers are keyed
to the first run's claim labels, so a re-bind would misapply them — run
`reset.sh` and walk through again instead.

### Stage 0 — the declared inputs

The precondition, not part of the run: a source list and a domain pack are
chosen once, and many questions are asked against them. This stage creates the
project and writes those declarations, then shows all three before any data is
touched: the **source list** (a human
writes it — the product never discovers files), the **domain guide**, and the
**domain laws** shipped for that domain.

It is the only stage that can fail before measurement: the guide's coherence
lint runs at load, so a guide that contradicts itself — a field declaring a
law, a slot its object's law does not have — is caught here rather than
surfacing later as a strange question.

Good (offline pins): 7 sources; 3 business objects and 5 fields, lint passed;
3 domain laws of 13 templates, the other 10 generic. The step also names the
corpus files *not* listed, so their absence is a visible decision rather than
an oversight.

### Stage 1 — the request

The frame opens. A human asks a business question; the request contract turns
it into an `AnswerRequest` — what output is wanted, over which scope, and
**which family of questions this one belongs to**.

That last part is the load-bearing one. The model does *not* write the list of
what the answer depends on. It names an **answer type** the domain guide
declares, and the engine expands that type's reviewed dependency list. The
reason is the failure mode a written list has: over-listing is visible and
waivable, but **under-listing is silent** — a dependency the model never
mentioned appears nowhere, so nobody can test, waive or ask about it, and the
verdict comes out too generous with nothing anywhere to show why.

It comes *after* the declared inputs for a hard reason: the classification is
made against the domain guide, and you cannot classify a question against a
vocabulary nobody has chosen yet.

The contract reads the question, the domain vocabulary and the answer types —
*definitions only, no profiles*. Whether the data can serve the question is the
rest of the pipeline's job; answering it here would be the model deciding.

Good (offline pins): treated as **`profit_and_loss_by_dimension`**, **0** delta
items drafted, 0 skipped — the question is fully covered by the type, so the
contract stores no list of its own. The expansion is **9** items: the journal,
four of its fields, the intercompany object, and three business rules the
vocabulary does not contain (which accounts are P&L, the sign convention, the
month cut-off). Every one reads `[contract]`.

Three things to look at:

- **The guide fingerprint** next to the classification (`guide 0ac5f94b7b63`).
  Every human decision about this list records it, so a confirmation given
  against one version of the guide cannot go on vouching for another.
- **What is not on the list**: `subledger_ar`. Open receivables do not enter a
  profit and loss, so this question does not require them. That absence is the
  question bounding discovery, made visible — the whole reason the frame
  exists.
- **Nobody has confirmed the classification yet.** Stage 6 will say so.

### Stage 2a — scan

Look at: the **source list** (7 sources — this is what drives everything
downstream), the views with row counts, the normalization declarations.
Good: all 7 sources became `<source>__<table>` views; 260 column profiles;
every normalization is a visible SYSTEM declaration; **claim count is 0** —
the scan never infers.

Who writes the source list: a **human**. `init_project()` creates
`before-ai.yaml` with an empty `sources: []` — the product never discovers
files by itself. For the walkthrough the corpus harness fills it in
(`validation/support/corpus.py`), and the step prints which corpus files are
*not* listed: `buchhaltungsrichtlinie.pdf` and `rabattvertrag.pdf` carry the
policy traps (F14/F15/F19/F25) and are invisible here — PDFs are only
fingerprinted, the document pipeline is M5.

### Stage 2b — the candidate matrix

Look at: top pairs by containment (`--top 30` for more); full table in
`data/project/profiles/candidate_matrix.md`.
Good: the real finance joins (accounts, document refs across de_erp / us_erp /
buchungen_report / the Excel files) score high — and some coincidental
overlaps are in the list too. That is by design: the matrix measures, never
judges; filtering happens later via checks.

### Stage 3a — hypotheses

Look at: created/deduped/skipped counts, predicate mix, sample claims; then
`llm-log.sh 1` for the verbatim prompt and answer.
Good (offline pins): **52 created, 0 deduped, 3 skipped** with visible
reasons; every claim `proposed`, created by `ai`, with a structured
predicate. Audit the prompt: profiles + matrix only, no corpus hints.

### Stage 3b — mapping candidates

Look at: candidates per role — objects first, their fields indented beneath.
Good (offline pins): **22 candidates** over the 8 finance guide entries (3
business objects + 5 journal fields), all still `proposed`; the journal object
has three competitors including the CSV report export — competition is wanted,
the invariant checks will decide.

### Stage 3c — check plans

Look at: template mix; the three honest rejection buckets.
Good (offline pins): **42 check plans**, **19 unbindable** (model answered
`template=null`, with its reason), **6 semantic-only** (no admissible check
definition exists — the semantic-equivalence class lives here), **7 skipped**
(validation rejected the model's binding — e.g. `accounts` given as a string
where the contract requires a list). Nothing disappears silently: each of
those **32** claims carries a DECLARATION in the store with the verbatim
reason, so the readiness report shows *why* it was never tested — read them, they
are the sharpest evidence of what the domain pack is still missing (several
say, in effect: "the rule is in a document I cannot see" → M5).

### Stage 4 — test

Look at: executed/skipped, verdict mix, role verdicts, the false-promotion
audit line.
Good (offline pins): **42 executed, 0 skipped**; verdicts **35 pass, 7 fail**;
journal role: `de_erp__gl_postings` **test-supported**, `buchungen_report`
**contradicted** (the decoy loses — trap F27), `us_erp__gl_postings`
**contradicted** (honest — the data has a missing intercompany leg, trap F22);
audit **CLEAN**. Resulting AI-claim statuses: 35 test-supported, 32 proposed,
7 contradicted.

### Stage 5 — clarification

Every entry in the domain guide declares its settlement path (`decided_by:`,
linted on load). A **business object** is elected by a domain law or by
`clarification` — no arithmetic can decide what a column *means*. A **field**
is a `slot` of its object's law or a `clarification`; it can never declare a
law of its own. The rule is: **every object and every clarification-decided
field ends in a check verdict or a clarification question, never in nothing.**

Good (offline pins): **six** clarification questions, one per unsettled entry —

- `intercompany`, `subledger_ar` — law-decided objects whose invariant V2
  bound to no candidate (an honest `template=null`) →
  "What is missing before the 'intercompany' can be tested? … No proposed
  candidate could be put to the ic_symmetry law at all, so nothing about it
  has been tested."
- `account`, `doc_ref`, `entity`, `period` — clarification-decided journal
  fields → "Which of the proposed candidates is the 'doc_ref'? … No check can
  settle this — what the data means is a business fact, not an arithmetic
  one."

Each question is written ask-first, then the guide's own definition of the
thing being asked about, then what the machine already tried. The candidates
are linked, never written into the sentence; the readiness report renders
them as a list to pick from.

Nothing is drafted for the settled object (`journal`) — nor for its
`amount_local` slot, and the step says so explicitly: the passing balance run
consumed `de_erp__gl_postings.amount_local_currency`, so the posting amount is
answered by evidence that already existed. Note what a pass does *not* buy: the same
run grouped by `period`, and `doc_ref` still has to be asked — a journal
balances per document AND per period, so a passing law never identifies the
grouping column.

The project now holds **13** open questions in total: these 6 plus 7 drafted
by the engine in stage 4 where a check failed or was inconclusive.

### Stage 6 — the verdict

The frame closes. **No model is involved:** the ReadinessMap is derived from
the claims and evidence stages 2–5 produced, and is never stored — re-render
the report and it recomputes.

Good (offline pins): **blocked**, naming `journal.entity`, `journal.period`,
`journal.account` and `intercompany`. The honest verdict on this landscape:
the ledger of record is identified and its amount column is settled, but
nothing yet says which column carries the entity or the period — and a P&L
*by entity and month* is computed from exactly those.

Three things to check, because they are the guarantees:

- **The verdict names its dependency.** A verdict without its reason is the
  one thing this product may not ship.
- **Every satisfied item says *how*.** `journal` is satisfied because its own
  claim is test-supported. `journal.amount_local` is satisfied because the
  balance law of `journal` passed while reading
  `de_erp__gl_postings.amount_local_currency` — its own candidate claims are
  still `proposed`, and the sentence says so. *Satisfied* and *promoted* are
  deliberately different things (owner decision); an item reading only
  "satisfied" would hide the difference.
- **The verdict also judges the list.** The reason ends with a second
  sentence: the list was expanded from `profit_and_loss_by_dimension`, and
  nobody has confirmed that the question depends on nothing more. Whether the
  dependencies hold and whether anyone has read the list of them are different
  questions, and only the second protects against a list that was short to
  begin with.

The stage then confirms the classification in front of you and re-evaluates, so
you can see what the confirmation buys. Here the verdict does not move — it is
blocked on missing dependencies and a confirmation supplies none of them. On a
landscape where everything held, this is exactly the step between
`ready_with_limitations` and `ready`.

Answer the four open mapping questions and the verdict narrows rather than
clearing: `ready_with_limitations`, with the three business rules named as the
limitations they are. That is the third outcome — permit, narrow, or block.

**Try this.** Edit `src/before_we_ai/domains/finance.yaml`, add a fourth
rule to the answer type, and re-run `./scripts/report.sh`. The new dependency
is on the list and named in the verdict, the confirmation you just gave has
lapsed, and nothing in `data/project/` changed — the list was never stored.

## Tools

- `llm-log.sh` — list all LLM calls; `llm-log.sh 2` shows one call fully
  formatted (system prompt, user input, every attempt with its validation
  errors and pretty-printed answer); `llm-log.sh --html f.html` for a
  browsable page. Stages 0 and 3 also refresh that page automatically at
  `data/report/llm_calls.html` — it opens with the **domain knowledge**
  actually in play (source list, domain guide, domain-law check definitions),
  every call carries a comment mapping it back to its walkthrough step, and
  the page grows as you progress (stages 1, 2, 4, 5 and 6 add nothing: they
  never talk to the model).
- `report.sh` — rebuild every artifact on demand. You rarely need it: each
  stage does the same rebuild when it finishes. The readiness page *is* this
  walkthrough,
  rendered from the store, in the same order and under the same stage numbers:
  a **process diagram** on top carrying this project's live numbers (each one a
  link into the section that produced it, with the actor boundary drawn where
  the AI's proposals stop and promotion begins), then
  **0 inputs** (the three declared domain inputs), **1 request** (the question
  verbatim, the classification with its guide fingerprint, and every dependency
  with where it came from), **2 measured** (sources, column profiles, candidate
  overlaps), **3 proposed** (the funnel: 74 proposed → 42 planned / 19
  unbindable / 6 semantic-only / 7 skipped → 42 judged → the derived statuses,
  every number a filter), **4 tested** (the role elections — each object with
  its fields nested beneath it: the winner, each loser with the domain law that
  felled it, and for a slot field the column its object's passing law
  consumed), **5 clarification** (the open questions, answered ones folded
  away), **6 readiness** (the verdict and every dependency with the sentence
  saying where it stands), then one claim at a time as a story: proposed →
  planned → judged → context.
- `two-entities.sh` — a tiny synthetic project the frozen corpus cannot show:
  DE and US each own a ledger and a period column, both ledgers pass the
  balance law, and the question is asked *for Germany*. Renders its own report
  at `data/two-entities/report.html`. What to look for: **two** journal
  elections rather than one contest with a loser; **two** period questions,
  which is why the dedup key includes the scope — on text alone the second
  would collapse into the first and lose its candidate; and a readiness map
  that reads only DE's evidence — `journal` for entity DE, `amount_local`
  settled by DE's own passing run with DE's column.
- `db.sh` — SQL shell over the catalog (`db.sh "select …"` for one-shots).
- `db-export.sh` — snapshot the catalog as a **self-contained** DuckDB file
  (`data/project/cache/export.duckdb`) — this is what you point DataGrip at.

### Why external tools can't open `cache/analysis.duckdb`

That file holds only **views**: over ATTACHed ERP databases and over
CSV/Parquet, all referenced by *container-absolute* paths
(`read_csv('/workspace/src/corpus/data/buchungen_report.csv')`). A DuckDB
client on the host opens the file but cannot resolve `/workspace/...` and
fails with `No files found that match the pattern ...`; views over ATTACHed
databases additionally don't survive a fresh connection at all.

So run `db-export.sh` and open `export.duckdb` — 48 real tables, no external
references, browsable from anywhere. Re-export after a re-scan; it is a
snapshot, and `cache/` stays disposable.

Close the file in the external client before rerunning the scripts: a host
DuckDB client takes an exclusive lock, and ours then fails with
`Conflicting lock is held in PID 0`.
- `recall.sh [--online]` — Seeded-Recall scoring in its own project under
  `validation/data/recall/`. The offline replay deterministically scores
  **14/25** — the frozen fixtures are one particular sample; the online run of
  also scored 14/25 (`docs/seeded-recall.md`). Note online runs
  vary by ±2–3 traps.

## Expected behaviors that are NOT bugs

- Three V1 hypotheses and seven V2 bindings are skipped on every offline
  replay — the recorded answers kept a few bad items; skips are per-item and
  visible in the logs (`outcome: partial`).
- The **repair attempt is always discarded offline**: when items fail, the
  retry resends only those items, but the stub can only replay the one
  recorded answer — the full batch — so the splice guard refuses it
  (`repair returned 55 item(s), expected 3 — discarded, originals kept`).
  That is the guard working; online the repair gets a real short answer.
- `us_erp__gl_postings` journal candidate is CONTRADICTED — data-honest (the
  US ledger's missing IC leg breaks the per-period balance).
- Two objects end in "what domain knowledge is missing?" rather than a check
  verdict: the model declined to bind their invariants. That is the honest
  path — an unbound law is a knowledge gap, not a silent pass.
- Online runs sample differently each time (~50–62 hypotheses, recall
  14–15/25); only the recorded fixtures are frozen. Claim statements are
  model-worded — identity/dedup lives in predicate+params, never wording.
- A check that cannot execute lands in `skipped("execution error…")`, writes
  no evidence, and does not stop the sweep.
