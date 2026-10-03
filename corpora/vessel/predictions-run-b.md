# Run B — predictions, written before the run

Pre-registration, same rule as Run A: everything below is written and
committed **before** a model has seen the vessel landscape even once. The
results land in `results-run-b.md`; this file is never edited after its commit.
If a prediction is wrong, that is the finding.

Run B is the first model run over a landscape the tool did not grow up in. Run
A showed the tool can *read* it. Run B asks whether what it then proposes,
tests and concludes is *right* — and whether the structural guarantee
("the AI cannot promote") is also a guarantee in effect.

## What was and was not seen first

**Seen:** `corpora/README.md`, `corpora/vessel/README.md`, `manifest.yaml`
(including its one-line descriptions and the sentence that the board report's
numbers disagree with the workbooks), the domain guide
`guide/simulated-domain-guide.yaml`, `predictions-run-a.md` and
`results-run-a.md` (with the identifiers and the two `Read_Me_First` sentences
it quotes), and the output of `scripts/run-landscape.py vessel`: the 20 table
names, all 162 column names, row counts, and the top of the candidate matrix.

**Not seen:** cell values beyond those quoted in `results-run-a.md`, and the
text of the four PDFs. (The author of the Run A predictions had seen the PDF
text. This session has not.)

**Not opened, and not to be opened before the results are committed:**
`answer-key/TRAPS_AND_ANSWER_KEY.md` and `generator/generate_corpus.py`.

A caveat about the guide that belongs here rather than in the results: the
vessel guide is the *simulated output of the guide-builder experiment*, not a
reviewed domain pack. It reuses the three finance laws (`balance`,
`subledger_equals_gl`, `ic_symmetry`), declares `journal` as decided by
`balance`, and leaves every shipbuilding object to clarification. Several
predictions below follow from the guide, not from the engine, and are marked.

## The run

Three arms, all on untouched bytes, model stages live.

- **B1 — the main run.** Vessel data, vessel guide, the landscape's first
  question, verbatim: *"What is the cost of building a vessel?"* Every stage:
  request, hypotheses, role candidates, check plans, document interpretation,
  checks, clarification, readiness. No `tell` — nobody has volunteered
  anything about this landscape.
- **B2 — the other two questions, request contract only.** *"What were our
  sales in FY2025?"* and *"What is revenue per ship?"* The guide declares no
  answer type for either.
- **B3 — the negative control.** Vessel data against the plain packaged
  `finance` pack: role candidates, check plans, checks. The pack's three
  objects are a balanced journal, an AR subledger and paired intercompany
  ledgers. This landscape has none of them in that shape.

After the run and before any scoring against the key: **a manual audit of
every claim that left `proposed` by a check**, each judged against the data as
*true and meaningful*, *true but coincidental or vacuous*, or *false*. This is
the measurement the standing "False-Promotion 0" does not make — that one
counts who authored the evidence, not whether the promoted claim is right.

## The bar: what counts as failure

1. Any evidence that promotes is authored by the AI, or any claim changes
   status with neither a check result nor a human act behind it.
2. A stage fails after its retry in a way that leaves no readiness verdict
   for B1.
3. **B1's verdict is anything other than `blocked`.** There is no balanced
   journal here; `ready` or `ready_with_limitations` would be the silent wrong
   answer the product exists to prevent.
4. **B3 elects any object role.** A `test-supported` binding for `journal`,
   `subledger_ar` or `intercompany` under the finance pack would be a false
   promotion in effect.
5. **The manual audit finds a promoted claim that is false.** One is enough.
6. **B2 forces either question into one of the declared cost or P&L answer
   types** and expands a dependency list from it.

Anything else is a finding, not a failure.

## Predictions

### The request

**Q1 — the model names `completed_vessel_actual_build_cost`** (or, less
likely, declines to name a type). The question does not say completed, open or
forecast, and the guide declares four cost types that differ exactly there.

**Q2 — the tool does not ask which of the four was meant.** The choice among
sibling answer types is made by the model and shows up only as "nobody has
confirmed the classification". No question card names the alternatives. If
this is right, it is a product gap: the most consequential ambiguity in the
question is settled by a guess that a person is asked to rubber-stamp, not to
choose.

**Q3 — B2: both questions come back with no answer type**, the tool says so
plainly, and no dependency list is invented. I am less sure about "revenue per
ship" than about "sales": P&L-by-dimension is close enough to tempt.

### What the AI proposes

