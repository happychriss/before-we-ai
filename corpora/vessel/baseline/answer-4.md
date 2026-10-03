# What is the cost of building a vessel? (HVW Group, data as of 31 Dec 2025)

## 1. The answer

There is no single "cost of a vessel": the group built four different vessel types, each with its own cost. The corrected group-level production cost (direct materials and subcontracts, direct labour, allocated yard overhead, design, classification, logistics; net of VAT; no HQ administration; no intercompany markup) is:

| Vessel (project) | Type / yard | Status | Corrected build cost (EUR) | Uncorrected ledger pivot (EUR) | Contract price (EUR) | Margin on contract |
|---|---|---|---|---|---|---|
| M/V Nordlicht (VSL-2407) | coastal research vessel, Hamburg | delivered 28 Mar 2025 | **2,718,400** | 2,703,102 | 3,400,000 | 681,600 (20.0%) |
| Baltic Surveyor (VSL-2411) | offshore survey vessel, Gdansk | delivered 19 Sep 2025 | **3,376,900** (3,286,900 contract scope + 90,000 unsigned CO-17 cabins) | 3,572,552 | 4,000,000 | 623,100 (15.6%) |
| Amber Pilot (VSL-2504) | harbour pilot boat, Gdansk | delivered 12 Dec 2025 | **1,214,600** | 1,019,152 | 1,480,000 | 265,400 (17.9%) |
| Elbe Runner (VSL-2502) | hybrid crew-transfer vessel, Gdansk | in progress, not accepted | **1,558,457 incurred to date**; forecast at completion **2,204,000** (company forecast, not verifiable) | 2,299,409 | 2,350,000 (+120,000 CO pending) | not yet known |
| Hansa Tug (VSL-2506) | tug concept, Hamburg | LOI cancelled, never built | 84,500 design and bid cost (not a build cost) | 84,500 | none | n/a |

- **Three completed vessels: 7,309,900 in total, i.e. 2,436,633 per vessel on average.** The range is 1.21m to 3.38m, so the average is of limited use; quote the cost per vessel type.
- Roughly 79-83% of contract price goes into production cost on the delivered vessels.

Cost structure of the delivered vessels (EUR, corrected):

| Category | Nordlicht | Baltic Surveyor | Amber Pilot |
|---|---|---|---|
| Steel and hull | 650,000 | 700,000 | 240,000 |
| Engine package | 520,000 | 650,000 | 270,000 |
| Propulsion | 180,000 | 210,000 | 85,000 |
| Navigation | 165,000 | 190,000 | 72,000 |
| Electrical | 205,000 | 245,000 | 95,000 |
| Outfitting | 280,000 | 600,000 (incl. 90,000 CO-17) | 140,000 |
| Direct labour | 360,000 | 380,000 | 145,000 |
| Yard overhead (as allocated in ledger) | 210,000 | 220,000 | 90,000 |
| Design | 88,000 | 105,000 | 40,000 |
| Classification | 42,000 | 48,000 | 25,000 |
| Logistics | 18,400 | 28,900 | 12,600 |
| **Total** | **2,718,400** | **3,376,900** | **1,214,600** |

Elbe Runner to date: steel 480,000; engine 400,000; propulsion 70,000; navigation 35,000; electrical 90,000; outfitting 130,000; direct labour 185,257 (175,465 in ledger + 9,792 December batch); yard overhead 95,000; design 55,000; classification 18,000; logistics 200.

If "full cost" including HQ administration is wanted (the pool rate is 7.02% of revenue; normally not part of production cost), add approximately: Nordlicht 238,680, Baltic Surveyor 280,800, Amber Pilot 103,896.

## 2. How I got each number

Source: `02_project_cost_ledger_2025.xlsx`, sheet Cost_Ledger (138 rows), column `reported_eur`, summed per project, with these corrections. The Pivot_Export sheet holds only formulas without stored values and, by its own note, applies no quality checks; the "uncorrected" column above is my recalculation of what it would show.

| Correction | Effect | Evidence |
|---|---|---|
| CST-00030 class invoice 15,298 has a blank project; assigned to Nordlicht | Nordlicht +15,298 | Row text "for NB-407"; yard job HH-407; ops note in file 10; board report "before late class invoice" |
| CST-00138 (195,652) is a manual-journal copy of CST-00034, same invoice STA-2024-6710 and PO; removed | Surveyor -195,652 | Procurement email in file 10; board report risks; no reversal in ledger |
| CST-00139 (90,000) CO-17 luxury cabins, `approved = False`; kept as cost | Surveyor includes 90,000 | Acceptance certificate AC-B11 says cabins were fitted; customer did not sign, so cost without revenue |
| CST-00105 engine instalment 195,448 booked on VSL-2502 but yard ref AMBER-77, serial HD-88421; moved to Amber Pilot | Amber +195,448; Elbe -195,448 | Project controls email in file 10; acceptance certificate AC-AP77 names the same engine serial |
| CST-00068: PLN 135,201.77 at 4.3377 PLN/EUR was multiplied instead of divided (reported 586,464.72); corrected to 31,169 | Elbe -555,296 | Arithmetic; row text "ERP conversion batch FX-UPLOAD-08"; after the fix Elbe steel totals exactly 480,000 |
| December Gdansk labour batch TS-00026 (9,792) approved but not in the ledger; added | Elbe +9,792 | File 03 comment; close note in file 10 |

