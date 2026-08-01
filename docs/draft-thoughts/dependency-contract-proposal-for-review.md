# Proposal for Review: Dependency Contract Between Question Interpretation and the Readiness Engine

> **Status: reviewed and decided — 2026-08-01.** The confirmed design lives
> in `docs/architecture.md` → "Answer types — deriving the dependency list";
> the build slice and its timing in `meta/memory.md`. The six decisions:
> answer types live *inside* the domain guide (Q1) · `RequiredKnowledge`
> becomes derived, only human acts persist, each against a guide version
> (Q2) · no `criticality` field (Q4, superseded by the kind-based verdict
> rule) · no `condition:` — variants are separate answer types (Q5) ·
> unmatched questions fall back to labelled free drafting capped at
> `ready_with_limitations`; only broken contracts block (Q6/Q7) · one new
> canonical word, **answer type** (glossary `PLANNED`). This paper remains
> the option analysis (§2), the failure-behaviour rationale (§8) and the
> Guide-Builder outlook (§§3, 10).

## Purpose

This document summarizes a design discussion about a trust-critical weakness in `before-we-ai` and proposes a bounded architectural change for review.

The central question is:

> How can the system avoid silently under-listing the knowledge dependencies required for a business answer?

The proposal is not to build the full guide-construction machinery now. It is to introduce a stable dependency contract as an interface between question interpretation and the existing readiness engine.

Repository reviewed:

- `https://github.com/happychriss/before-we-ai`
- `src/before_we_ai/llm/v4_request.py`
- `docs/architecture.md`
- `docs/before-ai-concept.md`

---

## 1. Current Trust Problem

The readiness verdict is only meaningful if two artifacts are sufficiently complete:

1. The domain guide.
2. The per-question `RequiredKnowledge` list.

Both are currently influenced by an LLM.

The dangerous failure mode is under-listing. If the LLM omits a material dependency, that dependency never enters the readiness process. Nobody can reject, waive, test, or clarify an item that was never listed.

The current request contract in `src/before_we_ai/llm/v4_request.py` performs this flow:

```text
Business question
+ DomainGuide
        ↓ LLM
AnswerRequest
+ RequiredKnowledge
        ↓
existing discovery, checks, evidence, clarification and readiness
```

The code validates individual proposed knowledge items against the guide and skips invalid items. However, it cannot detect a valid but incomplete list.

This means the current engine can rigorously assess only the dependencies it was given.

---

## 2. Options Discussed

### A. Human confirmation as the minimum control

After the dependency list has been drafted, a human answers:

> Does the answer depend on anything not listed here?

This can use the existing clarification machinery and create an auditable confirmation with user, timestamp and guide version.

This is immediately implementable, but every question requires human review. It is the minimum control, not the scalable solution.

### B. Derive dependencies from a reviewed guide

Instead of asking the LLM to invent the full dependency list for every question, the guide defines reusable answer concepts and their dependencies.

The LLM only identifies which answer concept or guide concepts the question touches. The engine then expands the dependencies deterministically.

Example:

```yaml
answer_types:
  pnl_by_entity_and_month:
    requires:
      - journal
      - amount_local
      - reporting_period
      - legal_entity
      - account_classification
```

The trust-critical move is:

```text
LLM drafts the dependency list
```

becomes:

```text
LLM proposes the applicable answer type
Guide defines the dependencies
Engine expands them deterministically
```

This reduces the LLM claim from many individual dependencies to a smaller classification claim.

### C. Reviewed question archetypes

Recurring question families can reuse confirmed dependency templates.

A new question is compared with the nearest archetype, and only the delta requires review.

Examples:

- P&L by dimension
- Balance sheet
- Inventory valuation
- Build-readiness of a vessel
- Expected vessel cost

The archetype match must remain visible and proposed, not silently accepted.

### D. Data-side under-listing detectors

The measurement layer can flag structurally connected fields or objects that are absent from the dependency list.

Example:

> The journal contains an intercompany indicator, but no listed dependency covers elimination.

This is useful evidence, but it only detects structural relationships visible in data. Pure business rules without a corresponding field remain invisible.

### E. Adversarial second LLM pass

A second LLM asks:

