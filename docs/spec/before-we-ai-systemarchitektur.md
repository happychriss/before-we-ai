# before-we-ai – Systemarchitektur (Grobentwurf, Handoff-Dokument)
*Zielbild: Laptop-Installation, Datenbank verbinden, Dateien ablegen, Scan drücken. CLI-first, UI später. Dieses Dokument ist die Bauvorlage für die Implementierung.*
*Verweise: Validierungsbasis in `before-we-ai-testdatensatz-finance-anforderungen.md` (Zielfragen Z1–Z4, Fallen F1–F29, Kennzahlen); Produkt-Rationale in `before-we-ai-konzept-zusammenfassung.md`.*

## 1. Leitentscheidungen

**Ein Python-Paket, keine Services.** Installation via `pipx install before-we-ai` (bzw. `uv tool install`). Keine Server-Datenbank, kein Docker, kein Orchestrator. Ein Projekt ist ein Verzeichnis, idealerweise ein Git-Repo.

**Dateien sind die Quelle der Wahrheit.** Claims, Evidenzen, Fragenkarten, Profile liegen als YAML/JSON/Markdown im Projektordner. Alles andere ist ableitbar. Daraus folgt die wichtigste Invariante des Systems: **`cache/` ist jederzeit löschbar und vollständig rekonstruierbar.** Der DuckDB-Cache, gerenderte Reports, LLM-Logs — alles Derivat.

**DuckDB ist die einzige Ausführungsmaschine.** Es attached Postgres/MySQL, liest CSV/Parquet direkt, dient als Profiling- und Sonden-Engine und liefert per FTS-Extension die Dokumentsuche. Kein Vektor-Store, keine Graph-DB (der Graph wird aus Datei-Querverweisen gerendert), kein LangChain (stattdessen vier dünne, typisierte Vertragsfunktionen).

**Evidenz ist append-only.** Evidence Records werden nie verändert oder gelöscht, nur ergänzt und ggf. als stale markiert.

**LLM nur über die vier Verträge (V1–V4).** Jeder Aufruf: zugeschnittener Kontext, Pydantic-validierte Antwort, ein Retry, vollständiges Logging nach `cache/llm_log/`. Es existiert ein **Stub-Modus** (`--offline`), in dem die Verträge aus Fixture-Antworten bedient werden — Grundlage für deterministische Tests und CI.

## 2. Projektlayout auf der Platte (der eigentliche Datenvertrag)

```
myproject/
  before-ai.yaml        # Quellen, Modell-Tiers, Toleranz-Overrides
  sources/            # abgelegte Dateien (csv, xlsx, pdf, txt)
  claims/             # ein YAML pro Claim (5 Status, Evidenz-Referenzen)
  evidence/           # append-only: Sondenergebnisse, Anker, Bestätigungen
  questions/          # Fragenkarten (Frage, SQL, Ergebnisreferenz, Stückliste)
  profiles/           # Spaltenprofile, Kandidatenmatrix (JSON + MD)
  reports/            # gerenderte MD/HTML-Reports (Status, Gap-Lastliste)
  cache/              # DISPOSABLE: duckdb-Datei, normalisierte Views,
                      # Fingerprints, Doc-Chunks, llm_log/
```

IDs sind ULIDs; Querverweise laufen über IDs. `before-ai check` prüft referenzielle Integrität (keine hängenden Referenzen) — der Preis dafür, dass keine Datenbank diese Arbeit macht.

## 3. Komponenten (Python-Module)

**`model` — der epistemische Kern.** Pydantic-Modelle (Source, ColumnProfile, Claim, EvidenceRecord mit den fünf Evidenztypen, Probe, QuestionCard, ConceptClaim, **RoleBindingClaim**) plus Zustandsmaschine und Promotionsregeln als reine Funktionen. Keine IO-Abhängigkeit. Vollständig unit-testbar. Hier lebt: Konflikt erzwingt `unresolved`, nur Sonde/Mensch promoted, KI erzeugt nur `inferred`. Claims können **Abhängigkeiten** deklarieren: Eine Sonde läuft erst, wenn vorausgesetzte Claims mindestens `technically tested` sind (z. B. Nebenbuch=Hauptbuch erst nach Bindung beider Seiten). Auflösung per topologischer Sortierung — ein Mini-Scheduler, kein Workflow-System.

**`store` — Dateirepository.** Lesen/Schreiben der YAML-Objekte, In-Memory-Index beim Laden (Projektgröße erlaubt das), optionale Git-Checkpoints via `git`-CLI (weiche Abhängigkeit, kein Zwang).

