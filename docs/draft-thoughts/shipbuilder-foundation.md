# A foundation document for a shipbuilder — what it would look like

**Status:** experiment, 2026-10-03. Not a domain pack the engine can load. A
paper version, measured by hand against the vessel landscape, to answer one
question before anything is built: *is the tool defensive because it lacks
domain knowledge, and would a real foundation document change that?*

**Not blind.** This was written after Run B and after the answer key was
opened. A real foundation document is written by someone who knows the
business and has *not* seen the data. The identities below are ordinary
project-accounting knowledge, but the numbers are an upper bound, not a test.

## The idea

Run B settled 0 of 46 dependencies by machine. The reason is not that the data
is unreadable. It is that only a *domain law* may say "this column is that
thing", and the vessel guide borrowed three ledger laws from finance that a
shipbuilder's files do not fit. Everything else was marked "a person decides".

A foundation document is where a person who knows the business writes down
**what must be true of the data if it is what it claims to be** — once, in
general, before any file is seen. The machine then applies it. That keeps the
original intent intact: no AI judges whether data is fit for AI. A human
authorises the rule; arithmetic applies it.

The form that works is an **identity that ties several columns together**. If
`reported amount = local amount ÷ rate` holds on 137 of 138 rows, then all
three columns are what they are taken to be — nobody has to confirm them one
by one — and the 138th row is a finding.

## The laws, as a controller would sign them

Each is stated for the business, names what it settles, and was measured on
the vessel data. "Holds" uses a rounding tolerance a person would accept (one
euro, or half a percent).

| | law | settles | holds on |
|---|---|---|---|
| S1 | **A build is listed once.** Every vessel build has exactly one master record with a stable key. | `build`, `build.authoritative_key` | 5 of 5 |
| S2 | **A delivered vessel has an acceptance date, and only a delivered one does.** | `build.completion_status`, `build.acceptance_date` | 5 of 5 |
| S3 | **Every cost line belongs to a known build.** | `journal`, `journal.build_ref` | 137 of 138 |
| S4 | **Reported amount = local amount ÷ FX rate.** | `journal.amount_local`, `journal.amount_reporting_currency`, `journal.currency` | 137 of 138 |
| S5 | **A cost line has one transaction id.** | `journal.doc_ref` | 138 of 138 |
| S6 | **A supplier invoice number appears once per supplier.** | `journal.invoice_ref` | 136 of 138 |
| S7 | **Every cost line is booked by a group company.** | `journal.entity` | 138 of 138 |
| S8 | **Labour cost = hours × hourly rate.** | `labour_allocation`, its cost and its source reference | 47 of 47 |
| S9 | **Every time entry resolves to a build**, directly or through the alias table. | `labour_allocation.labour_build_ref` | 47 of 47 |
| S10 | **Overhead pool = rate × base quantity.** | `overhead_pool`, its amount and base quantity | 3 of 3 |
| S11 | **Recharge = cost base × (1 + markup).** | `intercompany.ic_cost_base`, `intercompany.ic_markup_rate` | 5 of 5 |
| S12 | **What one company charges, the other books.** | `intercompany` | **3 of 5** |
| S13 | **Every recharge belongs to a known build.** | `intercompany.ic_build_ref` | **4 of 5** |

## What that does to the 46 dependencies

With the rule *a law that holds on at least 95% of rows settles its roles, and
every exception is reported*:

| | on the day | re-judged | with this document |
|---|---|---|---|
| settled by the machine | 0 | 0 | about 22 |
| left to a person | 46 | 46 | about 24 |

Of the 24 that remain, 11 are the rules — which cost categories count, which
FX source, how overhead is allocated, what to do with an unsigned change order.
Those are policy and should be asked. The other 13 are things no arithmetic
can show: which column is the cost category, which is the approval flag, and
whether the alias table has been approved.

## The exceptions are the seeded errors

This is the part worth noticing. The rows where a law does *not* hold are not
noise:

- S3, the one line with no build — the class invoice with a blank project.
- S4, the one line — PLN multiplied by the rate instead of divided.
- S6, the two lines — the duplicated steel invoice.
- S12, two of five — the missing receiving-side booking and the EUR 1,400
  difference. **This law fails, and should: the intercompany object stays
  open.**
- S13, one of five — a recharge with no build.

So the same document that unblocks 22 dependencies also produces the findings
list. The two were never in tension. What put them in tension was treating one
exception as a verdict on the column.

## What Run B got wrong that this explains

On the day, the labour table was *contradicted* in 41 of 47 rows. With a
tolerance of one euro, S8 holds in 47 of 47. The model had proposed exactly
this identity as a check — and S4, S10 and S11 too. It found the right rules.
They carried no authority, because no person had declared them, and they ran
with a tolerance of one cent.

## What the engine would need

Three changes, none of them large on its own:

1. **Laws declared in the guide, not written in Python.** One generic
   row-identity check — *left expression = right expression per row, within a
   tolerance* — parameterised from the foundation document. Today a new law is
   a SQL template, a prepare function and a vocabulary entry.
2. **A law holds or fails by share, not by a single row.** Above a declared
   threshold it settles its roles and lists its exceptions as findings; below
   it, the object stays open, as `intercompany` does here.
3. **A tolerance that belongs to the law.** One euro for a cost line is a
   domain fact, like the law itself.

## What this does not solve

- **It is the standing trap, in a friendlier costume.** The project's own rule
  says data can refute an interpretation and never confirm one. A law that
  holds says the columns are arithmetically tied, not that they mean what the
  guide says. A decoy export that copies the real ledger passes every one of
  these. Finance already accepts this trade for `balance`; this document would
  accept it thirteen more times.
- **The threshold is a judgement.** 95% is not derived from anything.
- **Someone has to write it.** That is the real cost of adoption, and it is
  paid per industry, not per customer.
- **"Is the data ready for AI" still has no general answer** — only "ready for
  this question, under these laws, with these exceptions".
