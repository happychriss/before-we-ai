# Meridia Pharma Norvania – purchasing data FY 2025: three questions

All amounts in NVK are local-currency book values. EUR conversion: balance-sheet items at the December closing rate 11.8260 NVK/EUR (group manual 7.4); flows (payments, deliveries) at the booking rate of the month.

## 1. The three answers

### Q1 – Goods received but not yet invoiced (GRNI) at 31.12.2025

**EUR 220,881 (NVK 2,612,143.00)**, sum of the order positions with a credit balance after correcting posting errors, not netted against debit positions.

| | NVK | EUR |
|---|---:|---:|
| Group companies (group account 211520) | 1,258,281.25 | 106,399.56 |
| Third parties (group account 211510) | 1,353,861.75 | 114,481.80 |
| **Total** | **2,612,143.00** | **220,881.36** |

For comparison, what the ledger shows without any correction: sum of credit positions on 2810 + 2815 = NVK 2,157,774.50 (EUR 182,460); net balance of the two accounts = NVK 1,448,117.78 credit (EUR 122,452). Neither is the right figure.

About EUR 62,600 of my figure rests on two judgement calls (P25-0203 and P25-0076, see section 5).

### Q2 – Vendor invoices paid without a goods receipt

**Eight invoices, NVK 442,482.00 paid (about EUR 38,100)**, all third-party, all still without a matching receipt at year end:

| Invoice | Vendor | Order | Paid on | Paid NVK (gross) | Net NVK | Remark |
|---|---|---|---|---:|---:|---|
| 51007419 | 70041 Paleta Drovnik | 45002121/10 | 27.03.2025 | 69,840.00 | 58,200.00 | 150 pallets, no receipt |
| 51007515 | 70022 Reagens Mivor | 45002184/10 | 29.05.2025 | 30,600.00 | 25,500.00 | laboratory order, no receipt |
| 51007634 | 70034 Uredska Oprema Hrist | 45002270/10+20 | 17.07.2025 | 12,762.00 | 10,560.00 | no receipt; invoice is 12,672.00, paid 90.00 too much |
| E25-00116 | 70043 Termo Log Savrin | P25-0045/10 | 11.09.2025 | 21,960.00 | 18,300.00 | no receipt; invoice booked in EUR by mistake |
| E25-00188 | 70023 Analitika Preles | P25-0104/10 | 16.10.2025 | 53,640.00 | 44,700.00 | laboratory order, no receipt |
| E25-00313 | 70045 Senzor Tehnika Olvar | P25-0178/10 | 11.12.2025 | 143,040.00 | 119,200.00 | 80 data loggers, no receipt |
| *Subtotal: no receipt at all* | | | | *331,842.00* | *276,460.00* | *EUR 28,665.80* |
| 51007509 | 70032 Biro Dalven | 45002139/10+20 | 15.05.2025 | 5,520.00 | 4,600.00 | duplicate of 51007461, paid twice |
| E25-00296 | 70011 Kartonaza Velmir | P25-0130/10 | 04.12.2025 | 105,120.00 | 87,600.00 | duplicate of E25-00256, paid twice |
| *Subtotal: duplicates* | | | | *110,640.00* | *92,200.00* | *EUR 9,436.22* |
| **Total** | | | | **442,482.00** | **368,660.00** | **EUR 38,102.02** |

Not in the total, but relevant:

- **Permitted advance, goods still outstanding:** E25-00360, 70044 Logistika Materijal Benko (terms ADV), P25-0243/10, paid 11.12.2025, NVK 32,160.00 (EUR 2,738.54). Delivery is due 12.01.2026.
- **Paid in advance, received later (ADV vendors, permitted by manual 7.1):** 51007348 (30,816.00), 51007579 (35,304.00), E25-00255 (16,848.00) from 70026 Medilab Torvan; 51007433 (24,120.00), E25-00145 (15,360.00) from 70044. Total NVK 122,448.00; receipts followed 7–14 days after payment.
- **Only apparently without receipt – the receipt was posted to the wrong place:** 51007596 line 2 (70021 Labtek Soran, 45002225/20, net 42,300.00 of an 86,040.00 invoice) and E25-00227 (70012 Brenko Pak, P25-0116/10, paid 45,312.00).
- **Returned after payment, credit note outstanding:** E25-00286 (70013 Etiketa Sorvin, P25-0149/10): 50 rolls returned 16.12.2025, net 4,800.00 / gross 5,760.00.
- No group invoice was settled before its receipt was posted.

