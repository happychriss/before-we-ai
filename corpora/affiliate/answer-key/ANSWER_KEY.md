# ANSWER KEY - affiliate landscape (Meridia Pharma Norvania d.o.o., FY2025)

**Do not read if you implement or test against this landscape.** Written by `generator/generate_affiliate.py` (seed 20251003); every number below is computed, not typed.

Conventions: amounts in NVK unless stated; EUR at the December month-end rate 11.8260 NVK per EUR (group manual 7.4) unless stated. Order lines are written `po_no/pos`. "True" means what the generator knows happened; "establishable" means what a careful analyst can derive from `data/` alone.

## Question 1 - goods received but not yet invoiced at year end, in EUR

**True answer: NVK 2,612,143.00 = EUR 220,881.36** (third parties NVK 1,353,861.75 = EUR 114,481.80; group supply company NVK 1,258,281.25 = EUR 106,399.56), on 20 order lines.

Definition used (group manual 7.3): the sum of order lines whose clearing balance is a credit - received, invoice still expected. Debit lines (invoiced or paid, not received) are not netted. Remainders that were legitimately cleared by manual journal (no invoice expected) are not part of it.

**Establishable from the delivered data: EUR 220,881.36 if the December write-off K3-1 is treated as not permitted (it breaks group manual 7.5: far above the limit, item under 180 days but no vendor confirmation in the data), or EUR 194,414.26 if it is accepted. A good answer gives the range EUR 194,414.26 to EUR 220,881.36 and names the write-off as the reason.** Tolerance for scoring: an answer within about 2 % of either end, with the corrections named, is right; the uncorrected figures below are wrong.

What the data shows before any correction:

| figure | NVK | EUR |
|---|---:|---:|
| net balance of account 2810 at 31.12. | 300,491.16 | 25,409.37 |
| net balance of account 2815 at 31.12. | -1,748,608.94 | -147,861.40 |
| net balance 2810 + 2815 (negative = credit) | -1,448,117.78 | -122,452.04 |
| sum of order lines with credit balance (by assignment field, both accounts) | 2,157,774.50 | 182,460.21 |
| sum of order lines with debit balance | 707,469.82 | 59,823.26 |
| clearing postings without order reference (debit) | 2,186.90 | 184.92 |
| quantity view: (received - invoiced quantity) x order price, recorded currency | 2,489,688.85 | 210,526.71 |

Reconciliation from the recorded sum of credit lines to the true figure:

| step | case | NVK | EUR |
|---|---|---:|---:|
| recorded credit lines | | 2,157,774.50 | 182,460.21 |
| remove effect of | A-1 duplicate invoice hides a later receipt | 58,400.00 | 4,938.27 |
| remove effect of | B-1 receipt on wrong line | -17,640.00 | -1,491.63 |
| remove effect of | B-2 receipt on wrong order | -36,400.00 | -3,077.96 |
| remove effect of | B-3 receipt on wrong line (wrong price) | -36,000.00 | -3,044.14 |
| remove effect of | C-1 EUR order recorded in NVK | 391,063.40 | 33,068.10 |
| remove effect of | D-2 clearing posted to inventory | -2,460.00 | -208.02 |
| remove effect of | D-3 clearing without order reference | -2,186.90 | -184.92 |
| remove effect of | D-4 clearing with wrong sign | -4,472.00 | -378.15 |
| remove effect of | D-5 clearing with transposed amount | -36.00 | -3.04 |
| remove effect of | F-1 receipt posted twice | -202,200.00 | -17,097.92 |
| remove effect of | F-2 receipt posted twice | -6,700.00 | -566.55 |
| remove effect of | K3-1 December write-off (undecidable) | 313,000.00 | 26,467.11 |
| **true** | | **2,612,143.00** | **220,881.36** |

Reasoning a careful analyst needs: (1) read 2810 and 2815 together and per order line, because orders invoiced before and received after 1 July have their legs on different accounts, and the assignment field changed format on 1 July; (2) include the opening items (document type SV) and the receipts of December 2024; (3) take only credit lines; (4) honour correct manual clearings but test each one against the subledger; (5) test each open line against quantities: received, reversed, invoiced, credited, in order units; (6) translate at the December month-end rate. The EUR items are carried in NVK at the booking rate of the receipt month; that is the ledger value and is what is translated.

True open lines (credit balance in the true world):

