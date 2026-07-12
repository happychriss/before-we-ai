# Expdash – Testdatensatz Finance (Anforderungen)
*Korpus v2, Domäne Finanzen/Vertrieb: Quellenliste mit Eigenschaften und eingebauten Fallen. Keine Testdaten — die Bauvorlage für den Generator.*

## Zweck und Validierungsprinzip

Dieser Korpus bildet eine Mini-Unternehmensgruppe ab, deren Belege am Ende eine GuV und eine Bilanz aufmachen. Er wird **von oben validiert**: Vier Zielfragen definieren, was das Tool am Ende leisten muss; der Generator berechnet für jede Frage das Referenzergebnis aus den Daten. Die Zielfragen: **Z1** Außendiensttage je Mitarbeiter und Quartal. **Z2** Umsatz- und Margenentwicklung je Kunde und Key Account (extern, netto, EUR). **Z3** Gewinnerwartung: Plan vs. Ist je Profitcenter. **Z4** Schließt die Bilanz je Gesellschaft und Periode (Meta-Frage, Invariante).

**Rahmen:** Zwei Gesellschaften (DE in EUR, US in USD) mit Intercompany-Verkehr, 24 Monate (2024-01 bis 2025-12), drei Währungen (EUR, USD, CHF), ~300 Kunden, ~200 Materialien, ~8.000 Rechnungen, ~40.000 Hauptbuchzeilen. Klein genug für Sekunden-Läufe. Maximal drei unterjährige Organisationsänderungen (siehe F5, F14, F15) — Realismus durch gezielte Gemeinheiten, nicht durch Volumen.

**Generator-Prinzip:** Erzeugt wird nur die Transaktionsachse (Aufträge → Rechnungen/Gutschriften → Zahlungen). Alle Finanzdaten (Hauptbuch, Rückstellungen, IC, Bilanz) werden über deklarierte Buchungsregeln daraus **abgeleitet**. „Bilanz schließt" und „Nebenbuch = Hauptbuch" sind Selbsttests des Generators — vor dem Einfrieren. Referenzergebnisse werden nachgerechnet, nie hineingeschrieben.

## Quellen und Fallen

### A. Vertriebskette (ERP-Datenbank, je Gesellschaft)

| Quelle | Eigenschaften | Fallen |
|---|---|---|
| A1 `orders` (Kopf+Positionen) | Auftragsdatum, Kunde, Vertriebsmitarbeiter, Belegwährung, Status | **F1** ~5 % stornierte Aufträge mit kryptischem Statuscode ('X'); Aufträge ohne Rechnung (offen) — legitime Waisen, erwartet: Fachfrage, nicht Fehler |
| A2 `invoices` (Kopf+Positionen) | Beleg- und Hauswährungsbetrag, Belegkurs, Referenz auf Auftrag, führende Nullen in Belegnummern | **F2** Teillieferung (1 Auftrag → n Rechnungen) und Sammelrechnung (n Aufträge → 1 Rechnung) — Fan-out-Falle für naive Joins. **F3** Stornorechnungen als Umkehrpaare mit Referenz — naive Summe zählt doppelt |
| A3 `credit_notes_legacy` | Alte Gutschriftentabelle, nur befüllt bis 2024-06; ab 2024-07 sind Gutschriften Belegart 'G' in `invoices` | **F4** Doppelzähl-/Lückenfalle: Erlösschmälerung lebt in zwei Orten; korrekte Antwort erfordert beide — erwartet: Konzept-Claim + Fachfrage |

### B. Stammdaten

| Quelle | Eigenschaften | Fallen |
|---|---|---|
| B1 `customers` | Inkl. IC-Kunden im Nummernkreis 9xxxx; Dubletten; ein Kunde 2025 auf neue Nummer migriert | **F5** Alt→Neu-Mapping existiert **nur** in `kunden_migration.xlsx` — ohne sie zerfällt die Kundenentwicklung (Z2) in zwei Kunden |
| B2 `customer_hierarchy` | Versioniert (valid_from/valid_to); Umhängung eines Großkunden zum 01.07.2025 | **F6 (Kernfalle)** Join ohne Gültigkeitsprädikat: hohe Überlappung, Anti-Join grün — Vorjahre laufen auf falschen Key Account. Erwartet: technically tested erlaubt, aber Z2 muss die Zeitannahme als offene Annahme ausweisen (Silent-Wrong-Answer-Test) |
| B3 `materials` | Beschreibungen DE/EN gemischt; Produkthierarchie als Positionsstring (PRODH-artig, '0001 0002 0003' konkateniert) | **F7** Beziehung steckt **im** String — kein Wert-Overlap, kein Gleichheits-Join; erfordert Decode-Sonde oder Fachfrage |
| B4 `material_hierarchy` + `marketing_grouping.xlsx` | Offizielle Decodier-Tabelle vs. konkurrierende Marketing-Gruppierung | **F8** Zwei Hierarchien beanspruchen „Produktgruppe"; Plan (D6) referenziert stillschweigend die Marketing-Sicht — erwartet: unresolved bis Mensch klärt |
| B5 `sales_reps` + `territory_plz` + `kontakte_aussendienst.xlsx` | Gebietszuordnung über PLZ-**Bereiche** (von–bis); ein Mitarbeiter scheidet zum 30.09.2025 aus; Kontaktliste mit privaten Handynummern | **F9** BETWEEN-Beziehung — Kandidatenmatrix blind (strukturelles Pendant zu T7). **F10** Aktivitäten nach Austritt (Datenfehler, muss als Befund auftauchen). Kontaktliste: legitime Quelle für Rep-Stamm, darf aber in keiner Umsatzfrage landen |

