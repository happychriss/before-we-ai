# before-we-ai – Evidenzbasierte Context Discovery
*Konzeptzusammenfassung v3 — das „Warum" und die Leitplanken. Das „Wie" steht in den referenzierten Dokumenten und wird hier nicht wiederholt.*

## 1. Dokumentenlandkarte

**`before-we-ai-konzept-zusammenfassung.md`** (dieses Dokument): Rationale, Prinzipien, Leitplanken — für den Owner, nicht für den Build. **`before-we-ai-systemarchitektur.md`**: die Bauvorlage — Leitentscheidungen, Projektlayout, Module, die vier KI-Verträge, Nutzeraussagen-Quellenart, Milestones M0–M8. **`before-we-ai-testdatensatz-finance-anforderungen.md`**: die Validierungsbasis — Zielfragen Z1–Z4, Quellen, Fallen F1–F29, Fallenklassen K1–K7, Kennzahlen, Rollenliste Finance. **`before-we-ai-fixture-korpus-spezifikation.md`**: abgelöst, bleibt Fallenreferenz (T1–T12, Regeln gegen Selbstbetrug). An den Build gehen Architektur + Finanz-Korpus; die Zusammenfassung bleibt beim Owner.

## 2. Gedankengang

before-we-ai begann als AI-Dashboard-Tool und wurde auf seinen Kern reduziert: Nicht Visualisierung ist das Produkt, sondern das schnelle Verstehen fremder, verteilter Daten. Der Engpass liegt zwischen den Schichten — zwischen fragmentierten Daten und mächtiger, aber unzuverlässiger KI fehlt eine Schicht, die festhält, *was man weiß, was man nur vermutet und was man nicht weiß*. Der Differenziator: **Context Discovery durch Evidenz, nicht durch KI-Inferenz.**

## 3. Fundiertes Know-how

Die Wissenschaft liefert alle Bausteine, zusammengesetzt hat sie niemand: Dataset-Discovery (Beziehungen aus Datenverhalten), Truth Discovery und Uncertain Knowledge Graphs (widersprüchliche Quellen), Provenienz und Truth Maintenance (Rückverfolgbarkeit, Invalidierung). Der Markt belegt den Hebel — Grounding in kuratiertem Kontext hebt Text-to-SQL von ~40 % auf 85–95 % — aber **kein Produkt behandelt den Wissensstatus als Objekt erster Klasse**; Zustände wie „widersprüchlich" oder „unzureichend belegt" existieren nirgends.

## 4. Kernprinzipien (das Destillat)

**Epistemik ohne Mathematik, dafür mit Buchhaltung.** Der Mensch in der Loop ersetzt Kalibrierung, Fusionsmathematik und Relevanz-Engine; das Tool leistet, was Menschen nicht können: Behauptung und Beleg strukturell trennen, automatisch falsifizieren, Konflikt von Nichtwissen unterscheiden. Claims sind Git-versionierte Dateien mit fünf Status und Evidenzliste statt Konfidenzzahl; die KI kann strukturell nur `inferred` erzeugen — Statuswechsel gehören Sonde und Mensch. **Das Brain sitzt in der Pipeline, nicht in der KI:** Das LLM ist Subroutine an vier Vertragsstellen mit zugeschnittenem Kontext; Modellqualität bestimmt Effizienz, nie Korrektheit. **Relevanz zeigt sich am Gebrauch:** Hypothesen und Nutzeraussagen werden nicht vorab kuratiert — tragfähig wird, worauf Fragen ruhen (epistemische Stückliste); der Governance-Gap ist eine Lastliste, kein Score. **Sonden speisen sich aus vier Quellen:** Claim-Negation, Strukturformen-Katalog, Domänen-Invarianten (gegen Rollen formuliert, die Bindung ist selbst ein Claim), Fehler-Archäologie — Letztere ist kristallisierte Berufserfahrung und der eigentliche, nicht kopierbare Kern.

## 5. Leitplanken und Risiken

Harte Invarianten: **False-Promotion-Rate = 0** und **Silent-Wrong-Answers = 0** (Abweichung vom Referenzergebnis ohne markierte Annahme = Release-Blocker); Tests bestrafen Entschiedenheit, wo „ungeklärt" korrekt wäre. Disziplin: Korpus einfrieren vor Produktcode, Toleranzen nie „bis grün", Blind Traps durch den Owner, Regel der Drei (Abstraktion zum Domänenpaket erst ab der dritten Domäne), Milestone-Abschluss erst nach realem Datensatz. Echte Aufwandstreiber sind unglamourös: schmutzige Realdaten, Excel, SQL-Parsing-Edge-Cases, kryptische Legacy-Namen; das strukturell fragilste Stück ist die Dokumenteninterpretation (V3) — ihre Evidenz bleibt darum grundsätzlich schwach. Format-Entscheidung: Markdown als Quelle der Wahrheit (diffbar, token-schlank, von Mensch und Modell editierbar), HTML nur als generiertes Derivat.

## 6. Stand und nächster Schritt

Konzept, Architektur und Validierungsbasis sind konsistent und übergabefähig. Nächster Schritt: **M0 — der Finanz-Korpus-Generator** (nur Transaktionsachse erzeugen, Finanzen per Buchungsregeln ableiten, Bilanzschluss als Selbsttest, Referenzergebnisse nachrechnen), danach M1–M8 gemäß Architektur. Die offene Kernfrage bleibt empirisch: produzieren die Sonden auf echten Daten so wenige Fehlalarme, dass der Analyst dem Tool nach der dritten Sitzung noch glaubt.
