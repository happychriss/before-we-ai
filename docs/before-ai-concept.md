# before-ai — how it works, in plain language

This document walks through the whole system once, from a business question
to a defensible answer. Every concept is introduced by the problem that
forces it, then named. Behind each plain name stands exactly one code
object, shown in brackets — the same word is used everywhere: here, in the
code, in the readiness report. No synonyms (`before_we_ai/glossary.py` is the
one home of these words).

Two stages of honesty apply throughout:

- Steps marked **(built)** run today and are validated against a frozen
  test corpus.
- Steps marked **(M5)** are specified but not built yet — the document
  pipeline. This document describes them so the whole flow reads as one
  piece, and says so at each step.

---

## A user starts with a business question

> What was the group's external revenue in 2023?

Innocent-looking, and the data landscape it lands in is not: two ERP
systems (Germany and the US), a chart of accounts, Excel report exports,
open-item lists, and a folder of policy PDFs. Somewhere in there sits the
answer — and several convincing wrong answers.

The system first writes down exactly what the user wants to know, which
part of the business is in scope, and what the result should contain.

The structured software representation of the business question is called
the **answer request** [`AnswerRequest` — **built**].

For example:

```yaml
question: What was the group's external revenue in 2023?

scope:
  entities: [DE, US]
  period: 2023
  customers: external only

output:
  total_revenue
  by_entity
```

From the answer request, the system works out what must be known before it
can produce the answer. For group revenue it must know, at least:

* which table is the ledger of record (and which lookalike export is not);
* which accounts count as revenue — and which contra accounts reduce it;
* which customers are intercompany and must be excluded from "external";
* which currency rate policy converts the US figures;
* whether the two entities' books are internally consistent at all.

This required information is called the **required knowledge**
[`RequiredKnowledge` — **built**]. The answer request identifies the required
knowledge; from here on, the system hunts for exactly these items and
nothing else.

> **(built) honestly stated:** the middle of the pipeline still runs
> *bottom-up* — it scans the whole landscape and proposes everything it can
> find. What M6 added is the frame: the question decides what must be known,
> and the readiness map at the end judges only those items. An item the
> question does not depend on is not a gap.

---

## The system needs starting knowledge — but never company knowledge

To search for "the ledger of record", the system must know what a ledger
*is*. That reusable starting knowledge is called the **domain guide**
[`DomainGuide`, a curated YAML file declared as `llm.domain_guide_file` in
`before-ai.yaml`].

The domain guide names the **business objects** of the domain — the nouns
— each with one human-written definition, and the **fields** each object
carries:

```yaml
domain: finance
objects:
  journal:
    decided_by: balance
    definition: >-
      The transactional ledger of record: one row per posting line,
      carrying a signed amount and a document reference; debit and
      credit lines balance per document.
    fields:
      amount_local:
        decided_by: slot
        fills: amount
        definition: >-
          The signed posting amount in local currency on the journal —
          the column that must sum to zero per document.
      period:
        decided_by: clarification
        definition: >-
          The posting period on the journal, at fiscal-period
          granularity.
  subledger_ar:
    decided_by: subledger_equals_gl
    definition: >-
      The accounts-receivable open items ... reconcilable against the
      journal's control account.
```

Three properties are deliberate:

- **The domain guide does not describe the company's actual files.** No
  system names, no table names, no example values. It gives the system a
  vocabulary to search with, not answers to find.
- **Every entry declares how it can ever be settled** (`decided_by:`). An
  object: a domain law that can elect it, or `clarification` (no
  arithmetic can decide what a column *means* — humans decide). A field:
  `slot` — carried inside its object's law, naming which slot of it
  (`fills:`) — or `clarification`. An entry without a settlement path is
  rejected when the file loads. Silence must be a declared property,
  never an accident.
- **A field can never declare a law.** The shape does not allow it: laws
  judge objects, and a field rides its object's law. This is a fix by
  construction for a real bug — the finance guide once declared the
  posting amount as balance-decided, and the system then asked what
  domain knowledge was missing about a column its passing balance check
  had just used. What cannot be written cannot be got wrong.

The domain guide is data. The *laws* of the domain — "books balance per
document", "subledger equals general ledger", "intercompany postings
mirror" — are reviewed code [`CheckDefinition(domain="finance")` in
`checks/library.py`]. Together, guide + domain-tagged laws are the **domain
pack**: everything domain-specific, explicit and enumerable. The machine
itself is domain-agnostic — new domain, new pack, same machine.

---

## The system inspects the data — and only measures

The system loads the declared sources (`before-ai.yaml` `sources:` — a
human writes this list, the tool never invents sources) into a disposable
DuckDB catalog, and measures every column: type, row count, nulls,
distinct values, min/max, length patterns, top values.

These factual descriptions are called **data profiles** [`DataProfile`,
stored in `profiles/`]. For example:

```text
### de_erp__gl_postings.account_id
type=BIGINT class=integer rows=4020 nulls=0 distinct=38
min=1000 max=9999
```

