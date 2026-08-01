# Refactor work order — for an external coding agent

Five work packages, each one PR, in this order. Scope decided by the owner
2026-08-01 from `docs/draft-thoughts/code-structure-and-testing-recommendations.md`
(accepted: C, D, F-half, G, B · deferred: A, until the GUI milestone defines
its shape · rejected: generating the architecture stage table, the drift test
is wanted). The whole order must land **before M5 starts** — M5 builds new
report sections and must build them into the new structure, not the old one.

## Hard rules — every work package, no exceptions

1. **The full suite passes** (`cd src && python -m pytest -q`, currently 457).
   Never delete or weaken a test to get green. If a pinned wording or a
   pinned number blocks you, **stop and report** — the pins are the product's
   voice and someone decided them.
2. **Prompt bytes are frozen.** No edit to any prompt or model-facing input
   under `src/before_we_ai/llm/`, and every file under
   `src/tests/fixtures/llm/` stays byte-identical. The drift guard
   (`tests/corpus_driven/test_llm_offline_corpus.py::test_fixtures_match_current_inputs`)
   is the proof; if it goes red, the change is wrong.
3. **Wording is owned.** Derived sentences (verdicts, `because` texts,
   treated-as lines), glossary terms, walkthrough prose printed by
   `validation/scripts/_steps.py`, and everything in `docs/spec/` are
   untouchable. Refactors move sentences, never reword them.
4. **No new runtime dependencies.** `jinja2` is already declared and may be
   used for templates. Nothing else without owner approval.
5. **English only**, matching the surrounding comment density and idiom.
6. One PR per work package. PR description states which acceptance checks
   ran and their results.

After each PR the owner runs `/code-review ultra <PR#>` and re-runs the
offline walkthrough (`validation/scripts/reset.sh`, then stages 0–6); the
walkthrough's printed output must be unchanged except where a package says
otherwise.

## WP1 — test lanes (recommendation C)

Markers only; zero behavior change.

- Add pytest markers `unit`, `integration`, `contract`, `acceptance` in
  `src/pyproject.toml` (`[tool.pytest.ini_options] markers`), and apply them
  per module via `pytestmark`:
  - `tests/unit/*` → `unit` (except: `test_llm_guardrail.py`,
    `test_llm_request.py`, and other fixture/prompt-facing tests → `contract`)
  - store/scan/engine round-trip tests → `integration`
  - `tests/corpus_driven/*` → `acceptance`
- Document the lanes in `meta/project-setup.md` (fast lane for edits, full
  suite as the release gate — the full suite stays the gate).

**Accept:** `pytest -m unit` runs a strict subset; full run count unchanged.

## WP2 — no live counts in durable docs (recommendation F, accepted half)

- `docs/architecture.md` currently claims "391 tests green" — already false
  (457). Replace every exact suite count in `docs/` and `README.md` with the
  command plus the gate ("run the full offline suite; all tests must pass").
- `meta/memory.md` may keep counts — it is the live-state file.
- Do **not** generate the architecture stage table from `stages.py`. The
  drift test (`tests/unit/test_stages.py`) is deliberate and stays.

**Accept:** `grep -rn "[0-9]\{3\} tests" docs/ README.md` finds nothing.

## WP3 — shared corpus construction out of tests/ (recommendation G)

`validation/scripts/_steps.py` imports `src/tests/eval/_corpus.py`: owner
validation depends on test-internal code, which is the wrong direction.

- Move the reusable project construction (`build_corpus_project`,
  `DOMAIN_GUIDE_FILE`, related constants) to `validation/support/corpus.py`.
- `tests/eval/_corpus.py` becomes a thin re-import so every existing test
  import keeps working; `_steps.py` imports the support module directly.
- `tests/eval/refresh_fixtures.py` and `seeded_recall.py` follow.
- Product code (`src/before_we_ai/`) must not import it — add a test if none
  guards that.

**Accept:** no `sys.path` insertion of `src/tests/...` left in
`validation/scripts/`; suite green; walkthrough output unchanged.

## WP4 — capability boundary instead of source inspection (recommendation D)

`tests/unit/test_llm_guardrail.py` greps module source and counts
`EvidenceRecord(` constructors. Too brittle (an extraction breaks it) and too
weak (a helper that writes evidence escapes it). Replace text with capability.

- New `src/before_we_ai/store/proposals.py`: class `ProposalStore` wrapping a
  `ProjectStore`, exposing **reads** plus exactly: `save_claim`, `add_claim`,
  `save_check_plan`, `save_question`, `find_question`, `save_request`,
  `save_required_knowledge`, and `declare(claim_id, payload)` — which
  constructs only `EvidenceType.DECLARATION` with `actor=Actor.SYSTEM`
  (v2_bind's one legitimate write; keep its exact payload shape). No
  `add_evidence`, no `mark_evidence_stale` on the facade.
- LLM contract entry points (`hypothesize`, `propose_mappings`, `plan_checks`,
  `ask`) accept `ProjectStore` as today but immediately wrap:
  `store = ProposalStore(store)` — internal code uses only the facade.
- Rewrite the guardrail test as behavior: run the offline corpus pipeline
  through stage 3 and assert the evidence written is exactly the SYSTEM
  declarations (no CHECK_RESULT/CONFIRMATION/TESTIMONIAL/DOCUMENT_ANCHOR
  authored during LLM stages); assert `ProposalStore` has no evidence-writing
  attribute. **Write the new test first, watch it pass, then delete the
  source-inspection tests** — never a moment without the guarantee.

**Accept:** `grep -rn "add_evidence\|attach_evidence" src/before_we_ai/llm/`
finds nothing; False-Promotion tests untouched and green.

## WP5 — report projection out of the renderer (recommendation B)

The big one: `src/readiness_report/render.py` is 2,824 lines doing
projection, wording and HTML at once. Three phases, **each its own PR**.

**WP5a — extract the view model.** New `src/readiness_report/projection.py`:
`build_view_model(store, root, config) -> ReportViewModel` — frozen
dataclasses (`StageView`, `RequestView`, `ElectionView`, `QuestionView`,
`ReadinessView`, `ClaimView`, …) holding everything the page shows,
presentation-ready, including the derived sentences (wording moves, verbatim
— it is produced by evaluate/semantics and passes through). `render.py` keeps
every HTML string but reads only the view model — no `ProjectStore`, no
`evaluate_request`, no `resolve_status` imports left in it.
*Accept: all existing report tests pass **unmodified**. That is the proof the
extraction preserved behavior — do not touch test assertions in this phase.*

**WP5b — retarget the semantic tests.** Report tests asserting *facts*
(counts, verdicts, grounds, which items appear) move to view-model
assertions; keep a deliberately small presentation suite on the HTML: every
section renders, anchors resolve, escaping, self-contained (no external
URLs), the three-voices attributions, verdict headline wording.
*Accept: suite green; the HTML suite is a named small set; no fact is tested
only through HTML anymore.*

**WP5c — templates as resources.** Move HTML structure to jinja2 templates
under `src/readiness_report/templates/` (package-data), CSS/JS as resources,
embedded at render time; output stays one self-contained file.
*Accept: rendered walkthrough report visually unchanged (owner spot-check);
`render.py` shrinks to orchestration + escaping helpers.*

## Out of scope — do not touch

- Recommendation A (application/pipeline layer): **deferred** until the GUI
  milestone defines its shape. Do not add it, even partially.
- `validation/scripts/_steps.py` printed prose, `docs/spec/`, `glossary.py`,
  prompts, fixtures, corpus data.
- Anything M5: documents, V3, answer operations.
