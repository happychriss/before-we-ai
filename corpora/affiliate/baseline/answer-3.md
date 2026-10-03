# Meridia Pharma Norvania – purchasing data FY 2025: answers to the three questions

Rates used: closing rate 31.12.2025 = 11.8260 NVK/EUR (balance sheet, manual 7.4); monthly booking rates for flows.

## 1. The three answers

| # | Question | Answer |
|---|---|---|
| 1 | Goods received not invoiced (GRNI) at 31.12.2025 | **EUR 220,881** (NVK 2,612,143.00), of which group companies (211520) EUR 106,400 and third parties (211510) EUR 114,482. The ledger as delivered shows only EUR 182,460 (NVK 2,157,774.50) as the sum of credit positions; the difference is corrections I made (section 2). |
| 2 | Vendor invoices paid without a goods receipt | **8 invoices, NVK 442,482 paid (about EUR 38,102; net of VAT NVK 368,660)**: six with no receipt at all and two duplicate invoices paid a second time. Listed below. In addition, 6 advance-payment invoices (NVK 154,608) that the rules allow, and 2 invoices (NVK 96,072) where the receipt exists but was posted to the wrong order or line. |
| 3 | Purchase volume delivered late | **EUR 858,041 of EUR 3,864,964 measurable volume = 22.2 %.** Measurable means orders created from 1 July 2025 (the only ones with a confirmed delivery date). That is 41 % of all 2025 receipts (EUR 9.39 m); for the other 59 % no statement is possible. |

Invoices paid without goods receipt (question 2):

| Invoice | Vendor | Order / pos | Paid on | Paid NVK (gross) | EUR | Finding |
|---|---|---|---|---|---|---|
| 51007419 | 70041 Paleta Drovnik | 45002121 / 10 | 27.03.2025 | 69,840.00 | 6,162.81 | 150 pallets, no receipt to date |
| 51007515 | 70022 Reagens Mivor (lab) | 45002184 / 10 | 29.05.2025 | 30,600.00 | 2,687.98 | no receipt to date |
| 51007634 | 70034 Uredska Oprema Hrist | 45002270 / 10, 20 | 17.07.2025 | 12,762.00 | 1,110.56 | no receipt to date; invoice gross is 12,672.00, payment is 90.00 too high |
| E25-00116 | 70043 Termo Log Savrin | P25-0045 / 10 | 11.09.2025 | 21,960.00 | 1,892.37 | no receipt to date; invoice also booked in the wrong currency |
| E25-00188 | 70023 Analitika Preles (lab) | P25-0104 / 10 | 16.10.2025 | 53,640.00 | 4,631.72 | no receipt to date |
| E25-00313 | 70045 Senzor Tehnika Olvar | P25-0178 / 10 | 11.12.2025 | 143,040.00 | 12,180.36 | no receipt to date |
| 51007509 | 70032 Biro Dalven | 45002139 / 10, 20 | 15.05.2025 | 5,520.00 | 484.89 | duplicate of 51007461 (ref F-037924 vs F-37924), paid twice |
| E25-00296 | 70011 Kartonaza Velmir | P25-0130 / 10 | 04.12.2025 | 105,120.00 | 8,951.33 | duplicate of E25-00256 (INV-2025-24992 vs INV202524992), paid twice |
| **Total** | | | | **442,482.00** | **38,102.02** | |

EUR at the booking rate of the payment month; at the closing rate the total is EUR 37,416.

## 2. How I got each number

### 2.1 GRNI at year end

Method (group manual 7.3): balance of the clearing accounts 2810 and 2815 **together**, per order position, at 31.12.2025; sum of the positions with a credit balance; no netting with debit positions; NVK divided by the closing rate. The assignment field was normalised for both formats (`4500201800010` and `P25-0018/10`).

Ledger as delivered: 588 positions, 26 with a credit balance = NVK 2,157,774.50; 19 with a debit balance = NVK 709,656.72; net NVK −1,448,117.78.

Positions kept unchanged (NVK):

