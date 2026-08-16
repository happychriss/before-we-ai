# Positioning and pitch — how the argument was built

> **Status: thinking record, not a confirmed decision — 2026-08-08.** Nothing
> here is architecture. Confirmed design belongs in `docs/architecture.md`,
> delivery status only in `README.md`, live sequencing in `meta/memory.md`.
> This file records how the product's external argument was arrived at, what
> was rejected on the way, and which claims can and cannot currently be
> defended.
>
> **Language exception:** `meta/conventions.md` forbids German outside
> `docs/spec/`. The VP Finance conversation below is kept in German on
> purpose — it is a sales asset for a German-speaking market and translating
> it would destroy the thing being drafted. This is a deliberate, marked
> exception, not an oversight. Everything else in this file is English.

---

## 1. Why this document exists

The pitch was not written. It was argued into existence over one session,
and several of the strongest formulations only appeared *after* a weaker one
had been proposed and knocked down. The knocking-down is the valuable part
and it is not visible in the finished text, so it is recorded here.

Two things this file is for:

1. So the finished pitch can be re-derived if someone later asks "why is it
   worded exactly like that" — every load-bearing sentence has a reason, and
   most of them have a rejected predecessor.
2. So the gap between what is claimed and what is built stays visible.
   A pitch whose whole premise is *"we say what we do not know"* cannot
   afford a single overclaim; an overstating pitch for an
   anti-overstatement product is self-refuting.

---

## 2. Where the project actually is

Stated plainly, because every claim below has to be checked against it.

**Built and working, fully offline, suite green:**

- M0 fixture corpus · M1 epistemic core · M2 ingestion & profiling ·
  M3 check engine & epistemics runtime · M4 LLM contracts V1/V2 ·
  the readiness report · M5 documents & V3 · M6 question flow, answer types
  and the ReadinessMap.
- M7 in progress: staleness (7.1), a second answer type (7.2), request
  revisions (7.3), the defer act and source descriptions (7.5) are done.

**Not built:**

- **7.4** — the end-user projection and reference resolver. The report today
  speaks claim vocabulary; nothing yet renders the same store in a reader's
  words, and nothing turns an internal id into "this workbook, this sheet,
  this column".
- **7.6** — guide-builder integration. The guide builder itself is an
  experimental Stage 1 vertical slice in a separate workstream.
- **7.7** — document screening that reads tables as tables.
- **M8** — the end-user GUI. Planned, not started.
- **M9** — computing the answer (SQL generation + assumption capture).

**Standing measures:** False-Promotion **0** (structural, non-negotiable) ·
Seeded-Recall **14–15/25** in-scope traps, run-to-run noise ±2–3, no agreed
bar · prompt-leakage scan CLEAN.

**What this means for the pitch.** The pitch that emerged — *readiness,
gating, evidence, a verdict* — is almost exactly what is built. It does not
require M9. That coincidence between the sharpest positioning and the honest
capability is worth exploiting, and it is not an accident: the product was
always a control layer rather than an answering machine.

What is *not* demonstrable today is the surface. Today's demo is the
readiness report plus the owner walkthrough — a strong technical-buyer
demo, and not a CFO demo. That gap is M8's whole justification.

---

## 3. The intended shape of the product

Recorded because the pitch implies it and a reader should know what is being
promised.

**A simple Python program, easy to install, with a guided UI.** Not a
platform, not a service, not a deployment project:

- one `pip install`, one command to start, everything running locally;
- server-rendered UI (FastAPI + Jinja2 + htmx, no frontend build step —
  reasoning in `frontend-deployment-proposal.md`), so there is no second
  state model that could show a stale verdict after a rerun;
- the user's data never has to leave their laptop, which matters for the
  first real-data run;
- a hosted instance with a demo dataset for people who only want to look.

**Guided, not configured.** The user should never see YAML. The flow the UI
has to carry is: state the business question → drop in documents and data →
review and confirm the proposed business rules one card at a time → run →
work the open questions → see the verdict change. Page structure sketched in
`page-structure-thinking.md`; the reference mockup adds a tab split between
*guide decisions* and *answer issues*, which is where 7.4 lands.

All of this is planned. None of it is built.

---

## 4. How the argument developed

Recorded in order, including the wrong turns.

### 4.1 It started as a rendering question, not a positioning one