### Q3 – Purchase volume delivered late

**EUR 858,165 of EUR 3,866,437 measurable delivered volume was late: 22.2 %.**

| | EUR | Share |
|---|---:|---:|
| Delivered volume 2025, all receipts (order price) | 9,394,333 | |
| of which not measurable (order lines without a confirmed date) | 5,527,897 | 58.8 % of total |
| of which measurable (orders from 1 July, P25-…) | 3,866,437 | 41.2 % of total |
| Late, on the dates as they stand in the order lines | 801,727 | 20.7 % of measurable |
| **Late, after restoring overwritten dates** | **858,165** | **22.2 % of measurable** |
| Late by more than 3 days (dates as recorded) | 704,278 | 18.2 % of measurable |

Split of the 22.2 %: group supply company EUR 572,458 of 3,100,656 (18.5 %); third parties EUR 285,708 of 765,781 (37.3 %).

The figure says nothing about the first half-year: 59 % of the year's volume has no confirmed date. In addition, about EUR 163,000 of order lines were overdue and still undelivered at year end (not in the figure, because nothing was delivered).

## 2. How I got each number

### Q1

1. Took all ledger lines on 2810 and 2815 together (group deliveries moved to 2815 on 1 July; old balances were not moved).
2. Normalised the assignment field: old format `4500201800010` and new format `45002018/10` to one key, order/position. All 1,857 assigned lines matched an order line.
3. Summed per order position. Opening balances (document 09000001, nine positions) agree with the December 2024 receipts and invoices in the extract. Result: 26 credit positions (NVK 2,157,774.50), 18 debit positions (NVK 707,469.82).
4. Compared every position with its receipts, invoices and credit notes in quantities (invoice quantities converted from pieces/bottles/reams to the order unit with the material master). Reviewed all 81 positions where quantities differ plus every manual journal.
5. Corrections, reconciling the ledger figure to mine:

| Step | Position(s) | Records | NVK |
|---|---|---|---:|
| Credit positions per ledger | | | 2,157,774.50 |
| Receipt entered twice (same delivery note, two warehouse users) | P25-0222/10, /20 | W25-00388 duplicates W25-00380 | −202,200.00 |
| Receipt entered twice | 45002107/10 | 50013156 duplicates 50013151 | −6,700.00 |
| Receipt posted to wrong position; goods belong to /20, which is invoiced | 45002225/10 | 50013358 line 2 | −17,640.00 |
| Receipt posted to wrong position and valued at the wrong price: 60 boxes of material 500011 belong to P25-0169/30 at 890.00 = 53,400.00, booked on /10 at 1,490.00 = 89,400.00 | P25-0169/10 → /30 | W25-00397 | −36,000.00 |
| Receipt posted to the wrong order; it belongs to P25-0116/10, which is invoiced | P25-0059/10 | W25-00190 | −36,400.00 |
| Over-delivery cleared with the wrong sign (doubled instead of cleared) | 45002232/10 | journal 10000887 | −4,472.00 |
| Over-delivery cleared against inventory 1410 instead of the clearing account | 45002260/10 | journal 10000896 | −2,460.00 |
| Three small over-deliveries cleared in one journal line without assignment (2,186.90 = 1,126.40 + 742.50 + 318.00) | P25-0087/10, P25-0073/10, /20 | journal J25-0049 | −2,186.90 |
| Clearing with transposed digits (1,348.20 instead of 1,384.20) | P25-0151/10 | journal J25-0054 | −36.00 |
| Receipt written off in full although no invoice has arrived | P25-0076/10, /20 | journal J25-0065 (239,800.00 + 73,200.00) | +313,000.00 |
| Second delivery of 40 pieces hidden by a duplicate invoice | P25-0130/10 | receipt W25-00382; duplicate E25-00296 | +58,400.00 |
| Order entered in NVK for a EUR vendor: 36,400 is EUR, revalued at the December booking rate 11.7435 (427,463.40 instead of 36,400.00) | P25-0203/10, /20 | receipt W25-00369 | +391,063.40 |
| **GRNI corrected** | | | **2,612,143.00** |

