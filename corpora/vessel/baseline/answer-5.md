# What is the cost of building a vessel?

## 1. The answer

There is no single figure: the company built three very different vessels in the period, plus one still under construction. The cost of building a vessel was **between EUR 1.21m and EUR 3.38m**, depending on the vessel. All figures are production cost (materials, bought-in systems, direct labour, booked yard overhead, design, classification, logistics), in EUR, net of VAT, life-to-date (2024 and 2025 postings together), after correcting five errors I found in the cost ledger.

| Vessel (project) | Type | Yard | Status | **Build cost (corrected)** | Uncorrected ledger total | Contract price | Margin on contract |
|---|---|---|---|---|---|---|---|
| M/V Nordlicht (VSL-2407) | coastal research vessel | Hamburg | delivered 28 Mar 2025 | **2,718,400** | 2,703,102 | 3,400,000 | 681,600 (20.0%) |
| Baltic Surveyor (VSL-2411) | offshore survey vessel | Gdansk | delivered 19 Sep 2025 | **3,376,900** | 3,572,552 | 4,000,000 | 623,100 (15.6%) |
| Amber Pilot (VSL-2504) | harbour pilot boat | Gdansk | delivered 12 Dec 2025 | **1,214,600** | 1,019,152 | 1,480,000 | 265,400 (17.9%) |
| Elbe Runner (VSL-2502) | hybrid crew-transfer vessel | Gdansk | **not finished** | **1,558,457 to date**; 2,204,000 forecast at completion | 2,299,409 | 2,350,000 | not yet known |

- Average of the three completed vessels: **EUR 2,436,633** (total 7,309,900). I would not use this average for planning; the vessels are of different types and sizes. As a ratio, build cost was about **82% of contract price** (80.0%, 84.4%, 82.1%).
- Baltic Surveyor's figure includes EUR 90,000 for the CO-17 cabin upgrade, which was built but never agreed in writing by the customer. Without it the cost is 3,286,900.
- Hansa Tug (VSL-2506) was never built (letter of intent cancelled). EUR 84,500 of design and bid cost was spent on it; this is not a vessel build cost.

Cost by category (corrected, EUR):

| Category | Nordlicht | Baltic Surveyor | Amber Pilot | Elbe Runner (to date) |
|---|---|---|---|---|
| Steel and hull | 650,000 | 700,000 | 240,000 | 480,000 |
| Engine package | 520,000 | 650,000 | 270,000 | 400,000 |
| Propulsion | 180,000 | 210,000 | 85,000 | 70,000 |
| Navigation | 165,000 | 190,000 | 72,000 | 35,000 |
| Electrical | 205,000 | 245,000 | 95,000 | 90,000 |
| Outfitting | 280,000 | 600,000 (incl. 90,000 CO-17) | 140,000 | 130,000 |
| Direct labour | 360,000 | 380,000 | 145,000 | 185,257 |
| Yard overhead (as booked) | 210,000 | 220,000 | 90,000 | 95,000 |
| Design | 88,000 | 105,000 | 40,000 | 55,000 |
| Classification | 42,000 | 48,000 | 25,000 | 18,000 |
| Logistics | 18,400 | 28,900 | 12,600 | 200 |
| **Total** | **2,718,400** | **3,376,900** | **1,214,600** | **1,558,457** |

**If a broader definition of cost is wanted**, these are the additions (not included above):

| Possible addition | Nordlicht | Baltic Surveyor | Amber Pilot | Elbe Runner |
|---|---|---|---|---|
| HQ administration at 7.02% of revenue (not normally counted as build cost) | +238,680 | +280,800 | +103,896 | n/a (no revenue yet) |
| Intercompany services at cost, *only if* they are not already in the ledger (see section 5) | +347,619 | +300,000 | +285,714 | +260,465 |
| Overhead re-rated at the 2025 pool rate on labour hours, instead of the amount booked (rough) | +33,073 | +100,829 | +34,606 | +53,471 |

## 2. How I got each number

