# Recommendation for Code Structure and Testing

> **Status: recommendation for review.**
>
> This document records an architectural assessment of why small changes in `before-we-ai` often require disproportionate implementation and validation effort. It proposes a bounded refactor. It does not change the confirmed architecture until the owner accepts the recommendations.

## Executive recommendation

The project does not need a rewrite.

The epistemic core is reasonably well separated and the main safety invariants are explicit. The largest source of development friction sits outside that core:

- the full product workflow has no single application-level interface;
- the readiness renderer also performs projection and workflow interpretation;
- broad tests bind internal code, persisted objects, report text, validation scripts and documentation together;
- the complete test suite is effectively the only supported feedback lane.

The recommendation is to introduce two explicit boundaries:

```text
Application workflow boundary
    one typed interface for running and inspecting stages

Presentation boundary
    ProjectStore -> ReportViewModel -> HTML renderer
```

The existing core, store, checks, LLM contracts and readiness rules should remain in place.

The objective is not fewer controls. The objective is to apply each control at the narrowest boundary that can prove it.

---

## 1. Current assessment

### 1.1 What is structurally sound

The project already has several strong architectural properties:

- Pydantic objects contain no IO.
- The project store owns persisted YAML objects and keeps an in-memory index.
- The check engine is distinct from LLM proposal generation.
- Readiness is derived from stored state rather than persisted as a separate verdict.
- The AI cannot author evidence that promotes a claim.
- Domain-specific knowledge enters through guides and check definitions rather than finance-specific Python logic.

These boundaries support the product thesis and should be preserved.

### 1.2 Where the friction is concentrated

The development cost is concentrated in three areas.

#### The workflow is assembled outside the product API

The seven stages are represented as data in `before_we_ai/stages.py`, but there is no product-level object that runs those stages.

The validation driver currently imports and coordinates scanning, profiling, LLM contracts, mappings, check execution, clarification and readiness directly. A future UI would have to repeat much of this knowledge or call validation-specific code.

This creates two risks:

1. Every new interface must understand internal package order and dependencies.
2. Workflow changes propagate into scripts, reports, tests and documentation because no stable orchestration contract absorbs them.

#### The renderer is also a projection layer

`src/readiness_report/render.py` does more than render HTML.

It loads the project, resolves statuses, groups elections, derives answered questions, evaluates readiness, calculates stage counts and constructs product wording. It then generates the HTML, CSS and JavaScript in the same module.

This makes the report difficult to change safely. A presentation change can touch domain interpretation. A domain change can require updates to broad HTML assertions.

The renderer is not improperly promoting claims, but it has become a second application layer.

#### Tests protect whole surfaces rather than narrow contracts

The suite contains valuable invariants, but several tests bind unrelated concerns together.

Examples include:

- stage data tested against validation filenames and a manually maintained Markdown table;
- readiness behavior tested through exact HTML phrases;
- LLM safety tested by inspecting module source text for function names and constructor counts;
- prompt and schema changes tied to recorded model fixtures and full offline pipeline expectations.

These tests make broad regression unlikely. They also make safe internal refactoring expensive.

---

## 2. The desired change boundary

A normal feature should touch only the layer that owns its behavior.

Examples:

```text
Change a readiness rule
-> readiness evaluator + focused readiness tests

Change report wording or layout
-> ReportViewModel wording or template + presentation tests

Change workflow sequencing
-> application workflow + stage contract tests

Change an LLM contract
-> contract schema + fixture/drift tests + affected integration tests

Change a persisted object
-> model + repository compatibility + affected consumers
```

The full suite remains the release gate. It stops being the first diagnostic tool for every edit.

---

## 3. Recommendation A — introduce an application workflow boundary

Add a package such as:

```text
before_we_ai/application/
    pipeline.py
    results.py
```

The name is less important than the boundary.

The application service should be the only supported interface for running the product flow.

A possible shape is:

```python
pipeline = Pipeline(project_root)

pipeline.declare_inputs(...)
pipeline.structure_request(question)
pipeline.measure()
pipeline.propose()
pipeline.test()
pipeline.apply_clarification(...)
pipeline.evaluate(request_id)
```

Each method should return a typed result describing what changed and where the resulting artifacts live.

Example:

```python
@dataclass(frozen=True)
class StageResult:
    stage: str
    created_ids: tuple[str, ...]
    skipped: tuple[StageFinding, ...]
    artifact_paths: tuple[Path, ...]
```

