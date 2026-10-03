# Run B — results

Run 2026-10-03 against `corpora/vessel/`, model stages live. Predictions were
written and committed first — `predictions-run-b.md`, commit `d577fa4` — and
that file has not been edited since. The models were fixed before the first
call (commit `6f03819`): **Opus 5.5** for request, hypotheses, role
binding and documents, **Sonnet 5.5** for plain check binding. That is an
owner decision and not the finance recordings' Opus 4.8 / Sonnet 5, so a
difference between the two landscapes cannot be put down to the landscape
alone.

These results are **blind**: no file under `answer-key/` or `generator/` was
opened. Trap recall against the key is a separate step and the owner's call.

Reproduce: `scripts/run-landscape-live.py` (spends the key). The three
projects, with every prompt and answer verbatim, are kept under `runs/`
(git-ignored).

## Verdict

**One of the six failure conditions fired: the audit found a promoted claim
that is false as stated.** The other five held: no AI-authored promoting
evidence, no stage failed, the main verdict is `blocked`, the negative control
elected nothing, and neither unclassifiable question was forced into a
declared answer type.

The run also produced the finding nobody predicted, and it is the mirror image
of the one that fired: **the AI cannot promote, but it can contradict — by
choosing the check.** 15 role candidates that are almost certainly the right
column were marked `contradicted` by checks testing a neighbouring
proposition, several of them failing only on rounding.

## What came out

| | B1 main | B3 control | B2 request |
|---|---|---|---|
| guide | vessel (6 objects, 41 roles) | packaged finance (3 objects, 8 roles) | vessel |
| hypotheses | 37 | — | — |
| role candidates | 50, for 41 of 41 roles | 26, for 8 of 8 roles | — |
| document claims | 28, each with a validated quote | — | — |
| checks planned / run | 46 / 45 (1 crashed) | 6 / 6 | — |
| pass / fail | 17 / 28 | 0 / 6 | — |
| claims test-supported / contradicted / proposed | 11 / 28 / 76 | 0 / 6 / 20 | — |
| question cards | 71 (40 role cards) | 12 | — |
| verdict | **blocked**, 0 of 46 dependencies | no role elected | no answer type, twice |
| tokens in / out | 196,480 / 37,064 | 77,174 / 6,701 | 11,884 / 2,532 |
| wall time | 5 min 8 s | 1 min 6 s | 31 s |

Total: about 286,000 input and 46,000 output tokens.

B1's 46 dependencies by ground: 23 undecided (candidates proposed, none
settled), 13 **all candidates contradicted**, 10 nothing proposed.

## The bar

| | condition | outcome |
|---|---|---|
| 1 | AI-authored promoting evidence, or a status change with no check or human behind it | **held** — none |
| 2 | a stage fails after its retry | **held** — every stage completed; 3 retries in total |
| 3 | B1's verdict is not `blocked` | **held** — blocked |
| 4 | B3 elects an object role | **held** — all six law checks failed |
| 5 | the audit finds a promoted claim that is false | **FIRED** — one, see below |
| 6 | B2 forces a question into a declared type | **held** — `answer_type: None` for both |

## The audit: every claim a check promoted

Eleven claims reached `test-supported`. Each was checked against the data by
hand.

| | claim | judgement |
|---|---|---|
| T1 | every `customer_id` on sales documents is in the customer master | true, meaningful |
| T2 | every `vessel_master.customer_id` is in the customer master | true, meaningful |
| T3 | the cost ledger's `project_id` references the vessel master | **true, but narrower than stated** — 1 of 138 rows has a blank `project_id`; the anti-join skips blanks and says nothing about them |
| T4 | `project_id` is a unique key of the vessel master | true, meaningful |
| T5 | `transaction_id` uniquely identifies cost ledger rows | true, meaningful |
| T6 | monthly FX rates cover every month in which time is allocated | true, meaningful (the list of 11 months was supplied by the model and matches the data) |
| T7 | elimination journal `source_document` references the IC `sender_document` | true, meaningful |
| T8 | `gross_amount` = `net_amount` + `vat_amount` on sales documents | true, meaningful |
| T9 | `revenue_by_ship.vessel_contract_revenue` reconciles to `vessel_master.contract_value` per project | **false as stated** |
| T10 | cost ledger `entity` is consistent with `location` | true, meaningful (all 138 rows joined) |
| T11 | entity codes in ledgers reference `group_structure` | true; the check tested one ledger, the claim says "ledgers" |

### T9, the one that fired the bar

The claim says the two reconcile *per project*. They do not: `VSL-2502` (work
in progress) has a contract value of 2,350,000 against a contract revenue of 0,
and `VSL-2506` (cancelled letter of intent) 3,100,000 against 0. Two of five
projects disagree.