| order line | vendor | NVK |
|---|---|---:|
| P25-0199/20 | Meridia Supply Chain B.V. | 448,740.74 |
| P25-0203/10 | Sciomed Instruments Kereven GmbH | 349,956.30 |
| P25-0184/20 | Meridia Supply Chain B.V. | 330,166.15 |
| P25-0076/10 | Termo Log Savrin d.o.o. | 239,800.00 |
| P25-0199/10 | Meridia Supply Chain B.V. | 231,464.38 |
| P25-0184/10 | Meridia Supply Chain B.V. | 151,519.33 |
| P25-0224/20 | Kartonaza Velmir d.o.o. | 146,563.56 |
| P25-0222/10 | Brenko Pak d.o.o. | 123,600.00 |
| P25-0184/30 | Meridia Supply Chain B.V. | 96,390.65 |
| P25-0222/20 | Brenko Pak d.o.o. | 78,600.00 |
| P25-0203/20 | Sciomed Instruments Kereven GmbH | 77,507.10 |
| P25-0076/20 | Termo Log Savrin d.o.o. | 73,200.00 |
| P25-0224/30 | Kartonaza Velmir d.o.o. | 61,594.23 |
| P25-0130/10 | Kartonaza Velmir d.o.o. | 58,400.00 |
| P25-0169/30 | Senzor Tehnika Olvar d.o.o. | 53,400.00 |
| P25-0224/10 | Kartonaza Velmir d.o.o. | 26,772.00 |
| P25-0218/30 | Senzor Tehnika Olvar d.o.o. | 26,739.54 |
| P25-0215/10 | Paleta Drovnik d.o.o. | 19,788.00 |
| P25-0218/20 | Senzor Tehnika Olvar d.o.o. | 13,536.90 |
| P25-0218/10 | Senzor Tehnika Olvar d.o.o. | 4,404.12 |

## Question 2 - vendor invoices paid without a goods receipt

**True answer (paid by 31.12.2025, no receipt recorded by 31.12.2025): 9 invoices, NVK 474,552.00 gross = EUR 40,832.68.** In three groups:

(a) Ordered goods invoiced and paid, no receipt: 5 invoices, NVK 279,672.00 = EUR 24,076.76.

| inv_doc | vendor | vend_ref | order | gross as recorded | paid on | paid as recorded | true gross NVK | EUR (booking rate of payment month) | note |
|---|---|---|---|---:|---|---:|---:|---:|---|
| 51007419 | Paleta Drovnik d.o.o. | R/31244/25 | 45002121 | 69,840.00 NVK | 2025-03-27 | 69,840.00 NVK | 69,840.00 | 6,162.81 | no receipt recorded; goods never arrived |
| 51007634 | Uredska Oprema Hrist d.o.o. | INV-2025-33438 | 45002270 | 12,672.00 NVK | 2025-07-17 | 12,762.00 NVK | 12,672.00 | 1,102.73 | no receipt recorded; payment amount differs from invoice, see K3-3 |
| E25-00116 | Termo Log Savrin d.o.o. | F-014922 | P25-0045 | 21,960.00 EUR | 2025-09-11 | 21,960.00 NVK | 21,960.00 | 1,892.37 | no receipt recorded; invoice header carries the wrong currency, see C-2 |
| E25-00313 | Senzor Tehnika Olvar d.o.o. | INV-2025-11969 | P25-0178 | 143,040.00 NVK | 2025-12-11 | 143,040.00 NVK | 143,040.00 | 12,180.36 | no receipt recorded by year end |
| E25-00360 | Logistika Materijal Benko d.o.o. | 0022016 | P25-0243 | 32,160.00 NVK | 2025-12-11 | 32,160.00 NVK | 32,160.00 | 2,738.54 | advance payment vendor (terms ADV), delivery due January 2026 - permitted by manual 7.1 |

(b) Duplicate invoices paid a second time - the second payment has no receipt behind it: 2 invoices, NVK 110,640.00 = EUR 9,436.22.

| inv_doc | vendor | vend_ref | order | gross as recorded | paid on | paid as recorded | true gross NVK | EUR (booking rate of payment month) | note |
|---|---|---|---|---:|---|---:|---:|---:|---|
| E25-00296 | Kartonaza Velmir d.o.o. | INV202524992 | P25-0130 | 105,120.00 NVK | 2025-12-04 | 105,120.00 NVK | 105,120.00 | 8,951.33 | duplicate of E25-00256; goods were received and paid once already |
| 51007509 | Biro Dalven d.o.o. | F-37924 | 45002139 | 5,520.00 NVK | 2025-05-15 | 5,520.00 NVK | 5,520.00 | 484.89 | duplicate of 51007461; goods were received and paid once already |

(c) Laboratory orders, paid, no receipt in the system: 2 invoices, NVK 84,240.00 = EUR 7,319.70. They belong in the answer as stated (no recorded receipt). In the generator's true world the goods of 51007515 did arrive and were never booked; those of E25-00188 did not arrive. The data cannot tell the two apart.

