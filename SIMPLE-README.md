# before-we-ai — einfach erklärt

Dieses Dokument erklärt das Projekt ohne Fachchinesisch. Es wächst mit:
nach jedem Milestone kommt ein neuer Abschnitt dazu, im gleichen einfachen Stil.

---

## Worum geht es überhaupt?

Das Tool `before-we-ai` soll später auf echten, chaotischen Firmendaten arbeiten
und Fragen beantworten — und zwar so, dass es **niemals still und heimlich eine
falsche Antwort** gibt. Entweder die Antwort stimmt, oder das Tool sagt ehrlich:
„Hier bin ich unsicher, und zwar deshalb."

Das Problem: Wie beweist man, dass ein Tool ehrlich ist? Auf echten Daten kann
man es nicht testen, denn da kennt niemand die richtige Antwort. Also bauen wir
zuerst **die Prüfung** — und erst danach den Prüfling.

---

## M0 — Die Prüfung bauen (✅ fertig, eingefroren als `m0-corpus-v1`)

### Der Korpus = die erfundene Übungsfirma

Eine komplette, ausgedachte, aber realistische Firma: zwei Gesellschaften
(DE in Euro, US in Dollar), 24 Monate Geschäft — Aufträge, Rechnungen,
Buchhaltung, Kundenlisten in Excel, Verträge als PDF. Absichtlich unordentlich,
wie im echten Leben.

Der entscheidende Unterschied zu echten Daten: **Wir haben das Antwortheft**
(`expected_verdicts.yaml`). Wir wissen für jede Frage, was rauskommen muss,
weil wir die Firma selbst gebaut haben.

### Die Zielfragen Z1–Z4 = die vier Prüfungsaufgaben

Vier typische Geschäftsfragen, z.B. „Wie viel externer Umsatz pro Kunde?" (Z2)
oder „Gehen die Bücher auf?" (Z4). Für jede kennen wir das richtige Ergebnis
auf den Cent. Wenn das Tool später etwas anderes ausrechnet, **ohne zu sagen
warum**, ist es durchgefallen. Das ist die Messlatte für „das Tool funktioniert".

### Die Fehler F1–F29 = die versteckten Fallen

Einzelne, absichtlich eingebaute Stolperfallen — jede eine Geschichte, die in
echten Firmen ständig passiert:

- Kunde 1101 bekommt 2025 die neue Nummer 1201 (F5) — wer das nicht merkt,
  verliert seinen Umsatz.
- Eine Rechnung plus ihre Stornierung (F3) — wer naiv summiert, zählt doppelt.
- Eine Umsatzzahl steht in einer alten Pressemitteilung, ist aber längst
  verkauftes Geschäft (F26) — wer sie glaubt, ist vergiftet.

Dazu **3 Blind-Fallen**, die nur der Projektinhaber kennt — wie
Prüfungsaufgaben, die der Lehrer vorher nicht verrät.

### Die Fehlerklassen K1–K7 = die Sorten von Fallen

Das Muster hinter den einzelnen Fallen:

- **K1** = „grün aber falsch" — die Rechnung geht auf, ist aber inhaltlich
  trotzdem falsch. Die gefährlichste Sorte.
