# Project Memory — live state and open points

<!-- Forward-looking only: what is in flight, what is undecided, what is
     queued. No history — git has that. Durable facts belong in README.md
     (roadmap + status) and docs/ (confirmed design). -->

## Where we are

- **Built:** M0 corpus · M1 core · M2 ingestion · M3 checks & engine ·
  M4 LLM contracts V1/V2 · readiness report · M6 question flow +
  ReadinessMap · **answer types** (the guide declares what a family of
  question depends on; the model classifies, the engine expands, a human
  confirms) · **the outer-layer refactor** (`meta/refactor-workorder.md`,
  all seven PRs).
- **What the refactor changed for anyone writing code now:** report facts
  live in `readiness_report/projection.py`, HTML in
  `templates/report.html.j2` with CSS/JS as package resources, and
  `render.py` is 98 lines of wiring. Model-facing code receives a
  `ProposalStore` and structurally cannot write promoting evidence. Test
  lanes exist (`pytest -m unit`, ~0.5s); every test module declares one.
  Domain packs ship in `before_we_ai/domains/`.
- **The stage spine is the organising idea** (`before_we_ai/stages.py`, as
  data; `docs/architecture.md` → "The stage spine" for reading). Seven stages,
  one actor each; the walkthrough script number *is* the report section
  number. 0 inputs · 1 request · 2 measured · 3 proposed · 4 tested ·
  5 clarification · 6 readiness. Stage 0 is the precondition; 1 and 6 are the
  frame around the middle.
- **The suite is green and fully offline** (`cd /workspace/src &&
  source /workspace/.venv/bin/activate && python -m pytest -q`); lanes for
  faster feedback in `meta/project-setup.md`. No count is written down
  anywhere, here included — it went stale three times and never once
  changed a decision.
- **Standing measures** (these do change decisions, so they are written
  down): False-Promotion **0** (non-negotiable at every commit) ·
  Seeded-Recall **14–15/25** · prompt-leakage scan CLEAN.
- **Walkthrough pins** (offline; `validation/README.md` carries them per
  stage; re-pinned end to end 2026-08-02 after the live re-record): 12 sources
  (6 data, 6 documents) · 260 column profiles · 6 pages / 10 passages, 1 inside
  a chart · 54 hypotheses / 1 deduped / 1 skipped · 22 candidates · 54 plans /
  12 unbindable / 6 semantic-only / 4 skipped · **0 param normalizations** ·
  9 document claims / 9 anchors / 2 links / 5 refusals · 54 executed,
  42 pass / 12 fail · 6 role questions, 22 open in total · 2 statements told
  (1 parked, 1 claim) · 9 required-knowledge items · verdict **blocked**,
  naming `journal.entity`, `journal.period`, `journal.account`,
  `intercompany`. Seeded-Recall unmoved at 14/25.

## Next

1. **Owner validation run using only the readiness report.** Deferred twice,
   and the reason to do it is now evidence rather than principle: reading real
   output has found four things the whole green suite did not — a grammar slip
   in a derived sentence, three dead fields, two report surfaces disagreeing
   about one store, and the unconfirmed required-knowledge list below.

   Run it: `cd validation && ./scripts/reset.sh && ./scripts/0-inputs.sh`,
   then follow the `next:` line each stage prints. Every stage rebuilds
   `validation/data/report/index.html` — leave a tab open on it.
   `validation/README.md` says what to look for and the numbers to expect.
