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
     names.
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
   proposes: first **suspicion cards** about this concrete data ("the
   document number in the report references the general ledger"), then
   **role candidates** ("this table could be the journal" — competition
   wanted), then for each card the **fitting probe** from the toolbox,
   with parameters. Everything stays "suspected".
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