Source for all four: the `Cost_Ledger` sheet in `02_project_cost_ledger_2025.xlsx`, column `reported_eur`, summed by project, then corrected. The workbook's own `Pivot_Export` sheet has formulas with no stored values and, by its own note, applies no quality checks; the "uncorrected" column above is what those formulas would return.

**Nordlicht: 2,718,400**
- Ledger rows tagged VSL-2407: 2,703,102.
- Plus 15,298: classification invoice CST-00030 has a blank project field (yard job HH-407, text says NB-407). The operations notes (file 10) confirm it belongs to Nordlicht.
- Result equals `latest_forecast_cost` in the vessel master (2,718,400) exactly.

**Baltic Surveyor: 3,376,900**
- Ledger rows tagged VSL-2411: 3,572,552.
- Minus 195,652: CST-00138 (manual journal) repeats steel invoice STA-2024-6710 / PO-2024-43717 already posted as CST-00034. Procurement's email (file 10) confirms it is a scan copy, not a second delivery, and that no reversal was posted.
- Kept in: 90,000 for CST-00139 (CO-17 cabin upgrade, flagged "not approved"). The acceptance certificate says the cabins were fitted, so the cost was incurred even though no revenue can be charged.
- Result equals the vessel master forecast (3,286,900) plus the 90,000.

**Amber Pilot: 1,214,600**
- Ledger rows tagged VSL-2504: 1,019,152.
- Plus 195,448: engine instalment CST-00105 is tagged VSL-2502 (Elbe Runner) but carries yard job AMBER-77; the Project Controls email (file 10) and the engine serial on the acceptance certificate (file 9) confirm it is Amber Pilot's.
- Result equals the vessel master forecast (1,214,600) exactly.

**Elbe Runner: 1,558,457 to date**
- Ledger rows tagged VSL-2502: 2,299,408.72.
- Minus 195,448: the Amber Pilot engine instalment above.
- Minus 555,295.72: CST-00068 is PLN 135,201.77 at 4.3377 PLN/EUR, which is EUR 31,169, but 586,464.72 was reported (the amount was multiplied by the rate instead of divided).
- Plus 9,792: December Gdansk labour batch (TS-00026 in file 03), approved but never reached the ledger; confirmed by the close note in file 10.
- The 2,204,000 forecast at completion is taken directly from the vessel master; I could not rebuild it.

**Other figures**
- Contract prices: vessel master, cross-checked to the contract register (file 9) and to invoice totals in file 04.
- Hansa Tug 84,500: ledger rows for VSL-2506 (design 62,000, sales engineering 22,500).
- Administration: `Overhead_Pools` rate 0.0702 × contract price.
- Intercompany at cost: `cost_base_eur` in file 05 (markup excluded).
- Overhead re-rating: timesheet hours per project (6,177 / 7,031 / 2,731 / 3,254) × pool rate (Hamburg 39.35, Gdansk 45.63) minus overhead booked.

**Checks that passed**
- Timesheet cost per project (file 03) equals ledger direct labour for Nordlicht (360,000), Baltic Surveyor (380,000) and Amber Pilot (145,000). I therefore treated timesheets as the detail behind the ledger labour, not as extra cost.
- Every other PLN row converts correctly at its stated rate. Re-translating the 2025 PLN rows at the treasury monthly rates changes any vessel by less than EUR 7,000.

## 3. Assumptions

1. "Cost of building a vessel" means production cost per project: direct cost plus the yard overhead booked to the project. HQ administration is excluded (the overhead sheet says it is "not normally inventoried").
2. Cost is life-to-date. The ledger is titled 2025 but holds 2024 postings too; I included both, since a build spans years.
3. Group view: intercompany markups are not cost. I did not add intercompany recharges to the main figures.
4. The CO-17 cabin upgrade is a real cost of Baltic Surveyor even though unapproved and unbilled.
5. Timesheet cost is already inside ledger direct labour (the totals match on three vessels), so I did not add it again. The duplicate timesheet row TS-00047 (31,091, "approved-copy") is ignored.
6. Yard overhead is taken as booked, not re-rated.
7. Yard job numbers and contract references map to projects as in the hidden `Project_Aliases` sheet (marked work in progress but internally consistent). "Danzig" and "Gdansk" are the same yard.
8. VAT is excluded; all amounts are net.

