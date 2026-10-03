# Frontend & deployment proposal (M8)

**Status:** draft for owner decision · 2026-08-02
**Scope:** how the M8 end-user GUI is built, run locally, and put in front of
evaluators. Not a design proposal — the page structure lives in
`page-structure-thinking.md`.

> **Update 2026-08-20 — option C is partly built already, and not by M8.**
> The repository-publication work shipped a root `Dockerfile`, a `compose.yaml`
> and a CI job that builds the image on every push. That is option C's
> "Dockerfile carried and checked" discipline, except the check is a build
> rather than a per-milestone habit, so it cannot rot quietly. What remains
> for M8 is the UI layer on top, not the container decision.
>
> This file is deliberately **not committed** — it describes a UI that does
> not exist. It stays here until M8 makes it real.

---

## 1. Requirements (owner, this session)

| # | Requirement | What it rules on |
|---|---|---|
| R1 | Simple install on enterprise laptops, running locally | Distribution channel |
| R2 | Minimized build effort | Build tooling |
| R3 | Small impact from changes | Where state and rendering live |
| R4 | LLM stability — the code must be reliably machine-editable | Framework choice |
| R5 | Everything on the owner's laptop first | Sequencing |
| R6 | If it later moves local → server, that move must be small | Packaging discipline |
| R7 | One-click try-out for other people | Evaluation channel |

Two further constraints come from the product itself, not from this session:

- **The GUI is two looping workflows** (`page-structure-thinking.md`):
  Knowledge (propose → question → answer → save version → revise) and
  Assessment (dependencies → run → gaps → resolve → rerun → compare).
  Both loops end in *something became stale*.
- **Derived, never stored.** Statuses, settled slots and readiness verdicts
  are recomputed on every read.

---

## 2. Verdict

**FastAPI + uvicorn, Jinja2 templates, htmx as a single vendored and
exact-pinned file (package data, exactly like `readiness_report/static/`
today), SSE for run status. No frontend build tool: no Node, no
`package.json`, no lockfile, no `dist/`.**

### Why this, against the requirements

- **R1/R2** — `pip install` only. No npm registry allowlisting, no proxy
  negotiation, no Node runtime, no build step in CI.
