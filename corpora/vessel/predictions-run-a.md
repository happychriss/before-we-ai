# Run A — predictions, written before the run

Pre-registration. Everything below was written and committed **before** the
vessel landscape was ingested even once, because a prediction made before a run
is evidence and the same sentence written afterwards is a story. The results
land in `results-run-a.md`; this file is never edited after its commit — if a
prediction is wrong, that is the finding.

Run A is the deterministic half only: declare the ten sources, scan them, build
column profiles and the candidate matrix, chunk the four PDFs. **No model call,
no API key, no answer key.** Nothing here is scored against a trap.

## What was and was not seen first

Stated because the value of this run depends on it.

**Seen:** `corpora/vessel/README.md` (fictional company, Hamburg HQ and a
Gdansk yard, seed 20250802, the three questions), the file names and sizes, the
domain guide at `guide/simulated-domain-guide.yaml`, and — through an unrelated
tool's log earlier in the same session — the extracted **text of the four
PDFs**. That last one is accidental and is recorded rather than hidden. It does
not break the blindness rule, which covers `answer-key/` and `generator/`: the
source documents are the thing under test and are meant to be read. It does
mean the PDF-side predictions below are better informed than the spreadsheet
ones, and the honest reading of any PDF prediction that comes true is "of
course it did".

**Not seen:** the six `.xlsx` files, in any form. Not one cell. Every
spreadsheet prediction is inference from file names and the domain.

**Not opened, and not to be opened:** `answer-key/TRAPS_AND_ANSWER_KEY.md` and
`generator/generate_corpus.py`.

## The bar: what counts as failure

Run A fails if any of these happen. They are the reason to run it before
building anything else.

1. Any of the ten sources does not ingest at all.
2. Any table ingests with zero columns profiled, or with every column typed as
   text when the file plainly holds numbers.
3. PDF chunking raises, or produces zero passages for any of the four
   documents.
4. Two consecutive runs over untouched bytes produce different chunk ids,
   different profile ids, or a different candidate matrix. Determinism is the
   contract; a second landscape is a fair place to find out it was accidental.
5. The scan creates a claim. It must create exactly zero — nothing is proposed
   before a model runs.

Anything else is a finding, not a failure.

## Predictions

**P1 — all ten sources ingest, and the ugliness is in the spreadsheets.**
Nothing about the file list suggests an unreadable format. Expected trouble is
shape, not encoding.

**P2 — at least two of the six workbooks have more than one sheet**, so the
count of ingested tables is higher than six. `01_company_and_vessel_master` in
particular reads like several master tables in one book (companies, yards,
vessels, projects).

**P3 — merged or two-row headers cost at least one table its column names.**
The finance landscape's Excel normalization was built against German business
spreadsheets, and this is another one. I expect at least one table where the
first data row is really a header continuation, and column names like
`Unnamed: 3` or a value where a name belongs. **This is the prediction I most
expect to be wrong in the interesting direction** — either the normalizer
handles it cleanly (good, and it generalises), or it produces something worse
than a wrong name, like a silently dropped row.

**P4 — column names are mixed German, Polish and English within one landscape,
and possibly within one table.** The corpus has a Hamburg HQ and a Gdansk yard,
so `Projekt`, `Kwota`, `amount`, `Kostenstelle` can all be column names in the
same workbook. Nothing in the ingestion cares, but it is the first real test of
whether anything downstream quietly assumed one language.

**P5 — two currencies, and no column that says which.** PLN and EUR both
appear. I expect at least one amount column where the currency is implied by
the file, the sheet, or a neighbouring column rather than stated per row. This
is the shape of the finance landscape's F17/F19 FX traps in a different
costume, and it is exactly the kind of thing that cannot be settled by
measurement.

**P6 — the four PDFs chunk, and the board report is the hard one.** Document 07
carries tables and what a chart-detector will read as chart fragments; the
per-vessel revenue/cost/margin table is the content that matters and the format
that extraction handles worst. I expect it to chunk without raising and to
produce passages that a reader can follow, with at least one table arriving as
a run of loose values rather than rows.

**P7 — the candidate matrix will be thin, and that is the real finding.** The
same physical vessel appears as `HH-407`, `NB-407`, `Nordlicht`, `AP-77`,
`VSL-2504`, `GD-11/B`, `Danzig-11`. Value-overlap containment finds joins
between columns that *share literal values*; identifiers that mean the same
thing in different formats share nothing. So I predict **markedly fewer strong
candidates than the finance landscape's 20**, and I predict that the joins a
human would care about most are among the ones not found.
If that comes true it is not a bug in the matrix — the matrix measures overlap
and reports it, which is all it claims — but it does say something load-bearing
about the tool: on a landscape where identity is expressed inconsistently, the
measured stage contributes much less, and proportionally more rests on the
model's proposals and on clarification questions. That would be the most
important sentence to come out of Run A.

**P8 — zero claims and zero evidence of any promoting kind.** The structural
invariant does not depend on the landscape, so this is a prediction I expect to
be boring, and I would want to know immediately if it were not.

## What Run A explicitly cannot answer

The negative control — vessel data against the plain packaged `finance` pack,
expecting no candidate to win a role — **cannot run here.** Binding a candidate
to a role is a V2 model call. It belongs to Run B, with the next recording
session. Correcting an earlier claim of my own: that check is not free and not
offline.

Nothing in Run A says whether the tool is *right* about this landscape. It says
whether the tool can read it at all. That is the only question worth asking
first, and it is the one that has never been asked.
