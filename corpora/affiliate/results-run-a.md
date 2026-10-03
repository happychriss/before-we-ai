# The affiliate landscape — results, blind

Run 2026-10-03. Predictions were committed before the data existed
(`predictions-run-a.md`, commit `adf91c0`) and have not been edited. These
results are **blind**: nothing under `answer-key/` or `generator/` has been
opened. Whatever needs the key to judge is marked *needs the key* and left
open.

## Verdict

**The low-AI flow did not earn its place on this landscape, and the plain
model did not behave the way I predicted.**

- The machine's own search for arithmetic ties — the piece meant to replace a
  person's or a model's judgement in binding — found **one** tie in twelve
  tables and could not name it.
- With a binding written by hand, the foundation document's rules surfaced
  real things. **Every one of them is also in all three of the plain model's
  answers**, which contain a good deal more.
- The three plain-model runs agreed with each other far more than predicted:
  the same year-end balance to the euro.

Whether the model's agreed answer is *right* cannot be said blind. That is the
one thing these results cannot tell, and the reason the key matters.

## Arm A — the deterministic read

Fine. 14 sources, 12 tables, 0 claims. The local ERP's names arrive as they
are: `amt_lc`, `qty_bu`, `vend_no`, `dlv_compl`. Bar 3 did not fire.

## Arm B — the plain model, three times

Three fresh agents, a clean directory outside the repository, a short handover
text, the three questions. Seven to eight minutes each, about 30 tool calls.
Answers kept verbatim in `baseline/answer-1.md` … `answer-3.md`.

| | run 1 | run 2 | run 3 |
|---|---|---|---|
| 1. goods received, not invoiced, year end | EUR 220,881 | EUR 220,881 | EUR 220,881 |
| …of which group / third parties | 106,400 / 114,482 | 106,400 / 114,482 | 106,400 / 114,482 |
| …the ledger as delivered | 182,460 | 182,460 | 182,460 |
| 2. paid without a goods receipt | 8 invoices, NVK 442,482 | 6 invoices, NVK 331,842 | 8 invoices, NVK 442,482 |
| 3. delivered late | 22.2% of the measurable volume | 21.8% | 22.2% |
| …measurable share of the year | 41% | 41% | 41% |

- **Question 1: identical to the euro**, each run arriving there through its
  own list of corrections — double receipts, receipts posted to the wrong
  line, an order read in the wrong currency, a duplicate invoice hiding an
  open quantity, a written-off balance put back. All three say that two of
  those are judgement calls worth about EUR 31,000–63,000.
- **Question 2: the same six invoices in all three.** Two runs add two
  duplicate invoices that were paid a second time; one lists them separately.
  The difference between "6" and "8" is a definition, not a finding. All three
  also set aside permitted advance payments and invoices whose receipt sits on
  the wrong order line.
- **Question 3: all three refuse the full year**, measure only orders from
  1 July, and say that overwritten delivery dates hide some delays.
- The three answers cite 73 to 81 record ids each; **58 are cited by all
  three.**

## Arm C — the low-AI flow

### The machine binding itself

`foundation.discover` over all twelve tables: **one tie** —
`net_val = qty * price` on order lines, 609 of 609. No coincidences.

Nothing else, and the reason is the landscape's realism rather than a bug.
These are normalised ERP extracts: net amounts sit on invoice lines and gross
and tax on the header; the exchange rate is in its own table; the unit
conversion is in the material master; debit and credit are an indicator beside
an unsigned amount. The relations that matter cross tables. The vessel
landscape was spreadsheets with everything on one row — which is why the
search looked so good there.

The one tie stayed **unclaimed**: the document's rule for it has four terms
(`quantity × price ÷ price unit`) and the search knows three. Every other line
of the proposed binding was by column name only, and several were wrong
(`invoice_id` → the invoice *date* column). It also cannot express that an
order line is two columns.

So the binding was written by hand (`foundation-binding.yaml`), from column
names, code values and the account descriptions — without knowing which
records are wrong. It needed three things the engine did not have until today:
a key built from several columns, a row filter to say which ledger lines are
the clearing account, and a sign taken from a debit/credit indicator.

### The rules, with that binding

31 rules in the document. 19 had data to run on.