- **R3** — a change lives in one place: `projection.py` → template. There is
  no second state model in the browser and no JSON API that can drift from
  the projection. The M8 seam ("consumes the M7 projection and the operation
  verbs, nothing else") stays intact by construction.
- **R4** — one language, one templating dialect, small files. htmx's surface
  is roughly six HTML attributes, so generated code is verifiable by reading
  it. FastAPI, Jinja and htmx are all heavily represented in training data.

### Why the two loops are the decisive argument

Both loops end in staleness. The server recomputes status, settled slots and
readiness on every read. A client-side framework would have to mirror that
invalidation — i.e. reimplement M7's staleness logic in JavaScript against a
JSON API that duplicates the projection. That is not an effort problem, it is
a correctness risk: a client cache showing a stale verdict after a rerun is
exactly the silent wrong answer the product forbids.

Server rendering means every action returns freshly computed state. There is
no second place where truth could live.

### Page structure → mechanism

| Page | Hardest interaction | Mechanism |
|---|---|---|
| Setup | Upload + per-source read status | `<form enctype=multipart>` + htmx swap of the status list |
| Knowledge | Answer a question → refresh question list, conflicts *and* counters | one `hx-post`, fragment back + `hx-swap-oob` for side panels |
| Knowledge | Editor for individual draft entries | one inline form per entry, no client state |
| Assessment | Long-running run, stage-by-stage status | SSE (`text/event-stream`); run in a background thread, browser subscribes by run id |
| Assessment | Resolve gap → staleness impact → rerun affected | server computes, page re-renders; no client-side diffing |
| Assessment | Compare runs | server-side comparison of two projections |
| Report | Export HTML/PDF | what the readiness report already does |
| all | Jump-to via the resolver (M8 requirement) | real URLs, because real routes |

Nothing in that table needs a bundler. The only genuinely new mechanism
versus today's readiness report is SSE for run status — plain HTTP, not a
dependency.

### Framework runner-up

**Flask** is defensible: simplest mental model, Jinja is native, the largest
training-data presence of the three. It loses on two points — Pydantic v2 is
already a core dependency (FastAPI validates request and response against the
same models as the store, for free), and SSE plus the background run are
fiddlier over synchronous WSGI.

**One FastAPI pitfall to write down now:** a blocking DuckDB call inside an
`async` route freezes the event loop. Route handlers that touch DuckDB must
be plain `def` so FastAPI runs them in a threadpool. Models reflexively write
`async def`; this needs to be a review item.

---

## 3. Local development, and keeping the move to a server small

Development runs locally via `pip install -e .` and `before-ai ui`. But a
**Dockerfile is carried from the first UI commit**, and **one run per
milestone goes through the container** — the acceptance run, not every test.

Rationale: the determinism contract (pymupdf pinned exactly, identical bytes
→ identical chunk ids) is a statement about the *environment*. Discipline
cannot guarantee it; an image can. But it does not need hourly proof, only
milestone proof.

Options considered:

| Option | Plus | Minus |
|---|---|---|
| **A** — pip only, containerize when the move happens | Fastest start, no container friction (development already runs inside a dev container, so this avoids Docker-in-Docker) | The move is small but **unproven**. Local assumptions surface all at once, and a differing pymupdf environment on the server means re-recorded fixture hashes |
| **B** — Docker from day 1, same image locally and on the server | Move is nearly free (push the image); the four seams below cannot silently break; determinism guaranteed rather than hoped | Daily friction: Docker-in-Docker, slower test loop, rebuilds on dependency changes. Paid every day for a benefit redeemed once |
| **C** — pip daily, Dockerfile carried and checked per milestone **(chosen)** | Day-to-day speed of A with the proof of B at the only point that matters | Requires discipline; a Dockerfile nobody runs daily rots quietly if the milestone run is skipped |

If the per-milestone container run cannot be held reliably, take **B** over
**A** — unproven is worse than inconvenient.

### The four seams that make the move small

Close these and the move is a ten-line Dockerfile. Leave them open and it is
an afternoon of hunting.

1. Project root comes from config/env, never hardcoded
2. The API key comes from `os.environ` — set locally by `with-api-key.sh`, a
   secret on the server; the application cannot tell the difference
3. No state outside the store directory (already true: `cache/` is disposable)
4. Bind address and port from config — `127.0.0.1` locally, `0.0.0.0` in a
   container

---

## 4. Deployment options

The same application serves all three channels. No second build, no second
codebase — that is the payoff of server-side rendering.

### Option 1 — Hosted URL (recommended for try-out)

Fly.io Machines, scale-to-zero, demo dataset preloaded, Basic Auth or
`fly proxy` instead of a public listener.

- **Plus:** genuinely one click. No installation, no admin rights, no code
  signing certificate. Works on any managed laptop. Central updates mean all
  feedback arrives against one version. One image also *improves* the
  determinism guarantee.
- **Minus:** needs a Fly Volume — the store is a directory tree with
  append-only `evidence/`, so without a volume all project state is lost on
  machine restart. One machine, no horizontal scaling. `shared-cpu-1x` at
  256 MB is not enough for DuckDB profiling over Excel — plan 1–2 GB.
  The API key sits permanently in a machine environment, which departs from
  the current process-scoped key discipline. A `*.fly.dev` URL may be blocked
  by web-proxy categorisation; a custom domain with proper TLS materially
  improves the odds.

### Option 2 — `uvx` one-liner (for the owner and technical colleagues)

`uvx before-we-ai ui`, optionally wrapped in a `.cmd`/`.command` file to make
it double-clickable.

- **Plus:** minimal build effort (publish to PyPI or an internal index). No
  admin rights needed — uv installs into the user profile and brings its own
  Python. Data never leaves the laptop, so this channel also works for real
  data.
- **Minus:** **not a viable evaluation channel in a regulated enterprise.**
  It needs proxy egress to `pypi.org`, `files.pythonhosted.org` and the
  `astral-sh` GitHub releases; it executes an unknown binary from the user
  profile, which is the exact pattern AppLocker/WDAC and EDR are tuned for;
  and in a GxP/SOX-governed company, installing software outside the approved
  catalogue is a policy violation even when it technically succeeds. The
  evaluator will not report "policy", they will report "it doesn't work".

  *One question settles this for any given company:* "Is there an internal
  PyPI mirror (Artifactory/Nexus), and is Python already provisioned on the
  laptops?" Two yeses make the local path plausible — and then `pip install`
  against the internal index is enough, without uv at all.

### Option 3 — Signed installer (deferred)

PyInstaller/Nuitka plus a code-signing certificate.

- **Plus:** the only variant that works for a non-technical end user *and*
  with real data. This is the eventual product form.
- **Minus:** a work package of its own. Certificate cost and annual renewal,
  macOS notarisation on top, one build per platform, a 150–250 MB binary
  because of DuckDB and pymupdf, and PyInstaller artefacts routinely trigger
  antivirus false positives. Vastly oversized for "let people have a look".

  Note: bundling was never the blocker — signing and policy were. Desktop
  packaging helpers (including NiceGUI's) produce the same unsigned artefact
  that SmartScreen intercepts.

### Recommendation

**Option 1 for try-out, Option 2 for the owner and technical colleagues,
Option 3 only when a paying customer requires it.**

**The spec `:42` acceptance run stays local.** Real data whose truth the owner
knows does not leave the laptop.

---

## 5. Preconditions — before the first UI line

1. **The four seams** (section 3), closed from the start
2. **Run id + background thread**, so the long-running assessment run does not
   hang off an HTTP request
3. **One project directory per tester.** The store is a directory tree with
   append-only `evidence/`. Two concurrent testers on one machine write into
   the same files and see each other's answers — that corrupts the evidence
   chain, it is not a cosmetic flaw. Cheapest clean solution for the POC: a
   path prefix chosen at entry or derived from the access link, with the demo
   dataset copied in on first use. No tenancy model, no login system.

---

## 6. Rejected, with the reason

- **SPA (React/Vue/Svelte as the foundation)** — duplicates M7's staleness
  logic in the client and turns an effort question into a correctness risk.
  Also needs a JSON API that duplicates the projection, plus a router to
  recover the deep links that routes give for free.
- **NiceGUI as the foundation** — weakest LLM stability of the candidates
  (niche, moving API, thin training-data presence); server-held per-client UI
  state reintroduces the manual invalidation that server rendering avoids;
  and Jinja would still be needed for the report and the export, leaving two
  rendering systems in one project. Its desktop-packaging story does not help,
  because signing was the blocker, not bundling.
- **Next.js/Nuxt** — a Node runtime as a second process next to Python.
- **Electron** — installer, signing, update channel: the most expensive path
  on managed laptops.
- **Webpack** — configuration burden with no benefit at this scale.

## 7. Escape hatches (nothing here is a dead end)

If one page turns out to be genuinely awkward in htmx — the Knowledge editor
is the candidate, if it grows into multi-entry editing with live validation —
that **single page** becomes an island: either a Svelte bundle built once and
committed, or a NiceGUI page mounted into the same app (NiceGUI runs on
FastAPI itself). No rewrite of the rest.

Choosing FastAPI forecloses nothing. Choosing NiceGUI as the foundation would.

---

## 8. Open for owner decision

- Confirm the verdict and Option C for the local/server discipline
- Confirm hosted-demo-only for try-out, with `:42` staying local
- Whether the API key on a hosted machine is acceptable for the demo channel
  (it departs from process-scoped key handling)
- Whether to record this in `meta/memory.md` as M8 preparation, with a route
  list per page and the run-id/SSE model
