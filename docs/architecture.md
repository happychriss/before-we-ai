# Product architecture — confirmed design (M1–M4 + M6 built; M5 specified where marked)

Per-package confirmed decisions and gotchas for `src/before_we_ai/`. Feature
status: `README.md` (roadmap table). Plain-language walkthrough:
`docs/before-ai-concept.md`. Working rules: `meta/conventions.md`.

## Terminology (realigned 2026-07-31)

The vocabulary was realigned to the question-first process description (owner
decision 2026-07-30); `before_we_ai/glossary.py` is the one home of the terms.
Renames: `Probe` → `CheckPlan`, `TemplateSpec` → `CheckDefinition` (package
`probes/` → `checks/`), `RoleBindingClaim` → `MappingClaim`, `RoleSet` →
`DomainGuide` (`llm/roles.py` → `llm/domain_guide.py`), `QuestionCard` →
`ClarificationQuestion` ("Fachfrage" retired), statuses `inferred` → `proposed`
and `tested` → `test-supported`, actor/evidence `probe`/`probe_result` →
`check`/`check_result`.

- **Config break, no shim**: `before-ai.yaml` key `llm.roles_file` is now
  `llm.domain_guide_file`. Project stores are regenerated, not migrated
  (no committed store carried the old strings).
- **The model's wire contract stayed stable**: the 13 `REGISTRY` template
  names (`anti_join`, `cardinality`, …), the JSON fields the model fills
  (`claim_id`, `template`, `params`, `no_template_reason`, `hypotheses`,
  `bindings`), the contract names (`v1_hypotheses`, `role_binding`,
  `v2_bind`) and the claim labels `c1..cN` did not change. Prompt prose and
  section headers did → fixtures re-recorded live; any count movement in
  that diff is a signal about prompt fragility, not a schema artifact.
- The concepts reserved at that rename (`AnswerRequest`, `RequiredKnowledge`,
  `ReadinessMap` + ready/ready_with_limitations/blocked) were **built in M6**
  and are live in `glossary.py`; `ClarificationQuestion.sql`/`result_ref`
  moved to `AnswerRequest`, and the card gained a `scope`.

## Dev environment

- Python 3.13, venv at `/workspace/.venv` (system pip is externally-managed)
- Repo root: `/workspace` — https://github.com/happychriss/before-we-ai
  (`pyproject.toml` lives in `src/`)
- Install: `source /workspace/.venv/bin/activate && pip install -e '.[dev]'` in
  `/workspace/src`; run `python -m pytest -q` there (374 tests green after M6,
  incl. readiness_report; CI runs fully offline from recorded fixtures)
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
never on its own (owner decision 2026-07-12). A domain pack = the domain
guide (data) + the domain-tagged check definitions (code). What is
domain-specific is therefore explicit and enumerable: `CheckDefinition.domain`
(`None` = generic; today exactly the three invariants carry
`domain="finance"`, 10 of 13 templates are generic), locked by
`test_domain_specific_templates_are_explicitly_tagged`. Showing the tag in
the rendered V2 template docs would change prompt bytes → joins the M5
fixture re-record batch.

### Portability — measured, not assumed (2026-07-31)

Owner question: would a second domain (shipbuilding — bill of materials and
supply chain) work, or would the wording break? Tested by writing that guide
and rendering a report from it. Three results, worth keeping:

1. **The narration is domain-neutral and needs no change.** Every derived
   sentence is composed from three slots that belong to the domain pack: the
   guide's **definition**, the law's **name**, and the run's **verdict
   numbers**. "The bom_rollup law passed on `pdm__bom_positions` and felled
   the other candidate" comes out of the same template as the finance one.
   The only sentence carrying business meaning is the one the guide's author
   wrote.
