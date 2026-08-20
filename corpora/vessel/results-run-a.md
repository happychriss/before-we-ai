# Run A — results

Run 2026-08-20 against `corpora/vessel/`, deterministic stages only: declare
ten sources, scan, profile every column, build the candidate matrix, chunk the
four PDFs. No model call, no API key, no answer key opened. Predictions were
written and committed first — `predictions-run-a.md`, commit `c205c19` — and
that file has not been edited since.

Reproduce: the run script is `scripts/run-landscape.py` (see below).

## Verdict

**The tool reads a landscape it did not grow up in.** All ten sources ingest,
20 tables come out of six workbooks, every column is profiled, all four PDFs
chunk, and the scan creates zero claims. None of the five failure conditions
fired.

Two real limitations surfaced that the finance landscape structurally could
not show, and one of them is the kind this product exists to prevent. They are
findings, not failures — see *What broke quietly*.

## What came out

| | |
|---|---|
| sources declared | 10 |
| tables ingested | 20 (six workbooks, 2–5 sheets each) |
| columns profiled | 162 |
| documents chunked | 4, 8 pages, 36 passages |
| candidate pairs examined | 5,597 → 128 kept at containment ≥ 0.5 |
| normalization declarations | 46, all `actor=system` |
| **claims created by the scan** | **0** |

Column value classes as measured: 114 text, 21 integer-like, 11 decimal-like,
10 date-like, 6 empty.

Documents: `07_board_management_report` 12 passages (6 text, 3 table, 3 chart);
`08_tax_and_transfer_pricing_memo` 11 (5/2/4); `09_contracts_change_orders` 7
(3/1/3); `10_yard_operations_notes` 6 (3/0/3).

**Determinism holds.** Two independent runs over untouched bytes produce
byte-identical stdout, a byte-identical candidate matrix, and byte-identical
profiles once the per-run ULIDs and creation timestamps are masked. Chunking
each PDF twice yields identical ids, text and kinds.

## The predictions, scored

| | prediction | outcome |
|---|---|---|
| P1 | all ten ingest, trouble is shape not encoding | **right** |
| P2 | ≥2 workbooks have several sheets | **right**, and understated — all six do; 20 tables from 10 sources |
| P3 | merged/two-row headers cost a table its column names | **right**, and in the worse way it warned about — see below |
| P4 | column names mixed German, Polish, English | **wrong**. Every one of the 162 column names is English snake_case. This landscape is *less* linguistically hostile than the one the tool grew up on |
| P5 | two currencies, no column saying which | **wrong**. Currency is explicit nearly everywhere: `currency`, `pln_per_eur`, `reported_eur`, `amount_bank_currency` + `currency_per_eur`, and a `monthly_fx_rates` table |
| P6 | PDFs chunk; the board report is the hard one | **right on both halves** — it chunks, and it is the only document producing 3 table passages plus 3 chart fragments from 2 pages |
| P7 | candidate matrix markedly thinner than finance | **wrong, and this is the most useful miss** — see below |
| P8 | zero claims, no promoting evidence | **right** |

Five of eight. The three misses are worth more than the five hits, because each
one says something the finance landscape could not.

### P7 was wrong, and why that matters

The prediction was that inconsistent identifiers (`HH-407` / `NB-407` /
`Nordlicht` / `VSL-2504` / `GD-11/B` / `Danzig-11`) would starve a matcher that
works on literal value overlap. Instead: **128 candidates from 5,597 pairs**,
77 of them at containment 1.0, and 106 spanning two different workbooks.

The honest comparison, same tool, same threshold: finance keeps 445 of 11,001
pairs (4.0%), vessel 128 of 5,597 (2.3%). So the *rate* is roughly half — the
prediction had the direction right — but "markedly thinner" was meant as
"starved", and 128 usable candidates including 106 cross-workbook ones is not
starved. The prediction was wrong about what mattered.

The reason is a design choice by whoever built the landscape: workbook 01
carries a `Project_Aliases` sheet mapping `project_id` ↔ `yard_job_no` ↔
`contract_reference` ↔ `vessel_name`. 18 of the 128 candidates run through it.
The identity problem is real, and the corpus contains its own bridge.

