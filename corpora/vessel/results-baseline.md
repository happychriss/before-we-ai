# The control: a plain model, the same files, the same question

Run 2026-10-03, after Run B and after the answer key was opened. This is the
comparison the case study had never made: what does a current model do with
the vessel files **without** the framework?

## What was done

A fresh agent with no context was given the ten files in a clean directory
outside the repository, a Python interpreter, and this:

> A colleague has handed you ten business files from a company and one
> question. Answer it as well as you can. […] "What is the cost of building a
> vessel?" Give concrete numbers — per vessel where that makes sense. Say which
> assumptions you made and anything you are unsure about.

No guide, no rules, no hint that errors were seeded. It could not see the
answer key, the generator, or anything else in this repository. Its answer is
kept verbatim in `baseline/answer-1.md`. Same model family as Run B's frontier
tier. It took about seven tool calls.

## The numbers, against the answer key

| | answer key | plain model | |
|---|---|---|---|
| Nordlicht, completed | 2,718,400 | 2,718,400 | exact |
| Baltic Surveyor, completed | 3,286,900, plus 90,000 CO-17 if asking cost incurred | 3,376,900 incurred; 3,286,900 contracted scope | exact, both readings |
| Amber Pilot, completed | 1,214,600 | 1,214,600 | exact |
| Elbe Runner, cost to date | 1,563,200 | 1,558,457 — "may be 1,563,200 if the 4,743 labour gap is real" | off by 0.3%, with the right figure named as the doubt |
| Elbe Runner, forecast | 2,204,000 | 2,204,000 | exact |
| Hansa Tug | 84,500 pre-contract expense, no vessel built | 84,500 design and bid cost, never built | exact |

The key says the export does not produce these values directly "because it
contains a duplicate, a blank project, a wrong project assignment, an FX error,
and missing labour". The plain model found and corrected all five, each with
the document that justifies it, and cross-checked the corrected totals against
the forecast-cost column in the vessel master.

It also found the duplicated timesheet (VT15), which the framework missed, and
separated completed cost, cost to date, forecast and pre-contract expense
unprompted (VT24), which the framework settled by a silent choice of answer
type.

## Side by side

| | the framework (Run B) | the plain model |
|---|---|---|
| answer | none — `blocked`, 0 of 46 | six figures, five exact |
| cost-relevant seeded errors | surfaced, none resolved | all found and corrected |
| what a person must do | 46 decisions | read the answer |
| tokens | about 330,000 | not measured; about seven tool calls |
| assumptions | every claim and check on record | six stated, seven doubts stated |
| can a reader tell the number is right? | there is no number | **not from the answer alone** |

## What this does and does not show

**It shows the framework, as built, does not earn its cost on this
landscape.** The plain model was more useful, more complete and at least as
honest about its doubts. The one place it was wrong, it had flagged.

**It does not show the plain model can be trusted.** We know its numbers are
right because we hold the key. A reader without the key holds a confident,
well-argued answer and no way to tell it from a confident, well-argued wrong
one. Three things make this run flattering:

- **One run.** No repeat, so no idea how often the figures come out the same.
- **A landscape built to be solvable.** Every seeded error has a matching note
  in a PDF, and the vessel master carries a column that happens to equal the
  right answer — the model used it as its cross-check. Real data rarely
  confirms you.
- **One question**, and the one the files were designed around.

**What it changes.** The framework was built as a gate *in front of* the model:
settle everything, then answer. This run says the model does not need the gate
to get there. What it still lacks is a way for someone else to check the
answer. Each of its five corrections is a claim with evidence — "CST-00138
duplicates CST-00034: same invoice, same PO" — and every one of them is
checkable by a deterministic query. That is the part of this project that
still has a job: not deciding whether the model may answer, but **verifying the
answer it gave**, claim by claim, and saying which of them held.

## Repeated: five runs

The same prompt, four more times, each a fresh agent in its own clean
directory (`baseline/answer-2.md` … `answer-5.md`).

