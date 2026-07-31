# before-we-ai — Key Findings and Conclusions

## 1. We started with terminology and the meaning of a “role”

The initial question was how to explain the logic of the project, especially the term `role`.

The first idea was to use a theatre metaphor:

- the domain pack as the play;
- roles as characters;
- checks as scenes that must work;
- mappings as casting.

We concluded that the metaphor added another translation layer rather than making the system clearer.

The deeper problem was structural: the current role model mixes different levels.

For example:

```text
journal          business object
amount_local     field inside the journal
account          field inside the journal
period           field inside the journal
subledger_ar     another business object
```

Treating all of these as equivalent “roles” makes the model difficult to explain and limits future development.

The first conclusion was:

> Replace the metaphor with a clear process and separate business objects from their required fields.

---

## 2. We questioned whether a complete enterprise domain model is realistic

We then considered a large enterprise ERP landscape covering finance, treasury, FX, cash application, P&L, intercompany, and other processes.

The conclusion was that a complete enterprise domain model would become too complex.

A full finance model would have to capture:

- different systems and implementations;
-- legal and management reporting;
- local variations;
- historical migrations;
- policy changes;
- purpose-dependent definitions;
- organisational exceptions.

This would turn `before-we-ai` into an ontology or enterprise semantic-model programme.

The important correction was:

> The system should not model the entire enterprise domain before it can answer a useful question.

Instead, domain knowledge should be bounded by the requested use case.

---

## 3. We shifted to a question-first approach

The next idea was to begin with the report or business question.

For example:

> What is the expected cost of vessel S42?

The question defines what must be known:

- material quantities;
- applicable material prices;
- labour hours;
- labour rates;
- subcontractor treatment;
- overhead rules.

This led to a more practical process:

```text
Question
→ determine what the answer needs
→ inspect the available data
→ identify possible mappings
→ test or confirm them
→ expose what is missing
→ answer, qualify, or block
```

The question prevents the domain model from growing without limit.

---

## 4. We introduced small reusable domain foundations

The question-first approach still needs some starting knowledge.

For vessel costing, the system should already understand basic relationships such as:

```text
material cost = quantity × price
labour cost = hours × labour rate
total cost may include material, labour, subcontracting, and overhead
```

We initially called these reusable components `domain foundations` and later refined the term to `DomainGuide`.

A `DomainGuide` is not a complete company model.

It provides:

- common concepts;
- common relationships;
- known check types;
- vocabulary for inspecting the data.

The conclusion was:

> Use small, composable guides such as product structure, material costing, labour costing, or finance core rather than a broad “shipbuilding” or “finance” ontology.

---

## 5. We considered how non-technical users could contribute

A mid-sized company may have its knowledge distributed across Excel sheets and employees who cannot create YAML models or formal definitions.

We considered an AI-guided onboarding process.

The user should not be asked:

> What are the business objects in your domain?

Instead, the system should ask concrete questions:

> Does this quantity apply to one vessel or to the production batch?

> Which price is used for expected costing?

> Are these hours planned or actual?

> Does the BOM quantity already include scrap?

The AI translates these answers into structured knowledge.

The important conclusion was:

> The user teaches the system by correcting concrete interpretations, not by authoring a domain model.

---

## 6. We recognised that this was becoming a standard market pattern

At this point, the concept began to resemble existing approaches:

- AI-assisted semantic modelling;
- business glossaries;
- mapping business terms to data;
- guided data discovery;
- human confirmation;
- semantic context for AI.

We concluded that this workflow alone would not provide a strong unique selling point.

The key distinction had to be sharper.

---

## 7. We identified the real product: answer readiness

The strongest concept emerged when we stopped treating the semantic model as the final product.

The product is not simply:

> Build context and give it to AI.

It is:

> Determine whether the exact context required for a specific answer is sufficiently supported.

The system should trace the requested answer back to everything it depends on.

Example:

```text
Expected vessel cost

Material quantity
└── supported

Material price
└── confirmed

Labour hours
└── supported

Overhead rule
└── unresolved
```

The result may therefore be:

```text
Direct cost: ready

Fully loaded cost: blocked
```

This led to the central distinction:

> `before-we-ai` does not ask whether the data landscape is generally AI-ready. It checks whether this specific answer is ready.

The semantic model became supporting infrastructure.

The central product object became the readiness view.

---

## 8. We simplified the human-facing terminology

The first terminology exercise produced too many concepts.

We reduced the public explanation to a small sequence:

```text
Question
→ needs
→ candidates
→ claims
→ checks
→ evidence
→ gaps
→ answer
```

The main user-facing concepts became:

- starting knowledge;
- claim;
- evidence;
- gap;
- readiness.

Technical terms should remain available for developers, but should not dominate the product explanation.

---

## 9. We cleaned up the technical terminology

We then revisited the implementation vocabulary.

Several existing terms were accurate but difficult to remember or carried unnecessary academic weight.

The proposed changes were:

| Previous term | Revised term |
|---|---|
| `QuestionSpecification` | `AnswerRequest` |
| `AnswerRequirement` | `RequiredKnowledge` |
| `StartingModel` | `DomainGuide` |
| `RelationshipSignal` | `LinkCandidate` |
| `RoleBindingClaim` | `MappingClaim` |
| `ProbeTemplate` | `CheckDefinition` |
| `ProbeBinding` | `CheckPlan` |
| `ProbeResult` | `CheckRun` |
| `EvidenceRecord` | `Evidence` |
| `DomainQuestion` / `Fachfrage` | `ClarificationQuestion` |
| `AnswerEvidenceMap` | `ReadinessMap` |

The human question remains the **business question**.

Its structured software representation is the `AnswerRequest`.

---

## 10. We connected the terminology to the actual software flow

A definition of each class was not enough.

The missing explanation was:

- who creates it;
- what it consumes;
- what consumes it next;
- what changes because of it.

This produced the end-to-end technical sequence:

```text
Business question
→ AnswerRequest
→ RequiredKnowledge
→ DomainGuide
→ DataProfiles and LinkCandidates
→ MappingClaims
→ CheckDefinition
→ CheckPlan
→ CheckRun
→ Evidence
→ Claim status
→ ClarificationQuestion where necessary
→ more Evidence
→ ReadinessMap
→ ready, limited, or blocked
→ permitted answer
```

The most important handover was:

> A check does not directly prove a claim or create an answer.

Instead:

```text
CheckPlan
→ CheckRun
→ Evidence
→ Claim status
→ Readiness decision
```

This preserves the separation between measurement and interpretation.

---

## 11. We assessed the current unique selling point

The honest assessment was approximately **6.5 out of 10** in its current state.

The underlying concept was stronger than the current product maturity.

The project scores well on:

- relevance of the problem;
- conceptual quality;
- the distinction between proposals and evidence;
- the ability to refuse unsupported answers.

It remains weaker on:

- demonstrability;
- technical maturity;
- defensibility;
- risk of becoming too broad;
- similarity to existing semantic and governance products.

The strongest potential USP is:

> `before-we-ai` traces a business answer back to every mapping, meaning, and rule it depends on, tests what can be tested, and blocks the answer when a material dependency remains unsupported.

---

## 12. We concluded that the first product should be narrower

The recommendation was to stop expanding the general domain model and build one complete, convincing flow.

A suitable first demonstration would be:

> Can these files reliably produce actual P&L by entity and month?

The example should contain:

- one correct journal candidate;
- one attractive but wrong journal export;
- one account master;
- one sign convention;
- one policy that cannot be inferred from structure alone.

The system should:

1. identify both candidates;
2. reject or qualify the wrong one;
3. find the missing business rule;
4. ask one focused clarification;
5. create the `ReadinessMap`;
6. permit, narrow, or block the answer.

The complete synthetic finance corpus should remain as the test environment, not the first user experience.

---

## 13. We reconsidered the long-term role of deterministic checks

We questioned whether factual SQL validation would become unnecessary as AI models improve.

The revised conclusion was:

> More capable AI may generate and configure checks, but it does not remove the need for independently executable evidence.

The reason is that several distinct questions are involved:

```text
AI reasoning:
What is likely?

Deterministic check:
What happened in the data?

Authority:
What does the organisation intend?

Readiness:
Is the available support sufficient for this use?
```

An AI may generate SQL, run it, inspect exceptions, and explain the result.

However, the check should still execute independently against pinned data.

Otherwise, the same incorrect interpretation may produce:

```text
wrong assumption
→ plausible SQL
→ plausible result
→ plausible self-verification
```

The long-term product should therefore not depend on the statement:

> AI is weak, so we need SQL.

It should depend on the more durable principle:

> Capability is not authority, and plausible reasoning is not evidence.

---

## 14. We examined where trust ends

Trust does not end when the model becomes sufficiently intelligent.

It ends at a controlled boundary appropriate to the consequence of being wrong.

For exploratory analysis, visible assumptions may be sufficient.

For internal management reporting, deterministic reconciliation and approved definitions may be needed.

For statutory reporting, payments, pricing, or compliance, the process may require authoritative policies, access controls, accountable approval, and an audit trail.

The trust chain became:

```text
The model may propose.
The data may demonstrate.
A source may authorise.
A human may confirm.
The system may enforce.
The organisation accepts the remaining risk.
```

Trust is always conditional:

> Trusted to perform which task, within which scope, using which evidence, and with which consequence if wrong?

---

# Final conclusion

The project began as a system for discovering and validating domain context.

During the discussion, it became clear that this was too broad and too close to existing semantic-layer and governance products.

The stronger product is:

> **An answer-readiness control layer for enterprise AI.**

The user begins with a business question.

The system determines what must be known, proposes where that knowledge may exist, tests what can be measured, asks focused questions where organisational meaning is missing, and builds a `ReadinessMap`.

The requested answer is then:

- produced;
- produced with explicit limitations;
- or blocked.

The final product logic is:

```text
The AI proposes the path.

The Check Engine measures what happened.

Evidence changes what the system is allowed to believe.

The Readiness Evaluator decides what the system is permitted to claim.
```

The final product thesis is:

> **before-we-ai does not merely provide context to AI. It controls whether the evidence and authority behind a specific answer are sufficient for that answer to be trusted.**

The practical next step is to build one narrow end-to-end example in which the `ReadinessMap` visibly blocks or narrows a plausible but unsupported answer.