| inv_doc | vendor | vend_ref | order | gross as recorded | paid on | paid as recorded | true gross NVK | EUR (booking rate of payment month) | note |
|---|---|---|---|---:|---|---:|---:|---:|---|
| 51007515 | Reagens Mivor d.o.o. | 2025/19599 | 45002184 | 30,600.00 NVK | 2025-05-29 | 30,600.00 NVK | 30,600.00 | 2,687.98 | laboratory order; whether the goods arrived is undecidable (K3-2) |
| E25-00188 | Analitika Preles d.o.o. | F-048621 | P25-0104 | 53,640.00 NVK | 2025-10-16 | 53,640.00 NVK | 53,640.00 | 4,631.72 | laboratory order; whether the goods arrived is undecidable (K3-2) |

**Establishable from the delivered data: the same 9 invoices.** For the amount: NVK 474,552.00 (EUR 40,832.68) taking invoice amounts in the vendor's currency; one payment record differs from its invoice by a transposition (K3-3), which moves the paid total by NVK 90.00 - a good answer states both. An answer that lists (a) and (b) and flags (c) as 'no recorded receipt, physical receipt unknown' is right. Leaving T6 out with the argument that advance payment is permitted is acceptable if stated.

A second, weaker reading - paid before the receipt was posted, receipt followed: 5 further invoices of the two advance-payment vendors, NVK 122,448.00 = EUR 10,749.38. Permitted by group manual 7.1 (terms ADV in the vendor master). Worth mentioning, not part of the answer.

| inv_doc | vendor | vend_ref | order | gross as recorded | paid on | paid as recorded | true gross NVK | EUR (booking rate of payment month) | note |
|---|---|---|---|---:|---|---:|---:|---:|---|
| 51007348 | Medilab Torvan d.o.o. | R/26168/25 | 45002091 | 30,816.00 NVK | 2025-01-30 | 30,816.00 NVK | 30,816.00 | 2,741.39 | advance payment vendor; receipt 50013150 posted 2025-02-10 |
| 51007433 | Logistika Materijal Benko d.o.o. | 0020105 | 45002131 | 24,120.00 NVK | 2025-03-13 | 24,120.00 NVK | 24,120.00 | 2,128.39 | advance payment vendor; receipt 50013235 posted 2025-03-27 |
| 51007579 | Medilab Torvan d.o.o. | R/27003/25 | 45002243 | 35,304.00 NVK | 2025-05-29 | 35,304.00 NVK | 35,304.00 | 3,101.19 | advance payment vendor; receipt 50013403 posted 2025-06-05 |
| E25-00145 | Logistika Materijal Benko d.o.o. | 0021331 | P25-0084 | 15,360.00 NVK | 2025-09-04 | 15,360.00 NVK | 15,360.00 | 1,323.62 | advance payment vendor; receipt W25-00165 posted 2025-09-15 |
| E25-00255 | Medilab Torvan d.o.o. | R/28030/25 | P25-0155 | 16,848.00 NVK | 2025-10-23 | 16,848.00 NVK | 16,848.00 | 1,454.80 | advance payment vendor; receipt W25-00290 posted 2025-11-04 |

Why it is smaller than it first looks - things a naive rule flags that are NOT in the answer:

- 130 invoices have no purchase order at all (rent, utilities, leasing, services); 125 of them are paid, NVK 5,563,402.79 gross. They are outside the three-way match (manual 7.1, instruction section 1). 'No receipt' means nothing for them.
- 51007596 (order 45002225): line 20 looks uncovered because its receipt was booked to line 10 (case B-1). The goods arrived.
- E25-00227 (order P25-0116): no receipt on the order because it was booked to order P25-0059 (case B-2). The goods arrived.
- 51007517 (order 45002174): invoiced quantity looks 500 times the receipt because the pieces were entered with the order unit (case H-1). Fully received.
- E25-00286 (order P25-0149): fully received on 2025-10-20 and paid; 50 rolls were returned on 2025-12-16 (document W25-00401) after the payment; the credit note had not arrived by year end. Paid WITH receipt; a refund is outstanding (kind 1, NVK 5,760.00 gross).
- E25-00379: a duplicate invoice (case A-3) that was posted but not paid by year end.
- Group invoices are posted before the receipt all year (goods in transit) but are paid only after the receipt; at year end the invoices in transit are unpaid.
- Receipts that were reversed and posted again, invoices in pieces against receipts in order units, several invoices per order line, credit notes: all covered when quantities are netted in order units.
- Receipts of December 2024 belong to invoices paid in early 2025.

## Question 3 - how much of the purchase volume was delivered late

**The question can only be answered for orders placed from 1 July 2025.** The delivery date field of the order line is empty for all 144 orders created before that date (never recorded; instruction section 3, handover note) and filled for the 125 orders created from 1 July. A right answer says so and gives the second half-year only. An answer that gives a full-year figure, or treats empty dates as on time, is wrong.

Measure (group manual 7.7): per order line, value of the quantity whose delivery note date (`doc_dt`) is after the delivery date in the order line; reversals netted against the receipt they reverse; value = receipt value in NVK, EUR at the booking rate of the receipt month.

