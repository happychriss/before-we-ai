# Seeded-Recall report

mode: online
leakage scan of every logged request: CLEAN
false promotions (must be 0): 0

claims: 50 hypotheses (+0 deduped, 2 skipped), 22 role candidates
check plans: 47 planned, 20 unbindable, 5 semantic-only, 0 unanswered
engine: 47 checks executed, 0 skipped
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


---

# Post-rename re-measurement (2026-07-31)

Run context: terminology realignment reworded every prompt (wire contract —
template names, JSON fields, claim labels — unchanged; see architecture.md
"Terminology"). This run doubles as the null test: same shape, reworded
prompts.

**Delta vs M4: 14/25 (−1 net).** Flips in both directions — lost F12, F13
(CRM customer references) and F18 (fx_rates coverage), all recall-gap class
(expressible, just not proposed this run); gained F14 (s_h_indicator
debit/credit semantic equivalent, an M4 miss) and F25 (document_reference →
invoices). No one-directional degradation ⇒ read as single-sample variance
of a stochastic sampler, not prompt fragility. Finding worth keeping: the
recall measurement has run-to-run noise of ±2–3 traps — the owner's numeric
bar should be set with that in mind. **False-Promotion stayed 0** (structural),
leakage scan CLEAN, semantic-only 1/1.

The fixture re-record (same day, separate live run) showed the same
conservatism shift: the mapping batch answered template=null for 19 of 22
role bindings (M4 recording: 15 of 23) — in that sample `intercompany` and
`amount_local` were never bound to their invariants and settle via
clarification questions instead of check verdicts (the journal election
still lands: GL test-supported, F27 decoy and US GL contradicted). Check
plans 42 vs 58. All honest paths — nothing promoted falsely — but the
reworded V2 prompt appears to make invariant binding more hesitant; watch
this at the M5 re-record. It also exposed and fixed a recorder bug:
`refresh_fixtures.py` recorded `attempts[-1]` even when that was an
item-scoped repair answer; it now records the last full-batch attempt.

# Seeded-Recall report

mode: online
leakage scan of every logged request: CLEAN
false promotions (must be 0): 0

claims: 55 hypotheses (+0 deduped, 2 skipped), 20 role candidates
checks: 53 bound, 16 unbindable, 6 semantic-only, 0 unanswered
engine: 53 checks executed, 0 skipped
role questions: 6
token usage: {'input_tokens': 302455, 'output_tokens': 26321}

## Recall: 14/25 in-scope traps (semantic-only: 1/1)

| trap | result | matched claim |
|---|---|---|
| F1 | HIT | de_erp__invoices.order_reference references de_erp__orders.order_id. |
| F2 | HIT | de_erp__invoices.order_reference references de_erp__orders.order_id. |
| F3 | miss |  |
| F4 | miss |  |
| F5 | HIT | de_erp__customers.legacy_id equals kunden_migration old_customer_id tr |
| F6 | HIT | de_erp__customer_hierarchy carries per-customer validity intervals via |
| F7 | miss |  |
| F8 | HIT | marketing_grouping.marketing_product_group is semantically equivalent  |
| F9 | HIT | de_erp__territory_plz maps postal-code ranges (plz_from..plz_to) to a  |
| F10 | HIT | de_erp__crm_activities.rep_id references de_erp__sales_reps.rep_id. |
| F11 | miss |  |
| F12 | miss |  |
| F13 | miss |  |
| F14 | HIT | buchungen_report.s_h_indicator (Soll/Haben) is semantically the debit/ |
| F15 | miss |  |
| F16 | HIT | de_erp__gl_postings.cost_center_id references de_erp__cost_centers.cos |
| F17 | miss |  |
| F18 | miss |  |
| F19 | miss |  |
| F20 | HIT | de_erp__ar_open_items.invoice_reference references de_erp__invoices.do |
| F21 | miss |  |
| F22 | HIT | DE and US intercompany postings are mirror images for the same period. |
| F23 | out of scope (m5_docs) |  |
| F24 | out of scope (m5_docs) |  |
| F25 | HIT | de_erp__gl_postings.document_reference references de_erp__invoices.doc |
| F26 | out of scope (m5_docs) |  |
| F27 | HIT | buchungen_report.betrag_eur is the EUR-denominated amount equivalent t |
| F28 | HIT | de_erp__invoices.amount_doc_currency reconciles to de_erp__orders.tota |
| F29 | out of scope (m6_tell) |  |
| BLIND_1 | out of scope (blind) |  |
| BLIND_2 | out of scope (blind) |  |
| BLIND_3 | out of scope (blind) |  |

**Semantic-only trap recalled — run the leakage protocol before celebrating:** the scan above covers the denylist only; open the logged requests in cache/llm_log/ and audit what the model saw.
