"""Text of the three documents delivered with the affiliate landscape.

The documents describe rules and practice. They never refer to an individual
record. Each document is a list of (style, text) blocks; style is "h1", "h2",
"p" or "meta".
"""

POSTING_INSTRUCTION = [
    ("h1", "Local Instruction LI-FIN-04"),
    ("h1", "Purchasing, goods receipt and invoice verification"),
    ("meta", "Meridia Pharma Norvania d.o.o. - Finance department"),
    ("meta", "Version 3 - valid from 1 March 2023 - owner: Head of Finance - next review: March 2024"),
    ("h2", "1. Purpose and scope"),
    ("p", "This instruction describes how purchases of goods are recorded in the local system: trade "
          "goods supplied by the group and packaging, laboratory, office and logistics materials bought "
          "from local and foreign vendors. Every purchase of goods requires a purchase order in the "
          "system. Services, rent, utilities, leasing and similar costs are not ordered in the system; "
          "their invoices are booked directly to the cost account and cost centre named by the requester."),
    ("h2", "2. Document numbers"),
    ("p", "The system assigns eight-digit numbers by document class: purchase orders 45xxxxxx, goods "
          "receipt documents 50xxxxxx, vendor invoices and credit notes 51xxxxxx, manual journals "
          "10xxxxxx and payment documents 15xxxxxx. The accounting document of a goods receipt or an "
          "invoice carries the same number as the receipt or the invoice. In the assignment field of a "
          "ledger line the system writes the order number followed by the five-digit order position "
          "without a separator."),
    ("h2", "3. Purchase orders"),
    ("p", "Purchasing enters the vendor, the material, the quantity in the order unit and the price per "
          "order unit. The order currency is taken from the vendor master. The conversion between the "
          "order unit and the base unit (for example cartons to packs, boxes to pieces) comes from the "
          "material master. Delivery dates are agreed with the vendor by e-mail; the delivery date field "
          "of the order line is not used. If a price is renegotiated after the order was sent, "
          "purchasing should change the order line; the system then shows the new price and the date of "
          "the change, and receipts posted earlier keep their value."),
    ("h2", "4. Goods receipt"),
    ("p", "The warehouse posts the receipt with movement type 101 against the order position on the day "
          "the goods arrive or on the next working day, and enters the number and the date of the "
          "vendor's delivery note. The receipt is valued at the order price. For orders in EUR the "
          "system uses the booking rate of the posting month, which is the closing rate of the previous "
          "month. The receipt debits inventory (1400 trade goods, 1410 other materials and supplies) "
          "and credits the clearing account 2810."),
    ("p", "A posted receipt is never changed. A mistake is corrected with movement type 102, which "
          "refers to the original document, followed by a new receipt with the correct data and the "
          "original delivery note. Goods sent back to the vendor are also posted with movement type "
          "102. Quantities and amounts of receipt documents are always shown without a sign; the "
          "movement type gives the direction."),
    ("h2", "5. Invoice verification"),
    ("p", "Accounts payable enters the vendor's invoice number in the reference field and assigns each "
          "invoice line to an order position. Quantities are entered in the unit printed on the "
          "invoice; the system converts them to the order unit. The invoice debits the clearing account "
          "2810 and credits the vendor: 3300 for domestic vendors, 3310 for foreign vendors, 3350 for "
          "group companies. Credit notes are entered with document type KG, with positive amounts."),
    ("p", "When receipt and invoice for a quantity are both posted, the system posts the difference "
          "between the receipt value and the invoice value automatically: to 5890 (price differences) "
          "for orders in NVK and to 6900 (exchange differences) for orders in EUR."),
    ("p", "An invoice for goods that have not yet been received may be entered and released for payment "
          "if the requester confirms the delivery in writing; an e-mail is sufficient. Invoices of the "
          "group supply company are issued on dispatch and normally arrive before the goods. At the "
          "half-year and at year end the Head of Finance reclassifies group deliveries that are "
          "invoiced but not yet received from the clearing account to 1450 (goods in transit); the "
          "journal is reversed on the first day of the following period."),
    ("h2", "6. Clearing of account 2810"),
    ("p", "At month end the accountant reviews the list of open items on 2810. Small remaining "
          "differences on order positions for which no further invoice and no further delivery are "
          "expected - free over-deliveries, rounding between units - are cleared with a manual journal "
          "(document type SA) against 5890. The order number and position are entered in the assignment "
          "field. The accountant may clear up to NVK 2,500 per order position; larger amounts need the "
          "approval of the Head of Finance."),
    ("h2", "7. Payments"),
    ("p", "The payment run takes place every Thursday and pays the invoices due. Credit notes are "
          "deducted from the next payment to the vendor. Payables to group companies are settled once "
          "a month through group netting. Vendors with payment terms ADV are paid on receipt of the "
          "invoice, before delivery."),
    ("h2", "8. Tax"),
    ("p", "Domestic purchases carry the standard VAT rate of 20 % (tax code V2). Invoices from foreign "
          "vendors and from group companies are entered without tax (tax code V0)."),
]