Two things follow, and the second is uncomfortable:

- The measured stage does more here than expected, so less rests on the model
  than the prediction assumed. Good.
- **The bridge is marked `mapping_status`, and the sheet is hidden** — the
  landscape's own `Read_Me_First` says *"the Project_Aliases sheet is hidden
  because it was marked 'work in progress'"*. The candidate matrix cannot know
  that. It measures overlap and reports it, which is all it claims; but 18 of
  its strongest candidates rest on a mapping the business has not approved.
  Whether that reaches a human as a question is a V2/readiness matter and is
  Run B's business — the point for now is that a strong measured signal and a
  trustworthy one are not the same thing, and Run A is where the difference
  became visible.

## What broke quietly

Both of these are pre-existing product behaviour, not vessel-specific bugs.
The finance landscape hides both because its numeric data lives in DuckDB files
that carry real types, while this landscape is spreadsheets end to end.

### 1. A formula column arrives empty, and nothing says so

`02_project_cost_ledger_2025 → Pivot_Export.reported_eur_total` profiles as
`value_class: empty`, 6 rows, 6 nulls. The column is not empty. It holds
`=SUMIF(Cost_Ledger!E:E, A2, Cost_Ledger!O:O)` in every row, with **no cached
value**, so the reader returns `None`. Same in
`04_sales_invoices_and_credit_notes → Management_Recognition`, two cells.

This is the failure class the product exists to prevent, in miniature. Nothing
is promoted and no wrong answer is produced — the invariants hold. But a
profile saying *empty* is a positive statement about the source, and it is
false: the truth is *"this column holds a formula this reader cannot
evaluate"*. A human reading the profile concludes the business has no data
there. **A missing capability should arrive as a declaration, not as a
plausible-looking zero.**

Fix, when it is scheduled: the Excel reader should detect a formula cell with
no cached value and record a system declaration per affected column, so the
column reads as *unevaluated*, not as *empty*. Note that a workbook last saved
by Excel usually does carry cached values — this corpus was written
programmatically. That makes it a narrower bug and a fair warning: any file
produced by a script rather than by Excel behaves this way.

### 2. `min` and `max` are lexicographic on every spreadsheet number

`cost_ledger.amount_local` reports `min = 106861.97, max = 97643`. Both are
wrong as numbers, because the column is `VARCHAR` in the catalog and DuckDB's
`min`/`max` compare text. Every integer-like and decimal-like column from a
spreadsheet is affected — which here is all of them, since the landscape has no
database.

Not new: finance's `buchungen_report.betrag_eur` reports
`min = 1001810.17, max = 991090.22` and has done all along. The finance
landscape simply never made it matter, because its ledgers come from
`erp.duckdb` with native `DOUBLE` columns and correct extremes. **This is
exactly what a second landscape is for**: not to find new bugs, but to stop an
existing one from staying invisible.

Nothing downstream currently promotes on `min`/`max`, so no verdict is wrong
today. It is a wrong number in a profile a human reads.

### 3. A prose sheet ingests as a table

`01_company_and_vessel_master → Read_Me_First` becomes a 6-row, 6-column table
with the columns `master_data_export`, `master_data_export_2` … `_6`, five of
them entirely null. The sheet is a cover note, and its content is exactly the
kind that matters: *"Danzig and Gdansk are both used in legacy systems"*,
*"yard job numbers and contract references are not project IDs"*.

P3 predicted this class and it landed. The pipeline treats the cover note as
data rather than as a document, so the warnings inside it never reach the
document path that would anchor them. That is a routing question — is a text
sheet in a workbook a table or a document? — and it is the first time the
question has come up.

## What Run A did not do

The negative control (vessel data against the plain packaged `finance` pack,
expecting no candidate to win a role) **did not run and could not**: binding a
candidate to a role is a V2 model call. It belongs to Run B.

Nothing here says whether the tool is *right* about this landscape. It says the
tool can read it. That was the question, and it had never been asked.
