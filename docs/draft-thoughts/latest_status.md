# Latest status — an outside read of the build process

> **Status: assessment for owner review — 2026-08-08.** Not architecture, not
> a status of record. Feature status lives in `README.md`; live sequencing in
> `meta/memory.md`. This file is one reader's judgement of *how* the project
> is being built, what worries me about it, and a verdict I am willing to be
> wrong about in public.
>
> Placed in `docs/draft-thoughts/` rather than at the repository root on
> purpose: a file called `latest_status.md` at root would compete with the
> README roadmap table, which is the one home of feature status. Move it if
> you disagree.

---

## 1. What this assessment rests on, and what it does not

Being explicit, because the product's entire argument is that an unstated
basis is worthless.

**What I did:** read `CLAUDE.md`, `README.md`, all of `meta/`, all of
`docs/` including the four draft proposals and the full 1636-line
`architecture.md`, the validation walkthrough, and selected source — the
check library, the core objects, the projection module's shape, the
document chunker, the source catalog and the Excel reader. Ran targeted
greps against specific claims rather than trusting prose.

**What I could not do:** run the test suite. This container's venv has lost
the execute bit on every binary and no longer contains a `python`
interpreter, and the DuckDB FTS extension is missing from
`~/.duckdb/extensions/v1.5.4/` — which `architecture.md` says the dev image
bakes in. A forced run through the system interpreter produced 34 failures
and 60 errors, **all** of which I traced to the missing extension. I am
recording that as an environment failure, not a code failure, and I am
**not** claiming the suite is green. `meta/memory.md` says it is; that is
your claim, not my verification.

**What nobody has done:** run this product against data whose truth is known
outside the project. Everything measured anywhere in this repository was
measured on one synthetic corpus built by the same people who built the
tool. That fact shapes every judgement below.

---

## 2. What this project does unusually well

Not flattery — these are specific and I would cite them elsewhere.

**Rules instead of tasks, where backfilling is expensive.** *"No new domain
law without its two fixtures"* is a standing rule rather than a backlog item,
with the reason attached: cheap per law, expensive to backfill. Most projects
discover that distinction after the backfill.

**Failures are converted into rules, and the rules keep their reason.**
Three recordings in a row each fixed one trap and lost another; each loss was
patched locally as if it were its own bug; the actual cause was one sentence
in a prompt making two of three laws impossible to bind. The outcome was not
a fix, it was two rules — *before patching a flipped trap, ask what the
prompt now makes impossible*, and *never re-record to see whether it comes
out better*. That is a mature response to an expensive lesson.

**Bad states are made inexpressible rather than merely caught.** Replacing
the flat role list with objects-and-fields did not add a lint for the
`amount_local` mis-declaration — it made that entire class of mistake
unwritable. Stronger than detection, and the project knows the difference.

**Heuristics are tested by mutation.** Invert one, disable one, see what
turns red. The drift guard only became a real guard when someone mutated
`V3_SYSTEM` and watched it say nothing; it now hashes the system prompt as
well as the input, and a second guard asserts no fixture escapes either
check. That is the correct instinct applied to the project's own safety net.

**The contract is suspected before the model is.** Four of five rejected V2
bindings turned out to be one misleading sentence in the template
documentation — including all three `subledger_equals_gl` bindings, meaning
the only law that could settle receivables had never run once. The lesson
was written down as a class, not an incident.

**Numbers that nobody acts on are not kept.** No test count is recorded
anywhere, deliberately, because it went stale three times and never once
changed a decision. Standing measures that *do* change decisions —
False-Promotion, Seeded-Recall, the leakage scan — are recorded.

The epistemic core is sound. `Actor.AI` cannot author promoting evidence,
and that is enforced by construction rather than by prompt discipline or
review vigilance. False-Promotion is 0 because it is structurally difficult
to make it anything else. This is the part of the product I have no doubts
about.

---

## 3. Doubts about the build process

Ranked by how much they would change what I do next.

### 3.1 The roadmap is sequenced by dependency, not by what would falsify the product fastest

This is my strongest criticism and everything else is downstream of it.