| Position | NVK | Note |
|---|---|---|
| P25-0199 / 10, 20 (group) | 231,464.38 + 448,740.74 | receipt W25-00409, 19.12., no invoice |
| P25-0184 / 10, 20, 30 (group) | 151,519.33 + 330,166.15 + 96,390.65 | receipt W25-00387, 12.12., no invoice |
| P25-0224 / 10, 20, 30 | 26,772.00 + 146,563.56 + 61,594.23 | receipt W25-00422, 25.12. |
| P25-0218 / 10, 20, 30 | 4,404.12 + 13,536.90 + 26,739.54 | receipt W25-00421 |
| P25-0215 / 10 | 19,788.00 | second delivery W25-00418, 25.12. |

Corrections (NVK):

| Position | Ledger | Corrected | Reason |
|---|---|---|---|
| P25-0222 / 10, 20 | 404,400.00 | 202,200.00 | Receipt posted twice for the same delivery note LS515398 (W25-00380 by WH01, W25-00388 by WH02), no reversal. W25-00388 removed. |
| P25-0169 / 10 → 30 | 89,400.00 | 53,400.00 | W25-00397 line 1 is material 500011 (60 BOX) posted on position 10 (material 500009) and valued at 1,490 instead of 890. Moved to position 30 at order price. |
| P25-0203 / 10, 20 | 36,400.00 | 427,463.40 | Order created in NVK for EUR vendor 70025; prices 7,450 and 660 are the EUR prices. Receipt W25-00369 is worth EUR 36,400, restated at the December booking rate 11.7435. |
| P25-0130 / 10 | 0 (debit 29,200) | 58,400.00 | Second delivery of 40 PCE (W25-00382, 11.12.) is not invoiced; it is hidden by the duplicate invoice E25-00296. |
| P25-0076 / 10, 20 | 0 | 313,000.00 | Receipt W25-00148 (09.09.), never invoiced, written off to 5890 by journal J25-0065 on 19.12. (user DPET). Far above both limits, 101 days old, no vendor confirmation visible. Reinstated. |
| P25-0059 / 10 | 36,400.00 | 0 | Second receipt W25-00190 (29.09., DN63059) belongs to order P25-0116 / 10 (same vendor, material, 80 CAR, due 29.09.), which is invoiced and paid (E25-00227). |
| 45002225 / 10 | 17,640.00 | 0 | Receipt 50013358 line 2 (material 300003) posted on position 10 instead of 20; position 20 is invoiced and paid. |
| 45002107 / 10 | 6,700.00 | 0 | Receipt posted twice for delivery note DN23028 (50013151, 50013156). |
| 45002232 / 10 | 4,472.00 | 0 | Free over-delivery of 20 ROL (2,236.00); clearing journal 10000887 posted on the wrong side and doubled the balance. |
| 45002260 / 10 | 2,460.00 | 0 | Free over-delivery of 40 ROL; clearing journal 10000896 debited 1410 instead of 2810. |
| P25-0087 / 10, P25-0073 / 10, 20 | 1,126.40 + 318.00 + 742.50 | 0 | Over-deliveries of one unit each; cleared together by J25-0049 (2,186.90, exactly the sum) without an order in the assignment field. |
| P25-0151 / 10 | 36.00 | 0 | Remainder of a clearing: J25-0054 booked 1,348.20 instead of 1,384.20. |

Result: 2,157,774.50 − 308,094.90 removed + 762,463.40 added = **NVK 2,612,143.00 = EUR 220,881.36**. Group NVK 1,258,281.25 = EUR 106,399.56; third parties NVK 1,353,861.75 = EUR 114,481.80.

Checks made: every receipt and invoice of 2025 has its ledger document and the amounts agree; received and invoiced quantities were compared per position (invoice quantities converted from pieces to order units) and all remaining differences are explained above or were cleared by small journals. The year-end reclassification J25-0066 (14 group positions invoiced but not received, NVK 6,213,515.68 to 1450) is consistent and does not touch any credit position.

