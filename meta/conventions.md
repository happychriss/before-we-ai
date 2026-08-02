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
  Domain rules enter the product only as data — tell statements, documents, checked
  patterns — becoming Claims, never Python. When tempted to add domain logic, ask:
  "should this be a Claim instead?"
- **Status changes only via check or human evidence.** A new evidence type or status
  is an epistemic-law change — treat as such. AI/system actors structurally cannot
  author promoting evidence.
- **Growth contract:** a new normalization rule = one case in `sources/canonical.py`
  + one unit test + auto-declaration. Downstream never enumerates rules.
- **No new domain law without its two fixtures** (decided 2026-08-01): one
  where the law *holds* and one where it is *violated*, and for a new role a
  wrong candidate that must lose its election. A law is only as good as the
  case that would break it — a too-loose one passes everything, elects the
  wrong candidate, and now produces a confident, product-branded "ready"
  that has collected a human confirmation on the way. Cheap per law,
  expensive to backfill: that is why it is a rule and not a task. (The three
  existing finance laws are the backlog; `meta/memory.md` → acceptance kit.)
- **Rule of three for the controlled vocabularies.** A new **check template**
  or a new **predicate** is added only when a concrete corpus case forces it —
  never speculatively, never "for completeness". Anything the vocabulary
  cannot express is *untestable*, which is a clarification question and a
  visible gap, not a reason to invent an entry. The pressure to add a
  plausible-sounding predicate will come; this is the answer. Same rule
  governs abstractions generally: no ontology, no plugin framework, until a
  third real case demands one.
- **Prompts are part of the product — they stay domain-agnostic too** (M4+): LLM
  prompts may contain generic data-profiling language only; domain knowledge enters
  a prompt exclusively via the profile/source data being passed in. Never encode
  corpus-trap hints in a prompt — that would be teaching to the test and would
  invalidate Seeded-Recall and the blind traps.

## What the model may assert: can we check it?

The dividing line is **not** "does the model touch it" — that rule is too
blunt and costs real capability. It is *can the answer be verified against
something we already hold*.

- `kind` (text / table / chart) is unknowable from the text: a chart
  figure extracts as ordinary prose, so a model asserting it could only be
  believed. **Derived from page geometry, never asked for.**
- `value` (which number a sentence is about) is a reading, and a reading
  is checkable: the named literal must appear in the quote and parse as a
  number. **Asked for, and verified.**

The failure mode this replaced is the tempting one: rather than ask, the
engine *guessed* — largest number in the quote, and before that the first.
Both were tuned until the corpus passed and both are wrong on ordinary
sentences ("earnings per share of 4.12 on 8,312,504 shares"). An unchecked
guess by us is not safer than a checked answer from the model; it is the
same trust, moved somewhere nobody reviews it.

**Test heuristics by mutation.** Invert one, disable one, and see what
turns red. If a safety property depends on it, it is not a heuristic — it
is a law sitting in the wrong place. Anything tuned against the corpus
must survive this before it ships.

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

- Update `docs/before-ai-concept.md`: fold what the milestone added into the
  one linear flow (plain language, canonical vocabulary only — the words in
  `before_we_ai/glossary.py`, no synonyms, no metaphors) and refresh its
  "What comes next?" list and its not-yet-built markers.
- Update the `README.md` roadmap status and `docs/architecture.md` with
  confirmed design decisions; slim `meta/memory.md` back to live state.
- Tag milestones `mN-<name>-vX` and push.

**The docs are forward-looking, not a log.** State the design as it stands
and why, never how it got there: no dates, no "we used to", no "renamed
from", no milestone narrative. A rule keeps its *reason* — that is what
stops it being re-litigated — but loses its story. Open points stay, and
they belong in `meta/memory.md`; git holds the history.

## Readiness report

`src/readiness_report/` is **fully owned code**: review it, maintain it,
extend it, and hold it to the same standards as the rest of the codebase.

## Language policy

- `docs/spec/` stays **German** — it is the owner's authoritative spec and reading
  aid; new canonical English object names appear there as proper nouns.
- Everything else — all other documentation, code, comments, commit messages — is
  **English**. German terms encountered outside spec/ may simply be replaced with
  English equivalents (the German↔English table lives in
  `before_we_ai/glossary.py`).
- No German outside `docs/spec/` — not in prose, not in comments, not in
  quoted spec passages (translate them and cite the section instead).
