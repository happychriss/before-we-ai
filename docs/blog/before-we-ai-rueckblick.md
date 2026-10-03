# Before we AI — warum mein Tor vor der KI an der falschen Stelle stand

*Entwurf für die Webseite, Stand 4. Oktober 2026. Die ausführliche Fassung
liegt daneben: `before-we-ai-rueckblick-lang.md`.*

---

Ich war überzeugt: **KI kann nicht KI bewerten.** Wer eine Antwort erzeugt und
sie selbst prüft, sieht, was er sehen möchte. Also braucht es vor jeder
KI-Analyse ein Assessment der Daten, mit einem Sign-off am Ende: gesichtet,
geklärt, so annotiert, dass eine KI sie versteht. Erst dann darf sie
antworten. Daher der Name.

Ich habe das gebaut. Jede Aussage über die Daten wurde ein *Claim* mit einem
Status. Die KI durfte nur vorschlagen; befördern durfte nur eine feste Prüfung
oder ein Mensch. Rund 16.000 Zeilen Code, knapp 900 Tests, und eine Kennzahl,
auf die ich stolz war: Nie hat die KI einen Claim selbst befördert.

## Dann habe ich gemessen

Auf fremden Testdaten – zehn Dokumente eines fiktiven Schiffbauers –
antwortete mein Gerüst auf die Frage nach den Baukosten: *blockiert*. 0 von 46
Punkten geklärt, 46 Entscheidungen für einen Menschen. Korrekt nach seinen
eigenen Regeln, und genau das, was auch eine Maschine sagt, die immer Nein
sagt.

Dieselben Dateien, dieselbe Frage, an ein aktuelles Sprachmodell ohne jedes
Gerüst: nach zwei Minuten sechs Zahlen, fünf davon auf den Euro richtig. Auf
einer dritten, bewusst unordentlichen Landschaft, in der kein Dokument einen
Fehler erklärt, lieferten drei Läufe den Jahresendsaldo exakt und fanden alle
18 eingebauten Fehler. Mein Regelwerk fand sieben. Von meinen zwölf vorher
festgeschriebenen Vorhersagen waren sieben falsch – alle in dieselbe Richtung.

## Was ich daraus gelernt habe

**Erstens: Es gibt kein „davor".** Ich wollte die KI aus dem Aufbau des
Kontextes heraushalten. Aber die Daten zu verstehen *ist* die Aufgabe: Welche
Tabelle ist das Journal, was bedeutet diese Spalte, ist das ein Duplikat oder
eine Teillieferung? Wer das klären will, ist schon mittendrin. Entweder ein
Mensch entscheidet jede Zuordnung einzeln, oder man vertraut der KI bereits
beim Herstellen des Kontextes, den man eigentlich prüfen wollte. Und auf meinen
Testdaten war sie darin besser und schneller als jedes Regelwerk, das ich von
Hand hätte aufstellen können.

**Zweitens: Mein Misstrauen war trotzdem berechtigt.** Fünf Läufe waren sich
auf den Euro einig – auch bei der einen Zahl, die danebenlag. Übereinstimmung
einer KI mit sich selbst beweist nichts. Dass die Antworten stimmten, wusste
ich nur, weil ich den Lösungsschlüssel hatte. Die Prüfung gehört also nicht
vor die Antwort, sondern dahinter: Jede Korrektur der KI lässt sich als
Behauptung nachrechnen, und am Ende unterschreibt jemand die Antwort, nicht die
Daten.

**Drittens, und das betrifft mich selbst: Ich habe der KI den Weg überlassen.**
Ich habe das Projekt mit ihr als Sparringspartner entwickelt, und genau das war
ein Teil des Problems. Mit einer KI einen Weg zu *verfeinern* und ihn gemeinsam
zu gehen, ist großartig. Den Weg mit ihr zu *suchen*, ist gefährlich. Es ist
wie bei einer Wanderung: Die Route plane ich selbst. Dann kann ich sie mit
jemandem gehen und unterwegs korrigieren. Plane ich sie nicht, laufe ich
begeistert los – und übersehe den Elefanten im Raum.

Mein Elefant war, dass es inzwischen effizienter ist, Kontext mit KI zu
erarbeiten und zu prüfen, als Regeln von Hand aufzustellen. Ich habe monatelang
an einer Lösung für ein Problem gebaut, ohne vorher festzulegen, was am Ende
herauskommen soll und woran ich erkenne, ob es stimmt. Das hätte ich wissen
müssen, bevor die erste Zeile Code entstand.

## Was „Before we AI" jetzt heißt

Die Datenprüfung ist ein *After the AI* geworden. Der Name behält trotzdem
seinen Sinn, nur einen anderen: Bevor ich mit KI arbeite, mache ich meine
Hausaufgaben. Ich weiß, was ich bauen will, wie der Ablauf aussieht, was
herauskommen soll – zumindest zum großen Teil – und wie ich das Ergebnis
überprüfe. Das ist keine Aufgabe, die man delegiert.

Eine Einschränkung gehört dazu: Meine Testdaten waren synthetisch, klein, und
zwei der drei Landschaften hat ein Sprachmodell gebaut, bevor ein Modell
derselben Familie sie löste. Auf echtem Durcheinander habe ich das nicht
gemessen.

Ich habe ein Tor gebaut, um die KI von Daten fernzuhalten, die sie nicht
versteht. Sie verstand sie besser als mein Tor. Was ich vorher hätte klären
müssen, waren nicht die Daten. Es war mein eigener Plan.

---

*Code, Testdaten, alle Vorhersagen samt den falschen und die Antworten der KI
im Wortlaut: GitHub, `happychriss/before-we-ai`, Zweig `case-study`.*