### 2.2 Invoices paid without goods receipt

Method: for every paid invoice line with an order, cumulative invoiced quantity on the position against net received quantity (101 less 102) on the payment date and at year end. 22 invoices showed a shortfall on the payment date. Sorted as follows:

- **Counted (8 invoices, table above).** Six have no receipt on the order at year end. Two are second entries of an invoice already posted and paid (same vendor, invoice date and amount; reference differs only in punctuation or a zero).
- **Not counted – advance payment terms (allowed by manual 7.1 and local instruction):** vendors 70026 and 70044, terms ADV in vendor master and order. Invoices 51007348 (30,816.00), 51007433 (24,120.00), 51007579 (35,304.00), E25-00145 (15,360.00), E25-00255 (16,848.00), E25-00360 (32,160.00); total NVK 154,608.00 (EUR 13,488). All received within two weeks except E25-00360 (order P25-0243, due 12.01.2026).
- **Not counted – receipt exists but is posted elsewhere:** 51007596 line 2 (order 45002225 / 20, NVK 50,760 gross; receipt sits on position 10) and E25-00227 (order P25-0116 / 10, NVK 45,312; receipt sits on order P25-0059). Formally these are paid without a receipt on the position; NVK 96,072 in total.
- **Not counted – returns:** 51007354, 51007431, 51007499, 51007589, 51007642. Goods were received and paid, part was later returned, the credit notes (51007414, 51007475, 51007566, 51007652, E25-00044) were deducted in later runs.
- **Not counted – unit error:** 51007517 (order 45002174): invoice entered as 18,000 BOX instead of PCE; the receipt of 36 BOX covers it.
- **Outside the question:** 130 invoice lines without an order (rent, utilities, leasing, services; NVK 4,731,289 net) are outside the three-way match. Group invoices: none was settled through netting before the receipt.

Also noted: the third duplicate E25-00379 (70041, duplicate of E25-00318, NVK 26,904.00) is posted but not yet paid.

### 2.3 Late deliveries

Method (manual 7.7): per receipt line, delivery note date (`doc_dt`) against the confirmed delivery date of the order line; late if the delivery note date is later; partial deliveries count with the value delivered; reversals and re-entries netted (they carry the original delivery note date). Value = receipt value in NVK divided by the booking rate of the posting month. Returns to vendor deducted from the delivery they refer to.

Corrections and adjustments:

- W25-00388 (duplicate receipt, P25-0222) removed.
- W25-00190 counted on P25-0116 / 10 (on time, value NVK 37,760); W25-00397 line 1 counted on P25-0169 / 30 (35 days late, NVK 53,400).
- P25-0203 valued at EUR 36,400 (1 day late).
- Overwritten delivery dates: six lines where the date was pushed back and the other lines of the order still show the original date were measured against the original date – P25-0004 / 10 (16.07.), P25-0051 / 20 (08.09.), P25-0095 / 30 (10.10.), P25-0099 / 20 (29.09.), P25-0206 / 20 (05.12.), P25-0218 / 30 (15.12.). This adds EUR 42,710 of late volume.
- Five lines where the date was changed and the original cannot be recovered (P25-0119 / 10, 20; P25-0212 / 10; P25-0228 / 10, 20) are counted as late: EUR 13,729.
- Ten further lines with a change date are price changes (receipt value differs from the current price, date equals the other lines) and were left as they are.

Result: late EUR 858,041.31 (group EUR 572,458; third parties EUR 285,584) of EUR 3,864,963.77 = 22.20 %.

Sensitivity: without the five unrecoverable lines 21.85 %; against the dates as they stand in the file 20.74 %; without any correction 20.55 %. Using the posting date instead of the delivery note date would give 65.8 %, which is wrong – receipts are routinely posted one to three days after delivery.

## 3. Assumptions