2. **The cost of a new domain is laws, not prose — and it fails loudly.**
   A guide naming a law that does not exist is rejected at load ("`bom_rollup`
   is no check template and not 'clarification'"). A guide with only
   `decided_by: clarification` objects loads and renders, but then nothing is
   ever promoted and every object ends in a question: honest, and no longer
   discovery. So onboarding a domain means writing its conservation laws as
   SQL templates.
3. **Two leaks found and fixed.** `glossary.py` explained general terms with
   finance examples ("a business object … journal, subledger, intercompany"),
   and the "1.3 Domain-law templates" panel listed the whole `REGISTRY`, so a
   shipbuilding project displayed three finance laws among its declared
   inputs — laws its own lint would refuse. **Two rules follow, both now
   enforced by tests:** the canonical vocabulary carries no domain examples
   (`tests/unit/test_glossary.py`), and the law panel shows this project's
   domain only, counting the others
   (`test_the_law_panel_shows_this_project_s_domain_and_no_other`). A scan of
   a rendered shipbuilding report for finance nouns now returns nothing.

### The domain pack is the critical — and currently unverified — input

Established in the owner validation walkthrough of 2026-07-31. This is the
most load-bearing open weakness in the product; treat it as such.

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

**Measured, not assumed (2026-07-31).** No plausible impostor in the frozen
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

**Guide acceptance kit — the three parts.** `docs/before-ai-concept.md` §6
predicted the need and sketched the first two; the third comes from the
2026-07-31 findings:

1. **Per new law:** one fixture where it holds (check must PASS) and one
   deliberately violated (must FAIL, and only on the seeded row). Catches the
   trivially-passing law — the named remaining path to false confidence.
2. **Per new role:** at least one wrong candidate that must lose its
   election. Catches definitions too vague to discriminate.
3. **Coherence lint** (static analysis over guide + REGISTRY, no data
   needed): no role may declare a law it can only be a **slot** of; every
   law's slots must be fillable by declared roles. Catches the `amount_local`
   class automatically, and is the same mechanism as the slot-side lint
   already queued for M5 — build them together.

### Guide by construction — owner-aligned 2026-07-31 (pre-M6 + M6)

Owner discussion record: `docs/before-we-ai-key-findings-and-conclusions.md`.
Three decisions close the "nothing tests the guide" gap **by construction**
rather than only by testing. The first was the **pre-M6 alignment step**, and
it had to land before the ReadinessMap consumes the guide's shape, because a
structure change under an already-built dependent layer is the expensive kind.

1. **Objects with fields, not a flat role list — BUILT 2026-07-31.** The old
   guide mixed levels: `journal` (a business object) and `amount_local` (a
   field inside it) were both "roles" with their own settlement paths — which
   is exactly what made the `amount_local` mis-declaration *expressible*. The
   guide now declares **business objects** (`decided_by:` a domain law or
   `clarification`) each with **fields** (`decided_by: slot` plus `fills:`, or
   `clarification`; **a field can never declare a law**). That makes the
   `amount_local` bug class inexpressible — stronger than a lint that merely
   catches it. A slot field settles through its object's passing law from
   evidence that already existed and was simply not connected (`settled_slots`
   — see the resolution bullets under Domain inputs). The **coherence lint**
   (part 3 of the acceptance kit) is built against the new shape and absorbed
   the former M5 kickoff item 5; the slot-side metadata it needs lives on
   `CheckDefinition.slots`.
   **Wire-contract rule applied again, and held:** the model sees the same flat
   rendered definitions as before (`decided_by` never entered a prompt; the
   hierarchy is consumed by the lint, role resolution, and elections only).
   Objects and their fields flatten in guide order, and the fixture drift guard
   passed **untouched** — the byte-stability proof, offline. No fixture
   re-record was needed: every recorded LLM answer replays unchanged.

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
   not replace the kit.** Under M6's question-first flow, a guide wrong by
   *omission* surfaces as `blocked` in the ReadinessMap: the question is the
   external referent the guide is measured against, and small per-question
   guides (a page, reviewable) replace an unbounded domain model. A guide
   wrong by **commission** — a too-loose law that a wrong table passes — is
   untouched by question-first; the acceptance kit and coherence lint remain
   the only protection on that path, and they matter *more* under the
   readiness framing, because a wrong guide then produces a confident,
   product-branded "ready".

## Epistemic core (`model/`, `store/` — M1, tags m1-core-v1/v2)

- `model/` is pure and IO-free; `store/` is a YAML repo with append-only evidence,
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

## Ingestion & profiling (`sources/`, `profile/`, `scan.py` — M2, tag m2-ingestion-v1)

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

## Checks & engine (`checks/`, `engine/` — M3, tag m3-probes-v1)

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
  skipped(reason)). Since M4, a check whose SQL cannot execute is **contained**:
  it lands in `skipped` with the error as reason, writes no evidence, leaves its
  claim untouched — AI-planned checks must never kill the sweep (visibility, not
  judgment; the loud-crash-on-uncastable-amounts contract inside running checks
  is unchanged).