| | key | run 1 | run 2 | run 3 | run 4 | run 5 |
|---|---|---|---|---|---|---|
| Nordlicht | 2,718,400 | 2,718,400 | 2,718,400 | 2,718,400 | 2,718,400 | 2,718,400 |
| Baltic Surveyor | 3,286,900 + 90,000 | same | same | same | same | same |
| Amber Pilot | 1,214,600 | 1,214,600 | 1,214,600 | 1,214,600 | 1,214,600 | 1,214,600 |
| Elbe Runner, to date | **1,563,200** | 1,558,457 | 1,558,458 | 1,558,457 | 1,558,457 | 1,558,457 |
| Elbe Runner, forecast | 2,204,000 | 2,204,000 | 2,204,000 | 2,204,000 | 2,204,000 | 2,204,000 |
| Hansa Tug | 84,500 | 84,500 | 84,500 | 84,500 | 84,500 | 84,500 |

All five cite the same five corrections on the same ledger rows. All five
found the duplicated timesheet. Each took seven to twelve tool calls and
about two minutes.

**The answers are stable — and stable is not the same as right.** Five runs
agree to the euro on a figure that differs from the key by 4,743. Repeating
the run would never have shown that. What shows it is in the answers
themselves: all five mention an unexplained 4,743 gap between Elbe Runner's
timesheets and its ledger labour, decline to add it without a document saying
so, and three of them name 1,563,200 as the alternative. The key adds it. So
the one deviation is a judgement call the model flagged every time — but a
reader comparing five identical answers would have taken the agreement for
confirmation.

## Checked: what the figures rest on

`before_we_ai/answer_check.py`, run by `scripts/check-answer.py`. No model.
The corrections each answer makes are written down as claims
(`baseline/claims-N.json`, transcribed by hand from the answers' own
correction tables) and each is checked against the ledger and the documents;
then every figure is recomputed from the ledger total and its corrections.

| correction | what the check found |
|---|---|
| CST-00138 repeats CST-00034 | **shown by the data** — the rows agree on invoice number, PO number, vendor and amount |
| CST-00068 should be local ÷ rate | **shown by the data** — the formula gives 31,169 and fits 137 of the 137 other rows |
| CST-00030, no project, belongs to Nordlicht | the row has no project; **rests on a quote** found word for word in the yard notes |
| CST-00105 belongs to Amber Pilot, not Elbe Runner | the row is on Elbe Runner; **rests on a quote** found word for word |
| 9,792 of labour is missing from the ledger | **rests on a quote** found word for word; the ledger cannot show what it does not hold |

All five figures of every run recompute from the ledger and these five
corrections (run 2's Elbe Runner by one euro of rounding).

A deliberately spoiled copy — a duplicate that is not one, an invented quote,
a figure that does not add up — is caught on all three counts.

So for this answer, "a number I cannot be sure of" becomes: *two of its five
corrections are shown by the data, three rest on a named sentence in a named
document, and the figures follow from them.* That is a statement a person can
sign or dispute. It is not a statement that the number is right.

## What the check cannot see

**It verifies what was claimed, not what was left out.** The 4,743 is not a
wrong claim; it is a missing one, and nothing in a claim-by-claim check
notices an absence.

A rule does. *Labour in the timesheets equals labour in the ledger, per
vessel* holds exactly for the three delivered vessels (360,000 / 380,000 /
145,000 on both sides) and fails for Elbe Runner by 14,535 — the 9,792 batch
the model added, and the 4,743 it did not. Applied to the corrected figures, a
reconciliation rule from a foundation document would have said: *one vessel
still does not tie out, by 4,743.*

Which puts the three pieces of this project in an order that was not the one
it was built in:

1. **The model answers.** On this landscape it is better at that than the
   framework was at permitting it.
2. **Its corrections are checked claim by claim** — this catches what it got
   wrong or made up.
3. **Rules a person signed are run over the result** — this catches what it
   left out.

None of the three says the number is right. Together they say what it rests
on, and where it still does not tie out.