6. Resulting positions:

| Position | Vendor | NVK | EUR |
|---|---|---:|---:|
| P25-0184/10, /20, /30 | 79001 Meridia Supply Chain (receipt W25-00387, 12.12.) | 578,076.13 | 48,881.80 |
| P25-0199/10, /20 | 79001 Meridia Supply Chain (W25-00409, 19.12.) | 680,205.12 | 57,517.77 |
| P25-0203/10, /20 | 70025 Sciomed Instruments (W25-00369, 09.12.) | 427,463.40 | 36,146.07 |
| P25-0076/10, /20 | 70043 Termo Log Savrin (W25-00148, 09.09.) | 313,000.00 | 26,467.10 |
| P25-0224/10, /20, /30 | 70011 Kartonaza Velmir (W25-00422, 25.12.) | 234,929.79 | 19,865.53 |
| P25-0222/10, /20 | 70012 Brenko Pak (W25-00380, 10.12.) | 202,200.00 | 17,097.92 |
| P25-0130/10 | 70011 Kartonaza Velmir (W25-00382, 11.12.) | 58,400.00 | 4,938.27 |
| P25-0169/30 | 70045 Senzor Tehnika Olvar (W25-00397, 15.12.) | 53,400.00 | 4,515.47 |
| P25-0218/10, /20, /30 | 70045 Senzor Tehnika Olvar (W25-00421, 25.12.) | 44,680.56 | 3,778.16 |
| P25-0215/10 | 70041 Paleta Drovnik (W25-00418, 25.12.) | 19,788.00 | 1,673.26 |

7. Debit positions are not netted (manual 7.3). The year-end reclassification J25-0066 (NVK 6,213,515.68 to 1450, group invoices without receipt for P25-0219, P25-0227, P25-0240, P25-0255) only touches debit positions and does not affect GRNI; I checked that none of those positions has a receipt.

### Q2

1. Only invoices with a purchase order (the three-way match applies to them). The 130 invoice lines without an order are rent, utilities, leasing, services and are outside the match.
2. For each paid invoice line, compared the cumulative invoiced quantity with the quantity received on that position by the payment date and by year end; credit notes and receipt reversals taken into account.
3. Excluded 15 invoices where the shortfall is a return to the vendor covered by a credit note (for example 51007354/45002057, E25-00014/45002288, 51007431/45002110): the positions are balanced in quantity at year end.
4. Treated ADV vendors (70026, 70044) separately; advance payment is recorded in their payment terms.
5. Treated the two misdirected receipts (50013358 line 2, W25-00190) as received.
6. Counted the two paid duplicates (51007509, E25-00296) because no receipt stood behind the second payment. For E25-00296, 40 pieces arrived a week after payment (W25-00382); that delivery has not been invoiced in its own right, so the vendor effectively holds NVK 105,120.00 against a delivery worth 70,080.00 gross.
7. Amount = amount paid per payments file. EUR at the booking rate of the payment month.

### Q3

