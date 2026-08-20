# before-we-ai

**Evidence-based context discovery — know what you know before you let an AI answer.**

before-we-ai (short: **before-ai**) helps an analyst understand foreign, scattered data
(databases, Excel files, CSVs, PDFs, notes) quickly — without silently trusting AI
inference. The missing layer between fragmented data and powerful-but-unreliable LLMs
is one that keeps track of *what is known, what is merely assumed, and what is
unknown*. That layer is the product.

## Run it

Everything below is offline and needs no API key. Recorded model answers are
replayed, so a fresh clone reproduces the same numbers the maintainer sees.

```bash
git clone https://github.com/happychriss/before-we-ai.git
cd before-we-ai
./scripts/bootstrap.sh          # venv, dependencies, DuckDB fts, verify
source .venv/bin/activate
python -m pytest -q             # the gate: everything must pass
```

Requirements: Python 3.11+ and network access *once* — for pip and for DuckDB's
full-text-search extension. That extension is not optional and has no fallback
on purpose: a substitute would select different document chunks, and the
selected chunks are what the model gets asked about. `bootstrap.sh` installs it
and tells you exactly what to do if it cannot reach the network. On a machine
with no network at all, use the image instead — it bakes the extension in:

```bash
docker compose run --rm suite
```

Then take the guided tour. [`validation/README.md`](validation/README.md) drives
the pipeline **one stage at a time** over a landscape with 32 seeded errors, and
says what to look for after each one. It is the fastest way to see what this
does that a chat window does not:

```bash
validation/scripts/0-inputs.sh          # ... through 6-readiness.sh
open validation/data/report/index.html  # rebuilt by every stage
```

## Core idea

Most tools ask: how do we make the LLM more reliable? This project asks: **how do we
make the LLM's unreliability irrelevant?** Knowledge status is a first-class object:

- **Claims** are versioned files with five statuses (`proposed`, `test-supported`,
  `contradicted`, `unresolved`, `business-confirmed`) and an evidence list — no
  confidence scores, just bookkeeping.
- **The AI can only ever produce `proposed`.** Status promotions belong to checks
  (deterministic SQL, fixed verdicts) and humans. Conflicting evidence forces
  `unresolved` — conflict is never averaged away.
- **Evidence is append-only.** Every check run records its rendered SQL, verdict,
  and data fingerprints. Nothing is edited, only superseded.
- **What data cannot decide becomes a question, never silence.** Every domain role
  ends in a check verdict or a drafted clarification question — the system is
  allowed not to know, but not allowed to be quiet about it.

Hard invariants: **false-promotion rate = 0** (structural — the AI cannot author
promoting evidence) and **zero silent wrong answers**. The test suite punishes
decisiveness where "unresolved" is the correct answer.

Plain-language walkthrough of the whole flow: [`docs/before-ai-concept.md`](docs/before-ai-concept.md).
Design detail: [`docs/architecture.md`](docs/architecture.md).

## Architecture in one paragraph

One Python package, no services: point it at a directory. Files (YAML/Markdown) are
the source of truth; everything under `cache/` is disposable and reconstructible.
**DuckDB is the only execution engine** — it attaches databases, reads CSV/Parquet/
Excel, and runs the profiling and check SQL. The LLM is a subroutine behind **typed
contracts** (question classification, hypothesis generation, mapping proposals,
check planning, document interpretation), each with deterministic input building,
schema-validated output, full logging, and an offline stub mode for deterministic
tests. Everything domain-specific enters through a declared **domain pack** (a
curated domain-guide YAML + domain-law check definitions) — new domain, new pack,
same machine. Model quality affects efficiency, never correctness.

## The machine, in seven stages

A **stage** is a change in what is known, with one actor responsible. Stage 0
is the precondition — a source list and a domain pack, chosen once. Stages 1
and 6 are the frame around the middle: the question bounds the work, the
verdict closes it.

```
0 inputs         a human declares       → sources, domain guide, domain laws
1 request        a human asks           → classified; what must be known, nothing else
2 measured       nobody, it is counted  → data profiles, candidate overlaps
3 proposed       the AI guesses         → claims, candidates, check plans
  ─────────────── no proposal may promote itself ───────────────
4 tested         the checks judge       → evidence, statuses, elections
5 clarification  a human answers        → what no check could settle
6 readiness      derived, never stored  → ready / with limitations / blocked
```

The line is the structural invariant, not a drawing convention: `Actor.AI`
cannot author promoting evidence, so nothing the model produces changes what is
believed. Full table with what each stage reads and produces:
`docs/architecture.md` → *The stage spine*, held as data in
`before_we_ai/stages.py`. Running it stage by stage: `validation/README.md`.

```
myproject/
  before-ai.yaml # sources, domain guide, model tiers, tolerance overrides
  sources/       # dropped files (csv, xlsx, pdf, txt)
  claims/        # one YAML per claim (5 statuses, evidence refs)
  evidence/      # append-only check results, anchors, confirmations
  answers/       # answer requests + the knowledge each one requires
  questions/     # clarification questions
  checks/        # persisted check plans
  profiles/      # data profiles, candidate matrix
  reports/       # rendered status / gap reports
  cache/         # DISPOSABLE: duckdb file, fingerprints, llm_log/
```

## Validation before code

A **frozen, generated fixture corpus** (finance domain: bookkeeping rules, balance
check as self-test) was built *before* the tool, with 32 seeded traps — leading
zeros, recycled legacy IDs, a lookalike journal, chance column overlaps, grain
mismatches, dirty Excel headers, policy rules that live only in PDFs. Each trap has
an expected verdict; several are designed so the only correct answer is
"unresolved". Blind traps are held back by the owner to test what the implementer
didn't anticipate.

