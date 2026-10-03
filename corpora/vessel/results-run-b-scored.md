# Run B — scored against the answer key

Written **after** `results-run-b.md` was committed blind (commit `41cc76e`),
and only then: the owner authorised opening
`answer-key/TRAPS_AND_ANSWER_KEY.md` on 2026-10-03. From this point the vessel
landscape is no longer blind to whoever reads this file or wrote it. Nothing in
the blind results was changed afterwards.

## How this was scored, and how far to trust it

The key lists 27 seeded traps. Each is scored against what the main run (B1)
left in its store — claims, check results, question cards:

- **surfaced** — something in the store names this specific trap;
- **partly** — a neighbouring fact is there, the trap itself is not;
- **missed** — nothing.

Three limits, stated before the numbers:

1. **"Surfaced" is not "resolved".** The key's expected behaviours are things
   like *reassign only with the note, or ask*. The run asked one question, got
   `blocked`, and computed nothing. Every document claim below is still
   `proposed`. This table says the tool *noticed*; it does not say the tool
   would have got the number right.
2. **Only the cost question was run end to end.** About a third of the traps
   belong to the sales and revenue-per-ship questions, which the guide has no
   answer type for. They are scored on whether anything surfaced anyway.
3. **Scored by the same hand that ran it**, with the key open. A second reader
   would move a few rows between "surfaced" and "partly".

## The traps

| | trap | outcome | where it surfaced |
|---|---|---|---|
| VT01 | five spellings identify one build | surfaced | alias claims from data and from the acceptance certificate; `alias_set` question |
| VT02 | Gdansk = Danzig; `GD-YARD` is not an entity | surfaced | data claim, and the memo quoted: "not a separate legal entity" |
| VT03 | invoice date vs revenue-recognition date | partly | "recognition basis is customer acceptance; unclear whether POC qualifies" — the date split is not named |
| VT04 | Elbe Runner progress billings vs internal POC revenue | surfaced | the disputed 68% cost-to-cost, quoted and flagged as disputed |
| VT05 | Hansa Tug deposit and positive-number credit note | partly | the deposit booked as order intake is quoted; the credit note's sign is not |
| VT06 | receipts and invoice totals contain VAT | partly | `gross = net + VAT` is test-supported; "sales are net" is never said |
| VT07 | one Polish invoice at an obsolete 22% | partly | the right hypothesis (rate follows the entity's country) was proposed and **never tested** |
| VT08 | intercompany sales inside the sales export | surfaced | IC customers mapped to group entities; elimination quoted from the memo |
| VT09 | one IC receiving entry missing; Q2 differs by EUR 1,400 | surfaced | quoted exactly, and the sender/receiver reconciliation fails in 2 groups |
| VT10 | steel invoice duplicated, EUR 195,652 | surfaced | failed uniqueness check on `invoice_number` — `STA-2024-6710`, twice — plus procurement's note |
| VT11 | engine instalment coded to the wrong vessel | surfaced | quoted with amount and serial |
| VT12 | class cost with a blank project | surfaced | quoted with amount and PO — **and hidden by the data check**, whose anti-join skipped the blank row and passed |
| VT13 | PLN multiplied instead of divided | surfaced | failed reconciliation, one row: `CST-00068` |
| VT14 | approved December labour missing from the ledger | surfaced | quoted with amount |
| VT15 | one timesheet duplicated, EUR 31,091 | **missed** | `TS-00002` and `TS-00047` are identical apart from the id; no claim, no check |
| VT16 | overhead pools use different bases | surfaced | proposed as an open definition; the rule stays an open dependency |
| VT17 | CO-17 cost incurred but unsigned | surfaced | quoted with amount |
| VT18 | board figures rounded and inconsistent | surfaced | seven question cards refuse the board's figures as unsupported or self-contradicting |
| VT19 | cash is not sales | **missed** | three receipts applied to missing documents were found; the concept was not |
| VT20 | EUR 200k post-delivery upgrade revenue | **missed** | |
| VT21 | customer and vessel names drift | surfaced | alias claims |
| VT22 | a draft invoice duplicates a posted number | surfaced | failed uniqueness on `document_id` (`PL/2025/00813`, posted and draft), and separately "only posted invoices count" — the two were not connected |
| VT23 | tax appendix says 22%, memo says 23% | **missed** | |
| VT24 | never answer "cost" without naming which one | partly | the tool named one (`completed actual`) and marked it unconfirmed; it did not ask which was meant |
| VT25 | operations notes are weak provenance | surfaced | structural: every document claim stays `proposed` |
| VT26 | zero-rated invoices lack an evidence pack | **missed** | |
| VT27 | vessel name absent on some revenue rows | **missed** | |

**16 surfaced, 5 partly, 6 missed.**

## What the key adds to the blind results

**The documents did most of it.** Of the 16, nine rest wholly or mainly on a
quoted passage. Four rest on a deterministic check finding the error in the
data with nobody telling it where to look: the duplicated steel invoice, the
FX direction error, the draft-and-posted invoice number, the intercompany
mismatch. Those four are the strongest evidence in this run that the approach
works on data it did not grow up on.

**The miss that matters is VT15.** A duplicated timesheet is exactly the class
the tool found twice elsewhere (VT10, VT22), and it was missed for a plain
reason: nobody proposed that a timesheet row is unique by employee, project,
month and amount, so no check ran. What the tool finds in data is bounded by
what the model thinks to propose.

**VT12 is the cautionary one.** The tool both found it (in a document) and
certified its absence (in the data): *"the cost ledger project_id references
the vessel master"* is test-supported, with one blank row skipped. Two parts of
the same run disagree and nothing connects them.

**VT07 is the cheap one.** The right hypothesis was on the table and no check
was bound to it. One more passing binding would have caught a seeded trap.

**The right answer was never at risk — and never in reach.** The key's cost
figures need the duplicate removed, the blank project linked, the instalment
reassigned, the FX row corrected and the labour batch added. The run surfaced
all five. It connected none of them to the dependency list (one link from 28
document claims), so a person working from the readiness map would not be led
to them.