| | rule | records | |
|---|---|---|---|
| R01–R03 | order line, receipt line, invoice are unique | all | hold |
| R05 | one group account per local account and period | 126 of 128 | holds — **1 exception: account 1450 mapped twice from 1 July** |
| R06, R07, R09 | receipt → order line, invoice line → order line, payment → invoice | all | hold |
| R08 | an invoiced order line has a goods receipt | 717 of 741 | holds — **24 order lines, 13 invoices, 9 of them paid** |
| R10 | a reversal points to a real receipt | 0 of 75 | fails — *an artefact of the binding: the reference names the document, the rule expects the line* |
| R11 | a clearing account is mapped to the group | 1,456 of 1,829 | **fails — account 2815 has no mapping row at all (373 lines)** |
| R12 | order value = quantity × price ÷ price unit | 609 of 609 | holds |
| R14, R20, R21, R25 | signs, reversals name what they reverse, manual journals carry a text | all | hold |
| R17 | posted on or after the invoice date | — | not evaluable: the rule language cannot compare dates |
| R22 | a manual journal names an order line | 52 of 53 | holds — **1 manual journal with no order** |
| R24 | received at most what was ordered | 603 of 609 | holds — **6 order lines over-received** |
| R26 | invoiced at most what was received | 481 of 600 | fails — *119 lines, invoice quantities a thousand times the received ones: the two extracts count in different units* |

Twelve rules had no data: the extract carries no header net amount, no
exchange rate or local amount on invoices, no settled amount, no open-balance
table. Among them the one that matters most — **receipts minus invoices equals
the clearing account, per order line (R31)** — because invoice lines carry no
local-currency amount.

### What the rules found, against what the model found

| the rules' finding | in the plain model's answers? |
|---|---|
| the six invoices paid with no receipt (inside R08's nine) | all six, in all three runs |
| the other three paid invoices in R08 | all three, in all three runs — and classified: one permitted advance, two with the receipt on the wrong line |
| six over-received order lines (R24) | all six, in all three runs |
| account 1450 mapped twice (R05) | all three runs |
| account 2815 not mapped (R11) | all three runs |
| the manual journal with no order (R22) | not checked by id |

**Nothing the rules surfaced was missed by the model.** The model's answers go
further on every question, and they sort the rules' raw exceptions into what
is an error and what is ordinary business — which a rule cannot do.

Two of the three failing rules failed for reasons that are not errors in the
data: a key format and a unit of measure. Both would be fixed by a better
binding, which is to say by more hand work from someone who knows the system.

## Arm D — checking the answers

**Not run.** `answer_check` models an answer as one ledger total per group
plus corrections to rows of that ledger. The year-end balance here is the sum
of open positions per order line across two accounts, after corrections that
touch receipts, invoices and manual journals in different tables. The check
does not fit, and bending the answers into its shape by hand would have
measured my transcription. Prediction A11 is therefore untested.

## The predictions, scored blind

| | prediction | outcome |
|---|---|---|
| A1 | the three runs differ on question 1 by more than 2% | **wrong** — identical to the euro |
| A2 | at most one run within 1% of the truth | *needs the key* |
| A3 | question 2 overstated by every run | *needs the key*; the runs differ only in whether twice-paid duplicates count |
| A4 | all runs notice the first half-year cannot be measured | **right** |
| A5 | at most half the real errors found; ≥ 3 legitimate events flagged per run | *needs the key* |
| A6 | ties found in at least three extracts, plus two coincidences | **wrong** — one extract, no coincidences |
| A7 | a true rule falls below the threshold through legitimate complexity | **right, for a different reason** — "invoiced at most what was received" fails on units of measure, not on partial deliveries; "received at most what was ordered" held, because the document's author wrote "at most" and gave it a 10% class |
| A8 | fewer than three in ten exceptions are real errors | *needs the key*; two rules alone contribute 194 exceptions that are artefacts |
| A9 | the mid-year mapping gap is caught by a rule and missed by a model run | **wrong** — caught by the rule and by all three runs |
| A10 | the clearing-account reconciliation is not found by the tie search | **right, and worse** — it cannot be run even as a stated rule: the extract lacks the amounts |
| A11 | most corrections can be neither shown by data nor tied to a quote | *not tested* |
| A12 | no arm gets question 1 exactly; model plus rules comes closer than either | *needs the key*; blind, the rules added nothing to the model's answer |

Three right, three wrong, six open.

## The bar

1. **Arm C surfaces fewer of the real errors than arm B** — *needs the key to
   count, but everything visible says it fired*: every rule finding is inside
   the model's answers, and the model reports corrections no rule points at.
2. **More than nine in ten exceptions are ordinary events** — *needs the key*.
   By record count it is close: 567 of the 599 exception records come from
   three causes (an unmapped account, a unit mismatch, a key format).
3. **Arm A cannot read the landscape** — did not fire.

## What this run says, before the key

- **The self-binding idea does not survive normalised data.** It was developed
  on spreadsheets and it works on spreadsheets.
- **A foundation document plus a hand binding is real work for a result the
  model already delivers.** Its rules did find true things. They found nothing
  additional.
- **The plain model was consistent here too** — more than on a landscape with
  no explanatory notes it had any right to be. Either the answer is right, or
  three runs share one way of being wrong. On the vessel landscape it was the
  second: five runs agreed on a figure that was off. The key decides.