GROUP_MANUAL = [
    ("h1", "Meridia Pharma Group - Group Accounting Manual"),
    ("h1", "Extract: Chapter 7 - Goods receipt, invoice verification and the clearing account"),
    ("meta", "Group Finance - edition 2025 - applies to all consolidated entities, including entities "
             "that do not run the group ERP"),
    ("h2", "7.1 Three-way match"),
    ("p", "A vendor invoice for goods is paid only when purchase order, goods receipt and invoice agree "
          "in quantity and price. The only exception is an advance payment agreed in the contract and "
          "recorded in the payment terms of the vendor master. Invoices without a purchase order are "
          "permitted for services, rent, utilities and similar costs and require the approval of the "
          "cost centre owner; they are outside the three-way match."),
    ("h2", "7.2 Valuation of the goods receipt"),
    ("p", "A goods receipt is valued at the order price. For orders in a foreign currency the entity "
          "uses its booking rate of the posting month. Differences between receipt value and invoice "
          "value are shown as price differences or exchange differences in the income statement."),
    ("h2", "7.3 The clearing account and the reported balance"),
    ("p", "The clearing account between goods receipt and invoice receipt is credited with the receipt "
          "and debited with the invoice. It is analysed per order position at every reporting date. "
          "Positions with a credit balance are goods received but not yet invoiced and are reported as "
          "an accrued liability in group account 211510 (third parties) or 211520 (group companies). "
          "Positions with a debit balance are invoiced but not yet received; they are not netted "
          "against the liability. Deliveries from group companies under way are reported as goods in "
          "transit, other debit positions as advances to suppliers. The reported figure for goods "
          "received not invoiced is therefore the sum of the positions with a credit balance, not the "
          "net balance of the account."),
    ("h2", "7.4 Currency translation"),
    ("p", "Balance sheet items of an entity are translated into EUR at the closing rate of the reporting "
          "month. Income statement items are translated at the booking rate of the month in which they "
          "were posted."),
    ("h2", "7.5 Manual journals on the clearing account"),
    ("p", "Manual journals on the clearing account are permitted only to clear a difference for which "
          "no further document is expected. Every line carries the order number and the order position "
          "in the assignment field and the reason in the text, and is approved by a second person. The "
          "offsetting account is the price difference account; manual clearings are never posted to "
          "inventory or vendor accounts. The limit is EUR 150 per order position. Above the limit a "
          "written confirmation of the vendor and the approval of the regional controller are required. "
          "An item older than 180 days may not be written off without a written confirmation of the "
          "vendor that no invoice will follow."),
    ("h2", "7.6 Duplicate invoices"),
    ("p", "The reference of a vendor invoice is entered exactly as printed on the invoice. Before "
          "posting, the entity checks vendor, reference, invoice date and amount against invoices "
          "already posted."),
    ("h2", "7.7 Delivery performance"),
    ("p", "From 1 July 2025 every entity records the confirmed delivery date in each purchase order "
          "line. Delivery performance is measured per order line by comparing the date of the vendor's "
          "delivery note with the confirmed delivery date. A partial delivery counts with the value "
          "delivered. The correction of a receipt by reversal and re-entry does not change the date of "
          "delivery."),
    ("h2", "7.8 Mapping of local accounts"),
    ("p", "Entities with a local chart of accounts maintain a mapping to the group chart. Every local "
          "account that carries postings is mapped to exactly one group account for every day of the "
          "reporting period. A change to the mapping takes effect on the first day of a month; periods "
          "already reported are not restated."),
]