The system also measures where values overlap between columns — 98% of
the values in one column appearing in another suggests a reference. A
possible connection discovered this way is called a **link candidate**
[the candidate matrix, `profiles/candidate_matrix.json`].

The measuring step *never judges*. Chance overlaps are deliberately kept
in the matrix (two unrelated columns can share values by coincidence —
the corpus seeds exactly this trap), and inspection creates **zero
claims**. False promotion at this stage is impossible by construction.

---

## The AI proposes — and only proposes

Now the AI joins, under a strict contract. It sees **data profiles and
link candidates only — never the raw data**. A model that never saw the
rows cannot have memorized the answers; that is what makes the honesty
measurable.

From the profiles it proposes two kinds of things:

**Proposed rules** about the landscape [a `Hypothesis` that becomes a
`Claim`]: "the document number in the report export references the general
ledger", "account_id decodes against the chart of accounts", "the two AR
tables reconcile per period". Each accepted proposal becomes a claim —
a rule with an author, an evidence list, and a status.

**Proposed mappings** [`MappingClaim`]: where the domain guide's roles may
be located in this concrete landscape.

```yaml
role: journal
binding:
  table: de_erp__gl_postings
statement: de_erp__gl_postings plays the journal role.
```

Competing mappings for the same role are *wanted* — in the test corpus,
the polished report export `buchungen_report` looks like a journal too,
and proposing both is correct. Something deterministic will decide, not
the model.

Every claim begins as **proposed** — it is not trusted because the AI
considers it plausible. There is no confidence score anywhere; the model's
reasoning is logged but never stored on the claim, so its eloquence cannot
promote anything.

---

## A proposed claim must be assessed

The system looks for an approved way to check each claim against the
actual data. A reusable description of such an assessment is called a
**check definition** [`CheckDefinition`, one entry per template in
`checks/REGISTRY` — 13 exist, each forced by a corpus case]. A check
definition describes general logic, independent of any concrete file:

```text
Check: anti_join
Expected relationship: every child value has a counterpart in the parent
```

Connecting a check definition to the actual tables and columns of one
claim is called a **check plan** [`CheckPlan`, proposed by the V2
contract, strictly validated]. The AI proposes the plan — which definition
fits, filled with which concrete columns — but it never writes SQL, and
its proposal is validated against the catalog: a hallucinated column dies
at this gate, visibly.

The AI is also allowed to answer *no*: `template: null` plus a reason,
persisted as evidence. **A refusal is a result.** Claims that no check can
ever test (what a column *means*, definitions that live in documents) are
marked as exactly that, never quietly dropped.

---

## The check runs — deterministically

The engine executes each ready check plan against the real data
[`run_check` in `engine/runner.py`]. This execution is the **check run**:
rendered SQL, population counted, exceptions counted, representative
exception samples kept, verdict derived by a fixed rule — PASS, FAIL, or
INCONCLUSIVE. No judgment ever comes from a model.

The result is stored as **evidence** [`EvidenceRecord`, append-only, in
`evidence/`]:

```text
check:      balance (finance law)
population: 4,020 posting lines
exceptions: 0
verdict:    pass
sql:        (kept verbatim on the record)
```

Evidence is never edited or deleted; the one permitted mutation is marking
a record stale when the source data changed underneath it. Five evidence
types exist: check result, document anchor, confirmation, testimonial,
declaration — and only check results and human confirmations can ever
promote a claim.

---

## Evidence changes what the system may believe

The evidence is used to reassess the claim — this is **status
resolution** [`resolve_status` in `model/transitions.py`], and it is the
epistemic heart of the machine:

- check supports the claim → **test-supported**
- check contradicts it → **contradicted**
- conflicting evidence → **unresolved** — conflict is never averaged away
- a human confirms, with explicit scope → **business-confirmed**
- nothing decisive yet → stays **proposed**

The handover is always:

```text
CheckPlan → CheckRun → Evidence → Claim status
```

A check never directly proves a mapping and never creates the answer. It
produces evidence; the evidence changes what the system is allowed to
believe. Status is *derived* from the evidence list, never hand-set — and
structurally, the AI cannot author promoting evidence (a validator in
`model/objects.py` forbids it). That is why the false-promotion rate is
zero by construction, not by luck.

In the corpus this decided the journal election: the real general ledger
passed the balance law; the pretty report export failed it and ended
**contradicted**, with the rendered SQL kept as the reason.

---

## Some knowledge no data can settle

The files may contain both a spot rate and a monthly-average rate — both
technically valid columns. No SQL decides which one *policy* mandates for
converting US revenue. The same is true for "which customers count as
external": the intercompany exclusion is a convention, not a data
property.

The system therefore asks a focused business question — a **clarification
question** [`ClarificationQuestion`, drafted automatically, stored in
`questions/`]:

> Which of the proposed candidates is the 'period'? The posting period on
> the journal, at fiscal-period granularity. No check can settle this —
> what the data means is a business fact, not an arithmetic one.