The session began on M7.4 — the end-user projection. The question asked was:
*the current solution is claim-focused, which is what makes it testable; the
user needs it question-focused, so do we need the logic the other way
around?*

**That was 80% right and the missing 20% would have broken the product.**
What must not invert is the *derivation direction*: evidence → derived status
→ readiness verdict. That arrow is the false-promotion invariant. Inverting
it means starting from the question, deciding what the answer needs, and
letting that decide what counts as settled — a machine reasoning backwards
from the desired answer.

What inverts is the **traversal order**:

- **claim-first is the proof order** — bottom-up: what does the evidence
  support?
- **question-first is the reading order** — top-down: what does this answer
  need, and where does each need stand?

Same facts, same one-way computation, entered from the other end. The
question-first half already exists in the engine (`ReadinessMap` starts at
the request and walks the dependencies; `gap_load()` already inverts claim →
questions-resting-on-it). What is missing is a projection that *enters*
there.

The rule that fell out, and which 7.4 should be built against:

> **The projection may re-index and re-word. It may never re-decide.**

The moment a question-first view computes its own notion of "this looks
answerable", there are two homes for one derived judgement, and they will
disagree quietly in the direction the user was hoping for.

The shape of that distinction — *same truth, entered from the other end* —
turned out to be the shape of the whole positioning argument, which is why
the session moved from code to pitch without changing subject.

### 4.2 Why "ask a question, get an answer" does not give a real answer

First attempt at the logical core. The structure:

```
answer = f(data, interpretation)
```

`interpretation` is the set of decisions fixing what the data *means*: which
table is the ledger of record, which accounts are revenue, what "last year"
spans, whether intercompany is eliminated.

Three facts about it:

1. it is **not in the question** — a question states a requirement and
   supplies no answers to it;
2. it is **not in the data** — no column says which table is authoritative,
   no file states the fiscal year;
3. it is **required** — you cannot compute without fixing it.

So any system taking a question and data and returning a number has
necessarily supplied `interpretation` from somewhere. Its options were ask,
refuse, or guess. Asking requires already knowing which choices are
load-bearing — which is the dependency structure it does not have. Refusing
is useless. So it guesses, and the guess is invisible because the output has
no slot for it.

**The property that makes this lethal:** a wrong interpretation does not
produce an erroneous answer. It produces a correct evaluation of a different
function. Internally consistent, no residual, no anomaly, self-verification
passes — because the computation *was* performed correctly. Which is why
accuracy improvements do not touch it: the failure happened before the
computation, in choosing which computation to perform.

Stated as the pair of distinctions:

- "I don't know" vs "here is a number" — obviously different.
- "here is the right number" vs "here is a number resting on a guess" —
  **identical**.

Every question-answering system collapses the second distinction while
carefully preserving the first.

### 4.3 The first formulation was wrong — and the correction was stronger

Three compressed forms were offered. The first was:

> *"Wrong assumptions don't produce wrong answers. They produce right answers
> to questions nobody asked. That's undetectable, so we check the assumptions
> instead of the answer."*

It was challenged and it does not survive. Four defects, worth keeping
because the same temptations will recur:

1. **"don't produce wrong answers"** — false as stated. They do produce wrong
   answers; that is the harm. What was meant is that the answer is not
   *internally* erroneous. The slogan traded accuracy for a snap.
2. **"questions nobody asked"** — somebody did ask; the system substituted a
   different question. And "right" only holds inside a frame the asker never
   entered. It is also not universally true: a wrong mapping can fan out a
   join or sum mixed currencies and produce something right under *no*
   interpretation.
3. **"undetectable"** — the worst, because the product contradicts it. The
   decoy journal *is* caught; the balance law refutes it. A detector was
   built. The defensible claim is much narrower: not detectable from the
   answer alone, and not detectable by any amount of checking the
   computation.
4. **"check the assumptions instead of the answer"** — assumptions are not
   checked; that would be the same trust problem one level up. The testable
   ones are tested and *the rest are routed to a human*. And "instead of the
   answer" describes a trade-off M9 has not yet forced.

**What survived is stronger, and it was already in `docs/architecture.md`.**
Detectability is asymmetric:

- a check can prove an interpretation **wrong** — the decoy fails `balance`;
- no check can prove one **right** — all three `account` candidates pass
  their anti-join and none promotes (`establishes: False`). *A journal
  balances per period AND per document AND per year, so a passing law never
  proves what one slot means.*