> What did the first dependency list miss?

This may improve recall, but it cannot carry trust. It is an optimization, not a control.

### F. Precedent memory and measurable recall

Confirmed dependency lists become a corpus for future proposals.

Over time, the system can:

- cite precedents;
- compare new lists with historical ones;
- measure seeded recall;
- reduce review to deltas.

This is the likely enterprise scaling path.

---

## 3. Important Refinement: The Guide Does Not Need to Exist First

A realistic customer may not begin with a formal domain guide.

They may instead provide:

- business questions;
- policies;
- process descriptions;
- reporting manuals;
- Excel workbooks;
- technical documentation;
- data structures;
- local calculation logic.

A separate guide-bootstrap process can use:

```text
Business question
+ selected documents
+ data profiles
+ general LLM domain knowledge
        ↓
proposed dependency map
+ candidate rules
+ contradictions
+ clarification questions
```

The output should distinguish:

```text
Document-supported
Inferred from the available material
Expected from general domain knowledge
Unresolved
Contradicted
```

Example:

```yaml
dependency: currency_conversion

basis:
  - reporting output is defined in EUR
  - treasury policy describes monthly rates

unresolved:
  - the documents do not establish whether actual or planning rates apply

clarification:
  - which rate type governs this report?
```

This bootstrap process does not need to be implemented in the current milestone.

Its future output should conform to the same dependency contract consumed by the readiness engine.

---

## 4. Proposed Architectural Boundary

The proposal is to treat option B as a formal input contract.

### Current state

```text
Question
+ DomainGuide
        ↓ v4_request LLM
AnswerRequest
+ freely drafted RequiredKnowledge
        ↓
existing readiness engine
```

### Proposed first stage

```text
Question
+ reviewed DependencyContract
        ↓ deterministic conversion
AnswerRequest
+ RequiredKnowledge
        ↓
existing readiness engine
```

### Proposed later stage

```text
Question
+ documents
+ data profiles
+ LLM domain knowledge
+ precedents
        ↓ Guide Builder
proposed DependencyContract
        ↓ human or authoritative confirmation
confirmed DependencyContract
        ↓
existing readiness engine
```

The engine should not need to know how the contract was created.

Possible sources include:

- manually authored guide;
- finance starter pack;
- reviewed question archetype;
- document-derived local guide;
- enterprise-managed template library.

---

## 5. Example Contract

A possible minimal schema:

```yaml
id: pnl_by_entity_and_month
version: 1

question_family: pnl_by_dimension

requires:
  - concept: journal
    criticality: critical

  - concept: amount_local
    criticality: critical

  - concept: reporting_period
    criticality: critical

  - concept: legal_entity
    criticality: critical

  - concept: account_classification
    criticality: critical

  - concept: intercompany_elimination
    criticality: conditional
    condition: consolidated_scope

provenance:
  source_type: domain_guide
  source_id: finance_core
  source_version: 3

status: confirmed
```

A recursive version could also support dependencies between concepts:

```yaml
concepts:
  expected_vessel_cost:
    requires:
      - material_cost
      - labour_cost
      - subcontracting_cost
      - overhead_cost

  material_cost:
    requires:
      - bill_of_material
      - component_quantity
      - scrap_factor
      - applicable_price
      - currency_conversion
```

The engine computes the transitive closure and produces `RequiredKnowledge`.

---

## 6. Relationship to the Current Domain Guide

The current guide already contains useful structure:

- business objects;
- fields;
- slots;
- `fills`;
- `decided_by`;
- domain laws and check definitions.

This structure currently answers mainly:

> What does this object or field mean, and how can it be resolved or tested?

The proposed contract adds:

> Which objects, fields and rules are required for this answer type?

This is a new layer rather than a replacement for the existing guide.

Conceptually:

```text
Answer type
→ required business concepts
→ guide objects and fields
→ applicable laws
→ candidate mappings
→ checks
→ evidence
→ readiness
```

---

## 7. Expected Code Impact

The proposed bounded implementation should be a medium-sized change at the top of the engine, not a broad rewrite.

Likely changes:

1. Add a schema for answer types or dependency contracts.
2. Add loading and validation.
3. Add deterministic dependency expansion.
4. Validate that referenced guide concepts exist.
5. Detect cycles and unresolved references.
6. Convert the expanded result into the existing `RequiredKnowledge`.
7. Change `v4_request` so that the LLM proposes an answer type or concept set rather than freely drafting every dependency.
8. Expose the selected answer type, guide version and dependency provenance in the report.
9. Add tests for completeness behavior and hard failure on invalid contracts.

The existing downstream flow should remain largely unchanged:

```text
RequiredKnowledge
→ candidate mappings
→ check plans
→ deterministic execution
→ evidence
→ clarification
→ ReadinessMap
→ ReadinessDecision
```

---

## 8. Failure Behavior

The current `v4_request` skips invalid individual LLM proposals.

That behavior is reasonable for non-critical hypothesis generation, but dangerous for a dependency contract.

Recommended distinction:

```text
Invalid LLM proposal:
may be skipped and reported.

Invalid contract reference:
must block the request.

Cyclic dependency:
must block the request.

Question does not match a defined answer type:
must surface as blocked or require explicit fallback review.

Unconfirmed contract:
may cap the verdict at ready_with_limitations.
```

A broken dependency contract must never degrade into a shorter list.

---

## 9. Recommended Scope

The recommended first milestone is deliberately narrow.

### Build now

- one dependency-contract schema;
- one finance answer type;
- deterministic expansion;
- integration with `RequiredKnowledge`;
- clear provenance and version display;
- hard validation;
- tests;
- optional human confirmation using the existing clarification mechanism.

### Do not build now

- full document ingestion;
- semantic search across all documents;
- automatic guide creation;
- contradiction resolution workflow;
- enterprise approval workflow;
- large archetype library;
- precedent-based recall scoring.

These belong to a later Guide Builder or onboarding layer.

---

## 10. Product Interpretation

This separation creates two architectural components.

### Guide Builder

Responsible for discovering or drafting what an answer depends on.

Possible inputs:

```text
question
documents
data structures
domain knowledge
precedents
```

Output:

```text
proposed dependency contract
```

### Readiness Engine

Responsible for determining whether those dependencies are sufficiently supported.

Input:

```text
confirmed or explicitly provisional dependency contract
```

Output:

```text
ready
ready_with_limitations
blocked
```

The product boundary becomes clearer:

> The Guide Builder proposes the knowledge contract. The Readiness Engine tests whether that contract is satisfied.

---

## 11. Working Recommendation

Recommended direction:

```text
A now
B as the architectural direction
C and F as the scaling path
D as an optional detector
E as a non-trust-bearing optimization
```

More concretely:

> Introduce a validated dependency-contract interface between question interpretation and `RequiredKnowledge`. Populate it manually for one answer type now. Later build a separate guide-bootstrap process that derives proposed contracts from documents, data structures and domain knowledge.

This preserves the current engine while creating a stable seam for future automation.

---

## 12. Questions for Review

Please assess the proposal critically.

1. Is the dependency contract the correct architectural boundary, or should the dependency structure remain inside `DomainGuide`?
2. Should `RequiredKnowledge` remain a persisted object, or become a derived view of the contract and request?
3. Is classification to an answer type materially safer than direct dependency generation, or does it merely move the under-listing risk?
4. What minimum provenance is required for each dependency?
5. Should conditional dependencies be expressed in the contract, or resolved during request interpretation?
6. How should unmatched questions fail?
7. Should unconfirmed contracts cap readiness at `ready_with_limitations`, or block entirely?
8. Does the proposed change fit the current object/field/law model cleanly?
9. Which existing modules would require modification beyond `v4_request`, guide schemas, storage and reporting?
10. What tests would prove that the change reduces silent under-listing rather than only moving it?
11. Is the proposed first milestone sufficiently small?
12. What alternative design would preserve the same trust boundary with less complexity?

---

## 13. Requested Review Output

Please respond with:

1. A direct assessment: accept, modify, or reject.
2. The strongest argument against the proposal.
3. The recommended target model and ownership of each object.
4. The likely code impact by module.
5. The smallest useful implementation slice.
6. Any hidden trust or lifecycle problem not covered here.
