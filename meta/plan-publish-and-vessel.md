# Active plan — make the repository runnable, then read the vessel corpus

> **Read this file first after a compaction, together with `meta/memory.md`.**
> It is the executable plan for the work in flight. When a phase is done, tick
> it here; when the whole plan is done, delete this file and leave the durable
> facts in their homes. Nothing here is confirmed design — that is
> `docs/architecture.md`.

**Goal.** A stranger can clone the repository and run it; both landscapes live
in one structure that makes a third cheap; then Run A — the vessel corpus is
ingested and profiled for the first time.

**Why this order.** Everything after Run A rests on evidence from a landscape
the tool did not grow up in. Building further before that raises the cost of
finding out the base was wrong. Verified this session: the suite is green
(873 passed) and the environment works, so nothing here is blocked.

---

## Decisions already taken (do not re-litigate)

- **License: Apache-2.0** (owner decision, this session).
- **`pyproject.toml` moves to the repo root**, src-layout via `package-dir`
  (owner decision, this session).
- **Both corpora are committed openly.** No encryption, no private repo, no
  submodule for the answer keys. Reason: `corpus-vessel/generate_corpus.py`
  contains the full trap table at line 1143, so sealing `ground-truth/`
  protects nothing while the generator stays in the repo — and it must stay,
  or the corpus is not reproducible.
- **Blindness is a reading rule, not cryptography.** The key protects against
  *tuning to it*. The owner cannot be blind to a corpus he owns; the
  implementer and any agent can. Rule already in auto mode, extended here:
  never read, grep, quote or summarize `corpora/vessel/answer-key/**` **or**
  `corpora/vessel/generator/generate_corpus.py` — that file *is* the key.
- **Pre-registration replaces sealing.** Before any scored run, write the
  predictions and the pass/fail rule into a committed file. That is the part
  that carries the value.
- **What is public, decided this session.** The vessel source documents stay
  public — they are what lets a stranger reproduce Run A, and without them the
  owner remains the only party who can verify anything. The *sales* half of
  the thinking records comes out. The *honest* half is promoted into the
  README rather than buried in a draft. Detail in Phase 3, item 7.

## Standing constraints that apply to every phase

- **Never `git add -A`.** These paths are another workstream's uncommitted
  work and must not be staged: `src/before_we_ai/guide_builder/`,
  `src/tests/unit/test_guide_builder.py`,
  `src/tests/unit/test_guide_builder_landscape.py`, and the working-tree edits
  to `src/before_we_ai/llm/config.py` (the `guide_builder` model tier) and
  `src/pyproject.toml` (the `before_we_ai.guide_builder` package entry).
  **Committing that pyproject line without the code breaks every fresh
  install** — verified: the committed file does not contain it today, and
  declared packages currently match disk exactly.
- `corpus-vessel/` moves in Phase 2 by explicit owner instruction this
  session. `guide_builder/` is **not** covered by that and stays untouched.
- Corpus bytes are frozen. No file under a landscape's `data/` may change —
  Phase 2 adds a checksum test that proves it.
- No live LLM calls without an explicit owner go-ahead. Everything in this
  plan is offline.
- English everywhere except `docs/spec/`, which is owner-edit-only.

---

## Phase 1 — a repository a stranger can run

1. **`LICENSE`** — Apache-2.0 text, plus the year and copyright holder line.
2. **Move `src/pyproject.toml` → `pyproject.toml`** with
   `[tool.setuptools] package-dir = {"" = "src"}` and the package list
   unchanged. Update every place that says "install from `src/`":
   `docs/architecture.md` (~:1606), `meta/project-setup.md`,
   `meta/memory.md:38`, `validation/scripts/_env.sh`, `CLAUDE.md`.
3. **Pin what determinism rests on.** `duckdb` becomes an exact pin (the FTS
   extension is built per DuckDB version — the dev image carries
   `~/.duckdb/extensions/v1.5.4/`). Add `requirements.lock` for CI and Docker;
   `pyproject.toml` keeps ranges for library users.
4. **`scripts/bootstrap.sh`** — the one setup command, idempotent:
   create `.venv`, `pip install -e ".[dev]"`, run `INSTALL fts` once (needs
   network), then verify by running the unit lane. Must fail loudly with the
   exact fix if `INSTALL fts` cannot reach the network.
5. **README quickstart** — clone, bootstrap, run the suite, run the
   walkthrough. Include the FTS note. Point at `validation/README.md`: it is a
   deterministic, offline, API-key-free guided tour of a landscape with 32
   seeded errors, and it is currently invisible from the front page.
6. **`Dockerfile` + `compose.yaml`** at the root: python 3.13-slim, the lock
   file, `INSTALL fts` baked in at build time so the image is offline-ready.