**`sources` — Anbindung & Normalisierung.** DuckDB-Attach für Postgres/MySQL; Dateien aus `sources/`. Hässliches Excel geht **nicht** direkt durch DuckDB, sondern durch einen Python-Vorleser (openpyxl): verbundene Header auflösen, Dezimalkommas, Typen als Text bewahren, Ergebnis als Parquet in den Cache. Jede Normalisierungsentscheidung (Trim, Cast, Null-Kanon) wird als deklarative Evidenz protokolliert. Fingerprints (Zeilenzahl, Schema-Hash, Max-Timestamp) entstehen hier.

**`profile` — Vermessung & Kandidatenmatrix.** Spaltenstatistik per SQL (Kardinalität, Null-Quote, Muster, Top-k). Kandidatenmatrix zweistufig: Vorfilter über Typ-/Musterkompatibilität, dann exakte Overlap-Zählung auf Distinct-Werten (bei Laptop-Skala vertretbar); MinHash-Sketches (datasketch) nur als Optimierung, wenn nötig.

**`probes` — Sonden-Engine.** Jinja2-SQL-Templates: anti_join, cardinality, coverage, duplicate, grain, attribute_contradiction, reconciliation; aus der Finanz-Domäne erzwungen zusätzlich validity_join, range_join, decode. Verdikt-Funktionen deterministisch in Python, Toleranzen als Template-Defaults (Overrides nur in `before-ai.yaml`, nie im Modell). Jeder Lauf erzeugt einen EvidenceRecord mit gerendertem SQL, Zeitpunkt, Rohergebnis, Verdikt und den Fingerprints der beteiligten Tabellen.

Zweite Sondenklasse: **Invariantensonden** — landschafts- statt claim-gebunden. Sie kodieren Erhaltungssätze der Domäne (Soll=Haben je Beleg, Nebenbuch=Hauptbuch, IC-Symmetrie) und sind gegen **Rollen** formuliert (journal, amount, doc_ref …) statt gegen konkrete Spalten. Die Rollenbesetzung eines Projekts ist selbst ein RoleBindingClaim: KI schlägt Kandidaten-Bindungen vor (Frontier-Aufgabe), die Invariante entscheidet — eine bestandene Invariante stützt Bindung **und** Datenkonsistenz zugleich; scheitern alle Kandidaten, ist das Ergebnis `unresolved` mit Fachfrage, nie stilles Verwerfen. Rollenlisten pro Domäne sind flaches, kuratiertes YAML (Finance: ~8 Rollen) — bewusst keine Ontologie, kein Plugin-Framework (Regel der Drei: Abstraktion erst ab der dritten Domäne).

**`engine` — Epistemik-Laufzeit.** Wendet Promotionsregeln auf Claims an, erkennt Konflikte, propagiert Staleness (Fingerprint-Vergleich → Flags bis in Fragenkarten), berechnet die Gap-Lastliste (ungeprüfte Annahmen gewichtet nach abhängigen Fragen).

**`llm` — Vertragsschicht.** Vier Funktionen (V1 Hypothesen, V2 Sondenbindung, V3 Dokumenteninterpretation, V4 SQL-Generierung) mit festen Input-Buildern (Profile statt Daten, <25k Tokens) und Output-Schemas. Anthropic-SDK direkt; Modell-Tiers in `before-ai.yaml` (V1/V3 Frontier, V2/V4 Mittelklasse — Ausnahme: die **Rollenbindung** für Invariantensonden ist eine Suchaufgabe mit Fachverständnis und läuft in der Frontier-Klasse, mit der Kandidatensuche der Invariante als Netz darunter). Stub-Modus liest Antworten aus Fixtures.

**`docs` — Dokumentpipeline.** PyMuPDF für Text+Layout, Chunking mit Positionsankern, DuckDB-FTS als Retrieval. V3 chunkweise; Zitat-Validierung per String-Match gegen den Chunk.

