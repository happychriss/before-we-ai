# What is the cost of building a vessel?

## 1. The answer

There is no single figure: the yard builds one-off vessels of very different size. From the corrected project cost ledger, a completed vessel cost between EUR 1.21m and EUR 3.38m to build, which is about 80-84% of its contract price.

| Vessel (project) | Type | Status | Build cost (production cost, EUR) | Contract price (EUR) | Cost / price |
|---|---|---|---|---|---|
| M/V Nordlicht (VSL-2407) | coastal research vessel | accepted 28 Mar 2025 | **2,718,400** | 3,400,000 | 80.0% |
| Baltic Surveyor (VSL-2411) | offshore survey vessel | accepted 19 Sep 2025 | **3,376,900** (3,286,900 without the unsigned CO-17 cabin upgrade) | 4,000,000 | 84.4% (82.2%) |
| Amber Pilot (VSL-2504) | harbour pilot boat | accepted 12 Dec 2025 | **1,214,600** | 1,480,000 | 82.1% |
| Elbe Runner (VSL-2502) | hybrid crew-transfer vessel | in progress | **1,558,457 to date**; 2,204,000 forecast at completion | 2,350,000 | 93.8% on forecast |
| Hansa Tug (VSL-2506) | tug concept, cancelled | never built | 84,500 of design and bid cost | none | n/a |

- **Simple average of the three delivered vessels: EUR 2,436,633** (total 7,309,900). Excluding CO-17 it is 2,406,633. The average hides a range of nearly 3x, so I would quote the per-vessel figures.
- These are **production costs**: materials and equipment, direct labour, yard overhead as booked, design, classification and logistics. Headquarters administration is not included.

Cost structure of the three delivered vessels (EUR):

| Category | Nordlicht | Baltic Surveyor | Amber Pilot |
|---|---|---|---|
| Steel and hull | 650,000 | 700,000 | 240,000 |
| Engine package | 520,000 | 650,000 | 270,000 |
| Propulsion | 180,000 | 210,000 | 85,000 |
| Navigation | 165,000 | 190,000 | 72,000 |
| Electrical | 205,000 | 245,000 | 95,000 |
| Outfitting | 280,000 | 600,000 (incl. 90,000 CO-17) | 140,000 |
| Direct labour | 360,000 | 380,000 | 145,000 |
| Yard overhead | 210,000 | 220,000 | 90,000 |
| Design | 88,000 | 105,000 | 40,000 |
| Classification | 42,000 | 48,000 | 25,000 |
| Logistics | 18,400 | 28,900 | 12,600 |
| **Total** | **2,718,400** | **3,376,900** | **1,214,600** |

Bought-in material and equipment is roughly 74-78% of the cost, direct labour 11-13%, and yard overhead 6.5-7.7%.

Two sensitivities change the picture and are not in the figures above:

| Sensitivity (EUR) | Nordlicht | Baltic Surveyor | Amber Pilot |
|---|---|---|---|
| Yard overhead at the 2025 pool rate on labour hours instead of the booked amount | +33,075 | +100,824 | +34,615 |
| HQ administration at 7.02% of contract revenue (full cost, not production cost) | +238,680 | +280,800 | +103,896 |

## 2. How I got each number

Source: `02_project_cost_ledger_2025.xlsx`, sheet `Cost_Ledger`, column `reported_eur`, summed by project. The ledger is life-to-date (it has 2024 and 2025 postings). I made five corrections, each backed by another file:

| Project | Raw ledger sum | Correction | Corrected |
|---|---|---|---|
| VSL-2407 Nordlicht | 2,703,102 | + 15,298 class invoice CST-00030 with a blank project field (ops notes: belongs to NB-407) | 2,718,400 |
| VSL-2411 Baltic Surveyor | 3,572,552 | - 195,652 duplicate steel invoice CST-00138 (same invoice and PO number as CST-00034; procurement confirms a scan copy) | 3,376,900 |
| VSL-2504 Amber Pilot | 1,019,152 | + 195,448 engine instalment CST-00105, coded to Elbe Runner but described as AMBER-77 / serial HD-88421 (project controls email, acceptance certificate) | 1,214,600 |
| VSL-2502 Elbe Runner | 2,299,409 | - 195,448 (the Amber engine); - 555,296 currency error on CST-00068 (PLN 135,201.77 was multiplied by 4.3377 instead of divided: 586,465 reported, 31,169 correct); + 9,792 December labour batch missing from the ledger | 1,558,457 |
| VSL-2506 Hansa Tug | 84,500 | none | 84,500 |