7. **`.devcontainer/devcontainer.json`** referencing that same Dockerfile.
   This makes the owner's VS Code setup reproducible and is inert for everyone
   else — it only activates if someone opens the repo in VS Code and chooses
   "reopen in container". It is not imposed on any user.
8. **`.github/workflows/ci.yml`**, two jobs, both offline, no API key:
   - *fresh-clone*: ubuntu-latest, no container, runs exactly the README
     commands. This is the reproducibility test — if it goes red, the README
     lies.
   - *suite*: inside the Docker image, full `pytest -q`.
   Matrix on Python 3.11 (declared floor) and 3.13. If a fixture hash differs
   between interpreters, that is a determinism hole worth finding now.

9. **Pre-publication scan — a gate, not a hope.** Both landscapes' `data/`
   assert they are fully fictional; nobody has checked that with a tool. Scan
   for real company names, real people, real email addresses, real VAT and tax
   IDs, and anything that looks copied from an actual customer document rather
   than generated. Run it over the vessel documents (xlsx and pdf text) and
   the finance corpus. Ten minutes, and it runs before the first push, not
   after.

**Acceptance:** the fresh-clone CI job is green, `pip install -e .` works from
the clone root, and the pre-publication scan is clean.

## Phase 2 — one home for landscapes

Split the harness code from the landscape data. Code stays in `src/`;
landscapes become pure data.

```
corpora/
  README.md                  # what a landscape is; how to add one
  finance/
    manifest.yaml
    data/                    # moved from src/corpus/data — bytes unchanged
    generator/               # from src/raw-training-data + corpus/generator_spec
    answer-key/              # expected_verdicts.yaml, trap classes
  vessel/
    manifest.yaml
    data/                    # the 10 business documents
    generator/generate_corpus.py     # DO NOT READ — contains the key
    guide/simulated-domain-guide.yaml
    answer-key/TRAPS_AND_ANSWER_KEY.md   # DO NOT READ
src/corpus/                  # harness only: invariant checkers, report builder
```

1. **`manifest.yaml` per landscape** — name, domain, `frozen`, seed, which
   guide to use, the source list (name/kind/location), where the answer key
   is, which traps are held out. This replaces the same facts as they are
   hardcoded today in four places: the `SOURCES` list in
   `tests/corpus_driven/test_check_verdicts.py`, the PDF list in
   `tests/corpus_driven/fixture_registry.py`, `CORPUS = parents[2]/…` in every
   corpus test, and the source block in the walkthrough's `before-ai.yaml`.
2. **A resolver** so nothing hardcodes a path again — `corpora.load("vessel")`
   returns the manifest and resolved paths. Test-side only; the product
   package still never imports corpus code.
3. **Vessel first, finance second.** Vessel is 296 KB and nothing depends on
   it, so it proves the layout before the frozen one moves.
4. **Freeze proof:** before moving anything, write a test pinning the sha256
   of every file under `finance/data/`. The move must not change one byte.
5. **Fixture rename** `__corpus` → `__finance` in `tests/fixtures/llm/`. Safe:
   the drift guard hashes the built input and the system prompt, not the file
   name. `fixture_registry.py`'s escape guard keeps the two sides honest.
6. **`_env.sh`** should find the venv rather than assume `$BW_REPO/.venv`.

**Acceptance:** full suite green, corpus checksums unchanged, and
`corpora/README.md` describes adding a third landscape in under a page.

## Phase 3 — clean the history, keep the lessons

Rule: a historical file is deleted only after its lesson has a home. Lessons
go to `meta/conventions.md` (rules), `docs/architecture.md` (confirmed
design), or `docs/seeded-recall.md` (measurement).

1. **Record the scorer defect — highest value item in this phase.** Measured
   this session against `tests/eval/seeded_recall.py`:
   - 23 of 25 in-scope matchers are keyed to physical corpus identifiers
     (`de_erp__orders`, `fx_rates`, `crm_activities`); only F15 and F25 use
     generic wording. Point the tool at other data and the number falls
     because the words changed, not because the tool got worse.
   - **11 hand-written claims, every statement false or vacuous, score
     25/25.** The matcher is a lowercased substring test over statement,
     params and binding; it never reads what a claim asserts.
   - `BLIND_1/2/3` are hard-coded `scope="blind"` and always print
     `out of scope` — the blind traps are in no automated measurement at all.
   Home: `docs/seeded-recall.md`, in the "how to read the number" section.
   The lesson for `meta/conventions.md`: *the project's own rule "test
   heuristics by mutation" was never applied to the scorer* — a metric needs
   a negative control, the same way a law needs a violated fixture.
