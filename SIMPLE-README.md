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

## Wie geht es weiter?

- **M2 — Daten einlesen und vermessen**: Das Tool lernt, die chaotischen
  Quellen der Übungsfirma zu öffnen (Datenbanken, hässliches Excel, CSV)
  und jede Spalte zu vermessen. *(Abschnitt folgt, wenn M2 gebaut ist.)*
- M3–M8 folgen danach: Sonden (Probes), LLM-Verträge, Dokumente,
  Fragenfluss, Veralterung, Paketierung.