1. Method from manual 7.7: per order line, delivery note date (document date of the receipt) against the confirmed delivery date of the order line; partial deliveries with the value delivered; value = quantity × order price.
2. Reversal-and-re-entry pairs netted out on the original delivery note date (26 correction documents in the year, 11 of them on orders with a confirmed date). Returns to vendor (movement 102 with text "return to vendor") not deducted: the goods were delivered.
3. Same receipt corrections as in Q1: W25-00388 and 50013156 dropped as duplicates; W25-00397 moved to P25-0169/30; W25-00190 moved to P25-0116/10; P25-0203 valued in EUR.
4. Only deliveries with a 2025 delivery note date. NVK orders converted at the booking rate of the delivery month.
5. Late = delivery note date after the confirmed date, no tolerance: 106 of 324 measurable deliveries on the dates as recorded.
6. Overwritten dates: the system keeps only the last date. I treated a line as overwritten where the change date precedes the recorded delivery date and that date either differs from the other lines of the same order or lies outside the vendor's usual lead time. Eleven lines: P25-0004/10, P25-0051/20, P25-0095/30, P25-0099/20, P25-0119/10, P25-0119/20, P25-0206/20, P25-0212/10, P25-0218/30, P25-0228/10, P25-0228/20. All their deliveries count as late in the corrected figure (adds EUR 56,439). Changes dated on or after the recorded delivery date coincide with a price that differs from the standard price; I read them as price changes and left them alone.

## 3. Assumptions

- GRNI is defined as in manual 7.3: sum of credit positions per order position, no netting, split group / third parties.
- Year-end translation at 11.8260 on the NVK book value. EUR-denominated positions are not revalued to their EUR document amount; if they were, the group part would be EUR 107,147.04 instead of 106,399.56 and P25-0203 EUR 36,400.00 instead of 36,146.07 (total EUR 221,883).
- Small over-deliveries and unit rounding differences that the accountant cleared, or clearly tried to clear, are not GRNI (the affiliate judged that no invoice will follow). This covers 45002232/10 and 45002260/10 (together NVK 4,696 of real over-delivery, EUR 397).
- P25-0203 is a EUR order: vendor currency EUR, material standard prices 7,450.00 and 660.00 in EUR, identical figures in the order.
- P25-0076 is still owed: no invoice from the vendor in the data, the item was 101 days old and far above both clearing limits.
- A receipt with the same delivery note number, quantity and position as an earlier unreversed receipt is a duplicate entry, not a second delivery.
- "Paid without a goods receipt" means: paid, and no receipt in the system covering the invoiced quantity at year end. Goods physically in the building but not recorded count as without receipt.
- "Purchase volume" for Q3 is the value of goods delivered at order price; service invoices without an order are not part of it.

## 4. Problems found in the data

**Receipts**
- Duplicate receipts: W25-00388 (P25-0222, 202,200.00), 50013156 (45002107, 6,700.00). Inventory is overstated by the same amounts.
- Receipts on the wrong position or order: 50013358 line 2, W25-00397, W25-00190. Two of them are also valued at the wrong price (inventory off by −24,660.00 and +36,000.00).
- Unit codes in mixed case (car, set, pce, rol, box); 11 receipt lines without delivery note number and 13 with "w/o DN".
- Receipt and return quantities carry no sign; corrections and returns share movement 102 and can only be told apart by the text.

**Invoices**
- Three duplicate invoices, reference retyped differently: 51007509 (F-37924 vs F-037924), E25-00296 (INV202524992 vs INV-2025-24992), E25-00379 (R-33067-25 vs R/33067/25). The first two are paid; E25-00379 (26,904.00) is unpaid and should be blocked.
- E25-00116: NVK invoice booked in EUR. Clearing debit of 211,053.90 and payable of 253,264.68 instead of 18,300.00 / 21,960.00; paid 21,960.00 NVK.
- 51007517 (45002174/10): quantity 18,000 entered with unit BOX instead of PCE. The system posted a bogus price difference of 31,975.92 as income on 5890 and left the same amount as debit on the clearing account.
- 51007634 paid 12,762.00 against an invoice of 12,672.00.
- Vendor references with leading or trailing blanks (for example " F-014923").