This is not an engineering limitation. It is **affirming the consequent**.
Every check you can write is a *necessary condition*; passing a necessary
condition is not proof, and no finite pile of them entails the
correspondence. That is why no better model, no more tests and no bigger
semantic layer closes it.

**Corrected formulations, in order of preference:**

> "Data can prove an interpretation wrong. It can never prove one right.
> Everything we build follows from that."

> "A wrong assumption doesn't look wrong. The number comes out clean, the
> arithmetic holds, and it answers a question you didn't ask."

> "The risk isn't a wrong number. It's a clean number resting on an
> assumption nobody chose on purpose."

**The lesson worth carrying:** the honest version of every argument in this
session turned out to be already written somewhere in `docs/architecture.md`.
The slogans drifted off the confirmed design; the confirmed design was right.

### 4.4 Applying the asymmetry to a context / semantic layer

Where does interpretation happen in a system that builds a context layer and
answers questions over it? **Both places, and neither records it:**

1. **at authoring** — someone decided `gl_postings` is the general ledger,
   that revenue is accounts 4000–4999, that period means posting date;
2. **at query time** — even given the layer, the model still picks which
   metric, which grain, which filter, and what "last year" means.

The layer's pitch is that (1) eliminates (2). It does not; it **relocates**
it — and the relocation makes the error *harder* to see:

- at query time interpretation is visible, per-question and contestable;
- at authoring time it becomes a **definition**, living in a file, under
  version control, wearing the authority of infrastructure. A guess written
  as a definition is indistinguishable from a fact.

That is laundering a guess into a finding, done once, inherited by every
answer afterwards.

**The consistency trap** — a second-order effect worth its own sentence,
because it is counter-intuitive and it lands hard with a finance audience.
The semantic layer's headline benefit is consistency: one version of the
truth. But disagreement was the detector. When two teams computed revenue
two ways and got two numbers, somebody investigated. Unify them on a wrong
definition and every answer now agrees with every other answer — and the
removal of the warning signal is sold as the feature.

**The real diagnosis: the context layer is under-typed.** It has one
syntactic slot — the definition — holding assertions of five different
epistemic kinds:

| the entry asserts | what can serve as evidence |
|---|---|
| this table has this column | a deterministic check |
| it balances / keys unique / no orphans | a deterministic check, decidable both ways |
| **this table *is* the ledger** | only survival — a law that killed the competitors. Comparative, never positive |
| **accounts 4000–4999 *mean* revenue** | a document anchor, or a named human with a scope. Not in the data at all |
| **this definition applies to *this* question** | the reviewed dependency list, plus someone confirming it is complete |

A schema fact and a policy decision are written the same way, look the same
way and are consumed the same way. The defect is not missing evidence — it
is **missing distinctions**, so one kind of evidence gets silently accepted
in place of another. Which is exactly what five evidence types and a
`resolve_status` that refuses to promote on the weak ones are for.

### 4.5 "Waterproofing the semantic layer" — right target, wrong metaphor

Proposed synthesis: before-we-ai waterproofs the semantic layer.

**The strategic instinct is right and should be kept.** The target is the
same artifact. This is a treatment applied to a semantic layer, not a
replacement for one — which means compatibility with an installed base
rather than competition with it. Commercially that is a much better wedge
than "an alternative to text-to-SQL".

**The metaphor is wrong in three ways**, each of which would cost credibility
in a technical conversation:

- waterproofing **seals**; this **exposes** — the point is making visible
  which entries are load-bearing and unproven;
- waterproofing is **applied once**; status here is derived on every read and
  lapses when the guide moves;
- waterproofing works on the artifact alone; half the mechanism is
  **external** — the question bounds the guide and gives it a referent it can
  be measured against.

Better:

> A semantic layer is a set of unverified premises wearing the clothes of
> infrastructure. We turn each premise back into a claim — with an author, a
> status and its evidence — and refuse to compute until the ones this
> question rests on have been settled.

**Honest caveat.** Nothing today ingests someone else's LookML, dbt semantic
model or Datasphere model and converts its entries into claims with
settlement paths. That import seam is a direction, not a capability. It is
notably close to what the guide builder does from documents.

### 4.6 The framing correction: grounded document, not answer-readiness

