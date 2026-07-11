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

## Wie geht es weiter?

- **M1 — Der epistemische Kern**: das Gedächtnis des Tools. Was ist eine
  Behauptung (Claim), wann darf sie befördert werden, wann bleibt sie
  Verdacht? *(Abschnitt folgt, wenn M1 gebaut ist.)*
- M2–M8 folgen danach: Daten einlesen, Sonden (Probes), LLM-Verträge,
  Dokumente, Fragenfluss, Veralterung, Paketierung.
