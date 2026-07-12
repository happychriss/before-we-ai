# Seeded-Recall report

mode: online
leakage scan of every logged request: CLEAN
false promotions (must be 0): 0

claims: 50 hypotheses (+0 deduped, 2 skipped), 22 role candidates
probes: 47 bound, 20 unbindable, 5 semantic-only, 0 unanswered
engine: 47 probes executed, 0 skipped
role questions: 1
token usage: {'input_tokens': 291502, 'output_tokens': 36713}

## Recall: 15/25 in-scope traps (semantic-only: 1/1)

| trap | result | matched claim |
|---|---|---|
| F1 | HIT | de_erp__invoices.order_reference references de_erp__orders.order_id. |
| F2 | HIT | de_erp__invoices.order_reference references de_erp__orders.order_id. |
| F3 | miss |  |
| F4 | miss |  |
| F5 | HIT | de_erp__customers.legacy_id maps migrated customers to kunden_migratio |
| F6 | HIT | de_erp__customer_hierarchy defines temporal validity per customer via  |
| F7 | miss |  |
| F8 | HIT | marketing_grouping__produktgruppen_marketing.marketing_product_group e |
| F9 | HIT | de_erp__territory_plz maps postal-code ranges (plz_from..plz_to) to te |
| F10 | HIT | de_erp__crm_activities.rep_id references de_erp__sales_reps.rep_id. |
| F11 | miss |  |
| F12 | HIT | de_erp__crm_activities.customer_reference references de_erp__customers |
| F13 | HIT | de_erp__crm_activities.customer_reference references de_erp__customers |
| F14 | miss |  |
| F15 | miss |  |
| F16 | HIT | de_erp__gl_postings.cost_center_id references de_erp__cost_centers.cos |
| F17 | miss |  |
| F18 | HIT | de_erp__fx_rates covers all 24 periods for each currency pair and rate |
| F19 | miss |  |
| F20 | HIT | de_erp__ar_open_items.invoice_reference references de_erp__invoices.do |
| F21 | miss |  |
| F22 | HIT | The DE and US intercompany postings are mirror sides of the same inter |
| F23 | out of scope (m5_docs) |  |
| F24 | out of scope (m5_docs) |  |
| F25 | miss |  |
| F26 | out of scope (m5_docs) |  |
| F27 | HIT | buchungen_report__buchungen_report.betrag_eur expresses the same monet |
| F28 | HIT | de_erp__gl_postings.amount_doc_currency and amount_local_currency are  |
| F29 | out of scope (m6_tell) |  |
| BLIND_1 | out of scope (blind) |  |
| BLIND_2 | out of scope (blind) |  |
| BLIND_3 | out of scope (blind) |  |

**Semantic-only trap recalled — run the leakage protocol before celebrating:** the scan above covers the denylist only; open the logged requests in cache/llm_log/ and audit what the model saw.
