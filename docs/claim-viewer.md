# Claim Viewer — component spec

**Source:** `src/claim_viewer/` · **Status:** complete, owned code (originally built by
an external agent, PR #2; ownership transferred 2026-07-12 — maintained to the same
standards as the rest of the codebase).

## Purpose

A read-only, click-through HTML viewer for validators of the epistemic core. It starts
at a claim and lets a human walk outward — evidence, sources, lineage, and the questions
that depend on it — without hand-reading YAML files.

## Usage

```bash
python -m claim_viewer <project_root> -o <out.html>
```

Renders one self-contained HTML file. Works for an empty project (zero claims) and for
freshly created claims with no evidence.

## Binding constraints (still in force)

- **Strictly read-only**: uses `ProjectStore(root)` load/convenience methods only;
  never calls `save_*` / `add_*` / `mark_*_stale`; modifies nothing in the inspected
  project (output goes elsewhere).
- **Core must not know the viewer exists**: no dependency from `before_we_ai/*` on
  `claim_viewer/`.
- Static HTML, no runtime dependency beyond a browser.

## What it renders

**The page mirrors the pipeline** (docs/SIMPLE-README.md "The big picture"): outcome
first, the story of one claim second, raw fields last. Master–detail — the sidebar is
the claim list (search + status/predicate/role filters), the main pane shows one claim
at a time; deep links (`#claim-…`, `#evidence-…`, `#probe-…`, `#question-…`) still work
and reveal their claim.

- **The funnel** — the epistemic story in four rows, each number a filter on the list:
  proposed (all claims, inferred when created) → bound / unbindable / semantic-only /
  skipped → judged (a probe actually ran) → derived status. The buckets are read from
  the `DECLARATION` records V2 writes (architecture.md "A refusal is a result"), so
  they match the step-5 report exactly, and each claim shows **the model's verbatim
  reason** where its probe would have been ("No documented pairs mapping
  account_range_group values to expected account_id ranges is available to populate the
  decode template's required 'pairs' parameter").
- **Fachfragen inbox** — every open QuestionCard on top, with the claims it rests on.
- **Role elections** — one block per role: the candidates, the elected winner, and each
  loser with the domain law that felled it (`ic_symmetry` (finance law) — 1 exception in
  24 rows). A role whose candidates were never bound to an invariant probe says so
  ("never put to the test"); a role that lost every candidate ends in its Fachfrage.
- **Claim detail as a story**: statement, the derived status badge and its one-line
  rationale, then collapsible *1 proposed → 2 bound → 3 judged → 4 context*, with ids,
  timestamps and raw fields in a "fine print" block. Probes show template, params,
  roles, default tolerances and a visible domain-law badge; probe-result evidence links
  back to the probe that produced it. Sources, lineage (`depends_on`, `derived_from`,
  reverse links) and dependent QuestionCards sit in *context*.
- One status badge — the **derived** one, since that is the truth. When the stored status
  disagrees, a loud banner says so instead of two badges side by side.
- The five statuses are color-coded; `contradicted` and `unresolved` stand out.

The funnel/election reader imports `admissible_templates` from `before_we_ai.llm.mapping`
and `REGISTRY` from `before_we_ai.probes` — read-only, and still one-directional (core
never imports the viewer).

## Probe linking (gap closed 2026-07-12)

The viewer predated M3's persisted `Probe` records; that gap is closed. Each claim
section shows a "Probes (falsification attempts)" block — template, params, roles,
the registry's `domain` tag and default tolerances — and every probe-result
evidence record links back to the probe that produced it. Invariant probes carry
no `claim_id`; they are reached through the `probe_id` on the role claim's
evidence, so they appear on the claims they judged. Rendered SQL stays where it
lives: on the evidence payload.

## Redesign — approved and shipped 2026-07-12

Motivation: the viewer was technically complete but read like an *archive dump* —
all claims stacked as full sections on one endless page, every field at equal
visual weight (a ULID as prominent as a verdict), and no view answered the
validator's first questions. The viewer is the basis of understanding and
validation, so it had to become an *instrument*. All six items below are
implemented; "What it renders" above describes the result, and
`tests/unit/test_claim_viewer.py` locks the funnel stage counts and the
winner / loser-with-its-domain-law / Fachfrage of the role elections.

**Principle: the page mirrors the pipeline** (docs/SIMPLE-README.md "The big
picture") — outcome first, the story of one claim second, raw fields last.
Terminology stays canonical (hypothesis / claim / status / role / binding /
probe / domain-law template / Fachfrage) — no synonyms.

1. **Master–detail instead of stacked sections.** Left: the filterable claim
   list (add predicate + role filters). Right: one claim's detail at a time
   (vanilla JS show/hide — still one self-contained file).
2. **Overview = the epistemic funnel**, replacing the four count boxes; each
   number a clickable filter:
   `85 claims (ai) → 58 bound / 18 unbindable / 8 semantic-only / 1 skipped →
   58 executed → tested / contradicted / inconclusive`.
3. **"Role elections" panel** — the heart of M4 validation, today invisible.
   One row per role: candidates with statuses, winner highlighted, each loser
   with the law that felled it; a role with no winner ends visibly in its
   Fachfrage.
4. **"Fachfragen inbox" panel** — the open questions are the human's to-do list
   and belong on top, each linking to the claims it rests on.
5. **Claim detail as a story in pipeline order**: statement + derived status
   with its one-line rationale first ("contradicted — probe `balance` found 1
   exception in 4,020 rows"); then collapsible blocks in the order things
   happened: *proposed* (predicate, author, time) → *bound* (probe, template,
   params, rendered SQL) → *judged* (evidence, verdict, population, exception
   samples) → *context* (sources, lineage, questions). IDs and timestamps move
   into collapsed fine print.
6. **Small but load-bearing**: collapse the stored-vs-derived double badge to
   one badge, with a loud banner *only* when they diverge; tag domain-law
   probes visibly as such; keep the existing status colors and words.

Explicitly still NOT in scope: graph visualizations, chart libraries, multi-file
output, any external dependency. The binding constraints above all stay.

Building item 2 surfaced a real gap and closed it: the store persisted probes but not
the model's refusals, so the funnel could not say *why* 19 claims went untested. V2 now
declares that (architecture.md "A refusal is a result"), and the funnel reads it.
