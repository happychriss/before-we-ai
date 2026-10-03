# Before we AI — ich habe ein Tor vor die KI gebaut und es am Ende nicht gebraucht

*Ein Rückblick auf ein Projekt, das mit einer festen Überzeugung begann und mit
einer anderen endete. Entwurf für die Webseite, Stand 3. Oktober 2026.*

---

## Die Überzeugung, mit der alles anfing

Ich war mir sicher: **KI kann nicht KI bewerten.** Wer eine Antwort erzeugt hat
und sie danach selbst prüft, sieht das, was er sehen möchte, und übersieht den
Rest. Das gilt für Menschen, und ich sah keinen Grund, warum es für ein
Sprachmodell anders sein sollte.

Daraus folgte für mich ein klarer Auftrag. Bevor man eine KI auf fremde,
verstreute Unternehmensdaten loslässt – zwei ERP-Systeme, ein paar
Excel-Exporte, ein Ordner voller Richtlinien-PDFs –, braucht es eine Prüfung
*davor*. Ein Assessment. Am Ende sollte ein Sign-off stehen: Diese Daten sind
gesichtet, ihre Bedeutung ist geklärt, sie sind so annotiert, dass eine KI sie
verstehen kann. Erst dann darf sie antworten. Daher der Name: *Before we AI*.

Der Kern der Idee stand in einem Satz meiner ersten Konzeptnotiz: Zwischen
fragmentierten Daten und mächtiger, aber unzuverlässiger KI fehlt eine Schicht,
die festhält, **was man weiß, was man nur vermutet und was man nicht weiß.**

## Was ich gebaut habe

Ich habe diese Schicht gebaut, und zwar gründlich.

Jede Aussage über die Daten – „diese Tabelle ist das Hauptbuch", „diese Spalte
ist der Betrag in Landeswährung", „diese beiden Listen passen über die
Kundennummer zusammen" – wurde zu einem **Claim** mit einem von fünf Zuständen:
vorgeschlagen, durch einen Test gestützt, widerlegt, ungeklärt, vom Fachbereich
bestätigt. Dazu eine Regel, die nicht verhandelbar war: **Die KI darf nur
vorschlagen.** Befördern darf einen Claim nur eine deterministische Prüfung in
SQL oder ein Mensch mit Namen. Belege werden nur angehängt, nie überschrieben.
Was die Daten nicht entscheiden können, wird zur Rückfrage – niemals zu
Schweigen.

Am Ende stand ein Urteil pro Geschäftsfrage: bereit, bereit mit
Einschränkungen oder blockiert. Mein Leitsatz dafür: *Nicht die KI
zuverlässiger machen, sondern ihre Unzuverlässigkeit irrelevant.*

Das waren am Ende rund 16.000 Zeilen Code, knapp 900 Tests, eine eigene
Testlandschaft mit 32 versteckten Fehlern und ein Gerüst, auf das ich ehrlich
stolz war. Die harte Kennzahl hieß „False Promotion = 0": Kein einziger Claim
wurde je von der KI selbst befördert.

## Der Tag, an dem ich es gemessen habe

Irgendwann musste die Frage gestellt werden, die ich lange vor mir hergeschoben
hatte: Funktioniert das auf Daten, auf denen das Werkzeug nicht groß geworden
ist? Ich habe sie mit einem KI-Assistenten als skeptischem Gegenüber
durchgearbeitet, mit einer festen Disziplin: Vorhersagen aufschreiben und
einchecken, *bevor* etwas läuft, Lösungsschlüssel erst danach öffnen.

**Erste Messung, eine fremde Landschaft:** zehn Dokumente eines fiktiven
Schiffbauers, gebaut von jemand anderem. Frage: „Was kostet der Bau eines
Schiffs?" Mein Gerüst antwortete: *blockiert.* 0 von 46 Abhängigkeiten geklärt,
46 Entscheidungen für einen Menschen offen.

Das Urteil war nach seinen eigenen Regeln korrekt. Es war aber auch genau das,
was ein Werkzeug gesagt hätte, das immer Nein sagt. „False Promotion = 0"
erfüllt man auch, indem man nichts tut. Ich hatte eine Verbotsmaschine gebaut
und es Sicherheit genannt.

Dazu kam ein Befund, den niemand vorhergesagt hatte. Meine Regel schützte nur
in eine Richtung. Die KI konnte nichts befördern – aber sie durfte die Prüfung
auswählen, und damit konnte sie *verwerfen*. Fünfzehn offensichtlich richtige
Spalten wurden als „widerlegt" markiert, weil das Modell ihnen Prüfungen
zugeordnet hatte, die etwas anderes testeten. Die Stundentabelle galt als
falsch, weil Stunden mal Satz um ein paar Cent vom gerundeten Betrag abwich.