2. **M5 — documents & V3. FEATURE-COMPLETE 2026-08-02.** PDF pipeline,
   position anchors, DuckDB FTS, multi-anchor reconciliation, `tell` +
   mirror loop. Acceptance: T8 negatives and a real PDF — every PDF it
   needs is in the frozen corpus (`src/corpus/data/`, including `noise/`).

   **Design settled first** (architecture.md → "Documents & V3"), then
   built. Four things the design doc got wrong and the code corrected —
   each recorded there, listed here because they are the shape of the
   milestone:
   - **`kind` and `match` are derived, not asked for.** The plan had V3
     classify an anchor as text/table/chart. The corpus killed it: F23's
     chart figure extracts as ordinary text, so asking would rest the
     whole rule on the model's word about something it cannot see. Kind
     comes from page geometry (PyMuPDF `find_tables()` + drawing
     clusters), match from reconciliation parsing the quote.
   - **Value corroboration ≠ definitional grounding.** The multi-anchor
     rule as first written required two independent anchors before
     anything could link — which would have made K3 impossible, since the
     accounting policy is the only document stating the sign convention.
     The threshold governs figures; a policy sentence links on its own,
     and costs nothing because a link is not evidence (the claim stays
     `proposed`).
   - **Retrieval bounds, it does not filter.** A document that fits under
     the passage cap is sent whole. Keyword-selecting passages silently
     drops the paragraph that answers a differently-phrased question.
   - **Documents have one owner.** `scan()` used to fingerprint PDFs too;
     both stages then wrote one Source in two fingerprint shapes, and
     staleness compares fingerprints. `scan()` now skips documents.

   **Decisions taken at kickoff (2026-08-02):**
   - **All six corpus PDFs are declared sources — DONE** (was: only
     `management_report.pdf`). Noise presence is the precision test.
     Walkthrough pins still need re-recording (below).
   - **The spec's real public PDF — SUPPLIED 2026-08-02, decision B
     closed.** `src/corpus/data/real/bosch-geschaeftsbericht-2025.pdf`:
     146 pages of published annual report, InDesign, encrypted, bilingual.
     Read end to end in `tests/corpus_driven/test_real_document.py`;
     deliberately **not** a walkthrough source, because 539 passages would
     make one V3 call larger than the rest of the corpus put together.

     It earned its place immediately. **R1** — 3,081 soft hyphens and six
     kinds of exotic space across 512 of 539 passages meant a *correct*
     quote could not match: the page reads "Verlustrechnung", the
     extraction held "Verlust\u00adrechnung". Extraction now normalises
     invisible characters once, deterministically, and the match against
     the normalised text stays exact — normalising the text is not
     loosening the match. **R2** — a 146-page financial report yields
     essentially **no detected tables**: designed reports rule with
     whitespace and colour, not strokes, so balance-sheet rows arrive as
     `text`. That is the permissive direction and the strongest argument
     for the layout-analyser evaluation below. **R3** — on a designed page
     anything inside a drawn region reads as `chart`, including cover
     titles and navigation bars: false *refusals*, which is the right way
     round to be wrong.

     Still open from the same spec section (:42, wider than decision B):
     the milestone's own completion asks for **a run against a real,
     well-known dataset whose truth the owner knows** — real data, not a
     real document.

   **Built so far (2026-08-02), suite 470 → 580 green:**
   `before_we_ai/documents/` — `extract` (geometry → kind), `chunk`
   (deterministic, kind-pure, stable ids), `index` (DuckDB FTS, hard error
   if the extension is missing), `figures` (reads numbers without
   inventing agreement — an ambiguous literal like `500.000` reports both
   readings and never counts), `reconcile` (the multi-anchor rule) ·
   `read_documents(root)`, the stage-2c twin of `scan` — profiles, zero
   claims, zero evidence · `DocumentProfile` sharing `profiles/` with
   `DataProfile` via the `object_type` discriminator ·
   `ProposalStore.anchor()` with the quote string-matched at the write, so
   a hallucinated citation cannot be stored at all · `AnchorKind` /
   `AnchorMatch` in `core/enums.py` · contract **V3** (`llm/v3_documents`,
   `interpret_documents`) — one call per document, findings become
   proposed claims + anchors, refusals become clarification questions.

   **Also built:** `statements.py` (`tell`, `confirm_claim`,
   `answer_question`, the `Mirror`) · the `_status_rationale` fix, by making
   `confirmation_admissible` public so the report asks the law instead of
   restating it · the report's **decision log** (owner decision: its own
   chapter after the process diagram, plus inline hints) · documents and
   anchors rendered for a reader · walkthrough stages `2c-measure-documents`
   and `3d-propose-documents`, six hand-authored V3 fixtures, README re-pinned
   · the **hard document** (`corpus/data/hard/`, not the spec's real public
   PDF — that stays open) · `system_sha256` closing the prompt half of the
   drift guard.

   **Nothing in M5 is unbuilt.** All five kickoff items landed, the
   acceptance run is green (T8 negatives, K3, F28/F29 against the
   *recorded* answers, False-Promotion 0), and the walkthrough is
   re-pinned and audited against a fresh run.

   **Two things stand between here and calling the milestone done, and
   neither is code:**
   1. the **owner validation run** (item 1 of this Next list) — read the
      report end to end and judge it;
   2. the spec's `:42` requirement — **a run against a real,
      well-known dataset whose truth the owner knows.** Real *data*,
      not a real document; decision B (the Bosch PDF) closed the
      document half only.

   **Done this session (2026-08-02, second):**
   - **`discover(root)`** — `scan` walks `sources/` and merges what it
     finds; never overwrites, so a hand-tuned entry wins. Plus
     `domain_guide_file: finance` now resolving to the shipped pack.
   - **Kickoff item 3, with the refutation-only rule.** A role may bind
     to any template; a *generic* check over a role writes
     `establishes: False` and its PASS does not promote. Proven on the
     corpus: all three `account` candidates get an anti_join, all three
     pass, all three stay `proposed`.
   - **`amount_expr`** — `balance` and `subledger_equals_gl` read a text
     amount column in whatever format it is stored, and **refuse** a
     column that could be read two ways rather than pick a majority.
     The corpus is plain-format, so this is unit-tested, not corpus-tested.
   - **The contract descriptions that misled the model** — `balance` and
     `subledger_equals_gl` now say BARE COLUMN NAME and that the template
     reads the number itself. Effect: param normalizations went **16 → 0**.
     The machinery stays; the next landscape will need it.
   - **Walkthrough re-pinned end to end** — every number above, plus two
     *qualitative* corrections the old README got wrong: answering the
     mapping questions no longer clears to `ready_with_limitations` (it
     stays blocked on `intercompany`, which no answer can move), and 3d
     refuses five figures rather than three.
   - **Stage 5b, the `tell` beat** (`5-clarify.sh` → `5a-clarify.sh` +
     `5b-tell.sh`). Two fixtures recorded live. **Each statement needs its
     own scenario** — the fixture key is contract + scenario + document and
     every statement is the same "document", so one scenario would have
     them overwrite each other.
   - **Question priority — owner work-list point 2, the "real lever".**
     Every card carries a band (blocks / limits / bears on / not on this
     path), section 5 sorts by it, `gap_load` breaks ties. Derived from
     the ReadinessMap, never stored — see the note under "Derived, never
     stored" below.
   - **M5 acceptance run: green.** T8 negatives, K3, F28/F29 against the
     *recorded* answers, False-Promotion 0. 732 tests.
   - **Three real defects found by doing this, none of which the suite saw:**
     see "Defects the green suite was blind to" below.

   **Done in the first 2026-08-02 session:** the guardrail now covers
   V3 · decision B closed (the Bosch report, `corpus/data/real/`) · the
   live re-record (every fixture is a real answer; request and V3 for the
   first time) · staleness superseding · the unblock chapter · question
   magnitude.

   **Unblocked, and the sequencing was deliberate:** the refactor ran first
   so M5 builds its document surfaces into `projection.py` and the template
   rather than into a 2,800-line renderer that no longer exists. Its new
   contract (V3) is born inside `ProposalStore`, and `anchor()` is the
   weak-evidence method that facade was shaped to accept — `DOCUMENT_ANCHOR`
   promotes nothing (`resolve_status` never reads it), so V3 writing anchors
   does not touch the promotion boundary. **`PyMuPDF` is M5's first line of
   code**: the spec names it and it is still undeclared.

   **M5 also builds the missing answer operation.** The *law* exists and is
   tested (a scoped CONFIRMATION makes a claim business-confirmed,
   `core/transitions.py`), but no product code constructs CONFIRMATION or
   TESTIMONIAL evidence — only tests do. `answer_question(store, card,
   answer, by=human)` is the mirror-loop machinery M5 needs anyway, and it
   is the core interaction of the GUI milestone below.

   **And it must fix `_status_rationale`** (found 2026-08-01 pre-flighting
   WP5). That function restates the promotion law in prose inside the
   renderer, and it already disagrees with it: `resolve_status` counts only
   *admissible* confirmations (mirror-loop — a testimonial claim needs an
   explicit scope), while the prose counts every confirmation record and
   then says "admissible" anyway. A claim would read: status `proposed`,
   trail "1 confirmation", why "Nothing stronger than proposed evidence is
   live yet." Unreachable while nothing creates confirmations — **M5 makes
   it reachable**, and the case it garbles is exactly the mirror loop's
   teaching moment ("you did not say for which scope"). The refactor moves
   the function verbatim and does not touch it; the fix belongs here.

   Its target is concrete: the three unsupported **rule** items in the
   ReadinessMap (`which accounts are profit and loss`, `sign convention for
   income and expense`, `month cut-off for late postings`). A sign convention
   lives in a policy, not in a column. V3 must **link** the claims it
   produces to the rules they answer (`readiness.link_claim` — the seam is
   built and tested).

   It also unlocks three walkthrough claims whose V2 refusals literally name
   documents: `decodes` account ranges, the AR control account, and
   opening-balances coverage. Read them in the readiness report.