### C. CRM

| Quelle | Eigenschaften | Fallen |
|---|---|---|
| C1 `crm_activities` | Besuche/Calls: Datum, Mitarbeiter, Kunde — Basis für Z1 | **F11** Kundenreferenz uneinheitlich: teils ID, teils Alt-ID (F5!), teils Klarname. **F12** Sync-Dubletten (gleicher Besuch, zwei Datensätze, Sekunden versetzt). **F13** Aktivitäten für Interessenten ohne Kundenstamm — **legitime** Waisen; erwartet: Fachfrage, nicht contradicted |
| C2 `crm_notes` | Freitext | Versteckte Definitionen („Gebiet Nord läuft über PLZ", Hinweis auf Rabattvertrag); Rauschen |

### D. Finanzen (je Gesellschaft)

| Quelle | Eigenschaften | Fallen |
|---|---|---|
| D1 `gl_postings` | Konto, Kostenstelle, Profitcenter, Belegreferenz, Buchungs- vs. Belegdatum, Betrag in Beleg- und Hauswährung, **Vorzeichenkonvention: Haben negativ** | **F14** Umsatzkonten sind negativ — naive SUM liefert negative Erlöse; Konvention muss als Konzept-Claim entstehen. Stornopaare, monatliche Rabatt-Rückstellungsbuchungen, IC-Konten enthalten |
| D2 `chart_of_accounts` | Deutsche Kontennamen, GuV/Bilanz-Kennzeichen, Bereichslogik | **F15** „Umsatzerlöse" = 4000–4999 **abzüglich** 4800er Erlösschmälerungen — Bereichs-Mapping, kein 1:1-Join; Definition steht in E3 |
| D3 `cost_centers` + `profit_centers` + Zuordnung | Hierarchien; KST→PC-Zuordnung ändert sich zum 01.07.2025 | Versionsfalle analog F6 auf der Kostenseite (Z3) |
| D4 `projects` | Interne Aufträge mit Budget | **F16** Ab Q3/2025 laufen Teile der Kosten auf Projekte statt Kostenstellen — die KST-Sicht hat ein Loch, das kein Fehler ist; Z3 braucht beide Dimensionen; erwartet: Befund + Fachfrage |
| D5 `fx_rates` | Monatsdurchschnitt + Stichtagskurs, Kurstypen M/B | **F17** Eine fehlende Kurs-Periode (CHF); **F18** ein Paar invertiert notiert (USD/EUR statt EUR/USD — Größenordnungs-Check muss anschlagen); **F19** Belegkurs ≠ Monatskurs: drei plausible Umrechnungen für Z2, nur eine matcht E1 — Reconciliation als Schiedsrichter |
| D6 `plan` | Plan-GuV je Profitcenter × Monat, nur EUR | Grain- und Währungsbruch zu Ist (Z3); referenziert Marketing-Gruppierung (F8) |
| D7 `opening_balances` + `ar_open_items` | Eröffnungsbilanz; offene Posten mit Teilzahlungen | **F20** Zahlung ohne Rechnungsreferenz (unapplied cash); Bilanz schließt nur, wenn Generator korrekt ableitet — Z4-Invariante |
| D8 Intercompany | IC-Umsätze DE↔US über 9xxxx-Kunden und IC-Konten | **F21** E1 berichtet nur externen Umsatz — Reconciliation scheitert bis IC ausgeschlossen (Konzept-Claim „Umsatz = extern"). **F22** Ein gezielter IC-Bruch: DE gebucht, US fehlt — Invariantensonde muss ihn finden |

### E. Dokumente

| Quelle | Eigenschaften | Fallen |
|---|---|---|
| E1 `management_report.pdf` | Quartalszahlen: Umsatz (extern, netto nach Erlösschmälerung und Rabatt-Rückstellung), EBIT; gerundet | **F23** Eine Zahl nur in einer Grafik (V3-Negativfall). **F24** Eine Vorjahreszahl restated — matcht die DB **absichtlich nie**; erwartet: dokumentierter Widerspruch, keine erzwungene Versöhnung |
| E2 `rabattvertrag.pdf` | Retro-Rabatt 2 % ab 500 T€ Jahresvolumen für eine Kundengruppe, Jahresend-Gutschrift, monatliche Rückstellung | **F25** Verbindet B2 (Gruppe!), D1 (Rückstellung) und E1 (Netto-Zahl) — Z2 stimmt nur mit Rabattlogik; der anspruchsvollste Mehrquellen-Fall |
| E3 `buchhaltungsrichtlinie.pdf` | Kontodefinitionen, Rückstellungskonto, Umrechnungsregeln | Der Schlüssel, der F14/F15/F19 auflösbar macht — testet, ob V3-Definitionen zu Konzept-Claims werden |
| E4 Rauschen | Reisekostenrichtlinie; Lieferantenkatalog; **alte Pressemitteilung über einen verkauften Geschäftsbereich mit Umsatzzahl** | **F26 (vergifteter Anker)** Die Zahl des verkauften Bereichs existiert in keiner Tabelle — Reconciliation darf sie **nicht** irgendwo hineinzwingen; kein Claim darf auf E4 ruhen (Präzisionstest V1/V3) |

## Neue Fallenklassen und ihre Konsequenzen fürs Tool

**K1 Grün-aber-falsch** (F6, F14, F19, Kurstyp/Brutto-Netto): Sonde besteht, Claim semantisch falsch. Erzwingt die neue Systemmetrik **Silent-Wrong-Answers = 0**: Für Z1–Z4 liegen Referenzergebnisse vor; jede Abweichung ohne markierte verantwortliche Annahme ist ein Release-Blocker. **K2 Doppelzählung durch Strukturbrüche** (F3, F4). **K3 Konventionssemantik** (F14, F15) — nur über Konzept-Claims + Richtliniendokument lösbar. **K4 Nicht-wertbasierte Strukturen** (F7 positional, F9 Bereiche, F6/D3 Gültigkeit): erzwingt drei neue Sonden-Templates (validity_join, range_join, decode) — Regel gegen Wildwuchs: neue Templates nur, wenn ein Korpus-Fall sie erzwingt, sonst untestable→Fachfrage. **K5 Invariantensonden** (Z4, F22, Nebenbuch=Hauptbuch): landschafts- statt claim-gebunden — neue Sondenklasse, konzeptionell im Architektur-Dokument nachzuziehen. **K6 Legitime Waisen** (F1, F13): Verdikt-Granularität — Waise ≠ Fehler. **K7 Vergiftete Anker und Restatements** (F24, F26): Reconciliation braucht Negativ-Disziplin — nicht jede Dokumentzahl darf einen Treffer suchen.

## Ergänzung: Rollenbindung (nach Architektur-Update)

Neue Quelle **D9 `buchungen_report.csv`**: ein aggregierter Buchhaltungs-Export mit sprechenden Spaltennamen, aber ohne Stornopaare, Beträge nur positiv mit separatem S/H-Kennzeichen. **F27** Die naheliegende Bindung ist falsch: Für die Rolle *journal* wirkt der Report (Namen!) attraktiver als `gl_postings` — aber nur `gl_postings` erfüllt Soll=Haben je Beleg. Erwartet: Die Kandidatensuche wählt per Invariante die richtige Bindung; die Report-Bindung endet verworfen/contradicted mit dokumentierter Begründung, der Report selbst bleibt als sekundäre Quelle (Abstimmziel) erhalten.

**Anhang — Rollenliste Finance v1** (flaches YAML, kuratiert; Erweiterung nur, wenn ein Template sie erzwingt): `journal`, `amount_doc`, `amount_local`, `account`, `period`, `doc_ref`, `entity`, `subledger_ar`.

### Nutzeraussagen als Quellenart (nach Architektur-Update)

Der Korpus enthält ein Skript vorgegebener `tell`-Aussagen, die während des Testlaufs eingespielt werden. **F28 (Aussage vs. Daten):** Aussage „Wir beliefern nur Apotheken und Großhändler" — die Kundentyp-Sonde findet ab 2024 zusätzlich Kliniken. Erwartet: dokumentierter Konflikt, testimonialer Claim auf `unresolved`, Fachfrage; die Aussage darf **nicht** stillschweigend gewinnen. **F29 (Geltungsbereich):** Aussage „Geschäftsjahr läuft Mai bis April" — gemeint ist nur die US-Gesellschaft, die Aussage sagt es nicht. Erwartet: Die Spiegelung fragt den Geltungsbereich explizit ab (V3-Pflichtfeld `scope`); ein entity-übergreifend bestätigter Kalender-Claim, der Z2/Z3 für die DE-Gesellschaft verschiebt, zählt als Silent-Wrong-Answer.

## Regeln (unverändert aus Korpus v1, hier verschärft)

Einfrieren vor Produktcode; Referenzergebnisse und Bilanzschluss als Generator-Selbsttest; Toleranzen nie „bis grün"; zwei bis drei Blind Traps durch den Owner (Vorschlag: eine zusätzliche Währungs- oder Periodenfalle, die in diesem Dokument bewusst **nicht** steht); Milestone-Abnahme erst nach Lauf gegen einen realen Datensatz. Bekannte Grenze: Keine Konsolidierungslogik über die IC-Eliminierung hinaus (keine Kapitalkonsolidierung, kein Minderheitenanteil) — das wäre Realismus ohne Testertrag.
