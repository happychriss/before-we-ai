# Product architecture — confirmed design (M1–M4)

Per-package confirmed decisions and gotchas for `src/before_we_ai/`. Feature list
and status: `docs/requirements.md`. Working rules: `meta/conventions.md`.

## Dev environment

- Python 3.13, venv at `/workspace/.venv` (system pip is externally-managed)
- Repo root: `/workspace` — https://github.com/happychriss/before-we-ai
  (`pyproject.toml` lives in `src/`)
- Install: `source /workspace/.venv/bin/activate && pip install -e '.[dev]'` in
  `/workspace/src`; run `python -m pytest -q` there (183 tests green after M3,
  incl. claim_viewer)
- Authoritative German spec: `docs/spec/`

## Domain inputs — declared, transparent, validated (cross-cutting)

Everything domain-specific enters through exactly **three declared inputs**;
the rest of the product is domain-agnostic. Each input must be (a) declared
as input, (b) transparent to the user, (c) logically validated:

| input | declared | transparent | validated |
|---|---|---|---|
| raw data | `before-ai.yaml` `sources:` (human-authored) | step-INPUT blocks; fingerprints; SYSTEM declarations | canonicalization + profiling; re-scan idempotence |
| role pack (data) | `llm.roles_file` | INPUT block prints the file; definitions land in prompts verbatim (logged) | Pydantic `RoleSet`, `extra="forbid"` — **schema only; role↔invariant consumption check is an M5 gap** (see docs/onboarding-workflow.md) |
| probe/invariant templates (code) | `probes/REGISTRY` | rendered template docs in the V2 prompt (logged); executed SQL kept in evidence | unit test locks `TEMPLATE_PARAMS` ↔ REGISTRY; review like all code |

**The product is a general machine only together with a domain pack** —
never on its own (owner decision 2026-07-12). A domain pack = the role YAML
(data) + the domain-tagged templates (code). What is domain-specific is
therefore explicit and enumerable: `TemplateSpec.domain` (`None` = generic;
today exactly the three invariants carry `domain="finance"`, 10 of 13
templates are generic), locked by
`test_domain_specific_templates_are_explicitly_tagged`. Showing the tag in
the rendered V2 template docs would change prompt bytes → joins the M5
fixture re-record batch.

## Epistemic core (`model/`, `store/` — M1, tags m1-core-v1/v2)

- `model/` is pure and IO-free; `store/` is a YAML repo with append-only evidence,
  integrity check, optional git checkpoint.
- **Status is derived, never set**: `resolve_status(claim, evidence)` recomputes
  from non-stale evidence, order-independent. Conflict (probe fail + anything
  supporting) → unresolved; fail alone → contradicted; confirmation →
  business-confirmed; pass → tested; weak evidence never promotes.
- **Five evidence types** (derived enumeration; spec says "die fünf Evidenztypen"
  without listing): probe_result | document_anchor | confirmation | testimonial |
  declaration. Pydantic validators enforce actor consistency — AI structurally
  cannot author promoting evidence.
- **Mirror-loop guard (F29)**: confirmation on a testimonial claim requires explicit
  `Scope` or `attach_evidence` raises `PromotionError`; `resolve_status` also
  ignores inadmissible confirmations.
- **Claims are semantic rules, not rows**: identity = Predicate(name+params) +
  Scope + Validity + source_ids, hashed by `semantics.claim_key()` (wording
  excluded); `store.add_claim()` dedups on key. Probe evidence is aggregate-only
  (population / exception_count / exception_samples capped at 20 / result_ref
  parquet). `escalate_exception()` mints a child claim (provenance via
  `derived_from`, NOT status-bearing; child starts inferred). Impact is derived
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

## Probes & engine (`probes/`, `engine/` — M3, tag m3-probes-v1)

- `probes/REGISTRY`: name → TemplateSpec(file, prepare, verdict, tolerances,
  question); 13 Jinja2 templates in `templates/*.sql.j2`, split by
  `-- ::exceptions::` marker into population + exceptions query. Verdicts
  deterministic.
- **Verdict granularity comes from the claim**: anti_join param
  `expectation: "empty" | "report"` — report-claims (K6 legitimate orphans) can
  structurally never FAIL, only INCONCLUSIVE + drafted Fachfrage (QuestionCard,
  deduped by exact text).
- **Cardinality probe = chance-overlap counter-evidence (T6)**: PASS needs
  containment ≥ 0.95 AND parent uniqueness ≥ 0.99.
- Invariants attach to claims like everything else (RoleBindingClaims; F27:
  journal=buchungen_report FAIL → contradicted, rendered SQL kept as reason).
  Amounts CAST, not TRY_CAST — un-castable values crash loudly.
