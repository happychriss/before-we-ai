---
name: before-we-ai-conventions
description: Standing project conventions for before-we-ai — architectural boundaries, validation style, documentation duties
---

# before-we-ai Conventions

Standing rules for this project. Confirmed facts live in `docs/`; this file is
about how to work.

## Architectural boundaries (hard)

- **Corpus is test infrastructure, product stays domain-agnostic.** `src/corpus/`
  (incl. its finance answer-key logic) is never imported by `src/before_we_ai/`.
  Domain rules enter the product only as data — tell statements, documents, probed
  patterns — becoming Claims, never Python. When tempted to add domain logic, ask:
  "should this be a Claim instead?"
- **Status changes only via probe or human evidence.** A new evidence type or status
  is an epistemic-law change — treat as such. AI/system actors structurally cannot
  author promoting evidence.
- **Growth contract:** a new normalization rule = one case in `sources/canonical.py`
  + one unit test + auto-declaration. Downstream never enumerates rules.
- **Prompts are part of the product — they stay domain-agnostic too** (M4+): LLM
  prompts may contain generic data-profiling language only; domain knowledge enters
  a prompt exclusively via the profile/source data being passed in. Never encode
  corpus-trap hints in a prompt — that would be teaching to the test and would
  invalidate Seeded-Recall and the blind traps.

## Corpus & validation style

- **Sources stay heterogeneous and dirty** (native DuckDB/xlsx/csv/PDF, never
  pre-consolidated). Several traps exist only because of format heterogeneity;
  pre-merging would do the tool's ingestion work for it. DuckDB is the execution
  engine, not the storage format.
- **Trap-class-generic checkers:** validation asserts per K-class from
  `expected_verdicts.yaml` tags, never per hardcoded trap ID — this is what makes
  blind traps meaningful.
- **Spot-check, don't re-derive:** Z1–Z4 are validated via business-rule spot-checks
  (F14/F15/F19/F21/F22/F25) read from the spec prose, trusting the generator's own
  self-tests for bulk arithmetic. Don't build a second accounting engine.
- **Ground-truth claims live only in tests** (`tests/corpus_driven/`), keyed by
  scenario; the false-promotion gate is exact tested-set equality.

## Documentation duties (per milestone, before tagging)

- Append a plain-German section to `docs/SIMPLE-README.md` (analogies, no jargon,
  ends with "Mx in einem Satz") and update its "Wie geht es weiter?" list.
- Update `docs/requirements.md` feature status and `docs/architecture.md` with
  confirmed design decisions; slim `meta/memory.md` back to live state.
- Tag milestones `mN-<name>-vX` and push.

## Claim viewer

`src/claim_viewer/` was originally built by an external agent (PR #2) but is now
**fully owned code** (ownership transferred 2026-07-12): review it, maintain it,
extend it, and hold it to the same standards as the rest of the codebase.

## Language policy

- `docs/spec/` stays **German** — it is the owner's authoritative spec and reading aid.
- `docs/SIMPLE-README.md` stays **plain German** by design (per-milestone explainer).
- Everything else — all other documentation, code, comments, commit messages — is
  **English**. German terms encountered outside spec/ and SIMPLE-README may simply
  be replaced with English equivalents.
- No mass rewrite of existing mixed-language content: clean it up opportunistically
  whenever you touch a file anyway.
