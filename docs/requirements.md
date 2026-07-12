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

**Status:** Complete — merged PR #2 (originally external; owned code since 2026-07-12)
**Source:** `/workspace/src/claim_viewer/`

Read-only validation UI rendering one self-contained HTML per project root.
Maintained to the same standards as the rest of the codebase. Component spec,
binding constraints, and known gaps: `docs/claim-viewer.md`.

### 6. V1 hypotheses + V2 probe binding — LLM contracts (M4)

**Status:** Not started — next milestone
**Source:** `/workspace/src/before_we_ai/` (planned)

LLM proposes claim hypotheses from profiles (V1) and binds them to probes (V2), under
strict contracts.

**Requirements:**
- Input builders from profiles — **no hard token limit**: the goal is a
  well-designed system that gives the model complete, well-structured context and
  lets the AI do what it's good at (~25k tokens is a rough orientation, not a cap)
- Pydantic output schemas, one retry, full logging to `cache/llm_log/`
- Stub mode (`--offline`, fixture answers) from day one; CI offline and deterministic
- LLM output can only ever create `inferred` claims — promotion stays with probes/humans
- Acceptance: Seeded-Recall incl. the F7/T7 semantic pair

**Design constraints (owner-aligned 2026-07-12):**
- Prompts stay domain-agnostic — no corpus-trap hints ever (see `meta/conventions.md`)
- The `inferred`-only guardrail must hold **structurally** (actor restrictions in the
  model layer, like `Actor.SYSTEM`), never by prompt discipline alone
- Stub fixtures are refreshed from logged real runs (`cache/llm_log/`) so CI can't
  drift green while real output rots; Seeded-Recall is a separate online eval,
  never a CI gate
- Input builder assembles profiles **deterministically** (stable ordering and
  selection) — reproducible online runs; if anything must ever be trimmed, trim
  visibly (logged), never silently
- If F7/T7 is recalled suspiciously easily, investigate prompt leakage before
  celebrating
