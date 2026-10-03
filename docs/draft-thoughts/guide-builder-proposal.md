# Proposal for Review: Question- and Document-First Guide Builder

> **Status: proposal for review — 2026-08-02.** Nothing in this paper is a
> confirmed architecture decision or an implementation commitment. Confirmed
> decisions belong in `docs/architecture.md`; delivery status belongs only in
> `README.md`; live sequencing belongs in `meta/memory.md`.

## Purpose

This paper proposes a separately bounded, user-facing **Guide Builder** for
`before-we-ai`.

The Guide Builder starts with a business question and documents supplied by the
user. It reads those documents through the product's anchored document layer,
proposes abstract and reusable business knowledge, asks the user to confirm,
edit, reject, or defer each organisational proposition, and deterministically
compiles the accepted result into the existing `DomainGuide` YAML contract.

The intended product flow is:

```text
basic business question
+ user-provided documents
+ fixed, versioned finance foundation
        ↓
anchored document reading
        ↓
candidate abstract business propositions
        ↓
focused user Q&A
        ↓
validated, immutable domain-guide.yaml release
        ↓
existing request and readiness core
```

This is a pre-step to the current question/readiness flow, but it is part of the
program rather than manually prepared project setup. It is also part of the
end-to-end product test: a test that begins with a hand-authored project guide
does not test whether the program can build a trustworthy one.

The proposal assumes M5's document-measurement seam is finished and stable
before implementation begins.

---

## 1. Why This Is a Separate Component

The confirmed architecture already contains the consumer-side boundary:

```text
business question
→ answer-type classification
→ deterministic dependency expansion from DomainGuide
→ discovery, checks, clarification and readiness
```

The core is intentionally unaware of where a guide came from. A guide may be
handwritten, copied from a shipped finance foundation, or constructed by a
later Guide Builder. This gives the proposed component a narrow handover:

> The Guide Builder decides what may be proposed for the guide and records how
> it was confirmed. The current core accepts only a published `DomainGuide` and
> evaluates the landscape against it.

The separation matters for trust:

- The Guide Builder may propose and ask.
- A human may author organisational decisions.
- The deterministic compiler may validate and publish.
- The readiness core may derive and evaluate.
- No model may silently move a draft across any of those boundaries.

It also gives a practical implementation boundary. The first Guide Builder can
be a Flask application in the same Python distribution, calling Python services
directly. It does not require an internal REST API or a separate deployment.

---

## 2. Product Proposition

The first user experience should not be "write a domain guide." It should be:

1. What business question do you want to answer?
2. Which documents describe how your organisation handles it?
3. Here is what the system believes those documents imply in reusable business
   language. Is that correct, for what scope, and from when?
4. Here is the resulting answer type, the knowledge it requires, and the
   remaining limitations. Publish it?

The user confirms business meaning, not YAML syntax.

Example confirmation card:

```text
Proposed organisational rule

For completed vessel sales, revenue is recognised when the customer signs the
acceptance protocol.

Why this matters

"Revenue per ship" changes materially if invoice date, completion date or
customer acceptance is used.

Sources

- Accounting policy, page 12, paragraph 3
- Standard vessel contract, page 8, clause 7.2

Scope proposed: vessel sales
Effective from: 2025-01-01

[Confirm] [Edit and confirm] [Reject] [I don't know] [Choose another source]
```

The technical representation is produced only after that interaction.

---

## 3. Documents Are First-Class Input

The project guide comes **after** the initial document intake. User documents
are not merely evidence used after a guide already exists; they are an input to
the process that proposes the project-specific part of the guide.

The sequence is therefore:

```text
question + documents
→ deterministic extraction and anchors
→ model interpretation
→ abstract propositions
→ human decisions
→ guide compilation
```

This does not mean that every sentence or number in a document becomes guide
content. The Guide Builder must route extracted material according to what kind
of knowledge it is.

