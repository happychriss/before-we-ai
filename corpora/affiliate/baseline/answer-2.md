# Meridia Pharma Norvania – purchasing data FY2025: answers to the three questions

Amounts in NVK are local-currency book amounts. The closing rate is 11.8260 NVK/EUR (`fx_rates.csv`, `rate_eom` 2025-12). The December booking rate is 11.7435.

## 1. The three answers

### Q1 – Goods received but not yet invoiced (GRNI) at 31.12.2025

**EUR 220,881** (NVK 2,612,143 at the closing rate), after corrections.

| | NVK | EUR |
|---|---:|---:|
| Third parties (group account 211510) | 1,353,861.75 | 114,481.80 |
| Group company Meridia Supply Chain (211520) | 1,258,281.25 | 106,399.56 |
| **Total, corrected** | **2,612,143.00** | **220,881.36** |

For comparison, the ledger as extracted gives different figures:

| Uncorrected ledger view | NVK | EUR |
|---|---:|---:|
| Sum of order positions with a credit balance on 2810 + 2815 (the manual's 7.3 definition) | 2,157,774.50 | 182,460.21 |
| Net balance of 2810 + 2815 (not the reportable figure) | 1,448,117.78 | 122,452.04 |

The corrected figure rests on two judgement calls that add to the liability:

- **P25-0076 (EUR 26,467):** I reinstated a receipt that was written off in December without an invoice. Without it the total is EUR 194,414.
- **P25-0130 (EUR 4,938):** I show 40 received pieces as uninvoiced, although a duplicate invoice hides them in the ledger. Without it the total is EUR 215,943.
- Without both, the total is EUR 189,476.

### Q2 – Vendor invoices paid without a goods receipt

**Six invoices, NVK 276,460 net (NVK 331,842 paid including VAT), about EUR 23,882 net (EUR 28,666 paid).** These are goods invoices on purchase orders that were paid although no receipt exists for the order position up to year end, the vendor is not on advance-payment terms, and no mis-posted receipt explains it.

| Invoice | Vendor | Order / pos. | Net NVK | Paid NVK | Paid on | Net EUR | Paid EUR |
|---|---|---|---:|---:|---|---:|---:|
| 51007419 | 70041 Paleta Drovnik | 45002121/10 | 58,200.00 | 69,840.00 | 27.03.2025 | 5,135.67 | 6,162.81 |
| 51007515 | 70022 Reagens Mivor (lab) | 45002184/10 | 25,500.00 | 30,600.00 | 29.05.2025 | 2,239.99 | 2,687.98 |
| 51007634 | 70034 Uredska Oprema Hrist | 45002270/10, /20 | 10,560.00 | 12,762.00 | 17.07.2025 | 918.94 | 1,110.56 |
| E25-00116 | 70043 Termo Log Savrin | P25-0045/10 | 18,300.00 | 21,960.00 | 11.09.2025 | 1,576.97 | 1,892.37 |
| E25-00188 | 70023 Analitika Preles (lab) | P25-0104/10 | 44,700.00 | 53,640.00 | 16.10.2025 | 3,859.77 | 4,631.72 |
| E25-00313 | 70045 Senzor Tehnika Olvar | P25-0178/10 | 119,200.00 | 143,040.00 | 11.12.2025 | 10,150.30 | 12,180.36 |
| **Total** | | | **276,460.00** | **331,842.00** | | **23,881.64** | **28,665.80** |

EUR is at the booking rate of the payment month.

- Invoice 51007634 has a gross of NVK 12,672.00 but NVK 12,762.00 was paid, an overpayment of NVK 90 (transposed digits).
- The two lab invoices (51007515, E25-00188) are probably missing receipt postings rather than missing goods; the handover note describes exactly this for lab deliveries.

Related cases that I did not count in the six:

- **Duplicate invoices paid a second time, with no second delivery:**
  - 51007509 (vendor 70032, order 45002139, duplicate of 51007461): NVK 4,600 net, 5,520 paid on 15.05.2025.
  - E25-00296 (vendor 70011, order P25-0130, duplicate of E25-00256): NVK 87,600 net, 105,120 paid on 04.12.2025.
  - Together NVK 110,640 paid, about EUR 9,436.
  - A third duplicate, E25-00379 (vendor 70041, order P25-0167, duplicate of E25-00318, NVK 26,904 gross), is posted but not yet paid and should be blocked.
- **Advance-payment vendors (terms ADV, allowed by manual 7.1):** seven invoice lines of vendors 70026 and 70044 were paid before receipt (invoices 51007348, 51007433, 51007579, E25-00145, E25-00255, E25-00360). Only E25-00360 (order P25-0243, NVK 26,800 net, 32,160 paid on 11.12.2025) is still without receipt at year end; delivery is due 12.01.2026.
- **Receipt exists but was posted to the wrong place:**
  - E25-00227 (vendor 70012, order P25-0116, NVK 37,760 net): the receipt W25-00190 was posted to order P25-0059.
  - 51007596 line 2 (vendor 70021, order 45002225/20, NVK 42,300 net): the receipt 50013358 line 2 was posted to position 10.
- **Group invoices:** none was paid before the goods were received. The 14 group positions invoiced but not received at year end (NVK 6,213,515.68, goods in transit) are unpaid.

### Q3 – Share of purchase volume delivered late

**21.8 % of the measurable volume: EUR 844,437 late out of EUR 3,866,333.** Delivery performance can only be measured for orders created from 1 July 2025 (P25- orders), because only they carry a confirmed delivery date.

| | Late EUR | Measured EUR | Share |
|---|---:|---:|---:|
| Group supply company (79001) | 565,410 | 3,100,656 | 18.2 % |
| Third-party vendors | 279,027 | 765,677 | 36.4 % |
| **Total** | **844,437** | **3,866,333** | **21.8 %** |

- There are 112 late delivery events; the median delay is 14 days and the longest is 66 days.
- By delay: EUR 113,016 was 1–3 days late, EUR 52,337 was 4–7 days, EUR 196,363 was 8–14 days and EUR 482,721 was more than 14 days.
- Not measurable: EUR 5,531,739 of the EUR 9,398,072 received in 2025 (59 %). Of this, EUR 4,917,600 was delivered in the first half-year and EUR 614,140 in the second half-year against old 45- orders without a date.
- Taking the dates as they stand in the system, without my reconstruction of six overwritten dates, the figure is EUR 801,727 (20.7 %).
- Counting five more lines whose original date was overwritten and cannot be reconstructed, it is EUR 858,165 (22.2 %).

## 2. How I got each number

### Q1 – GRNI

Method, following group manual 7.3:

1. I took all ledger lines on clearing accounts 2810 and 2815 together, as the handover note requires.
2. I parsed the assignment field in both formats: order number plus five-digit position before 1 July, and order number, slash, position after.
3. I summed per order position and kept the positions with a credit balance, without netting debit positions.
4. I checked every non-zero position against the receipts, invoices and payments of that order.
5. I translated at the closing rate of 11.8260.

The ledger agrees with the documents: every 2025 receipt line and every 2025 order-related invoice line matches a ledger line in amount. So the corrections below are errors in the documents themselves, not extraction gaps.

**Positions in the corrected figure**

| Order / pos. | Vendor | NVK | EUR | Comment |
|---|---|---:|---:|---|
| P25-0184/10, /20, /30 | 79001 | 578,076.13 | 48,881.80 | Received 12.12., no invoice yet |
| P25-0199/10, /20 | 79001 | 680,205.12 | 57,517.77 | Received 19.12., no invoice yet |
| P25-0224/10, /20, /30 | 70011 | 234,929.79 | 19,865.53 | Received 09.12. and 25.12.; position 10 partly invoiced |
| P25-0218/10, /20, /30 | 70045 | 44,680.56 | 3,778.16 | Received 25.12. |
| P25-0215/10 | 70041 | 19,788.00 | 1,673.26 | Second delivery of 51 pieces on 25.12. |
| P25-0222/10, /20 | 70012 | 202,200.00 | 17,097.92 | Booked 404,400; corrected, see below |
| P25-0169/30 | 70045 | 53,400.00 | 4,515.47 | Booked 89,400 on position 10; corrected |
| P25-0203/10, /20 | 70025 | 427,463.40 | 36,146.07 | Booked 36,400; corrected |
| P25-0076/10, /20 | 70043 | 313,000.00 | 26,467.11 | Booked 0; reinstated |
| P25-0130/10 | 70011 | 58,400.00 | 4,938.27 | Booked as a debit of 29,200; corrected |

**Corrections that change a kept position**

- **P25-0222, duplicate receipt.** W25-00388 (12.12., user WH02) repeats W25-00380 (10.12., user WH01): same delivery note LS515398, same quantities, and the order quantity is received twice. I removed NVK 202,200.
- **P25-0169, wrong position.** W25-00397 is 60 boxes of material 500011 (humidity cards) posted to position 10 (data loggers) and valued at the logger price, NVK 89,400. It belongs to position 30 (60 boxes at NVK 890 = 53,400). I removed NVK 36,000.
- **P25-0203, wrong currency.** Vendor 70025 is a EUR vendor and the prices equal the EUR standard prices (7,450 and 660), but the order header says NVK. The receipt W25-00369 was therefore booked at NVK 36,400 instead of EUR 36,400 (× 11.7435 = NVK 427,463.40). I added NVK 391,063.40.
- **P25-0076, write-off reinstated.** Journal J25-0065 (19.12., user DPET) cleared NVK 239,800 and 73,200 to price differences. The receipt W25-00148 dates from 09.09., no invoice exists, the amount is far above both limits (NVK 2,500 local, EUR 150 group), and nothing in the data shows a vendor confirmation. I treat the liability as still existing.
- **P25-0130, duplicate invoice hides a real receipt.** 100 pieces were received (60 on 08.10., 40 on 11.12.). Invoice E25-00256 covers 60 pieces; E25-00296 is the same vendor invoice entered again (reference INV202524992 versus INV-2025-24992). The 40 pieces received on 11.12. are genuinely uninvoiced (NVK 58,400). The duplicate (NVK 87,600 net) is a claim against the vendor, not an offset.

**Credit positions I excluded (NVK 69,894.90 in total)**

| Order / pos. | NVK | Reason |
|---|---:|---|
| 45002107/10 | 6,700.00 | Duplicate receipt: 50013156 repeats 50013151, same delivery note DN23028 |
| 45002225/10 | 17,640.00 | Receipt 50013358 line 2 (material 300003) posted to position 10 instead of 20; both positions are fully invoiced |
| P25-0059/10 | 36,400.00 | Receipt W25-00190 (29.09., 80 cartons of material 200007) belongs to order P25-0116/10 (same vendor, material and quantity, confirmed date 29.09.), which is invoiced and has no receipt |
| 45002232/10 | 4,472.00 | Over-delivery of 20 rolls (NVK 2,236); journal 10000887 posted the clearing on the wrong side and doubled it |
| 45002260/10 | 2,460.00 | Over-delivery of 40 rolls; journal 10000896 debited inventory 1410 instead of 2810, so the clearing account was never cleared |
| P25-0073/10, /20 and P25-0087/10 | 2,186.90 | One extra unit each (318.00 + 742.50 + 1,126.40); cleared in one line by J25-0049, which has no assignment |
| P25-0151/10 | 36.00 | One extra box (1,384.20); J25-0054 cleared 1,348.20, apparently a typing error |

That leaves NVK 2,087,879.60 of booked credit positions that I kept, of which I reduced P25-0222 and P25-0169 and revalued P25-0203.

**Reconciliation, NVK**

| | NVK |
|---|---:|
| Credit positions as booked | 2,157,774.50 |
| Excluded positions | −69,894.90 |
| P25-0222 duplicate receipt | −202,200.00 |
| P25-0169 revaluation | −36,000.00 |
| P25-0203 currency | +391,063.40 |
| P25-0076 reinstated | +313,000.00 |
| P25-0130 uninvoiced receipt | +58,400.00 |
| **Corrected** | **2,612,143.00** |

**Debit positions (not netted, not part of the answer)**

- Group positions invoiced but not received (orders P25-0219, P25-0227, P25-0240, P25-0255; 14 positions) were reclassified to goods in transit by J25-0066 on 31.12.: NVK 6,213,515.68, about EUR 525,411. Their clearing balance is zero.
- Third-party debit positions total NVK 709,656.72 as booked. They consist of the invoices without receipt from Q2, the duplicate invoices, the advance P25-0243, an expected credit note on P25-0149 (return of 50 rolls on 16.12., NVK 4,800) and three bookkeeping artefacts:
  - P25-0045/10 shows NVK 211,053.90 instead of 18,300, because invoice E25-00116 was entered in EUR.
  - 45002174/10 shows NVK 31,975.92, because invoice 51007517 was entered as 18,000 boxes instead of 18,000 pieces and the system posted a bogus difference.
  - P25-0031/10 shows NVK 38,400, because the receipt was written off by J25-0057 on 31.10. and the invoice E25-00330 arrived on 18.11.

### Q2 – Invoices paid without goods receipt

1. I restricted the test to invoice lines that reference a purchase order. The 130 invoices without order are rent, utilities, leasing, services and similar, and are outside the three-way match (manual 7.1).
2. I converted invoice quantities to order units with the pack sizes of the material master, because several vendors bill in pieces, bottles or reams.
3. I corrected the receipts first: the two duplicate receipts removed (50013156, W25-00388) and the three mis-assigned receipts moved (W25-00190, 50013358 line 2, W25-00397).
4. For every paid invoice line I compared the net received quantity at the payment date and at year end with the quantity invoiced so far.
5. Lines where returns (movement 102, "return to vendor") were later matched by a credit note are not findings: orders 45002057, 45002063, 45002110, 45002150, 45002154, 45002176, 45002196, 45002247, 45002249, 45002255, 45002262, 45002288 and P25-0054.
6. What remained I classified as shown in section 1: no receipt at all (the six invoices), duplicates, advance-payment vendors, and receipts posted to the wrong place.

### Q3 – Late deliveries

1. Rule from manual 7.7: per order line, the delivery note date (`doc_dt` of the receipt) against the confirmed delivery date (`dlv_dt`). A partial delivery counts with the value delivered. Late means any day after the confirmed date; I applied no tolerance.
2. Deliveries are movement 101 lines minus correction reversals. Re-entries keep the original delivery note date (I checked all 58 correction reversals), so corrections do not shift the date. Returns to the vendor are not deducted, since the delivery took place.
3. The same receipt corrections as in Q1 and Q2 apply:
   - W25-00388 is excluded as a duplicate.
   - W25-00190 is measured against P25-0116 (on time) instead of P25-0059, where it would count as 35 days late.
   - W25-00397 is measured on P25-0169/30 at NVK 890 per box.
   - P25-0203 is valued in EUR.
4. Value is quantity times order price. NVK orders are converted at the booking rate of the receipt month; EUR orders are taken directly.
5. Overwritten dates: purchasing overwrites the confirmed date when a vendor announces a delay. All lines of an order normally share one date, so for six lines whose date differs from the other lines of the same order I used the other lines' date as the original:

| Order / pos. | Date in system | Original used | Delivered |
|---|---|---|---|
| P25-0004/10 | 30.07. | 16.07. | 28.07. |
| P25-0051/20 | 13.10. | 08.09. | 13.10. |
| P25-0095/30 | 15.10. | 10.10. | 13.10. |
| P25-0099/20 | 23.10. | 29.09. | 23.10. |
| P25-0206/20 | 09.12. | 05.12. | 08.12. |
| P25-0218/30 | 22.12. | 15.12. | 22.12. |

   This adds EUR 42,710 of late volume compared with the dates as stored.
6. Five further changed lines have no unchanged line in the same order to compare with: P25-0212/10, P25-0228/10 and /20, P25-0119/10 and /20. Their deliveries on or before the stored date (EUR 13,729) are counted as on time in the headline.
7. The other changed lines have a price different from the standard price and the same date as the rest of the order, so I read the change as a price change and left the date alone.

## 3. Assumptions

- GRNI follows the group manual: credit positions per order position, 2810 and 2815 together, no netting, closing rate.
- A receipt with the same delivery note, order position and quantity as an earlier unreversed receipt, and which doubles the ordered quantity, is a duplicate.
- A receipt whose material does not match the order position belongs to the position of the same order with that material. W25-00190 belongs to P25-0116 because vendor, material, quantity and confirmed date all match.
- Small over-deliveries that the accountant tried to clear are not liabilities, even where the journal was posted wrongly. If they were kept, GRNI would rise by about EUR 700 (NVK 8,267).
- P25-0203 is a EUR order; I used the December booking rate for what should have been booked.
- For Q2, "paid without a goods receipt" means no receipt for the position at all up to 31.12.2025. Contractual advance payments and duplicates are shown separately.
- For Q3, "purchase volume" means value of goods received on orders, at order price. Invoices without order (services) are not included.
- EUR translation: closing rate for Q1 (balance sheet), monthly booking rate for Q2 and Q3 (transactions).

## 4. Problems found in the data

**Receipts**
- Duplicate receipts: 50013156 (order 45002107) and W25-00388 (order P25-0222).
- Receipts on the wrong position or order: 50013358 line 2, W25-00397, W25-00190.
- Unit codes in mixed case (`car`, `box`, `pce`, `rol`, `set`) and delivery note numbers in mixed case or `w/o DN`.

**Invoices**
- Three duplicate invoices, entered with reformatted references: 51007509, E25-00296, E25-00379. Two were paid.
- E25-00116 has currency EUR for an NVK vendor; the ledger shows NVK 211,053.90 instead of 18,300, while the payment was NVK 21,960.
- 51007517 has 18,000 with unit BOX instead of PCE, which triggered an automatic difference posting of NVK 31,975.92.
- 24 vendor references carry leading or trailing blanks, which defeats an exact duplicate check.
- Payment Z25-0025 is NVK 90 higher than the invoice gross.
- Payee names in `payments.csv` are free text (114 spellings for 40 vendors). I found no payee that points to a different company.

**Manual journals on the clearing account**
- J25-0065 (NVK 313,000) and J25-0057 (NVK 38,400) are far above both limits and were posted on items younger than 180 days. J25-0057 was followed by the invoice 18 days later.
- J25-0019 (NVK 5,460.90) is above the local limit of NVK 2,500.
- J25-0049 has no assignment and clears three positions in one line.
- 10000896 posts to inventory, which the manual forbids. 10000887 is on the wrong side. J25-0054 clears the wrong amount.
- The local limit (NVK 2,500) and the group limit (EUR 150, about NVK 1,770) differ; several clearings fall between the two.

**Order master data**
- P25-0203 has the wrong currency.
- The confirmed delivery date is missing on all 45- orders and is overwritten on delays; only the last change date is kept.
- The order status flag is "O" on many fully delivered and invoiced orders, so it is not usable.

**Account mapping (`acct_mapping.xlsx`)**
- Account 2815 (group clearing, 373 ledger lines since July) is not mapped at all. Group account 211520 exists but nothing maps to it.
- Account 1450 maps to two group accounts from 1 July (120150 and 120500).
- Account 6950 has no mapping for July 2025 (9 lines, NVK 6,534.30); the new line starts on 1 August.
- Account 2810 mapped to 211500 until 30 June and to 211510 afterwards, so first-half figures are not split between third parties and group.

**Formats and coverage**
- Dates are `dd.mm.yyyy` in orders, receipts and payments and ISO in invoices and ledger.
- The assignment field has two formats.
- The ledger covers 2025 only; 2024 history is present only as nine carried-forward positions.
- The local instruction still names 6900 for exchange differences; 6950 is in use.

## 5. What I am unsure about

- **P25-0076 (EUR 26,467).** I cannot see whether the vendor confirmed that no invoice will follow. If so, the write-off stands and GRNI is lower.
- **P25-0130 (EUR 4,938).** Whether to show the 40 uninvoiced pieces gross, or net against the duplicate invoice, is a presentation choice; I chose gross.
- **P25-0203.** I infer the EUR currency from the vendor master and the standard prices. If the order really was agreed in NVK, GRNI is lower by about EUR 33,068.
- **Group positions in EUR.** I translated the NVK book value at the closing rate (EUR 106,400). At EUR order value the same goods are EUR 107,147. For P25-0203 the same effect is EUR 254.
- **Unrecorded receipts.** Goods in the building without a receipt posting (the lab case) and without an invoice are invisible in the data, so GRNI may be understated. Of the six Q2 invoices I cannot tell which goods really arrived.
- **Extra units.** I assumed the single extra units and rolls are free. If vendors bill them, about NVK 8,267 (EUR 700) more is owed.
- **W25-00190.** The reassignment to P25-0116 is an inference. If it was a second, unordered delivery on P25-0059, GRNI rises by NVK 36,400 (EUR 3,078), invoice E25-00227 becomes a seventh "paid without receipt" case (NVK 37,760 net), and the late volume rises.
- **Late deliveries.** The original confirmed dates of overwritten lines are reconstructed, not recorded. The five unreconstructable lines could add EUR 13,729. The headline uses no tolerance and counts calendar days. The 21.8 % describes only the second-half orders; nothing can be said about the 59 % of volume without a confirmed date.
- **Promotional materials.** Six invoices without order for "Promotional materials campaign" (NVK 539,826, account 6500) could be goods that the local instruction says need an order. I treated them as services.
- **Cut-off.** I see nothing posted after 31.12.2025, so I cannot test for December deliveries that were recorded in January.