**Zweite Messung, die Kontrollgruppe:** Dieselben zehn Dateien, dieselbe
Frage, an ein aktuelles Sprachmodell – ohne Gerüst, ohne Regeln, ohne Hinweis,
dass Fehler versteckt sind. Zwei Minuten später lagen sechs Zahlen vor. Fünf
davon stimmten auf den Euro mit dem Lösungsschlüssel überein, die sechste wich
um 0,3 Prozent ab – und genau bei dieser hatte das Modell selbst dazugeschrieben,
dass es unsicher ist. Es hatte die doppelt gebuchte Rechnung gefunden, den
falsch herum gerechneten Wechselkurs, die Buchung auf dem falschen Schiff.

Die KI hatte die Frage beantwortet, die mein Tor nicht freigeben wollte.

## Der Versuch, es ohne KI zu retten

Mein erster Reflex war: Dann fehlt eben Fachwissen. Also bekam das Gerüst ein
**Grundlagendokument** – ein Word-Dokument mit Regeln, die ein Controller
unterschreiben würde: „Betrag in Hauswährung = Transaktionsbetrag × Kurs",
„jede Kostenzeile gehört zu einem bekannten Bau". Mit Toleranzklassen statt
Einzeltoleranzen, und geschrieben von einem Agenten, der keine einzige Datei
gesehen hatte. Die Maschine sollte prüfen, in wie vielen Zeilen eine Regel
gilt; die Ausnahmen wären die Befunde.

Das funktionierte erstaunlich gut – bis zu einer Stelle, die sich als der
eigentliche Knackpunkt herausstellte. **Um eine Regel anzuwenden, muss jemand
sagen, welche Spalte welche ist.** Welche der drei Betragsspalten ist der
„Transaktionsbetrag"? Das ist ein Urteil. Entweder fällt es ein Mensch, Spalte
für Spalte, oder ein Modell schlägt es vor.

Ich habe noch einen dritten Weg probiert: Die Maschine sucht selbst, welche
Spalten rechnerisch zusammenhängen. Auf Excel-Blättern, in denen alles in einer
Zeile steht, sah das glänzend aus. Auf realistischen ERP-Extrakten – Netto in
der einen Tabelle, Steuer in der anderen, Kurs in der dritten – fand sie
**einen einzigen** Zusammenhang in zwölf Tabellen.

## Die dritte Landschaft

Um mir nichts vorzumachen, habe ich eine dritte Testlandschaft bauen lassen,
bewusst unordentlich: eine kleine Landesgesellschaft mit eigenem ERP, die ihre
Daten ins Konzern-Warehouse liefert. Wareneingang, Rechnungsprüfung, manuelle
Ausbuchungen. Umstellung mitten im Jahr. Und vor allem: **kein Dokument, das
irgendeinen Fehler erklärt.**

Meine Vorhersage, vorher eingecheckt: Hier wird die KI danebenliegen, sich von
Lauf zu Lauf widersprechen und höchstens die Hälfte der Fehler finden.

Das Ergebnis: Drei unabhängige Läufe lieferten den Jahresendsaldo **auf den
Euro identisch und exakt richtig**, nannten dieselben neun Rechnungen und
fanden alle 18 eingebauten Fehler – einschließlich einer Ausbuchung mit
falschem Vorzeichen und eines Zahlendrehers über 36 Einheiten Landeswährung.
Mein Regelwerk mit handgeschriebener Zuordnung fand sieben davon klar; von zehn
Ausnahmen, die es meldete, war eine ein echter Fehler.

Von meinen zwölf Vorhersagen waren sieben falsch. Alle in dieselbe Richtung:
Ich hatte die KI unterschätzt und die Regeln überschätzt.

## Denkfehler oder Erkenntnis?

Beides, und es lohnt sich, die beiden auseinanderzuhalten.

**Der Denkfehler lag nicht im Misstrauen, sondern an der Stelle, an der ich es
eingebaut habe.** Ich wollte die KI aus der Herstellung des Kontextes
heraushalten: erst die Daten verstehen und absegnen, dann die KI fragen. Aber
„die Daten verstehen" ist selbst die Arbeit, um die es geht. Welche Tabelle ist
das Journal, was bedeutet diese Spalte, ist diese doppelte Rechnungsnummer ein
Fehler oder eine Teillieferung – das sind Urteile. Wer sie fällen will, ist
schon mittendrin. Es gibt kein „davor". Entweder ein Mensch arbeitet sich durch
jede einzelne Zuordnung, oder man vertraut der KI bereits beim Aufbau des
Kontextes, den man eigentlich prüfen wollte.

Ob das eine neue Einsicht ist, kann ich nicht beurteilen. Mir war sie nicht
klar, bis ich es gebaut hatte: Ein Assessment *vor* der KI lässt sich nicht
effizient machen, weil das Assessment die Aufgabe ist.

