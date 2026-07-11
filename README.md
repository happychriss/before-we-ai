# before-we-ai (Expdash)

**Evidence-based context discovery — know what you know before you let an AI answer.**

Expdash helps an analyst understand foreign, scattered data (databases, Excel files,
CSVs, PDFs, notes) quickly — without silently trusting AI inference. The missing layer
between fragmented data and powerful-but-unreliable LLMs is one that keeps track of
*what is known, what is merely assumed, and what is unknown*. That layer is the product.

## Core idea

Most tools let the AI guess relationships and definitions. Expdash treats the
**knowledge status as a first-class object**:

- **Claims** are versioned files with five statuses and an evidence list — no
  confidence scores, just bookkeeping.
- **The AI can only ever produce `inferred`.** Status promotions belong to probes
  (automated SQL tests) and humans. Conflicting evidence forces `unresolved` —
  conflict is never averaged away.
- **Evidence is append-only.** Every probe run records its rendered SQL, verdict,
  and data fingerprints. Nothing is edited, only superseded.
- **Relevance shows itself through use.** Nothing is curated up front; a claim
  becomes load-bearing when questions rest on it (the "epistemic bill of materials"
  per question). Unverified assumptions form a gap list, weighted by how many
  answers depend on them.

Hard invariants: **false-promotion rate = 0** and **zero silent wrong answers**.
The test suite punishes decisiveness where "unresolved" is the correct answer.

## Architecture in one paragraph

One Python package, no services: `pipx install expdash`, point it at a directory.
Files (YAML/Markdown) are the source of truth; everything under `cache/` is
disposable and reconstructible. **DuckDB is the only execution engine** — it
attaches Postgres/MySQL, reads CSV/Parquet, runs the profiling and probe SQL, and
provides full-text search over documents. The LLM is a subroutine behind **four
typed contracts** (hypothesis generation, probe binding, document interpretation,
SQL generation), each with tailored context, schema-validated output, full logging,
and an offline stub mode for deterministic tests. Model quality affects efficiency,
never correctness.

```
myproject/
  expdash.yaml   # sources, model tiers, tolerance overrides
  sources/       # dropped files (csv, xlsx, pdf, txt)
  claims/        # one YAML per claim (5 statuses, evidence refs)
  evidence/      # append-only probe results, anchors, confirmations
  questions/     # question cards (question, SQL, result, bill of materials)
  profiles/      # column profiles, candidate matrix
  reports/       # rendered status / gap reports
  cache/         # DISPOSABLE: duckdb file, fingerprints, llm_log/
```

CLI-first: `init`, `scan`, `hypothesize`, `probe`, `ask "…"`, `tell "…"`,
`confirm <claim>`, `status`, `check`, `report`.

## Validation before code

A **frozen, generated fixture corpus** (finance domain: bookkeeping rules, balance
check as self-test) is built *before* the tool, with seeded traps — leading zeros,
recycled legacy IDs, name-based Excel joins that contradict a CRM note, chance
column overlaps, grain mismatches, dirty Excel headers. Each trap has an expected
verdict; several are designed so the only correct answer is "unresolved". Blind
traps are held back by the owner to test what the implementer didn't anticipate.

## Status

Concept, architecture, and validation basis are complete. Implementation follows
milestones **M0–M8**; the current step is **M0: the finance corpus generator**.

## Roadmap

| Milestone | Deliverable |
|---|---|
| M0 | Fixture corpus generator + expected verdicts (self-checking ground truth) |
| M1 | Epistemic core: models, state machine, promotion rules (pure functions) |
| M2 | Ingestion & profiling (incl. dirty-Excel normalization) |
| M3 | Probe engine + epistemics runtime — validated **without any LLM** |
| M4 | LLM contracts V1/V2 (hypotheses, probe binding) + offline stub mode |
| M5 | Document pipeline + V3 (interpretation with anchor validation) |
| M6 | Question flow + V4 (SQL generation, assumption capture, gap report) |
| M7 | Staleness propagation & replay against a "prod" copy |
| M8 | Packaging (`pipx install expdash`) + 10-minute quickstart |