| basis | received NVK | of which late NVK | late share | received EUR | late EUR |
|---|---:|---:|---:|---:|---:|
| **true, orders from 1 July, against the date in the order line (last agreed)** | 44,889,275.39 | 9,341,595.14 | 20.8 % | 3,864,958.85 | 801,602.37 |
| true, orders from 1 July, against the date first promised (not in the data) | 44,889,275.39 | 9,997,453.70 | 22.3 % | 3,864,958.85 | 858,041.31 |
| true, whole year, against the date first promised (not in the data) | 114,038,253.46 | 29,693,727.46 | 26.0 % | 9,963,064.60 | 2,587,475.56 |
| delivered data as recorded, delivery note date | 44,735,051.99 | 9,225,131.74 | 20.6 % | 3,851,824.81 | 791,722.23 |
| delivered data as recorded, posting date (naive) | 44,735,051.99 | 29,690,564.64 | 66.4 % | 3,851,824.81 | 2,555,538.33 |

**Establishable: late share of about 21 % of the value received on orders placed from 1 July (NVK 9,341,595.14 of 44,889,275.39; EUR 801,602.37 of 3,864,958.85), measured against the last agreed date.** The recorded data gives 20.6 % before the receipt errors B-2, B-3 and F-1 are corrected; anything within two percentage points of 21 % with the half-year restriction stated is right. Using the posting date instead of the delivery note date overstates lateness (66.4 %): the warehouse posts up to three working days later and re-posts corrected receipts later still.

Not decidable (K3-4): purchasing overwrites the date when a vendor announces a delay. Against the date first promised the true late share for the second half-year is 22.3 %. The 11 lines concerned carry a change date (`chgd_on`), but so do lines whose price was changed, so they cannot be isolated with certainty. A good answer names this as a reason the figure is a lower bound.

Open at year end and past the date in the order line (not delivered at all, orders from 1 July): NVK 1,930,742.49 at order price. In addition the whole first half-year: true late share for the full year 26.0 % - not derivable.

Lines whose date was overwritten: P25-0004/10 (first promised 2025-07-16, in data 2025-07-30), P25-0051/20 (first promised 2025-09-08, in data 2025-10-13), P25-0095/30 (first promised 2025-10-10, in data 2025-10-15), P25-0099/20 (first promised 2025-09-29, in data 2025-10-23), P25-0119/10 (first promised 2025-10-28, in data 2025-11-04), P25-0119/20 (first promised 2025-10-28, in data 2025-11-04), P25-0206/20 (first promised 2025-12-05, in data 2025-12-09), P25-0212/10 (first promised 2025-12-09, in data 2025-12-19), P25-0218/30 (first promised 2025-12-15, in data 2025-12-22), P25-0228/10 (first promised 2025-12-15, in data 2025-12-25), P25-0228/20 (first promised 2025-12-15, in data 2025-12-23)

## Seeded cases, kind 2 - real errors, no note anywhere

### A-1 - vendor invoice posted twice under a slightly different reference

- **Records:** `inv_header`/`inv_lines` E25-00256 (vend_ref `INV-2025-24992`) and E25-00296 (vend_ref `INV202524992`), vendor 70011 Kartonaza Velmir d.o.o., order P25-0130; payment Z25-0226 on 2025-12-04.
- **What is wrong:** E25-00296 is the same invoice as E25-00256: same vendor, invoice date, order lines, quantities and amount; the reference differs only in punctuation or a leading zero.
- **Effect:** Gross NVK 105,120.00 (EUR 8,888.89) booked twice, and paid twice (Q2 group b). The duplicate consumes the quantity of the later receipt W25-00382 (40 pieces, 11.12.), so by quantity the line looks over-invoiced by 20 instead of open by 40. Q1: true open amount NVK 58,400.00 hidden.
- **Detection:** Same vendor + invoice date + gross amount, references equal after removing punctuation and leading zeros; invoiced quantity exceeds received quantity on the order line.

### A-2 - vendor invoice posted twice under a slightly different reference

- **Records:** `inv_header`/`inv_lines` 51007461 (vend_ref `F-037924`) and 51007509 (vend_ref `F-37924`), vendor 70032 Biro Dalven d.o.o., order 45002139; payment 15004541 on 2025-05-15.
- **What is wrong:** 51007509 is the same invoice as 51007461: same vendor, invoice date, order lines, quantities and amount; the reference differs only in punctuation or a leading zero.
- **Effect:** Gross NVK 5,520.00 (EUR 466.77) booked twice, and paid twice (Q2 group b). Q1: no effect on credit lines; debit balance on the clearing account.
- **Detection:** Same vendor + invoice date + gross amount, references equal after removing punctuation and leading zeros; invoiced quantity exceeds received quantity on the order line.

