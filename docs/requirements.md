# Project Requirements

## Project Type

Follow `meta/project-setup.md` for working conventions, folder structure, knowledge
flow, and development workflow. Project-specific rules: `meta/conventions.md`.

---

## Project Summary

**before-we-ai** (short: before-ai) — evidence-based context discovery. Helps an analyst
understand foreign, scattered data (databases, Excel, CSV, PDF) without silently trusting
AI inference. Knowledge status is a first-class object: every claim about the data is
inferred / testable / confirmed / contradicted / unknown, with status always derived from
evidence, never hand-set.

- Authoritative German spec: `docs/spec/`
- Source: `src/`
- Confirmed design decisions & gotchas: `docs/architecture.md`, `docs/corpus.md`
- Live state: `meta/memory.md`

Roadmap M0–M8 (deliverable table): `README.md`.

---

## Functional Specification

### 1. Fixture corpus with seeded traps (M0)

**Status:** Complete — frozen, tag `m0-corpus-v1`
**Source:** `/workspace/src/corpus/`

Deterministic dirty-data test corpus (DE/US) with 32 seeded traps across classes K1–K8,
expected verdicts, and a data-driven validation harness. Facts: `docs/corpus.md`.

### 2. Epistemic core (M1)

**Status:** Complete — tags `m1-core-v1`, `m1-core-v2`
**Source:** `/workspace/src/before_we_ai/model/`, `store/`

Pure domain model + derived-status state machine + YAML store. Claims are semantic
rules (not rows) with five evidence types; only probes/humans can promote.

### 3. Ingestion & profiling (M2)

**Status:** Complete — tag `m2-ingestion-v1`
**Source:** `/workspace/src/before_we_ai/sources/`, `profile/`, `scan.py`

Canonicalization of heterogeneous sources into a disposable DuckDB catalog, column
profiles, and a join-candidate matrix. Scan records declarations, creates zero claims.

### 4. Probes & engine — deterministic falsification, no LLM (M3)

**Status:** Complete — tag `m3-probes-v1`
**Source:** `/workspace/src/before_we_ai/probes/`, `engine/`

13 SQL probe templates with deterministic verdicts, dependency-gated sweep, Fachfragen
as QuestionCards. Acceptance held: False-Promotion = 0 against the corpus.

### 5. Claim viewer

**Status:** Complete — merged PR #2 (external agent; hands-off)
**Source:** `/workspace/src/claim_viewer/`

Read-only validation UI rendering one self-contained HTML per project root.

### 6. V1 hypotheses + V2 probe binding — LLM contracts (M4)

**Status:** Not started — next milestone
**Source:** `/workspace/src/before_we_ai/` (planned)

LLM proposes claim hypotheses from profiles (V1) and binds them to probes (V2), under
strict contracts.

**Requirements:**
- Input builders from profiles, <25k tokens per prompt
- Pydantic output schemas, one retry, full logging to `cache/llm_log/`
- Stub mode (`--offline`, fixture answers) from day one; CI offline and deterministic
- LLM output can only ever create `inferred` claims — promotion stays with probes/humans
- Acceptance: Seeded-Recall incl. the F7/T7 semantic pair
