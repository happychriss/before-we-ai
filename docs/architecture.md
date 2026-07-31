# Product architecture — confirmed design (M1–M4)

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
- Genuinely new concepts (`AnswerRequest`, `RequiredKnowledge`,
  `ReadinessMap` + ready/ready_with_limitations/blocked) are **specified as
  M6**, not built; `ClarificationQuestion.sql`/`result_ref` are the
  vestigial answer-half that migrates to `AnswerRequest` then.

## Dev environment

- Python 3.13, venv at `/workspace/.venv` (system pip is externally-managed)
- Repo root: `/workspace` — https://github.com/happychriss/before-we-ai
  (`pyproject.toml` lives in `src/`)
- Install: `source /workspace/.venv/bin/activate && pip install -e '.[dev]'` in
  `/workspace/src`; run `python -m pytest -q` there (257 tests green after M4,
  incl. claim_viewer; CI runs fully offline from recorded fixtures)
- Authoritative German spec: `docs/spec/`

## Domain inputs — declared, transparent, validated (cross-cutting)

Everything domain-specific enters through exactly **three declared inputs**;
the rest of the product is domain-agnostic. Each input must be (a) declared
as input, (b) transparent to the user, (c) logically validated:

| input | declared | transparent | validated |
|---|---|---|---|
| raw data | `before-ai.yaml` `sources:` (human-authored) | step-INPUT blocks; fingerprints; SYSTEM declarations | canonicalization + profiling; re-scan idempotence |
| domain guide (data) | `llm.domain_guide_file` | INPUT block prints the file; definitions land in prompts verbatim (logged) | Pydantic `DomainGuide`, `extra="forbid"` + settlement-path lint — **the slot-side check is an M5 gap** (see "Onboarding workflow") |
| check definitions / domain laws (code) | `checks/REGISTRY` | rendered template docs in the V2 prompt (logged); executed SQL kept in evidence | unit test locks `TEMPLATE_PARAMS` ↔ REGISTRY; review like all code |