- Normalization is part of the claim: T1 passes canonical, fails with
  `canonical: false` (raw CAST). decode template checks functional dependency,
  not string equality.

## LLM contracts (`llm/` — M4, tag m4-llm-v1)

- **Thin typed functions, no framework**: `hypothesize(root)` (V1, frontier),
  `propose_mappings(root)` (frontier), `plan_checks(root)` (invariant batch
  frontier / ordinary batch mid-tier) — library seams like `scan(root)`; models
  and offline switch in `before-ai.yaml` `llm:` (defaults in `llm/config.py`;
  key ONLY via env var `ANTHROPIC_API_KEY`, lazy SDK import, optional `[llm]` extra).
  Owner decisions 2026-07-12: Anthropic API; `claude-opus-4-8` for V1 + mapping
  proposals, `claude-sonnet-5` for plain check planning.
- **Controlled predicate vocabulary** (`llm/vocabulary.py`): closed `Literal` in
  the output schemas — free-form predicates fail validation. `TEMPLATE_PARAMS`
  mirrors `checks.REGISTRY` key-for-key, locked by a unit test. Every hypothesis
  carries a `Predicate` with canonicalized params ⇒ claim_key dedup works for
  AI claims; `rationale` is logged, never stored (wording-free identity).
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
  fixture `input_sha256` against rebuilt inputs; refresh procedure under
  "Operations" below. GOTCHA (found+fixed 2026-07-31): the recorder must
  take the last **non-repair** attempt — an item-scoped repair answer can
  never stand in for the full batch; and a live repair that *accepted*
  items is irreproducible offline (labels shift downstream) — the script
  warns, re-run the refresh in that case. GOTCHA: the corpus generator's
  `generator_spec/roles.yaml` names trap decoys — runtime domain guides must be
  clean (see `tests/fixtures/domain_guide_finance.yaml`).
