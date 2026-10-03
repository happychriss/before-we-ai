# The affiliate landscape — scored against the answer key

Written after `results-run-a.md` was committed blind (commit `fe124b8`). The
owner authorised opening `answer-key/ANSWER_KEY.md` on 2026-10-03. Nothing in
the blind results was changed afterwards. The landscape is no longer blind to
whoever wrote or reads this.

## The short version

**The plain model got all three questions right, in all three runs, and found
every seeded error.** The landscape was built to be the hard one — no document
explains any error — and it was not hard for the model.

**The low-AI flow found less than half of what the model found**, and most of
what it reported was ordinary business.

## The three questions

| | answer key | run 1 | run 2 | run 3 |
|---|---|---|---|---|
| 1. goods received, not invoiced | **EUR 220,881.36** (or 194,414 if the December write-off is accepted) | 220,881 | 220,881 | 220,881 |
| …split group / third parties | 106,399.56 / 114,481.80 | 106,400 / 114,482 | same | same |
| 2. paid without a goods receipt | **9 invoices, NVK 474,552**; leaving out the one permitted advance is acceptable if stated | 8, NVK 442,482, advance stated separately | 6, NVK 331,842, the two twice-paid duplicates listed separately | 8, NVK 442,482, advance stated separately |
| 3. delivered late | **about 21%** of the value received on orders from 1 July; first half-year not answerable | 22.2%, second half only | 21.8%, second half only | 22.2%, second half only |

- **Question 1: exact, three times.** Reaching it needs eleven corrections the
  key lists — a duplicate invoice hiding an open quantity, three receipts on
  the wrong line or order, an order entered in the wrong currency, four faulty
  manual clearings, two receipts posted twice — plus a view on the write-off.
  All three runs made them, and all three named the write-off as the
  judgement call, which is what the key says a good answer does.
- **Question 2: the same nine invoices in all three runs.** NVK 442,482 is the
  key's 474,552 less the permitted advance (32,160) plus the 90 by which one
  payment differs from its invoice — a difference the key itself calls
  undecidable. Runs 1 and 3 are right as the key defines it. Run 2 found the
  same invoices and drew the line one group earlier.
- **Question 3: right, three times** — within the key's two percentage points,
  with the half-year restriction stated and the overwritten dates named as the
  reason the figure is a lower bound. Run 3's EUR 858,041 equals, to the euro,
  the key's figure against the dates *first promised*, which the key says are
  not in the data.

## The seeded cases

Checked by whether each answer cites the records the key names for the case;
the surrounding sentences were read for the less obvious ones.

| | cases in the key | found by run 1 | run 2 | run 3 |
|---|---|---|---|---|
| kind 2 — real errors, no note anywhere | 18 | 18 | 18 | 18 |
| kind 3 — the data cannot decide | 5 | 5 | 5 | 5 |

Including the ones no rule could have pointed at: a clearing journal posted
with the wrong sign, one with two digits transposed (NVK 36), one posted to the
inventory account, and a mapping row that starts a month late.

**Kind 1 — legitimate events that look like errors.** No run treated the 130
invoices without a purchase order as "paid without receipt", none counted the
permitted advances, none called the monthly rent a duplicate, and each
recognised the two invoices whose receipt sits on the wrong line. I did not
check all 450-odd kind-1 order lines against each answer; I found no false
alarm in what I read.

## The low-AI flow against the same key

Of the 18 real errors, the rules' exception lists touch:

| rule | exceptions | what they are |
|---|---|---|
| R24 received at most what was ordered | 6 order lines | **all real**: both double receipts and all three misplaced receipts (5 cases) |
| R11 clearing account is mapped | 1 account, 373 ledger lines | **real**: the missing mapping row |
| R22 a manual journal names an order | 1 | **real**: the clearing without an order reference |
| R05 one group account per local account | 1 | the double mapping — a kind-3 case |
| R08 an invoiced order line has a receipt | 24 order lines | 14 are group deliveries in transit at year end — ordinary; the rest are the nine invoices and the two misplaced receipts |
| R26 invoiced at most what was received | 119 order lines | 70 are invoices in pieces against receipts in cartons — ordinary; the three duplicate invoices and the unit slip are in there, unmarked, among them |
| R10 a reversal points to a real receipt | 75 | none — a key format in the binding |

So: **7 of 18 errors clearly surfaced**, another 4 buried in a list of 119, and
7 not touched at all — both currency slips, four of the five faulty clearings,
the mapping gap of one month. Counting order lines rather than causes, about
one exception in ten points at an error.

## The predictions, final

| | prediction | outcome |
|---|---|---|
| A1 | the runs differ on question 1 by more than 2% | **wrong** — identical |
| A2 | at most one run within 1% of the truth | **wrong** — all three exact |
| A3 | question 2 overstated by every run | **wrong** — none overstated |
| A4 | all runs notice the first half-year cannot be measured | right |
| A5 | at most half the real errors found; false alarms in every run | **wrong** — all 18 found, no false alarm seen |
| A6 | ties found in at least three extracts | **wrong** — one |
| A7 | a true rule falls below the threshold through legitimate complexity | right — on units of measure |
| A8 | fewer than three in ten exceptions are real errors | right — about one in ten |
| A9 | the mapping gap is missed by at least one model run | **wrong** — found by all, with the second gap no rule saw |
| A10 | the clearing reconciliation is not found by the tie search | right — and not runnable as a rule either |
| A11 | corrections can be neither shown by data nor tied to a quote | not tested |
| A12 | no arm gets question 1 exactly; model plus rules beats either | **wrong** — the model alone is exact; the rules add nothing |

Four right, seven wrong, one untested. Every wrong prediction is wrong in the
same direction: **I underestimated the plain model and overestimated what
deterministic rules would add.**

## The bar

1. **Arm C surfaces fewer real errors than arm B — fired.** 7 to 11 of 18,
   against 18 of 18.
2. **More than nine in ten exceptions are ordinary events — at the line.**
   About one in ten is real.
3. Arm A cannot read the landscape — did not fire.

## What to make of it, and what not

**What it says.** On two synthetic landscapes — one with explanatory notes,
one without — a current model given the files and a plain question produced
the right figures, found the seeded errors, separated them from ordinary
business, and said where it was guessing. A framework of claims, checks and
signed rules did not improve on that in either case, and cost far more work.

**What it does not say.** Three reasons this result is weaker than it looks:

- **The landscape was written by the same kind of model that solved it.** An
  agent asked to seed "realistic errors" seeds the errors a model thinks of —
  and a model looking for errors looks for the errors a model thinks of. Every
  seeded case in the key comes with a clean detection rule. Real mess is not
  generated from a list.
- **It is small.** 6,674 rows can be read in full. A real affiliate's year is
  two or three orders of magnitude larger, and what a model can inspect row by
  row stops being what it can inspect.
- **We know the answers are right only because we hold the key.** This has not
  changed since the vessel run and is the one finding that survives every
  experiment: the model's right answer and a wrong one read the same.

The honest next test is not a fourth synthetic landscape. It is data whose
mess nobody designed.