HANDOVER_NOTE = [
    ("h1", "Handover note - purchasing ledger and clearing account"),
    ("meta", "From: Jelka Kovarin, Accountant - To: Dario Petran - Copy: Marek Halvor, Head of Finance"),
    ("meta", "Velograd, 28 July 2025"),
    ("p", "Dario, as agreed here is what I do every month and what changed on 1 July. My last day is "
          "31 July. Tina Berec stays on accounts payable and knows the daily routine."),
    ("h2", "What changed on 1 July"),
    ("p", "New document numbers. Everything created from 1 July has a letter, the year and a running "
          "number: P25- for purchase orders, W25- for goods receipts, E25- for vendor invoices and "
          "credit notes, J25- for manual journals, Z25- for payments. Old orders keep their 45 number, "
          "so a W25 receipt or an E25 invoice against a 45 order is normal. The assignment field also "
          "changed: the system now writes order number, a slash and the position; before it was order "
          "number and five-digit position in one string."),
    ("p", "New clearing account. Group deliveries are posted to 2815 from 1 July, third-party "
          "deliveries stay on 2810. I did not move the old balances. An order that was invoiced in June "
          "and received in July therefore has one leg on 2810 and the other on 2815; you have to look "
          "at both accounts together."),
    ("p", "New mapping sheet. Group sent a list of changed group accounts in June. I copied the old "
          "sheet and gave the old lines an end date and the new lines a start date of 1 July. The first "
          "half-year was reported under the old mapping and was not restated."),
    ("p", "Delivery dates. Since July purchasing has to enter the confirmed delivery date in every "
          "order line; before that the field was simply empty. When a vendor announces a delay, "
          "purchasing overwrites the date. The system keeps only the last value and the date of the "
          "last change to the line."),
    ("h2", "Monthly routine on the clearing account"),
    ("p", "At month end I run the open items list for 2810 (now also 2815) and go through it line by "
          "line. Leftovers where nothing more will come - a few free units, rounding because the "
          "vendor bills in pieces and we order in cartons, boxes or rolls - I clear against 5890 with "
          "an SA journal. I normally put the order in the assignment field. When several small ones "
          "belong together I have sometimes cleared them in one line. We use the limit from the local "
          "instruction, NVK 2,500; the group manual says EUR 150. Marek's view is that the local "
          "instruction applies until it is rewritten."),
    ("p", "Exchange differences go to 6950 since 2024. The instruction still says 6900."),
    ("p", "At 30 June I reclassified the group invoices without receipt to 1450 from the open items "
          "list and reversed the journal on 1 July. The same is due at year end."),
    ("h2", "Things you will run into"),
    ("p", "Group invoices are raised when the goods leave the supply company and are usually here two "
          "weeks before the lorry. Sometimes it is the other way round and the invoice comes weeks "
          "after the goods."),
    ("p", "Several vendors bill in pieces while the order is in cartons, boxes or rolls. The pack sizes "
          "are in the material master. Tina enters the quantity and unit as printed on the invoice."),
    ("p", "The warehouse corrects receipts by reversing and posting again, sometimes days later. "
          "Returns to the vendor are also movement 102. The credit note usually follows within two or "
          "three weeks and is deducted in the next payment run."),
    ("p", "Laboratory orders are delivered straight to the lab on the second floor. The lab does not "
          "always pass the delivery note on to the warehouse, so a receipt can be missing in the "
          "system although the goods are in the building. When Tina has a lab invoice without a "
          "receipt I call the lab; if they confirm, we release the invoice."),
    ("p", "Two vendors only deliver against advance payment (terms ADV). Their invoices are paid "
          "first; the receipt follows when the goods arrive."),
    ("p", "Prices: purchasing sometimes agrees a new price after the order has gone out and does not "
          "always change the order. The invoice is then entered as it is and the difference goes to "
          "5890."),
    ("h2", "Open points"),
    ("p", "The local instruction LI-FIN-04 has not been updated for the changes of 1 July. The "
          "extraction for the group data warehouse runs on the third working day and takes the purchase "
          "documents, the ledger lines of the inventory, clearing, vendor and difference accounts, the "
          "mapping sheet and the rate table as they are on that day."),
]