The ask comes first, then the guide's own definition of what is being
asked about, then what the machine already tried. The candidates are *not*
written into the sentence: the question card links them (`claim_ids`), and
the readiness report renders them as a list to pick from. A list of
bindings flattened into prose is the least readable form of that data —
and it duplicates links the card already carries.

The rule completed by this step: **every business object and every
clarification-decided field ends in a check verdict or a clarification
question — never in silence** [`resolve_mappings` in
`llm/domain_guide.py`]. Checked-and-lost objects, objects whose law could
never be bound, entries with no candidate at all — each becomes a question
the human can answer in one pick.

A slot field is the one entry that may stay quiet, and only for a reason
that can be shown: its object's passing law already consumed a column for
it. The elected journal's balance check ran with
`amount=amount_local_currency`, so *that* column is the posting amount —
the evidence was there all along and no one had to be asked. If the object
is unsettled, its own question carries the field; if the law passed
without consuming the slot, the field asks after all
[`settled_slots`].

A human answer is stored as new evidence, with its scope spelled out
("applies to: all entities? which period?") before it may confirm anything
— and status resolution may then mark the claim **business-confirmed**.

```text
Unresolved claim → ClarificationQuestion → human answer → Evidence
                → updated claim status
```

**(M5)** Documents join the same loop: policy PDFs are read, figures get
page-and-position anchors [document anchors] — but an anchor alone
promotes nothing, exactly like the AI's rationale.

---

## Finally: is the answer allowed? (built)

For every item of required knowledge, the system identifies the relevant
claim, its evidence, its current status, and any remaining gap. This
complete view is the **readiness map** [`ReadinessMap` — **built**]:

```text
External group revenue 2023

Ledger of record
└── MappingClaim: de_erp__gl_postings   status: test-supported

Revenue account range (incl. contra accounts)
└── ConceptClaim: 4000–4999 minus 4800–4899
    └── Evidence: policy document anchor  status: proposed (M5 pending)

Intercompany exclusion
└── No sufficiently supported rule       status: unresolved

FX conversion policy
└── ClarificationQuestion drafted        status: unresolved
```

The readiness evaluation then determines whether the requested answer is
**ready**, **ready with limitations**, or **blocked**. An answer is ready
when all material knowledge is sufficiently supported; ready-with-
limitations when a useful but explicitly narrower result can be produced;
blocked when unresolved knowledge would make the result materially
unreliable.

In the example, the honest verdict today would be:

> DE ledger revenue is supported. The *external group* revenue is blocked:
> the intercompany exclusion and the FX policy are unresolved.

The reporting step may then produce the narrower number — but it may not
present it as the full one. **The system is allowed not to know. It is not
allowed to be quiet about not knowing.**

---

## The complete flow

```text
Business question         → AnswerRequest            (built)
AnswerRequest             → RequiredKnowledge        (built)
RequiredKnowledge + DomainGuide guide the discovery  (guide: built)
Data discovery            → DataProfiles + LinkCandidates
Profiles + guide          → Claims + MappingClaims   (proposed)
Claim + CheckDefinition   → CheckPlan
CheckPlan                 → CheckRun
CheckRun                  → Evidence
Claim + Evidence          → Claim status             (derived, never set)
Undecidable knowledge     → ClarificationQuestion → human answer → Evidence
Everything                → ReadinessMap             (built)
ReadinessMap              → ready / ready with limitations / blocked (built)
```

---

## How we know it is honest — the exam came first

Before the tool existed, a frozen test corpus was built: an invented
two-country company with known answers and **32 seeded traps** — leading
zeros, recycled legacy IDs, a lookalike journal, chance value overlaps,
policy rules that live only in PDFs. Several traps are designed so the
only correct answer is "unresolved". Blind traps are held back by the
owner to test what the implementer did not anticipate.

Every run is measured against it:

- **False promotion — must be 0, always.** It is zero structurally (the
  AI cannot author promoting evidence), not empirically.
- **Seeded recall — allowed to be imperfect, reported honestly.** First
  measurement: 15 of 25 in-scope traps found; the misses cluster in rules
  that live only in documents — which is exactly why M5 is the next
  milestone (`docs/seeded-recall-m4.md`).

---

## Glossary

