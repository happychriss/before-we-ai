# What is the cost of building a vessel?

Company: Hanseatic Vessel Works Group (HVW-DE, Hamburg) with its subsidiary Baltic Hull Works (BHW-PL, Gdansk yard). All figures in EUR, net of VAT, cumulative over the whole build (2024 and 2025 postings), as at 31 December 2025.

## 1. The answer

There is no single "cost of a vessel": the company built three very different vessels to completion, and each has its own cost. Corrected production cost (materials, bought-in systems, direct labour, yard overhead; no HQ administration):

| Vessel | Type / yard | Status | Corrected build cost | Contract price | Cost as % of price | Uncorrected ledger total |
|---|---|---|---|---|---|---|
| M/V Nordlicht (VSL-2407) | coastal research vessel, Hamburg | accepted 28 Mar 2025 | **2,718,400** | 3,400,000 | 80.0% | 2,703,102 |
| Baltic Surveyor (VSL-2411) | offshore survey vessel, Gdansk | accepted 19 Sep 2025 | **3,376,900** (3,286,900 without the unsigned CO-17 cabin upgrade) | 4,000,000 | 84.4% (82.2%) | 3,572,552 |
| Amber Pilot (VSL-2504) | harbour pilot boat, Gdansk | accepted 12 Dec 2025 | **1,214,600** | 1,480,000 | 82.1% | 1,019,152 |
| Elbe Runner (VSL-2502) | hybrid crew-transfer vessel, Gdansk | not finished | **1,558,458 to date**; forecast at completion 2,204,000 | 2,350,000 | 93.8% (forecast) | 2,299,410 |
| Hansa Tug (VSL-2506) | tug concept, Hamburg | never built (LOI cancelled) | 84,500 of design and bid cost, not a build cost | none | n/a | 84,500 |

Short version:

- A completed vessel cost between **1.2 million and 3.4 million**, depending on size and type. The three delivered vessels cost 7,309,900 in total, a simple average of about 2.44 million, but the average of three dissimilar ships is of little use.
- The more transferable figure: build cost was **80% to 84% of the contract price** on all three delivered vessels (gross margin 16% to 20%).
- The uncorrected ledger totals are wrong for four of the five projects, in one case by about 740,000. They should not be quoted.

Cost breakdown of the three delivered vessels after corrections:

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

Roughly: bought-in material and systems about 73% to 77%, direct labour 11% to 13%, yard overhead 6.5% to 8%, design, class and logistics 5% to 6%.

Resulting gross margin on the contract price: Nordlicht 681,600 (20.0%), Baltic Surveyor 623,100 (15.6%), Amber Pilot 265,400 (17.9%). The board draft shows 25.0%, 23.8% and 19.6%, which is too favourable for all three.

## 2. How I got each number

Source for all costs: `02_project_cost_ledger_2025.xlsx`, sheet `Cost_Ledger`, column `reported_eur`, 138 rows, summed by `project_id`. The `Pivot_Export` sheet in that file has formulas with no stored values, so I recomputed the sums myself. Then I applied the corrections below, each of which is supported by a second document.

**Nordlicht: 2,703,102 + 15,298 = 2,718,400**
- Row CST-00030 (classification, 15,298) has a blank project field but yard job HH-407 and the text "class attendance for NB-407; project field rejected by ERP". The yard notes (file 10) confirm it belongs to Nordlicht.
- The result equals `latest_forecast_cost` in the vessel master (2,718,400) exactly.
- The board draft shows 2.70m, "rounded before late class invoice".

**Baltic Surveyor: 3,572,552 - 195,652 = 3,376,900**
- Rows CST-00034 and CST-00138 are the same steel invoice (Stal-Marine STA-2024-6710, same PO, same amount 195,652); the second is a manual journal. Procurement's email (file 10) says it is a scan copy, not a second delivery, and that no reversal was posted. I removed one.
- Row CST-00139 (90,000, luxury cabin upgrade, CO-17) is marked not approved. I kept it in the cost because the acceptance certificate says the cabins were actually fitted. The customer did not sign the price change, so it is cost without revenue. Without it the cost is 3,286,900, which equals the vessel master forecast exactly.
- The board draft shows 3.05m. I cannot reproduce that; the controller's note says the board figure omitted CO-17 and may have deducted the duplicate twice (that would give 3,091,248).

