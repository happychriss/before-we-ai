# before-we-ai — explained simply

This document explains the project without jargon. It grows with the project:
after every milestone a new section is added, in the same plain style. Where a
picture is used, the real thing in the code is named in brackets — so every
metaphor can be traced back to an actual file or object.

---

## What is this about?

The tool `before-we-ai` is meant to work on real, messy company data and
answer questions — in a way that it **never quietly gives a wrong answer**.
Either the answer is right, or the tool says honestly: "I am unsure here, and
this is why."

The problem: how do you prove that a tool is honest? You cannot test it on
real data, because there nobody knows the right answer. So we build **the
exam first** — and only then the student.

---

## M0 — Building the exam (✅ done, frozen as `m0-corpus-v1`)

### The corpus = the invented practice company

A complete, made-up but realistic company [`src/corpus/`]: two legal entities
(DE in euros, US in dollars), 24 months of business — orders, invoices,
bookkeeping, customer lists in Excel, contracts as PDF. Deliberately untidy,
like real life.

The decisive difference to real data: **we have the answer booklet**
[`src/corpus/data/expected_verdicts.yaml`]. For every question we know what
must come out, because we built the company ourselves.

### The target questions Z1–Z4 = the four exam tasks

Four typical business questions, e.g. "How much external revenue per
customer?" (Z2) or "Do the books balance?" (Z4). For each one we know the
correct result to the cent. If the tool later computes something different
**without saying why**, it has failed. That is the yardstick for "the tool
works".

### The faults F1–F29 = the hidden traps

Individual, deliberately built-in stumbling blocks — each one a story that
happens in real companies all the time:

- Customer 1101 gets the new number 1201 in 2025 (F5) — miss that, and you
  lose their revenue.
- An invoice plus its cancellation (F3) — sum naively and you double-count.
- A revenue figure sits in an old press release but belongs to a business
  unit sold off long ago (F26) — believe it, and you are poisoned.

Plus **3 blind traps** known only to the project owner — like exam questions
the teacher does not reveal in advance.

### The trap classes K1–K7 = the kinds of traps

The pattern behind the individual traps:

- **K1** = "green but wrong" — the calculation balances, yet the content is
  still wrong. The most dangerous kind.