| plain term | meaning | in the code |
|---|---|---|
| **source** | a connected file or database; the list is written by a human | `before-ai.yaml` `sources:` |
| **data profile** | statistics of one column — the only thing the AI ever sees of the data | `DataProfile`, `profiles/` |
| **link candidate** | measured value overlap between columns; chance echoes deliberately included | `profiles/candidate_matrix.json` |
| **hypothesis** | one proposed rule, the AI's raw output; accepted ones become claims | `Hypothesis` (`llm/schemas.py`) |
| **claim** | a rule about the data, with author, evidence, and status | `Claim` (`model/`) |
| **mapping claim** | a claim that concrete views/columns play a domain role | `MappingClaim` |
| **status** | proposed / test-supported / contradicted / unresolved / business-confirmed — always derived from evidence | `ClaimStatus`, `resolve_status` |
| **domain guide** | one domain's business objects and their fields, with definitions and settlement paths — curated data, never code | `DomainGuide` YAML (`llm.domain_guide_file`) |
| **business object** | what a domain law judges: a thing of the domain a table can be (journal, subledger) | `ObjectSpec` (`llm/domain_guide.py`) |
| **field** | something an object carries; a `slot` of its object's law, or a clarification — never a law of its own | `FieldSpec` (`llm/domain_guide.py`) |
| **role** | any guide entry — object or field — a table/column can play | `MappingClaim.role` |
| **check definition** | reusable test logic: SQL template + deterministic verdict | `CheckDefinition`, `checks/REGISTRY` |
| **domain law** | a check definition encoding a conservation law — elects role winners | `CheckDefinition(domain="finance")` |
| **check plan** | a check definition bound to one claim's concrete columns | `CheckPlan` (V2, `llm/v2_bind.py`) |
| **check run** | the deterministic execution of a check plan | `run_check` (`engine/`) |
| **evidence** | an append-only finding: check result, document anchor, confirmation, testimonial, declaration | `EvidenceRecord` (five types) |
| **clarification question** | a drafted question to the humans when data alone cannot decide | `ClarificationQuestion` |
| **answer request** | the structured form of one business question: requested output + scope | `AnswerRequest` (V4, `llm/v4_request.py`) |
| **required knowledge** | the objects, fields and rules one answer depends on, each scoped | `RequiredKnowledge`, `KnowledgeItem` |
| **readiness map** | per knowledge item: claim, evidence, gap, and how each satisfied one is satisfied → ready / limited / blocked | `readiness/` (derived, never stored) |

---

## What comes next?

- **M5 — documents**: read the policy PDFs, back figures with source
  anchors; the poisoned figures in the divested-unit press release must
  not get through. It is also what the three unsupported *rules* in the
  readiness map above are waiting for — a sign convention lives in a
  policy, not in a column.
- M7 staleness propagation, M8 packaging.

---
---

# Background — the core idea, in questions and answers

*(Session of 2026-07-13, recorded in full rather than summarized. The sections
above describe **what** was built, milestone by milestone. This one records
**why it is the point** — and where the questions asked of it found real
gaps. Nothing here is canonical design; where a fact has a home, the home is
named.)*

---

## 0. The thesis

The sentence the milestones circle around but never quite say:

> **A thought is compiled into something refutable — and what will not compile
> is marked, never swallowed.**

