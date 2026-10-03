# Seeded-Recall — method and current measurement

Seeded-Recall **reports, it never gates.** It measures how many of the
corpus's seeded traps the pipeline surfaces as claims, against a ground truth
the corpus generator computes for itself. Run it with
`python tests/eval/seeded_recall.py` (online) or `--offline` (a harness smoke
test over the recorded fixtures, not an evaluation).

**Two numbers matter more than recall.** *False-Promotion* must be **0** — it
is structural, and a non-zero value is a release blocker, not a regression.
The *leakage scan* must be CLEAN: it checks that no corpus-trap token reached
a prompt, because a recall figure earned by teaching to the test is worth
nothing.

**How to read the recall number.** Run-to-run variance is **±2–3 traps** on
the same code: the sampler is stochastic and flips traps in both directions.
Treat any single measurement as one sample. A numeric bar therefore has to
sit outside that band — it is an open owner decision (`meta/memory.md`).

**Where the misses are.** They cluster in the definition-style traps whose
rule lives only in a policy document (F15 revenue definition, F19 rate
policy, F23/F24/F26 anchors). Those are the document pipeline's job, not a
prompt-tuning problem; a bar over relationship-style traps only is worth
considering.

## What the number does not measure

Measured 2026-08-20 against `tests/eval/seeded_recall.py`, and pinned by
`src/tests/unit/test_seeded_recall_scorer.py` so the finding cannot quietly
disappear. Nothing below is a prediction; all of it is reproducible offline in
under a second.

**The scorer never reads what a claim asserts.** `matches()` is a lowercased
substring test over the claim's statement, its predicate params, and its
binding. Fabricate one claim per trap whose statement is plainly false —
*"Nothing whatsoever is true about de_erp__orders and de_erp__invoices."* — and
the scorer awards **25/25**. A claim and its exact negation score identically,
because the tokens are the same in both.

So the headline figure is *"how often did some claim mention the right
columns"*, not *"how often did the pipeline find the seeded relationship"*.
14/25 is still evidence — the claims it scored are real claims from a real run,
and False-Promotion 0 and the leakage scan are unaffected — but it is weaker
evidence than the number looks, and it is not the number a reader assumes.

**It is keyed to this corpus's vocabulary.** 21 of the 25 in-scope matchers
fire only on a token naming a table or column that exists here
(`de_erp__orders`, `fx_rates`, `crm_activities`). Of the remaining four, three
accept a generic word *or* one of this corpus's account numbers (4000, 4300,
4800, 90001); exactly one, F22, is domain-generic. Point the pipeline at
`corpora/vessel/` and the figure falls because the words changed, not because
the machine got worse. **A second landscape needs behaviour-class scoring
before its recall figure means anything** — that work is scoped, not started.

**The blind traps are in no automated measurement at all.** `BLIND_1/2/3` carry
an empty matcher and `scope="blind"`, so the report has always printed *"out of
scope"* for them. The three traps held back specifically to catch what the
implementer did not anticipate are scored by nobody.

**What a rewrite has to do**, when it happens: score the *verdict* rather than
the sentence; match on structured predicate and params resolved through the
source catalog rather than on substrings; ship a negative-control fixture that
must score **0**; and make the blind traps count.

**The lesson, which is bigger than this file.** The project's own rule — *test
a heuristic by mutation* — was applied to the checks, the domain laws and the
document pipeline, and never to the thing that produces the headline number.
A metric needs a negative control the same way a domain law needs a violated
fixture. Now a standing rule in `meta/conventions.md`.

**Watch at the next re-record.** The mapping batch has been answering
`template=null` for roughly 19 of 22 role bindings. Every such answer is
honest — nothing is promoted falsely — but a more hesitant binder means more
roles settle by clarification question than by check verdict, which shifts
work onto the human. Compare the ratio after the next live run.

---

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