- The corrected Nordlicht and Amber Pilot totals equal the `latest_forecast_cost` in the vessel master exactly, and Baltic Surveyor equals it plus the 90,000 CO-17 line. That independent match is why I trust the corrections.
- Elbe Runner forecast at completion (2,204,000) is taken from the vessel master; I could not rebuild it.
- Overhead sensitivity: approved timesheet hours per project (6,177 / 7,031 / 2,731) times the pool rates in `03_time_and_overhead_allocations.xlsx` (Hamburg 39.35, Gdansk 45.63), less overhead already booked.
- Administration sensitivity: the 0.0702 rate in the same sheet times contract value.

## 3. Assumptions

- **"Cost of building" means production cost per vessel project**, at group level, excluding administration, selling cost and tax. The overhead-pool sheet itself says administration is "not normally inventoried".
- **CO-17 (90,000) is included** in Baltic Surveyor. The cabins were fitted (acceptance certificate), so the cost was incurred even though the customer never signed the price change and the ledger line is marked not approved.
- **Timesheet cost is not added on top of the ledger.** The approved timesheet totals per project equal the ledger's direct labour exactly (360,000 / 380,000 / 145,000), so they are the same cost. I excluded the "approved-copy" duplicate TS-00047 (31,091).
- **Intercompany recharges are not added.** I assumed the project ledger already holds the underlying cost and the recharges eliminate at group level.
- Ledger amounts are net of VAT, and the ledger's own EUR translation is accepted apart from the one obvious error.
- Hansa Tug is not a vessel build and is left out of any average.

## 4. Problems found in the data

- The ledger's own summary (`Pivot_Export`) trusts project codes and EUR amounts unchecked. Used as is, it overstates Elbe Runner by about 751,000, understates Amber Pilot by 195,448, and overstates Baltic Surveyor by 195,652.
- The duplicate steel invoice was still not reversed in the December export.
- Transaction CST-00092 is missing from the ledger sequence (it falls among the Elbe Runner labour lines).
- Elbe Runner labour does not reconcile: timesheets excluding the December batch total 180,208, the ledger shows 175,465. The 4,743 gap is unexplained and may be the missing CST-00092.
- The board report's costs (2.70 / 3.05 / 1.19 / 1.80 EURm) do not match the ledger: Nordlicht omits the late class invoice, Baltic Surveyor omits CO-17 and appears to deduct the duplicate twice, and Elbe Runner is described as a "forecast-to-date blend".
- Posting dates look unreliable. About 1.73m of Nordlicht cost and 0.67m of Baltic Surveyor cost is dated after customer acceptance, including engine packages. Timesheets are all dated 2025 while the matching ledger labour lines are partly dated 2024.
- Overhead is inconsistent: the Gdansk pool is defined on machine hours, the board report uses labour hours, and the amounts booked to projects match neither rate. Whether the Hamburg pool includes HQ occupancy is disputed.
- The ledger's PLN rates (about 4.21-4.42) differ from the treasury monthly rates (4.19-4.41 for 2025), and the treasury August rate is inverted (0.2299).
- Intercompany: Q2 engineering was charged at 7.5% instead of the 5% policy, one receiving-side booking is missing, and the elimination journal is incomplete.
- Project identifiers are inconsistent across files (project ID, yard job, contract reference, "Danzig-11"); the alias table is hidden and not fully approved.

## 5. What I am unsure about

- **Intercompany recharges are the largest open question.** Cost bases of 347,619 (Nordlicht), 300,000 (Baltic Surveyor), 285,714 (Amber Pilot) and 260,465 (Elbe Runner) were charged between the two entities. I cannot see them as identifiable lines in the project ledger. If they represent work that is not already in the ledger, each vessel's cost would be higher by roughly those amounts (10-24%). The exact match to the vessel master's forecast cost suggests they are not additional, but the files do not prove it.
- Whether some Nordlicht cost dated after acceptance belongs to the EUR 200,000 post-delivery science-module upgrade rather than the original build. If so, the build cost is lower than 2,718,400.
- Whether the booked yard overhead is right; the sensitivity in section 1 shows a possible +33,000 to +101,000 per vessel.
- Elbe Runner: cost to date may be 1,563,200 rather than 1,558,457 if the 4,743 labour gap is real. The 2,204,000 forecast is unverified, completion is estimated at 61%, 68% or 72% depending on who is asked, and the pending change order CO-02 (+0.12m price) has no cost estimate.
- Whether Baltic Surveyor's cost should be quoted with or without CO-17 depends on purpose: 3,376,900 is what it cost; 3,286,900 is the cost of the contracted scope.
- Retranslating PLN items at treasury rates would move the Gdansk vessels' cost slightly; I have not quantified it, and the treasury table only covers 2025.
- Three delivered vessels of three different types is too small a base to predict the cost of a future vessel.
