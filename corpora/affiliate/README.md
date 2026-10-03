# The affiliate landscape

**Entirely synthetic.** The country, the currency, the group, the affiliate,
every vendor, person, product and number are invented. General finance and ERP
knowledge only.

## The company

**Meridia Pharma Norvania d.o.o.** is the sales and distribution company of the
**Meridia Pharma Group** in the Republic of Norvania — about 60 people, a
warehouse, a small quality laboratory, a finance team of three. The group
reports in EUR; the affiliate keeps its books in Norvanian krona (NVK, roughly
11–12 NVK per EUR during the year). Norvania has one standard VAT rate of 20 %.

The affiliate does not run the group ERP. It has its own local system, its own
chart of accounts and its own habits. It buys finished medicines from the
group's supply company, **Meridia Supply Chain B.V.**, invoiced in EUR, and
buys packaging, laboratory, office and logistics materials from local and a few
foreign vendors.

## The situation

Fiscal year 2025 (1 January – 31 December). On **1 July 2025** the affiliate
changed two things at once: the numbering scheme of its documents, and the
version of its mapping from local accounts to group accounts. The earlier
months were not restated. The delivery date promised by the vendor is recorded
in purchase order lines only from that change onward. The accountant who looked
after the purchasing ledger left at the end of July.

Every month the affiliate's data is extracted into the group data warehouse.
What is in `data/` is that delivery for the slice purchase order → goods
receipt → vendor invoice → payment, with the clearing account between receipt
and invoice, as it stood after the December close. Group finance wants to run
analyses on it.

## The nine extracts

| file | holds |
|---|---|
| `vendors.csv` | vendor master, including the group supply company |
| `materials.csv` | material master with base unit, order unit and the conversion |
| `po_header.csv`, `po_lines.csv` | purchase orders: vendor, currency, material, quantity, price, delivery date |
| `goods_receipts.csv` | goods receipt lines against order lines, including reversals |
| `inv_header.csv`, `inv_lines.csv` | vendor invoices and credit notes, with and without a purchase order |
| `payments.csv` | payment runs and the documents they settled |
| `gl_lines.csv` | ledger lines of the inventory, clearing, vendor and difference accounts — automatic and manual postings, with document type, user and text |
| `acct_mapping.xlsx` | local account → group account, with validity dates |
| `fx_rates.csv` | monthly rates NVK per EUR for 2025 |

CSV files are UTF-8, comma-separated, with a header row. The column names are
the ones the local system exports. The extraction selects purchase orders that
had any movement or open item in 2025 and takes all their documents, so a few
receipts and invoices are dated late 2024. The ledger extract covers 2025 for a
range of accounts only; payment documents are not repeated in it.

## The three documents

| file | what it is |
|---|---|
| `posting_instruction_local.pdf` | the affiliate's local posting instruction for purchasing, goods receipt and invoice verification (version of March 2023) |
| `group_accounting_manual_ch7.pdf` | extract of the group accounting manual: goods receipt, invoice verification, the clearing account, manual journals |
| `handover_note_accounting.pdf` | the handover note the departing accountant wrote in July 2025 |

## The three questions group finance asks

1. What is the balance of goods received but not yet invoiced at year end, in EUR?
2. Which vendor invoices were paid without a goods receipt, and for how much?
3. How much of the purchase volume was delivered late?

## Layout and the reading rule

```
affiliate/
  manifest.yaml     sources with sha256, questions, pointers
  data/             the nine extracts and the three documents, as delivered
  answer-key/       DO NOT READ
  generator/        DO NOT READ
```

Whoever implements or tests against this landscape reads this file,
`manifest.yaml` and `data/`, and nothing else in this directory. The answer key
and the generator are committed so the landscape is reproducible; opening
either ends a blind evaluation for good.