| Material found in a document | Canonical destination |
|---|---|
| Stable business vocabulary and object meaning | Domain guide entry |
| How an object or field is settled or which source is authoritative | Domain guide entry, after human confirmation |
| What a family of answers depends on | Answer type in the domain guide |
| A reusable organisational policy value | Scoped claim and confirmation; the answer type may name it as a required rule |
| A period-specific amount, transaction or project fact | Data or document evidence, never the guide |
| The fact that a user accepted an abstraction | Append-only Guide Builder decision log |
| The original words and location | Document index and anchor |

This routing preserves "one fact, one home." In particular, a confirmed policy
must not be copied as both a guide definition and an independent claim. The guide
may state that a revenue-recognition policy is required; the scoped confirmed
claim states what that policy is.

### 3.1 Anchored abstraction

Every document-derived proposition must retain a path back to the exact source:

```text
abstract proposition
→ document fingerprint
→ page/sheet/cell or chunk
→ exact quotation or observed value
→ user decision
```

The user is confirming the abstraction, not merely agreeing that the quoted
words appear in the document.

For example, the sentence "all engineering-office hours are allocated monthly
to active builds" may support the proposed abstraction "allocated engineering
overhead is included in vessel construction cost." Those are not the same
statement. The second is a business interpretation and needs a human decision.

### 3.2 Conflicting documents

A conflict must create a question, never a silent source choice. The Builder may
ask:

- Which document is authoritative?
- Are the documents scoped to different entities, products or periods?
- Did the policy change, and on what date?
- Is one document an informal description rather than an approved policy?

Filename recency, document tone, model confidence, or the number of documents
supporting one side cannot settle organisational authority.

### 3.3 Question-first bounding

The initial business question bounds what the Builder tries to learn. Without
that boundary, uploading ten documents invites an unreviewable enterprise
ontology.

For "What does it cost to build a vessel?", relevant abstractions may include
cost categories, project-to-vessel identity, allocation policy, intercompany
treatment, currency, actual-versus-forecast meaning and authoritative sources.
An unrelated travel policy should not become part of the draft merely because
it was uploaded.

Later business questions may open a revision job and extend the published guide.

---

## 4. The Fixed Finance Foundation

The Builder does not begin from model memory alone. It begins from a fixed,
versioned foundation delivered with the product.

The current repository already contains part of this foundation:

- the shipped finance guide data in `src/before_we_ai/domains/finance.yaml`;
- executable finance laws in the check registry;
- the domain-guide coherence lint;
- answer-type and request contracts;
- document extraction and anchoring primitives;
- model-call logging and offline fixtures.

A complete Guide Builder foundation should be packaged and versioned as:

```text
foundation manifest
+ curated finance guide seed
+ available-law catalogue
+ fixed explanatory finance documents
+ starter answer types
+ authoring questionnaire and review rubric
+ provenance and release fingerprints
```

The explanatory documents do not become a second implementation of the laws.
They explain concepts and supply context. The check registry remains the one
home of executable laws, and the guide may reference only laws the core
actually exposes.

The foundation version is recorded on every Guide Builder job and release so a
later foundation change can be distinguished from a user-document change.

---

## 5. Trust and Authority Model

The Guide Builder has four relevant voices.

| Voice | May do | May not do |
|---|---|---|
| Shipped foundation | Supply curated generic vocabulary, laws and starter answer types | Assert customer-specific organisational choices |
| LLM | Extract, abstract, propose, find conflicts, draft questions, perform advisory review | Confirm organisational knowledge, publish a guide, create promoting evidence |
| Human user | Confirm, edit, reject, scope and supersede organisational propositions | Make invalid guide references load successfully |
| Deterministic compiler/core | Validate shapes and references, compile YAML, fingerprint releases, calculate impact | Decide ambiguous business meaning |

Existing provenance values remain useful:

```text
drafted-by-ai
confirmed-by-human
```

The current schema carries provenance on objects and fields. Before Guide
Builder publication, equivalent provenance is also needed for answer types and
their individual requirements; otherwise the most trust-critical list has no
entry-level authorship record.

### 5.1 New laws

The Builder may identify that a new invariant would be useful. It may not
generate a law implementation and activate it through normal user Q&A.

A proposed law that is absent from the registry becomes an explicit gap. Adding
it requires a developer-reviewed `CheckDefinition`, a fixture where it holds, a
fixture where it fails, and the normal acceptance review. Until then, an object
cannot declare that unavailable law as its settlement path.