## 4. Problems found in the data

- **Wrong currency conversion**: CST-00068 overstates Elbe Runner by 555,296.
- **Duplicate invoice**: CST-00138 overstates Baltic Surveyor by 195,652; not reversed.
- **Wrong project**: CST-00105 (195,448) sits on Elbe Runner, belongs to Amber Pilot.
- **Blank project**: CST-00030 (15,298) belongs to Nordlicht.
- **Missing labour**: December batch (9,792) absent from the ledger for Elbe Runner.
- **Missing ledger row**: transaction IDs run CST-00001 to CST-00139 with CST-00092 absent. It falls among Elbe Runner's direct-labour rows.
- **Elbe Runner labour gap**: timesheets show 190,000; the ledger shows 175,465. The December batch explains 9,792; **4,743 remains unexplained** (possibly the missing CST-00092).
- **Posting dates after delivery**: EUR 1.73m of Nordlicht's cost (including steel, 650,000) is dated after its 28 March 2025 acceptance, and its timesheets run to August 2025. About 667,000 of Baltic Surveyor's cost is also dated after acceptance. Either the dates are unreliable or some of this is not build cost.
- **Board report figures do not match the ledger**: the board shows 2.70m / 3.05m / 1.19m / 1.80m. Nordlicht's 2.70m omits the late class invoice. The controller's own note says the Baltic Surveyor figure omits CO-17 and may deduct the duplicate twice. I could not reproduce 3.05m or 1.19m exactly. The Elbe Runner 1.80m is described as a "forecast-to-date blend".
- **Overhead basis is inconsistent**: Gdansk pool is defined on machine hours, the board uses labour hours; no machine hours per project exist in the files. Hamburg's booked overhead (210,000) is below what the pool rate implies (243,073).
- **Intercompany records incomplete**: one recharge has no receiving-side booking, one pair differs by 1,400, Q2 used a 7.5% markup against a 5% policy.
- **FX table**: the August 2025 PLN rate is inverted (0.2299); ledger row rates differ from the treasury monthly rates (small effect).
- Not relevant to cost but present: a 22% Polish VAT rate on one invoice, a draft duplicate of invoice PL/2025/00813, an unrefunded Hansa Tug deposit.

## 5. What I am unsure about

- **Whether intercompany services are inside the ledger (largest uncertainty).** File 05 shows the two entities charging each other for work on these same projects: yard labour for Nordlicht (cost base 347,619), engineering and procurement for Baltic Surveyor (300,000) and Elbe Runner (260,465), launch support for Amber Pilot (285,714). No ledger row names the sister company as vendor, so I cannot tell whether this work is already in the ledger under other vendors or is missing from it. Because my corrected totals match the master forecast exactly for three vessels, I believe the ledger is treated as complete, but if these are additional, each vessel costs roughly 0.26m to 0.35m more.
- **Elbe Runner's final cost.** The vessel is unfinished. Completion is quoted as 68% (cost), 61% (engineering milestones) and 72% (foreman), with no agreed measure. My cost to date is 70.7% of the 2,204,000 forecast. A pending change order (CO-02, +0.12m price) may add cost. The 4,743 labour gap and the missing CST-00092 are open.
- **Whether Nordlicht's cost includes the later upgrade.** A EUR 200,000 science-module upgrade was invoiced after delivery, and much of Nordlicht's cost is dated after delivery. If upgrade cost is in the project, the pure build cost is lower than 2,718,400; the files do not separate it.
- **The true overhead per vessel.** The booked amounts are round figures that do not follow from either pool rate. A re-rating could add 33,000 to 101,000 per vessel.
- **Whether the master forecast is an independent check.** The exact match to my corrected totals is reassuring, but the forecast may simply have been derived from the same ledger.
- **Whether more errors exist that no document mentions.** I found one error by arithmetic alone (the conversion) and the others with help from notes in files 9 and 10; file 10 itself warns that its statements are unverified.