M7.4 → M8 → M9 is a clean engineering build order: each milestone sits on
the one before. But the thing most likely to be *wrong* — does a domain guide
survive contact with a landscape nobody curated? — is scheduled last, inside
M8's acceptance. And the cheapest available test of the product's own stated
central weakness, the acceptance kit's holds/violated fixtures, is
**unscheduled entirely**.

`architecture.md` names the domain pack as *"the most load-bearing open
weakness in the product; treat it as such."* It is not being treated as such.
It is being treated as a backlog item behind three feature milestones.

### 3.2 The project is doing to itself what it warns customers against

The product's thesis is that you cannot confirm a correspondence claim from
inside the system — that data curated under an interpretation cannot validate
that interpretation.

The corpus was designed by the people who designed the traps, using the same
model of the finance domain that produced the domain guide, the check
templates and the expected verdicts. Seeded-Recall measures the tool against
its authors' understanding of the domain. The blind traps (BLIND_1/2/3,
owner-held) are a real mitigation and the right instinct — they are also
three traps.

This is not a flaw in the corpus, which is excellent. It is a limit on what
any measurement taken inside it can mean, and it is the same limit the
product sells against.

### 3.3 Documentation may be outrunning construction

`architecture.md` is 1636 lines. The guide-builder README is 930. Three
substantial proposals describe things not yet built: the frontend and
deployment strategy, the guide builder, the page structure. This session
added a fourth, and now a fifth.

The documents have paid for themselves — they caught a live contradiction in
`meta/memory.md`, they carry the honest version of every argument, and they
made it possible to resume with full context after a compaction. But the
ratio deserves naming. Writing a design thoroughly enough can make building
it feel less urgent, and a repository can accumulate a shelf of
well-reasoned papers about software that does not exist.

**Concretely:** this session produced roughly 1,200 lines of documentation
and zero lines of committed code.

### 3.4 The environment is the least version-controlled thing in a project whose contract is about determinism

`pymupdf` is pinned exactly because identical bytes must give identical
chunks. Chunk bytes feed fixture hashes. Offline replay, the drift guard and
the staleness digests all rest on that. This is a statement about the
*environment*.

And the environment is a hand-built venv plus a DuckDB extension living in a
home directory, neither reproducible from anything in the repository. I lost
both in one session without touching them. `frontend-deployment-proposal.md`
proposes the fix (option C: carry a Dockerfile from the first UI commit, run
it once per milestone) and it is a proposal, not a file.

### 3.5 Two workstreams share one working tree, held apart by discipline

`guide_builder/` and `corpus-vessel/` sit untracked in the tree with an
explicit standing rule: *never `git add -A`*. `pyproject.toml` names a
package only partly on disk, so a fresh `pip install -e .` may break while
the running editable install does not notice.

That is a landmine sitting armed, defused only by everyone remembering. The
structural fix — a branch, a worktree, or a separate repository — costs less
than the rule does.

### 3.6 The refactor moved the projection problem rather than dissolving it

`code-structure-and-testing-recommendations.md` diagnosed that `render.py`
was also a projection layer. The refactor satisfied the letter of the
recommendation: `render.py` is now 98 lines of wiring and produces HTML from
a view model.

`projection.py` is 3939 lines holding around sixty dataclasses. The
recommendation said the projection must not produce HTML. It did not say the
projection may be one module the size of a small application, and M7.4
proposes to add a second projection beside it.

### 3.7 The measurement that reports is not converging

Seeded-Recall has sat at 14–15/25 across recordings, with ±2–3 run-to-run
noise and no agreed bar — which means it currently cannot distinguish
progress from sampling. The metric split that would make it meaningful
(relationship-style traps separately from definition-style ones) was decided
in principle on 2026-08-01 and remains unscheduled. A number reported for
months without moving and without a bar is a number that has stopped doing
work.

---

## 4. Findings verified this session

Separate from opinion. Each of these is checkable.

