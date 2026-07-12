# Onboarding workflow — design (owner-aligned 2026-07-12, not yet built)

The spec's Zielbild ("Datenbank verbinden, Dateien ablegen, Scan drücken")
as a concrete first-run flow:

**init project → pick a bundled role pack or draft one (LLM-assisted,
human-curated) → drop files into `sources/` → scan.**

Three pieces, found as gaps during the M4 validation session. Timing: pieces
1+2 at **M5 kickoff** (both change prompt bytes → one fixture re-record
instead of two); piece 3 post-M5; the assembled workflow + quickstart is
**M8** territory.

## 1. Sources discovery — `discover(root)`

Today `init_project()` writes `sources: []` and a human hand-authors every
entry; the `sources/` project dir exists ("dropped files") but nothing reads
it. `discover(root)` walks it, infers `kind` from the suffix
(`.duckdb`/`.csv`/`.xlsx`/`.pdf`), and **merges** new entries into
`before-ai.yaml`:

- merge, never overwrite — a hand-tuned entry wins; re-running adds only
  what's new (same idempotence contract as `scan`)
- report what was skipped (unknown extension, unreadable) — never silent
- never touch entries pointing outside `sources/` (connected databases)
- `scan(root)` calls it first → "drop files, press scan" becomes literally true

A dropped PDF still yields only a fingerprint until the M5 document pipeline
lands — but it becomes *visible* in the source list, which beats today's
silent absence.

## 2. Bundled role packs

Ship curated per-domain packs as package data: `before_we_ai/roles/finance.yaml`
(content = today's test fixture `src/tests/fixtures/roles_finance.yaml`).
Config `roles_file: finance` resolves to the bundled pack; an explicit path
overrides. Flat YAML, no plugin framework (Regel der Drei). Shipped packs
must pass the same leakage tripwire as prompts. Tests keep pointing at the
fixture until the next fixture re-record (byte-identical content anyway).

## 3. Role-pack drafting (LLM contract, post-M5)

"Draft a role pack for domain X" — a small V-contract of the standard shape
(deterministic input, `RoleSet` schema, one repair-tier retry, full logging).
The system prompt is the **authoring questionnaire**:

1. **Laws first**: what must be true in ANY correctly-run system of this
   domain, vendor-independent? (Finance: debits=credits per document;
   subledger reconciles to control account; IC legs mirror.) One law = one
   invariant probe — a new law also needs a new SQL template (code, not YAML).
2. **Extract the nouns** each law quantifies over — those are the roles,
   nothing else is. A role no invariant consumes is prompt noise. (The 8
   finance roles ↔ 3 invariant templates, zero leftovers.)
3. **New-hire test** per definition: could an analyst who has never seen
   these systems point at the right column using only this sentence?
   Structural marks (granularity, signedness, grouping behavior), never
   vendor names.
4. **Leakage test**: nothing that exists only in one landscape — no system
   names, table names, example values. (Corpus world: teach-to-test; real
   world: anchoring on one system blinds the model to shadow copies.)
5. **Falsifiability** per role: what makes a wrong candidate FAIL? No
   answer → not a role yet. Definitions stay loose enough to invite
   competing candidates — the invariants run the election (F27 pattern).

**GUARDRAIL**: a generated pack is a *draft a human curates*, never silently
consumed. A too-strict law is self-policing (everything fails → Fachfragen);
a too-**loose** law is the one path to false confidence — an invariant that
trivially passes promotes role bindings on evidence that tests nothing.
Pack authorship ends with a person signing off, like every
`business-confirmed` elsewhere.
