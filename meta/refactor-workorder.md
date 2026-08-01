# Refactor work order — for an external coding agent

Five work packages in this order, **seven PRs** — WP5 splits into 5a/5b/5c,
each reviewed on its own because the first of them carries the whole risk. Scope decided by the owner
2026-08-01 from `docs/draft-thoughts/code-structure-and-testing-recommendations.md`
(accepted: C, D, F-half, G, B · deferred: A, until the GUI milestone defines
its shape · rejected: generating the architecture stage table, the drift test
is wanted). The whole order must land **before M5 starts** — M5 builds new
report sections and must build them into the new structure, not the old one.

## Hard rules — every work package, no exceptions

1. **The full suite passes** (`cd src && python -m pytest -q`). Run it before
   you start, put that number in the PR, and it must not go **down** — a
   package may add tests, never lose them. Never delete or weaken a test to
   get green. If a pinned wording or a pinned number blocks you, **stop and
   report** — the pins are the product's voice and someone decided them.
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

## WP1 — test lanes (recommendation C) · DONE 2026-08-01 (`5a9f590`)

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

## WP2 — no live counts in durable docs (recommendation F, half) · DONE 2026-08-01

- `docs/architecture.md` claimed "391 tests green" — false by 69. Replaced
  with the command and the gate.
- **`meta/memory.md` lost its count too**, which this order originally
  allowed. The evidence overruled it: the number went stale three times
  (391 → 397 → 460), was corrected by hand each time, and never once changed
  a decision. What stayed are the measures that *do* — False-Promotion 0,
  Seeded-Recall 14–15/25, leakage CLEAN.
- The architecture stage table is **not** generated from `stages.py`. The
  drift test (`tests/unit/test_stages.py`) is deliberate and stays: it
  stopped a wrong edit twice, which silent regeneration would not have.

**Accept:** `grep -rn "[0-9]\{3\} tests" docs/ README.md meta/` finds nothing.

## WP3 — shared corpus construction out of tests/ (rec. G) · DONE 2026-08-01

Landed as written, minus the bridge: **no collected test imported the
module**, so the re-import shim below was unnecessary and the file was moved
outright. Its only consumers were the walkthrough and the two online tools,
which are owner-facing operations themselves — it was never test-internal,
it just lived under `tests/`. The guard is `tests/unit/test_layering.py`
(parsed imports, not text).

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

## WP4 — capability boundary instead of source inspection (rec. D) · DONE 2026-08-01

Built by the external agent (`7c190b2`) plus a review follow-up
(`9cdacb3`). `ProposalStore` name-mangles the wrapped store and hands back
`MappingProxyType` views, so neither the write capability nor the read
dictionaries are reachable by an obvious refactor — both stricter than this
order asked. `__attach` is the private seam M5's `anchor()` extends.

The follow-up added the invariant next to the allow-list: the behavior test
pinned *today's* set (only SYSTEM declarations), which is the right shape but
goes red the moment V3 writes anchors, leaving the next reader nothing to say
whether widening is allowed. `test_llm_stages_author_nothing_that_could_promote`
is the assertion that survives the widening and may never be relaxed.

`tests/unit/test_llm_guardrail.py` greps module source and counts
`EvidenceRecord(` constructors. Too brittle (an extraction breaks it) and too
weak (a helper that writes evidence escapes it). Replace text with capability.

**State the invariant correctly first.** It is *the LLM layer writes no
**promoting** evidence* — not *no evidence*. `resolve_status`
(`core/transitions.py`) promotes on exactly two things: a `CHECK_RESULT`
verdict and an admissible `CONFIRMATION`; a `TESTIMONIAL` blocks a conflict.
`DECLARATION` and `DOCUMENT_ANCHOR` are read by nothing and promote nothing —
the docstring calls them weak evidence and the code agrees.

The current test's `for promoting in (...)` list wrongly includes
`DOCUMENT_ANCHOR`. Harmless today (V2 writes none), a trap tomorrow:
**M5's V3 writes document anchors — that is its job.** Carry that list into
the new behavior test verbatim and the facade forbids V3 its core
operation, after which M5 would have to weaken a safety test. Do not.

