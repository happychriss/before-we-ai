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

`src/claim_viewer/` was built by an external agent (PR #2) and stays hands-off —
report issues to the owner instead of editing.