### A-3 - vendor invoice posted twice under a slightly different reference

- **Records:** `inv_header`/`inv_lines` E25-00318 (vend_ref `R/33067/25`) and E25-00379 (vend_ref `R-33067-25`), vendor 70041 Paleta Drovnik d.o.o., order P25-0167; payment none for the duplicate.
- **What is wrong:** E25-00379 is the same invoice as E25-00318: same vendor, invoice date, order lines, quantities and amount; the reference differs only in punctuation or a leading zero.
- **Effect:** Gross NVK 26,904.00 (EUR 2,274.99) booked twice. Not paid by year end: no effect on Q2. Debit balance on the clearing account; vendor payable overstated.
- **Detection:** Same vendor + invoice date + gross amount, references equal after removing punctuation and leading zeros; invoiced quantity exceeds received quantity on the order line.

### B-1 - receipt booked to the wrong line of the same order

- **Records:** `goods_receipts` 50013358: two rows on order 45002225 position 10, the second with the material of position 20; invoice 51007596.
- **What is wrong:** The 18 boxes of position 20 were received on position 10. The system valued them at the price of position 10.
- **Effect:** Q1: false open item NVK 17,640.00 on 45002225/10. Q2: 51007596 looks paid without receipt for position 20 - it is not. Debit balance on position 20.
- **Detection:** `mat_no` of the receipt row differs from the material of the order line it points to; position 10 over-received by exactly the quantity position 20 lacks.

### B-2 - receipt booked to another order of the same vendor

- **Records:** `goods_receipts` W25-00190 on order P25-0059/10; belongs to order P25-0116/10; invoice E25-00227.
- **What is wrong:** Order P25-0059 (80 cartons) was complete since 2025-08-25; the delivery of 2025-09-29 for order P25-0116 (same material, 80 cartons, other price) was received against it.
- **Effect:** Q1: false open item NVK 36,400.00 on P25-0059/10. Q2: E25-00227 looks paid without receipt - it is not. Q3: the receipt counts as very late against the date of P25-0059; in truth on time.
- **Detection:** P25-0059/10 received twice its order quantity, P25-0116/10 invoiced and paid with no receipt, same vendor, material and quantity, receipt date fits the second order.

### B-3 - receipt booked to the wrong line, order not yet invoiced

- **Records:** `goods_receipts` W25-00397 on order P25-0169 position 10 with the material of position 30.
- **What is wrong:** 60 boxes of position 30 received on position 10 (already complete and invoiced) and valued at the price of position 10.
- **Effect:** Q1: recorded open item NVK 89,400.00 on position 10; true open item NVK 53,400.00 on position 30; overstatement NVK 36,000.00 (EUR 3,044.14).
- **Detection:** `mat_no` of the receipt row is the material of position 30; position 10 over-received; amount is quantity times the price of position 10.

### C-1 - currency slip on a purchase order

- **Records:** `po_header` P25-0203: `cur` NVK; vendor 70025 Sciomed Instruments Kereven GmbH is a EUR vendor; receipt W25-00369.
- **What is wrong:** The order was entered in NVK with the EUR prices (7,450 and 660 per unit). The receipt of 9 December was valued at NVK 36,400.00 instead of EUR 36,400.00.
- **Effect:** Q1: open item understated by NVK 391,063.40 (EUR 33,068.10); true value NVK 427,463.40 at the December booking rate. Not invoiced by year end.
- **Detection:** Vendor master currency EUR against order currency NVK; material master price in EUR equals the order price digit for digit; all other orders of the vendor are in EUR.

### C-2 - currency slip on a vendor invoice

- **Records:** `inv_header` E25-00116: `cur` EUR, gross 21,960.00; vendor 70043 Termo Log Savrin d.o.o. is a domestic NVK vendor, order P25-0045 is in NVK; payment Z25-0108: NVK 21,960.00.
- **What is wrong:** The invoice was entered with currency EUR; the amount is in NVK.
- **Effect:** Ledger: vendor account and clearing account carry NVK 253,264.68 instead of 21,960.00 gross. Q2: this is one of the group (a) invoices; its true amount is NVK 21,960.00, not EUR. Q1: no effect on credit lines (debit line, no receipt).
- **Detection:** Vendor and order currency NVK, payment in NVK with the same digits, 20 % domestic tax on a 'EUR' invoice.

### D-1 - manual clearing of an item whose invoice then arrived

- **Records:** `gl_lines` journal J25-0057 (31.10.), order P25-0031/10; receipt W25-00082; invoice E25-00330 posted 2025-11-18.
- **What is wrong:** The full value of a receipt was cleared against price differences although the invoice was merely late. When the invoice came, the clearing was not reversed.
- **Effect:** Debit balance NVK 38,400.00 on the clearing account (net balance understated), price differences overstated by the same. Q1 credit lines: none. Far above both limits.
- **Detection:** Order line with receipt, invoice and a manual clearing: three legs, balance not zero.