- **Tolerances**: defaults per TemplateSpec; overrides ONLY via `before-ai.yaml`
  `tolerances:` (scalar normalized to `{absolute: v}`).
- **Evidence contract per run**: probe_id + rendered exceptions-SQL + summary in
  payload, source_fingerprints per view, samples ≤20, full exception set →
  `cache/probe_runs/<evidence_id>.parquet`. Probe persisted before its evidence;
  integrity checks probe refs.
- `run_ready`: probes topo-sorted by claim; `ready_for_probe` gates (deps ≥
  tested); claim-less probes first; returns RunReport(executed, skipped(reason)).
  Since M4, a probe whose SQL cannot execute is **contained**: it lands in
  `skipped` with the error as reason, writes no evidence, leaves its claim
  untouched — AI-bound probes must never kill the sweep (visibility, not
  judgment; the loud-crash-on-uncastable-amounts contract inside running
  probes is unchanged).
- Normalization is part of the claim: T1 passes canonical, fails with
  `canonical: false` (raw CAST). decode template checks functional dependency,
  not string equality.

## LLM contracts (`llm/` — M4)

- **Thin typed functions, no framework**: `hypothesize(root)` (V1, frontier),
  `propose_role_bindings(root)` (frontier), `bind_probes(root)` (invariant batch
  frontier / ordinary batch mid-tier) — library seams like `scan(root)`; models
  and offline switch in `before-ai.yaml` `llm:` (defaults in `llm/config.py`;
  key ONLY via env var `ANTHROPIC_API_KEY`, lazy SDK import, optional `[llm]` extra).
- **Controlled predicate vocabulary** (`llm/vocabulary.py`): closed `Literal` in
  the output schemas — free-form predicates fail validation. `TEMPLATE_PARAMS`
  mirrors `probes.REGISTRY` key-for-key, locked by a unit test. Every hypothesis
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
- **Model output is untrusted input**: binding-time checks cover param value
  shapes (lists, int-able accounts), bare identifiers vs `*_expr`/`*where`,
  no pre-aggregation in expressions (templates SUM for themselves), and
  referential integrity (`VIEW_PARAMS`/`COLUMN_PARAMS`: views exist, columns
  exist on the view they're used against). Unambiguous `view.column` values
  are normalized to bare columns, not rejected. What still slips through is
  contained by the engine (see run_ready) — visible, never fatal.
- **ULIDs never enter a prompt**: V2 references claims via deterministic labels
  (`claim_label_map`, identity-sorted c1..cN) — binding inputs are byte-stable
  across fresh projects, which is what makes fixture hashes meaningful.
- **Input builders** (`llm/inputs.py`): deterministic rendering (sorted
  profiles, fixed key order); NO token cap — optional `max_chars` escape hatch
  trims lowest-signal fields first and always records `trim_notices` into the
  call log; silent truncation structurally impossible (all rendering funnels
  through `BuiltInput`).
- **Stub mode**: fixtures keyed contract+scenario (never input hash — a builder
  change must not strand keyless devs); drift guard = offline test comparing
  fixture `input_sha256` against rebuilt inputs; refresh via
  `tests/eval/refresh_fixtures.py` from `cache/llm_log/` (one JSON per call,
  verbatim request included). GOTCHA: the corpus generator's
  `generator_spec/roles.yaml` names trap decoys — runtime role files must be
  clean (see `tests/fixtures/roles_finance.yaml`).
- **A refusal is a result — and it is persisted** (2026-07-12). Every claim V2
  leaves without a probe (`unbindable` / `semantic_only` / `skipped`) gets a
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
- **Role resolution**: an unresolved role (candidates probed, none ≥ tested)
  becomes a deduped Fachfrage via `resolve_roles` — the losing candidates keep
  their honest derived statuses; nothing is silently discarded.
  KNOWN GAP the viewer made visible: roles that appear only as *slots* inside the
  invariants (`account`, `doc_ref`, `entity`) can never be elected by any probe —
  V2 correctly answers `template=null` for all their candidates, so they stay
  `inferred` and draft no Fachfrage. That is the role-pack lint's job (M5
  kickoff, `docs/onboarding-workflow.md`): every declared role must name the
  invariant that can elect it, or be declared slot-only.
- Seeded-Recall lives in `tests/eval/seeded_recall.py` — reports, never gates.

## Claim viewer (`claim_viewer/` — owned code since 2026-07-12)

`python -m claim_viewer <project_root> -o <out.html>` → one self-contained HTML.
Originally built by an external agent (PR #2); now maintained like the rest of
the codebase.
