# What is the cost of building a vessel?

## 1. The answer

There is no single figure: the company built four different vessels of different types and sizes. The production cost per vessel, after correcting five errors in the cost ledger, is:

| Vessel (project) | Type | Yard | Status | Production cost (EUR) | Contract price (EUR) | Cost as % of price |
|---|---|---|---|---|---|---|
| M/V Nordlicht (VSL-2407) | coastal research vessel | Hamburg | delivered 28 Mar 2025 | **2,718,400** | 3,400,000 | 80.0% |
| Baltic Surveyor (VSL-2411) | offshore survey vessel | Gdansk | delivered 19 Sep 2025 | **3,376,900** | 4,000,000 | 84.4% |
| Amber Pilot (VSL-2504) | harbour pilot boat | Gdansk | delivered 12 Dec 2025 | **1,214,600** | 1,480,000 | 82.1% |
| Elbe Runner (VSL-2502) | hybrid crew-transfer vessel | Gdansk | not finished | **1,558,457 so far**; 2,204,000 forecast at completion | 2,350,000 | 93.8% (forecast) |

- **The three finished vessels cost EUR 7,309,900 together, an average of about EUR 2.44m each.** The range is EUR 1.21m to EUR 3.38m, so the average is of limited use; cost runs at roughly 80-84% of the contract price.
- Baltic Surveyor's figure includes EUR 90,000 for cabin upgrades (CO-17) that were fitted but that the customer never signed for. Without it the cost is EUR 3,286,900 (82.2% of price).
- Elbe Runner's cost so far is probably EUR 1,563,200 rather than 1,558,457: a ledger row appears to be missing (see section 4).
- Hansa Tug (VSL-2506) was never built. The letter of intent was cancelled; EUR 84,500 of design and bid cost was spent on it.

"Production cost" here means materials and bought-in equipment, direct labour, yard overhead as booked, design, classification and logistics. It is net of VAT, in EUR, at group level, and excludes head-office administration and intercompany markups.

### Cost breakdown (EUR, corrected)

| Category | Nordlicht | Baltic Surveyor | Amber Pilot | Elbe Runner (to date) |
|---|---|---|---|---|
| Steel and hull | 650,000 | 700,000 | 240,000 | 480,000 |
| Engine package | 520,000 | 650,000 | 270,000 | 400,000 |
| Propulsion | 180,000 | 210,000 | 85,000 | 70,000 |
| Navigation | 165,000 | 190,000 | 72,000 | 35,000 |
| Electrical | 205,000 | 245,000 | 95,000 | 90,000 |
| Outfitting | 280,000 | 510,000 | 140,000 | 130,000 |
| Outfitting, unsigned CO-17 | - | 90,000 | - | - |
| Direct labour | 360,000 | 380,000 | 145,000 | 185,257 |
| Yard overhead | 210,000 | 220,000 | 90,000 | 95,000 |
| Design | 88,000 | 105,000 | 40,000 | 55,000 |
| Classification | 42,000 | 48,000 | 25,000 | 18,000 |
| Logistics | 18,400 | 28,900 | 12,600 | 200 |
| **Total** | **2,718,400** | **3,376,900** | **1,214,600** | **1,558,457** |

### If a wider definition of cost is wanted

| Vessel | Production cost | Plus HQ administration at 7.02% of contract revenue | "Full" cost |
|---|---|---|---|
| Nordlicht | 2,718,400 | 238,680 | 2,957,080 |
| Baltic Surveyor | 3,376,900 | 280,800 | 3,657,700 |
| Amber Pilot | 1,214,600 | 103,896 | 1,318,496 |

The overhead workbook says administration is "not normally inventoried", so I treat this as an optional view, not the main answer.

## 2. How I got each number

Starting point is the `reported_eur` column of the cost ledger (file 02), summed per project. The ledger's own pivot does this without checks and gives wrong totals. Corrections:

| Vessel | Raw ledger total | Correction | Corrected |
|---|---|---|---|
| Nordlicht | 2,703,102 | + 15,298 class invoice CST-00030 with blank project field; yard notes (file 10) confirm it belongs to NB-407 | 2,718,400 |
| Baltic Surveyor | 3,572,552 | - 195,652 duplicate steel invoice CST-00138 (same invoice and PO number as CST-00034, entered by manual journal; procurement confirms it is a scan copy) | 3,376,900 |
| Amber Pilot | 1,019,152 | + 195,448 engine instalment CST-00105, booked to Elbe Runner by mistake (yard job AMBER-77, engine serial matches Amber's acceptance certificate) | 1,214,600 |
| Elbe Runner | 2,299,409 | - 195,448 Amber engine; - 555,296 currency error on CST-00068 (PLN 135,201.77 at 4.3377 is EUR 31,169, not the 586,464.72 reported - the amount was multiplied instead of divided); + 9,792 December labour batch that is approved in the time workbook but never reached the ledger | 1,558,457 |

Checks that support the corrected figures:

- Nordlicht and Amber Pilot now equal the `latest_forecast_cost` in the vessel master exactly (2,718,400 and 1,214,600). Baltic Surveyor equals the master figure (3,286,900) plus the 90,000 CO-17 cost.
- After correction, every cost category comes to a round figure, which the raw totals did not.
- Approved timesheet cost per vessel (file 03, excluding one copied entry) equals the ledger's direct labour exactly: 360,000 / 380,000 / 145,000. So timesheets and ledger labour are the same cost and I did not add them together.
- Elbe Runner forecast at completion (2,204,000) is taken from the vessel master, not calculated by me.
- HQ administration: 920,000 pool / 13,100,000 revenue = 7.02%, applied to each contract price.

## 3. Assumptions

1. "Cost of building" means production cost at group level, not the selling price and not full cost including administration.
2. The ledger covers the whole build, not just 2025. It is named "2025" but holds postings from 2024 as well; I included all of them.
3. The unsigned CO-17 work (EUR 90,000) is a real cost of Baltic Surveyor because the cabins were fitted, even though no revenue can be booked for it.
4. Intercompany recharges (file 05) are not added. They move cost between the Hamburg and Gdansk companies and carry a 5-7.5% markup that is not a group cost. I assume the underlying work is already in the ledger, because the corrected ledger ties to the vessel master without them.
5. Yard overhead is taken as booked in the ledger, not recalculated from the overhead pool rates.
6. The ledger's own exchange rate per row is used for PLN amounts; apart from CST-00068 every row converts correctly.
7. The yard notes and emails in file 10 are unapproved statements. I relied on them only where the ledger itself shows the same thing (matching invoice number, yard job reference, amount).

## 4. Problems found in the data

- **Unassigned cost:** CST-00030 (15,298) has no project ID.
- **Duplicate invoice:** CST-00138 (195,652) on Baltic Surveyor; procurement asked for a reversal that is not in the export.
- **Wrong project:** CST-00105 (195,448) Amber Pilot engine booked to Elbe Runner.
- **Currency error:** CST-00068 overstated by 555,296.
- **Missing labour:** December Gdansk batch (9,792) not in the ledger.
- **Missing ledger row:** transaction CST-00092 does not exist; the numbering jumps from 00091 to 00093, between Elbe Runner's labour and overhead rows. Elbe Runner timesheets total 190,000 against 185,257 of labour (ledger plus December batch), a gap of 4,743. A missing labour row of that amount would explain both.
- **Duplicate timesheet:** TS-00047 is a copy of TS-00002 (31,091, Nordlicht), marked "approved-copy". Excluded.
- **Unapproved cost:** CST-00139 (CO-17, 90,000) is flagged not approved.
- **Board report figures do not match the ledger:** Nordlicht 2.70m (before the class invoice), Baltic Surveyor 3.05m (excludes CO-17, and the controller notes the duplicate may have been deducted twice), Amber Pilot 1.19m, Elbe Runner 1.80m (described as a "forecast-to-date blend"). I did not use them.
- **Posting dates do not fit the build timeline:** EUR 1.73m of Nordlicht cost and EUR 0.67m of Baltic Surveyor cost is dated after customer acceptance, including steel. Dates therefore cannot be used to split cost by year or stage.
- **Timesheet rates and locations disagree with the employee rate table** on almost every line (for example EMP-067 charged at 62 against a table rate of 42.5).
- **Overhead basis is inconsistent:** Gdansk overhead is defined per machine hour, but the board report uses labour hours, and no machine hours per vessel are provided.
- **Intercompany records are incomplete:** one recharge has no receiving booking (300,000, Amber Pilot), one pair differs by 1,400, and Q2 used a 7.5% markup instead of the 5% policy.
- The pivot sheet and one total in the sales workbook hold formulas without stored values; I recalculated them.

## 5. What I am unsure about

- **Intercompany recharges are the largest open question.** If their cost base is not already in the ledger, costs would be higher by: Nordlicht +347,619 (yard labour), Baltic Surveyor +300,000 and Elbe Runner +260,465 (engineering and procurement), Amber Pilot +285,714 (launch support). I think this is unlikely, because the ledger ties to the vessel master without them, but the files do not prove it either way.
- **Yard overhead may be understated.** The ledger charges 210,000 to Nordlicht; the stated Hamburg rate (EUR 39.35 per labour hour x 6,177 hours) gives 243,071. For Gdansk, using labour hours as the board does (EUR 45.63) gives 320,828 for Baltic Surveyor against 220,000 booked, and 124,608 for Amber Pilot against 90,000. Only about a quarter to a third of each yard's overhead pool is charged to these vessels; the rest presumably sits with refit and repair work or is not absorbed. Using the pool rates would add roughly EUR 33,000-101,000 per vessel.
- **Nordlicht may include upgrade cost.** A EUR 200,000 post-delivery upgrade was sold in October 2025. Some late-2025 Nordlicht postings could belong to it, but the descriptions do not say and the dates are unreliable.
- **Elbe Runner's final cost is a forecast.** The 2,204,000 is management's figure; completion is estimated at 61%, 68% or 72% depending on who is asked, and my cost-to-date figure is already 70.7% of the forecast. A pending change order (CO-02, +0.12m price) may also bring extra cost.
- **Whether the missing row CST-00092 is a real cost** (4,743) or just a deleted entry.
- **Hours behind direct labour** rest on timesheet rates that do not match the rate table; if the table is right, labour cost would differ.
- All figures are unaudited. The source files themselves state that entities and figures are fictional.