A first pitch was drafted around *"an answer-readiness control layer for your
context model"* and was rejected by the owner in favour of:

> I start with a bunch of data and a grounded document — one that everyone in
> the company needs and can align on — and it shows me that my data is
> consistent with the ground rules, and what proves it.

**Why the correction is better.** It sells a *document the company owns*
rather than a verdict that appears at the end of a process. And the
parenthesis carries more weight than it looks: a shared statement of what the
data means is a **coordination good** — it settles arguments between
departments, it is what an auditor asks for, it is what a new hire needs on
day one. Coordination goods have executive owners and budgets. Verdicts do
not. It also lowers activation energy: it starts where a company already is,
rather than requiring a question first.

**Three objections raised against it, all still open:**

1. **Who says the ground document is right?** `docs/architecture.md` already
   answers honestly: *"the domain pack is the critical — and currently
   unverified — input… the most load-bearing open weakness in the product."*
   And this framing **increases** the exposure: in the answer-readiness
   framing the question was an external referent, so a guide wrong by
   omission surfaced as `blocked`. Remove the question and nothing measures
   the guide. A too-loose law passes everything, elects the wrong candidate
   and produces a confident, product-branded pass.
2. **"Consistent with" is the affirming-the-consequent trap again.**
   Consistency is the necessary condition. Data consistent with the ground
   rules does not mean the data means what was agreed — all three `account`
   candidates pass and none promotes. If the pitch implies consistent ⇒
   correct, it sells the exact move the engine refuses to make.
3. **"What proves it" is right for half the output.** For a failure there is
   genuine proof: executed SQL, population, exception count, offending rows,
   fingerprints. For a pass there is *survival*, not proof.

**The reframing that came out of it:** the value is in the failures, not the
passes. `de_erp__gl_postings` passing the balance law is not a story;
`buchungen_report` failing in every one of 24 months is, and `intercompany`
failing on both sides simultaneously — so that no answer clears it and the
data itself has to change — is a finding someone must act on.

> *"It finds where what you agreed and what your data actually does have come
> apart."*

**How the two framings fit:** they are not competing.

- **The grounded document is what you sell** — concrete, ownable, has an
  executive buyer, needed regardless of AI.
- **Answer-readiness is what proves it is working** — ask a question and it
  tells you whether the document and the data between them can support an
  answer. That is the demo that stops the document being shelfware.