The existing one-liner ("the data and the rules are given, the AI guesses, the
checks decide") says what *happens*. It does not say why that is worth
building. This does.

Unpacked:

An intuition — *"invoices probably reference customers"* — is not something you
can be right or wrong about. It is a vibe. What the pipeline does is force it
through a shape that has a **truth condition**: a form (`Predicate`) for which
an SQL query exists whose result settles the matter. Before compilation it is a
hunch. After, it is a proposition that reality can veto.

That is the move. The AI's output is treated as a **conjecture, never as a
finding.** And a conjecture that cannot be phrased as a falsifiable proposition
does not get to masquerade as knowledge.

### The reframing

Everyone else asks: *how do we make the LLM more reliable?*

This project asks: **how do we make the LLM's unreliability irrelevant?**

You do not fix the model. You build a system in which a wrong model output
cannot cost you anything except a *missed discovery* — never a *false belief*.
That is why M0 (the exam) had to come before M1 (the tool): the claim is only
worth something if it is measurable. And it is measured, every run: seeded
recall (what did we find?) and false promotions (what did we wrongly believe?).

**Recall is allowed to be bad.** It was 15 of 25 — mediocre, reported honestly,
misses diagnosed. **The other number is not allowed to be anything but zero.**
It is zero for a structural reason, not a lucky one.

---

## 1. Where the brain actually is

Not in the AI. Not in the check. **In the gap between them.**

> In a language model, *having an idea* and *deciding whether it is true* are
> the same operation. That is the disease. It is *why* it hallucinates with a
> straight face: the confidence and the content come out of the same
> next-token machine, so the confidence carries no information.

This system separates those two faculties into different organs and puts an air
gap between them:

- the **AI** can generate but structurally cannot judge — `Actor.AI` cannot
  author promoting evidence, forbidden by a validator in `model/objects.py`;
- the **check** can judge but structurally cannot generate — it only ever
  answers a question someone else posed.

Neither organ is a brain. Neither is trustworthy alone. The **architecture** is
the brain — and it is an old one: *conjecture and refutation*. The AI's job is
bold guessing; the check's job is trying to kill the guess. It works because of
an asymmetry of cost: a bad conjecture costs a discovery, a bad refutation
would cost the truth. So conjecture is made cheap and unaccountable, and
refutation is made deterministic, reviewed, and expensive.

### The detail that shows how seriously this was taken

The model's `rationale` — its *reasoning*, the thing every other AI product
proudly surfaces as justification — is **logged but never stored on the claim**
[`Hypothesis.rationale`, `llm/schemas.py`: "logged, never stored on the claim"].

Deliberate. If the AI's argument sat next to the claim, a human would read it,
find it persuasive, and promote. Its eloquence is a *liability*, so it is kept
out of the record. There is no confidence field on a `Claim`. There is nowhere
to write one.

**Its persuasiveness is inert by construction.**

---

## 2. How a sentence becomes a card

Every proposal the AI makes carries **two representations of the same rule**:

```
statement:  "Invoices reference customers"     <- prose, for humans
predicate:  references                         <- the logic, for machines
params:     {child: "invoices.customer_id",
             parent: "customers.customer_id"}
```

The `statement` is **decoration**: displayed to humans, and deliberately
*excluded* from the card's identity hash. The `predicate` + `params` are
**binding** — that is what the system reasons over, dedups on, and tests.

So "sentence logic" never really enters the system. The AI must hand over the
logic *and* a sentence describing it; only the logic is load-bearing. You cannot
hash a sentence, cannot dedup a sentence, cannot compile a sentence into SQL —
but you can do all three with a predicate.

### The predicate is the hinge — it does three jobs at once

```python
"references": _spec(("anti_join", "cardinality"),   # <- testable by these
                    {"child", "parent"},            # <- required params
                    {"expectation"}),               # <- optional params
```

1. **It is the rule's identity.** `claim_key()` hashes predicate + params +
   scope + validity + sources. Same skeleton, same card — regardless of
   wording, language, or session.
2. **It is a parameter contract.** Required and allowed params are declared.
   A missing or invented param is rejected by set comparison, not by judgment.
3. **It declares what may test it.** That first tuple lists the admissible
   check definitions. A `references` claim can never be bound to the `balance`
   check — the predicate already ruled it out.

And the two predicates whose template tuple is **empty** are the system
encoding its own limit as a type:

```python
"semantic_equivalent": _spec((), {"left", "right"}),
"concept_definition":  _spec((), set(), {"term"}),
```

`()` means: **no check can ever settle this.** "This German column and that
English column mean the same thing" is not decidable from values; no SQL
exists that would settle it. So the vocabulary declares these rules
*structurally unpromotable by machine*. They stay `proposed` until a human or
a document weighs in.

### The funnel — five gates, each narrower

**Gate 0 — what the AI may see.** Not the data. Ever. Only **profile cards**
(per-column statistics) and the **candidate map**. It proposes rules about data
it has never read. This is load-bearing twice: it is why the step scales
(O(schema), not O(data)), and it is why the honesty claim is *provable* — a
model that never saw the rows cannot have memorized the answer, which is what
makes the leakage scan meaningful.

**Gate 1 — the structural gate** [`llm/schemas.py`]. `extra="forbid"`
everywhere: an answer with a field we did not ask for is a *wrong answer*, not
a bonus. And `predicate` is a `Literal` over the closed vocabulary — **an
invented predicate fails at JSON parse time.** The model picks from the menu or
it fails. A structural failure is fatal for the whole batch → retry.

**Gate 2 — the semantic gate** [`check_*` in `llm/mapping.py`]. Do the params
satisfy the predicate's contract? **Does every referenced column actually
exist** (looked up in the `ProfileIndex`, built from the real scan — a
hallucinated column dies here)? Is the rule grounded in at least one known view?
Two design details worth keeping:

- **Failures are per-item, not per-batch** — one bad hypothesis is dropped and
  logged, the other 59 proceed. A scar from the first real run, recorded in the
  module docstring: *"56 hypotheses died over two items missing a term."* So
  item-level checks were deliberately moved **out** of the schema (fatal) and
  **into** mapping (survivable).
- **The error strings are reused verbatim as retry feedback** — the function
  that decides "invalid" produces the sentence sent back to the model. Retry
  feedback and final acceptance therefore *cannot disagree*. There is no
  second, looser judge.

**Gate 3 — the deterministic conversion** [`hypothesis_to_claim()`]. A pure
function. No LLM, no IO. Validated hypothesis in, `Claim` out; nothing
interprets anything. Params are canonicalized (strings stripped, string lists
sorted) so paraphrases hash identically, and `created_by=Actor.AI` is stamped
on — from here M1's law takes over. As its docstring says: *"that is the M1
core's law, not this module's choice."*

**Gate 4 — dedup.** `store.add_claim()` computes the claim key. Same rule
already filed, differently worded, from another session, in another language?
**No second card.**

**Gate 5 — the binding (V2).** A *separate* AI call: pick the check definition
and fill its parameters. Constrained by the predicate (job 3 above) and
validated against `TEMPLATE_PARAMS`, which mirrors the check library key for
key. And the AI is explicitly allowed to say **no** — `template: None` plus a
`no_template_reason`, persisted as a `DECLARATION`. A refusal is a result.

### Why the funnel holds

| stage | what it constrains | what a bad answer does |
|---|---|---|
| profile cards only | the AI never sees data | cannot leak, cannot memorize rows |
| `Literal` predicates | only 13 rule forms proposable | invented rule → parse failure |
| param contracts | the rule must be well-formed | wrong shape → item dropped |
| `ProfileIndex` | every reference must exist | hallucinated column → item dropped |
| pure mapping fn | no interpretation on the way in | — |
| `Actor.AI` | authors no promoting evidence | its confidence is inert |
| predicate → templates | cannot pick an unfitting check | disallowed template → rejected |
| reviewed SQL templates | it never writes SQL | — |
| `resolve_status` | truth recomputed from evidence | — |

**A wrong AI answer can cost a discovery. It can never buy false confidence.**
That asymmetry is the product; every gate exists to preserve it.

---

## 3. Where the 13 predicates came from — honest provenance

**Question asked: "How do we know the 13 are complete? Who invented this
Literal?"**

**Answer: they are not in the spec, and completeness is not claimed.**
`grep "Prädikat" docs/spec/` returns nothing. They were written by the AI
assistant during M4 (commit `36bf0ad`, "M4: LLM contract layer"). Not derived
from a standard, a paper, or prior art.

Note the contrast: the *five evidence types* carry an explicit "derived
enumeration — the spec says *die fünf Evidenztypen* without listing them" note.
The predicate list carries **no such provenance note anywhere** —
`docs/architecture.md` describes the mechanism (closed `Literal`, mirrors
`TEMPLATE_PARAMS`) but never says where the 13 came from. A reader could
mistake the list for something authoritative. *(Gap → §6.)*

### How they were actually derived — bottom-up, not top-down

Nobody asked "what are the fundamental forms of a data rule?" That would have
produced a taxonomy, and it would have been wrong. The real chain runs the
other way:

> **a trap in the practice company → forced a check definition → the template
> needed a predicate that could address it**

The governing rule was set in M3: *a template exists only when a case from the
practice company forces it. No building for stock.* So the templates are a
fossil record of 32 traps, and the predicates largely mirror them (sometimes
many-to-one: `references` covers `anti_join` **and** `cardinality`;
`unique_key` covers `duplicate` **and** `grain`).

Only **two** predicates were not template-forced — `semantic_equivalent` and
`concept_definition`, both with empty template tuples, added for the opposite
reason: to express rules that **no** template can settle.

**The vocabulary is an empirical residue of one corpus, not a theory.**

### Are they complete? No — and the incompleteness is measured

Seeded recall: **15 of 25**. Ten misses. That number *is* the answer, and it is
published in `docs/seeded-recall-m4.md` rather than buried. But the misses split
into two very different kinds, and the distinction matters more than the number:

**Recall gaps — the vocabulary *can* say it, the AI just didn't.**
F7 is a positional hierarchy needing a decode… and `decodes` exists. F11 is
legacy IDs in CRM references… and `references` exists. Nothing was missing.
The model simply did not propose it. *Better prompting fixes these; the
vocabulary is innocent.*

**Expressiveness gaps — the vocabulary genuinely cannot say it.**
Look at what the misses cluster into:

- **F14** — "credit entries are stored as negative amounts." In a policy PDF only.
- **F15** — "revenue = 4000–4999 **minus** the 4800–4899 contra accounts."
- **F19** — "use the monthly average FX rate, not spot." Both sit in the data,
  equally plausible, differing 0.5–2%.
- **F21** — "intercompany customers 90001/90002 are excluded from external revenue."
- **F25** — "2% rebate accrual above €500,000 annual key-account volume."

Every one is a **rule that does not live in the data at all.** No column
statistic reveals it; no SQL check discovers it. You could stare at perfect
profiles forever and never learn that policy mandates the *M* rate over the
*B* rate — both are just numbers. Trap class **K3**: conventions that exist
only in a document.

> **The 13 predicates cover the rules that data can betray. They systematically
> cannot express the rules only a document can tell you.**

Which is precisely why M5 is the next milestone and not an afterthought. The
brain's limit here is **sensory, not intellectual** — M5 gives it another sense
organ.

### Why a closed vocabulary is still right

**The closed `Literal` is not a claim of completeness. It is a claim about what
happens when we are wrong.**

If the vocabulary were open — if the AI could coin a predicate whenever the
existing ones did not fit — then hitting a K3 policy trap would produce a
confident-sounding rule form that nobody reviewed, wired to no check, tested by
nothing, indistinguishable from a real one. The failure mode would be **quiet
invention**.

Because it is closed, hitting a limit is **loud**. And there are four distinct
ways for the system to say "this does not fit," none of which pretends
otherwise:

1. **parse failure** — an invented predicate dies at the schema boundary;
2. **`templates=()`** — "I believe it, and *nothing can test it*." Stays
   `proposed` forever unless a human weighs in;
3. **`no_template_reason`** — "no template fits," persisted as evidence and
   shown in the viewer;
4. **clarification question** — data cannot decide; ask a human.

**An incomplete vocabulary costs a discovery. It cannot cost a false
promotion.**

### And what the naive design would get wrong

Worth stating, because it is the subtle part. A simpler system does one of two
things with a thought it cannot compile into SQL:

- **rejects it** → the tool goes blind to everything that is not a data
  property. Every K3 policy rule vanishes *silently*, and the tool confidently
  computes the wrong revenue with a green checkmark. That is **K1: green but
  wrong** — the most dangerous class in the whole corpus.
- **accepts it as a belief** → false confidence, the thing the entire machine
  exists to prevent.

This design does neither: it accepts uncompilable thoughts **labelled as
unprovable**. *The tool is allowed not to know. It is not allowed to be quiet
about not knowing.*

---

## 4. A worked correction — the card that looked right and wasn't

Recorded because the mistake is more instructive than the fix, and because it
exposed a real trap in the design.

**The bad card** (offered as an example of K6, "legitimate orphans"):

> ❌ *"Every order has an invoice."* — template `coverage`, exceptions treated
> as findings rather than errors.

**Objection raised: "but every order is either open or completed."**

Correct, and it lands two hits.

**Wrong template.** The orphans-are-not-errors behaviour does not come from
`coverage` at all. It comes from `anti_join` carrying the parameter
`expectation: "report"`, which flips the verdict function from `empty_expected`
(any exception row falsifies → **FAIL**) to `report_only` (exceptions are a
finding → **INCONCLUSIVE** + clarification question). One line: `verdicts.py`.
`coverage_verdict` does something else entirely. And note **where** the
parameter lives: on the **binding**, not on the card. The card states the rule;
the binding decides how a violation is read. (The earlier phrasing "the card
itself says what exceptions mean" was sloppy.)

**And the rule is false as stated.** The corpus orders table *has* a `status`
column (values like `COMPLETE`). So "every order has an invoice" is not a rule —
it is **two populations mashed together**. `expectation: "report"` does not fix
that, it **hides** it: the check now shrugs at *every* invoice-less order,
including completed ones, where a missing invoice is a genuine error. The card
can no longer fail. **A card that cannot fail is not checking anything.**

**The sharp version is two cards, and the ordering between them is the point.**

**Card A — what does `COMPLETE` even mean?**
> *"`orders.status = 'COMPLETE'` means the order is finished and must therefore
> have an invoice."* — a `ConceptClaim`.

**No check can settle this.** To the tool, `COMPLETE` is a string. Nothing *in
the values* reveals whether it means "delivered and billable" or "fully entered"
or "closed as cancelled." Settlement path: `decided_by: clarification`. It sits at
**proposed** until a person answers.

**Card B — the real rule, gated behind A.**
> *"Every completed order has an invoice."* — `anti_join` over
> `orders WHERE status='COMPLETE'` against `invoices.order_reference`,
> **without** `expectation: "report"`, so exceptions are real violations and the
> card can land on **contradicted**. `depends_on: [Card A]`.

And now `depends_on` earns its keep: `ready_for_probe()` returns `False` while
Card A is below *tested*. **The tool may not measure until it knows what it is
measuring.** It cannot quietly assume `COMPLETE` means what it looks like it
means, run a clean-looking check, and hand back a green light built on an
unexamined guess.

### So when *is* the "orphans are findings" card right?

When the distinction genuinely is not available — no status column, or one whose
meaning nobody has confirmed. Then `expectation: "report"` is the honest answer:
*"I see 40 orders with no invoice; I cannot tell from the data whether that is an
error or a waiting state."* → INCONCLUSIVE + clarification question. Better than false alarm
*or* false reassurance. That is exactly what the corpus card `k6_orders` does
[`tests/corpus_driven/test_probe_verdicts.py`].

> **The lesson: `expectation: "report"` is not a licence to make a fuzzy rule
> unfalsifiable. It is an admission that a distinction is missing, and a
> standing order to go get it.** Once the distinction exists, the card must be
> sharpened — not left parked on "finding".

*(This trap is not warned about anywhere in the docs today. Gap → §6.)*

---

## 5. A new domain — IFRS, a bike shop, a cookery

**Question asked: "If we enter a new domain — US GAAP to IFRS, a bike shop, a
cookery — do we need a completely different corpus?"**

First, three things must be pulled apart, because the word "corpus" is doing too
much work:

| | what it is | changes per domain? |
|---|---|---|
| **the machine** | M1 core, M2 profiling, the 10 untagged templates, the 13 predicates | **never** |
| **the domain pack** | domain-guide YAML (the *nouns*) + domain-tagged law templates (the *laws*) | **yes — that is the point** |
| **the corpus** | the exam: a fake company, known answers, seeded traps | only to *prove a new pack*, never to *run* |

**You do not need a corpus to run on a bike shop.** You need sources and a pack.
The corpus exists to prove honesty, not to enable operation.

The three examples turn out to be three very different *sizes* of change.

### IFRS — costs nothing

The finance pack's eight roles (`journal`, `amount_local`, `doc_ref`, `account`,
`period`, `entity`, `subledger_ar`, `intercompany`) and three laws (books
balance per document; subledger reconciles to control account; IC legs mirror)
contain **nothing GAAP-specific**. Double-entry bookkeeping is not an accounting
standard — it is arithmetic. Debits equal credits under IFRS exactly as under US
GAAP.

What *does* change is **definitions**: revenue recognition, lease treatment,
what counts as revenue. Every one of those is a K3 rule living in a **policy
document** — surfacing in this system as `ConceptClaim`s read out of the
accounting manual, exactly like corpus trap F15.

> **IFRS is not a new domain. It is a different set of documents.** M5's job,
> not a packaging job.

This is the strongest validation of the design available: the accounting
standard was never anywhere in the code, so switching it breaks nothing.

### The bike shop — a new pack, same machine

It almost certainly keeps double-entry books, so the **finance pack applies
unchanged** and Z4-style questions ("do the books balance?") work on day one.

But its *interesting* questions — margin per model, stock accuracy, late
suppliers — need a **retail pack**: new roles (`stock_movement`, `sku`,
`supplier`) and at least one genuinely new **law**:

> opening stock + receipts − sales − shrinkage = closing stock

A conservation law of the same species as "the books balance". And the price is
already stated in `docs/architecture.md ("Onboarding workflow")`: *"One law = one invariant check
— a new law also needs a new SQL template (**code, not YAML**)."*

**Roles are data; laws are reviewed code.** That asymmetry is deliberate: a law
is the one thing that can *promote* a claim, so no law enters without a human
writing and reviewing SQL.

### The cookery — this one bites

A restaurant's central rule is a **recipe explosion**:

> portions sold × recipe quantity per portion = ingredients consumed

`reconciles` compares two tables on a grouping and a measure. This rule joins
*through* a bill of materials and **multiplies**. It likely fits none of the 13
predicates cleanly and cannot be rendered by `reconciliation.sql.j2`.

**So the cookery would force a new template and probably a new predicate** —
the growth rule firing exactly as designed. And the codebase already anticipated
the question: the domain guide's header says *"Regel der Drei: no ontology, no
plugin framework before a **third** domain forces one."* Bike shop is domain
two. The cookery is domain three. The reconsideration is already scheduled.

### So: is a new corpus needed?

**For the machine — no.** "False promotions = 0" is not an empirical finding
about the finance corpus that might fail to replicate on bicycles. It is
**structural**: `Actor.AI` cannot author promoting evidence because a validator
forbids it, and `resolve_status` recomputes truth from evidence regardless of
what the evidence is *about*. Domain-blind. Transfers for free.

**For a new pack — yes**, and `docs/architecture.md ("Onboarding workflow")` already names the
reason:

> *"A too-strict law is self-policing (everything fails → clarification questions); a
> too-**loose** law is the one path to false confidence — an invariant that
> trivially passes promotes role bindings on evidence that tests nothing."*

If a new inventory-conservation SQL has a bug that makes it pass vacuously,
**nothing in the system catches it.** The check says PASS, the role binding is
promoted, and the tool is confidently wrong — the exact failure mode the whole
architecture exists to prevent. You cannot catch that by reading the code, and
the AI certainly cannot.

**But what is needed is corpus-*shaped*, not corpus-*sized*.** Not 24 months and
two legal entities. Per new law: one fixture where the law **holds** (check must
PASS) and one where it is **deliberately violated** (check must FAIL, and only
on the seeded row). Per new role: at least one wrong candidate that must lose
the election. A handful of tables, not a company.

**And one number never transfers: recall.** "15 of 25" is a statement about the
finance corpus and nothing else. On the bike shop we would have *no idea* what
fraction of its real traps the tool finds — and the system will not lie about
that either. It simply will not know. Honesty about not-knowing is preserved;
the measurement is not.

> **New domain = new pack, same machine.** A pack is a domain-guide YAML plus one SQL
> template per law. The corpus is needed only to prove the pack, and it can be
> small.

---

## 6. What this conversation exposed (open — not yet canonical)

Three gaps, all real, none yet in `README.md` or `meta/`:

1. **Predicate provenance is unrecorded.** The five evidence types are marked
   as a *derived* enumeration; the 13 predicates are not marked as anything. A
   note belongs next to the "Controlled predicate vocabulary" bullet in
   `docs/architecture.md`: derived bottom-up from the corpus-forced M3
   templates, **not** from the spec; completeness not claimed; the
   seeded-recall misses measure the gap.

2. **The predicate growth rule is unwritten.** M3 has one for templates ("only
   when a corpus case forces it"). M4 inherited the discipline in practice but
   never wrote it down for predicates. It belongs in `meta/conventions.md` —
   the pressure to add a speculative predicate *will* come, and the answer
   should already exist.

3. **No "pack acceptance kit."** `docs/architecture.md ("Onboarding workflow")` says how to
   *author* a domain pack (laws first → extract the nouns → new-hire test →
   leakage test → falsifiability per role, human signs off). It does not say
   how to **prove a pack is not quietly broken** — the minimal seeded fixture,
   positive *and* negative, per new law and per new role. Given that a
   too-loose law is named as *the* remaining path to false confidence, this is
   the most load-bearing of the three.

Also worth noting for the docs: **nothing currently warns that
`expectation: "report"` can be misused** to neuter a card that should have been
split (§4).
