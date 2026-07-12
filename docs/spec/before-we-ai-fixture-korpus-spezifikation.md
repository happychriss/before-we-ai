# before-we-ai – Fixture-Korpus-Spezifikation
*Testbasis vor dem Tool: Quellen, eingebaute Fallen, erwartete Verdikte, Messgrößen*

> **Status: abgelöst durch `before-we-ai-testdatensatz-finance-anforderungen.md`.** Der Finanz-Korpus enthält das Handelsszenario als Teilmenge (Aufträge, Rechnungen, Kunden, Hierarchien); es wird nur **ein** Generator gebaut. Dieses Dokument bleibt als Fallenreferenz gültig — die Fallenklassen T1–T12, die Kennzahlen-Definition und die „Regeln gegen Selbstbetrug" gelten unverändert und werden vom Finanz-Korpus referenziert.

## Zweck und Prinzip

Der Korpus ist der Prüfstand, der den Tool-Code ehrlich hält. Er wird **vor** der Implementierung gebaut und eingefroren (Git-Tag), damit das Tool gegen ihn entwickelt wird — nicht er gegen das Tool. Er ist **generiert, nicht handgepflegt**: ein Python-Skript mit Seed erzeugt alle Quellen; jede Falle ist ein Parameter. So lassen sich Varianten erzeugen (Seed-Jitter), gegen die Verdikte stabil bleiben müssen. Ziel ist Korrektheit, nicht Skalierung — die Datenmengen sind bewusst klein (Sekunden-Laufzeit).

## Quellen (Referenzszenario Handel/Vertrieb)

`erp/` als DuckDB-Datei: `customers` (~5.000 Zeilen, enthält echte Duplikate), `invoices` (~50.000, Kundenreferenz mit führenden Nullen als Text), `invoice_items` (Tag × SKU), `returns` (~3.000, Rechnungsreferenz). `kundenhierarchie.xlsx`: Key-Account-Zuordnung über Kunden**namen** — verbundene Header-Zellen, Umlaute, „GmbH" vs. „GmbH & Co. KG", Leerzeichen. `forecast_2026.xlsx`: Monat × Produktgruppe, deutsche Dezimalkommas, deutsche Monatsnamen, ein Datumsfeld als Text. `legacy_customers.csv`: Latin-1-Encoding, Datum als DD.MM.YYYY, IDs numerisch überlappend mit `customers`, aber teils recycelt. `marketing/`: ein synthetisches Dokument **plus ein echtes, hässliches öffentliches PDF** (z. B. Geschäftsbericht) mit manuell annotierten Ankern. `crm_notes/`: ~50 Textnotizen, darunter die widersprechende Hierarchie-Aussage, eine implizite „aktiv"-Definition, Legacy-Kürzel (KDNR), Rauschen.

## Eingebaute Fallen und erwartete Verdikte