- **K2** = Doppelzählung durch Strukturbrüche.
- **K3** = Konventionen, die nur im Richtlinien-PDF stehen (z.B. „Haben ist negativ").
- **K4** = Verknüpfungen, die man nicht am Wert erkennt (Gültigkeitszeiträume,
  PLZ-Bereiche, codierte Textspalten).
- **K5** = Grundregeln, die immer gelten müssen (Bücher gehen auf).
- **K6** = „legitime Waisen" — ein offener Auftrag ohne Rechnung ist **kein**
  Fehler, nur ein Wartezustand.
- **K7** = vergiftete Zahlen, die man niemals glauben darf.

Wichtig: Die Prüfung testet **Fallentypen, nicht einzelne Fallen** — deshalb
kann sie auch die Blind-Fallen prüfen, ohne sie zu kennen.

### M0 in einem Satz

Wir haben eine Übungsfirma mit versteckten Fallen und einem Antwortheft gebaut,
unabhängig nachgeprüft und eingefroren — jede zukünftige Version des Tools muss
diese Prüfung bestehen, bevor sie irgendetwas darf. Und das Tool selbst bekommt
**kein Finanzwissen einprogrammiert**: Es muss die Regeln selbst aus den Daten
und Dokumenten herausfinden. Das Finanzwissen wohnt im Korpus, nicht im Tool.

---

## M1 — Das Gedächtnis des Tools (✅ fertig, Tag `m1-core-v1`)

Jetzt gibt es das erste Stück vom Tool selbst. Noch keine Datenanalyse,
keine KI — nur das **Gedächtnis**: die Regeln, nach denen das Tool sich
merkt, was es weiß, was es vermutet und was es nicht weiß.

### Der Claim = die Karteikarte

Jede Vermutung wird eine Karteikarte: „Ich glaube, Konto 4300 ist
Innenumsatz." Auf der Karte steht immer, **wer sie geschrieben hat** und
**welche Beweise dranhängen**. Eine Karte hat genau einen von fünf Stempeln:

- **vermutet** (inferred) — jemand glaubt es, geprüft hat es keiner.
- **geprüft** (tested) — eine automatische Stichprobe (Sonde) hat es bestätigt.
- **widerlegt** (contradicted) — die Sonde sagt: stimmt nicht.
- **ungeklärt** (unresolved) — die Beweise widersprechen sich. Laut, nicht leise!
- **vom Chef bestätigt** (business-confirmed) — ein Mensch hat es abgesegnet.

### Die drei eisernen Regeln

1. **Die KI darf nur vermuten.** Egal wie überzeugt sie klingt — sie kann
   Karten anlegen, aber niemals selbst einen besseren Stempel draufdrücken.
   Befördern dürfen nur eine Sonde oder ein Mensch. Das ist keine
   Vereinbarung, das ist eingebaut: Es gibt schlicht keinen Weg im Code.
2. **Widerspruch macht laut.** Sagt eine Sonde „stimmt" und eine andere
   „stimmt nicht", wird nicht gemittelt und nicht das Neueste geglaubt —
   die Karte springt auf **ungeklärt**, und ein Mensch muss ran. Das gilt
   sogar für Chef-bestätigte Karten: Findet eine Sonde später etwas
   Gegenteiliges, ist auch die wieder ungeklärt.
3. **Beweise sind ein Kassenbuch.** Jeder Beweis wird nur angehängt, nie
   geändert, nie gelöscht. Höchstens als „veraltet" markiert — dann zählt
   er nicht mehr, bleibt aber nachlesbar.

### Die Spiegel-Schleife

Sagt der Nutzer „Unser Geschäftsjahr läuft Mai bis April", speichert das
Tool den Satz wörtlich — und bevor ein Mensch das bestätigen darf, muss
geklärt sein, **wofür es gilt**: Welche Gesellschaft? Welcher Zeitraum?
Eine Bestätigung ohne diese Angabe wird abgelehnt. (Das ist genau die
Falle F29 aus dem Korpus: Der Satz galt nur für die US-Firma.)

### Eine Karte pro Regel, nicht pro Zeile

Wichtig bei großen Datenmengen: Eine Karteikarte beschreibt immer eine
**Regel** („jeder offene Posten hat eine Buchung im Hauptbuch"), nie eine
einzelne Datenzeile. Prüft die Sonde 100.000 Zeilen und findet 37
Ausreißer, entsteht **eine** Karte mit **einem** Beweis: geprüfte Menge,
Anzahl Ausnahmen, eine Handvoll anschaulicher Beispiele — nicht 100.000
Karten, die nie jemand durchsieht. Die vollständige Ausnahmeliste landet
im wegwerfbaren Zwischenspeicher, nicht in den Akten.

Zwei Schutzmechanismen gehören dazu: Wird dieselbe Regel doppelt
vorgeschlagen (anders formuliert, andere Sitzung), erkennt der
Aktenschrank sie an ihrem Inhalt und legt **keine zweite Karte** an. Und
wenn sich hinter den Ausnahmen ein eigenes Muster verbirgt (z.B. „alle
37 stammen aus der alten Nummernwelt"), kann ein Mensch daraus gezielt
eine **neue Karte** machen — die mit der Ursprungskarte verknüpft ist,
aber wieder bei „vermutet" anfängt und sich ihre Stempel selbst verdienen
muss.

### Der Aktenschrank

Alles liegt als einfache Textdateien in einem Projektordner — eine Datei
pro Karteikarte, eine pro Beweis. Keine Datenbank, alles mit Git
versionierbar. Ein Prüf-Kommando kontrolliert, dass keine Karte auf
Beweise verweist, die es gar nicht gibt.

### Und die Prüfung aus M0?

Das Gedächtnis wurde direkt gegen das Antwortheft getestet: Für jede der
32 Fallen wird durchgespielt, welche Beweise sie erzeugen würde — und
geprüft, dass die Karteikarte auf dem richtigen Stempel landet. Vergiftete
Zahlen (K7) bleiben **vermutet**, egal wie viele Dokumente sie erwähnen.
Legitime Waisen (K6) werden **nicht** als widerlegt abgestempelt. Und der
härteste Test: Mit nur KI-Beweisen wird **keine einzige** der 32 Fallen
befördert — falsche Beförderungen: null.

### M1 in einem Satz

Das Tool hat jetzt ein ehrliches Gedächtnis: Karteikarten mit fünf
Stempeln, bei denen die KI nur vermuten darf, Widerspruch laut wird und
kein Beweis je verschwindet — geprüft gegen alle 32 Fallen der Übungsfirma.

---

## M2 — Das Tool bekommt Sinne (✅ fertig, Tag `m2-ingestion-v1`)

Bisher hatte das Tool ein Gedächtnis, aber keine Augen. Jetzt kann es
Datenquellen öffnen und **vermessen** — immer noch ohne KI, alles pures
Handwerk.

### Quellen anschließen

Das Tool öffnet, was eine Firma so herumliegen hat: Datenbanken, CSV-Dateien,
hässliches Excel. Alles wird unter einem Dach als abfragbare Tabellen
bereitgestellt. Wichtigste Regel dabei: **Nichts wird kaputtgeputzt.** Eine
Belegnummer wie `0001042` bleibt Text mit ihren führenden Nullen — das Tool
rät niemals, dass Text „eigentlich eine Zahl" sei. (Genau daran sind schon
viele Datenprojekte gestorben — das ist Falle T1 aus der Prüfung.)

### Der Excel-Vorleser mit Putzprotokoll

Excel ist ein Sonderfall: verbundene Überschriften, Zahlen wo Nummern
stehen sollten, Datumswerte in Excel-Geheimschrift. Ein eigener Vorleser
bügelt das glatt — aber nicht heimlich: **Jede Putz-Entscheidung wird als
Beweis protokolliert** („Spalte X: Zahl zu Text gemacht, Beispiel: 1101").
So kann später jeder nachlesen, was beim Einlesen verändert wurde. Das
Protokoll kann eine Karteikarte niemals befördern — Einlesen ist Beobachten,
nicht Urteilen.

### Jede Spalte wird vermessen

Für jede Spalte jeder Tabelle entsteht ein Steckbrief: Wie viele Werte, wie
viele verschiedene, wie viele leer, welches Muster (`AA-AAA-9999999`),
welche häufigsten Werte. Die spätere KI wird **diese Steckbriefe** sehen,
nie die Rohdaten — so bleiben auch Millionen Zeilen zusammenfassbar.

### Die Kandidaten-Landkarte

Dann vergleicht das Tool alle Spalten paarweise: Wo tauchen dieselben Werte
auf? Heraus kommt eine Landkarte möglicher Verknüpfungen — die Kundennummer
auf der Rechnung passt zum Kundenstamm, die Migrationstabelle aus dem Excel
passt zu den alten Kundennummern (Falle F5 wird damit erst findbar!).

Wichtig: Die Landkarte **urteilt nicht**. Sie enthält absichtlich auch
Zufalls-Echos — zwei Datumsspalten, die rein zufällig dieselben Werte
tragen, stehen genauso drin. Aussortieren ist Aufgabe der Sonden (M3) und
der Menschen. Und weil M2 gar keine Karteikarten anlegt, kann in dieser
Phase auch nichts fälschlich befördert werden: null Risiko, eingebaut.

Ehrlich bleibt die Karte auch bei ihren blinden Flecken: Beziehungen, die
nicht über gleiche Werte laufen (Postleitzahl-*Bereiche*, codierte
Hierarchie-Strings), stehen **nicht** drin — die muss später die KI finden,
und das wird eigens gemessen.

### Und die Prüfung aus M0?

Der komplette Scan lief gegen die Übungsfirma: Die führenden Nullen
überleben (T1), das schmutzige Excel wird mit Protokoll normalisiert (T9),
alle eingebauten wertbasierten Beziehungen stehen auf der Landkarte —
inklusive des Zufalls-Echos als Negativkontrolle (T6). Und: Der komplette
Zwischenspeicher darf jederzeit gelöscht werden — ein neuer Scan baut ihn
identisch wieder auf.

### M2 in einem Satz

Das Tool kann jetzt chaotische Quellen öffnen, ohne etwas kaputtzuputzen,
protokolliert jede Aufräum-Entscheidung als Beweis und zeichnet eine
ehrliche Landkarte möglicher Verknüpfungen — urteilen darf darüber erst
die nächste Stufe.

---

## Wie geht es weiter?

- **M3 — Die Sonden**: Automatische Stichproben prüfen die vermuteten
  Regeln gegen die Daten — noch immer ganz ohne KI, gegen handgeschriebene
  Karteikarten aus dem Antwortheft. *(Abschnitt folgt, wenn M3 gebaut ist.)*
- M4–M8 folgen danach: LLM-Verträge, Dokumente, Fragenfluss, Veralterung,
  Paketierung.