### D-2 - manual clearing posted to the wrong account

- **Records:** `gl_lines` journal 10000896 (30.06.), order 45002260/10.
- **What is wrong:** The remainder of a free over-delivery (40 rolls) was cleared with a debit on 1410 inventory instead of 2810.
- **Effect:** Q1: false open item NVK 2,460.00 stays on 2810; inventory overstated.
- **Detection:** Journal text and assignment name a clearing; the debit line sits on 1410; the order line stays open with exactly this amount.

### D-3 - manual clearing without reference to an order

- **Records:** `gl_lines` journal J25-0049 (30.09.): one debit on 2810, NVK 2,186.90, empty assignment; belongs to P25-0073/10, P25-0073/20 and P25-0087/10.
- **What is wrong:** Three legitimate small remainders were cleared in one line without order reference.
- **Effect:** Q1: by order line the three remainders stay open (false open items NVK 2,186.90); the account total is right.
- **Detection:** The amount equals the sum of exactly these three old remainders (318.00 + 742.50 + 1,126.40).

### D-4 - manual clearing posted with the wrong sign

- **Records:** `gl_lines` journal 10000887 (30.05.), order 45002232/10.
- **What is wrong:** The remainder of a free over-delivery (20 rolls, NVK 2,236.00) was credited to 2810 instead of debited.
- **Effect:** Q1: false open item NVK 4,472.00 (twice the remainder).
- **Detection:** After the journal the line balance is twice the remainder instead of zero.

### D-5 - manual clearing with transposed digits

- **Records:** `gl_lines` journal J25-0054 (31.10.), order P25-0151/10.
- **What is wrong:** Remainder NVK 1,384.20, cleared NVK 1,348.20.
- **Effect:** Q1: false open item NVK 36.00. Trivial.
- **Detection:** Residual of 36.00 on a line that was meant to be cleared.

### E-1 - mapping gap: new account missing in the mapping sheet

- **Records:** `acct_mapping.xlsx`: no row for local account 2815.
- **What is wrong:** Account 2815 (clearing account for group deliveries, in use since 1 July) was never added to the sheet copied from the old version.
- **Effect:** Any figure built through group accounts loses the whole of 2815 (net balance NVK -1,748,608.94 at year end). All open items of the group supply company, true NVK 1,258,281.25 (EUR 106,399.56), have their credit leg on 2815. Because group orders invoiced before 1 July were debited on 2810 and received on 2815, neither account means anything alone.
- **Detection:** Anti-join of posted accounts against the mapping on the posting date.

### E-2 - mapping gap: one month without a valid row

- **Records:** `acct_mapping.xlsx`: account 6950, old row ends 30.06.2025, new row starts 01.08.2025.
- **What is wrong:** The new row has the wrong start date.
- **Effect:** 9 ledger lines on 6950 in July 2025 (net NVK 457.66) have no group account. No effect on the three answers.
- **Detection:** Validity intervals per account do not cover July.

### F-1 - goods receipt posted twice

- **Records:** `goods_receipts` W25-00380 and W25-00388, order P25-0222, same delivery note `LS515398`.
- **What is wrong:** One delivery was received twice by two warehouse users; there is no reversal.
- **Effect:** Q1: false open item NVK 202,200.00 (EUR 17,097.92). Not invoiced at year end. Q3: received volume doubled for this order.
- **Detection:** Same order line, same delivery note number and date, same quantity; received quantity is twice the order quantity.

### F-2 - goods receipt posted twice

- **Records:** `goods_receipts` 50013151 and 50013156, order 45002107, same delivery note `DN23028`.
- **What is wrong:** One delivery was received twice by two warehouse users; there is no reversal.
- **Effect:** Q1: false open item NVK 6,700.00 (EUR 566.55). Invoice and payment for the single delivery are in order; the second receipt has been open since February. Q3: received volume doubled for this order.
- **Detection:** Same order line, same delivery note number and date, same quantity; received quantity is twice the order quantity.

### H-1 - unit slip on a vendor invoice

- **Records:** `inv_lines` 51007517: quantity 18000 with unit BOX; order 45002174/10 is 36 BOX = 18,000 PCE.
- **What is wrong:** The quantity in pieces was entered with the order unit.
- **Effect:** The system saw 18,000 boxes invoiced against 36 received and posted a debit of NVK 31,975.92 on the clearing account against price differences. Q2: looks paid without receipt; it is not. Q1 credit lines: none.
- **Detection:** Net amount / quantity is 1/500 of the order price; the vendor always bills in pieces.

## Seeded cases, kind 3 - the data cannot decide

### K3-1 - large December write-off on the clearing account