### Responsibilities of the application layer

It should:

- enforce valid stage prerequisites;
- call existing package functions in the correct order;
- rebuild projections or reports when required;
- return typed results for CLI, UI and validation use;
- expose product-level operations without exposing internal package topology.

It should not:

- contain domain-specific rules;
- duplicate epistemic transitions;
- own HTML rendering;
- replace the existing core or store.

### Immediate benefit

The validation scripts become thin adapters:

```text
parse arguments
-> call Pipeline method
-> print StageResult
```

A future web UI can use the same interface without importing scan, mapping, engine and readiness packages independently.

---

## 4. Recommendation B — separate report projection from rendering

Replace the current direct path:

```text
ProjectStore -> render.py -> HTML
```

with:

```text
ProjectStore
    -> build_report_view_model(...)
    -> ReportViewModel
    -> HTML template renderer
```

### ReportViewModel

The view model should contain everything the renderer needs in presentation-ready form.

Possible top-level structure:

```python
@dataclass(frozen=True)
class ReportViewModel:
    project: ProjectSummary
    stages: tuple[StageView, ...]
    requests: tuple[RequestView, ...]
    claims: tuple[ClaimView, ...]
    elections: tuple[ElectionView, ...]
    questions: tuple[QuestionView, ...]
    readiness: tuple[ReadinessView, ...]
    integrity_findings: tuple[str, ...]
```

The projection layer may derive report facts from the store. It should not produce HTML.

### Template layer

The renderer should receive a `ReportViewModel` and produce the self-contained HTML.

The final output can remain one file. Source templates, CSS and JavaScript can be separate package resources and embedded during rendering.

This keeps the current distribution model while making maintenance local.

### Wording ownership

Derived product statements such as a blocked verdict need one canonical implementation. They may live in readiness or in the report projection, depending on whether they are domain output or presentation wording.

The same sentence must not be independently recreated by the evaluator, renderer and tests.

---

## 5. Recommendation C — create explicit test lanes

Add pytest markers and documented commands.

Suggested lanes:

```bash
pytest -m unit
pytest -m "unit or integration"
pytest -m contract
pytest -m acceptance
pytest
```

### Unit lane

Purpose: fast feedback during implementation.

It should cover:

- Pydantic validation;
- pure transition and semantic functions;
- readiness item judgment;
- guide expansion and validation;
- report projection helpers;
- deterministic utility behavior.

### Integration lane

Purpose: verify package boundaries with temporary project stores.

It should cover:

- repository persistence and reload;
- scan to profile flow;
- check planning to evidence;
- application-stage behavior;
- report view-model construction.

### Contract lane

Purpose: verify model-facing contracts and drift.

It should cover:

- prompt/input hashes;
- schema validation;
- fixture replay;
- semantic rejection and retry;
- the structural rule that AI output remains proposed.

This lane may remain slower and fixture-sensitive because that cost belongs to LLM contract changes.

### Acceptance lane

Purpose: prove the product promise using the frozen corpus and presentable scenarios.

It should cover:

- false-promotion remains zero;
- seeded traps remain visible;
- the question bounds required knowledge;
- readiness permits, narrows or blocks correctly;
- the complete owner walkthrough remains executable.

Acceptance tests should not be the main place for exact HTML structure assertions.

---

## 6. Recommendation D — test behavior instead of source layout

Source inspection can be useful as a temporary containment guard, but it is brittle as a long-term architectural test.

The current LLM guardrail test searches module source for evidence-writing calls. This can fail after harmless extraction or aliasing and can miss equivalent behavior introduced through another function.

Prefer a capability boundary.

For example:

```text
LLM services receive a ProposalRepository
Checks receive an EvidenceRepository
Human confirmation receives a ConfirmationService
```

The LLM layer then has no evidence-writing capability to call.

Tests can verify behavior:

- LLM execution creates claims and plans only.
- No new promoting evidence appears after an LLM stage.
- Evidence creation requires an authorized service and actor.

The structural invariant remains stronger, while refactoring becomes safer.

---

## 7. Recommendation E — reduce HTML-string coupling

Most report tests should assert the `ReportViewModel`.

Keep a smaller presentation suite for:

- all sections render;
- links target existing anchors;
- escaping is correct;
- the file is self-contained;
- critical verdict wording is shown;
- browser-level controls have the required data attributes.