3. **Confirm the answer-type slice against real output.** Built
   2026-08-01 (`docs/architecture.md` → "Answer types"); the walkthrough now
   classifies, shows the guide fingerprint and per-item provenance, and
   demonstrates the confirmation lifting the cap. What has *not* happened
   is a human reading it end to end — which is the same argument as item 1
   above, applied to the newest surface.

   Two things to judge while reading, both deliberate and both reversible:
   - **The cap is aggressive.** Every project reads
     `ready_with_limitations` until someone confirms the classification.
     True, but it means `ready` is now rare by construction.
   - **Only a confirmation lapses** when the guide moves, not waivers or
     links. A waiver is about one item; a confirmation is about the list.

4. **Confirm the two report fixes while reading** (done 2026-08-01, worth a
   look because both were found by reading and not by testing): section 0
   now lists the guide's answer types with what each one requires — a
   reader cannot judge the classification in section 1 without seeing what
   was on offer — and its subsections read `0.1 / 0.2 / 0.3` instead of the
   pre-spine `1.1 / 1.2 / 1.3`.


## The ping-pong, and what was under it — 2026-08-02

Three re-recordings in a row each fixed one trap and lost another:

| | plans | F27 decoy | F22 intercompany |
|---|---|---|---|
| A (baseline) | 50 | caught | caught |
| B (item 3, wider menu) | 56 | **lost** | caught |
| C (balance-note fix) | 48 | caught | **lost** |

