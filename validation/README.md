# Validation walkthrough — owner's guide

You drive the pipeline **one stage at a time** with the scripts in
`validation/scripts/` and inspect what each stage produced before moving on.
Everything lands in `validation/data/` (git-ignored, disposable — `0-reset.sh`
wipes it). The scripts activate the venv themselves; run them from anywhere.

New to the flow or the terminology? `docs/before-ai-concept.md` walks the whole
flow in plain language and ends with a glossary — the walkthrough below is that
flow, one stage per script.

Default mode is **offline**: recorded real answers (Opus 4.8 / Sonnet 5) are
replayed through the full validation path, so every run is deterministic and
needs no API key.
For live calls run `1-scan.sh --online` and `export ANTHROPIC_API_KEY=...`
first — expect different numbers (the model samples).

## The steps

| # | script | pipeline stage |
|---|--------|----------------|
| 0 | `0-reset.sh` | wipe `validation/data/` |
| 1 | `1-scan.sh` | load: ingest all 7 sources, build catalog + data profiles |
| 2 | `2-matrix.sh` | link candidates: table:table value-overlap matrix |
| 3 | `3-hypotheses.sh` | V1: LLM proposes claim hypotheses |
| 4 | `4-role-proposals.sh` | LLM proposes mapping claims (role candidates) |
| 5 | `5-plan-checks.sh` | V2: LLM binds claims to check definitions |
| 6 | `6-run-checks.sh` | engine: execute checks, derive statuses |
| 7 | `7-resolve-roles.sh` | unsettled roles become clarification questions |
| 8 | `8-ask.sh` | V4: a business question → what must be known → the ReadinessMap |
| 9 | `9-collect.sh` | gather everything into a clickable report |

Every step opens with an **INPUT** block naming the files that drove it — the
source list, the domain guide, the profiles, the check-definition catalog, the
prompts. An output you cannot trace back to its input is an assertion, not
evidence; for LLM steps the exact bytes sent are in the call log with their
sha256 (`llm-log.sh <#>`).

Rerunning steps 3 and 4 is safe (claim-key dedup catches everything), and
step 7 is idempotent. Step 5 refuses to run twice: the offline replay answers
are keyed to the first run's claim labels, so a re-bind would misapply them —
run `0-reset.sh` and walk through again instead.

### Step 1 — load

Look at: the **source list** (7 sources — this is what drives everything
downstream), the views with row counts, the normalization declarations.
Good: all 7 sources became `<source>__<table>` views; 260 column profiles;
every normalization is a visible SYSTEM declaration; **claim count is 0** —
the scan never infers.

Who writes the source list: a **human**. `init_project()` creates
`before-ai.yaml` with an empty `sources: []` — the product never discovers
files by itself. For the walkthrough the corpus harness fills it in
(`src/tests/eval/_corpus.py`), and the step prints which corpus files are
*not* listed: `buchhaltungsrichtlinie.pdf` and `rabattvertrag.pdf` carry the
policy traps (F14/F15/F19/F25) and are invisible here — PDFs are only
fingerprinted, the document pipeline is M5.

### Step 2 — link candidates (the matrix)

Look at: top pairs by containment (`--top 30` for more); full table in
`data/project/profiles/candidate_matrix.md`.
Good: the real finance joins (accounts, document refs across de_erp / us_erp /
buchungen_report / the Excel files) score high — and some coincidental
overlaps are in the list too. That is by design: the matrix measures, never
judges; filtering happens later via checks.

### Step 3 — V1 hypotheses

Look at: created/deduped/skipped counts, predicate mix, sample claims; then
`llm-log.sh 1` for the verbatim prompt and answer.
Good (offline pins): **52 created, 0 deduped, 3 skipped** with visible
reasons; every claim `proposed`, created by `ai`, with a structured
predicate. Audit the prompt: profiles + matrix only, no corpus hints.

### Step 4 — mapping claims (role candidates)

Look at: candidates per role — objects first, their fields indented beneath.
Good (offline pins): **22 candidates** over the 8 finance guide entries (3
business objects + 5 journal fields), all still `proposed`; the journal object
has three competitors including the CSV report export — competition is wanted,
the invariant checks will decide.

### Step 5 — V2 check planning

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

### Step 6 — engine sweep