The check passed because the model bound it with a filter it wrote itself:
`left_where: status = 'delivered'`. Over the three delivered projects the
figures agree exactly. The proposition that was tested is true and is good
business sense — contract revenue is recognised on delivery. **But it is not
the proposition that was promoted.** The claim's text carries no "for delivered
vessels", and a reader of the claim list sees an unqualified reconciliation
marked test-supported.

Two things about this:

- **It is visible only because of a change made the same day.** The runner now
  records how many rows a filter let through, so the evidence says "tested 3 of
  5 rows of vessel_master". Before that change this pass would have carried no
  trace of the narrowing at all.
- **The binding-time guard added the same day does not stop it, and should
  not.** The filter names a column and selects rows. It is an honest filter.
  The defect is that a filter narrows the *test* without narrowing the *claim*.
  The fix is not validation: either a filtered pass promotes a claim whose
  scope carries the filter, or it does not promote.

## The finding nobody predicted: contradiction by choice of check

28 claims ended `contradicted`. Sorted by what the failing check actually says:

**Real findings in the data (11).** These are what the tool is for, and several
are sharp: a duplicate `invoice_number` in the cost ledger (`STA-2024-6710`,
twice); a duplicate sales `document_id`; two yard job references that map to
the wrong project; one cost row where `reported_eur` is `amount_local`
*multiplied* by the PLN rate instead of divided (`CST-00068`: 135,201.77 PLN at
4.3377 reported as EUR 586,464.72); intercompany sender amounts that do not
equal cost base plus markup in 3 of 5 rows; three bank receipts applied to
documents that do not exist; and both `journal` candidates failing the balance
law, as they should on a single-sided ledger.

**An artefact of the reader (1).** *"The pivot export's project totals should
equal the sum of cost ledger reported_eur per project"* is contradicted in all
6 groups — because every pivot total is `NULL`. They are Excel formulas with no
cached value, the limitation Run A already found. The claim is not refuted; it
was never testable. The tool says "contradicted".

**Role candidates refuted by a check about something else (15).** The model
picks the check for a role candidate, and a generic check "may break a role
binding but never make one". On this landscape that rule cut the wrong way:

- `time_allocations` as `labour_allocation`, and its `extended_cost_eur` as the
  labour cost: contradicted because `extended_cost_eur` ≠ `hours` ×
  `hourly_rate_eur` in 41 of 47 rows. The first row: 211.15 × 62 = 13,091.30
  against a stored 13,091. **It is rounding to whole euros.**
- `cost_ledger.amount_local` as the local amount: contradicted because one row
  out of 138 has the FX error above.
- `ic_transactions.project_id` as the IC build reference: contradicted because
  one of five values is not in the vessel master.
- `overhead_pools` as the overhead pool: contradicted because pool ≠ rate ×
  base in 2 of 3 rows.

In each case the check found something true about the *data* and the engine
recorded it as a verdict on the *binding*. The readiness map then reports, for
13 of the 46 dependencies, *"all candidates were tested and contradicted. This
is not a missing answer but a wrong one"* — about columns a person would
confirm in a second. A dirty row is evidence that the data needs care. It is
not evidence that the column is not what it plainly is.

This matters more than T9. The product's guarantee is stated in one direction:
the AI cannot make a claim believed. Run B shows the other direction is open —
through the same door, the choice of check — and that it is the more common
event on real-shaped data: 15 wrongful contradictions against 1 wrongful
promotion.

## The predictions, scored

