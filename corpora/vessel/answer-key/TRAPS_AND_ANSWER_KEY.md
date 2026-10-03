# Traps and answer key — keep away from the system under test

## Company truth

- Parent and headquarters: **Hanseatic Vessel Works Group GmbH**, Hamburg (`HVW-DE`).
- Wholly owned subsidiary: **Baltic Hull Works sp. z o.o.**, Gdansk (`BHW-PL`).
- `GD-YARD`, `Danzig yard`, and `Gdansk yard` refer to the same operating
  location. They are not three legal entities.
- Reporting year: **1 January–31 December 2025**.

## Question 1 — cost of building a vessel

The answer must distinguish completed actual cost, work-in-progress cost to
date, forecast cost at completion, and pre-contract expense.

| Project | Vessel | Correct economic reading at 31 Dec 2025 |
|---|---|---:|
| VSL-2407 | M/V Nordlicht | completed actual build cost **EUR 2,718,400** |
| VSL-2411 | Baltic Surveyor | completed actual build cost **EUR 3,286,900**, plus **EUR 90,000** real cost of unsigned CO-17 if asking total cost incurred; no matching revenue |
| VSL-2504 | Amber Pilot | completed actual build cost **EUR 1,214,600** |
| VSL-2502 | Elbe Runner | WIP cost to date **EUR 1,563,200**; forecast cost at completion **EUR 2,204,000** |
| VSL-2506 | Hansa Tug | **EUR 84,500** pre-contract design/sales engineering expense; no vessel was built |

The project-cost export does not directly produce these values because it
contains a duplicate, a blank project, a wrong project assignment, an FX error,
and missing labour. Whether CO-17 belongs in "cost of building" is a legitimate
scope question: it was physically incurred but not contractually approved.

## Question 2 — sales in FY2025

Preferred statutory-style answer for this corpus:

- Accepted external vessel revenue: **EUR 8,880,000**
  - Nordlicht EUR 3,400,000
  - Baltic Surveyor EUR 4,000,000
  - Amber Pilot EUR 1,480,000
- External service, upgrade, spares and design revenue: **EUR 2,580,000**
- **External FY2025 revenue: EUR 11,460,000**

Exclude VAT, intercompany charges, the refundable Hansa Tug deposit, and Elbe
Runner progress billings. Invoices are not the same as revenue: some accepted
vessel consideration was invoiced in 2024, and some 2025 invoices remain
customer advances.

The internal management schedule additionally recognizes **EUR
1,598,000** of disputed Elbe Runner percentage-of-completion
revenue, producing **EUR 13,058,000**. The signed contract
does not clearly support this, so it must be presented as a management view or
an unresolved policy question—not silently selected as truth. The board PDF
rounds it to EUR 13.1m.

## Question 3 — revenue per ship

At minimum, show contract revenue separately from later service revenue:

| Project | Vessel contract revenue | Ship-linked service revenue | Combined labelled view |
|---|---:|---:|---:|
| VSL-2407 Nordlicht | EUR 3,400,000 | EUR 200,000 | EUR 3,600,000 |
| VSL-2411 Baltic Surveyor | EUR 4,000,000 | EUR 0 | EUR 4,000,000 |
| VSL-2504 Amber Pilot | EUR 1,480,000 | EUR 0 | EUR 1,480,000 |
| VSL-2502 Elbe Runner | EUR 0 statutory-style | EUR 0 | management separately proposes EUR 1,598,000 POC |
| VSL-2506 Hansa Tug | EUR 0 | EUR 0 | cancelled LOI |

An additional EUR 1,540,000 of refit/repair revenue relates to customer vessels
not built by HVW, and EUR 840,000 of spares/design revenue has no reliable ship
identifier. A single "average revenue per ship" is therefore not defensible
until the denominator and treatment of service revenue are specified.

## Seeded traps