---

## 6. Output and Handover Contract

The canonical core input remains YAML, not model-generated prose and not XML.

The Guide Builder produces a release directory:

```text
guides/<guide-id>/<release>/
  domain-guide.yaml
  manifest.json
  decisions.jsonl
```

### 6.1 `domain-guide.yaml`

This file uses the existing `DomainGuide` shape:

```yaml
domain: finance
objects:
  vessel_project:
    definition: >-
      A build project attributable to one vessel, carrying the costs incurred
      in constructing that vessel.
    decided_by: clarification
    provenance: confirmed-by-human
    fields:
      vessel_id:
        definition: >-
          The stable vessel identifier to which the build project belongs.
        decided_by: clarification
        provenance: confirmed-by-human

answer_types:
  vessel_build_cost:
    definition: >-
      The cost incurred or expected to construct a vessel, under the selected
      costing basis and scope.
    requires:
      - object: vessel_project
        why: >-
          Costs must be attributed to the correct vessel build project.
      - rule: vessel construction cost inclusion policy
        why: >-
          Materials, labour, subcontracting and allocated overhead cannot be
          included or excluded from layout alone.
```

The example is illustrative, not a proposed final vessel guide.

The current `DomainGuide` has `extra="forbid"`, so release metadata must remain
outside this YAML unless the canonical schema is deliberately evolved.

### 6.2 `manifest.json`

The manifest should contain at least:

```text
format version
guide id and immutable release id
parent release, if any
status: published or superseded
foundation id, version and fingerprint
document fingerprints
guide fingerprint
semantic component fingerprints
created/published timestamps and actors
open limitations
decision-log reference
model-call-log references
```

### 6.3 `decisions.jsonl`

Each line is an append-only act over a stable proposition identity. It records
the proposition the user saw, its anchors, the decision, scope, actor, time and
draft/foundation version. Storing only the question text and "yes" would be
insufficient because the meaning of the proposition may change later.

### 6.4 Publication boundary

Drafts must never be pointed to by `llm.domain_guide_file`. Publication is an
explicit, atomic operation:

1. Compile into a temporary release directory.
2. Validate through the canonical `DomainGuide` model and law registry.
3. Compute fingerprints and a semantic diff.
4. Show the user the guide, limitations and impact.
5. Record explicit publication confirmation.
6. Move the release atomically to its immutable location.
7. Update the project configuration to the published YAML.
8. Load that exact file and hand the resulting guide to the existing core.

The readiness core does not import Guide Builder code.

---

## 7. User-Facing Job

A Guide Builder session is a persistent, resumable job rather than one long
model call.

Suggested states:

```text
created
→ foundation_selected
→ documents_indexed
→ drafting
→ awaiting_answers
→ ready_for_review
→ validated
→ published
→ superseded
```

Suggested screens:

1. **Start** — project, foundational pack and first business question.
2. **Documents** — upload/select documents and review what was successfully
   read.
3. **Proposed understanding** — answer type, objects, dependencies, candidate
   policies, conflicts and gaps.
4. **Q&A** — one focused decision card at a time with its reason and anchors.
5. **Guide review** — business view and detailed validation view.
6. **Publish** — final diff, limitations, affected prior requests and explicit
   activation.
7. **Continue** — hand over to the existing readiness flow.

The detailed validation view is necessary for owner testing. It should expose
stable IDs, object/field hierarchy, answer-type dependencies, provenance,
anchors, law bindings and discarded proposals. The end-user view should show
the same decisions in business language without requiring them to understand
the YAML schema.

"I don't know" is a real state. It must leave a visible open proposition or
limitation and must not trigger an endless rephrasing loop.

---

## 8. Flask and Direct Python Calls

The first application can be one Python deployment:

```text
browser
→ Flask route
→ GuideBuilderService method
→ repository / document seam / LLM contract / compiler
→ server-rendered response
```

There is no internal REST API. Flask is the user interface and calls typed
Python services directly.

Recommended package boundary:

```text
src/guide_builder/
  models.py
  repository.py
  service.py
  foundations.py
  documents.py
  llm_contracts.py
  questions.py
  compiler.py
  validation.py
  publication.py
  impact.py
  web/
    app.py
    routes.py
    forms.py
    viewmodels.py
    templates/
    static/
```

`guide_builder` may import stable seams from `before_we_ai`; the core must not
import `guide_builder`.

Routes are deliberately thin. They read forms, invoke a service method and
render a view model. They do not build prompts, call vendor SDKs, interpret
provenance, write YAML or decide whether publication is permitted.

The job repository must survive Flask restarts. Flask session state is not a
canonical store. Long model/document operations can begin synchronously for the
first vertical slice; if measured latency is unsuitable, a persisted worker may
call the same Python service without adding a REST boundary.

Upload handling must include size limits, extension and MIME checks, generated
safe filenames, duplicate fingerprints, explicit project roots and no
user-controlled arbitrary filesystem paths.

---

## 9. LLM Contracts

The LLM must return typed JSON proposals. It never returns the final YAML.

Three Guide Builder contracts are proposed.

### 9.1 `guide_propose`

Inputs:

```text
business question
+ selected foundation entries and available laws
+ anchored document passages
+ bounded workbook observations/data profiles
+ existing published guide, when revising
```

Outputs:

```text
candidate objects and fields
candidate answer types and requirements
candidate organisational propositions
conflicts
missing information
proposed confirmation questions
source anchor ids
```

Semantic validation rejects unresolvable anchors, unknown guide references,
mis-kinded entries and unavailable settlement laws.

### 9.2 `guide_revise`

Inputs are the current draft plus new append-only user decisions. The output is
a typed patch over stable proposition IDs, not a complete rewrite. A complete
rewrite after every answer could perturb previously accepted content without
the user noticing.

### 9.3 `guide_review`

An advisory adversarial pass looks for:

- likely missing dependencies;
- document conflicts not yet surfaced;
- customer-specific leakage into generic definitions;
- duplicate or overlapping concepts;
- unavailable laws;
- too-loose definitions;
- unconfirmed organisational bindings;
- period-specific facts incorrectly proposed as guide content.

This review can add warnings and questions. It is non-trust-bearing and cannot
confirm, publish or promote anything.

### 9.4 Retrieval before a guide exists

The current V3 document interpretation asks which open rule items of an
existing guide a document might settle. Guide Builder runs before that guide
exists, so it must not call V3 as if the guide already existed.

It should reuse the M5 measurement seam—file reading, deterministic chunks,
anchors, fingerprints and retrieval—but use the initial business question and
foundation vocabulary to bound passage selection. This is a new interpretation
contract over an existing measurement layer.

PDFs can retain page/chunk anchors. XLSX knowledge requires sheet/cell or range
anchors. Large transaction sheets should be profiled and sampled in a bounded,
visible way rather than sent in full. DOCX and further formats remain separate
scope decisions.

---

## 10. Multi-Vendor LLM Connection

The current implementation has the correct starting seam:
`LLMClient.complete(...)` is implemented by `AnthropicClient` and the offline
fixture client. Configuration currently permits only Anthropic, and the
repository's configured defaults use:

- `claude-opus-4-8` for frontier contracts;
- `claude-sonnet-5` for the mid-tier check-binding contract.

The first Guide Builder vertical slice should preserve the current Anthropic
client and use the configured Claude frontier tier. Multi-vendor support should
extend the existing seam rather than add an orchestration framework.

### 10.1 Proposed configuration direction

```yaml
llm:
  providers:
    anthropic:
      api_key_env: ANTHROPIC_API_KEY
    openai:
      api_key_env: OPENAI_API_KEY

  contracts:
    v1_hypotheses:
      provider: anthropic
      model: claude-opus-4-8
    guide_propose:
      provider: anthropic
      model: claude-opus-4-8
    guide_revise:
      provider: anthropic
      model: claude-opus-4-8
    guide_review:
      provider: anthropic
      model: claude-opus-4-8
```

The existing `provider:` plus `models:` form should remain readable during a
bounded migration. Environment variables remain the only source of API keys.

Two real vendors do not justify a plugin framework. An explicit registry is
enough:

```text
anthropic → AnthropicClient
openai    → OpenAIClient
stub      → StubClient
```

### 10.2 Provider-neutral contract

Normalize at least:

```text
completion text
requested and returned model identity
input/output token usage
duration
finish reason
transport/rate-limit error category
attempt count
provider name
```

Prompts and Pydantic response schemas remain provider-neutral. Vendor-specific
structured-output or tool features may be added only when the validated result
has identical semantics and offline replay remains possible.

### 10.3 No silent fallback

Automatic cross-vendor fallback is unsafe for an auditable authoring job. If a
Claude call fails, silently completing the same draft with another vendor makes
the provenance and repeatability unclear. A user may explicitly retry with
another configured provider; the job records the provider change and starts a
new model attempt or draft revision.

The user must also be told which provider will receive which document passages.
A project configured for one provider must not send its documents to another
provider merely because the first is unavailable.

### 10.4 Testing vendors

Exact prose equality across models is neither expected nor useful. The shared
contract tests assert outcome invariants:

- typed output validates;
- anchors resolve;
- organisational propositions remain unconfirmed;
- conflicts remain visible;
- no vendor can publish YAML;
- the deterministic compiler produces a guide accepted by the same core;
- provider, model, prompt/input hashes and usage are logged.

Claude remains the first fully recorded and accepted path. The second provider
proves that the seam is real rather than creating a requirement that every
provider be used in production.

---

## 11. Guide Revision and Feedback Loops

Two loops are useful and must remain distinct.

### 11.1 Authoring loop

```text
draft
→ identify unresolved propositions
→ ask user
→ append decision
→ patch affected draft entries
→ validate
→ repeat until publishable or explicitly limited
```

### 11.2 Runtime improvement loop

The core may later discover a reusable guide problem:

- no answer type matches a recurring question;
- the same per-question dependency is repeatedly added;
- the same dependency is repeatedly waived;
- a role cannot be settled;
- users regularly reject one classification;
- a clarification reveals a reusable organisational policy.

The core should emit a `GuideDiagnostic`. It must not edit the active guide.

```text
GuideDiagnostic
→ user chooses Improve Guide
→ new Builder job from published release
→ Q&A and review
→ immutable next release
→ impact calculation
→ affected readiness maps are recomputed
```

Not every runtime clarification belongs in the guide. A one-period missing
invoice is request-specific; the organisation's revenue-recognition event is
reusable guide or policy knowledge.

---

## 12. What Happens When a Guide Changes

The current core fingerprints the whole guide. `RequiredKnowledge` is derived
again on every read. Only the human confirmation that says "this classification
and list are complete" lapses when the fingerprint changes; item-specific
waivers, additions and links remain applicable when their referenced item still
exists. A removed answer type blocks its old requests until reclassification.

This is safe but broad: a wording change anywhere in the guide lapses every
confirmation taken against the prior file.

The initial Builder may preserve that conservative behavior. Before guide
revision becomes common, publication should calculate a semantic impact report
using stable IDs and component fingerprints.

| Change | Proposed impact |
|---|---|
| Formatting/order only | No semantic invalidation after canonical hashing exists |
| Answer-type dependency changed | Lapse confirmations for requests using that answer type |
| Answer-type definition materially changed | Reclassify affected requests |
| Unrelated answer type changed | Leave other requests valid |
| Object/field definition or settlement path changed | Re-evaluate affected mappings and readiness |
| Law implementation/version changed | Mark affected check evidence stale and rerun |
| Entry renamed/deleted | Explicit migration or block; never silently reinterpret |
| Organisational policy changed | Supersede the prior claim and recalculate affected requests |

`AnswerRequest` currently stores the answer-type name but not the guide revision
against which the model classified it. The Builder lifecycle makes this gap
material. A future `classified_against` or answer-type semantic fingerprint is
needed to identify unconfirmed classifications affected by a definition change.

Published releases remain readable. A past answer is not deleted; it is labelled
with the guide, data and evidence versions against which it was produced and may
become stale or superseded when an affected input changes.

---

## 13. Proposed Build Plan

No build should begin until the decisions in section 16 are reviewed.