| # | Falle | Erwartetes Endverdikt | Prüft |
|---|---|---|---|
| T1 | Führende Nullen: `invoices.cust_no` '0001042' vs. `customer_id` 1042 | technically tested **nur mit** dokumentierter Normalisierung; ohne Normalisierung muss die Sonde scheitern | Normalisierungsschicht |
| T2 | 13 % Retouren-Waisen, alle vor 2022 | Status bleibt inferred **plus** generierte Fachfrage „Datenschnitt?" — weder tested noch contradicted | Verdikt-Granularität, Fragen-Ausbeute |
| T3 | ID-Recycling Legacy: 61 % ID-Treffer, davon 38 % mit anderem Namen/PLZ | contradicted | Widerspruchssonde, Identitäts-Claims |
| T4 | Hierarchie-Excel joint über Namen (71 % Match), CRM-Notiz sagt „über Debitorennummer" | unresolved (Konflikt, laut) | Konflikt ≠ Mittelwert |
| T5 | Grain-Mismatch Forecast (Monat×Gruppe) vs. Items (Tag×SKU); Gruppen-Mapping fehlt | in Phase 4 lazy materialisierter inferred-Claim | Assumption Capture |
| T6 | Zufalls-Überlappung: zwei fachlich unverwandte Spalten mit gleichem Wertebereich (1–500) | darf hypothetisiert werden, darf aber **nie** über inferred hinaus; Kardinalitäts-/Fan-out-Sonde liefert Gegenindiz | Negativkontrolle, False-Positive-Pfad |
| T7 | Nur semantisch findbare Beziehung: Produktgruppen deutsch vs. Kategorien englisch („Zubehör"/„Accessories"), keine Wertüberlappung | Claim muss in Phase 2 **existieren** (Kandidatenmatrix ist hier blind) | V1-Recall auf mindestens einer Instanz |
| T8 | Dokument-Anker: gerundete 12,3 Mio (netto? brutto?); eine Zahl nur in einer Grafik; eine Zahl, die zufällig ein falsches Aggregat trifft | Einzeltreffer bleibt schwache Evidenz; Zufallstreffer darf **nicht** promoten; Grafik-Zahl darf nicht als Text-Anker erscheinen | V3-Negativfälle, Mehrfach-Anker-Regel |
| T9 | Excel-Schmutz: Kundennummern als Zahl gespeichert (Nullen verloren), verbundene Header, Dezimalkomma | Ingestion übersteht das; Sonden weisen Normalisierungsannahmen aus | Ingestion/Normalisierung |
| T10 | „Aktive Kunden": zwei plausible Operationalisierungen (Statusfeld: 5.340 vs. Kauf-in-24-Monaten: 4.812); PDF sagt „über 4.800" | zwei Konzept-Claims; nur einer wird durch Reconciliation gestützt; keiner wird ohne Mensch business-confirmed | Konzept-Claims × Reconciliation |
| T11 | Echte Duplikate im Kundenstamm | Schlüssel-Claim scheitert an Duplikatsonde, Fachfrage entsteht | Duplikat-Template |
| T12 | Rechnungen bis Jun 2026, Forecast ganz 2026 | Coverage-Sonde meldet Teilabdeckung als Befund, nicht als Fehler | Coverage-Verdikt |

## Ground Truth und Messgrößen

`expected_verdicts.yaml` hält pro eingebautem Claim: erwarteter Endstatus, erwartete Evidenztypen, pro Sonde das erwartete Verdikt — plus zwei Listen: Claims, die nach Phase 2/4 **existieren müssen** (Recall-Menge), und Claims, die **nie promoted werden dürfen** (Sperr-Menge).

Drei Kennzahlen, in dieser Rangfolge: **False-Promotion-Rate = 0** (harte Invariante — ein einziger fälschlich beförderter Claim ist ein Release-Blocker), **Seeded-Recall** (Anteil der eingebauten Beziehungen, die als Claim entstehen; Zielwert ehrlich niedrig ansetzen, T7 zählt gesondert), **Fragen-Ausbeute** (die eingebauten Definitionslücken T2, T8, T10, T11 müssen als Fachfragen auftauchen). Wichtig: Der Korpus enthält Fälle, deren richtige Antwort „ungeklärt" ist — die Tests müssen **Entschiedenheit bestrafen**, wo Nichtwissen korrekt wäre.

## Regeln gegen Selbstbetrug

Erstens: Korpus einfrieren, bevor Produktcode entsteht; Änderungen am Korpus nur mit begründetem Commit. Zweitens: Toleranz- und Schwellwertänderungen im Tool sind nur mit dokumentierter fachlicher Begründung erlaubt — nie „bis der Test grün ist"; Verdikte müssen über mehrere Generator-Seeds stabil sein. Drittens: **Blind Traps** — zwei bis drei Fallen definiert der Projektowner selbst im Generator-Config und hält sie aus den Implementierungs-Sessions heraus; sie testen, was der Implementierer nicht antizipiert hat. Viertens: Der Korpus beweist Korrektheit auf bekannten Fallen — nicht Robustheit auf Unbekanntem. Der Abschluss des Milestones ist deshalb erst ein Lauf gegen **einen realen, gut bekannten Datensatz**, dessen Wahrheit der Owner kennt.

## Bekannte Grenzen (bewusst akzeptiert)

Eine Domäne (Handel/Vertrieb) — Finance-Logik (Konten, Perioden, Stornobuchungen) bricht anders und braucht später eine zweite Mini-Domäne. Keine Skalierungsaussage — die Kandidatenmatrix ist über Spaltenpaare quadratisch; bei 30 Tabellen irrelevant, bei 800 ein eigenes Thema. Synthetische Dokumente testen V3 nur teilweise — deshalb das eine echte PDF als Pflichtbestandteil. Und der Generator selbst ist Code mit Fehlerpotenzial: seine erwarteten Zahlen (z. B. 4.812) müssen aus den generierten Daten **nachgerechnet**, nicht hineingeschrieben werden.