2. **`meta/memory.md` — remove history, keep rules.** The file is declared
   forward-looking, and two blocks are narrative:
   - "M5 kickoff batch — ALL FIVE DONE" — keep two rules and drop the story:
     *derive what is a pure function of something we already hold instead of
     asking the model for it*, and *leniency without a trace is the
     too-loose-law failure — normalize, but record the correction*.
   - the deleted-branch paragraph (~:313–326) — keep the rule
     *re-baselining a frozen corpus invalidates every pinned number, so it is
     rare and deliberate*; drop the branch name and the recovery SHA (git has
     them).
3. **Resolve or sharpen the 7.4 contradiction.** `meta/memory.md:105` says "a
   second projection over the same store"; `:225` says "HTML report and GUI
   become two renderings of one projection". These are different builds. Until
   the owner decides, state it in one place as an open decision with the two
   options, not as two confident sentences in different sections.
4. **Fold implemented proposals.** `code-structure-and-testing-recommendations.md`
   and `dependency-contract-proposal-for-review.md` describe work that
   shipped. Check each claim still holds, move anything still open into
   `meta/memory.md` (notably: `projection.py` is ~3939 lines, and 7.4 proposes
   a second projection beside it), then delete the files.
   **Do not touch `guide-builder-proposal.md`** — other workstream.
   Keep `frontend-deployment-proposal.md` (M8, still forward-looking) but mark
   its option C as absorbed by Phase 1.
5. **De-hardcode `/workspace`** in `docs/architecture.md:148,151,1606`,
   `validation/README.md:564`, `meta/project-setup.md`. A visitor's clone is
   not at `/workspace`. `meta/dev-container-cheatsheet.md` may keep it — it
   describes the owner's container on purpose, and should say so in its first
   line.
6. **Small fixes found by sweep:** `src/corpus/README.md` references
   `seed_stability.py`, which does not exist.
7. **What stays public and what comes out** (owner decision 2026-08-17).
   A visitor needs the README, `docs/before-ai-concept.md`,
   `docs/architecture.md` and `validation/README.md` — none of the thinking
   records. So:
   - **Out of the repository: the sales half.** `positioning-and-pitch-thinking.md`
     §9 (the German VP-Finance conversation) and §10 (the LinkedIn post),
     including the tactical notes — *"lead with the side-effect paragraph, that
     is where a VP stops defending the investment"*, *"never argue against SAP,
     he co-signed the decision"*. Fine as working notes, damaging to the VP who
     finds them. Move to a location outside the repository that the owner
     names (default `~/before-we-ai-private/`) and delete from the repo in the
     same commit.
   - **Promoted, not deleted: the honest half.** §5 "claims that can be
     defended today" and §6 "claims that cannot be defended yet" move into
     `README.md` as a maintained, first-class section. For a product whose
     argument is *we say what we do not know*, that list belongs on the front
     page as a feature, not in a draft where it reads as holes found and left.
     This is the one place the no-restating rule bends — the README is already
     the exempt home of status.
   - **Deleted after harvesting: `latest_status.md`.** Half of it is fixed by
     Phase 1, and stale criticism in public is worse than none. Anything still
     true moves into this plan or the README first.
   - **Not committed:** `frontend-deployment-proposal.md`,
     `page-structure-thinking.md`, `example_visual_screen.png` — they describe
     UI that does not exist. They stay untracked until M8 makes them real.
   - **Kept public:** `corpus-vessel/source-documents/`. They are what lets a
     stranger reproduce Run A. Gated by the Phase 1 scan, not by removal.
   - **Accepted limit:** the repository is already public and these files are
     already pushed. Deleting them from HEAD does not remove them from
     history — the commit SHAs stay reachable, as do any forks. A history
     rewrite would break every existing clone and is **not** being done for
     this content. Remove going forward; accept the history.

**Acceptance:** no file in `meta/` or `docs/` tells a story, every lesson named
above is findable in its home, the doc-path sweep is clean, and the README
carries the can-defend / cannot-defend list.

## Phase 4 — Run A: read the vessel corpus

The go/no-go. If the ten files do not ingest, nothing else matters.

1. **Write `corpora/vessel/predictions-run-a.md` first, and commit it before
   running anything.** What is expected to load, what is expected to be ugly
   (merged headers, German and Polish column names, PLN and EUR side by side,
   four PDFs including a board report with tables), and what would count as a
   failure. Written without opening the answer key.
2. **Run the measured stages only** — scan the ten sources, build column
   profiles, build the candidate matrix, chunk the PDFs. All deterministic,
   no model calls, no API key.
3. **Report what the landscape looks like**: sources loaded, tables, column
   profiles, PDF pages and passages, and every place ingestion struggled.
4. **Correction to an earlier statement in this session:** the negative
   control (vessel data against the plain `finance` pack, expecting no
   candidate to win a role) **cannot** run here. Binding candidates to roles
   is V2, a model call. It belongs to Run B, with the next recording session.

