# Product architecture — confirmed design

Per-package confirmed decisions and gotchas for `src/before_we_ai/`. Feature
status: `README.md` (roadmap table). Plain-language walkthrough:
`docs/before-ai-concept.md`. Working rules: `meta/conventions.md`. Open
decisions and live state: `meta/memory.md`.

Everything here is the design as it stands. Where a rule has a reason, the
reason is given — a rule without one gets re-litigated or quietly undone.

## Principles

Four statements the rest of the document is an implementation of.

**The product thesis.** *before-we-ai traces a business answer back to every
mapping, meaning and rule it depends on, tests what can be tested, and blocks
the answer when a material dependency remains unsupported.* It is an
**answer-readiness control layer**: it does not ask whether a data landscape
is generally AI-ready, it decides whether **this specific answer** is.

**The handover.** Measurement stays separate from interpretation. A check
never directly proves a claim and never produces an answer:

```
CheckPlan → CheckRun → Evidence → claim status → readiness decision
```

The AI proposes the path; the engine measures what happened; evidence changes
what the system is allowed to **believe**; the readiness evaluator decides
what it is permitted to **claim**. Each arrow is a different authority, and
none of them may be skipped.

**Capability is not authority, and plausible reasoning is not evidence.**
A more capable model may write the SQL, run it, read the exceptions and
explain the result — and the check must still execute independently against
pinned data. Otherwise one wrong assumption yields plausible SQL, a plausible
result, and a plausible self-verification. The four questions in play are not
the same question:

```
AI reasoning       what is likely?
Deterministic check what happened in the data?
Authority          what does the organisation intend?
Readiness          is the available support sufficient for this use?
```

**Trust is conditional, and ends at a boundary set by consequence.** Not at
the point where a model becomes clever enough. Exploratory analysis may need
only visible assumptions; management reporting needs deterministic
reconciliation and approved definitions; statutory reporting, payments and
pricing need authoritative policy, access control, accountable approval and
an audit trail. The chain:

```
The model may propose.
The data may demonstrate.
A source may authorise.
A human may confirm.
The system may enforce.
The organisation accepts the remaining risk.
```

So the question is never "is this trusted?" but *trusted to do which task,
within which scope, on which evidence, with which consequence if wrong?*

## The stage spine

One spine, referenced by everything else. A **stage** is a change in what is
known, with **one actor responsible**. The readiness report's section numbers,
the walkthrough's script numbers and this document all use it, and the report's
process diagram renders it rather than restating it.

**One home: `before_we_ai/stages.py`** — the same discipline `glossary.py`
applies to the vocabulary. The table below is that data, for reading.

| § | stage | who is responsible | reads | produces |
|---|-------|--------------------|-------|----------|
| 0 | **Inputs** — what a human declared | human | before-ai.yaml, the domain guide file, the check registry | the declared sources, business objects and domain laws |
| 1 | **Request** — the question, and what it requires | human asks · AI classifies | one business question + the domain guide's definitions and answer types | AnswerRequest (with its answer type) |
| 2 | **Measured** — what the data says about itself | no model involved | the declared sources | data profiles, the candidate matrix |
| 3 | **Proposed** — what the AI guessed | AI — proposals only | profiles, the candidate matrix, the domain guide | claims, mapping candidates, check plans — all proposed |
| 4 | **Tested** — what the checks settled | check — may promote | check plans, the data | evidence, derived statuses, scoped elections |
| 5 | **Clarification** — what only a human can answer | human — may promote | what the checks could not settle | clarification questions, and the answers that close them |
| 6 | **Readiness** — what may be answered | derived — never stored | the dependency list, and every claim and status under it | the ReadinessMap: ready / ready_with_limitations / blocked |

**Stage 0 is the precondition, not part of the run.** A source list and a
domain pack are chosen once, and many questions are asked against them. It
comes first for a hard reason, not a stylistic one: the request contract reads
the domain guide, so a question cannot be classified against a vocabulary
nobody has declared yet.

**Stages 1 and 6 are the frame** around the middle (2–5, which runs
bottom-up). The question opens it because it bounds the work — what the answer
does not depend on, nobody has to know — and the verdict closes it.

The **actor boundary** falls before *tested*: everything to its left
is a proposal. That is not a drawing convention but the structural invariant
made visible — `Actor.AI` cannot author promoting evidence, so nothing the
model produces can change what is believed.

**The script number is the section number.** A validator who ran `3b` knows to
read section 3. A stage that needs several runs, so one model call can be
inspected at a time, gets letters (`3a`, `3b`, `3c`) — never new numbers.
Per-stage detail, and the numbers each one should produce offline, live in
`validation/README.md`.

**LLM contracts are not a second numbering.** There are five of them in the
spec's four V-slots, so the contract's *name* is the handle and the V-number
is a spec alias:

| contract | § | spec | status |
|----------|---|------|--------|
| request | 1 | — | built (module `request` — deliberately unnumbered) |
| hypotheses | 3 | V1 | built |
| mappings | 3 | — (Rollenbindung) | built |
| plans | 3 | V2 | built |
| documents | 3 | V3 | not built |
| queries | — | V4 (SQL generation) | not built |

## Vocabulary

`before_we_ai/glossary.py` is the one home of the canonical terms, as data —
every owner-facing surface renders that list, so the definitions cannot drift
apart. Two standing rules:

- **No synonyms.** The words in the glossary are the only words.
- **No domain examples.** These terms render into every project's report
  whatever its domain; a general term explained with a finance example
  teaches a shipyard the wrong thing. Concrete nouns belong in the domain
  guide, which the report quotes from. Enforced by
  `tests/unit/test_glossary.py`.

The German↔English table in `GERMAN_TERMS` maps the owner's spec (`docs/spec/`,
German by design) onto these terms, and is the only place a German term of art
belongs.

**The model's wire contract is fixed** and changes only by deliberate
re-recording: the 13 `REGISTRY` template names, the JSON fields the model
fills (`claim_id`, `template`, `params`, `no_template_reason`, `hypotheses`,
`bindings`), the contract names (`v1_hypotheses`, `role_binding`, `v2_bind`,
`request`) and the claim labels `c1..cN`. Prompt prose may be edited only
together with a fixture re-record; count movement in such a diff is a signal
about prompt fragility, not a schema artifact.

## Dev environment

- Python 3.13, venv at `/workspace/.venv` (system pip is externally-managed)
- Repo root: `/workspace` — https://github.com/happychriss/before-we-ai
  (`pyproject.toml` lives in `src/`)
- Install: `source /workspace/.venv/bin/activate && pip install -e '.[dev]'` in
  `/workspace/src`; run `python -m pytest -q` there — **the gate is that every
  test passes**, and CI runs it fully offline from recorded fixtures. Lanes
  for faster feedback between edits: `meta/project-setup.md`. No exact suite
  count is kept in this document; it went stale three times before anyone
  noticed, and a number nobody acts on is a number nobody maintains.
- Authoritative German spec: `docs/spec/`

## Domain inputs — declared, transparent, validated (cross-cutting)

Everything domain-specific enters through exactly **three declared inputs**;
the rest of the product is domain-agnostic. Each input must be (a) declared
as input, (b) transparent to the user, (c) logically validated:

| input | declared | transparent | validated |
|---|---|---|---|
| raw data | `before-ai.yaml` `sources:` (human-authored) | step-INPUT blocks; fingerprints; SYSTEM declarations | canonicalization + profiling; re-scan idempotence |
| domain guide (data) | `llm.domain_guide_file` | INPUT block prints the file; definitions land in prompts verbatim (logged) | Pydantic `DomainGuide`, `extra="forbid"` + coherence lint (settlement path, slot fillability, a field can never declare a law) |
| check definitions / domain laws (code) | `checks/REGISTRY` | rendered template docs in the V2 prompt (logged); executed SQL kept in evidence; `CheckDefinition.tests` says in business words what each one tries to break, rendered in the readiness report | unit test locks `TEMPLATE_PARAMS` ↔ REGISTRY; review like all code |

Note the asymmetry in that middle column: the **model** is shown
`TEMPLATE_PARAMS` / `TEMPLATE_NOTES` from `llm/vocabulary.py`, the **human**
is shown `CheckDefinition.tests`. They are separate fields on purpose — the
business sentence can be rewritten for clarity without touching a single
prompt byte.

**The product is a general machine only together with a domain pack** —
never on its own (owner decision). A domain pack = the domain
guide (data) + the domain-tagged check definitions (code). What is
domain-specific is therefore explicit and enumerable: `CheckDefinition.domain`
(`None` = generic; today exactly the three invariants carry
`domain="finance"`, 10 of 13 templates are generic), locked by
`test_domain_specific_templates_are_explicitly_tagged`. Showing the tag in
the rendered V2 template docs would change prompt bytes → joins the M5
fixture re-record batch.