**Amber Pilot: 1,019,152 + 195,448 = 1,214,600**
- Row CST-00105 (195,448, "Main engine instalment for AMBER-77 (AP-77 acceptance package)") is booked on project VSL-2502 (Elbe Runner) but carries yard job AMBER-77. Project Controls' email (file 10) asks for it to be moved, and the Amber Pilot acceptance certificate cites the same engine serial. I moved it.
- The result equals the vessel master forecast (1,214,600) exactly. Without the move, Amber Pilot's engine package would be only 74,552.

**Elbe Runner, cost to date: 2,299,410 - 555,296 - 195,448 + 9,792 = 1,558,458**
- Row CST-00068 (steel, "ERP conversion batch FX-UPLOAD-08"): 135,201.77 PLN at 4.3377 PLN per EUR is reported as 586,464.72. The amount was multiplied by the rate instead of divided. Correct value 31,169, a reduction of 555,296. With that fix the steel category comes to exactly 480,000.
- Minus the 195,448 Amber Pilot engine instalment (above).
- Plus 9,792 of December Gdansk labour (204 hours at 48), approved 8 January 2026, present in the time workbook but not in the ledger because the interface failed (files 03, 07, 10).
- Forecast at completion 2,204,000 is taken unchanged from the vessel master. Cost to date is 70.7% of that forecast.

**Hansa Tug: 84,500**
- Ledger as is: 62,000 design and 22,500 sales engineering. No vessel was built; there was only a letter of intent, cancelled 30 May 2025.

**Cross-checks that held**
- Approved timesheet cost per project (file 03) equals ledger direct labour for Nordlicht (360,000), Baltic Surveyor (380,000) and Amber Pilot (145,000), after excluding the duplicate entry TS-00047 ("approved-copy", 31,091, identical to TS-00002) and mapping yard job numbers (HH-407, GD-11/B, AMBER-77, ER-02) to project IDs through the alias sheet.
- All other PLN rows convert correctly (amount divided by the stated rate matches `reported_eur` within rounding).

## 3. Assumptions

1. "Cost of building" means production cost: direct material, bought-in systems, direct labour and yard overhead as booked on the project. HQ administration is excluded (the overhead sheet says it is "not normally inventoried").
2. Costs are cumulative across 2024 and 2025, not only 2025, because a build spans years. The file name says "2025" but 67 of the 138 rows are dated 2024.
3. Ledger amounts are net of VAT.
4. The ledger shows group-level cost. I did not add or remove intercompany recharges (see section 5).
5. For the mistranslated steel row I assumed the local amount really is PLN (corrected value 31,169). The round category total of 480,000 supports this.
6. The unsigned CO-17 work is a real cost of building Baltic Surveyor, even though it is unapproved and unbilled.
7. Yard overhead is taken as booked in the ledger, not recalculated from the overhead pools.
8. The hidden `Project_Aliases` sheet is used for mapping although it is marked "work in progress" and IT has not approved it. "Danzig" and "Gdansk" are the same yard.
9. Post-delivery work (Nordlicht science-module upgrade, 200,000 revenue) is not part of the build. No cost for it is identifiable in the ledger.

## 4. Problems found in the data