| finding | severity | effort |
|---|---|---|
| **No LICENSE file.** The LinkedIn post says "I put the project on GitHub." Without a license nobody may legally use, fork or contribute. | blocking for the word "open source" | hours |
| **No install or quickstart in README.** A visitor gets a product description and a roadmap table, and no way in. | blocking for any click the post earns | half a day |
| **A fresh environment needs a one-time `INSTALL fts` with network access**, undocumented in the README. I hit it; a visitor will. | high | minutes |
| **No `.github/`** — no CI configuration, no issue template, in a repository whose post invites criticism. | medium | hours |
| **`meta/memory.md` contradicts itself on M7.4**: line 105 specifies "a second projection over the same store", line 225 says "HTML report and GUI become two renderings of one projection". Unresolved, and it is a real fork. | medium — blocks 7.4 | a decision |
| **The reference resolver's table half is lossier than memory records.** Bindings carry the slug view name; `_slug` lowercases and flattens punctuation and `_sanitize` runs again on Excel sheet titles, so the original sheet name is never persisted. Splitting on `__` is safe (a slug cannot contain `__`), but "open workbook X, sheet 'Q1 – Sales'" cannot be reconstructed. Store-side work, not projection work. | medium — scopes 7.4 | small |
| **The elections already grade the guide, and nothing reads them that way.** Several candidates surviving means the definition is too loose; none surviving means the rule does not fit the business. Computed today, surfaced nowhere. | opportunity | rendering only |
| **Could not run the suite** (venv execute bits, missing FTS extension). Not a code finding. | environment | — |

---

## 5. Verdict

**The engineering is not the risk. The evidence base is.**

The epistemic core is genuinely sound, and soundness by construction rather
than by vigilance is rare enough to be the project's real asset. The
discipline around prompts, fixtures, re-recording and derived-versus-stored
state is better than most production systems I read. The positioning that
emerged this session is honest and defensible, and — unusually — the sharpest
version of the pitch describes what is already built rather than what is
planned.

What the project cannot currently say is whether any of it is *right*, in the
sense that matters to a buyer. Every number in this repository was measured
inside one synthetic landscape whose author also authored the domain guide,
the laws and the answer key. The product's own central argument is that this
arrangement cannot establish a correspondence claim. It applies to the
project as much as to a customer.

So the verdict is not about code quality. It is about where the next unit of
effort goes:

> **Stop building depth. Start buying evidence.**

Concretely, the three cheapest evidence purchases available, none of which is
a feature:

1. **The acceptance kit** (holds- and violated-fixtures for the three finance
   laws; an attractive wrong candidate per role). It is the only test of the
   product's stated central weakness, it costs one focused session, and it
   buys the one sentence the pitch most wants and cannot say — *"the ground
   rules are themselves tested."*
2. **A repository a stranger can run.** LICENSE, quickstart, the FTS note, and
   a pointer at `validation/` — which is already a deterministic, offline,
   API-key-free guided tour of a landscape with 32 seeded errors, and is
   invisible from the front page. This is the demo the post describes, and it
   exists.
3. **One real landscape.** Any data whose truth someone knows independently.
   It converts every claim in this repository from "measured on our corpus"
   to "measured", and it is the only thing that can.

Everything else — 7.4, 7.7, M8, M9 — is real work that should wait behind
those three. Not because it is wrong, but because building further on an
unvalidated base increases the cost of finding out the base was wrong.

**The one thing I would change about how the project is run:** schedule work
by what would most cheaply prove the product wrong, not by what the
dependency graph permits next. The dependency graph is currently deferring
the riskiest question to the last milestone, and the riskiest question is the
one the product exists to answer.

---

## 6. Where I might be wrong

Stated, because a verdict without its exposure is the thing this project
refuses to ship.

- **I never saw it run.** My reading of what works comes from code, tests I
  could not execute, and documentation. If the walkthrough is more convincing
  in motion than on the page, my emphasis on "buy evidence" is
  overweighted — the evidence may already be more visible than I can tell.
- **I may be undervaluing the documentation.** The proposals read to me as a
  ratio problem; they may instead be how one person keeps a system this
  intricate coherent across compactions and months. If so, §3.3 is wrong.
- **"One real landscape" may be commercially harder than I imply.** Getting a
  company to run an unfinished tool over books whose truth they know is a
  trust transaction, not a task, and the missing UI may genuinely block it.
  If that is the case, the acceptance kit carries more weight than I have
  given it, because it becomes the only available substitute.
- **I have not read the guide builder's code**, only its README, in line with
  the standing instruction not to touch it. Any judgement here about the
  commercial ranking of that workstream is based on documents alone.