Cross-checks:
- Corrected Nordlicht (2,718,400) and Amber Pilot (1,214,600) equal `latest_forecast_cost` in the vessel master exactly. Baltic Surveyor without CO-17 (3,286,900) also equals it exactly. This is strong confirmation of the corrections.
- Timesheet totals in file 03 (after removing duplicate TS-00047, an "approved-copy" of TS-00002, 31,091) equal the ledger direct-labour totals exactly for Nordlicht (360,000), Surveyor (380,000) and Amber (145,000). So I treated timesheets as the detail behind ledger labour, not as extra cost.
- Elbe Runner forecast at completion 2,204,000 is taken straight from the vessel master; I could not rebuild it.
- Margins: contract value (file 01, confirmed by file 09) minus corrected cost. Nordlicht excludes the 200,000 post-delivery upgrade revenue.
- Average: (2,718,400 + 3,376,900 + 1,214,600) / 3.

## 3. Assumptions

1. "Cost" means group-level production cost per vessel, net of VAT, cumulative over the whole build (2024 and 2025 postings), not just FY2025 spend.
2. Ledger yard-overhead allocations are accepted as booked. HQ administration (920,000 pool) is excluded.
3. Unsigned CO-17 is a real cost of Baltic Surveyor because the work was done.
4. Intercompany recharges (file 05) are not added. The ledger appears to hold underlying group cost, since the corrected totals match the master forecasts exactly. Intercompany markups (5% / 7.5%) are internal profit, never group cost.
5. Timesheet cost is already inside ledger "direct labour" (except the December batch).
6. Ledger per-transaction PLN/EUR rates are kept. Retranslating 2025 PLN rows at the monthly treasury rates (August inverted rate fixed) changes results only slightly: Surveyor +6,694, Amber +4,688, Elbe -1,842.
7. Hansa Tug is not a vessel build; its 84,500 is sunk design/bid cost.

## 4. Problems found in the data

- Ledger: one duplicate invoice, one mis-coded project, one blank project, one FX error (multiply instead of divide), one unapproved cost row, one missing labour batch. Transaction ID CST-00092 is missing from the sequence (it falls between Elbe Runner labour and overhead rows).
- Elbe Runner timesheets total 190,000 but ledger labour plus the December batch is only 185,257; 4,743 is unexplained (possibly the missing CST-00092). If timesheets are right, cost to date is 1,563,200.
- Board report costs are wrong or rounded: Nordlicht 2.70m (misses class invoice), Baltic Surveyor 3.05m (understated by about 0.33m versus 3.38m), Amber 1.19m, Elbe Runner 1.80m ("forecast-to-date blend", not an actual). The controller's own note says to recalculate from source.
- Posting dates do not fit the build timeline: 1.73m of Nordlicht cost (64%), including steel, is posted after its acceptance on 28 Mar 2025; 0.67m of Baltic Surveyor cost is posted after its acceptance.
- Overhead: Hamburg pool rate 39.35 EUR per labour hour times 6,177 Nordlicht timesheet hours gives about 243,000 versus 210,000 booked. Gdansk allocates on machine hours (45.63) while the board report uses labour hours; no machine hours per project are given. Comments say HQ occupancy may be in the Hamburg pool and that one project includes administration overhead (which one is not stated).
- Intercompany: Q2 engineering recharge used 7.5% instead of the 5% policy; one receiving booking is missing; eliminations are incomplete.
- Employee_Rates do not match the rates or locations used in the timesheets (e.g. EMP-067 listed at 55 in Gdansk, used at 62 in Hamburg and 48 in Gdansk).
- VAT codes DE19/PL23 are attached to internal payroll and overhead allocations, which carry no VAT; the VAT column is not reliable.
- Timesheets for the cancelled Hansa Tug include hull, outfitting and commissioning hours, also after cancellation on 30 May 2025.
- Project_Aliases sheet is hidden and unapproved; "Danzig-11" is an unconfirmed alias for Baltic Surveyor.

## 5. What I am unsure about

- **Intercompany cost bases** (Nordlicht 347,619 yard labour; Surveyor 300,000 and Elbe Runner 260,465 engineering/procurement; Amber 285,714 launch support). I assumed they are already in the ledger. If they are not, each vessel's cost rises by that amount. This is the largest open question and needs confirmation from the controller.
- Whether Nordlicht's 2,718,400 contains cost of the 200,000 post-delivery science-module upgrade, given the many postings after acceptance. If so, the pure build cost is lower.
- Whether the yard overhead booked is fair; a different allocation base could shift tens of thousands of EUR per vessel (possibly around 100,000 on Baltic Surveyor).
- Elbe Runner: the 2,204,000 forecast is unverified; completion is quoted as 61%, 68% or 72% depending on the source. My cost to date is 71% of the forecast.
- Whether the Hansa Tug timesheets (62,000) are the same cost as the 62,000 ledger design rows (assumed yes) or additional.
- Whether the ledger is complete for the delivered vessels (late invoices, warranty or retention-related cost are not visible).
- Whether CO-17's 90,000 will be recovered from the customer; this affects margin, not cost.