- GRNI is reported as the manual defines it (credit positions, both clearing accounts, closing rate). EUR positions are taken at their NVK book value divided by the closing rate. Valuing them at the EUR order amount instead gives EUR 221,883.
- Free over-deliveries that the accountant cleared, or tried to clear, are not a liability.
- A write-off of a full, uninvoiced receipt (P25-0076) is not valid without a vendor confirmation; the liability stands.
- Two invoices with the same vendor, date, amount and near-identical reference are duplicates.
- "Paid without goods receipt" means no receipt on the payment date for an order-based invoice; contractual advance payments are an allowed exception and reported separately.
- All lines of one order originally had the same confirmed delivery date (true for every order without a later change).
- Late means any delay of one day or more; no tolerance.
- Returned goods are not purchase volume (effect on the percentage: 0.01 points).

## 4. Problems found in the data

- **Mapping:** account 2815 (group clearing, since 1 July) is not in the mapping sheet at all, so group GRNI would not reach 211520. Account 1450 has two overlapping lines from 1 July (120150 and 120500). Account 6950 has no mapping for July 2025. A report built on the mapping would show 2810 with a debit balance of NVK 300,491 and nothing for 2815.
- **Clearing journals:** J25-0065 (313,000.00), J25-0057 (38,400.00; the invoice arrived three weeks later, leaving a false debit on P25-0031) and J25-0019 (5,460.90) exceed the local limit of NVK 2,500; six journals exceed the group limit of EUR 150. J25-0049 has no assignment. 10000887 is on the wrong side, 10000896 on the wrong account, J25-0054 has the wrong amount. No second approver is visible in the data.
- **Receipts:** two double postings (P25-0222, 45002107), three on the wrong position or order (45002225, P25-0169, and P25-0059 instead of P25-0116), 24 lines with lower-case units, 24 lines without a delivery note number.
- **Invoices:** three duplicates (51007509, E25-00296, E25-00379); E25-00116 booked as EUR 18,300 instead of NVK (clearing debit NVK 211,053.90 instead of 18,300); 51007517 with the wrong unit (false debit NVK 31,975.92); 24 references with leading or trailing blanks; payment of 51007634 is 90.00 above the invoice.
- **Orders:** P25-0203 in the wrong currency; 18 orders without buyer; delivery dates are overwritten on delay, so the file understates lateness.
- **Debit positions not reclassified:** NVK 709,656.72 of third-party debit positions remain on 2810 (not moved to advances to suppliers); most are the errors listed above. Return W25-00401 (P25-0149, NVK 4,800.00) still awaits its credit note.
- **Scope:** the ledger extract has no opening balance for 1450, so its balance in the extract (NVK 2,795,850.80) is not the true balance (NVK 6,213,515.68 per J25-0066).

## 5. What I am unsure about

- **P25-0076 (EUR 26,467):** reinstated on the evidence in the data. If the vendor confirmed that no invoice will follow, GRNI is EUR 194,414.
- **P25-0130 (EUR 4,938):** depends on E25-00296 being a duplicate. If it is a genuine second invoice, the position is over-invoiced instead and GRNI is EUR 215,943.
- **P25-0203:** I read the order as EUR 36,400. If it really was agreed in NVK, GRNI is EUR 187,813 and late volume falls by about EUR 33,300.
- **Lab invoices 51007515 and E25-00188:** the handover note says lab deliveries often go straight to the lab without a receipt. The goods may be in the building; the data cannot show it. The same could apply to nothing else on the list – the other four vendors deliver pallets, office material, seals and data loggers through the warehouse.
- **Cut-off:** the last receipt is posted on 25.12.2025. Deliveries between 26. and 31.12. posted in January, and lab deliveries never posted, would be missing from GRNI.
- **Late deliveries:** the five lines with unrecoverable original dates are an assumption (EUR 13,729). Dates overwritten before the first receipt on single-line orders without a change trace cannot be detected at all. Lines open and overdue at year end (14 lines, about EUR 163,000) are not in the figure because nothing was delivered.
- **EUR conversion of payments:** booking rate of the payment month is my choice; the manual does not prescribe a rate for this question.