- **A refusal is a result — and it is persisted** (2026-07-12). Every claim V2
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
- **Every entry declares its settlement path** (2026-07-12; the viewer's role
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
  question** (`settled_slots`, pre-M6 alignment). `CheckDefinition.slots` names
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
  2026-07-31 (owner): the ReadinessMap reads the derivation.** The claims keep
  their status; no new promotion path, so the machinery that keeps
  False-Promotion at 0 is untouched. The rejected alternative — letting the
  passing run's evidence attach to the field claim and promote it — would have
  meant evidence from a run bound to *one* claim changing *another* claim's
  status. Consequence, designed for: *satisfied* and *promoted* are now
  deliberately different things, so every ReadinessMap item states **which one
  it is and why** ("satisfied because its own claim is test-supported" vs
  "satisfied because the balance law of 'journal' passed while reading
  `<column>`; its own candidate claims are still proposed").
- **Elections run per scope** (gap found 2026-07-31, **closed in M6**). A role
  used to elect exactly one winner across the whole project, but a landscape is
  typically
  multi-entity: DE and US each legitimately own a journal, an account column,
  a period column, a doc_ref. Two visible consequences in the walkthrough:
  the `account`/`period`/`doc_ref` clarification questions offer three
  candidates that are **all correct**, so answering forces the owner to
  discard two right mappings; and `us_erp__gl_postings` is reported
  `contradicted` for `journal`, which reads as "not the journal" when it *is*
  the US journal carrying a €50k data defect (F22). Note the status alone
  cannot separate "wrong table" from "right table, broken data" — only the
  evidence can: the decoy fails 24/24 periods by millions, the US ledger
  fails 1 period by exactly 50,000.

  **The fix (M6).** The election unit is **role × scope**
  (`domain_guide.scopes_of`, `_candidates(store, role, scope)`), and
  `settled_slots` is scoped too: each ledger consumed its own amount column,
  and one entity's passing run answers nothing for another. Where a candidate's
  scope comes from matters more than the grouping. **Not** the model — it has
  not been told that scopes exist and must not be, since which entity a table
  serves is a human's statement. **Not** the source's name — that would be
  exactly the wording-dependent magic this product avoids. A **source declares
  whose books it is** (`sources[].scope` in `before-ai.yaml` →
  `Source.scope`), and a binding inherits the scope its sources agree on
  (`ProfileIndex.scope_of`); a binding reaching across differently-owned
  sources has no scope and belongs to no entity's election. A project that
  declares nothing gets one landscape-wide election per role — byte-for-byte
  its old behaviour, which is why no pinned number moved. `Scope` became
  frozen (and hashable) in the process: elections group by it, and a value
  editable underneath a grouping could move a claim into another entity's
  election.

  Two things ride along. Clarification questions gained a `scope` and dedup on
  `(question, scope)` — see the defect note under "Question flow & readiness".
  And the report renders one block per role × scope, naming the books in the
  heading; its diagram counts "elections settled", not "roles elected",
  because a slot answered by its object's passing run counts and nobody
  elected it.
- Seeded-Recall lives in `tests/eval/seeded_recall.py` — reports, never gates.
  First measurement (M4, full report `docs/seeded-recall-m4.md`):
  **False-Promotion 0**, Seeded-Recall **15/25** in-scope traps incl. the T7
  semantic-only pair; prompt-leakage scan clean (prompts carry no corpus
  hints — findings derive from profile data, as designed). Open owner
  decision: the numeric recall bar.

### M4 design constraints (owner-aligned 2026-07-12, still binding)

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

## Readiness report (`readiness_report/` — owned code since 2026-07-12)

```bash
python -m readiness_report <project_root> -o <out.html>
```

The rendered state of knowledge: what is known, what is assumed, what is
unknown — derived live from the store, never stored. Read-only and
click-through for validators: start at the process diagram, walk down the
pipeline, pick a claim and follow it outward to evidence, sources, lineage,
and the questions that depend on it — without hand-reading YAML. Renders one
self-contained HTML file; works for an empty project. Originally built by an
external agent (PR #2) as the *claim viewer*; owned and maintained like the
rest of the codebase since 2026-07-12, renamed 2026-07-31 when it became the
owner's primary validation *and* understanding surface (it was never only a
claim view). Since M6 it also carries the per-question ReadinessMap
(section 6), and the diagram's M6 ghost is a real stage.

**Binding constraints (in force):**

- Strictly read-only: `ProjectStore(root)` load/convenience methods only;
  never `save_*` / `add_*` / `mark_*_stale`; modifies nothing in the project.
- The core must not know the report exists: no dependency from
  `before_we_ai/*` on `readiness_report/`. (The report imports
  `admissible_templates`, `REGISTRY`, `load_domain_guide` and `settled_slots`
  read-only — still one-directional.)
- Static HTML, no runtime dependency beyond a browser. No graph libraries,
  no chart libraries, no multi-file output.

**What it renders** — the page *is* the pipeline, in pipeline order, each
section headed by the step that produced it; master–detail with search +
status/predicate/role filters; deep links reveal their claim:

- **The process diagram** (top) — the whole machine on one line, carrying this
  project's live counts, every count a link into the section that produced it:
  inputs → measured → the AI proposes → the checks decide → humans decide the
  rest. Two things are drawn, not written: the **actor boundary** between
  "proposed" and "decided" (nothing the AI authors can promote a claim — the
  structural False-Promotion invariant, made visible), and a **ghost node**
  for M5 (documents), dashed and labelled "not built", so what is missing is
  stated rather than omitted. M6's node became real when M6 shipped.
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
- **4 · Decided** — the elections, one per **role × scope** (the entity named
  in the heading): the candidates, the elected winner, each loser with the
  domain law that felled it; a role whose candidates were never bound to an
  invariant says so; a slot field shows the column its object's passing law
  consumed; a role that lost every candidate ends in its clarification
  question.
- **5 · Open** — the clarification-questions inbox with the claims each
  question rests on: the human's to-do list.
- **6 · Readiness** — per asked question: the business question verbatim, the
  derived verdict with the dependencies it names, and every required item with
  the sentence saying where it stands, grouped into "what the figures are
  computed from" and "what the figures mean". See "Question flow & readiness".
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

**The three-voices rule (confirmed 2026-07-31).** The report is read by
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
the question's wording. **Behaviour change 2026-07-31:** question dedup is
exact-text, so with the candidate list out of the string, a changed candidate
set no longer drafts a second card — it dedups to the same open question and
keeps the first card's `claim_ids`. That is the more correct reading ("which
column is the document reference?" is one question, not a new one per
candidate shuffle), and append-only means older stores keep their old
wording.

`tests/unit/test_readiness_report.py` locks the funnel stage counts, the
winner / loser-with-its-law / clarification-question of the role elections,
the process diagram (live counts, actor boundary, ghost nodes), the question
pick-list and folded ids, and the three voices.

## Onboarding workflow (design owner-aligned 2026-07-12, not yet built)

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
   `tests/fixtures/domain_guide_finance.yaml`). Config `domain_guide_file:
   finance` resolves to the bundled guide; an explicit path overrides. Flat
   YAML, no plugin framework (Regel der Drei). Shipped guides must pass the
   same leakage tripwire as prompts.
   **Logical pack validation:** the entry half shipped 2026-07-12
   (`decided_by:` + lint); the **slot side** shipped 2026-07-31 with the
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
   **Refined 2026-07-31:** the sign-off is per entry, not per file — generic
   laws/concepts may stay AI-drafted; organisational bindings must be
   human-answered (see "Guide by construction" under Domain inputs).