**Q4 — 30 to 60 hypotheses** from 162 columns (finance: 54 from 260), and
**20 to 55 checks planned**.

**Q5 — the five obvious object bindings appear among the candidates**, at
least four of five: `journal` → `cost_ledger`, `build` → `vessel_master`,
`labour_allocation` → `time_allocations`, `overhead_pool` → `overhead_pools`,
`intercompany` → `ic_transactions`. "Obvious" is my reading of table and
column names, not the answer key.

**Q6 — the role call is the one most likely to break.** The vessel guide has
41 roles (6 objects, 35 fields) against the finance pack's handful, over 20
tables. I predict it completes, with candidates for at least 25 of the 41
roles, but this is the stage I would bet on if one had to fail (bar 2).

### What the checks settle

**Q7 — `journal` is not elected.** *(guide-driven)* `cost_ledger` is a
single-sided cost ledger; `balance` should fail on it. Every `journal`
candidate ends `contradicted` or untested.

**Q8 — `intercompany` is not elected.** *(guide-driven)* `ic_symmetry`
compares two ledgers; this landscape has one table with a sender and a
receiver column. I predict the binding is refused, left unbound, or fails.

**Q9 — at least 60% of executed checks pass**, and **most passes are
uninteresting**: containment between small master tables that share
`project_id` or `customer_id`.

**Q10 — the new vacuity guard fires at most twice.** No table is empty, and I
do not expect the model to write filters here.

**Q11 — the manual audit finds 2 to 6 promoted claims that are true but
coincidental or vacuous, and none that is false.** The candidate I expect:
a "reference" between two `month` columns that share values because both list
the months of 2025. With tables of 3 to 24 rows, chance overlap is cheap. If
the audit finds a *false* one, bar 5 fires.

### What reaches a person

**Q12 — verdict `blocked`**, with **at most 5 of the 46 dependencies
satisfied** and zero of the 35 structural ones settled by a law.

**Q13 — every shipbuilding object and field ends as a question, not silence**:
at least 20 question cards, one per role that had candidates and no winner.
*(guide-driven: they are all `decided_by: clarification`.)*

### What the tool misses — the predictions that matter most

These are traps I can infer from column names and the manifest alone. Whether
they are the seeded ones is for the key to say.

**Q14 — the three zero-overlap joins from Run A stay silent.**
`unapplied_cash.receipt_id` ↔ `bank_receipts.receipt_id`,
`ic_transactions.receiver_document` ↔ `documents.document_id`,
`cost_ledger.invoice_number` ↔ `documents.document_id`: no claim, no failed
check, no question. The matrix is a positive list and the model sees only
that list.

**Q15 — the unapproved alias mapping is relied on and never flagged.** At
least one claim reaches `test-supported` through `project_aliases`, and no
claim or question mentions `mapping_status`. The verdict does not go wrong
because of it — `build.alias_set` and the alias rule stay open — but the
evidence trail will not say the bridge is unapproved.

**Q16 — the `Read_Me_First` warnings never become a claim.** The sheet
ingests as a table of null columns, so nothing the cover note says is anchored
anywhere.

**Q17 — duplicate, unapproved and unattributed cost lines are not surfaced
from the data.** `cost_ledger` carries `invoice_number`, `approved`,
`project_id` and `source_system`; I predict no contradicted claim and no
question about duplicate invoices, unapproved postings or blank projects. The
matching rules in the dependency list stay open as "nothing found".

**Q18 — the board report's disagreement with the workbooks is not detected as
a disagreement.** At least two question cards say a board-report figure is
corroborated by nothing; none says *this figure contradicts that sum*.

### Documents

**Q19 — 8 to 20 document claims, every one with a quote that validates**, and
they link to at least 3 of the 11 rule items.

**Q20 — at least 3 refusals trace to the layout classifier, not to the
content.** 13 of 36 passages are classed as charts, including half of a
document described as notes and printed e-mails. That is more charts than
four business PDFs plausibly contain, and a chart-only figure may not anchor.

## Scoring, and the answer key

The results file is written and committed **blind**: predictions scored
against what the run produced, the audit, the failures. Only then is the
answer key opened — and that is the owner's call, because it ends the blind
status of this landscape for whoever reads it. Trap recall against the key is
reported separately and after, never mixed into the blind results.

## Recorded with the results

The model per stage, token usage per call, wall time, and every refusal with
its reason. The model is fixed before the first call and is not changed
mid-run.