| | prediction | outcome |
|---|---|---|
| Q1 | the model names `completed_vessel_actual_build_cost` | **right** |
| Q2 | the tool does not ask which of the four cost types was meant | **right** — no card names the alternatives; the choice surfaces only as an unconfirmed classification |
| Q3 | B2: no answer type, and no dependency list invented | **half right** — no type for either; but the model drafted 10 and 13 dependencies anyway |
| Q4 | 30–60 hypotheses, 20–55 checks | **right** — 37 and 46 |
| Q5 | the five obvious object bindings appear | **right** — five of five |
| Q6 | the role call completes, ≥ 25 of 41 roles | **right, and understated** — 41 of 41, no retry |
| Q7 | `journal` is not elected | **right** — both candidates fail `balance` |
| Q8 | `intercompany` is not elected | **right** — though by a generic reconciliation, not by `ic_symmetry` |
| Q9 | ≥ 60% of checks pass, mostly uninteresting | **wrong** — 38% (17 of 45). The landscape is dirtier and the checks sharper than assumed |
| Q10 | the vacuity guard fires at most twice | **right on the count (0), wrong on the reason** — the model did write filters, four of them |
| Q11 | audit: 2–6 coincidental promotions, none false | **wrong twice** — 1 narrower-than-stated, 1 false; the coincidental `month` reference never appeared |
| Q12 | `blocked`, ≤ 5 of 46 satisfied | **right** — 0 of 46 |
| Q13 | ≥ 20 question cards | **right** — 71 |
| Q14 | the three zero-overlap joins stay silent | **right** — none produced a claim, a check or a question from the data |
| Q15 | the unapproved alias mapping is relied on and never flagged | **wrong, both halves** — nothing was promoted through `project_aliases`, and the yard e-mails yielded *"alias table has not been approved"* as an anchored claim |
| Q16 | the `Read_Me_First` warnings never become a claim | **wrong** — *"Danzig and Gdansk denote the same location"* was proposed from the profiled values |
| Q17 | duplicate, unapproved and unattributed cost lines are not surfaced from the data | **wrong on duplicates** (found, with a question card); **right on the one unapproved row**; the blank project was found only through a document |
| Q18 | board-report disagreement not detected as a disagreement | **half right** — the tool caught figures that disagree *inside* the document (3.60 vs 2.70 for one vessel) and a workbook total quoted against a chart; it never computed a workbook sum to set against a board figure |
| Q19 | 8–20 document claims, all quotes valid, ≥ 3 rule links | **wrong on both counts** — 28 claims (all quotes valid), 1 link |
| Q20 | ≥ 3 refusals from the layout classifier | **wrong** — 0 refusals; three claims anchor to passages classed as charts |

Eleven right, three half, six wrong.

### What the misses say

- **The documents carried more than the data, and the tool read them well.**
  Predictions Q15–Q17 assumed silence where the PDFs turned out to speak: the
  unapproved alias table, the misposted engine instalment (EUR 195,448 to the
  wrong vessel), the December labour batch missing from the ledger, the
  duplicated steel invoice. 28 claims, every one quoted verbatim.
- **And then almost none of it connects.** One link from 28 document claims to
  11 open rule items. The reading is good; the routing to what the answer
  depends on is not.
- **Zero-overlap silence is confirmed (Q14).** Where the PDFs do not mention a
  broken join, nothing does.

## What broke quietly

1. **A check that crashes leaves no trace on its claim.** One reconciliation
   failed to execute — a text note in a numeric column
   (`revenue_2025_eur`). It appears in the run report as skipped; the claim
   stays `proposed` with no evidence saying a test was attempted and could not
   run. Silence, in the one place the product promises none.
2. **A dependency list is drafted for a question with no answer type** (Q3).
   The guide's types did not fit, the model said so, and still proposed 10 and
   13 dependencies of its own. They are marked as proposed, not contract — but
   the stated design is that the list comes from the guide, never from what the
   model remembers.
3. **Three document claims anchor to chart passages**, which the design says
   may not corroborate. Whether they were allowed to here was not checked.

## What Run B did not do

- **It did not score trap recall.** That needs the answer key.
- **It did not test the human loop** on this landscape. With 13 dependencies
  marked all-contradicted, it is not clear a person could reach `ready` here at
  all, and that is worth finding out.
- **It says little about the guide.** The vessel guide is the simulated output
  of the guide-builder experiment and reuses finance laws that do not fit a
  shipbuilder. Q7, Q8 and Q13 follow from that as much as from the engine.
- **One run, one model pair.** No repeat, so no estimate of run-to-run noise.

## Afterwards — what was changed because of this run

Added 2026-10-03, after the blind results above were committed. Nothing above
this heading was edited.

All four engine issues were fixed the same day: a filtered pass writes its
limit onto the claim; a generic check carries no weight on a role binding in
either direction; a check that cannot run leaves an inconclusive record; an
unevaluated formula is declared by the reader and an all-empty measure reads as
nothing tested. The store this run left behind is kept unedited in `run-b/`.

Judging that same store again with the fixed engine — stages 2 and 4 only, no
model call, so the proposals are identical:

| | on the day | re-judged |
|---|---|---|
| claims contradicted | 28 | 12 |
| role candidates contradicted | 17 | 2 (both `journal`, by the balance law) |
| dependencies marked "all candidates contradicted" | 13 | 1 |
| the false promotion (T9) | unqualified | carries "holds only where status = 'delivered' — tested on 3 of 5 rows" |
| the pivot reconciliation | contradicted | inconclusive: nothing was tested |
| the check that crashed | no trace | an inconclusive record on its claim |

The verdict is `blocked` either way. What changed is what a person is told on
the way there: 35 open choices instead of 13 dead ends.

Scored against the answer key, separately and afterwards:
`results-run-b-scored.md`.