**The product is a general machine only together with a domain pack** —
never on its own (owner decision 2026-07-12). A domain pack = the domain
guide (data) + the domain-tagged check definitions (code). What is
domain-specific is therefore explicit and enumerable: `CheckDefinition.domain`
(`None` = generic; today exactly the three invariants carry
`domain="finance"`, 10 of 13 templates are generic), locked by
`test_domain_specific_templates_are_explicitly_tagged`. Showing the tag in
the rendered V2 template docs would change prompt bytes → joins the M5
fixture re-record batch.

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
domain). **None of the 257 tests asks whether the guide is correct.** The
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
- **Every role declares its settlement path** (2026-07-12; the viewer's role
  elections made the gap visible). Each role in the domain guide carries
  `decided_by:` — the domain law that can elect it, `clarification` (no
  arithmetic can decide what a column *means*: a journal balances per period
  AND per document AND per year, so a passing law never proves what one slot
  means), or `slot` (only carried inside another role's law). The guide lint
  (`DomainGuide` validator) rejects a silent role and rejects a generic
  template or a foreign domain's law as decider. `decided_by` never enters a
  prompt — only the definitions render.
- **Role resolution — no silence**: `resolve_mappings` completes the rule *every
  non-slot role ends in a check verdict or a clarification question*:
  checked-and-lost → "which source is authoritative?"; law never bindable
  (every candidate carries V2's no-check declaration — the subledger_ar case:
  knowledge missing to apply the law) → "what domain knowledge is missing?";
  clarification-decided → question listing the candidates, answerable in one
  pick; no candidate at all (once the search ran) → "does this role exist?".
  Candidates without a check result and without a declaration are in flight
  and draft nothing. The losing candidates keep their honest derived statuses.
  Still M5: the slot-fillability side of the lint and role claims binding to
  *generic* templates (both under "Onboarding workflow" below).
- **KNOWN GAP — elections are scope-blind** (found 2026-07-31). A role elects
  exactly one winner across the whole project, but a landscape is typically
  multi-entity: DE and US each legitimately own a journal, an account column,
  a period column, a doc_ref. Two visible consequences in the walkthrough:
  the `account`/`period`/`doc_ref` clarification questions offer three
  candidates that are **all correct**, so answering forces the owner to
  discard two right mappings; and `us_erp__gl_postings` is reported
  `contradicted` for `journal`, which reads as "not the journal" when it *is*
  the US journal carrying a €50k data defect (F22). Note the status alone
  cannot separate "wrong table" from "right table, broken data" — only the
  evidence can: the decoy fails 24/24 periods by millions, the US ledger
  fails 1 period by exactly 50,000. The missing concept already exists in the
  core — `Scope(entity, period, segment)` is on `Claim` and used for rules;
  `MappingClaim` elections simply never consult it. Likely shape: elect per
  scope, so each entity gets its own occupant and only genuine decoys lose.
  **Decide before M6** — the ReadinessMap is per-question and will inherit
  whatever scoping the roles have. Not a quick fix; do not bundle it into the
  M5 kickoff re-record.
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

## Claim viewer (`claim_viewer/` — owned code since 2026-07-12)

```bash
python -m claim_viewer <project_root> -o <out.html>
```

Read-only, click-through HTML viewer for validators: start at a claim, walk
outward to evidence, sources, lineage, and the questions that depend on it —
without hand-reading YAML. Renders one self-contained HTML file; works for an
empty project. Originally built by an external agent (PR #2); owned and
maintained like the rest of the codebase since 2026-07-12.

**Binding constraints (in force):**

- Strictly read-only: `ProjectStore(root)` load/convenience methods only;
  never `save_*` / `add_*` / `mark_*_stale`; modifies nothing in the project.
- The core must not know the viewer exists: no dependency from
  `before_we_ai/*` on `claim_viewer/`. (The viewer imports
  `admissible_templates` and `REGISTRY` read-only — still one-directional.)
- Static HTML, no runtime dependency beyond a browser. No graph libraries,
  no chart libraries, no multi-file output.

**What it renders** (the page mirrors the pipeline — outcome first, the story
of one claim second, raw fields last; master–detail with search + status/
predicate/role filters; deep links reveal their claim):

- **How to read this page** — intro + the core terms, rendered from
  `before_we_ai/glossary.py` (one home, no drift).
- **Domain pack** — the three declared domain inputs, live from the project:
  sources, the domain guide (domain, count, names, definitions, settlement
  paths), and the domain-law check definitions (naming the generic remainder
  as such).
- **The funnel** — proposed → planned / unbindable / semantic-only / skipped →
  judged → derived status; each number a clickable filter. The buckets are
  read from the `DECLARATION` records V2 writes ("A refusal is a result"), so
  they match the step-5 report exactly, and each claim shows the model's
  verbatim reason where its check would have been.
- **Clarification-questions inbox** — every open question on top, with the
  claims it rests on: the human's to-do list.
- **Role elections** — per role: the candidates, the elected winner, each
  loser with the domain law that felled it; a role whose candidates were
  never bound to an invariant says so; a role that lost every candidate ends
  in its clarification question.
- **Claim detail as a story**: statement, one derived-status badge (a loud
  banner only when the stored status diverges), then collapsible
  *1 proposed → 2 planned → 3 judged → 4 context*; ids and timestamps in
  collapsed fine print. Check-plan cards show template, params, roles,
  domain-law badge, default tolerances, and — from the check_result payload
  (`payload["sql"]`), where the runner writes it — the **rendered SQL as the
  question that was asked of the data**. A check that never ran says so.
  Invariant check plans carry no `claim_id`; they are reached through the
  `check_plan_id` on the mapping claim's evidence.

`tests/unit/test_claim_viewer.py` locks the funnel stage counts and the
winner / loser-with-its-law / clarification-question of the role elections.

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
   **Logical pack validation:** the role half shipped 2026-07-12
   (`decided_by:` + lint). Remaining for M5, needs template metadata: the
   **slot side** — each invariant `CheckDefinition` declares which *roles*
   its slots consume, so the lint can also reject an invariant whose slots
   the guide cannot fill (invariant params like `journal`, `subledger`,
   `left`/`right` are not literally role names today). Also M5 (prompt
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
  `validation/scripts/` (numbered stages, offline by default; `viewer.sh`
  renders the claim viewer, `llm-log.sh` the verbatim call log).