Treating those as three bugs was the error, and the owner caught it
before I did. **One cause**, in `V2_ROLES_SYSTEM`: "taking params from
the claim's binding". `balance` needs one view and never wavered;
`ic_symmetry` needs left AND right, `subledger_equals_gl` needs a
subledger AND its ledger. For two of three laws the instruction is
impossible, and `template=null` sits there as the way out — so **trap
coverage depended on the model disobeying the prompt.** Fixed: a
relation may take its missing params from the other claims in the same
batch, which were always in front of it.

**The lesson, worth more than the fix.** Every recording re-decides
*every* binding, so a flipped trap somewhere else is not evidence about
the change you just made. Two rules follow:

- **A flipped trap after a prompt change is a symptom, not a bug.**
  Ask what the prompt now makes impossible before patching the symptom.
- **Never re-record to see if it comes out better.** That is the tuning
  the owner forbade, and it is indistinguishable from debugging unless
  you can say in advance *which contradiction* the change removes.

`subledger_ar` never binding is **not** part of this: it declines
because it needs to know which GL accounts are the AR control accounts,
and nobody has told it. Correct, permanent, and already surfaced as a
clarification question.

**Still genuinely open (separate):** `CAST(x AS DOUBLE)` in
`balance.sql.j2` handles `304718.22` but not European `1.234,56` — such
a column makes the check *error*, not fail. The corpus does not
exercise it; `documents/figures.py` solves the same problem in Python
and is the model to follow. Related and also open: the `balance`
TEMPLATE_NOTE says "a plain column summed by the template" while the
`reconciliation` note one line above says text columns "must be cast",
which is what sent the model down the CAST path in recording B. Fix
both together, in one recording.

## Declared goal — the GUI milestone (after M5; not scheduled)

Owner statement 2026-08-01: a small product for **one question to one
answer**, with a GUI — ask the question, load documents, run, answer the
open questions, see the readiness map. **Computing the result is a further
milestone of its own**, and 2026-08-01 settled what belongs in it:

- the spec's **V4, SQL generation** — the contract number this repo left
  free when the request contract was renamed off it;
- **Assumption Capture** (`docs/spec/before-we-ai-systemarchitektur.md:59`):
  `sqlglot` parses the generated query, checks it against the allowed
  subset, extracts joins and claim-requiring filters, matches them against
  the claim store and **materialises what is missing as `proposed` claims**.
  The query becomes a source of claims — a real epistemic feature, not
  plumbing;
- `sql`/`result_ref` return to `AnswerRequest`, which is why deleting them
  was scaffolding removal rather than a loss.

They are one milestone, not two: Assumption Capture without SQL generation
has nothing to parse. That also fixes when `sqlglot` gets declared — then,
not before.

Design consequences that hold *now*, without building it:

- The GUI is a **loop** (ask → run → see questions → answer → re-run), not
  the walkthrough's linear batch. That is why recommendation A stays
  deferred: an application layer shaped today would be shaped like the
  walkthrough and thrown away.
- Its work-queue primitive half-exists (`gap_load` ranks unproven claims by
  the questions resting on them).
- Its core interaction is the answer operation M5 builds (Next, item 3).
- What it consumes is the report **view model** the refactor extracts —
  HTML report and GUI become two renderings of one projection.
- "Answered — what must now rerun / what is now stale?" is M7, and the GUI
  turns M7 from nice-to-have into required.

### M5 kickoff batch — ALL FIVE DONE 2026-08-02

Kept for the reasoning, not as a to-do list.

1. `discover(root)` sources discovery + bundled domain guides — **done.**
   Merge never overwrites; `domain_guide_file: finance` resolves to the
   shipped pack.