### GB0 — Freeze the contracts

Define and test the Builder records, job states, decision semantics, publication
manifest, stable identities and the exact handover to `DomainGuide`.

**Exit:** the lifecycle can be exercised in memory without Flask or an LLM.

### GB1 — Generalise the LLM connection

Retain `LLMClient`, `AnthropicClient`, `StubClient`, retry behavior and call
logging. Add per-contract provider/model routing, a second explicit provider
adapter, normalized transport results and backward-compatible configuration.

**Exit:** one small typed contract passes through current Claude, the second
provider and offline fixtures without changing the existing Claude path.

### GB2 — Job repository and application service

Implement persistent jobs, document references, proposition revisions,
append-only decisions and the `GuideBuilderService` direct-Python seam.

**Exit:** jobs survive process restart and reject illegal transitions.

### GB3 — Question and document intake

Build project/foundation selection, basic question capture, safe upload,
fingerprinting and reuse of M5 document measurement. Add XLSX knowledge anchors
or explicitly restrict the first slice if M5 does not provide them.

**Exit:** every passage or workbook observation given to a model has a stable,
verifiable anchor and visible narrowing notices.

### GB4 — Typed Guide Builder LLM contracts

Implement `guide_propose`, patch-based `guide_revise` and non-trust-bearing
`guide_review`, with semantic checks and recorded offline fixtures.

**Exit:** model output can create only candidate propositions and questions;
unanchored or incoherent proposals are refused visibly.

### GB5 — Confirmation Q&A

Implement confirm, edit-and-confirm, reject, unknown, source-authority and scope
decisions. Show anchors and impact in business language. Persist every act.

**Exit:** no document-derived organisational binding can become publishable
without a human-authored decision.

### GB6 — Deterministic compiler and publisher

Compile typed confirmed state to the existing YAML schema, validate through the
canonical core, write manifest and decision log, publish atomically, and point
the project configuration to the immutable release.

**Exit:** the current request and readiness code loads the generated guide with
no Guide Builder dependency.

### GB7 — Flask user experience

Implement server-rendered job, upload, Q&A, detailed review, validation,
publication, history and handover pages. Keep routes presentation-only and call
the application service directly.

**Exit:** the whole job can be completed after browser refresh and Flask restart.

### GB8 — Revision and impact

Implement Improve Guide, semantic diff, stable component fingerprints,
diagnostic intake, affected-request preview and explicit reclassification or
reconfirmation work queues.

**Exit:** a guide revision never silently changes the meaning or status of a
past readiness result.

### GB9 — End-to-end evaluation and hardening

Run the full flow against `corpus-vessel`: question and documents only,
foundation supplied by the product, user decisions simulated from the hidden
evaluation contract, generated guide consumed by the current core.

Add security, concurrent-publication, interrupted-job, provider-error, file
mutation and recovery tests.

**Exit:** the release gate tests the Guide Builder as part of the product, not as
handwritten test setup.

---

## 14. Testing Strategy

### 14.1 Unit

- legal and illegal job transitions;
- append-only decision replay;
- proposition identity and supersession;
- deterministic compilation;
- YAML coherence and reference validation;
- semantic diff and impact calculation;
- atomic publication;
- provider routing and legacy configuration.

### 14.2 Contract

- prompt and input hash drift for each Builder contract;
- Claude fixtures first, second-provider fixtures separately;
- malformed JSON and schema failures;
- item-scoped repair without perturbing accepted propositions;
- invented anchors and unavailable laws;
- model attempts to publish or self-confirm;
- refusal and partial-result behavior.

### 14.3 Integration

```text
upload
→ document chunks/observations
→ anchored propositions
→ decision acts
→ draft revisions
→ YAML compiler
→ core DomainGuide loader
```

### 14.4 Corpus-driven acceptance

The vessel test must not provide a handcrafted vessel guide. It supplies:

- the fixed finance foundation;
- the business questions;
- the user-visible vessel documents;
- simulated human answers held outside model-visible inputs.

The evaluator measures outcomes rather than exact transcripts:

- material confirmation areas were discovered;
- deliberate contradictions generated questions rather than guesses;
- no hidden trap or answer-key content leaked into prompts;
- transaction values did not become guide definitions;
- policies, guide entries and evidence were routed to the correct homes;
- every document-derived proposition had a valid anchor;
- organisational entries were confirmed by the simulated user;
- the YAML loaded and produced the expected downstream readiness behavior;
- removing or contradicting inputs caused visible gaps;
- equivalent input order did not change the compiled guide semantically.

### 14.5 Acceptance kit for new guide content

The existing architecture's guide acceptance kit remains necessary:

- each new law: a holds fixture and a deliberately violated fixture;
- each new role: an attractive wrong candidate that must lose election;
- coherence lint for every compiled guide.

Human confirmation protects organisational authority. It does not prove that a
too-loose executable law discriminates correctly.

---

## 15. First Release Scope

### Included

- Flask user interface with direct Python service calls;
- persistent, resumable job;
- basic question first;
- finance foundation;
- PDF upload and anchored reading;
- XLSX upload with bounded sheet/cell observations if the measurement seam is
  available;
- current Claude/Anthropic path as the default;
- one second provider adapter proving the multi-vendor seam;
- anchored abstract propositions;
- human Q&A with scope and source authority;
- deterministic `domain-guide.yaml` compilation;
- immutable publication and direct core handover;
- vessel-corpus end-to-end evaluation.

### Explicitly excluded

- internal REST API;
- automatic publication;
- silently switching LLM vendor;
- generated executable law code;
- enterprise ontology generation;
- unreviewed organisational bindings;
- automatic guide mutation by the readiness engine;
- plugin framework for providers or domains;
- treating model confidence as authority;
- embedding period-specific facts in the guide.

The first demonstrable vertical slice is intentionally narrower than the full
plan:

```text
one business question
+ two or three documents
+ finance foundation
→ Claude proposes anchored abstractions
→ user confirms them
→ deterministic YAML
→ current core loads it
```

---

## 16. Decisions Requested in Review

1. **Component boundary:** approve Guide Builder as a separate top-level Python
   package whose dependency on the current core is one-way?
2. **Canonical output:** approve `domain-guide.yaml` as the only core guide
   input, with manifest and decision log as sidecar audit artifacts?
3. **Knowledge routing:** approve the distinction between guide vocabulary and
   dependencies, scoped confirmed policy claims, and period-specific evidence?
4. **Publication:** must all document-derived organisational entries be
   human-confirmed before publication, or may a published release carry
   explicitly provisional organisational entries?
5. **Foundation:** what exact curated finance documents join the existing
   finance YAML and law registry in foundation release 1?
6. **Initial formats:** are PDF and XLSX both required for the first vertical
   slice, or may XLSX knowledge extraction follow PDF?
7. **Second vendor:** approve OpenAI as the second explicit adapter used to
   prove the multi-vendor boundary, while current Claude remains the default?
8. **Provider fallback:** approve explicit user-triggered retry only, with no
   silent cross-vendor fallback?
9. **Revision behavior:** retain whole-guide confirmation lapse for the first
   release, then add component-level impact before enabling routine revisions?
10. **Identity:** add stable guide-entry and answer-type revision identities
    before the first published guide can be revised?
11. **Confirmed policies:** should Guide Builder activation also import scoped
    confirmed policy claims into the project store, or should that be a separate
    explicit onboarding step?
12. **User identity:** what authentication or actor identity is sufficient for
    a confirmation to count as human-authored in the first deployment?

---

## 17. Recommendation

Proceed with the Guide Builder as a separate Flask-facing Python component after
M5, using the existing `DomainGuide` YAML as the stable consumer contract.

Start with current Claude through the existing `LLMClient`; generalise provider
routing before writing Builder-specific calls so the new contracts do not bake
Anthropic details into their schemas. Add one second explicit adapter, not a
provider framework and not silent fallback.

Make document grounding, human confirmation and deterministic compilation the
three load-bearing boundaries:

> Documents supply anchored statements. The model proposes abstractions. The
> user authors organisational decisions. The compiler produces YAML. The core
> evaluates the published result.

The Guide Builder is ready to hand off only when that chain is visible and
auditable end to end.
