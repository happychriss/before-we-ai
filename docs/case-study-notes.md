# Case study notes — what was done and what it showed

A working record, started 2026-10-03, of the day the project was reassessed.
Not the write-up: the material for it. Every claim here points at a file in
this repository that holds the evidence.

## Where it started

The project had been built as a **gate in front of a language model**: track
what is known, assumed and unknown about unfamiliar data; let the model only
*propose*; let deterministic checks or people *promote*; and say `ready`,
`ready with limitations` or `blocked` before any answer is computed. About
16,000 lines, 875 passing tests, one synthetic finance landscape it grew up
on, and nothing run since 2026-08-20.

The owner's question: is it worth continuing?

## What was done, in order

1. **A sceptical audit** of the code and a look at the market. The build was
   sound and honest about its limits. The headline guarantee had a hole (a
   model-written filter or an empty table made a check pass, and a pass
   promotes), the standing metric measured authorship rather than
   correctness, and "the model proposes, a person approves" had become
   ordinary in other products. → decision: **a case study, not a product.**
2. **Moved out of the container** into this repository, with a fresh history.
3. **A demo web app** (`ui/`, `scripts/ui.sh`): the run step by step, what is
   believed and who changed it, the decisions that move the verdict.
4. **Closed the hole** — a filter must name a column; a check that tested
   nothing is inconclusive.
5. **Run B**: the first live model run on a landscape the tool did not grow
   up on, with predictions committed first
   (`corpora/vessel/predictions-run-b.md`, `results-run-b.md`,
   `results-run-b-scored.md`).
6. **Four engine changes** Run B asked for.
7. **Foundation documents**: domain knowledge a person signs and a machine
   applies (`before_we_ai/foundation/`, `foundations/`).
8. **The control**: a plain model, no framework, same files, same question —
   five times (`corpora/vessel/results-baseline.md`).
9. **Checking an answer** somebody else computed
   (`before_we_ai/answer_check.py`).
10. **The data binding itself**: finding arithmetic ties without a model
    (`foundation/discover.py`, `foundation/match.py`).
11. **A third landscape**, meant to be realistic where the second was not
    (`corpora/affiliate/`, predictions committed before its data existed).

## What it showed

### 1. The gate blocks, and blocking is trivially safe

On the vessel landscape the framework's verdict on *"What is the cost of
building a vessel?"* was `blocked`, with 0 of 46 dependencies settled and 46
decisions left to a person. That is the correct verdict by its own rules. It
is also what a tool that always says no would have said. "False promotion: 0"
is satisfied by doing nothing.

### 2. The model cannot promote — but it could contradict

The guarantee was stated in one direction. Run B showed the other was open,
through the same door: the model chooses the check. Fifteen role candidates
that were plainly the right column were marked `contradicted` by checks about
something else, several on rounding to whole euros. Fixed: a general check on
a role candidate now carries no weight either way. Re-judging the recorded run
took contradictions from 28 to 12.

### 3. A promoted claim was false as stated

One of eleven. The model wrote a filter (`status = 'delivered'`) into a check;
the test narrowed and the claim did not. Fixed: a filtered pass writes its
limit onto the claim.

### 4. A plain model answered the question the gate would not allow

Given the ten files and the question, with no framework: six figures in about
two minutes, **five exact against the answer key**, the sixth off by 0.3% with
the right figure named as its doubt. It found and corrected every seeded error
that mattered for the answer.

### 5. Stable is not right

Five runs agreed to the euro — including on the one figure that differs from
the key. Repetition would never have shown that. Agreement between runs was
agreement on a judgement call.

### 6. And nobody without the key could tell

The model's answer reads as confidently when it is right as it would when it
is wrong. That part of the original worry survives intact.

### 7. What a deterministic check can add *after* the answer

Each of the model's corrections is a claim. Two of five were shown by the data
alone (a duplicate; a formula that fits every other row). Three rested on a
sentence that had to exist, word for word, in a named document. Every figure
recomputed from the ledger and those corrections. A deliberately spoiled copy
was caught. What the check cannot see is an *omission* — and a signed
reconciliation rule can.

### 8. Domain knowledge was the missing input, and it fits in a document

A foundation document written by an agent that saw no data: 32 rules, six
tolerance *classes* instead of a tolerance per rule, a minimum share, the
parameters only a company can supply. Applied to the vessel data, 13 rules
had data to run on, 9 held, and 9 of 46 dependencies settled with nobody
asked. The rows where rules broke were the seeded errors.

Two things it showed about tolerances: classes work; and one generic class was
wrong for this company (it rounds labour cost to whole euros, the document
allowed five cents). That is a line a reader ticks "ours is different".

### 9. Binding is where judgement comes back in

To apply a rule something must say which column is which. A person can; a
model can; arithmetic can for some. Trying every combination of numeric
columns against a few rule shapes found the real ties on the vessel data with
no coincidences. But shape alone names nothing: a rule about contract prices
bound itself to an invoice's net and VAT and "held" on 24 of 24 rows. Names
have to agree too, and which of two amounts is the home amount cannot be
decided by arithmetic at all.

### 10. The vessel landscape was built to be solved

Every seeded error had a note in a PDF explaining it, and a master-data column
held the right answer. Much of finding 4 is owed to that. The affiliate
landscape exists because of it.

## What the project is now

The three parts ended in an order that is not the one they were built in:

1. **The model answers.**
2. **Its corrections are checked claim by claim** — catches what it got wrong
   or invented.
3. **Rules a person signed are run over the data and the result** — catches
   what it left out.

None of the three says a number is right. Together they say what it rests on
and where it does not tie out. The question moved from *may the model answer?*
to *can someone sign this answer?*

What stays from the original design: claims with statuses, append-only
evidence, who may confirm what, deterministic checks, staleness. What goes:
the verdict as a gate, the model as the main source of claims, and code as the
home of domain rules.

## What is not established

- Whether any of this holds on realistic data. That is what the affiliate
  landscape is for; its predictions are in
  `corpora/affiliate/predictions-run-a.md`.
- Whether a weaker model would have failed where the current one succeeded.
  The "tipping point" is an impression; only one side of it was measured.
- Whether a foundation document given to a model as plain context does as
  much as the same rules run mechanically.
- Who binds. The vessel binding was written by hand by someone who had seen
  the data (`corpora/vessel/foundation-binding.yaml`).

## Where things are

| | |
|---|---|
| live state and next steps | `meta/memory.md` |
| the three landscapes | `corpora/finance/`, `corpora/vessel/`, `corpora/affiliate/` |
| Run B, as recorded | `corpora/vessel/run-b/` |
| the plain model's five answers | `corpora/vessel/baseline/` |
| foundation documents | `foundations/shipbuilding/`, `foundations/procure-to-pay/` |
| reading and applying them | `src/before_we_ai/foundation/` |
| checking an answer | `src/before_we_ai/answer_check.py`, `scripts/check-answer.py` |
| the demo web app | `ui/`, `scripts/ui.sh` |
| live model runs | `scripts/run-landscape-live.py` (spends an API key) |
| drafts and scenarios | `docs/draft-thoughts/` |
