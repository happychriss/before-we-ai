# Vessel-company test corpus

This directory contains an independent, synthetic test corpus for **Hanseatic Vessel Works Group GmbH**,
a fictional medium-sized vessel builder with its headquarters and one yard in
Hamburg and a wholly owned production yard in Gdansk (also called "Danzig" in
legacy material).

The ten files in `source-documents/` are the business-facing corpus. Feed those
to a system under test. **Do not feed `ground-truth/` or this generator to the
system** if you want a blind evaluation.

## Questions the corpus is designed to answer

1. What is the cost of building a vessel?
2. What were our sales last year? (`last year` means FY2025 in this corpus.)
3. What is revenue per ship?

The wording is intentionally underspecified. A good system should not collapse
cost-to-date, forecast cost, accepted-vessel sales, percentage-of-completion,
invoice volume, cash receipts, VAT, service revenue, and intercompany activity
into one unexplained number.

## Business documents

1. `01_company_and_vessel_master.xlsx`
2. `02_project_cost_ledger_2025.xlsx`
3. `03_time_and_overhead_allocations.xlsx`
4. `04_sales_invoices_and_credit_notes_2025.xlsx`
5. `05_intercompany_recharges_2025.xlsx`
6. `06_bank_receipts_and_fx_2025.xlsx`
7. `07_board_management_report_2025.pdf`
8. `08_tax_and_transfer_pricing_memo_2025.pdf`
9. `09_contracts_change_orders_and_acceptance.pdf`
10. `10_yard_operations_notes_and_email_prints.pdf`

## Design

- Deterministic seed: `20250802`.
- All companies, people, customers, VAT IDs, contracts, invoices and amounts are
  fictional.
- Public tax facts in the tax memo were checked against EU, German and Polish
  authority pages, but the corpus is not legal or tax advice.
- Errors and omissions are deliberate. `ground-truth/TRAPS_AND_ANSWER_KEY.md`
  explains them.
- Regenerate with `.venv/bin/python corpus-vessel/generate_corpus.py` from the
  repository root.