**Die Erkenntnis ist, dass der Kern meiner Überzeugung trotzdem stimmt.** Auf
der Schiffbau-Landschaft waren sich fünf Läufe auf den Euro einig – auch bei
der einen Zahl, die vom Lösungsschlüssel abwich. Wer fünf identische Antworten
sieht, hält das für eine Bestätigung. Es war keine. Übereinstimmung einer KI
mit sich selbst prüft nichts. Und in jedem einzelnen Experiment wusste ich nur
deshalb, dass die Antwort stimmt, weil ich den Lösungsschlüssel in der Hand
hatte. Ohne ihn liest sich eine richtige Antwort genauso überzeugend wie eine
falsche.

KI kann KI also tatsächlich nicht bewerten. Nur folgt daraus nicht, dass man
ein Tor davorstellen muss.

## Was bleibt

Die Frage hat sich verschoben. Sie lautet nicht mehr: *Sind meine Daten bereit
für die KI?* Sie lautet: **Kann jemand diese Antwort unterschreiben?**

Dafür taugen Teile von dem, was ich gebaut habe, überraschend gut – nur in
umgekehrter Reihenfolge:

1. **Die KI antwortet.** Darin ist sie inzwischen besser, als mein Gerüst im
   Erlauben war.
2. **Ihre Korrekturen werden einzeln nachgeprüft.** Jede Korrektur ist eine
   Behauptung: „Buchung 138 ist ein Duplikat von 34." Das kann eine feste
   Abfrage belegen oder widerlegen. Auf der Schiffbau-Landschaft waren zwei von
   fünf Korrekturen allein durch die Daten belegt, drei stützten sich auf einen
   Satz, der wörtlich im genannten Dokument stehen musste. Eine absichtlich
   verfälschte Antwort flog auf.
3. **Unterschriebene Regeln laufen über das Ergebnis.** Sie finden, was die KI
   weggelassen hat – etwa, dass Stundenzettel und Kostenjournal bei einem
   Schiff noch immer nicht zusammenpassen.

Keiner dieser Schritte sagt, dass die Zahl stimmt. Zusammen sagen sie, worauf
sie steht und wo sie noch nicht aufgeht. Das ist ein Sign-off – nur nicht für
die Daten, sondern für die Antwort.

Der Mensch bleibt dabei in der Verantwortung, aber an einer anderen Stelle.
Statt 46 Einzelfragen zu beantworten, gibt er einmal Regeln frei und liest am
Ende, worauf sich eine Zahl stützt. Das ist weniger Arbeit, und sie liegt
dort, wo ein Mensch etwas beitragen kann.

## Was ich nicht behaupte

Ein Projekt, dessen Anspruch es war, zu sagen, was man nicht weiß, sollte das
auch über sich selbst tun.

- **Alle drei Landschaften sind synthetisch.** Die beiden schwierigen wurden
  von einem Sprachmodell gebaut und von einem Modell derselben Familie gelöst.
  Wer „realistische Fehler" einbauen soll, baut die Fehler ein, an die ein
  Modell denkt – und genau die sucht ein Modell auch. Echtes Durcheinander
  entsteht nicht aus einer Liste.
- **Sie sind klein.** Ein paar tausend Zeilen kann ein Modell vollständig
  lesen. Ein echtes Geschäftsjahr ist hundert- bis tausendmal größer.
- **Den Kipppunkt habe ich nicht gemessen, nur seine eine Seite.** Ich weiß,
  dass das aktuelle Modell es kann. Ob ein Modell von vor einem Jahr gescheitert
  wäre und mein Tor damals richtig war, habe ich nie geprüft. Mein Eindruck
  ist, dass sich hier in kurzer Zeit etwas Grundlegendes verschoben hat.
  Belegt ist das nicht.

## Schluss

Ich habe ein Tor gebaut, um die KI von Daten fernzuhalten, die sie nicht
versteht. Dann habe ich gemessen und festgestellt, dass sie die Daten besser
versteht als mein Tor – und dass sich das Verstehen gar nicht von der Antwort
trennen lässt.

War die Arbeit umsonst? Ich glaube nicht. Ohne das Gerüst hätte ich nie
gewusst, *wo genau* mein Gedanke bricht: nicht beim Misstrauen gegenüber der
KI, sondern bei der Vorstellung, man könne den Kontext ohne sie herstellen. Und
ich hätte nicht die eine Sache behalten, die jede Messung überlebt hat: dass
man einer Zahl nicht ansieht, ob sie stimmt, und dass fünf gleiche Antworten
kein Beweis sind.

*Before we AI* war die falsche Präposition. Die Prüfung gehört nicht davor. Sie
gehört danach – und sie braucht weiterhin jemanden, der unterschreibt.

---

*Der vollständige Stand – Code, die drei Testlandschaften, alle Vorhersagen
samt den falschen, und die Antworten der KI im Wortlaut – liegt offen auf
GitHub: `happychriss/before-we-ai`, Zweig `case-study`. Die Belege zu jeder
Zahl in diesem Text stehen in `docs/case-study-notes.md`.*