Avoid asserting large numbers of incidental phrases or HTML fragments from full project setups.

Snapshot testing may be useful for a few stable report fragments. It should not replace semantic assertions.

---

## 8. Recommendation F — generate derivative documentation

The stage spine is already canonical data.

Documentation tables, validation indexes and similar representations should be generated from it instead of manually synchronized and then tested against it.

The same principle applies to current test counts. Exact suite counts should come from CI or generated status output rather than being maintained in durable architecture prose.

A durable document should state the command and the required gate:

```text
Run the complete offline suite. All tests must pass.
```

It should not require a documentation commit each time one test is added.

---

## 9. Recommendation G — move reusable scenario construction out of tests

`validation/scripts/_steps.py` imports `tests/eval/_corpus.py` to construct the walkthrough project.

This reverses the dependency direction: owner-facing product validation depends on test-internal code.

Move reusable frozen-corpus project construction into a neutral support package, for example:

```text
before_we_ai_demo/
```

or:

```text
validation/support/
```

Both tests and validation may depend on that support code. Product runtime code should not.

---

## 10. Proposed implementation sequence

### Phase 1 — create fast test lanes

This is the lowest-risk first step.

- Add pytest markers.
- Classify the existing tests without changing behavior.
- Document fast and full commands.
- Keep CI running the complete suite.

Success condition:

> A developer can validate a local core change without running corpus acceptance and report integration tests after every edit.

### Phase 2 — add the application workflow service

- Introduce typed stage results.
- Wrap the existing functions without redesigning them.
- Convert validation scripts to call the application service.
- Add workflow contract tests.

Success condition:

> The validation walkthrough no longer knows the package-level call sequence.

### Phase 3 — extract the report view model

- Move project-to-report derivation out of `render.py`.
- Keep the existing generated HTML initially.
- Redirect semantic report tests to the view model.

Success condition:

> Readiness, elections and stage counts can be tested without parsing HTML.

### Phase 4 — split report source assets

- Move HTML structure to templates.
- Move CSS and JavaScript to package resources.
- Embed them into the final self-contained output.
- Retain a small renderer integration suite.

Success condition:

> A layout change does not require editing a large Python string or touching readiness logic.

### Phase 5 — replace brittle architecture tests

- Replace source-text inspection with capability or boundary tests.
- Generate derivative stage documentation.
- Remove manually maintained suite counts from durable docs.
- Move shared scenario construction out of `tests/`.

Success condition:

> Internal refactoring stays green when observable behavior and safety boundaries remain unchanged.

---

## 11. What should not change

The refactor should not weaken the product's controls.

The following remain non-negotiable:

- AI-created claims start as proposed.
- AI output cannot author promoting evidence.
- Check evidence remains independently executable and persisted.
- Human authority remains explicit and attributable.
- Conflicting evidence remains visible.
- Readiness remains derived from current state.
- A blocked or limited answer names the unresolved dependency.
- The frozen corpus remains an acceptance instrument rather than product logic.

---

## 12. What not to build

Do not introduce a general plugin system, event bus or service architecture merely to solve local coupling.

The project is still one Python package operating on one project directory. That is an advantage.

The recommended design remains in-process:

```text
UI / CLI / validation
    -> application service
    -> existing core packages and store
    -> report projection
    -> renderer
```

A larger architecture would increase implementation cost before the product has demonstrated a need for it.

---

## 13. Expected effect

After this refactor, changes should fall into two distinct classes.

### Ordinary implementation changes

Examples include report layout, stage summaries, CLI behavior and local projection changes.

Expected validation:

```text
focused unit tests
+ relevant integration lane
+ full suite before merge
```

### Trust-critical changes

Examples include evidence authority, status transitions, readiness logic, guide contracts and persisted epistemic objects.

Expected validation remains broad:

```text
unit and integration tests
+ contract fixtures where affected
+ frozen-corpus acceptance
+ owner-facing walkthrough
```

This distinction is the desired outcome.

The project should continue to make dangerous changes expensive. It should stop making every change equally expensive.

---

## Final recommendation

Proceed with a bounded outer-layer refactor before adding a substantial UI or expanding the document pipeline.

Start with test lanes and the application workflow boundary. These provide immediate feedback improvement and establish the interface a UI will need.

Then extract the report view model while preserving the current self-contained report output.

Do not rewrite the epistemic core. The core is not the main source of friction. The missing application and presentation boundaries are.