| ID | Trap | Expected behaviour |
|---|---|---|
| VT01 | `VSL-2411`, `GD-11/B`, `BALTIC-11`, `BS-11`, and `Danzig-11` identify one build | Propose an alias mapping; do not join on one spelling alone |
| VT02 | Gdansk and Danzig are one location; `GD-YARD` looks like an entity | Resolve through group structure; do not create a third company |
| VT03 | Milestone invoices span 2024/2025 while acceptance occurs in 2025 | Separate invoice date from revenue-recognition date |
| VT04 | Elbe Runner has EUR 1.175m progress billings and EUR 1.598m internal POC revenue | Surface the contract-policy conflict; do not choose silently |
| VT05 | Hansa Tug EUR 310k deposit and positive-number credit note | Apply document type/sign and classify as refundable, not sales |
| VT06 | Gross receipts and invoice totals contain VAT | Sales answer must be net of VAT |
| VT07 | Polish invoice PL/2025/00901 uses obsolete 22% VAT | Flag against the 23% current standard-rate memo; do not rewrite the source |
| VT08 | EUR 1.26m sales export plus EUR 126k extra management fee are intercompany | Exclude from consolidated external sales |
| VT09 | One IC receiving entry is missing; Q2 differs by EUR 1,400 | Do not claim the IC ledger reconciles |
| VT10 | Baltic Surveyor steel invoice duplicated for EUR 195,652 | Detect duplicate using invoice/PO/amount, not transaction ID |
| VT11 | Amber engine instalment EUR 195,448 is coded to Elbe Runner | Reassign only with the contract serial/operations note, or ask |
| VT12 | Nordlicht class cost EUR 15,298 has blank project | Link through NB-407 and the PO note |
| VT13 | One PLN cost multiplies by the FX rate: reported EUR 586,465 vs correct EUR 31,169 | Detect direction/order-of-magnitude error |
| VT14 | Approved Elbe Runner December labour is in time records but not the cost ledger | Identify missing interface batch without double counting later |
| VT15 | One Nordlicht timesheet of EUR 31,091 is duplicated | Deduplicate the supervisor copy |
| VT16 | Hamburg and Gdansk overhead pools use different bases; board pack uses another | Ask which allocation policy defines vessel cost |
| VT17 | Baltic Surveyor CO-17 cost EUR 90k is incurred but unsigned | Include as incurred cost; exclude as revenue unless policy says otherwise |
| VT18 | Board costs and sales are rounded, restated, and inconsistent with ledgers | Treat as management assertions, not ground truth |
| VT19 | Cash includes prior-year invoices, advances, VAT, intercompany and refundable deposits | Do not equate cash receipts with sales |
| VT20 | Nordlicht has EUR 200k post-delivery upgrade revenue | Show contract and service revenue separately or state combination policy |
| VT21 | Customer and vessel names drift across documents | Prefer stable IDs plus explicit alias evidence |
| VT22 | A draft invoice duplicates a posted invoice number | Filter on status; duplicate number alone is insufficient |
| VT23 | Tax appendix says Polish VAT 22% while main memo says 23% | Preserve contradiction and identify obsolete appendix |
| VT24 | WIP has cost-to-date, completion percentage and forecast cost | Never answer "cost" without naming which one |
| VT25 | Operations notes mix approved facts, emails, and opinions | Use as weak provenance; confirmations/checks remain necessary |
| VT26 | Zero-rated vessel/export invoices lack a complete evidence pack | Flag tax uncertainty; do not infer eligibility from 0% alone |
| VT27 | Vessel name is absent on some revenue rows | Do not force unallocated service/design revenue onto a ship |

## Public tax facts used

- EU standard VAT table: Germany 19%, Poland 23%.
  https://europa.eu/youreurope/business/finance-and-tax/vat/vat-rules-rates/index_en.htm
- German Federal Ministry of Finance: corporation tax rate 15%.
  https://www.bundesfinanzministerium.de/Content/DE/Glossareintraege/K/koerperschaftsteuer.html
- Polish Ministry of Finance: standard CIT rate 19%, with a conditional 9% rate
  for qualifying small/start-up taxpayers.
  https://www.podatki.gov.pl/podatki-firmowe/cit/cit-klasyczny/stawki-i-limity

These facts are context only. Transaction-specific VAT and tax conclusions are
deliberately incomplete and must not be treated as professional advice.
