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

- Claim list with status badges, filterable by status/predicate/free text.
- Claim detail: core fields, subtype fields (ConceptClaim/RoleBindingClaim), full
  evidence trail per type (probe verdicts with population/exceptions, confirmations
  incl. mirror-loop admissibility, testimonials, anchors/declarations), a plain-language
  status rationale (why `resolve_status` landed where it did), sources (direct +
  via evidence fingerprints), lineage (`depends_on`, `derived_from`, and reverse
  links), and dependent QuestionCards.
- The five statuses are color-coded; `contradicted` and `unresolved` stand out.

## Probe linking (gap closed 2026-07-12)

The viewer predated M3's persisted `Probe` records; that gap is closed. Each claim
section shows a "Probes (falsification attempts)" block — template, params, roles,
the registry's `domain` tag and default tolerances — and every probe-result
evidence record links back to the probe that produced it. Invariant probes carry
no `claim_id`; they are reached through the `probe_id` on the role claim's
evidence, so they appear on the claims they judged. Rendered SQL stays where it
lives: on the evidence payload.

## Redesign — APPROVED by the owner 2026-07-12, not yet implemented

Motivation: the viewer is technically complete but reads like an *archive dump* —
all claims stacked as full sections on one endless page, every field at equal
visual weight (a ULID as prominent as a verdict), and no view answers the
validator's first questions. The viewer is the basis of understanding and
validation, so it must become an *instrument*.

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

Explicitly NOT in scope: graph visualizations, chart libraries, multi-file
output, any external dependency. The binding constraints above all stay.

Suggested order if split: 2–4 are pure additions to the top of the current page
and deliver most of the understanding-per-pixel; 1+5 is the larger rebuild.
