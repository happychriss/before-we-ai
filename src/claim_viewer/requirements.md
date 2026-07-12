# Claim Viewer — Requirements

## Purpose

A read-only, click-through HTML viewer for validators/testers of the
`before_we_ai` epistemic core. It starts at a claim and lets a human walk
outward from there — evidence, sources, lineage, and the questions that
depend on it — without hand-reading YAML files in `claims/`, `evidence/`,
etc.

## Context / why this exists

- `before_we_ai/model` + `before_we_ai/store` (M1) are built. Another agent
  is building M2 (ingestion & profiling) concurrently, in the **same
  working tree** (`/workspace/src` is a single git repo, no worktree
  isolation between agents).
- This tool must be **strictly additive and read-only**. It must not touch
  `before_we_ai/model/`, `before_we_ai/store/`, or the persisted project
  YAML schema — no new fields (specifically: do **not** add a `probe_id`
  to `EvidenceRecord`, even though it would make probe→evidence tracing
  cleaner; that schema decision is deliberately deferred to avoid
  colliding with the M2 work in progress).
- Motivation: a validator currently has no way to see *why* a claim landed
  at its status short of reading raw YAML and re-deriving the logic in
  `before_we_ai/model/transitions.py` by hand. This tool exists to make
  that trail visible and clickable — useful for validating M1's own
  acceptance bar (promotion paths, conflict→unresolved) and increasingly
  necessary from M2 onward as real data and probes start producing claims.

## Non-goals

- No editing or mutation of claims, evidence, sources, or questions —
  display only.
- No changes to `before_we_ai/model` or `before_we_ai/store` — treat
  `before_we_ai.store.repository.ProjectStore` as a frozen, stable read
  API for this task. Do not call any `save_*` / `add_*` /
  `mark_*_stale` method.
- No new persisted fields or schema changes of any kind.
- No live-server requirement — prefer static HTML generation so the
  result has no runtime dependency beyond a browser.
- Not a Probe browser. `Probe` objects are not currently persisted by
  `ProjectStore` (no `probes/` directory, no `ProjectStore.probes`).
  Where evidence is a probe result, render what's actually on the
  `EvidenceRecord` (type, verdict, population, exception_count,
  exception_samples, payload) — do not assume or fabricate a link to a
  `Probe` record.

## Users

Testers/validators of the `before_we_ai` epistemic core, working through
it milestone by milestone (M1, M2, M3, ...). They want to click into one
claim and see everything about it in a browser, not a terminal.

## Functional requirements

### 1. Data source

- Reads an existing `before_we_ai` project directory via
  `before_we_ai.store.repository.ProjectStore(root)`.
- Project root path is a script argument.
- Uses only the store's existing load + convenience methods (e.g.
  `evidence_for`) — read-only.

### 2. Entry point / navigation

- Landing page: list of all claims, each showing short id, one-line
  `statement`, and a status badge. Searchable/filterable by status,
  predicate name, or free text over `statement`.
- Clicking a claim opens its detail page.

### 3. Claim detail page

For a given claim, show:

- **Core fields**: id, statement, status (color-coded badge, see below),
  created_by, created_at, predicate (name + params), scope
  (entity/period/segment), validity (valid_from/valid_to),
  open_assumptions.
- **Subtype fields** when applicable: `ConceptClaim` (term, definition),
  `RoleBindingClaim` (role, binding).
- **Evidence trail** — every record in `evidence_ids`, rendered by type:
  - `probe_result`: verdict (pass/fail/inconclusive, color-coded),
    population, exception_count, exception_rate, exception_samples
    (table), result_ref, stale flag, source_fingerprints.
  - `confirmation`: scope, whether it satisfies the mirror-loop (explicit
    scope required on testimonial claims), actor, stale.
  - `testimonial`: verbatim statement, actor, stale.
  - `document_anchor` / `declaration`: whatever fields are populated
    (payload, statement).
  - The trail should make the claim's current status legible without the
    reader re-deriving `resolve_status`'s logic by hand — e.g. a
    probe-fail alongside a probe-pass/confirmation/testimonial is what
    forces `unresolved`; surface that plainly (either compute and state
    the rationale, or make the relevant records visually stand out
    together).
- **Sources**: resolve `source_ids` to `Source` objects (name, kind,
  location); also surface sources implied indirectly via each evidence
  record's `source_fingerprints`.
- **Lineage**:
  - `depends_on` → clickable links to prerequisite claims, showing each
    one's current status inline (this is what gates probe execution).
  - `derived_from` / `derived_from_evidence` → link to the parent claim
    and highlight which evidence record on the parent triggered the
    escalation.
  - Reverse links: claims that list *this* claim in their `depends_on` or
    `derived_from` should be discoverable from here too ("what depends on
    me" / "what was escalated from me").
- **Questions**: reverse lookup — every `QuestionCard` whose `claim_ids`
  includes this claim, so a validator can see which business answers rest
  on it.

### 4. Presentation

- Static, click-able HTML — no build step required to *view* it, just
  open in a browser. Generated by a script run against a project
  directory.
- Every cross-reference (claim↔claim, claim↔evidence, claim↔source,
  claim↔question) is a real `<a href>` between generated pages — this is
  the "click-able" requirement, not one dense dump page.
- Color-code the five `ClaimStatus` values consistently; make
  `contradicted` and `unresolved` visually distinct, since those are the
  states a validator most needs to notice.
- Must render correctly for an empty project (zero claims) and for a
  freshly created claim with no evidence yet (`inferred`, no lineage).

## Acceptance

- Given any `before_we_ai` project directory (e.g. a hand-built test
  fixture, or a project populated against the M0 corpus), running the
  tool produces a set of static HTML pages where every claim, its full
  evidence list, its sources, and its dependency/derivation lineage are
  reachable by clicking through from the claim list.
- Running the tool modifies nothing under `before_we_ai/model/`,
  `before_we_ai/store/`, or the inspected project's own directory (output
  goes to a separate location, e.g. `out/`).

## Implementation notes (non-binding)

- Suggested approach: a script that instantiates `ProjectStore(root)`,
  then renders one HTML file per claim (e.g. via Jinja2 templates) plus
  an index page, writing to a separate output directory — never into the
  project directory being inspected.
- Keep this a standalone tool in its own directory with its own small
  dependency footprint. Do not add a dependency on it from
  `before_we_ai/model` or `before_we_ai/store` — the core must not know
  the viewer exists.
- If static generation proves awkward for some interaction (e.g. live
  search), a small local read-only server is an acceptable fallback, but
  it must remain strictly read-only against the store.