- **K2** = double counting through structural breaks.
- **K3** = conventions that exist only in a policy PDF (e.g. "credit is
  negative").
- **K4** = relationships you cannot see in the values themselves (validity
  periods, postal-code ranges, encoded text columns).
- **K5** = ground rules that must always hold (the books balance).
- **K6** = "legitimate orphans" — an open order without an invoice is **not**
  an error, just a waiting state.
- **K7** = poisoned figures that must never be believed.

Important: the exam tests **trap types, not individual traps** — which is
why it can also grade the blind traps without knowing them.

### M0 in one sentence

We built a practice company with hidden traps and an answer booklet,
verified it independently and froze it — every future version of the tool
must pass this exam before it is allowed to do anything. And the tool itself
gets **no finance knowledge programmed in**: it must work the rules out from
the data and documents itself. The finance knowledge lives in the corpus,
not in the tool.

---

## M1 — The tool's memory (✅ done, tag `m1-core-v1`)

Now the first piece of the tool itself exists. No data analysis yet, no AI —
only the **memory** [`model/` + `store/` in `src/before_we_ai/`]: the rules
by which the tool remembers what it knows, what it suspects, and what it
does not know.

### The claim = the index card

Every suspicion becomes an index card [a `Claim`]: "I believe account 4300
is intercompany revenue." The card always records **who wrote it** and
**which evidence is attached**. A card carries exactly one of five stamps
[`ClaimStatus`]:

- **suspected** (inferred) — someone believes it; nobody has checked.
- **tested** — an automatic spot-check (a probe) confirmed it.
- **contradicted** — the probe says: not true.
- **unresolved** — the evidence contradicts itself. Loud, not quiet!
- **business-confirmed** — a human signed it off.

### The three iron rules

1. **The AI may only suspect.** However convinced it sounds — it can create
   cards, but it can never press a better stamp onto one itself. Only a
   probe or a human may promote. That is not an agreement, it is built in:
   there is simply no path in the code [`Actor.AI` cannot author promoting
   evidence — enforced by validators in `model/`].
2. **Contradiction gets loud.** If one probe says "true" and another says
   "false", nothing is averaged and the newest is not simply believed — the
   card jumps to **unresolved**, and a human must step in. That even applies
   to business-confirmed cards: if a probe later finds the opposite, that
   card is unresolved again too.
3. **Evidence is a ledger.** Every piece of evidence is only ever appended,
   never changed, never deleted. At most it is marked "stale" — then it no
   longer counts, but it stays readable.

### The mirror loop

If the user says "our fiscal year runs May to April", the tool stores the
sentence word for word — and before a human may confirm it, it must be
clear **what it applies to**: which entity? which period? A confirmation
without that scope is rejected [`PromotionError`]. (That is exactly trap F29
from the corpus: the sentence was true only for the US entity.)

### One card per rule, not per row

Important with large data: an index card always describes a **rule** ("every
open item has a posting in the general ledger"), never a single data row. If
the probe checks 100,000 rows and finds 37 outliers, **one** card gets
**one** piece of evidence: population checked, number of exceptions, a
handful of illustrative examples — not 100,000 cards nobody will ever read.
The full exception list goes to the disposable cache, not into the files.

Two safeguards belong to this: if the same rule is proposed twice (worded
differently, another session), the filing cabinet recognizes it by its
content and creates **no second card** [`claim_key` dedup — wording is
excluded from identity]. And if a pattern hides behind the exceptions
("all 37 come from the old numbering world"), a human can deliberately turn
that into a **new card** — linked to the original, but starting again at
"suspected" and earning its own stamps.

### The filing cabinet

Everything lives as plain text files in a project folder [`store/` — one
YAML file per card, one per piece of evidence]. No database, all
versionable with git. A check command verifies that no card points at
evidence that does not exist.

### And the exam from M0?

The memory was tested directly against the answer booklet: for each of the
32 traps, the evidence it would produce is played through — and the test
checks that the index card lands on the right stamp. Poisoned figures (K7)
stay **suspected**, no matter how many documents mention them. Legitimate
orphans (K6) are **not** stamped contradicted. And the hardest test: with
AI-only evidence, **not a single one** of the 32 traps gets promoted —
false promotions: zero.

### M1 in one sentence

The tool now has an honest memory: index cards with five stamps, where the
AI may only suspect, contradiction gets loud, and no evidence ever
disappears — tested against all 32 traps of the practice company.

---

## M2 — The tool gets senses (✅ done, tag `m2-ingestion-v1`)

Until now the tool had a memory but no eyes. Now it can open data sources
and **measure** them [`sources/` + `profile/` + `scan.py`] — still without
any AI, all pure craft.

### Connecting sources

The tool opens whatever a company has lying around: databases, CSV files,
ugly Excel. Everything is made available under one roof as queryable tables
[a DuckDB catalog, `cache/analysis.duckdb`]. The most important rule:
**nothing gets cleaned to death.** A document number like `0001042` stays
text with its leading zeros — the tool never guesses that text is "really a
number". (Exactly this has killed many a data project — that is trap T1
from the exam.)

### The Excel reader with a cleaning log

Excel is a special case: merged headers, numbers where identifiers should
be, dates in Excel's secret notation. A dedicated reader smooths that out —
but not silently: **every cleaning decision is recorded as evidence**
["column X: number turned into text, example: 1101" — a DECLARATION by
`Actor.SYSTEM`]. Anyone can later read what was changed during loading. The
log can never promote an index card — loading is observing, not judging.

### Every column gets measured

For every column of every table a profile card is written [`profile/`]: how
many values, how many distinct, how many empty, what pattern
(`AA-AAA-9999999`), which most-frequent values. The AI later sees **these
profile cards**, never the raw data — that is how even millions of rows
stay summarizable.

### The candidate map

Then the tool compares all columns pairwise: where do the same values show
up? The result is a map of possible relationships [the candidate matrix,
`profiles/candidate_matrix.json`] — the customer number on the invoice
matches the customer master, the migration table from the Excel matches the
old customer numbers (trap F5 only becomes findable through this!).

Important: the map **does not judge**. It deliberately also contains chance
echoes — two date columns that happen to share values are listed just the
same. Sorting that out is the job of the probes (M3) and of humans. And
because M2 creates no index cards at all, nothing can be falsely promoted
in this phase: zero risk, built in.

The map is also honest about its blind spots: relationships that do not run
through equal values (postal-code *ranges*, encoded hierarchy strings) are
**not** on it — the AI must find those later, and that is measured
separately.

### And the exam from M0?

The complete scan ran against the practice company: the leading zeros
survive (T1), the dirty Excel is normalized with a log (T9), all built-in
value-based relationships appear on the map — including the chance echo as
a negative control (T6). And: the entire cache may be deleted at any time —
a new scan rebuilds it identically.

### M2 in one sentence

The tool can now open messy sources without cleaning anything to death,
records every tidy-up decision as evidence, and draws an honest map of
possible relationships — judging them is reserved for the next stage.

---

## M3 — The probes (✅ done, tag `m3-probes-v1`)

Now the tool can **test** suspicions — by trying to refute them. Still no
AI involved: the probes ran against hand-written index cards from the
practice company's answer booklet.

### What is a probe?

A probe is an automatic spot-check [`probes/`]: an SQL query built from a
fixed template plus a fixed rule that translates the result into a stamp.
No discretion, no gut feeling — the same probe on the same data always
returns the same verdict. Every run leaves evidence with everything an
auditor needs: the executed query, how many rows checked, how many
exceptions, a handful of examples, and the fingerprint of the data at test
time.

There are a good dozen templates [`probes/templates/*.sql.j2`, catalogued
in `probes/library.py` REGISTRY]: reference check, duplicates, coverage,
reconciliation, validity periods, range mapping, decoding … — and one iron
rule: **a new template exists only when a case from the practice company
forces it.** No building for stock.

### Orphan is not error

The most important subtlety: an index card itself says what exceptions
mean. "Every order has an invoice" — open orders are **not** an error
there, but a waiting state. Such cards can never jump to "contradicted"
through findings; instead a **Fachfrage** — a question for the humans —
is drafted [a `QuestionCard`]: "data cutoff or error?". Real
contradictions, on the other hand, get loud: the CRM references that
resolve nowhere stamp their card "contradicted".

### The guardian probes

A second kind checks not individual cards but conservation laws of the
whole landscape: do the books balance per document? Does the subledger
match the general ledger? Are the intercompany postings symmetric? These
guardians [the invariant templates: `balance`, `subledger_equals_gl`,
`ic_symmetry`] found the practice company's deliberately built-in gap to
the point: **exactly one** unbalanced document, US entity, June 2024 — no
more, no less. And they decided the beauty contest between sources: the
nicely labelled accounting report looks like the journal but fails the
balance check — the unwieldy general ledger passes. The report stays
valuable anyway: as a second source for reconciliation, and exactly that
was proven too.

### Tolerances with reasons

Some deviations have a business explanation (open payments not yet matched
to invoices). For those there are tolerances — never hidden in code, but
visible in the project configuration [`before-ai.yaml` `tolerances:`],
with a reason. Never "turn the tolerance up until the test goes green".

### The final exam

All trap types from the answer booklet, played through with real probes on
real corpus data: leading zeros pass only **with** documented
normalization (without it the same relationship fails), orphans become
Fachfragen, contradiction between two probes makes the card "unresolved",
the chance echo from M2 is exposed by the cardinality probe and never gets
past "suspected". And the hardest number: **false promotions = 0** — the
set of "tested" cards is exactly the expected one, not one card more.

### M3 in one sentence

The tool now systematically tries to refute itself — with deterministic
spot-checks that tell orphans from errors, let conservation laws stand
guard, and promote not a single card unjustly.

---

## M4 — The AI joins (✅ done, `m4-llm-v1`)

### The AI as an intern with a clear employment contract

Up to M3 the tool was honest entirely without AI. Now, for the first time,
a language model joins [`llm/`] — but as an **intern, not a boss**. The
intern only ever sees the profile cards from M2 (statistics, never the real
data) and is allowed to do exactly two things:

1. **Propose suspicions** ("invoices probably reference customers", "this
   German and that English column mean the same thing") — each lands as a
   card with the stamp "suspected", never higher.
2. **Assign probes**: for each suspicion, pick the fitting check from the
   M3 toolbox. Whether the check passes is decided by the probe — never by
   the intern.

The decisive point: the intern **cannot** promote at all. The M1 rules make
it structurally impossible — whatever it writes, nothing more than
"suspected" comes out. And if it hands in nonsense (wrong column names,
broken formats), exactly that one proposal is sorted out and logged — the
rest keeps going.

### The cheat-sheet oath

One trap in the answer booklet is findable only semantically (German
product groups vs. an English hierarchy — no shared values). If the AI
finds it, there are two explanations: it is genuinely good — or we secretly
wrote it a cheat sheet. That is why tests check on every run that no prompt
contains corpus secrets [the leakage tripwire], and every conversation with
the AI is logged word for word [`cache/llm_log/`] and scanned.

### What came out (first real run)

- The AI proposed ~60 suspicions and 22 role candidates; the probes checked
  everything deterministically.
- **The general ledger won the "journal" role, the seductive report export
  lost** — exactly trap F27, decided by the conservation-law probe, not by
  the AI.
- 15 of 25 findable traps showed up as cards — including the semantic trap,
  with a clean cheat-sheet scan.
- And again the hardest number: **false promotions = 0.**

For testing, everything also runs **offline**: real, recorded AI answers
are replayed like a tape [`tests/fixtures/llm/`] — reproducible at any
time, no network, no cost.

### M4 in one sentence

An AI may now write up suspicions and suggest checks — but truth is still
awarded only by probes and humans, and that is not a policy, it is built-in
physics.

---

## The big picture — one pass from start to finish

All milestones together form **one** flow. The sentence to remember:

> **The data and the rules are given, the AI guesses, the probes decide.**

1. **Given: the raw data.** A human lists the sources (databases, CSV,
   Excel, PDF) in the project file [`before-ai.yaml` `sources:`] — the
   tool never invents sources.
2. **Given: the rules.** They come from two pots, and together they are
   the **domain pack**:
   - The **role pack** [a YAML file, e.g. the finance pack]: the *nouns*
     of the domain — what a journal is, what a subledger, what an
     intercompany posting. Written by humans, pure definitions, no system
     names. Each role also declares how it can ever be settled
     [`decided_by:` — a law, `fachfrage`, or `slot`; checked on load]:
     some roles a law can decide (books balance → this is the journal),
     others no arithmetic can — what a column *means* is a human
     question. The promise: **every role ends in a probe verdict or a
     Fachfrage, never in silence.**
   - The **domain-law templates** [the three templates tagged
     `domain="finance"` in `probes/library.py`]: the *laws* — "books
     balance per document", "subledger equals general ledger",
     "intercompany postings mirror". Shipped by the developers as
     reviewed code.

   Be honest about what this means: **the product alone is not a general
   solution.** The machinery is general — the ten untagged probe templates
   (reference check, duplicates, coverage …) work in any domain — but it
   only becomes useful *together with a domain pack*, and what is
   domain-specific is explicitly marked and listable, never hidden in the
   machinery. New domain = new pack, same machine.
3. **Measure (M2).** The data is loaded, every column gets a profile card,
   and the candidate map measures where the same values appear. Measuring,
   not judging.
4. **The AI guesses (M4).** The intern sees profile cards + map and
   proposes: first **hypotheses** — proposed rules about this concrete
   data ("the document number in the report references the general
   ledger"), each accepted one becoming an index card — then
   **role-binding candidates** ("this table could play the journal
   role" — competition wanted), then for each card a **binding**: the
   fitting probe template from the toolbox, with parameters. Everything
   stays "suspected".
5. **The probes decide (M3 machinery).** Deterministic SQL against the
   real data. Only here are stamps awarded: tested, contradicted,
   unresolved. Roles where no candidate passed become a **Fachfrage** to
   the humans.

So the AI never checks anything itself — it sits between measuring and
testing purely as a proposal generator. A wrong AI answer can at most cost
a discovery, but it can never create false confidence.

### Small glossary

| term | meaning | in the code |
|---|---|---|
| **source** | a connected file or database; the list is written by a human | `before-ai.yaml` `sources:` |
| **profile card** | statistics summary of one column — the only thing the AI ever sees of the data | `profile/`, `profiles/` output |
| **candidate map** | measured value overlap between columns; deliberately includes chance echoes | `profiles/candidate_matrix.json` |
| **hypothesis** | one proposed rule, the AI's raw output; every accepted one becomes an index card stamped "suspected" | `Hypothesis` (`llm/schemas.py`) |
| **index card** | a suspicion as a rule about the data, with author and evidence | `Claim` (`model/`) |
| **stamp** | suspected / tested / contradicted / unresolved / business-confirmed — always derived from evidence, never set directly | `ClaimStatus`, `resolve_status` |
| **role** | a domain noun a table/column can play (journal, subledger, …) | `RoleBindingClaim` |
| **role pack** | one domain's role definitions as a file — humanly curated | `RoleSet` YAML (`llm.roles_file`) |
| **probe** | an automatic SQL spot-check with a fixed verdict — the only machine path to a better stamp | `probes/`, `engine/` |
| **template** | a probe's blueprint (code); the AI only fills in parameters, never writes SQL | `probes/templates/*.sql.j2` + REGISTRY |
| **guardian / domain law** | templates for conservation laws of the whole landscape — they also decide which candidate wins a role | `TemplateSpec(domain="finance")` |
| **domain pack** | role pack + domain-law templates: everything domain-specific, explicit and listable | role YAML + `domain`-tagged REGISTRY entries |
| **binding** | the assignment card → template + parameters (AI proposal, strictly validated) | V2, `llm/v2_bind.py` |
| **evidence** | an appended, never-deleted finding: probe run, document anchor, confirmation, testimonial, declaration | `EvidenceRecord` (five types) |
| **Fachfrage** | a written question to the humans when data alone cannot decide | `QuestionCard` |

---

## What comes next?

- **M5 — documents**: read PDFs, back figures with source anchors; the
  poisoned figures in the management report must not get through.
- M6–M8 follow after: question flow, staleness, packaging.

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
probes decide") says what *happens*. It does not say why that is worth
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

Not in the AI. Not in the probe. **In the gap between them.**

> In a language model, *having an idea* and *deciding whether it is true* are
> the same operation. That is the disease. It is *why* it hallucinates with a
> straight face: the confidence and the content come out of the same
> next-token machine, so the confidence carries no information.

This system separates those two faculties into different organs and puts an air
gap between them:

- the **AI** can generate but structurally cannot judge — `Actor.AI` cannot
  author promoting evidence, forbidden by a validator in `model/objects.py`;
- the **probe** can judge but structurally cannot generate — it only ever
  answers a question someone else posed.

Neither organ is a brain. Neither is trustworthy alone. The **architecture** is
the brain — and it is an old one: *conjecture and refutation*. The AI's job is
bold guessing; the probe's job is trying to kill the guess. It works because of
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
   probe templates. A `references` claim can never be bound to the `balance`
   probe — the predicate already ruled it out.

And the two predicates whose template tuple is **empty** are the system
encoding its own limit as a type:

```python
"semantic_equivalent": _spec((), {"left", "right"}),
"concept_definition":  _spec((), set(), {"term"}),
```

`()` means: **no probe can ever settle this.** "This German column and that
English column mean the same thing" is not decidable from values; no SQL
exists that would settle it. So the vocabulary declares these rules
*structurally unpromotable by machine*. They stay `inferred` until a human or
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

**Gate 5 — the binding (V2).** A *separate* AI call: pick the probe template
and fill its parameters. Constrained by the predicate (job 3 above) and
validated against `TEMPLATE_PARAMS`, which mirrors the probe library key for
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
| predicate → templates | cannot pick an unfitting probe | disallowed template → rejected |
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

> **a trap in the practice company → forced a probe template → the template
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
confident-sounding rule form that nobody reviewed, wired to no probe, tested by
nothing, indistinguishable from a real one. The failure mode would be **quiet
invention**.

Because it is closed, hitting a limit is **loud**. And there are four distinct
ways for the system to say "this does not fit," none of which pretends
otherwise:

1. **parse failure** — an invented predicate dies at the schema boundary;
2. **`templates=()`** — "I believe it, and *nothing can test it*." Stays
   `inferred` forever unless a human weighs in;
3. **`no_template_reason`** — "no template fits," persisted as evidence and
   shown in the viewer;
4. **Fachfrage** — data cannot decide; ask a human.

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
finding → **INCONCLUSIVE** + Fachfrage). One line: `verdicts.py`.
`coverage_verdict` does something else entirely. And note **where** the
parameter lives: on the **binding**, not on the card. The card states the rule;
the binding decides how a violation is read. (The earlier phrasing "the card
itself says what exceptions mean" was sloppy.)

**And the rule is false as stated.** The corpus orders table *has* a `status`
column (values like `COMPLETE`). So "every order has an invoice" is not a rule —
it is **two populations mashed together**. `expectation: "report"` does not fix
that, it **hides** it: the probe now shrugs at *every* invoice-less order,
including completed ones, where a missing invoice is a genuine error. The card
can no longer fail. **A card that cannot fail is not checking anything.**

**The sharp version is two cards, and the ordering between them is the point.**

**Card A — what does `COMPLETE` even mean?**
> *"`orders.status = 'COMPLETE'` means the order is finished and must therefore
> have an invoice."* — a `ConceptClaim`.

**No probe can settle this.** To the tool, `COMPLETE` is a string. Nothing *in
the values* reveals whether it means "delivered and billable" or "fully entered"
or "closed as cancelled." Settlement path: `decided_by: fachfrage`. It sits at
**inferred** until a person answers.

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
error or a waiting state."* → INCONCLUSIVE + Fachfrage. Better than false alarm
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
| **the domain pack** | role YAML (the *nouns*) + domain-tagged law templates (the *laws*) | **yes — that is the point** |
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
already stated in `docs/onboarding-workflow.md`: *"One law = one invariant probe
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
the question: the role pack's header says *"Regel der Drei: no ontology, no
plugin framework before a **third** domain forces one."* Bike shop is domain
two. The cookery is domain three. The reconsideration is already scheduled.

### So: is a new corpus needed?

**For the machine — no.** "False promotions = 0" is not an empirical finding
about the finance corpus that might fail to replicate on bicycles. It is
**structural**: `Actor.AI` cannot author promoting evidence because a validator
forbids it, and `resolve_status` recomputes truth from evidence regardless of
what the evidence is *about*. Domain-blind. Transfers for free.

**For a new pack — yes**, and `docs/onboarding-workflow.md` already names the
reason:

> *"A too-strict law is self-policing (everything fails → Fachfragen); a
> too-**loose** law is the one path to false confidence — an invariant that
> trivially passes promotes role bindings on evidence that tests nothing."*

If a new inventory-conservation SQL has a bug that makes it pass vacuously,
**nothing in the system catches it.** The probe says PASS, the role binding is
promoted, and the tool is confidently wrong — the exact failure mode the whole
architecture exists to prevent. You cannot catch that by reading the code, and
the AI certainly cannot.

**But what is needed is corpus-*shaped*, not corpus-*sized*.** Not 24 months and
two legal entities. Per new law: one fixture where the law **holds** (probe must
PASS) and one where it is **deliberately violated** (probe must FAIL, and only
on the seeded row). Per new role: at least one wrong candidate that must lose
the election. A handful of tables, not a company.

**And one number never transfers: recall.** "15 of 25" is a statement about the
finance corpus and nothing else. On the bike shop we would have *no idea* what
fraction of its real traps the tool finds — and the system will not lie about
that either. It simply will not know. Honesty about not-knowing is preserved;
the measurement is not.

> **New domain = new pack, same machine.** A pack is a role YAML plus one SQL
> template per law. The corpus is needed only to prove the pack, and it can be
> small.

---

## 6. What this conversation exposed (open — not yet canonical)

Three gaps, all real, none yet in `docs/requirements.md` or `meta/`:

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

3. **No "pack acceptance kit."** `docs/onboarding-workflow.md` says how to
   *author* a domain pack (laws first → extract the nouns → new-hire test →
   leakage test → falsifiability per role, human signs off). It does not say
   how to **prove a pack is not quietly broken** — the minimal seeded fixture,
   positive *and* negative, per new law and per new role. Given that a
   too-loose law is named as *the* remaining path to false confidence, this is
   the most load-bearing of the three.

Also worth noting for the docs: **nothing currently warns that
`expectation: "report"` can be misused** to neuter a card that should have been
split (§4).