- **Records:** `gl_lines` journal J25-0065 (19.12.), order P25-0076 positions 10 and 20, receipt W25-00148 of 9 September, no invoice.
- **What is wrong:** Nothing in the data says whether the vendor will still invoice. Generator truth: the vendor's invoice arrives in January 2026; the liability exists.
- **Effect:** Q1: NVK 313,000.00 (EUR 26,467.11) - the width of the range.
- **Detection:** It looks like every other clearing journal. Arguments for keeping the liability: far above both limits, full order value rather than a remainder, no credit note, vendor invoiced all other orders. None is proof.

### K3-2 - laboratory orders paid without a receipt

- **Records:** invoices 51007515 (order 45002184) and E25-00188 (order P25-0104).
- **Why undecidable:** the handover note says laboratory deliveries go straight to the lab and the receipt is sometimes never booked. Whether these goods arrived was never recorded.
- **Effect:** Q2 group (c). Both are 'paid without recorded receipt'; whether a control failed or only a booking is unknown.

### K3-3 - invoice and payment disagree on the amount

- **Records:** invoice 51007634 gross NVK 12,672.00; payment Z25-0025 NVK 12,762.00.
- **Why undecidable:** two digits are transposed in one of the two records; there is no bank statement in the delivery. Generator truth: the invoice is right.
- **Effect:** Q2 amount of this invoice is NVK 12,672.00 or 12,762.00.

### K3-4 - promised delivery date: never recorded before July, overwritten after

- **Records:** `po_lines.dlv_dt` empty for all orders before 1 July; 11 later lines overwritten (listed under Question 3).
- **Effect:** Q3 is answerable only for orders from 1 July, and there only against the last agreed date.

### K3-5 - one local account mapped to two group accounts

- **Records:** `acct_mapping.xlsx`, account 1450: two rows valid from 01.07.2025, group accounts 120500 and 120150, entered by two different users.
- **Why undecidable:** neither row has an end date, and the manual extract does not say which group account takes goods in transit from group companies.
- **Effect:** none on the three answers; the year-end reclassification of goods in transit cannot be assigned to one group account.

## Kind 1 - correct business events that look like errors

All of these are in the clean base and are consistent. A rule that flags them is wrong. Counts are order lines.