- New `src/before_we_ai/store/proposals.py`: class `ProposalStore` wrapping a
  `ProjectStore`, exposing **reads** plus exactly: `save_claim`, `add_claim`,
  `save_check_plan`, `save_question`, `find_question`, `save_request`,
  `save_required_knowledge`, and `declare(claim_id, payload)` — which
  constructs only `EvidenceType.DECLARATION` with `actor=Actor.SYSTEM`
  (v2_bind's one legitimate write; keep its exact payload shape). No
  `add_evidence`, no `mark_evidence_stale` on the facade.
- Shape it so **one more weak-evidence method can be added without reopening
  the design** — M5 adds `anchor(...)` for `DOCUMENT_ANCHOR`. Adding it must
  not require the facade to expose `add_evidence`. Do not write `anchor()`
  now: V3 does not exist, and its arguments are its own to decide.
- LLM contract entry points (`hypothesize`, `propose_mappings`, `plan_checks`,
  `ask`) accept `ProjectStore` as today but immediately wrap:
  `store = ProposalStore(store)` — internal code uses only the facade.
- Rewrite the guardrail test as behavior: run the offline corpus pipeline
  through stage 3 and assert that **no promoting evidence** was authored
  during the LLM stages — no `CHECK_RESULT`, no `CONFIRMATION`, no
  `TESTIMONIAL` — and that every record written is a SYSTEM `DECLARATION`.
  Assert `ProposalStore` exposes no `add_evidence` / `mark_evidence_stale`.
  **Write the new test first, watch it pass, then delete the
  source-inspection tests** — never a moment without the guarantee.

**Accept:** `grep -rn "add_evidence\|attach_evidence" src/before_we_ai/llm/`
finds nothing; False-Promotion tests untouched and green.

## WP5 — report projection out of the renderer (recommendation B)

The big one: `src/readiness_report/render.py` is 2,824 lines doing
projection, wording and HTML at once. Three phases, **each its own PR**.

### Pre-flight findings — read before starting (measured 2026-08-01)

**What the 2,824 lines actually are.** Only **75 lines of CSS and 9 of JS**;
`render_project` alone is **692 lines** (page skeleton + style block). The
rest is Python: projection, wording, and 181 lines of f-string HTML. So
WP5c is a *small* package — the weight is in 5a.

**Wording ownership, decided — do not re-derive it per case.** Two kinds of
sentence live in this file and they move differently:

- **Passed through from the core** — `ReadinessItem.because`,
  `ReadinessMap.reason()`, the guide's definitions. The renderer only
  escapes and places them. These stay owned by `readiness/` and `core/`;
  the projection carries them unchanged.
- **Composed in the renderer** from derived facts — `_election_outcome`
  ("Identified. The balance law passed on …"), `_render_readiness_item`,
  `_render_treated_as`, `_rationales`, the section intros. These are
  product voice with no other home. **Move them into the projection layer
  verbatim.** Not one word changes; a diff that rewords one of these
  sentences is a failed PR, however much better the new wording reads.

**One trap, and it is a real one.** `_status_rationale`
(`render.py:2674`) **restates the promotion law in prose** — "At least one
failing check is present and no competing supporting evidence remains
live", and so on, branch for branch alongside `core/transitions.py`
`resolve_status`. It is a second implementation of the status rule, in
strings, in the renderer.

It already disagrees with the law it restates: `resolve_status` counts only
**admissible** confirmations (the mirror-loop rule — confirming a
testimonial claim requires an explicit scope, `_confirmation_admissible`),
while `_status_rationale` counts every `CONFIRMATION` record and then
asserts the word "admissible" in its sentence. A claim with an inadmissible
confirmation would read: status `proposed`, trail "1 confirmation", why
"Nothing stronger than proposed evidence is live yet." Unreachable today —
no product code creates confirmation evidence — and reachable the moment M5
builds `tell`/`confirm`.

**In WP5: move it verbatim and leave a comment pointing here. Do not fix
it.** Fixing it changes rendered output, which this refactor may not do, and
the fix belongs with the milestone that makes it reachable. It is recorded
as an M5 item in `meta/memory.md`.

**Leave room for M5.** It adds a documents/anchors surface: a section for
ingested documents and, per claim, `DOCUMENT_ANCHOR` evidence cards. The
view model should take a new `*View` tuple without reshaping — do not build
them, just do not build something they cannot join.

**WP5a — extract the view model.** · DONE 2026-08-01 (`19a2c71`)

Both gates passed on an independent re-run: report tests untouched
(`git diff -- src/tests/` empty), and the rendered page byte-identical —
1,279,721 bytes, same sha256, old renderer run from a worktree at the base
commit against the same store. `projection.py` contains no `escape(`, no
`<a href`, no `store_rel`, and does not know `out_dir` exists; `render.py`
no longer imports `ProjectStore`, `evaluate_request` or `resolve_status`.
`_status_rationale` moved verbatim with the required comment — the agent
did not "fix" the defect the pre-flight had put in front of it.

Gate 2 only proves what the corpus renders, so the wordings on branches it
never reaches (`unresolved`, `business-confirmed`, `Ready.`, `Ready, with
limitations.`) were checked separately: all verbatim. Cost, measured: +34%
characters (114,355 → 154,068), of which 47 dataclasses are pure addition;
`render.py` itself fell from 2,824 to 1,719 lines.

New `src/readiness_report/projection.py`:
`build_view_model(store, root, config) -> ReportViewModel` — frozen
dataclasses (`StageView`, `RequestView`, `ElectionView`, `QuestionView`,
`ReadinessView`, `ClaimView`, …) holding everything the page shows, including
the derived sentences (wording moves verbatim — it is produced by
evaluate/semantics and passes through). `render.py` keeps every HTML string
but reads only the view model — no `ProjectStore`, no `evaluate_request`, no
`resolve_status` imports left in it.

**Where the line falls between the two** (the agent asked, and the question
was right: `build_view_model(store, root, config)` has no `out_dir`, so it
*cannot* build the YAML links `render_project` threads around today as
`store_rel`):

| projection owns | renderer owns |
|---|---|
| what is true, and the exact sentence for it | HTML, CSS, the page skeleton |
| a **reference** to an object — kind + id, e.g. `("answers", request_id)` | resolving it to an href via `_relative_prefix(root, out_dir)` |
| ordering, grouping, counts | escaping (`html.escape`) |

The reason is not tidiness. A GUI has no output directory and no relative
file paths; if the projection bakes in `../../project/answers/x.yaml` the GUI
cannot reuse it — and being the layer both consumers share is the whole
argument for extracting it. Same for escaping: a non-HTML consumer must not
be handed pre-escaped text.

**One complication, so it is not a surprise.** Some sentences embed a link
mid-sentence — `_election_outcome` returns *"**Identified.** The balance law
passed on `<a …>de_erp__gl_postings</a>"*, and `_render_readiness_item` does
the same with claim ids. For those, the projection emits the sentence's
**pieces plus the reference** and the renderer assembles. Do not simplify by
dropping the link or by moving the whole f-string across.

**Accept — two gates, and the second is the real one:**

1. All existing report tests pass **unmodified**. `git diff` on
   `src/tests/unit/test_readiness_report.py` must be **empty**. Do not touch
   a single assertion in this phase.
2. **The rendered page is byte-identical.** Rendering is deterministic *for a
   given store* — two renders of the same project produce the same 38,936
   bytes. **Building the store is not**: every walkthrough run mints fresh
   ULIDs and timestamps, which is correct behaviour and must not be
   "fixed". So build the store **once** and run both renderers against it:

   ```
   # once — this is the fixed input, do not reset it again
   cd validation && ./scripts/reset.sh && for s in 0-inputs 1-request \
     2a-measure-scan 2b-measure-matrix 3a-propose-hypotheses \
     3b-propose-mappings 3c-propose-plans 4-test 5-clarify 6-readiness; do \
     ./scripts/$s.sh >/dev/null; done

   # the new renderer, from your branch
   python -m readiness_report data/project -o /tmp/after.html

   # the old renderer, from the base commit, against that same store
   git worktree add /tmp/base <base-sha>
   PYTHONPATH=/tmp/base/src python -m readiness_report data/project \
     -o /tmp/before.html
   git worktree remove /tmp/base

   diff /tmp/before.html /tmp/after.html          # must print nothing
   ```

   A worktree rather than `git stash`: nothing uncommitted is ever at risk.
   The pipeline does not import `readiness_report`, so the store is the same
   input for both.

   Paste the `diff` output (nothing) in the PR. A test suite proves what it
   asserts; this proves everything it does not — every space, every
   attribute, every sentence.

**WP5b — retarget the semantic tests.** Report tests asserting *facts*
(counts, verdicts, grounds, which items appear) move to view-model
assertions; keep a deliberately small presentation suite on the HTML: every
section renders, anchors resolve, escaping, self-contained (no external
URLs), the three-voices attributions, verdict headline wording.
The six categories above **are the decision** — do not re-litigate which
assertions stay on the HTML, just apply the list.

**Accept — three gates, all mechanical:**

1. **Production code untouched.** `git diff -- src/readiness_report/
   src/before_we_ai/` must be **empty**. This package changes tests and
   nothing else, which is what makes byte-identical output trivially true
   rather than something to prove again.
2. **Coverage does not shrink.** The suite count must not go down, and the
   PR carries a **mapping table**: every assertion removed from the HTML
   suite, next to the view-model assertion that now carries that fact. A
   row with an empty right-hand column is a fact that stopped being tested
   — stop and report instead.
3. **The new tests can fail.** For at least three retargeted facts, show
   that breaking the projection makes them red (change a value locally, run,
   paste the failure, revert). A test that cannot fail is not a test, and an
   assertion moved onto a view model is the easiest place in this codebase
   to write one by accident.

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
