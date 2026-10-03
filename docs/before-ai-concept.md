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

This required information is called the **required knowledge**. From here on,
the system hunts for exactly these items and nothing else.

**But who writes that list?** Not the AI — and this is the part worth
slowing down for. If a model writes the list, a forgotten dependency is
*invisible*: it appears nowhere, so nobody can test it, waive it or ask
about it, and the final verdict comes out confidently too generous with
nothing anywhere to show what was missed. Over-listing is a nuisance;
under-listing is a lie nobody can see.

So the domain guide declares **answer types** [`answer_types:` — **built**]:
per family of question — "a result by dimension", "a balance sheet",
"expected cost of a vessel" — the dependencies an answer of that family
carries, written and reviewed once by a human. The AI makes one much smaller
claim: *this question belongs to that family*. The engine then expands the
list [`readiness.expand` — **built**]. A human can read one classification;
nobody re-reads nine dependencies per question.

The list is **never stored** [`readiness.assemble` — **built**]. It is put
together on every read, so editing the guide changes every list that rests on
it — no copy anywhere can go on describing a guide that has moved. Only the
human *decisions* about it persist: the confirmation, the waivers, the items
someone added because the guide was short.

And until a human confirms the classification, the verdict is capped at
*ready with limitations*, naming the list itself as the limitation. Whether
the dependencies hold is one question; whether anyone has read the list of
them is another.

> **(built) honestly stated:** the middle of the pipeline runs *bottom-up* —
> it scans the whole landscape and proposes everything it can find. The
> question is the frame around it: it decides what must be known, and the
> readiness map at the end judges only those items. An item the question does
> not depend on is not a gap.
>
> And when no answer type fits the question, the AI does draft the list after
> all — labelled as an unreviewed draft, and capped the same way. The product
> stays usable on day one, before anyone has written a single answer type;
> *ready* is what has to be earned.

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
a record **stale** when the source data changed underneath it
[`staleness.py`]. Every reading carries a fingerprint of what it read, and
the next time the sources are read those fingerprints are compared: a
reading that no longer describes the data stops counting towards any
status, and the claims that rested on it fall back to what is left. The
flag is never taken off — you get freshness back by running the check
again, not by editing the old record. Five evidence types exist: check
result, document anchor, confirmation, testimonial, declaration — and only
check results and human confirmations can ever promote a claim.

What a *person* said is exempt. A testimonial does not expire because a
table changed, and a business confirmation does not expire at all from
data moving: moving data is not an argument.

---

## Evidence changes what the system may believe

The evidence is used to reassess the claim — this is **status
resolution** [`resolve_status` in `core/transitions.py`], and it is the
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
`core/objects.py` forbids it). That is why the false-promotion rate is
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
  milestone (`docs/seeded-recall.md`).

---

## Glossary

| plain term | meaning | in the code |
|---|---|---|
| **source** | a connected file or database; the list is written by a human | `before-ai.yaml` `sources:` |
| **data profile** | statistics of one column — the only thing the AI ever sees of the data | `DataProfile`, `profiles/` |
| **link candidate** | measured value overlap between columns; chance echoes deliberately included | `profiles/candidate_matrix.json` |
| **hypothesis** | one proposed rule, the AI's raw output; accepted ones become claims | `Hypothesis` (`llm/schemas.py`) |
| **claim** | a rule about the data, with author, evidence, and status | `Claim` (`core/`) |
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
| **answer request** | the structured form of one business question: requested output + scope + which answer type it was classified to | `AnswerRequest` (`llm/request.py`) |
| **answer type** | a family of question with the dependencies an answer to it carries, declared in the guide and reviewed once | `AnswerTypeSpec` (`llm/domain_guide.py`) |
| **required knowledge** | the objects, fields and rules one answer depends on, each scoped — expanded on every read, never stored | `readiness.assemble`, `KnowledgeItem` |
| **readiness map** | per knowledge item: claim, evidence, gap, and how each satisfied one is satisfied → ready / limited / blocked | `readiness/` (derived, never stored) |

---

## What comes next?

Documents (M5) and staleness (M7) are built — the walkthrough above runs
them. What is still ahead:

- **M7, the rest**: a second answer type, revisions of a question that has
  already been asked, a projection that speaks the reader's words instead
  of ours, and document screening that reads a table as a table rather
  than as a run of loose words.
- **M8** — the end-user surface on top of that projection, plus packaging.
- **M9** — computing the answer itself: generating the SQL, and capturing
  every assumption it had to make.
