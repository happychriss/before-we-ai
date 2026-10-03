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
kept verbatim in `baseline/answer.md`. Same model family as Run B's frontier
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