**Manual journals on the clearing account**
- J25-0065: 313,000.00 of uninvoiced receipt released to income (5890) on 19.12.2025. Local limit NVK 2,500, group limit EUR 150.
- J25-0057: 38,400.00 (P25-0031/10) cleared on 31.10.2025; the invoice E25-00330 arrived on 18.11.2025. Clearing account now shows a false debit of 38,400.00 and 5890 a false gain.
- J25-0019: 5,460.90 (P25-0021/10), above both limits.
- 10000887 posted with the wrong sign; 10000896 posted against inventory 1410; J25-0049 without assignment and without vendor; J25-0054 with transposed amount.
- The local limit (NVK 2,500) and the group limit (EUR 150, about NVK 1,770) differ; several clearings sit between the two.
- Net effect of the errors above on 5890: income overstated by roughly NVK 383,000 (313,000.00 + 38,400.00 + 31,975.92).

**Orders**
- P25-0203 in NVK for a EUR vendor: inventory and GRNI understated by about NVK 391,000.
- Confirmed delivery dates exist only for the 279 lines created from 1 July; dates are overwritten when a delay is announced.
- 18 order headers without buyer.

**Mapping sheet**
- Account 2815 has no mapping row at all, although it carries NVK 1,748,608.94 at year end (should go to 211520).
- Account 1450 has two overlapping rows from 1 July (120150 and 120500); it carries the goods-in-transit reclassification of NVK 6,213,515.68.
- Account 6950 has no mapping for July 2025 (old row ends 30.06., new row starts 01.08.).
- 2810 maps to 211510 from July, but still holds the pre-July group postings.
- Local instruction LI-FIN-04 still names 6900 for exchange differences and only 2810 as clearing account.

**Debit positions that need follow-up (not GRNI, NVK 707,469.82 in the ledger)**
- Paid without receipt: 45002121/10, 45002184/10, 45002270/10+20, P25-0104/10, P25-0178/10, P25-0243/10, P25-0045/10.
- Duplicate invoices: 45002139, P25-0130, P25-0167.
- False debits from errors: 45002174/10, P25-0031/10, 45002225/20, P25-0116/10.
- Return awaiting credit note: P25-0149/10.

## 5. What I am unsure about

- **P25-0203 (EUR 36,146 of the Q1 answer).** I read the order as EUR entered as NVK. If the order really is NVK 36,400, GRNI drops to about EUR 187,800.
- **P25-0076 (EUR 26,467).** The write-off may rest on a vendor confirmation I cannot see. If no invoice will come, GRNI drops by that amount; if both this and P25-0203 fall away, the figure is about EUR 161,300.
- **P25-0059 / P25-0116.** I matched the surplus receipt W25-00190 to P25-0116 on vendor, material, quantity and date (it was posted on P25-0116's confirmed delivery date). If it was a real second delivery on P25-0059, GRNI rises by NVK 36,400 (EUR 3,078) and E25-00227 (45,312.00) joins the Q2 list.
- **P25-0222.** If the second receipt was a real second delivery of the full order rather than a duplicate entry, GRNI rises by NVK 202,200 (EUR 17,098).
- **Laboratory orders in Q2 (51007515, E25-00188).** The handover note says lab deliveries often never get a receipt although the goods are in the building. The data cannot tell whether that happened here.
- **Duplicates in Q2.** Whether a duplicate payment counts as "paid without a goods receipt" is a matter of definition; without them the answer is six invoices, NVK 331,842.00 (EUR 28,666).
- **Q3 overwritten dates.** For P25-0119, P25-0212 and P25-0228 no line of the order kept the original date, so the classification rests on unusual lead times only (EUR 13,728 of the late volume). Overwrites that left no trace cannot be found at all, so 22.2 % is more likely too low than too high.
- **Q3 scope.** No tolerance is defined; one day late counts as late. Whether returned goods and the first half-year should be in the denominator is not specified; I used delivered volume with a confirmed date.
- **Cut-off.** I can only see documents posted up to 31.12.2025. Goods received in December and posted in January, or receipts never entered, are not in any of the figures.
- **Completeness of the ledger extract.** It covers a range of accounts only, so I could not check that documents balance or trace payments through the ledger.