Standing measures: **False-Promotion 0** (structural, non-negotiable),
Seeded-Recall **14–15/25**, prompt-leakage scan clean. The misses cluster in
rules that live only in documents — the document pipeline's job.

**Read the recall number with its caveat.** The scorer matches tokens, not
meaning: fabricated claims carrying the right column names score full marks,
and 21 of 25 matchers are keyed to this corpus's own table names. The figure
is closer to *"did some claim mention the right columns"* than to *"did the
pipeline find the seeded relationship"*, and it will not transfer to a second
landscape as it stands. False-Promotion and the leakage scan are unaffected.
Full measurement and what a rewrite has to do: `docs/seeded-recall.md`.
Owner-facing validation walkthrough: `validation/README.md`.

## What this can be held to — and what it cannot

A product whose argument is *we say what we do not know* has to say what it
does not know about itself. This list is maintained, not decorative: every line
in the first half is checkable against this repository, and a line moves to the
first half only when something in the repository makes it checkable.

### Defensible today

- The AI structurally **cannot promote a claim**; only a deterministic check or
  a named human can change a status. False-Promotion measured **0**.
- Every check result keeps the rendered SQL, the population, the exception
  count, sample offending rows, and the data fingerprints it ran against.
- Every document anchor keeps the source, the page and the verbatim quote, and
  the quote is validated against the passage at write time — an invented
  sentence cannot enter the store.
- Every human confirmation carries an author, a scope and a date. A
  confirmation without a scope is refused.
- The dependency list is **derived on every read** from a reviewed answer type
  plus recorded human acts, never stored — so it cannot describe a guide that
  has since changed.
- A verdict that blocks or limits **names the dependency**, and every satisfied
  item says *how* it is satisfied.
- A confirmation **lapses** when the guide or the question changes, and the
  verdict says which of the two moved.
- When the data moves under a conclusion, readings taken against the old data
  **stop counting**, and the report says which table moved.
- The whole pipeline **replays offline** from recorded model answers, with a
  drift guard over both the built input and the system prompt.
- A stranger can clone this and reproduce all of the above. CI runs the
  README's own commands on a clean machine, so if that stops being true the
  build goes red.

### Not defensible yet

- **"The ground rules are themselves tested."** The three finance domain laws
  have no holds-fixture and no violated-fixture, and no role has a deliberately
  wrong candidate that must lose. This is the single sentence the project most
  wants to say and cannot.
- **"Any recall number."** Seeded-Recall is 14–15/25 with ±2–3 run-to-run
  noise, no agreed bar, and — measured 2026-08-20 — a scorer that matches
  tokens rather than meaning. It reports; it never gates; it is not a figure to
  quote. See `docs/seeded-recall.md`.
- **"It has been proven on real data."** Every number comes from one frozen
  synthetic finance landscape built by the same people who built the tool. A
  second, independent landscape now ships (`corpora/vessel/`) precisely because
  that is a fair test of the mechanism and no test of the world — but it has
  not been read yet.
- **"The software reads your policies and proposes your rules."** That is the
  guide builder: an experimental slice in a separate workstream, not
  integrated.
- **"There is a UI."** M8. Today's surface is the readiness report and the
  owner walkthrough.
- **"It computes the answer."** M9. The product gates answers; it does not
  produce them.
- **"It works on your semantic layer."** No import seam from LookML, dbt or
  Datasphere exists.

The standing trap, written down so it stays visible: *"the data is consistent
with the ground rules, therefore the interpretation is right"* is affirming the
consequent. Data can refute an interpretation. It can never confirm one. Any
sentence that drifts back toward the friendlier version is wrong, however well
it reads.

## Roadmap & status

| Milestone | Deliverable | Status |
|---|---|---|
| M0 | Fixture corpus generator + expected verdicts (self-checking ground truth) | ✅ built |
| M1 | Epistemic core: models, state machine, promotion rules (pure functions) | ✅ built |
| M2 | Ingestion & profiling (incl. dirty-Excel normalization) | ✅ built |
| M3 | Check engine + epistemics runtime — validated **without any LLM** | ✅ built |
| M4 | LLM contracts V1/V2 (hypotheses, check planning) + offline stub mode | ✅ built |
| — | Readiness report (read-only validation UI, one self-contained HTML) | ✅ built |
| M6 | Question flow (`AnswerRequest` → `ReadinessMap`: ready / ready_with_limitations / blocked), elections per scope | ✅ built |
| — | Answer types: the guide declares what a family of question depends on; the model classifies, the engine expands, a human confirms | ✅ built |
| M5 | Document pipeline + V3 (interpretation with anchor validation), `tell` + mirror loop | ✅ built |
| M7 | Consumer-ready engine: staleness flagging & replay ✅, second answer type ✅, request revisions ✅, defer act + source descriptions ✅, end-user projection with jump-to resolver, document screening that reads tables as tables, guide-builder integration | **in progress** — scope in `meta/memory.md` |
| M8 | End-user GUI on the M7 projection (+ packaging & quickstart); acceptance includes the spec `:42` run against real data, through the UI | planned |
| M9 | Computing the answer: V4 SQL generation + Assumption Capture (one milestone — capture has nothing to parse without generation) | planned |

Authoritative German spec: `docs/spec/` (read-only). Live project state:
`meta/memory.md`.