## Question flow & readiness (M6 — BUILT 2026-07-31)

Owner-aligned spec; discussion record
`docs/before-we-ai-key-findings-and-conclusions.md`. Product thesis: **an
answer-readiness control layer for enterprise AI.** The system does not ask
whether the data landscape is generally AI-ready; it checks whether **this
specific answer** is ready. USP in one sentence: *before-we-ai traces a
business answer back to every mapping, meaning, and rule it depends on,
tests what can be tested, and blocks the answer when a material dependency
remains unsupported.*

**Flow (top-down).** The pipeline before M6 ran bottom-up (scan everything,
propose claims about the whole landscape) and survives unchanged as the
middle of the machine; M6 added the top and the bottom:

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

**Objects** (`model/objects.py`; all three words are live in
`glossary.py` since M6, and carry no domain examples):

- **`AnswerRequest`** — the structured form of one business question:
  `requested_output` + `Scope`. The human question stays the *business
  question* and is kept verbatim; this is its software representation. It
  absorbed the vestigial `sql`/`result_ref` answer-half that
  `ClarificationQuestion` used to carry. Stored in `answers/`.
  **No `created_by`**, and neither has `RequiredKnowledge`: authorship here
  is fixed by the shape — `question` is the human's, `requested_output` and
  `scope` are V4's — so the field would have read `human` on every record
  while being wrong about two of the three. A field whose value never varies
  carries no information (same defect class as the redundant
  `Hypothesis.kind`, M5 kickoff). `Claim.created_by` and
  `KnowledgeLink.linked_by` are the contrast: they vary, and code branches
  on them. The report attributes accordingly — the question as a human
  quote, the requested output as the AI's.
- **`RequiredKnowledge`** — `KnowledgeItem`s (`object` / `field` / `rule`),
  each carrying the request's scope, each with a `why` a human can prune on.
  Drafted by V4, persisted because the pruning is a human decision, not
  something re-derivable from the request. A field item names its object; a
  rule item is what the vocabulary does *not* contain.
- **`ReadinessMap`** (`readiness/`, a *derived structure*, never a record) —
  per item: claim, evidence, ground, remaining gap; overall verdict
  `ready` / `ready_with_limitations` / `blocked`. Recomputed on every read,
  the same discipline as `resolve_status`: a stored verdict could drift away
  from the evidence beneath it, and a drifted verdict is worse than none.

`readiness/` is deliberately its own package, not part of `model/`. The
epistemic core decides what may be **believed** from evidence; readiness
decides what may be **claimed** from those beliefs. Keeping the two
vocabularies apart is the handover principle spelled as a module boundary,
which is why `Readiness` does not live in `model/enums.py`.

**Handover principle** (measurement stays separate from interpretation): a
check never directly proves a claim or produces an answer —
`CheckPlan → CheckRun → Evidence → claim status → readiness decision`. In
product words: the AI proposes the path; the check engine measures what
happened; evidence changes what the system is allowed to believe; the
readiness evaluator decides what the system is permitted to claim.

### V4 — the request contract (`llm/v4_request.py`)

`ask(root, question, guide=…)`, the standard V-contract shape (typed schema,
`call_with_retry` with the two-tier repair, `CallLogger`, offline stub, drift
guard). Its input (`inputs.build_question_context`) is the question plus the
domain vocabulary — **no profiles**: whether the data can serve the request is
the rest of the pipeline's job, and answering it here would be the model
deciding. Fields render nested under their objects, unlike the flattened
role-binding input, because here the hierarchy is the point.