### Portability — what a second domain costs

Measured by writing a shipbuilding guide (bill of materials, supply chain) and
rendering a report from it, not assumed.

1. **The narration is domain-neutral.** Every derived sentence composes three
   slots that belong to the domain pack: the guide's **definition**, the
   law's **name**, and the run's **verdict numbers**. "The bom_rollup law
   passed on `pdm__bom_positions` and felled the other candidate" comes out of
   the same template as the finance one. The only sentence carrying business
   meaning is the one the guide's author wrote.
2. **A new domain costs laws, not prose — and it fails loudly.** A guide
   naming a law that does not exist is rejected at load ("`bom_rollup` is no
   check template and not 'clarification'"). A guide of only
   `decided_by: clarification` objects loads and renders, but then nothing is
   ever promoted and every object ends in a question — honest, and no longer
   discovery. Onboarding a domain means writing its conservation laws as SQL
   templates.
3. **Two rules keep it that way**, both test-enforced: the canonical
   vocabulary carries no domain examples (`tests/unit/test_glossary.py`), and
   the law panel shows this project's domain only, counting the rest
   (`test_the_law_panel_shows_this_project_s_domain_and_no_other`). Without
   them a shipbuilding project displays finance laws among its declared
   inputs — laws its own lint would refuse.

### The domain pack is the critical — and currently unverified — input

This is the most load-bearing open weakness in the product; treat it as such.

**Leverage.** The finance guide is **57 lines**, and it alone decides:
(1) what the AI searches for — a concept not named in the guide is invisible,
silently; (2) which candidates compete — too vague yields junk candidates,
too specific yields a single candidate and the election becomes theatre;
(3) which law judges which role; (4) which questions reach the human
(`decided_by: clarification`).

**The asymmetry, stated precisely.** A bad guide *cannot* give the AI power
to promote — that is structural and guide-independent. But the guide decides
**which claim is put to which test, and a passing test does promote.** A role
definition loose enough to admit a wrong table, where that table happens to
pass a real law, is therefore a genuine false-promotion path. The corollary
already stated under "Every role declares its settlement path" is the same
point from the other side: *a journal balances per period AND per document
AND per year, so a passing law never proves what one slot means.* A passing
invariant is strong evidence about **data consistency** and only weak
evidence about **meaning**.

**Measured.** No plausible impostor in the frozen
corpus passes the balance law: `de_erp__intercompany` fails 24/24 periods,
`us_erp__intercompany` 23/23, `de_erp__ar_open_items` 420 groups. So the risk
is not live here — but **what protects us is the shape of this dataset, not
the design.** A real landscape containing a clearing account, a netting
table, or a mirrored export that sums to zero per period could realise it.

**What validates the guide today: almost nothing.** Only the load-time
Pydantic lint (`extra="forbid"`; `decided_by` names a real law of the correct
domain). **Not one of the suite's tests asks whether the guide is correct.** The
`amount_local` mis-declaration (see meta/memory.md, M5 kickoff item 5) was
found by a human reading a generated question and thinking it looked odd —
not by any check. That is not a repeatable quality process.

**Why this is a product concern, not only a code concern.** New domain = new
pack, so the guide is the **unit of onboarding**: every customer means a new
one, and its quality *is* the product's quality for that customer. The person
writing it will usually know the domain, not the machine. That places the
guide-drafting contract (parked as "Onboarding workflow" item 3, post-M5)
closer to the commercial centre of the product than its position suggests.

**Guide acceptance kit — three parts, one shipped.**

1. **Per new law:** one fixture where it holds (check must PASS) and one
   deliberately violated (must FAIL, and only on the seeded row). Catches the
   trivially-passing law — the remaining path to false confidence. **Open.**
2. **Per new role:** at least one wrong candidate that must lose its
   election. Catches definitions too vague to discriminate. **Open.**
3. **Coherence lint** — static analysis over guide + REGISTRY, no data
   needed. **Shipped** (see "Guide by construction"): a field can never
   declare a law, a slot must name a fillable slot of its object's law, and
   the whole mis-declaration class is inexpressible rather than merely
   caught.

Parts 1 and 2 are an owner decision, and they matter more under readiness
framing: a wrong guide now produces a confident, product-branded "ready".

### Guide by construction

Three decisions close the "nothing tests the guide" gap **by construction**
rather than only by testing — a whole class of mistake becomes unwritable
instead of merely detected.

1. **Objects with fields, not a flat role list.** A flat list mixes levels:
   `journal` (a business object) and `amount_local` (a
   field inside it) would both be "roles" with their own settlement paths — which
   is exactly what made the `amount_local` mis-declaration *expressible*. The
   guide now declares **business objects** (`decided_by:` a domain law or
   `clarification`) each with **fields** (`decided_by: slot` plus `fills:`, or
   `clarification`; **a field can never declare a law**). That makes the
   `amount_local` bug class inexpressible — stronger than a lint that merely
   catches it. A slot field settles through its object's passing law from
   evidence that already existed and was simply not connected (`settled_slots`
   — see the resolution bullets under Domain inputs). The **coherence lint**
   (part 3 of the acceptance kit) is built against this shape; the slot-side
   metadata it needs lives on `CheckDefinition.slots`.

   **The hierarchy never reaches the model.** `decided_by` does not enter a
   prompt; objects and their fields flatten in guide order into the same
   rendered definitions a flat list would produce. The hierarchy is consumed
   by the lint, by role resolution and by the elections only — which is why
   the guide's shape can change without a fixture re-record, and the drift
   guard proves it.

2. **Guide provenance — the actor discipline extends to the guide.** The
   generic half (textbook laws and concepts: journals balance, AR ties to a
   control account) may be AI-drafted — it is checkable and fails loudly
   when wrong. The **organisational half** (which price is used for expected
   costing, whether the export is authoritative) is decided, not derivable:
   it enters the guide **only as an answered clarification question**,
   authored by a human. Each guide entry carries provenance
   (`drafted-by-ai` vs `confirmed-by-human`), so the guide stops being a
   hand-written unverified file and becomes made of the same evidence-backed
   material the store already trusts. This sharpens the Onboarding item 3
   guardrail from "a human signs off on the file" to "the binding half is
   human-authored, per entry" — capability is not authority, and
   `decided_by:` is literally an authority statement.

3. **Question-first bounds the guide and makes omissions visible — but does
   not replace the kit.** Under the question-first flow, a guide wrong by
   *omission* surfaces as `blocked` in the ReadinessMap: the question is the
   external referent the guide is measured against, and small per-question
   guides (a page, reviewable) replace an unbounded domain model. A guide
   wrong by **commission** — a too-loose law that a wrong table passes — is
   untouched by question-first; the acceptance kit and coherence lint remain
   the only protection on that path, and they matter *more* under the
   readiness framing, because a wrong guide then produces a confident,
   product-branded "ready".

## Epistemic core (`core/`, `store/`)

- `core/` is pure and IO-free; `store/` is a YAML repo with append-only evidence,
  integrity check, optional git checkpoint.
- **Status is derived, never set**: `resolve_status(claim, evidence)` recomputes
  from non-stale evidence, order-independent. Conflict (check fail + anything
  supporting) → unresolved; fail alone → contradicted; confirmation →
  business-confirmed; pass → test-supported; weak evidence never promotes.
- **Five evidence types** (derived enumeration; spec says "die fünf Evidenztypen"
  without listing): check_result | document_anchor | confirmation | testimonial |
  declaration. Pydantic validators enforce actor consistency — AI structurally
  cannot author promoting evidence.
- **Mirror-loop guard (F29)**: confirmation on a testimonial claim requires explicit
  `Scope` or `attach_evidence` raises `PromotionError`; `resolve_status` also
  ignores inadmissible confirmations.
- **Claims are semantic rules, not rows**: identity = Predicate(name+params) +
  Scope + Validity + source_ids, hashed by `semantics.claim_key()` (wording
  excluded); `store.add_claim()` dedups on key. Check evidence is aggregate-only
  (population / exception_count / exception_samples capped at 20 / result_ref
  parquet). `escalate_exception()` mints a child claim (provenance via
  `derived_from`, NOT status-bearing; child starts proposed). Impact is derived
  (`gap_load()`), never stored.
- Reference usage demo: `tests/acceptance/test_walkthrough.py` (9-step
  "Umsatz-Claim" scenario, F15/F29).

## Ingestion & profiling (`sources/`, `profile/`, `scan.py`)

- **One canonicalization everywhere**: `canonical_text()` + SQL twin
  `canonical_sql_expr()` (unit-tested to agree) bridge BIGINT 1101 / DOUBLE 1101.0 /
  Excel numbers / text '1101'. Genuine text is sacred — leading zeros never
  stripped. Every rewrite class has a rule tag.
- **Normalization decisions = DECLARATION evidence** by `Actor.SYSTEM` (can only
  author anchor/declaration). Dedup on (payload, source_fingerprints) so re-scans
  append nothing. Scan creates ZERO claims — false promotion impossible by
  construction.
- Excel pre-reader: merged-header resolution (parent_child names), all values →
  canonical text → all-VARCHAR Parquet in `cache/normalized/` (DuckDB COPY, no
  pyarrow). CSV read `all_varchar=true`.
- **Catalog**: `cache/analysis.duckdb`, views `<source>__<table>` (xlsx views named
  after sheet title). GOTCHA: views over ATTACHed DBs die on a fresh connection —
  re-open via `sources.open_catalog(root)` (or re-run `build_catalog`, idempotent).
  `cache/` is disposable: delete + re-scan ⇒ identical output, stable profile IDs.
- **Candidate matrix**: stage-1 prefilter (distinct≥2, value-class compat,
  cross-table; hard cap 50k pairs with TRUNCATED warning), stage-2 set-based
  overlap on distinct canonical values; containment threshold 0.5. Deterministic
  JSON+MD in `profiles/` (no timestamps). The matrix measures, never judges —
  chance overlaps deliberately included.

## Checks & engine (`checks/`, `engine/`)

- `checks/REGISTRY`: name → CheckDefinition(file, prepare, verdict, tolerances,
  question); 13 Jinja2 templates in `templates/*.sql.j2`, split by
  `-- ::exceptions::` marker into population + exceptions query. Verdicts
  deterministic.
- **Verdict granularity comes from the claim**: anti_join param
  `expectation: "empty" | "report"` — report-claims (K6 legitimate orphans) can
  structurally never FAIL, only INCONCLUSIVE + drafted clarification question
  (deduped by exact text).
- **Cardinality check = chance-overlap counter-evidence (T6)**: PASS needs
  containment ≥ 0.95 AND parent uniqueness ≥ 0.99.
- Invariants attach to claims like everything else (MappingClaims; F27:
  journal=buchungen_report FAIL → contradicted, rendered SQL kept as reason).
  Amounts CAST, not TRY_CAST — un-castable values crash loudly.
- **Tolerances**: defaults per CheckDefinition; overrides ONLY via `before-ai.yaml`
  `tolerances:` (scalar normalized to `{absolute: v}`).
- **Evidence contract per run**: check_plan_id + rendered exceptions-SQL + summary
  in payload, source_fingerprints per view, samples ≤20, full exception set →
  `cache/check_runs/<evidence_id>.parquet`. CheckPlan persisted before its
  evidence; integrity checks the references. A `CheckRun` is deliberately NOT a
  persisted object of its own — the check_result evidence record already carries
  its exact contents.
- `run_ready`: check plans topo-sorted by claim; `ready_for_check` gates (deps ≥
  test-supported); claim-less plans first; returns RunReport(executed,
  skipped(reason)). A check whose SQL cannot execute is **contained**:
  it lands in `skipped` with the error as reason, writes no evidence, leaves its
  claim untouched — AI-planned checks must never kill the sweep (visibility, not
  judgment; the loud-crash-on-uncastable-amounts contract inside running checks
  is unchanged).
- Normalization is part of the claim: T1 passes canonical, fails with
  `canonical: false` (raw CAST). decode template checks functional dependency,
  not string equality.

## LLM contracts (`llm/`)

- **Thin typed functions, no framework**: `hypothesize(root)` (V1, frontier),
  `propose_mappings(root)` (frontier), `plan_checks(root)` (invariant batch
  frontier / ordinary batch mid-tier) — library seams like `scan(root)`; models
  and offline switch in `before-ai.yaml` `llm:` (defaults in `llm/config.py`;
  key ONLY via env var `ANTHROPIC_API_KEY`, lazy SDK import, optional `[llm]` extra).
  Owner decisions : Anthropic API; `claude-opus-4-8` for V1 + mapping
  proposals, `claude-sonnet-5` for plain check planning.
- **Controlled predicate vocabulary** (`llm/vocabulary.py`): closed `Literal` in
  the output schemas — free-form predicates fail validation. `TEMPLATE_PARAMS`
  mirrors `checks.REGISTRY` key-for-key, locked by a unit test. Every hypothesis
  carries a `Predicate` with canonicalized params ⇒ claim_key dedup works for
  AI claims; `rationale` is logged, never stored (wording-free identity).
  **Provenance, stated so nobody assumes otherwise:** the 13 predicates are
  derived bottom-up from the check templates the corpus forced into existence,
  **not** from the spec. Completeness is not claimed, and the Seeded-Recall
  misses are the measure of the gap. They grow by the same rule as templates —
  see `meta/conventions.md`.
- **Retry contract, two-tier** (the spec fixes the count — *ein Retry* — not
  its payload). Parse + Pydantic + semantic checks (mapping dry-run) share one
  code path; the *kind* of failure decides what the one extra call contains:
  - nothing parsed (bad JSON/shape) → **whole-call retry**, errors fed back;
  - schema-valid batch, some items fail semantically → **item-scoped repair**:
    only those items are resent with their errors, and accepted corrections
    are spliced back into their slots (`client.BatchRepair`).
  Measured on a real V1 answer, the old whole-batch retry re-emitted all 65
  hypotheses byte-identically and fixed neither broken item: the corrective
  signal drowns in the rewrite instruction, and a rewrite may perturb items
  that already validated. The repair call is cheap (2 items, not 65) and
  structurally cannot touch the good ones.
  GOTCHA: the splice is **positional**, so a repair that answers with a
  different number of items (a re-emitted full batch, a short list) is
  **discarded whole** — a mis-spliced item would silently replace one claim
  with another. Offline replays hit exactly this (the stub returns the same
  full fixture), which is why fixture-driven counts are unchanged by the
  two-tier switch.
  Whatever is still broken afterwards is "partial" — offending items are
  skipped, never the batch; a double failure is logged and reported, never
  raised. Outcomes: ok / retried_ok / repaired_ok / partial / failed.
  LESSON (first real runs): schemas stay purely structural — every item-level
  or cross-field rule lives in the semantic layer, or one bad item kills 60.
- **Model output is untrusted input**: planning-time checks cover param value
  shapes (lists, int-able accounts), bare identifiers vs `*_expr`/`*where`,
  no pre-aggregation in expressions (templates SUM for themselves), and
  referential integrity (`VIEW_PARAMS`/`COLUMN_PARAMS`: views exist, columns
  exist on the view they're used against). Unambiguous `view.column` values
  are normalized to bare columns, not rejected. What still slips through is
  contained by the engine (see run_ready) — visible, never fatal.
- **ULIDs never enter a prompt**: V2 references claims via deterministic labels
  (`claim_label_map`, identity-sorted c1..cN) — planning inputs are byte-stable
  across fresh projects, which is what makes fixture hashes meaningful.
- **Input builders** (`llm/inputs.py`): deterministic rendering (sorted
  profiles, fixed key order); NO token cap — optional `max_chars` escape hatch
  trims lowest-signal fields first and always records `trim_notices` into the
  call log; silent truncation structurally impossible (all rendering funnels
  through `BuiltInput`).
- **Stub mode**: fixtures keyed contract+scenario (never input hash — a builder
  change must not strand keyless devs); drift guard = offline test comparing
  fixture `input_sha256` **and `system_sha256`** against the inputs and
  prompts rebuilt today. Both halves matter and only one existed until
  2026-08-02: a recorded answer answers a prompt as much as an input, so a
  reworded prompt made every fixture stale while CI stayed green. A second
  guard asserts no fixture escapes either check; refresh procedure under
  "Operations" below. GOTCHA (found+fixed ): the recorder must
  take the last **non-repair** attempt — an item-scoped repair answer can
  never stand in for the full batch; and a live repair that *accepted*
  items is irreproducible offline (labels shift downstream) — the script
  warns, re-run the refresh in that case. GOTCHA: the corpus generator's
  `generator_spec/roles.yaml` names trap decoys — runtime domain guides must be
  clean (see `before_we_ai/domains/finance.yaml`).
- **A refusal is a result — and it is persisted**. Every claim V2
  leaves without a check (`unbindable` / `semantic_only` / `skipped`) gets a
  `DECLARATION` evidence record carrying the verbatim reason
  (`payload: {decision, reason}`). Before that the reason existed only in the
  disposable `cache/llm_log/`, so wiping the cache erased *why* a claim was never
  tested — the most common question a validator asks. The declaration is process
  metadata, the same class as a normalization declaration: authored by
  `Actor.SYSTEM` (the AI still authors **no** evidence — the model's words travel
  as payload data), and `resolve_status` ignores declarations, so it is
  structurally incapable of promoting anything. The guardrail test was tightened
  accordingly: `llm/` may build exactly one `EvidenceRecord`, of type
  `DECLARATION`, and may not even name a promoting evidence type
  (`tests/unit/test_llm_guardrail.py`).
- **Every entry declares its settlement path** (; the viewer's role
  elections made the gap visible). Each entry in the domain guide carries
  `decided_by:`. An **object**: the domain law that can elect it, or
  `clarification` (no arithmetic can decide what a column *means*: a journal
  balances per period AND per document AND per year, so a passing law never
  proves what its grouping column means). A **field**: `slot` — plus `fills:`,
  the slot param of its object's law it is elected into — or `clarification`.
  The guide lint (`DomainGuide` validator) rejects a silent entry, a generic
  template or a foreign domain's law as decider, an object declared a slot, a
  field declaring *any* law, a `fills:` naming a slot its object's law does
  not have, two fields in one slot, and a duplicate entry name. `decided_by`
  never enters a prompt — only the definitions render, objects and fields
  flattened into one list.
- **Role resolution — no silence**: `resolve_mappings` completes the rule
  *every business object and every clarification-decided field ends in a check
  verdict or a clarification question*: checked-and-lost → "which source is
  authoritative?"; law never bindable (every candidate carries V2's no-check
  declaration — the subledger_ar case: knowledge missing to apply the law) →
  "what domain knowledge is missing?"; clarification-decided → question listing
  the candidates, answerable in one pick; no candidate at all (once the search
  ran) → "does this role exist?". Candidates without a check result and without
  a declaration are in flight and draft nothing. The losing candidates keep
  their honest derived statuses. Still open: role claims binding to *generic*
  templates (M5, under "Onboarding workflow" below).
- **A slot field rides its object's law — and is answered by the run, not by a
  question** (`settled_slots`). `CheckDefinition.slots` names
  which params of a law are slots and which view param each sits on (balance:
  `{"amount": "journal"}`). When an object's law passed, the column that run
  consumed for a slot *is* that field's answer — the elected journal's balance
  check ran with `amount=amount_local_currency`, so nothing about the posting
  amount had to be asked. Deliberately narrow: `group_column` is not a slot,
  because a pass says nothing about what the grouping column means, so
  `doc_ref` stays a clarification. A slot whose object is unsettled rides the
  object's own question; a slot its object's passing law never consumed draws
  a question of its own — riding a law may not become vanishing into one. The
  settlement is **derived, never stored**: the field's own candidate claims
  keep their evidence-derived statuses (today `proposed`), which is why the
  report shows the consumed column instead of an election. **DECIDED
  (owner): the ReadinessMap reads the derivation.** The claims keep
  their status; no new promotion path, so the machinery that keeps
  False-Promotion at 0 is untouched. The rejected alternative — letting the
  passing run's evidence attach to the field claim and promote it — would have
  meant evidence from a run bound to *one* claim changing *another* claim's
  status. Consequence, designed for: *satisfied* and *promoted* are now
  deliberately different things, so every ReadinessMap item states **which one
  it is and why** ("satisfied because its own claim is test-supported" vs
  "satisfied because the balance law of 'journal' passed while reading
  `<column>`; its own candidate claims are still proposed").
- **Elections run per scope.** The election unit is **role × scope**
  (`domain_guide.scopes_of`, `_candidates(store, role, scope)`), and
  `settled_slots` is scoped with it. A landscape is typically multi-entity:
  DE and US each legitimately own a journal, an account column, a period
  column. One winner across the whole project would force a human to discard
  correct mappings, and would report a working ledger as `contradicted`
  because another entity's balances better. Status alone can never separate
  "wrong table" from "right table, broken data" — only the evidence can (the
  decoy fails 24/24 periods by millions; the US ledger fails 1 period by
  exactly 50,000) — so the fix is the right unit, not a better verdict.

  **Where a candidate's scope comes from** matters more than the grouping.
  **Not** the model: it has not been told scopes exist and must not be, since
  which entity a table serves is a human's statement. **Not** the source's
  name: that is exactly the wording-dependent magic this product avoids. A
  **source declares whose books it is** (`sources[].scope` in
  `before-ai.yaml` → `Source.scope`), and a binding inherits the scope its
  sources agree on (`ProfileIndex.scope_of`). A binding reaching across
  differently-owned sources has no scope and belongs to no entity's election.
  A project that declares nothing gets one landscape-wide election per role.

  `Scope` is frozen, and therefore hashable: elections group by it, and a
  value editable underneath a grouping could move a claim into another
  entity's election.

  Riding along: clarification questions carry a `scope` and dedup on
  `(question, scope)` — see "Clarification questions dedup on wording *and*
  scope". The report renders one block per role × scope, naming the books in
  the heading, and counts "elections settled" rather than "roles elected",
  because a slot answered by its object's passing run counts and nobody
  elected it.
- Seeded-Recall lives in `tests/eval/seeded_recall.py` — it **reports, never
  gates**. Current standing: **False-Promotion 0** (non-negotiable),
  Seeded-Recall **14–15/25** in-scope traps, prompt-leakage scan clean. Misses
  cluster in the definition-style traps that need the document pipeline. Full
  report and method: `docs/seeded-recall.md`. **Open: the numeric bar** — run-
  to-run noise is ±2–3 traps, so a bar must sit outside it, and one over
  relationship-style traps only is worth considering.

### Standing constraints on the LLM layer

- Prompts stay domain-agnostic — no corpus-trap hints ever
  (`meta/conventions.md`).
- The `proposed`-only guardrail must hold **structurally** (actor restrictions
  in the model layer), never by prompt discipline alone.
- Stub fixtures are refreshed from logged real runs (`cache/llm_log/`) so CI
  can't drift green while real output rots; Seeded-Recall is a separate online
  eval, never a CI gate.
- Input builders assemble profiles **deterministically**; if anything must be
  trimmed, trim visibly (logged), never silently.
- No hard token limit — the goal is complete, well-structured context
  (~25k tokens is an orientation, not a cap).

## Documents & V3 (`documents/`, M5)

Design settled 2026-08-02, before code — same discipline as the answer-type
decisions. The module is `before_we_ai/documents/` (the spec's `docs` module;
renamed because `docs/` is this repo's documentation directory). The contract
is **documents** (spec alias V3), frontier tier.

### Pipeline shape

- **Extraction:** PyMuPDF, pinned **exactly** (`pymupdf==1.28.0`) — text
  extraction is deterministic only for a fixed version, and chunk bytes feed
  fixture hashes. A bump is therefore the same class of event as a prompt
  change: deliberate, with a fixture re-record.
- **Chunking is deterministic by construction:** chunks follow PyMuPDF text
  blocks in reading order (`sort=True`), greedily packed to a fixed target
  size, never split inside a block **and never mixing kinds** — a chart
  label and the paragraph beneath it are different chunks, because the
  chunk is what carries the anchor's kind. Chunk id = `{source}:p{page}:{seq}`
  — stable for identical PDF bytes. Position anchor data: page number plus
  the char span within the page text, where page text is defined as the
  chunk texts joined in reading order, so spans are exact by construction
  rather than by trusting a second extraction call to agree.
- **Index:** DuckDB FTS over the chunk table, in `cache/` (disposable, like
  the catalog: delete + re-scan ⇒ identical output). Extraction and indexing
  create ZERO claims — a scanned PDF yields a document profile, nothing else
  (same law as `scan`).
- **FTS is required, never silently substituted.** Verified 2026-08-02: the
  extension is not compiled into the duckdb wheel — it lives in
  `~/.duckdb/extensions/` (this dev image bakes it; loads and queries fully
  offline, duckdb 1.5.4). `LOAD fts` failure is a **hard error** naming the
  one-time fix (`INSTALL fts` with network — the same class of setup step as
  `pip install`). Rationale: a LIKE/trigram fallback would select different
  chunks per environment, and retrieval selection feeds V3 input bytes — a
  silent fallback would break offline replay invisibly.
- **Retrieval is deterministic:** query strings derive from rule items and
  open questions (fixed rendering), top-k per query with tie-break (score
  DESC, chunk id ASC), union capped, then ordered by document position — so
  a marginal score change reorders nothing downstream.

### V3 call shape — one call per document

The spec's "chunkweise" governs the granularity of **evidence** (every quote
is validated by string match against its chunk), not the granularity of
calls. V3 runs **once per document**, with the retrieval-selected chunks in
the input (bounded count, document order) — the same shape as `plans`' one
call per batch, and the shape the fixture machinery (`contract__scenario`
filename, one `input_sha256` pin each) replays without inventing per-chunk
scenario names. Input: document profile + selected chunks (id, page, text) +
the rule items and open questions being sought. Output items: anchors,
concept-claim candidates, links to rule items (`readiness.link_claim` is the
output seam), clarification questions. **Quote validation:** every quoted
string must appear verbatim in the chunk it cites, or the item fails semantic
validation — item-scoped repair applies, same two-tier retry as every
contract.

### The multi-anchor rule (Mehrfach-Anker-Regel)

The spec asserts the rule's name (T8's "Prüft" column) and the behaviours it
must produce; this is its definition. Anchors never promote —
`DOCUMENT_ANCHOR` is weak evidence and `resolve_status` never reads it — so
the rule governs what **reconciliation may propose** and how V3 must label
anchors, never status transitions.

Every anchor carries two labels. **Neither is supplied by the model** —
both are derived, which is what makes the rule structural rather than
prompt-dependent (revised 2026-08-02, after reading the corpus PDFs: the
chart figure F23 hides behind extracts as ordinary text, so a model asked
to classify it would have to be *trusted* to say "chart", and the whole
point of this layer is that nothing epistemic rests on trust):

- `kind`: `text` | `table` | `chart` — **derived from page geometry** at
  extraction time and carried by the chunk; an anchor inherits the kind of
  the chunk its quote lives in, and V3 cannot override it. PyMuPDF's
  `find_tables()` gives table regions; vector-drawing clusters outside
  them are graphic regions; text blocks are classified by which region
  contains them, everything else is `text`. Verified against the corpus:
  the management report's quarterly table is detected exactly (9×2) and
  the leftover drawing cluster is precisely the chart frame that boxes
  F23's `EUR 2,847,000`.
- `match`: `exact` | `rounded` | `coincidental_candidate` — **computed by
  reconciliation** by parsing numbers out of the quote and comparing them
  to the claim's value. `rounded` means agreement within presentation
  rounding; anything looser is `coincidental_candidate`.

What V3 supplies is the quote, what it takes the quote to assert, and —
for a figure — **which number in the quote it is about** (`value`, the
literal as the document writes it). That last field looks like a
concession and is the opposite of one. The dividing line is not "does the
model touch it" but **"can we check it"**: `kind` is unknowable from the
text, so the model must never assert it; which number a sentence is about
*is* a reading, and a reading can be verified — the named literal has to
appear in the quote and parse as a number, or the finding is refused.

The engine used to compute it instead, by taking the largest number in
the quote, and before that the first. Both are guesses. "Earnings per
share of 4.12 on 8,312,504 shares" defeats one; "Prior year Q1 2023
revenue: EUR 3,200,000" defeats the other, and did — it hid a restatement
behind a weaker refusal until a corpus run showed it. A checked answer
from the model beats an unchecked guess from us.

**What the rule is about, and what it is not** (settled 2026-08-02, while
implementing it — the first draft would have broken K3). Documents are read
for two quite different purposes, and only one of them is corroboration:

- **Value corroboration** — a figure in a document offered as agreeing with
  a number the data produces. This is where the multi-anchor rule lives and
  where T8's negatives (F23, F24, F26) are caught.
- **Definitional grounding** — a policy sentence that *states a rule* the
  data cannot show (a sign convention, a revenue definition, which FX rate
  type applies). One authoritative policy saying it once is what a policy
  *is*; demanding a second document would make policy documents useless and
  would make K3 — the accounting policy resolving F14/F15/F19 — impossible
  to satisfy.

Nothing is lost by letting definitional anchors through, because a link is
not evidence: `link_claim` only says *which dependency this claim answers*,
and the item counts as satisfied solely through the claim's own status.
A policy-grounded concept claim therefore sits at `proposed` until a check
tests it or a human confirms it — visible, named, and promoting nothing.

For **value corroboration**, reconciliation may propose a link only when:

1. **≥ 2 independent anchors** — different (document, page) pairs — of kind
   `text` or `table` with match `exact` or `rounded` agree, **or**
2. **1 such anchor + a matching DB aggregate** (an existing CHECK_RESULT on
   the same claim) agrees.

Everything else surfaces, never links:

- a **single** anchor stays weak evidence, visible in the report trail;
- `chart`-kind anchors never count toward the threshold — a chart-only
  figure is flagged low-confidence (F23);
- `coincidental_candidate` never counts, whatever the quantity — noise
  documents must be present and refused (F26);
- **disagreeing values** for the same figure are a restatement: marked as a
  documented finding **and** a clarification question, never silently
  reconciled to either value (K7/F24). Two anchors can disagree, but so can
  one quote with itself — F24's poisoned line carries both the restated and
  the original figure in a single sentence, which is precisely how a
  restatement announces itself in prose.
- **ambiguous figures never count.** `500.000` is half a million under one
  grouping convention and five hundred under the other. Where a literal has
  two readings and only one of them matches, agreement would be an artefact
  of the locale we assumed, so the anchor is a `coincidental_candidate` —
  the reading is recorded, the agreement is not claimed.

### Statements & the mirror loop (`tell`, `answer_question`)

Library operations in M5; the Typer CLI verbs wait for M8 with the rest of
packaging (the walkthrough scripts are the M5 surface).

Built 2026-08-02 in `before_we_ai/statements.py` — "the human's voice",
the third of the three voices and the only one that can settle anything.

- `tell(root, statement, guide=…, by, scope=None)` records the words
  **first**, verbatim and searchable, before anything is made of them, so
  a statement nothing can be structured from is parked rather than lost.
  Then V3 reads it: a statement is one passage under the same
  `read_passages` path a PDF gets, which buys it the same quote
  validation, the same anchoring and the same inability to promote. Each
  resulting claim carries the TESTIMONIAL, which records *that somebody
  said this* — a different fact from its being true, and the store keeps
  them different. What comes back is the `Mirror`: what was understood,
  and the scope question.
- `confirm_claim` / `answer_question(store, card, by, scope=None)` produce
  the scoped CONFIRMATION via `admit_evidence`. A confirmation on a
  testimonial claim without an explicit scope raises `PromotionError`
  (F29). Answering a card confirms every claim it rests on **or none** —
  half an answer would leave a reader believing they had settled
  something they had not.
- **`_status_rationale` now reads the law instead of restating it.** It
  counted every confirmation while `resolve_status` counted only
  admissible ones, so it could print "1 confirmation" beneath "nothing
  stronger than proposed evidence is live yet". `confirmation_admissible`
  became public for exactly this: the one way to be sure the explanation
  matches the law is to ask the law. The unscoped case now says what it
  is — a confirmation that "names no scope, and therefore counts for
  nothing". Reachable only for a store written before the rule existed
  (`attach_evidence` refuses to create one), which is why it is defensive
  and still worth being right about.
- `ProposalStore` gains `anchor()` — the weak-evidence method the facade was
  shaped to accept via its private `__attach` seam. The guardrail's
  `PROMOTING` tuple is untouched; only the allow-list widens.

### Where things land

- Anchors persist in `evidence/` (append-only store); the chunk index in
  `cache/`; document profiles in `profiles/`. No new `PROJECT_DIRS` entry.
- Stage spine: extraction + indexing is **2c-measure-documents** (measured,
  zero claims); V3 proposals are **3d-propose-documents**; tell/answer beats
  join stage **5** — letters, never new numbers.
- Report: a documents `*View` in `projection.py` next to `MeasurementView`,
  anchor-aware `EvidenceView`, and the "M5 · documents" ghost node in the
  process diagram becomes real.

## Readiness report (`readiness_report/`)

```bash
python -m readiness_report <project_root> -o <out.html>
```

The rendered state of knowledge: what is known, what is assumed, what is
unknown — derived live from the store, never stored. Read-only and
click-through: start at the process diagram, walk down the pipeline, pick a
claim and follow it outward to evidence, sources, lineage, and the questions
that depend on it, without hand-reading YAML. One self-contained HTML file;
works for an empty project. It is the owner's primary validation **and**
understanding surface.

**Binding constraints (in force):**

- Strictly read-only: `ProjectStore(root)` load/convenience methods only;
  never `save_*` / `add_*` / `mark_*_stale`; modifies nothing in the project.
- The core must not know the report exists: no dependency from
  `before_we_ai/*` on `readiness_report/`. (The report imports
  `admissible_templates`, `REGISTRY`, `load_domain_guide` and `settled_slots`
  read-only — still one-directional.)
- Static HTML, no runtime dependency beyond a browser. No graph libraries,
  no chart libraries, no multi-file output.

**What it renders** — the page *is* the pipeline, section for stage, each
headed by the stage that produced it. The **script number is the section
number**, so a validator who ran `3b` knows to read section 3
(`validation/README.md`). Master–detail with search + status/predicate/role
filters; deep links reveal their claim:

- **The process diagram** (top) — the whole machine on one line, carrying this
  project's live counts, every count a link into the section that produced it:
  inputs → measured → the AI proposes → the checks decide → humans decide the
  rest. Two things are drawn, not written: the **actor boundary** between
  "proposed" and "decided" (nothing the AI authors can promote a claim — the
  structural False-Promotion invariant, made visible), and a **ghost node**
  for M5 (documents), dashed and labelled "not built", so what is missing is
  stated rather than omitted.
- **0 · Request** — the frame opening: the business question verbatim, the
  requested output attributed to the model, the scope, and the
  required-knowledge list with each item's `why`. What the answer depends on,
  before anything has been measured.
- **1 · Inputs** — the three declared domain inputs, live from the project:
  sources, the domain guide (domain, count, names, definitions, settlement
  paths), and the domain-law check definitions (naming the generic remainder
  as such).
- **2 · Measured** — sources, column profiles, candidate-overlap summary:
  counted facts, no model involved yet.
- **3 · Proposed** — the funnel: proposed → planned / unbindable /
  semantic-only / skipped → judged → derived status; each number a clickable
  filter. The buckets are read from the `DECLARATION` records V2 writes ("A
  refusal is a result"), so they match the step-5 report exactly, and each
  claim shows the model's verbatim reason where its check would have been.
- **4 · Tested** — the elections, one per **role × scope** (the entity named
  in the heading): the candidates, the elected winner, each loser with the
  domain law that felled it; a role whose candidates were never bound to an
  invariant says so; a slot field shows the column its object's passing law
  consumed; a role that lost every candidate ends in its clarification
  question.
- **5 · Clarification** — the clarification-questions inbox with the claims each
  question rests on: the human's to-do list. A card leaves it the moment a
  claim it rests on settles (`semantics.is_answered`, derived from the same
  evidence the readiness map reads, so the two cannot disagree). Answered
  cards are kept, shown with what settled them.
- **6 · Readiness** — the frame closing: the derived verdict with the
  dependencies it names, and every required item with the sentence saying
  where it stands, grouped into "what the figures are computed from" and "what
  the figures mean". See "Question flow & readiness".
- **7 · Claim detail as a story**: statement, one derived-status badge (a loud
  banner only when the stored status diverges), then collapsible
  *1 proposed → 2 planned → 3 judged → 4 context*; ids and timestamps in
  collapsed fine print. Check-plan cards show template, params, roles,
  domain-law badge, default tolerances, and — from the check_result payload
  (`payload["sql"]`), where the runner writes it — the **rendered SQL as the
  question that was asked of the data**. A check that never ran says so.
  Invariant check plans carry no `claim_id`; they are reached through the
  `check_plan_id` on the mapping claim's evidence.
- **Core terms** (bottom) — rendered from `before_we_ai/glossary.py` (one
  home, no drift).

**The three-voices rule.** The report is read by
people who will act on it, so it must be business-legible — and being
legible is exactly how a page starts laundering a guess into a finding.
Three voices, never mixed:

1. **Derived narration** — deterministic sentences composed from evidence,
   verdicts and the guide's definitions. This is the headline voice, and the
   only one allowed to state a status. Never an LLM at render time (the door
   stays open; the guide's definitions already carry the business words).
2. **The AI's words** — claim statements, refusal reasons, proposal
   rationale. Shown, because they are legible and often the most useful
   sentence on the page; always attributed, always subordinate to the derived
   line above them. **The model's prose may headline a proposal, never a
   status.**
3. **The human's words** — testimonials and answers, verbatim. They are
   evidence; they are not paraphrased.

Two consequences worth stating. A mapping claim's own statement spells out
its whole binding, so it is quoted under "1 · Proposed" and never used as a
heading — headings use the derived title (`'journal' is played by
de_erp__gl_postings`). And the **proposal rationale is read best-effort from
`cache/llm_log/`**, matched by statement (hypotheses) or role+table (mapping
claims, a field inheriting its object's proposal). It is deliberately not
stored on the claim: trust maps to persistence, so derived sentences are
permanent and a rationale is allowed to fade. When it is gone the page says
so, without guessing why.

**Questions are written ask-first** (`QUESTION_*` in `llm/domain_guide.py`):
the ask, then the guide's definition of the thing, then what the machine
already tried. Candidates are *not* formatted into the text — they are the
`claim_ids` the card already carries, rendered as a list. Whether that list
is a *choice* is read off the guide (`decided_by: clarification`), not off
the question's wording.

Because the candidates are not in the string, a changed candidate set does
not draft a second card: it dedups to the same open question and keeps the
first card's `claim_ids`. That is the correct reading — "which column is the
document reference?" is one question, not a new one per candidate shuffle —
and it is why the dedup key had to gain a scope (below): two *entities* are
two questions; a reshuffled candidate list is not.

`tests/unit/test_readiness_report.py` locks the funnel stage counts, the
winner / loser-with-its-law / clarification-question of the role elections,
the process diagram (live counts, actor boundary, ghost nodes), the question
pick-list and folded ids, and the three voices.

## Onboarding workflow (specified, not built)

The spec's Zielbild ("Datenbank verbinden, Dateien ablegen, Scan drücken") as
a first-run flow: **init project → pick a bundled domain guide or draft one
(LLM-assisted, human-curated) → drop files into `sources/` → scan.** Pieces
1+2 land at **M5 kickoff** (both change prompt bytes → ride one fixture
re-record); piece 3 post-M5; the assembled workflow + quickstart is M8.

1. **Sources discovery — `discover(root)`.** Today `init_project()` writes
   `sources: []` and a human hand-authors every entry; nothing reads the
   `sources/` drop dir. `discover(root)` walks it, infers `kind` from the
   suffix (`.duckdb`/`.csv`/`.xlsx`/`.pdf`), and **merges** new entries into
   `before-ai.yaml`: merge never overwrite (a hand-tuned entry wins;
   re-running adds only what's new — same idempotence contract as `scan`);
   report what was skipped, never silent; never touch entries pointing
   outside `sources/` (connected databases). `scan(root)` calls it first —
   "drop files, press scan" becomes literally true. A dropped PDF still
   yields only a fingerprint until M5, but becomes *visible* in the list.
2. **Bundled domain guides.** Ship curated per-domain guides as package data:
   `before_we_ai/domain_guides/finance.yaml` (content = today's test fixture
   `before_we_ai/domains/finance.yaml`). Config `domain_guide_file:
   finance` resolves to the bundled guide; an explicit path overrides. Flat
   YAML, no plugin framework (rule of three). Shipped guides must pass the
   same leakage tripwire as prompts.
   **Logical pack validation:** the entry half shipped 
   (`decided_by:` + lint); the **slot side** shipped with the
   objects-and-fields restructure — `CheckDefinition.slots` names each law's
   slot params, and the lint rejects a field whose `fills:` is no slot of its
   object's law. (Note the direction: the guide's fields must fill real slots,
   but a law may still have slots no field names — V2 binds those from the
   profiles directly, so requiring guide coverage would force guides to grow
   for no epistemic gain.) Still M5 (prompt
   bytes → same re-record): mapping claims binding to *generic* templates
   where a real data property exists (`account` via anti_join against the
   chart of accounts — catches garbage, though it still cannot prove
   meaning).
3. **Domain-guide drafting (LLM contract, post-M5).** "Draft a domain guide
   for domain X" — a small V-contract of the standard shape. The system
   prompt is the authoring questionnaire: laws first (what must hold in ANY
   correctly-run system of this domain — one law = one invariant check
   definition, code not YAML); extract the nouns each law quantifies over
   (those are the roles, nothing else is); new-hire test per definition
   (structural marks, never vendor names); leakage test (nothing that exists
   only in one landscape); falsifiability per role (no answer → not a role).
   **GUARDRAIL**: a generated guide is a *draft a human curates*, never
   silently consumed. A too-strict law is self-policing (everything fails →
   clarification questions); a too-**loose** law is the one path to false
   confidence — an invariant that trivially passes promotes mappings on
   evidence that tests nothing. Authorship ends with a person signing off.
   **Refined :** the sign-off is per entry, not per file — generic
   laws/concepts may stay AI-drafted; organisational bindings must be
   human-answered (see "Guide by construction" under Domain inputs).

## Question flow & readiness

The layer that makes the product an answer-readiness control layer rather
than a landscape scanner (see **Principles**). The middle of the machine runs
bottom-up — scan everything, propose claims about the whole landscape — and
the question flow wraps it:

```
business question → AnswerRequest → RequiredKnowledge (scoped)
  → domain guide → data profiles + link candidates → mapping claims
  → check definitions → check plans → check runs → evidence
  → claim status → clarification questions where needed
  → ReadinessMap → ready / ready_with_limitations / blocked → permitted answer
```

The question bounds discovery: it defines what must be known, and nothing
else *has* to be. That is the correction to the too-wide domain — domain
knowledge is bounded by the requested use case, never by an enterprise
ontology. Visible in the walkthrough: the P&L question does not require
`subledger_ar`, because open receivables do not enter a profit and loss.

**Objects** (`model/objects.py`, all live in `glossary.py`):

- **`AnswerRequest`** — the structured form of one business question:
  `requested_output` + `Scope`, stored in `answers/`. The human question is
  kept verbatim; this is its software representation, and it carries no
  answer half.

  **No `created_by`, here or on `RequiredKnowledge`.** Authorship is fixed by
  the shape — `question` is the human's, `requested_output` and `scope` are
  V4's — so such a field would read `human` on every record while being wrong
  about two of the three. **A field whose value never varies carries no
  information**, and one that is also *wrong* is worse than absent.
  `Claim.created_by` and `KnowledgeLink.linked_by` are the contrast: they
  vary, and code branches on them. The report attributes accordingly: the
  question as a human quote, the requested output as the AI's.
- **`RequiredKnowledge`** — `KnowledgeItem`s (`object` / `field` / `rule`),
  each with a `why` a human can prune on. Drafted by V4 and persisted,
  because the pruning is a human decision rather than something re-derivable.
  (Decided 2026-08-01, not built: it becomes a *derived* structure once
  answer types land — see **Answer types** below.)

  **Only objects and fields carry a scope.** For them it is a *selector*:
  which table, which column — DE's ledger versus US's. A rule has nothing to
  select among; where a rule is valid lives on the **claim** that states it
  (`Claim.scope`, `Claim.validity`, which can also say *from when* — richer
  than the item could express), and the evaluator asks whether that claim
  reaches the scope the question was asked in. A rule item with an explicit
  scope is rejected at construction.

  **Pruning is `readiness.waive_item(ref, because=…)` — waived, not
  deleted** (owner decision). The item stays in the map, struck through,
  carrying the reason: a deleted dependency is invisible, and "we decided
  this does not matter, here is why" is what this product refuses to lose. A
  reason is mandatory; `require_again` undoes it. Waiving is allowed on any
  kind, unlike linking — linking a non-rule would bypass an election,
  waiving bypasses nothing.
- **`ReadinessMap`** (`readiness/`, a *derived structure*, never a record) —
  per item: claim, evidence, ground, remaining gap; overall verdict
  `ready` / `ready_with_limitations` / `blocked`. Recomputed on every read,
  the same discipline as `resolve_status`: a stored verdict could drift away
  from the evidence beneath it, and a drifted verdict is worse than none.

`readiness/` is deliberately its own package, not part of `core/`. The
epistemic core decides what may be **believed** from evidence; readiness
decides what may be **claimed** from those beliefs. Keeping the two
vocabularies apart is the handover principle spelled as a module boundary,
which is why `Readiness` does not live in `model/enums.py`.

### The request contract (`llm/request.py`)

`ask(root, question, guide=…)`, the standard contract shape (typed schema,
`call_with_retry` with the two-tier repair, `CallLogger`, offline stub, drift
guard). Its input (`inputs.build_question_context`) is the question, the
domain vocabulary and the answer types — **no profiles**: whether the data can
serve the request is the rest of the pipeline's job, and answering it here
would be the model deciding. Fields render nested under their objects, unlike
the flattened role-binding input, because here the hierarchy is the point.

**Not numbered.** The spec's four are V1 hypotheses, V2 check binding, V3
document interpretation and V4 SQL generation; this is none of them, and the
built-but-unnumbered `role_binding` already showed that five contracts do not
fit four slots.

The semantic check (`mapping.check_knowledge_item`) is asymmetric on purpose.
Objects and fields must exist in the vocabulary and sit where the item says
they sit, because a dependency the readiness evaluator could never resolve is
a gap that would go quiet. Rules are the mirror image: they exist *because*
the vocabulary has no entry for them, so a rule is rejected only when it names
one — which makes it a mis-kinded object or field, and the error says so.

The corpus fixture (`request__corpus.json`) is **hand-authored** and marked as
such, per the rule in `llm/stub.py`; `refresh_fixtures.py` records this
contract first, so the next online run replaces it.

### Answer types — deriving the dependency list

The verdict is only as good as the dependency list. When the model drafted
that list freely, over-listing was visible and fixable (`waive_item`) but
**under-listing was silent**: a dependency the model never listed appeared
nowhere, so nobody could test, waive or clarify it, and the verdict came out
too generous with nothing anywhere to show why. The fix reduces the model's
claim from *inventing the list* to *classifying the question* (option
analysis: `docs/draft-thoughts/dependency-contract-proposal-for-review.md`).

1. **The guide declares `answer_types:`** — per family of question, the
   objects, fields and rules an answer to it depends on, reviewed once and
   reused. It lives *inside* the guide, not beside it, so a rename cannot
   leave a dependency list pointing at a vocabulary entry that no longer
   exists: one lint checks both halves of one document. A dead reference is a
   **hard load error**, never a skipped item — it would expand to a silently
   shorter list. Rules are the mirror image, as in the contract's own
   semantic check: rejected only when they shadow an entry, because a rule
   exists precisely where the vocabulary is silent.
2. **The list is derived, never stored** (`readiness.assemble`). It is put
   together on every read from the expanded answer type, whatever the
   contract drafted freely for this question, and the acts replayed over
   both. Only the **acts** persist (`KnowledgeAct`, append-only in
   `answers/`), each recording the guide fingerprint it was taken against. A
   stored list would go on describing a guide that has since changed, and a
   list quietly out of date is the same failure as one that was short to
   begin with.
3. **No `criticality` field.** Severity follows from *kind* (the verdict
   rule); an authored weight would be a second home for the same decision,
   and a typo in it would turn a missing field into a friendly verdict.
   Per-question exceptions are what `waive_item` is for.
4. **No `condition:` field.** Variants are separate answer types, so the
   condition decision ("consolidated or not?") lives inside the one decision
   that is already visible and confirmed — the classification. (`extends:`
   between types is the reserved answer if the type list ever sprawls.)
5. **An unmatched question falls back to free drafting**, labelled as such
   and capped; only a broken contract blocks (see the verdict rule below).
6. **One new canonical word: `answer type`.** "Dependency contract" is the
   proposal paper's name for the seam, not a code object. The seam itself is
   the function `expand(answer_type, guide, scope)`, and the engine never
   asks where an answer type came from — a hand-written guide, a starter
   pack, or one day a guide builder that proposes one from documents.

**Only a confirmation lapses.** A `confirm` says *"this list is complete"*,
which stops being true the moment the list changes, so it is ignored once the
guide fingerprint no longer matches. Every other act is about one item —
"this does not matter here", "this claim speaks to it" — and a change
elsewhere in the guide leaves it exactly as true as it was; lapsing those too
would destroy a human's work to no one's benefit, and the lapsed confirmation
already puts them back in front of a reader.

**The contract** (`llm/request.py`) has two tiers of failure. A delta item
that fails its semantic check is skipped and reported, as everywhere. A
classification naming an answer type the guide does not declare fails the
whole call, retry included: it is the one claim the call exists to make, and
a request classified to a family that cannot be expanded is worse than no
request at all. The answer types reach the model *with what each one
requires*, because classification is a judgement about coverage and a
definition alone does not support one.

**On the page**, the classification headlines the request card in the derived
voice — *"Treated as: profit_and_loss_by_dimension (guide a1b2c3d4e5f6) — not
confirmed by anyone yet"* — above everything it governs, because naming the
wrong family makes the whole list below it wrong quietly. Each item shows its
provenance, and the `why` is attributed to whoever wrote it: a `why` expanded
from the guide is the reviewer's sentence, and citing it as the AI's would
put a human's words in the model's mouth.

**Not built, deliberately:** `extends` between types, and the guide-bootstrap
layer (documents + profiles → proposed answer types), which stays in the
proposal paper as the later Guide Builder.

### The verdict rule

It follows from **what kind** of dependency is missing, never from anyone's
opinion of how important it is:

- an **object or field** is what the figures are computed *from* — without it
  there is no number, so the answer is **blocked**;
- a **rule** is what the figures *mean* — the number exists but is qualified,
  so the answer is **ready_with_limitations** and the map names every
  qualification;
- nothing missing: **ready**.

That is "permit, narrow, or block", derived rather than judged.

Two things are non-negotiable in the output and are tested as such:

1. **`blocked` and `ready_with_limitations` name the dependency.** A verdict
   without its reason is the one thing this product may not ship.
2. **Every satisfied item says how it is satisfied** — by its own claim's
   status, or by the derivation `settled_slots` supplies for a slot field
   whose claims are still `proposed`. Since the owner decision,
   *satisfied* and *promoted* are deliberately different things (see "Guide by
   construction" above), and an item reading only "satisfied" would hide it.

"Unsupported" is likewise never bare: *nothing proposed*, *all contradicted*,
and *proposed but undecided* are three different jobs for the reader — declare
a source, fix the data, answer a question — so `Ground` tells them apart in
words.

**How each kind of item resolves.** An **object** or **field** resolves through
the domain guide and its scoped election — that is what the guide is for. A
**rule** has no guide entry by definition, so it resolves only through an
**explicit claim link** (`KnowledgeItem.satisfied_by`, a `KnowledgeLink`
carrying `linked_by`; created via `readiness.link_claim`).

*Owner decision .* The first implementation matched a rule's name
against a concept claim's `term` or a predicate name, slug-normalised. That was
rejected before M5 could build on it: V4 names a rule in the human's words
("sign convention for income and expense") while V3, reading a policy PDF,
coins its own term — so the match would miss exactly where it matters, and
could just as easily hit something unrelated that happens to slug the same. A
verdict resting on a coincidence of wording is not a verdict.

The link **routes, it does not vouch**: the linked claim's own status still
decides, so a link can never promote anything and an **AI may create one** —
structurally as harmless as an AI-authored claim. That is what makes it usable
as V3's output seam in M5. Two guards: a link on a non-rule item is refused
(model validator + `UnlinkableItem`), because it would be a way around the
scoped election; and a link to a vanished claim is both an integrity finding
and a distinct readiness sentence ("the link is broken, not the knowledge") —
a broken pointer and missing knowledge need different repairs. The report
prints who linked it and why, since a wrong link points a verdict at an
unrelated claim.

**What propagates, and what has to be re-run** (owner question).
The verdict needs no re-run at all: the map is derived on every read, so a
claim linked today changes the verdict on the next render. What *does* need a
re-run is new **testable** knowledge — a policy claim like "revenue = 4000–4999
minus contra" is a rule a check can falsify, so it must re-enter at V2 and the
engine. `v2_bind._untested_claims` therefore selects **every parameterised
claim without a plan**, filtering neither on `Actor.AI` nor on `proposed`:
*who said it, and whether anyone believes it, are both irrelevant to whether
it can be tested*, and the spec is explicit that a contradicting check is a
testimonial claim's only expiry date — it carries no data fingerprint, so
nothing else can ever expire it. Dormant until the document pipeline produces
such claims.

The third category is what is **written** to the store, which needs someone
to retract it. Answered clarification questions are handled by deriving the
answer rather than flagging it: `semantics.is_answered` reads the same
evidence the ReadinessMap reads, so the open-questions list and the map
cannot disagree about one store. Answered cards are kept, shown with what
settled them.

The rule to apply whenever something new writes to the store: **derived
surfaces propagate for free; written surfaces owe a retraction story.**
Source-fingerprint staleness — the remaining written case — is M7.

**A conflict is never silent.** A rule may carry several links. If a settled
claim satisfies it while a *contradicted* claim is linked to the same rule,
the verdict stands — the contradicted one may simply be the loser — but the
sentence names it ("A contradicted claim is also linked to this rule …").
Owner decision: name it, keep the logic. Silence here would be the
one failure the product exists to prevent, in the place that emits its
loudest statement.

One deliberate leniency, stated rather than hidden: a **landscape-wide claim
covers a scoped item**, because a shared account master genuinely serves every
entity and "no declared owner" is its normal state. The sentence then says so
("no source declares it as entity DE's, so this rests on a landscape-wide
mapping"). The reverse does not hold — DE's ledger says nothing about the
landscape.

### Clarification questions dedup on wording *and* scope

Cards carry a `scope`, and deduplication keys on
`ClarificationQuestion.dedup_key()` = `(question, scope)` — in both drafting
sites (`llm/domain_guide.py::_save`, `engine/runner.py::_draft_question`).
The scope also leads the rendered question ("For entity DE: …") where a
reader cannot miss it.

Text alone is not enough, and the reason is worth keeping: the candidate list
is deliberately *not* in the question string, so *"Which of the proposed
candidates is the 'doc_ref'?"* is byte-identical for DE and US. Keying on text
would collapse the second scope's card into the first and take its candidates
with it — silence, produced by a change made for readability. A regression
test asks one role in two scopes and demands two cards.

### The surface

The readiness report's process diagram carries readiness as its sixth
stage, with live counts ("2/9 dependencies
supported · blocked") and linking into **section 6 · Readiness**; the question
and its dependencies open the page as **section 0 · Request**. Two rules bind
both panels:

- **The three voices** (see "Readiness report"). The business question
  appears verbatim — it is the human's. The verdict and every item's status
  sentence are derived and are the headline. The `why` the model wrote when it
  listed a dependency is legible, attributed and subordinate: it says why the
  item is on the list, never what became of it.
- **Domain neutrality** — the panel's wording carries no domain nouns; the
  concrete ones come from the guide, as everywhere else.

Items are grouped as "what the figures are computed from" and "what the
figures mean", which *is* the verdict rule, so the page explains itself.

### Acceptance — the six demo behaviours

The narrow demo the product must satisfy: (1) identify both candidates,
(2) contradict or qualify the wrong one, (3) surface the missing business
rule, (4) ask one focused clarification, (5) build the ReadinessMap,
(6) permit, narrow, or block.

All six are asserted end to end in
`tests/corpus_driven/test_llm_offline_corpus.py`, against the frozen corpus
and its **recorded real** answers. The verdict that landscape earns is
`blocked`, naming `journal.entity`, `journal.period`, `journal.account` and
`intercompany`: the ledger of record is identified and its amount column is
settled by the run that consumed it, but nothing yet says which column carries
the entity or the period, and a P&L *by entity and month* is computed from
exactly those. A companion test answers each open card and shows the verdict
**narrow** to `ready_with_limitations` with the three conventions named — the
third outcome.

**Not built: the small standalone demo dataset** (one correct
journal, one attractive wrong export, an account master, a sign convention, a
non-inferable policy) intended to double as the first user experience. Running
it offline needs its own recorded V1/role/V2 answers; hand-authoring those
would mean writing the model's answers and then asserting the system found
what was written, so the acceptance test uses the frozen corpus instead. The
presentable dataset needs one live recording session. **Open** — see
`meta/memory.md`.

## Operations

- **Install & test**: from `/workspace/src`, `source
  /workspace/.venv/bin/activate && pip install -e '.[dev]'`; `python -m
  pytest -q` — fully offline, no API key. Never run pip against the system
  Python.
- **DuckDB catalog gotcha**: views over ATTACHed databases die on a fresh
  connection — always re-open via `sources.open_catalog(root)`; never hold a
  raw `duckdb.connect` on `cache/analysis.duckdb` across steps.
- **Cache disposability**: everything under `cache/` (catalog, normalized
  parquet, `check_runs/`, `llm_log/`) is reconstructible; delete + re-scan
  yields identical output with stable profile IDs. Truth lives only in the
  YAML dirs.
- **Fixture refresh** (only when prompts/input builders change and the drift
  guard goes red): from `src/`, with `ANTHROPIC_API_KEY` exported in the
  shell (never in a file), run `python tests/eval/refresh_fixtures.py` — it
  refuses to record from a `failed` call and warns on `partial`; then review
  the fixture diff, re-pin counts in
  `tests/corpus_driven/test_llm_offline_corpus.py`, and re-run
  `python tests/eval/seeded_recall.py` (report the delta vs the last
  published number honestly, including "unchanged").
- **Owner validation walkthrough**: `validation/README.md` +
  `validation/scripts/` (numbered stages, offline by default; `report.sh`
  renders the readiness report, `llm-log.sh` the verbatim call log).