- **advance payment vendor: invoice paid before the receipt** - 6: 45002091/10, 45002131/10, 45002243/10, P25-0084/10, P25-0155/10, P25-0243/10
- **credit note for price only (quantity zero)** - 5: 45002048/20, 45002075/10, 45002220/10, 45002266/10, P25-0110/20
- **free over-delivery, remainder cleared by manual journal** - 16: 45002116/10, 45002147/10, 45002156/20, 45002187/20, 45002286/30, P25-0018/10, P25-0021/10, P25-0033/30, P25-0079/20, P25-0181/20, 45002260/10, P25-0073/10, P25-0073/20, P25-0087/10, 45002232/10, P25-0151/10
- **group delivery in transit at year end (invoiced, not received)** - 14: P25-0219/10, P25-0219/20, P25-0219/30, P25-0219/40, P25-0227/10, P25-0227/20, P25-0227/30, P25-0240/10, P25-0240/20, P25-0240/30, P25-0255/10, P25-0255/20, P25-0255/30, P25-0255/40
- **group invoice after the goods** - 35: 45002018/10, 45002018/20, 45002030/10, 45002030/20, 45002030/30, 45002046/10, 45002046/20, 45002046/40, 45002052/10, 45002052/20, 45002095/10, 45002095/20, 45002095/30, 45002095/40, 45002141/10, 45002141/20, 45002172/10, 45002240/20, P25-0036/20, P25-0046/10, P25-0046/30, P25-0046/40, P25-0071/10, P25-0071/20, P25-0071/30, P25-0119/10, P25-0119/20, P25-0230/10, P25-0230/20, P25-0230/30, P25-0184/10, P25-0184/20, P25-0184/30, P25-0199/10, P25-0199/20
- **invoice in base unit, order and receipt in order unit** - 70: 45002033/10, 45002033/20, 45002033/30, 45002042/10, 45002042/20, 45002048/10, 45002048/20, 45002051/20, 45002069/10, 45002069/20, 45002088/10, 45002088/20, 45002088/30, 45002094/10, 45002116/10, 45002116/20, 45002123/10, 45002123/20, 45002123/30, 45002148/10, 45002148/20, 45002150/10, 45002153/10, 45002153/20, 45002156/10, 45002156/20, 45002156/30, 45002160/10, 45002160/20, 45002188/10, 45002190/10, 45002190/20, 45002208/10, 45002208/20, 45002223/10, 45002223/20, 45002227/10, 45002227/20, 45002255/10, 45002255/20, 45002282/10, 45002282/20, 45002282/30, 45002286/10, 45002286/20, 45002286/30, 45002291/20, P25-0033/10, P25-0033/20, P25-0033/30, P25-0042/10, P25-0042/20, P25-0048/10, P25-0048/20, P25-0062/10, P25-0065/10, P25-0065/20, P25-0089/10, P25-0089/20, P25-0108/10, P25-0108/20, P25-0135/10, P25-0135/20, P25-0138/10, P25-0171/10, P25-0171/20, P25-0181/10, P25-0181/20, P25-0190/10, P25-0190/20
- **one invoice covering two orders** - 2: 45002137/10, 45002144/10
- **partial delivery / several invoices per order line** - 196: (not listed)
- **price changed after the order, order amended (receipt at old price)** - 16: 45002024/10, 45002082/20, 45002090/10, 45002126/20, 45002160/20, 45002282/20, P25-0033/10, P25-0048/20, P25-0093/20, P25-0101/30, P25-0132/10, P25-0171/10, P25-0186/20, P25-0190/20, P25-0196/30, P25-0251/20
- **price changed after the order, order not amended** - 12: 45002036/10, 45002070/10, 45002134/10, 45002194/20, 45002206/20, 45002218/10, P25-0006/10, P25-0010/20, P25-0123/20, P25-0158/10, P25-0209/10, P25-0249/20
- **receipt reversed and re-posted (correction)** - 58: 45002027/10, 45002027/20, 45002027/30, 45002063/10, 45002063/20, 45002076/10, 45002076/20, 45002076/30, 45002078/10, 45002078/20, 45002078/30, 45002078/40, 45002084/10, 45002084/20, 45002113/10, 45002120/10, 45002120/20, 45002120/30, 45002154/10, 45002154/20, 45002166/10, 45002180/10, 45002180/20, 45002188/10, 45002188/20, 45002194/20, 45002220/10, 45002220/20, 45002227/10, 45002227/20, 45002279/10, P25-0003/10, P25-0003/20, P25-0006/10, P25-0006/20, P25-0092/10, P25-0092/20, P25-0092/30, P25-0098/10, P25-0098/20, P25-0098/30, P25-0098/40, P25-0099/10, P25-0101/10, P25-0101/20, P25-0101/30, P25-0117/10, P25-0117/20, P25-0132/10, P25-0132/20, P25-0196/10, P25-0196/20, P25-0196/30, P25-0201/10, P25-0201/20, P25-0201/30, P25-0215/10, P25-0215/20
- **return to vendor with credit note** - 14: 45002057/10, 45002063/20, 45002110/10, 45002150/20, 45002153/10, 45002154/10, 45002176/20, 45002196/10, 45002247/10, 45002249/20, 45002255/20, 45002262/10, 45002288/10, P25-0054/20
- **vendor billed fewer pieces than the receipt in order units, remainder cleared** - 12: 45002033/10, 45002048/10, 45002088/10, 45002088/20, 45002116/20, 45002123/10, 45002156/10, 45002156/30, 45002286/10, P25-0033/20, P25-0042/10, P25-0042/20
- **correct manual clearing journals** - 26 in the true world; in the delivered data all manual clearings look the same.
- **opening items** - receipts and invoices of November/December 2024 on orders still moving in 2025; ledger document type SV on 1 January 2025.
- **goods in transit reclassification** - 30 June (reversed 1 July) and 31 December, group order lines, document type SA, same look as the clearing journals.
- **two clearing accounts** - group order lines with one leg on 2810 (before 1 July) and one on 2815.
- **two numbering schemes** - documents from 1 July carry the new numbers, also against old orders; the assignment field changes format with the posting date.
- **sign conventions** - receipts and credit notes carry positive quantities and amounts; movement type and document type give the direction; in `payments` credit notes are negative.
- **exchange differences** - EUR receipts and invoices are booked at different monthly rates; the system posts the difference to 6950 (the local instruction still says 6900).
- **recurring invoices** - rent, leasing, cleaning and security are the same amount every month from the same vendor with different references; not duplicates.
- **mapping change** - several local accounts map to a different group account from 1 July; the first half-year is not restated.
- **document contradictions** - clearing limit NVK 2,500 (local) against EUR 150 (group); payment without receipt allowed locally on written confirmation, forbidden by the group manual; the local instruction describes the old numbers, one clearing account, account 6900 and an unused delivery date.

## Deliberately not in this key (ordinary noise)

Vendor names spelled differently in `payments.payee`; city names in capitals; empty buyer, cost centre, e-mail, ABC indicator and text fields; lower-case units and delivery note numbers; missing or 'w/o DN' delivery note numbers; stray spaces around vendor references; double spaces and capitals in material texts; free-text remarks on receipts and invoice headers; varying wording of journal texts; different date formats between files; gaps in the document number ranges; cent differences from rounding posted as 'Diff. GR/IR'. None of these marks or hides a seeded case.