The semantic check (`mapping.check_knowledge_item`) is asymmetric on purpose.
Objects and fields must exist in the vocabulary and sit where the item says
they sit, because a dependency the readiness evaluator could never resolve is
a gap that would go quiet. Rules are the mirror image: they exist *because*
the vocabulary has no entry for them, so a rule is rejected only when it names
one — which makes it a mis-kinded object or field, and the error says so.

The corpus fixture (`v4_request__corpus.json`) is **hand-authored** and marked
as such, per the rule in `llm/stub.py`; `refresh_fixtures.py` records V4 first,
so the next online run replaces it.

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
   whose claims are still `proposed`. Since the 2026-07-31 owner decision,
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

*Owner decision 2026-07-31.* The first implementation matched a rule's name
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

One deliberate leniency, stated rather than hidden: a **landscape-wide claim
covers a scoped item**, because a shared account master genuinely serves every
entity and "no declared owner" is its normal state. The sentence then says so
("no source declares it as entity DE's, so this rests on a landscape-wide
mapping"). The reverse does not hold — DE's ledger says nothing about the
landscape.

### DEFECT closed in M6 — question dedup collided under scoped elections

Clarification questions deduplicated on **exact text**
(`llm/domain_guide.py::_save`, `engine/runner.py::_draft_question`) and
`ClarificationQuestion` had no scope. While the candidate list sat inside the
question text, two scopes produced two strings and two cards. The readability
rework of 2026-07-31 took that list out — correctly, it was unreadable and
duplicated `claim_ids` — which made *"Which of the proposed candidates is the
'doc_ref'?"* byte-identical for DE and US. Under scoped elections the second
scope's card would have collapsed into the first and taken its candidates
with it: the "never silence" rule broken by a change made for readability.

Fixed before scoped elections landed: cards carry a `scope`, dedup keys on
`ClarificationQuestion.dedup_key()` = `(question, scope)`, and the scope leads
the rendered question ("For entity DE: …") where a reader cannot miss it. A
regression test asks one role in two scopes and demands two cards.

### The surface

The readiness report's process diagram had reserved M6's slot as a dashed
ghost; that node is real now, carrying live counts ("2/9 dependencies
supported · blocked") and linking into a new **section 6 · Readiness**.
Two rules bind that panel, neither of which existed when M6 was specified:

- **The three voices** (see "Readiness report" above). The business question
  appears verbatim — it is the human's. The verdict and every item's status
  sentence are derived and are the headline. The `why` the model wrote when it
  listed a dependency is legible, attributed and subordinate: it says why the
  item is on the list, never what became of it.
- **Domain neutrality** — the panel's wording carries no domain nouns; the
  concrete ones come from the guide, as everywhere else.

Items are grouped as "what the figures are computed from" and "what the
figures mean", which *is* the verdict rule, so the page explains itself.

### Acceptance — the six demo behaviours

Discussion record §12: (1) identify both candidates, (2) contradict or qualify
the wrong one, (3) surface the missing business rule, (4) ask one focused
clarification, (5) build the ReadinessMap, (6) permit, narrow, or block.

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

**Not built: the small standalone demo dataset** of findings §12 (one correct
journal, one attractive wrong export, an account master, a sign convention, a
non-inferable policy) intended to double as the first user experience. Running
it offline needs its own recorded V1/role/V2 answers; hand-authoring those
would mean writing the model's answers and then asserting the system found
what was written, so the acceptance test uses the frozen corpus instead. The
presentable dataset needs one live recording session — queued behind the API
key rotation.

**Ordering (owner decision 2026-07-31): M6 before M5**, with the pre-M6
alignment step (guide objects+fields restructure + coherence lint, "Guide by
construction") first, because the ReadinessMap must not be built on the flat
role model. M5 stays necessary — the K3 document-only traps and three
walkthrough claims whose V2 refusals literally name documents wait on it.

## Operations

- **Install & test**: from `/workspace/src`, `source
  /workspace/.venv/bin/activate && pip install -e '.[dev]'`; `python -m
  pytest -q` (257, fully offline). Never run pip against the system Python.
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
