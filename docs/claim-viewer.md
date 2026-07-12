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

## Known gaps (viewer predates M3)

The viewer was specified against the M1/M2 store, when `EvidenceRecord.probe_id` and
persisted `Probe` records deliberately did not exist yet. M3 added both. The viewer
still renders only what is on the evidence record and does not link to persisted
probes (`ProjectStore.probes`, rendered SQL, tolerances). Candidate improvement for
whenever the viewer is next touched.