2. Show the domain tag in the V2 template docs — **done.**
3. Mapping claims binding to *generic* templates — **done**, with the
   refutation-only rule (owner decision): a generic check over a role
   refutes but never establishes, via `establishes: False` on the
   evidence payload. All three `account` candidates pass an anti_join
   and none of them promotes.
4. **Derive `Hypothesis.kind` from the predicate instead of asking for it.**
   It is a pure function of the predicate (`concept` iff
   `concept_definition`), yet the model must supply it — and when it omits
   it, the `"rule"` default contradicts the predicate *and* triggers a
   second, bogus error ("grounded in no known view or column", which fires
   only for rules). All 3 V1 skips in the walkthrough are this one bug, and
   the retry cannot fix it. Also fall back `definition` → `statement` when
   the model gives only `term`. Schema change ⇒ prompt bytes. The gain is
   admitting the concept class at all, not a recall number: it would not have
   flipped F21, whose matcher also needs a revenue link the claim never
   states.
5. **Normalize `view.column` given for a view param — DECIDED 2026-08-02,
   and done: normalize, but record the correction.** The owner took the
   third option rather than either simple one. The check runs (so a
   binding the model shaped wrongly is no longer lost), *and* every
   corrected param is written to the store as a `param_normalized`
   declaration and rendered at the claim: "the model gave X where a bare
   name belongs; it was read as Y". Leniency without a trace is the
   too-loose-law failure — a misunderstood binding runs, passes, promotes,
   and nothing says we changed it.

   **The number that came out of it is the interesting part: 25
   corrections on this corpus, not one.** Column normalization had been
   happening *silently since M4*; only the view-param case was ever
   visible, and only as a failure. The decision did not add leniency so
   much as reveal how much was already there.

   Effect on the pins: 42 → 43 check plans, 7 → 6 V2 skips, 32 → 31
   claims without a check.

## The unblock path — measured 2026-08-02, hole closed the same day

Owner question: "I can read that it blocks, but what do I *do*?" Measured
rather than assumed. Going backwards from a blocker, there are three
routes, and the engine already distinguishes which one applies — the
`because` sentence says either "a human has to answer, or a check has to
run" or "this is not a missing answer but a wrong one — the data itself
has to change."

**Route 1, you answer.** Writes one `EvidenceRecord` (CONFIRMATION, human,
scoped) into `evidence/`; the chosen claim gains the id and its persisted
status is recomputed. **Nothing re-runs** — the ReadinessMap is derived on
every read, so the next render simply shows it.

**Route 2, you waive.** Writes one `KnowledgeAct` into `answers/` and
changes no other object at all: the dependency list is never stored, it is
re-assembled from the guide plus the acts on every read. Verified: waiving
`intercompany` drops it out of `blocking()` and leaves it visible, struck
through, with the reason beside it.

**Route 3, you fix the data — BUILT 2026-08-02, and it closes now.** It
did not: `run_ready` re-executed every plan and appended the new PASS
beside the live old FAIL, so `resolve_status` called the pair a conflict
and the claim went from *contradicted* to **unresolved**. You corrected
your books and the system found a new way to be stuck. Measured before
the fix: a second run took 49 check results to 98 and marked none stale.

A new run of a plan now marks that plan's earlier runs stale
(`engine/runner.py::_supersede`). Evidence stays append-only — nothing is
deleted, `stale` is the one mutation the store permits, and the
derivation stops counting it. Both readings stay in the trail; what
changes is which one describes the data as it is now.

**Still unbuilt from M7:** flagging evidence whose *source* has moved but
which has not been re-run yet. Today a project with edited data and no
re-run shows its old readings as live. Superseding is what unblocks;
flagging is what warns, and it is the remaining half.

Also measured, against expectation: **narrowing the question does not
help here.** `ic_symmetry` is inherently cross-entity — the DE table books
against a leg missing in US — so a DE-scoped request blocks on exactly the
same items. A report that offers "ask a narrower question" wherever it
blocks would be offering an escape that often is not one.

## The work list an analyst actually gets — reviewed 2026-08-02

Owner asked how much is still waiting on a person, and whether the
questions would be clear to a business analyst. Counted on the corpus:
**84 claims** (37 test-supported, 12 contradicted, 35 proposed), **22 role
candidates over 8 roles of which 7 are unsettled**, **0 human
confirmations so far**, **21 open questions**, verdict blocked on 4 items
with 3 limitations.

Read as a work list rather than as output, it fails on triage. Four
findings, none of them about correctness:

1. **No magnitude anywhere.** "de_erp__ar_open_items and de_erp__gl_postings
   do not agree per group" — by how much? One exception in 24 rows and 40%
   of rows are different decisions, and the exception counts are already
   on the evidence. Cheapest fix, biggest gain.
2. **No priority.** 21 questions, flat. Only 4 items block the answer; the
   other 17 may not bear on this question at all. `gap_load()` exists to
   rank unproven claims by the questions resting on them and nothing
   surfaces it.
3. **Candidates are not in the question.** "Which of the proposed
   candidates is the 'account'?" never lists them; they are on the card as
   claim ids. Fine in the report where the card expands, useless in a list.
4. **Duplicates.** ic_symmetry asks once per direction — de→us and us→de
   are one decision for a reader, two rows in the list. Also
   `de_erp__territory_plz` appears as both sides of its own range question,
   which reads as a bug even where it is not.

**Where each fix lands — this is not all one layer, and the difference
decides who may make the change.** A clarification question is not a view:
its wording is authored by the engine and **stored** in `questions/` as a
`ClarificationQuestion` (three authors: `engine/runner.py::_draft_question`,
`llm/domain_guide.py` for role cards, `llm/v3_documents.py` for document
refusals). Editing that wording rewrites project data, and old cards keep
their old text — it is a re-record-shaped change, not a re-render.

- **(1) magnitude — DONE 2026-08-02.** On the card as `finding`, not
  inside `question`: the wording is the dedup key, so a count in it would
  mint a fresh card every time the number moved and put one decision in
  front of the reader again and again. A re-run updates the size on the
  same card. What it buys, on the corpus: AR vs GL is **98.6%**,
  intercompany **4.2%**, invoices vs orders **2.4%** — three sentences
  that read alike and mean entirely different things.
- **(2) priority — DONE 2026-08-02.** Every card carries a band (blocks
  the answer / limits / bears on / not on this path); section 5 sorts by
  it; `gap_load()` — built since M3, called by nothing until now — breaks
  ties inside a band. On the corpus: **5 block, 18 are not on this path**.

  **The band is derived from the ReadinessMap and deliberately not
  stored.** A priority written beside the wording would be stale the
  moment a claim settled and would need migrating; a derived one changes
  by itself and cannot disagree with the verdict, because it is read off
  the same object the verdict is. Structural items block, rule items
  limit — the distinction `ReadinessItem.structural` already draws.
- **(3) candidates in the question** — presentation, still open. The card
  already holds the candidates as `claim_ids`; a list view can expand
  them. Note this is *already* done inside the report (`mode='bindings'`
  renders them as picks); what is missing is the compact list view.