Look at: executed/skipped, verdict mix, role verdicts, the false-promotion
audit line.
Good (offline pins): **42 executed, 0 skipped**; verdicts **35 pass, 7 fail**;
journal role: `de_erp__gl_postings` **test-supported**, `buchungen_report`
**contradicted** (the decoy loses — trap F27), `us_erp__gl_postings`
**contradicted** (honest — the data has a missing intercompany leg, trap F22);
audit **CLEAN**. Resulting AI-claim statuses: 35 test-supported, 32 proposed,
7 contradicted.

### Step 7 — role resolution

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
by the engine in step 6 where a check failed or was inconclusive.

### Step 8 — the question, and the verdict

The two ends of the machine, in one step. Steps 1–7 are the middle: they scan
a landscape and test what can be tested. This step puts the frame around
them — the business question that bounds the work, and the verdict that work
earns.

In a driven run the question comes **first**: it defines what must be known,
and nothing else has to be. The walkthrough asks it here because you have just
watched the middle happen and can see what the question does to it.

V4 reads the question and the domain vocabulary — definitions only, no
profiles. Whether the data can serve the request is the rest of the pipeline's
job; answering it here would be the model deciding. Good (offline pins): **9**
required-knowledge items, 0 skipped — the journal, four of its fields, the
intercompany object, and three business rules the vocabulary does not contain
(which accounts are P&L, the sign convention, the month cut-off). Note what is
*not* on the list: `subledger_ar`. Open receivables do not enter a profit and
loss, so this question does not require them — that is the question bounding
discovery, visible.

Then the ReadinessMap, derived with no model involved from the claims and
evidence steps 1–7 produced. Good (offline pins): **blocked**, naming
`journal.entity`, `journal.period`, `journal.account` and `intercompany`. The
honest verdict: the ledger of record is identified and its amount column is
settled, but nothing yet says which column carries the entity or the period —
and a P&L *by entity and month* is computed from exactly those.

Two things to check in the output, because they are the guarantees:

- **The verdict names its dependency.** A verdict without its reason is the
  one thing this product may not ship.
- **Every satisfied item says *how*.** `journal` is satisfied because its own
  claim is test-supported. `journal.amount_local` is satisfied because the
  balance law of `journal` passed while reading
  `de_erp__gl_postings.amount_local_currency` — its own candidate claims are
  still `proposed`, and the sentence says so. *Satisfied* and *promoted* are
  deliberately different things (owner decision); an item reading
  only "satisfied" would hide the difference.

Answer the four open mapping questions and the verdict narrows rather than
clearing: `ready_with_limitations`, with the three business rules named as the
limitations they are. That is the third outcome — permit, narrow, or block.

### Step 9 — collect

Builds `validation/data/report/index.html` linking the readiness report, the
LLM-call browser, the candidate matrix, and (if `recall.sh` ran) the
Seeded-Recall report. Open it in a browser or VS Code and click around.

## Tools

- `llm-log.sh` — list all LLM calls; `llm-log.sh 2` shows one call fully
  formatted (system prompt, user input, every attempt with its validation
  errors and pretty-printed answer); `llm-log.sh --html f.html` for a
  browsable page. Steps 3–5 and 8 also refresh that page automatically at
  `data/report/llm_calls.html` — it opens with the **domain knowledge**
  actually in play (source list, domain guide, domain-law check definitions),
  every call carries a comment mapping it back to its walkthrough step, and
  the page grows as you progress (steps 6, 7 and 9 add nothing: they never
  talk to the model).
- `report.sh` — rebuild the readiness report HTML at any point mid-walkthrough.
  Steps 3–8 also refresh it automatically at `data/report/readiness.html`
  (every step that changes the store). The page *is* this walkthrough,
  rendered from the store, in the same order: a **process diagram** on top
  carrying this project's live numbers (each one a link into the section that
  produced it, with the actor boundary drawn where the AI's proposals stop and
  promotion begins, and M5 shown as a not-built ghost), then
  **1 inputs** (the three declared domain inputs), **2 measured** (sources,
  column profiles, candidate overlaps), **3 proposed** (the funnel: 74 proposed
  → 42 planned / 19 unbindable / 6 semantic-only / 7 skipped → 42 judged → the
  derived statuses, every number a filter), **4 decided** (the role elections —
  each object with its fields nested beneath it: the winner, each loser with
  the domain law that felled it, and for a slot field the column its object's
  passing law consumed), **5 open** (the clarification-questions inbox),
  **6 readiness** (the question verbatim, the verdict, and every dependency
  with the sentence saying where it stands), then one claim at a time as a
  story: proposed → planned → judged → context.
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
