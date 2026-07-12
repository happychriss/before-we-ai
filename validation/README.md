# M4 validation walkthrough — owner's guide

You drive the pipeline **one stage at a time** with the scripts in
`validation/scripts/` and inspect what each stage produced before moving on.
Everything lands in `validation/data/` (git-ignored, disposable — `0-reset.sh`
wipes it). The scripts activate the venv themselves; run them from anywhere.

New to the flow or the terminology? `docs/SIMPLE-README.md` has the big
picture ("The big picture — one pass from start to finish") and a small
glossary — the walkthrough below is that flow, one stage per script.

Default mode is **offline**: the recorded real answers (Opus 4.8 / Sonnet 5,
2026-07-12) are replayed through the full validation path, so every run is
deterministic and needs no API key. For live calls run
`1-scan.sh --online` and `export ANTHROPIC_API_KEY=...` first.

## The steps

| # | script | pipeline stage |
|---|--------|----------------|
| 0 | `0-reset.sh` | wipe `validation/data/` |
| 1 | `1-scan.sh` | load: ingest all 7 sources, build catalog + profiles |
| 2 | `2-matrix.sh` | initial mapping: table:table value-overlap matrix |
| 3 | `3-hypotheses.sh` | V1: LLM proposes claim hypotheses |
| 4 | `4-role-proposals.sh` | LLM proposes role-binding candidates |
| 5 | `5-bind-probes.sh` | V2: LLM binds claims to probe templates |
| 6 | `6-run-probes.sh` | engine: execute probes, derive statuses |
| 7 | `7-resolve-roles.sh` | lost roles become Fachfragen |
| 8 | `8-collect.sh` | gather everything into a clickable report |

Every step opens with an **INPUT** block naming the files that drove it — the
source list, the role definitions, the profiles, the template catalog, the
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
Good: all 7 sources became `<source>__<table>` views; every normalization is
a visible SYSTEM declaration; **claim count is 0** — the scan never infers.

Who writes the source list: a **human**. `init_project()` creates
`before-ai.yaml` with an empty `sources: []` — the product never discovers
files by itself. For the walkthrough the corpus harness fills it in
(`src/tests/eval/_corpus.py`), and the step prints which corpus files are
*not* listed: `buchhaltungsrichtlinie.pdf` and `rabattvertrag.pdf` carry the
policy traps (F14/F15/F19/F25) and are invisible here — PDFs are only
fingerprinted, the document pipeline is M5.

### Step 2 — mapping (candidate matrix)

Look at: top pairs by containment (`--top 30` for more); full table in
`data/project/profiles/candidate_matrix.md`.
Good: the real finance joins (accounts, document refs across de_erp / us_erp /
buchungen_report / the Excel files) score high — and some coincidental
overlaps are in the list too. That is by design: the matrix measures, never
judges; filtering happens later via probes.

### Step 3 — V1 hypotheses

Look at: created/deduped/skipped counts, predicate mix, sample claims; then
`llm-log.sh 1` for the verbatim prompt and answer.
Good (offline pins): **62 created, 1 deduped, 2 skipped** with visible
reasons; every claim `inferred`, created by `ai`, with a structured
predicate. Audit the prompt: profiles + matrix only, no corpus hints.

### Step 4 — role proposals

Look at: candidates per role.
Good (offline pins): **23 candidates** over the 8 finance roles, all still
`inferred`; the journal role has three competitors including the CSV report —
competition is wanted, the invariant probes will decide.

### Step 5 — V2 binding

Look at: template mix; the three honest rejection buckets.
Good (offline pins): **58 probes**, **18 unbindable** (model said
`template=null`, with its reason), **8 semantic-only** (no admissible
template exists — the semantic-equivalence class lives here), **1 skipped**
(validation rejected a `ranges: []` binding). Nothing disappears silently:
each of those 27 claims carries a DECLARATION in the store with the verbatim
reason, so the claim viewer shows *why* it was never tested — read them, they
are the sharpest evidence of what the domain pack is still missing (three of
them say, in effect: "the rule is in a document I cannot see" → M5).

### Step 6 — engine sweep

Look at: executed/skipped, verdict mix, role verdicts, the false-promotion
audit line.
Good (offline pins): **58 executed, 0 skipped**; journal role:
`de_erp__gl_postings` **tested**, `buchungen_report` **contradicted** (the
decoy loses), `us_erp__gl_postings` **contradicted** (honest — the data has a
missing intercompany leg); intercompany contradicted everywhere; audit CLEAN.

### Step 7 — role resolution

Good (offline pins): exactly **one** German Fachfrage — the intercompany
role lost every candidate, so it becomes a question carrying both losing
claim ids. The settled journal role drafts nothing.

### Step 8 — collect

Builds `validation/data/report/index.html` linking the claim viewer, the
LLM-call browser, the candidate matrix, and (if `recall.sh` ran) the
Seeded-Recall report. Open it in a browser or VS Code and click around.

## Tools

- `llm-log.sh` — list all LLM calls; `llm-log.sh 2` shows one call fully
  formatted (system prompt, user input, every attempt with its validation
  errors and pretty-printed answer); `llm-log.sh --html f.html` for a
  browsable page. Steps 3–5 also refresh that page automatically at
  `data/report/llm_calls.html` — it opens with the **domain knowledge**
  actually in play (source list, role pack, domain-law templates), every
  call carries a comment mapping it back to its walkthrough step, and the
  page grows as you progress (steps 6–8 add nothing: they never talk to
  the model).
- `viewer.sh` — rebuild the claim viewer HTML at any point mid-walkthrough.
  Steps 3–7 also refresh it automatically at `data/report/claims.html`
  (every step that changes the store). The page mirrors the pipeline: the
  **funnel** on top (85 proposed → 58 bound / 19 without probe / 8
  semantic-only → 58 judged → the derived statuses, every number a filter),
  then the **Fachfragen inbox**, then the **role elections** (winner, and each
  loser with the domain law that felled it), then one claim at a time as a
  story: proposed → bound → judged → context.
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
  **17/25** — the frozen fixtures are one particular (good) sample; the
  official first online run scored 15/25 (`docs/seeded-recall-m4.md`).

## Expected behaviors that are NOT bugs

- Two V1 hypotheses and one V2 binding are skipped on every offline replay —
  the recorded answers kept a few bad items; skips are per-item and visible in
  the logs (`outcome: partial`).
- The **repair attempt is always discarded offline**: when items fail, the
  retry resends only those items, but the stub can only replay the one
  recorded answer — the full batch — so the splice guard refuses it
  (`repair returned 65 item(s), expected 2 — discarded, originals kept`).
  That is the guard working; online the repair gets a real 2-item answer.
- `us_erp__gl_postings` journal candidate is CONTRADICTED — data-honest (the
  US ledger's missing IC leg breaks the per-period balance).
- Online runs sample differently each time (~50–62 hypotheses, recall
  14–15/25); only the recorded fixtures are frozen. Claim statements are
  model-worded — identity/dedup lives in predicate+params, never wording.
- A probe that cannot execute lands in `skipped("execution error…")`, writes
  no evidence, and does not stop the sweep.