- **Wrong-way currency conversion**: one Elbe Runner steel row is overstated by 555,296.
- **Duplicate invoice**: 195,652 of Baltic Surveyor steel posted twice, never reversed.
- **Miscoded cost**: 195,448 of Amber Pilot engine cost sits on Elbe Runner.
- **Blank project**: 15,298 of Nordlicht class cost is unassigned.
- **Missing cost**: 9,792 of December labour for Elbe Runner never reached the ledger.
- **Unapproved cost**: 90,000 for CO-17 with no signed change order and no revenue.
- **Pivot sheet** has formulas without stored values and, by its own note, applies no quality checks.
- **Board draft cost figures** (2.70 / 3.05 / 1.19 / 1.80 / 0.08m) do not match corrected source data. The Elbe Runner 1.80m is described as a "forecast-to-date blend". Nordlicht's board margin also mixes 200,000 of upgrade revenue into the vessel.
- **Posting dates do not fit the build timeline**: 1.73m of Nordlicht cost is dated after its acceptance (28 Mar 2025) and 0.67m of Baltic Surveyor cost after its acceptance. Nordlicht timesheets run to August 2025. Either invoices were posted late or the dates are unreliable, so no dependable split by year is possible.
- **Timesheets cover 2025 only** yet equal the ledger's direct labour totals, which include 2024-dated postings. The two sources agree in total but not in timing.
- **Timesheet rates do not match the employee rate table**: 35 of the 45 approved employee entries use a different hourly rate than the employee's burdened rate, and 28 show a different home location. Re-priced at the rate table, labour would be 333,535 (Nordlicht), 401,523 (Baltic Surveyor), 150,501 (Amber Pilot) instead of 360,000 / 380,000 / 145,000.
- **Hansa Tug timesheets** show 62,000 of labour in 2025, including "hull", "outfitting" and "commissioning" work, continuing to October 2025, after cancellation and on a vessel that was never built. The ledger shows 62,000 as "design", mostly dated 2024.
- **Elbe Runner labour**: ledger 175,465 plus the missing batch 9,792 gives 185,257, but timesheets total 190,000. A gap of 4,743 is unexplained.
- **Elbe Runner logistics** is only 200, against 12,600 to 28,900 on the other vessels; possibly incomplete.
- **Overhead rates are inconsistent**: the Gdansk pool is allocated on machine hours (45.63 per hour), the board report uses labour hours, and no machine hours per project are given.
- **FX table**: the August 2025 PLN rate is inverted (0.2299), and there are no 2024 rates.
- **Intercompany**: Q2 engineering was charged at 7.5% instead of the 5% policy; the elimination journal is incomplete; one recharge has no receiving booking.

## 5. What I am unsure about

- **Intercompany recharges, the largest open point.** HVW-DE recharged engineering and procurement to BHW-PL (cost base 300,000 for Baltic Surveyor, 260,465 for Elbe Runner), and BHW-PL recharged yard labour to HVW-DE (cost base 347,619 for Nordlicht) and "launch support" for Amber Pilot (285,714). I cannot tell from the files whether these are already inside the ledger rows. Baltic Surveyor's ledger shows only 51,463 from "HVW Design Office", so the 300,000 may be missing; if so, its true group cost could be up to 300,000 higher (and Elbe Runner's up to 260,465 higher). If instead they are included at the charged price, costs are overstated by the mark-up (about 14,000 to 20,000 per vessel). The Amber Pilot recharge is odd in itself: the Gdansk yard billed Hamburg for a vessel Gdansk built and sold.
- **Elbe Runner final cost.** The 2,204,000 forecast is undated and may have been prepared from the uncorrected ledger. Completion is stated as 68% (cost), 61% (engineering milestones) and 72% (foreman). Dividing my corrected cost to date by those gives a final cost anywhere from about 2.16m to 2.55m; at the top of that range the vessel would lose money against the 2.35m price. A change order of +120,000 is pending.
- **Yard overhead level.** Applying the pool rates to 2025 labour hours instead of the booked amounts would raise overhead: Nordlicht 243,073 instead of 210,000 (+33,000); Baltic Surveyor about 320,800 instead of 220,000 (+101,000); Amber Pilot about 124,600 instead of 90,000 (+35,000). The Gdansk figures use labour hours as a stand-in for machine hours, so they are indicative only. Whether the Hamburg pool includes HQ occupancy is also unresolved.
- **Full cost including administration.** If HQ administration (7.02% of revenue) were added, it would add about 238,700 (Nordlicht), 280,800 (Baltic Surveyor) and 103,900 (Amber Pilot). I left it out.
- **The corrected steel row**: if the local amount was actually EUR rather than PLN, Elbe Runner's cost to date would be about 104,000 higher.
- **FX**: re-translating the 2025 PLN rows at treasury monthly rates instead of the booked rates would change each vessel by under 7,000. 2024 rows cannot be checked.
- **Whether CO-17 belongs in "build cost"** is a judgement; both figures are shown.
- **Completeness**: the ledger export ends 8 December 2025. Late invoices for Amber Pilot (accepted 12 December) may still be missing, as may warranty or retention-period costs for any vessel. The agreement of my totals with the vessel master forecasts is reassuring but the master may derive from the same ledger.
- All figures are unaudited management data.