- **(4) duplicates** — presentation, per owner 2026-08-02, still open.
  Two directions of one law are one decision for a reader; collapse them
  in the UI rather than suppressing a card the engine was right to write.
  **Sharper now that priority exists:** the two `ic_symmetry` directions
  land in *different bands* (one blocks, one does not, because only one
  direction's claim is a role candidate). Two near-identical questions
  sorted far apart reads worse than two adjacent ones — so collapsing
  them matters more than it did.

What is genuinely good: the role questions carry the guide's definition
and say *why* no check can settle them ("what the data means is a business
fact, not an arithmetic one"), which is exactly the sentence an analyst
needs to know it is their call and not a bug.

Fixed the same day: the four document questions did not name their
subject — they opened "only management_report p.1 carries this figure"
without saying which figure. They now lead with the claim.

## Defects the green suite was blind to — 2026-08-02

Three, all found by re-pinning rather than by testing, and each blind for
the same shape of reason: **the suite only ever exercised the one path.**

1. **`import before_we_ai.readiness` failed outright.** M5 had
   `v3_documents` reach back into `readiness` at module scope, so the
   package could not be imported first. Every test imported `llm` first,
   so 715 tests passed over it. Fixed by lazy imports; `tests/unit/
   test_import_order.py` now imports each package first in its own
   interpreter. **Any new cross-package import is a candidate for this.**

2. **`decodes` hypotheses were rejected for columns that exist.** The
   grounding lookup matched only `view.column` or a bare view, and
   `decodes` declares no table param — so an unqualified name is the only
   thing the model *can* write, and rejecting it claimed a real column did
   not exist. A bare name now grounds where exactly one view carries it;
   where two do it still grounds nothing, which is why one corpus skip
   survives (`account_range_group` is in both charts of accounts).

3. **Two fixtures shipped pinned by nothing.** The escape guard waves
   through anything named `v3_documents__*` on the grounds that
   `test_documents_offline_corpus.py` pins it — and that file pinned the
   six PDFs by iterating `store.documents`, which a statement is not.
   **The escape guard's allow-by-prefix rule is the weak spot**: adding a
   fixture under an existing prefix inherits a guarantee nobody checked.

The recorder learned precision from this: `--only-drifted` writes a
fixture only where the one on disk no longer answers its input or its
prompt, and `--skip-v3` leaves the document fixtures alone. The
`decodes` re-record touched one fixture and left seven; the `tell`
recording touched two and left eight. Before, both would have replaced
everything wholesale — and a replaced fixture moves the corpus baseline
that every pinned number is measured against.

## Open, found while finishing M5 — 2026-08-02

Small, real, and none of them blocking. Listed because each was found by
reading output rather than by testing, and none has a test that would
catch it coming back.

- **`reconciliation` still asks the model to cast.** Its TEMPLATE_NOTE
  says "text-typed numeric columns must be cast in the expression, e.g.
  CAST(col AS DOUBLE)" — true for that template, because its measure
  params really are row-level expressions. But `balance` and
  `subledger_equals_gl` now read the number themselves (`amount_expr`),
  so the three notes no longer describe one consistent contract. That
  inconsistency is exactly what produced the F27 loss in recording B.
  **Either give `reconciliation` the same treatment or say plainly in
  its note why it differs.** Prompt bytes → one recording.

- **A two-sided law is still modelled as a one-sided claim.** A
  `MappingClaim` binds one candidate to one view; `ic_symmetry` and
  `subledger_equals_gl` need two. The fix that landed is a *permission*
  in `V2_ROLES_SYSTEM` ("take the missing params from the other claims
  in this batch"), which works and is recorded — but the object model
  still cannot express "this pair plays this role", so the pairing lives
  in the model's answer rather than in a claim. If two-sided laws ever
  need to be elected against each other, this is where to start.

- **The escape guard allows by prefix.** `test_no_fixture_escapes_the_
  drift_guard` waves through anything named `v3_documents__*` on the
  grounds that the documents file pins it. Two `tell` fixtures shipped
  green and pinned by nothing before that was noticed. A new fixture
  under an existing prefix still inherits a guarantee nobody checked.

- **`amount_expr` covers `balance` and `subledger_equals_gl` only.**
  Other templates that touch numbers (`reconciliation` measure
  expressions) still rely on whatever the model wrote.

## Open decisions (owner)

- **Domain packs live in `before_we_ai/domains/` — decided and done
  2026-08-01.** The finance guide was in `src/tests/fixtures/`, which told
  every reader of the report that the product's critical input is test
  infrastructure. It is now `before_we_ai/domains/finance.yaml`, declared
  package-data and reached through `domains.packaged("finance")`.

  The deciding argument was not tidiness but **shipping**: the M5 item
  `discover(root)` promises "bundled domain guides", and nothing bundles out
  of `tests/fixtures/`. "Data, never code" is a rule about the *format*
  (YAML, not Python), not the location. A customer's own guide stays a
  different thing entirely — their data, in their project, via
  `llm.domain_guide_file`.

  The content did not change, so the fingerprint did not either
  (`0ac5f94b7b63`) and every walkthrough pin held.

- **`sql`/`result_ref` return with the spec's V4.** They were deleted from
  `AnswerRequest` on the stated grounds that "no milestone produces SQL".
  **That reason was wrong** — the spec's V4 (SQL generation) does, and
  `docs/spec/before-we-ai-systemarchitektur.md:59` says its result goes into
  the question card. The deletion stands (nothing set or read them), but they
  are unbuilt scaffolding that comes back, not dead weight. The V4 slot is
  now free: the request contract was renamed off it 2026-08-01.

- **Domain-guide acceptance kit — decided 2026-08-01, half done.** Part 3
  (the coherence lint) was already shipped. Parts 1+2 are now a **standing
  rule** in `meta/conventions.md`: no new domain law without a holds-fixture
  and a violated-fixture, no new role without a wrong candidate that must
  lose. Cheap per law, expensive to backfill — which is exactly why it is a
  rule rather than a task.

  **What remains is the backlog:** the three existing finance laws
  (`balance`, `subledger_equals_gl`, `ic_symmetry`) have no such fixtures.
  One focused session. **Not a Copilot package** — writing a *violating*
  fixture requires knowing what breaks a conservation law, which is domain
  judgement, not execution. Analysis: architecture.md → "The domain pack is
  the critical … input".

- **Seeded-Recall: split the metric first, set the bar after M5** (decided
  2026-08-01). One number today mixes two populations. Relationship-style
  traps are answerable now; definition-style traps need documents (a sign
  convention lives in a policy, not a column), and the misses cluster there.
  A single bar over 25 traps would therefore have to sit below the noise
  floor (±2–3) to be passable, which makes it say nothing.

  So: **count the two classes separately**, then a bar over the
  relationship-style half is meaningful immediately and M5 cannot move it.
  The other half gets its bar when M5 lands. The split is worth more than
  the bar anyway — it says *which kind* of knowledge is missing, which one
  number never could.
- **Evaluate a real layout analyser for the extraction layer (after M5).**
  We write no PDF parsing — PyMuPDF does all of it — but the ~40 lines
  deriving `kind` from geometry are the weakest part of the pipeline, and
  the hard document already measures exactly how weak: it beats us on the
  unruled table (H4) and on two-column reading order. Both are layout
  analysis, and better tools exist.

  Candidates: **`pymupdf4llm`/the layout add-on** (same dependency,
  PyMuPDF recommends it itself — the suggestion message is switched off in
  `documents/__init__.py`) and **Docling** (IBM, MIT: layout model, table
  structure, reading order, bboxes as provenance).

  **Not blocked on taste — blocked on determinism.** Docling ships ML
  models; CI is fully offline and chunk bytes feed fixture hashes, so a
  first-run model download would break both. Evaluate against
  `corpus/data/hard/acme_annual_extract.pdf` as the benchmark; it already
  pins the six behaviours that decide it. The swap is cheap by
  construction: everything downstream sees only `Block` (page, text,
  bbox, kind), so the rule, the figure reader and V3 do not change.

- **Standalone demo dataset** — one correct journal, one attractive wrong
  export, an account master, a sign convention, a non-inferable policy;
  intended as the first user experience. Needs its own recorded V1 / role /
  V2 answers, so it rides the M5 live session.
- **`scripts/` at repo root** is reserved by `CLAUDE.md` (start the process,
  readiness report, cleanup of stale processes) and does not exist yet —
  **deliberately**. An empty reserved directory is a claim with nothing
  behind it; it appears when the first operations tool does.

  The one candidate was deleted with the branch `copilot/create-scripts-folder`
  (commit `4d59382`, recoverable by that SHA): 71 lines copying generator
  output into the corpus, with default paths from before the `src/`
  reorganisation (`/workspace/raw-training-data`, `<root>/corpus/data` — both
  now wrong). And the operation itself is a *re-baselining* of a deliberately
  frozen corpus, which invalidates every pinned number and every fixture. It
  must be rare and deliberate; rewriting it correctly then costs ten minutes,
  merging it stale costs a file that rots further.

## Standing constraints

- **`guide_builder` is somebody else's work in progress — do not touch
  it** (owner instruction 2026-08-02: "ignore the guide-builder and
  corpus-vessel folder, other project"). It lives uncommitted in the
  tree as `src/before_we_ai/guide_builder/`, two `test_guide_builder*`
  files, plus edits to `src/before_we_ai/llm/config.py` (a
  `guide_builder` model tier) and `src/pyproject.toml` (a package
  entry). **Never `git add -A`** — stage your own paths explicitly, or
  you will commit their in-flight work. Note `pyproject.toml` names a
  package that is only partly on disk, so a fresh `pip install -e .`
  may break; the running editable install does not notice, which is why
  the suite stays green.
- **The Anthropic API key is reused, not rotated** (owner decision). It
  lives in `~/.config/before-we-ai/api-key` — outside the repo, chmod 600 —
  and reaches a process **only** through `scripts/with-api-key.sh`, which
  exports it for one command via `exec`. It is never written to any file
  inside the repo, never committed, never logged, and never pasted into a
  transcript.
  **Never put it back into `~/.zshenv` or any shell startup file, and never
  `export` it in a shell you keep working in.** It sat in `~/.zshenv` from
  2026-08-02 07:10 to 16:21, and every zsh loads that file — including the
  one Claude Code starts in. Claude Code takes `ANTHROPIC_API_KEY` from the
  environment and bills the *assistant session* to it, so a 1M-context Opus
  chat was charged to the key the owner had funded for a handful of
  recordings. The owner found it on the bill, not in a log. The recordings
  were never the expensive part. Rule: scope a credential by the **process**
  that may spend it, not by what it was intended for — and when setting a
  credential up, say out loud who else in the room can now see it.
- `docs/spec/` is the owner's authoritative German spec — edit only on an
  explicit owner decision. Everything else is English.
- Prompt bytes change only with a deliberate fixture re-record; the drift
  guard is the proof. **It only became the proof on 2026-08-02** — until
  then the guard hashed the built input and nothing else, so rewording a
  system prompt left every fixture stale and CI green. Found by mutating
  V3_SYSTEM and watching it say nothing. Fixtures now carry
  `system_sha256` alongside `input_sha256`, both are checked, and a second
  guard asserts that no fixture escapes either check.