**Nutzeraussagen als Quellenart.** `before-ai tell "…"` nimmt freies Hintergrundwissen entgegen („Geschäftsjahr Mai–April", „nur Apotheken und Großhändler"). Die Aussage wird **wörtlich** als testimoniale Evidenz gespeichert (Autor, Datum); V3 strukturiert sie in Claim-Kandidaten (`inferred`). Danach **Spiegel-Schleife**: Das System spiegelt seine Interpretation inklusive explizitem **Geltungsbereich** zurück (V3-Pflichtfeld `scope`: Gesellschaft, Zeitraum, Segment — „gilt für: alle Gesellschaften?"); erst die Bestätigung der Spiegelung hebt auf `business-confirmed`. Aussagen ohne strukturierbaren Claim-Typ werden als Notiz geparkt (FTS-durchsuchbar, nicht tragfähig). Testimoniale Claims sind sondierbar wie alle anderen (widersprechende Sondenbefunde ziehen sie auf `unresolved`) — das ist zugleich ihr einziges Verfallsdatum, da sie keinen Daten-Fingerprint für Staleness haben.

**`sql` — Fragenfluss.** sqlglot: Parse, Subset-Prüfung, Assumption Capture (Joins und claim-pflichtige Filter extrahieren, gegen Claim-Bestand matchen, Fehlendes als `inferred` materialisieren). Ausführung gegen DuckDB, Ergebnis in die Fragenkarte.

**`cli` + `report` — Bedienoberfläche der ersten Ausbaustufe.** Typer-CLI, 1:1 auf die Phasen abgebildet: `init`, `scan` (Phase 0–1), `hypothesize` (2), `probe` (3), `ask "…"` (4), `tell "…"` (Hintergrundwissen als Nutzeraussage), `confirm <claim>` (5), `status`, `check`, `report`, `replay --target <conn>`. Reports als Markdown (Claim-Übersicht, epistemische Stückliste je Frage, Gap-Lastliste); optional später `serve` als read-only-Viewer (FastAPI + statisch).

## 4. Bewusste Nicht-Ziele

Kein Scheduler/Monitoring, kein Multi-User, keine Rechteverwaltung, kein Dashboard-Builder, keine Vektor-Datenbank, kein eigener Query-Optimizer. Enterprise-Quellen jenseits Postgres/MySQL (SAP, Oracle, MSSQL) zunächst nur über den Datei-Dump-Weg — das ist kein Mangel, sondern das Einsatzmuster („Dateien dumpen, Scan drücken").

## 5. Milestone-Plan mit Validierung (jeder Schritt einzeln abnehmbar)

**M0 Fixture-Korpus** (spezifiziert): Generator + `expected_verdicts.yaml`; Selbstprüfung rechnet Ground-Truth-Zahlen aus den generierten Daten nach. **M1 Kern:** `model` + `store` + Zustandsmaschine; Abnahme: Unit-Tests aller Promotionspfade inkl. Konflikt→unresolved. **M2 Ingestion & Profiling:** Abnahme gegen Korpus: T1/T9 überleben die Normalisierung, Kandidatenmatrix enthält alle wertbasierten Seeds inkl. Negativkontrolle T6. **M3 Sonden & Engine — ohne jedes LLM:** Sonden laufen gegen **handgeschriebene Claims aus der Ground Truth**; Abnahme: erwartete Verdikte T1–T6, T11, T12; False-Promotion = 0. Damit ist der epistemische Kern validiert, bevor ein Modell beteiligt ist. **M4 V1+V2:** Hypothesen und Sondenbindung, Logging, Stub-Modus; Abnahme: Seeded-Recall inkl. T7, CI läuft offline deterministisch. **M5 Dokumente & V3:** Reconciliation mit Mehrfach-Anker-Regel; Abnahme: T8-Negativfälle, echtes PDF. **M6 Fragenfluss & V4:** Assumption Capture, Konzept-Claims, Stückliste, Gap-Report; Abnahme: T5 lazy Claim, T10, Lastlisten-Inhalt. **M7 Staleness & Replay:** Korpus-Variante per Seed mutieren → Flags propagieren; Sondensuite gegen „Prod"-Kopie. **M8 Packaging & Quickstart:** pipx-Installation, 10-Minuten-Walkthrough am Korpus; optional `serve`-Viewer.

## 6. Technologie-Bilanz

Bestehendes: DuckDB, sqlglot, Pydantic, Jinja2, Typer, PyMuPDF, openpyxl, pytest, Anthropic SDK, optional datasketch. Eigenentwicklung (weil es das nicht gibt — jeweils per Korpus validierbar): epistemischer Kern (Zustandsmaschine, Promotionsordnung, Stückliste, Staleness), Sonden-Template-Bibliothek mit Verdikt-Funktionen, Assumption Capture, Reconciliation-Kandidatensuche.

## 7. Offene Architekturrisiken (ehrlich)

Referenzielle Integrität über YAML-Dateien ist handgebaut (`before-ai check` ist Pflicht, nicht Kür). Die Kandidatenmatrix ist quadratisch über Spaltenpaare — bei ~30 Tabellen irrelevant, ein hartes Limit mit Warnung gehört trotzdem hinein. Excel-Ingestion ist ein eigenes kleines Projekt (T9 existiert genau dafür). Der Stub-Modus muss von Anfang an existieren, sonst sind M4–M6 nicht reproduzierbar testbar. Und: Die CLI darf nicht zum Framework wuchern — jedes Kommando entspricht einer Phase, sonst nichts.
