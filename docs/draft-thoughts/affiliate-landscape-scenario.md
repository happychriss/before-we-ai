# A third landscape: the affiliate — scenario for review

**Status:** draft for the owner to check for realism, 2026-10-03. Nothing is
built. Once agreed, a separate agent builds the data and the answer key from
this page; whoever implements and tests does not read the key.

**Entirely synthetic.** General finance and ERP knowledge only. No real
company's rules, account numbers, vendors or data.

## Why a third landscape

The vessel landscape turned out to be built to be solved: every seeded error
has a note in a PDF explaining it, and a master-data column holds the right
answer. A plain model got it right five times out of five. That says little
about data where nobody wrote down what went wrong. This landscape is meant
to be realistic in the way that matters: **not everything fits, and nobody
explains why.**

## The setting

A pharmaceutical group with strict, SOX-style finance rules. One small
country affiliate — a sales and distribution company, about 60 people — runs
its **own local ERP**, not the group system. It has local habits, local
account numbers, and a finance team of three that fixes things by hand when
they do not fit. Its data is extracted monthly into the **group data
warehouse**, and group finance wants to run analyses on it.

- The affiliate reports in a local currency; the group reports in EUR.
- It buys finished medicines **intercompany** from the group's supply company
  (transfer prices, goods in transit at year end) and buys locally from third
  parties (logistics, packaging, lab and office supplies).
- One fiscal year. Mid-year the affiliate changed something structural — a
  new numbering scheme or a new chart-of-accounts mapping — and did not
  restate the earlier months.

## The slice: goods receipt and invoice verification

Purchase order → goods receipt → vendor invoice → payment, and the clearing
account between receipt and invoice (goods received, not yet invoiced). Plus
a thin slice of **manual postings**: the affiliate clears differences on that
account by hand.

## What arrives in the warehouse

About nine extracts, a few thousand rows in total:

| extract | holds |
|---|---|
| vendors | vendor master, including the intercompany supplier |
| materials | material master with order unit, base unit and conversion |
| purchase orders | header and lines: quantity, price, currency, vendor |
| goods receipts | receipt lines, including reversals |
| vendor invoices | header and lines, including credit notes and invoices without a purchase order |
| payments | payment runs and what they settled |
| ledger lines | postings on the clearing account and neighbouring accounts, automatic and manual, with document type, user and text |
| account mapping | local account → group account, with a validity date |
| exchange rates | monthly, local currency to EUR |

And three documents: the affiliate's local posting instruction (a PDF, partly
out of date), an extract of the group accounting manual, and a handover note
from a finance colleague who left.

## The questions group finance asks

1. **What is the balance of goods received but not yet invoiced at year end,
   in EUR?** Determinable, with care.
2. **Which vendor invoices were paid without a goods receipt, and for how
   much?** Determinable, and smaller than it first looks.
3. **How much of the purchase volume was delivered late?** Only partly
   determinable: the promised delivery date was not recorded before the
   mid-year change. The right answer says so and gives the half-year it can.

## Three kinds of disorder

The generator is told the *kinds*. It chooses the instances, and they are not
disclosed to the implementer.

1. **Real complexity that looks like an error.** Partial deliveries, several
   invoices for one order, reversals and re-postings, credit notes, order unit
   against base unit, price changes agreed after the order.
2. **Real errors with no note explaining them.** Duplicated invoices under
   slightly different references, receipts booked to the wrong order line, a
   currency slip, manual clearings posted to the wrong account or with no
   reference to an order, a mapping gap after the mid-year change.
3. **Things the data cannot decide.** Two sources that disagree with no way to
   tell which is right; information that was never recorded.

Beyond the seeded cases the data should carry ordinary noise that is in no
answer key at all: inconsistent spelling, blank optional fields, free text in
the wrong place.

**The documents do not annotate the errors.** They describe how things should
be done and how the affiliate actually does them. They may contradict each
other. They never say "posting X is wrong".

## Deliberately left out

Service purchase orders, consignment stock, tax detail beyond one standard
rate, batch and serial tracking, the payment-terms and discount logic beyond
one simple case, anything about revenue.

## What the generator delivers

- the extracts and documents, as a company would hand them over;
- an answer key: the three answers, each seeded case with its kind, and for
  kind 3 the range within which the truth lies;
- a self-check that the clean base data is internally consistent before the
  disorder is applied, so that every inconsistency in the result is one that
  was put there.

## For the owner to check

1. Is the setting right — a small distribution affiliate with its own ERP,
   intercompany supply plus local purchasing?
2. Are the nine extracts what a group warehouse would realistically receive?
   Anything typical missing, anything unrealistic?
3. Are the three questions ones group finance would actually ask?
4. Which kinds of disorder are missing that you see in practice?
5. Which country and currency? A small non-euro country gives the FX angle;
   a fictional one avoids real tax rules.
6. Is the size right, or already too much?