**A scheduling consequence.** If the grounded document is the thing being
sold, then the guide builder is not adjacent to the product — it is the
*onboarding for the product*. `docs/architecture.md` already says as much
("the guide is the unit of onboarding… closer to the commercial centre of
the product than its position suggests"), and it is currently ranked as 7.6,
an integration item. If the pitch is the document, that ranking is wrong.

### 4.7 The hardest question: how can you be sure?

Asked directly: *how can you be sure what critical domain knowledge is needed
to answer a business question, and that it is aligned with the data?*

**Straight answer: you cannot. And it is two different impossibilities.**

- **Sufficiency** fails by affirming the consequent (§4.3).
- **Completeness** — "is this the whole list?" — is a claim about *absence*.
  Verifying it means enumerating every business distinction that could bear
  on the answer and showing none is missing. That space is not enumerable in
  advance. Same shape as "prove there are no more bugs": no observation's
  absence proves absence.

Both are logical, not engineering. So the question is not how to be sure but
what to do about not being sure, and there are only three postures:

1. claim completeness anyway → false, and the failure is silent. This is what
   every AI-on-your-data product does by omission;
2. refuse until certain → never answers anything;
3. state what the list rests on, make its incompleteness visible and cheap to
   correct, and never let a passing check stand in for a human's sign-off.

The product is the third.

**What actually moves the needle on completeness:**

- **Reduce the model's claim from generation to classification.** "List what
  this question depends on" is unbounded and under-listing is invisible.
  "Which family is this?" is one claim, visibly right or wrong, and the list
  then expands deterministically from something reviewed once. This does not
  create completeness — it *relocates* it into a stable, reused, reviewable
  artifact. One review protects N questions. The economics change; the logic
  does not.
- **Make omission surface as a symptom.** Question-first: a missing entry
  shows up as `blocked` because the question demanded it. Be precise about
  coverage — it catches only what the question's words *reach*. It caught
  "nothing says which column carries entity" because the question said *by
  entity and month*. It would not catch "intercompany must be eliminated" if
  nothing in the question named it.
- **Keep it small enough to be read.** 57 lines. Completeness cannot be
  proven but it can be *reviewed*, and review only happens if the artifact is
  reviewable. An enterprise ontology is unreviewable by construction, so its
  completeness is never examined by anyone.

**Alignment is more tractable, and it is the part that is built.** A table is
never *asserted* into a role; candidates **compete** and the law kills the
ones that cannot be it. Alignment is established by elimination.

**And the election outcome grades the guide, not only the data** — this is
computed today and not surfaced anywhere as such:

| election outcome | about the data | **about the ground document** |
|---|---|---|
| exactly one candidate survives | a clear ledger of record | the definition discriminates — it works |
| **several survive** | — | **the definition is too loose to mean anything** |
| **none survives** | the data contradicts the rule | **or the rule does not fit this business** |
| no candidate at all | the object is not here | or it is named in words this landscape does not use |

Three `account` candidates passing is not only the promotion rule working —
it is the guide reporting that its own definition cannot tell three columns
apart. Reading the elections this way is a rendering change, not new
machinery, and it is the most direct answer available to "is my ground
document any good".

**The strongest defensible position**, and it is already shipped: the verdict
does not only judge the dependencies, it judges the *list* —

> *"the list was expanded from `profit_and_loss_by_dimension`, and nobody has
> confirmed that the question depends on nothing more."*

Every competitor's architecture is incapable of representing that sentence.
So the answer to "how do you know the list is complete" is not a defence:

> **"We don't — and we are the only ones who say so. Every answer we permit
> names who confirmed the list and when. If nobody has, it says that too."**

---

## 5. Claims that can be defended today

Each of these is checkable against the repository.

- The AI structurally cannot promote a claim; only a deterministic check or a
  named human can change a status. False-Promotion measured **0**.
- Every check result keeps the rendered SQL, the population, the exception
  count, sample offending rows and the data fingerprints it ran against.
- Every document anchor keeps the source, the page and the verbatim quote,
  and the quote is validated against the passage at write time — an invented
  sentence cannot enter the store.
- Every human confirmation carries an author, a scope and a date; a
  confirmation without a scope is refused.
- The dependency list is derived on every read from a reviewed answer type
  plus recorded human acts, never stored — so it cannot describe a guide that
  has since changed.
- A verdict that blocks or limits **names the dependency**, and every
  satisfied item says *how* it is satisfied.
- A confirmation lapses when the guide or the question changes, and the
  verdict says which of the two moved.
- When the data moves under a conclusion, the readings taken against the old
  data stop counting and the report says which table moved.
- The whole pipeline replays offline from recorded model answers, with a
  drift guard over both the built input and the system prompt.

## 6. Claims that cannot be defended yet

- **"The ground rules are themselves tested."** The acceptance kit's parts 1
  and 2 are open: the three finance laws have no holds-fixture and no
  violated-fixture, and no role has a deliberately wrong candidate that must
  lose. This is the single sentence the pitch most wants and cannot say.
- **"The software reads your policies and proposes your rules."** This is the
  guide builder — an experimental Stage 1 slice in a separate workstream, not
  integrated (7.6). It is the one place the LinkedIn post currently writes a
  cheque the repository may not cash.
- **"There is a UI."** M8. Today's surface is the readiness report and the
  owner walkthrough.
- **"It computes the answer."** M9. The product gates answers; it does not
  produce them.
- **"It works on your semantic layer."** No import seam from LookML, dbt or
  Datasphere exists.
- **"It has been proven on real data."** Everything is measured on one frozen
  synthetic finance corpus. Portability was probed by writing one shipbuilding
  guide and rendering a report from it. The real-data run whose truth the
  owner knows is deferred to M8 acceptance.
- **Any recall number.** Seeded-Recall is 14–15/25 with ±2–3 run-to-run noise
  and no agreed bar. It reports; it never gates. It is not a marketing figure.

## 7. Doubts and concerns

Recorded as concerns, not as blockers.

1. **The pitch is held to a higher standard than the product it describes.**
   The argument is *"we say what we do not know"*. One overclaim and the
   position collapses — not because the overclaim is large, but because it is
   the exact failure being sold against. Every sentence should be checkable.
2. **The grounded-document framing removes the guide's only referent.**
   Question-first made omissions visible. Selling the document first is
   commercially better and epistemically weaker, and nothing currently
   compensates. Closing the acceptance kit is the direct answer.
3. **The demo does not match the pitch.** The pitch speaks to a VP Finance;
   the demo is a technical artifact. Until M8 exists, either the audience is
   technical or the demo is a walkthrough narrated by a person.
4. **"The engine works today" invites a click that must land somewhere real.**
   Whatever a stranger tries first after reading the post has to work without
   the author present. If it does not, the credibility earned by precision is
   spent in one visit.
5. **A single corpus is a real limit.** Every number quoted anywhere comes
   from one synthetic finance landscape built by the same people who built
   the tool. That is a fair test of the mechanism and no test of the market.
6. **The guide builder is ranked as an integration item and argued here as
   the commercial centre.** Those cannot both be right. It is also explicitly
   another workstream, so the resolution is a scheduling and ownership
   decision, not a technical one.
7. **"Consistent with the ground rules" will keep trying to creep back into
   the marketing**, because it is the friendliest sentence available. It is
   also the affirming-the-consequent trap. Watch for it.
8. **This document takes a stated convention exception** (German outside
   `docs/spec/`). If the exception is not wanted, the German section moves to
   a file outside `docs/`.

## 8. What would strengthen the pitch most

In order of leverage per unit of effort.

1. **Close acceptance-kit parts 1 and 2** — one holds-fixture and one
   violated-fixture per finance law, and one wrong candidate per role that
   must lose its election. One focused session. It buys the sentence "the
   ground rules are themselves tested", which is the pitch's largest hole.
   Explicitly domain judgement, not an execution package.
2. **Surface the election outcome as a verdict on the guide** (§4.7 table).
   A rendering change over data already computed, and it is the only direct
   evidence available that a ground document is any good.
3. **Decide the guide builder's rank.** If the document is the product, its
   onboarding cannot be an integration item.
4. **Build 7.4 and then M8.** The pitch is aimed at people who will never
   read a claim card.
5. **Run one real landscape.** One customer's data, or the owner's own,
   through the whole flow. It converts every number in this file from
   "measured on our corpus" to "measured".

---

## 9. The VP Finance conversation (German)

Situation: a VP Finance has just bought SAP Business Data Cloud with
Datasphere and the knowledge graph, and objects that SAP has already verified
the context. This is the answer to that objection. Kept in German
deliberately — see the language note at the top.

**Tactical notes first:** lead with the side-effect paragraph
(*"Sie haben Konsistenz gekauft und dabei das Warnsignal abgeschaltet"*), not
with the dividing line — that is the sentence at which a VP stops defending
the investment. Never argue against SAP; he co-signed the decision, so an
attack on BDC is an attack on him. The three questions at the end are the
actual close: they cost him nothing, he tests it himself, and he comes back
with the result.

---

**Sehr geehrter Herr Vice President — Sie haben recht. Und genau deshalb
sprechen wir.**

SAP hat etwas Echtes verifiziert: das eigene Datenmodell. Dass BSEG die
Belegzeile ist, was eine Belegart bedeutet, wie die Objekte im Knowledge
Graph zusammenhängen. Einmal verifiziert, gültig für alle Kunden. Das stelle
ich nicht in Frage.

Verifiziert ist damit aber das **Modell** — nicht **Ihr Geschäft**.

### Die Trennlinie

Drei Dinge kann SAP strukturell nicht verifizieren, weil sie bei jedem Kunden
anders sind:

**1. Ihr Customizing.** SAP kennt das Schema. Ihre Konfiguration kennt SAP
nicht: welche Buchungskreise wirklich bebucht werden und welche Hüllen sind,
welche Belegarten Sie tatsächlich verwenden, welche Z-Felder Ihre
Fachbereiche gebaut haben. Und in Z-Feldern steckt erfahrungsgemäß genau die
Bedeutung, die nie jemand standardisiert hat.

**2. Alles außerhalb von SAP.** Ihre GuV entsteht nicht in SAP allein. Da ist
die zugekaufte Tochter auf dem Altsystem, die Planungsdatei im Controlling,
die Bankauszüge, das Vorsystem im Vertrieb. Der Knowledge Graph deckt SAP ab.
Ihre Frage deckt er nicht ab.

**3. Ihre fachlichen Entscheidungen.** Ob der Export aus dem Vorsystem führend
ist. Auf welcher Ebene Sie Intercompany eliminieren. Welche Preisbasis für
Plankosten gilt. Das sind keine Metadaten — das sind Entscheidungen, die
jemand in Ihrem Haus getroffen hat. Meistens vor Jahren. Meistens mündlich.

### Der Punkt, der am meisten wehtut

Verifizierte Semantik sagt Ihnen, was ein Feld **bedeutet**. Sie sagt Ihnen
nicht, ob Ihre Daten sich daran halten.

SAP kann bestätigen, dass eine Tabelle das Hauptbuch ist. SAP kann nicht
bestätigen, dass Ihre Intercompany-Buchungen tatsächlich spiegelbildlich
gebucht sind. Und wenn sie es nicht sind, rechnet Ihnen jedes System darüber
sauber eine falsche Zahl — mit korrekter Arithmetik, aus der richtigen
Tabelle, ohne jede Auffälligkeit.

### Die unbequeme Nebenwirkung Ihrer Investition

Vor BDC haben Controlling und Konzernrechnungswesen unterschiedliche Zahlen
produziert, und dann hat jemand nachgefragt. Diese Reibung war lästig — und
sie war Ihr einziges Frühwarnsystem.

Jetzt kommen alle Zahlen aus einem Modell. Ist darin eine Annahme falsch,
sind ab sofort alle Zahlen **einheitlich** falsch. Und Einheitlichkeit lesen
Menschen als Richtigkeit. Sie haben Konsistenz gekauft und dabei das
Warnsignal abgeschaltet.

Das ist kein Vorwurf an SAP. Das ist die Logik jedes Semantic Layer.

### Was wir machen

Wir bringen in ein kurzes, lesbares Dokument, was in Ihrem Haus tatsächlich
gilt: welches System führend ist, was als Umsatz zählt, wann eine Periode
geschlossen ist. Ein bis zwei Seiten, die Ihre Fachbereiche gemeinsam
abnehmen können.

Dann prüfen wir Ihre echten Daten dagegen und zeigen Ihnen, **wo beides
auseinanderläuft** — mit der Abfrage, die gelaufen ist, und den Zeilen, die
es gebrochen haben.

Und bevor eine Frage beantwortet wird, sagen wir, was diese Antwort
voraussetzt und was davon belegt ist:

- was die **Daten bewiesen** haben,
- was in einem **Dokument** steht, mit Seite und Zitat,
- was ein **Mensch entschieden** hat, mit Namen, Geltungsbereich und Datum,
- und was schlicht **niemand geklärt** hat.

Das Ergebnis ist keine Zahl. Es ist ein Urteil: **belastbar**, **belastbar
mit benannten Einschränkungen**, oder **nicht belastbar** — jeweils mit der
Angabe, was fehlt und wer es beantworten muss.

### Warum das für Sie persönlich relevant ist

Lineage zeigt, woher eine Zahl **technisch** kommt. Sie zeigt nicht, wer die
**fachliche** Entscheidung dahinter getroffen hat.

Wenn Ihr Abschlussprüfer fragt, warum der Umsatz so und nicht anders
abgegrenzt wurde, ist *"so steht es im Semantic Layer"* keine Antwort.
*"Das hat Frau Berger am 14. März für die Buchungskreise DE und AT
entschieden, Grundlage ist die Richtlinie Seite 12"* ist eine.

### Drei Fragen, die Sie Ihrem eigenen System heute stellen können

Zehn Minuten, und Sie brauchen uns dafür nicht:

1. Fragen Sie nach dem Umsatz des letzten Jahres. Auf welcher
   Geschäftsjahresdefinition rechnet das System — und ist die Tochter
   enthalten, die noch nicht migriert ist?
2. Lassen Sie sich zeigen, **welche** der Umsatzdefinitionen, die Ihre
   Fachbereiche verwenden, im Modell hinterlegt ist — und **wer** sie
   hinterlegt hat.
3. Fragen Sie das System, was es **nicht** weiß. Kommt darauf keine Antwort,
   ist das die Antwort.

> **Wir konkurrieren nicht mit SAP.** SAP hat die Hälfte verifiziert, die sich
> zentral verifizieren lässt. Die andere Hälfte gilt nur bei Ihnen — und
> genau die entscheidet, ob die Zahl stimmt.

---

## 10. The LinkedIn post

Not a sales pitch: an open-source project addressing a gap, written for a VP
or Director who is starting an AI project. Simple English on purpose.

Three things carry the post and should be protected in any edit:

- **"You were asked a lot of questions. Just not the ones that matter."** More
  generous than "nobody asked", and therefore more credible.
- **"And your tests will pass."** This replaced an abstract passage about
  necessary conditions. Same argument, concrete consequence — a reader
  recognises their own UAT in it.
- **Step 2 (approval).** Nobody else in this space says it out loud. It must
  not get compressed into step 1.

---

**Your company is getting ready for AI.**

Someone has been hired. The promise is that soon anyone can ask any question
of your data and get an answer. The demo looked good. The budget is approved.
The mood in the room is positive.

And somewhere in the back of your mind, something does not feel right.

That feeling is worth listening to. Here is what it has probably noticed.

**You were asked a lot of questions. Just not the ones that matter.**

They asked about your KPIs. Your dashboards. Your systems. Your stakeholders.
Your reporting calendar.

Nobody asked which of your three systems is the one that counts when they
disagree.
Nobody asked when your fiscal year actually starts.
Nobody asked whether that export in Controlling is the source of truth or a
copy somebody kept.
Nobody asked at what level you eliminate intercompany.

And the demo still produced numbers.

That is what your gut picked up. It worked without those answers. So
somebody, or something, supplied them. Not you.

**A wrong assumption does not look wrong**

If the system picks the wrong table, you do not get an error. You get a
number. The SQL is correct. The arithmetic is correct. The number looks
completely normal. It is the right answer to a question you did not ask.

Say your fiscal year runs May to April. That is not written in any table. It
is in someone's head. A system assuming January to December hands you a
number that is wrong by four months of trading, and nothing anywhere says so.

**And your tests will pass**

This is the part that catches people.

You will test the solution properly. It will pass. It passes because a test
checks whether the system computes what you told it to compute. It cannot
check whether what you told it was right.

Your acceptance test compares the result against a number your controller
produced by hand — using the same assumption. So the two agree. Everything is
green. You go live.

Then nothing happens. Nothing happens for a long time.

It does not fail in testing. It fails in reality — in a board pack, a
transfer price, a filing — usually a year or two later, when somebody asks
how the number was calculated and nobody can reconstruct it.

**Where this comes in**

Before the AI project, not after it. At exactly the point where you would
normally hand a data model to a tool and start asking questions.

Four steps, in this order.

**1. Get the rules written down.** Not an enterprise data model. One or two
pages in business language: which system is authoritative, what counts as
revenue, when a period closes, and what must always be true — a journal
balances, the subledger ties to the general ledger.

You do not start from a blank page. The software reads your existing policies
and documentation, proposes what it believes your rules are, and shows each
one with the page and the sentence it came from. You confirm, correct or
reject.

**2. Have someone approve it.** Textbook rules can be drafted for you. But
whether that export is authoritative is not a fact anyone can look up. It is
a decision. So every entry of that kind carries a name, a scope and a date.
Not "the model is validated." Frau Berger decided this, for these company
codes, in March.

**3. Test your data against it.** Now the rules do real work. Candidates
compete: three tables could be your ledger, and the ones that do not balance
are eliminated. You see where your data and your agreed rules have come
apart, with the query that ran and the rows that broke it.

You also learn something about the rules. If three candidates survive, your
definition was too vague to mean anything. If none survives, either your data
is broken or the rule does not fit your business.

**4. Only then answer questions.** Ask for revenue by entity last month, and
the system first lists what that answer depends on and where each item
stands.

The output is not a number. It is one of three: ready, ready with
limitations, or blocked. If it blocks, it names what is missing and who has
to decide it.

**The idea that makes this possible**

Every piece of knowledge is stored as a claim with a status, and the AI can
only ever produce "proposed" — it is structurally unable to mark anything as
proven. Only a deterministic test or a named person can do that, and anything
nobody can settle becomes a visible question instead of silence.

That is the whole trick. The AI does the reading and the proposing, which it
is good at. It is never allowed to decide.

**Status**

The engine works today. The interface is next: ask a question, see the open
points, answer them, run again, and see what became stale.

I put it on GitHub because this problem is not specific to my customers. It
is early. I would rather have criticism than stars.

👉 [link]