**Acceptance:** all ten sources ingest, profiles exist for every table, the
PDFs chunk, the predictions file was committed before the run, and no file
under `answer-key/` or `generator/` was opened.

---

## Explicitly out of scope

7.4, 7.7, M8, M9, the Seeded-Recall scorer rewrite, the acceptance kit, and
any live recording. The scorer rewrite and the acceptance kit are the next
plan, before Run C — not this one.

---

## Decision log — taken while executing this plan

Every judgement call made without asking, so the owner can overturn any of them
in one line. Durable ones move to their home file when the plan is deleted.

**D1 — Copyright holder is `Christian Neuhaus`, year 2026.** `LICENSE` carries
the canonical Apache-2.0 text (copied from `/usr/share/common-licenses/Apache-2.0`,
not retyped) with the placeholder line replaced. The name is inferred from the
commit author (`Christian`) and the owner's email; if it should read differently
— a company, a different spelling — it is line 190 of `LICENSE` and nothing else
depends on it.

**D2 — packages are discovered, not listed.** `pyproject.toml` now uses
`[tool.setuptools.packages.find]` with `where = ["src"]` and
`include = ["before_we_ai*", "readiness_report*"]` instead of a hand-written
`packages = [...]`. This was not in the plan; it was the cheapest way out of a
real conflict. The other workstream's uncommitted edit to `src/pyproject.toml`
was *adding* `before_we_ai.guide_builder` to that list, and moving the file
would have forced a choice between losing their edit and committing a package
entry whose code is not on disk. Discovery removes the class of bug entirely —
a package list that drifts from disk fails silently, and only on someone else's
fresh clone. `src/corpus` and `src/tests` carry no `__init__.py`, so they can
never be picked up. Verified: `pip install -e ".[dev]"` from the clone root,
imports resolve, 873 tests pass.

**D3 — `requirements.lock` pins the versions the numbers were measured with,
not the newest that resolves.** A fresh resolve already drifts (python-ulid
3→4, packaging, Pygments). The lock therefore carries the dev environment's
versions, and `anthropic` is deliberately absent — it is the `llm` extra,
online mode only. Both were verified against the full suite: 873 pass on the
locked set *and* 873 pass on a fresh unpinned resolve, so the ranges in
`pyproject.toml` are honest today. That is exactly the pair of facts the two
CI jobs keep true.

**D4 — pytest moved with the pyproject.** `testpaths` is now `src/tests`,
relative to the clone root. Both `python -m pytest` from the root and from
`src/` still work (pytest finds the rootdir by walking up), so no existing
habit breaks. No test needed changing: every path anchor in the suite is
`Path(__file__)`-relative already.

**D5 — the Docker image is written but not built here.** This container has no
Docker daemon, so `Dockerfile`, `compose.yaml` and `.devcontainer/` are
unverified by execution. The CI `suite` job builds the image, so the first push
is the proof. Stated rather than glossed: if the image is wrong, CI goes red
before a visitor ever sees it.

**D6 — the publication scan found one real thing, and it is not the corpus.**
`scripts/publication-scan.py` reads both landscapes (26 files, including both
`erp.duckdb` catalogs) and looks for structurally verifiable identities:
e-mail addresses, IBANs by mod-97, German USt-IdNr and Polish NIP by check
digit, external URLs, and a denylist of large real companies. Result: the
generated data is clean. Every generated e-mail sits in a reserved
documentation domain (`@company.example`), no valid IBAN or VAT number exists
anywhere in either landscape, and the only external URLs are three public tax
authority pages cited by the vessel tax memo.

The one genuine finding is
`src/corpus/data/real/bosch-geschaeftsbericht-2025.pdf` — a real published
Bosch annual report, 6.8 MB, committed and read by four acceptance tests.
**Decision: keep it, document it, and hand the owner the question.** Deleting
it would break green acceptance tests and remove the one document the spec
calls a Pflichtbestandteil; that is a legal/redistribution judgement, not a
technical one, and not mine to make silently. What was done instead: a
`NOTICE` file scopes the Apache-2.0 grant to the project's own work and names
the file as third-party content with its reason for being there, and the scan
waivers spell out what each accepted hit is. The residual question — is
carrying someone else's annual report in a public Apache-2.0 repository
right — is recorded as an open item in `meta/memory.md` with its two
alternatives (swap for another public report; fetch on demand instead of
committing).

**D7 — findings are waived with a reason or they fail the build.**
`scripts/publication-scan-waivers.yaml` requires prose per waived finding, and
an unwaived finding exits non-zero. A file no reader can open is itself a
finding (`unreadable`), because a file nobody could check is not a file that
passed. The scan runs as its own CI job, so it stays a gate rather than a
thing that was done once.
