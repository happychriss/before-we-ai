# before-we-ai

**Evidence-based context discovery — know what you know before you let an AI answer.**

before-we-ai (short: **before-ai**) helps an analyst understand foreign, scattered data
(databases, Excel files, CSVs, PDFs, notes) quickly — without silently trusting AI
inference. The missing layer between fragmented data and powerful-but-unreliable LLMs
is one that keeps track of *what is known, what is merely assumed, and what is
unknown*. That layer is the product.

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
contracts** (question decomposition, hypothesis generation, mapping proposals,
check planning; document interpretation to follow), each with deterministic input building,
schema-validated output, full logging, and an offline stub mode for deterministic
tests. Everything domain-specific enters through a declared **domain pack** (a
curated domain-guide YAML + domain-law check definitions) — new domain, new pack,
same machine. Model quality affects efficiency, never correctness.

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

First measured run (M4): **False-Promotion 0**, Seeded-Recall **15/25** — reported
honestly, misses diagnosed (they cluster in document-only rules, which is M5's job).
Full report: `docs/seeded-recall-m4.md`. Owner-facing validation walkthrough:
`validation/README.md`.

## Roadmap & status

| Milestone | Deliverable | Status |
|---|---|---|
| M0 | Fixture corpus generator + expected verdicts (self-checking ground truth) | ✅ done — `m0-corpus-v1` |
| M1 | Epistemic core: models, state machine, promotion rules (pure functions) | ✅ done — `m1-core-v1/v2` |
| M2 | Ingestion & profiling (incl. dirty-Excel normalization) | ✅ done — `m2-ingestion-v1` |
| M3 | Check engine + epistemics runtime — validated **without any LLM** | ✅ done — `m3-probes-v1` |
| M4 | LLM contracts V1/V2 (hypotheses, check planning) + offline stub mode | ✅ done — `m4-llm-v1` |
| — | Readiness report (read-only validation UI, one self-contained HTML) | ✅ done — owned code |
| — | Pre-M6 alignment: domain guide → business objects + fields, coherence lint | ✅ done — 2026-07-31, prompts byte-identical |
| M6 | Question flow + V4 (`AnswerRequest` → `ReadinessMap`: ready / ready_with_limitations / blocked) | ✅ done — 2026-07-31; elections now run per scope; standalone demo dataset pending one live recording |
| M5 | Document pipeline + V3 (interpretation with anchor validation) | next — see `docs/architecture.md`; M5 kickoff batch in `meta/memory.md` |
| M7 | Staleness propagation & replay against a "prod" copy | planned |
| M8 | Packaging (`pipx install before-we-ai`) + 10-minute quickstart | planned |

Authoritative German spec: `docs/spec/` (read-only). Live project state:
`meta/memory.md`.
