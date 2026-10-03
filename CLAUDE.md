# CLAUDE.md

## Session Bootstrap

At the start of every session — and after any context compaction — read, in order:

1. `README.md` — what is being built + roadmap with per-milestone status (canonical)
2. `meta/*.md` — process conventions, project rules, live state (`meta/memory.md`)
3. `docs/architecture.md` + `docs/corpus.md` — confirmed design decisions and gotchas

These are sufficient to resume work with full context. The canonical vocabulary
lives in `src/before_we_ai/glossary.py` — use those words, never synonyms.

## Repository layout & one fact, one home

Every piece of information has exactly one canonical file; other files may link to it
but never restate it:

- `src/` — all code (Python package, corpus grading harness, tests).
  `pyproject.toml` lives at the repository root — install and run the tests
  from there
- `corpora/` — the landscapes, as data: one directory per landscape, each with
  a `manifest.yaml` that is the only place its facts are written down. Its
  `README.md` is the canonical definition of what a landscape is and carries
  the standing rule: **never open a landscape's `answer-key/` or
  `generator/`**
- `docs/` — everything about the software:
  `before-ai-concept.md` (plain-language walkthrough of the whole flow, one
  concept at a time, each tied to its real code object),
  `architecture.md` (confirmed design, component detail, operations),
  `corpus.md` (test-corpus facts & gotchas),
  `seeded-recall.md` (method + current measurement),
  `spec/` (authoritative German spec — edit only on explicit owner decision)
- `meta/` — how we work, not what we build: `project-setup.md` (workflow),
  `conventions.md` (project rules), `memory.md` (live state and open points —
  forward-looking only; move durable facts into docs/), environment notes
- `scripts/` — self-contained ops scripts, runnable directly after login:
  `with-api-key.sh` (the only way the Anthropic key reaches a process);
  start the process, readiness report, cleanup of stale processes to follow
- `ui/` — the demo web app (FastAPI + Jinja, server-rendered, no build step):
  `pipeline.py` (the run, step by step), `views.py` (what the pages show —
  read from the store, never deciding a status), `app.py` (routes and human
  acts), `templates/`, `static/`. Started by `scripts/ui.sh`; its project lives
  in `ui-data/` (git-ignored). It imports the engine and never the reverse
- `validation/` — owner-facing validation walkthrough: `README.md` (the test
  steps) + `scripts/` (runnable stage & report tools); `data/` is generated
  and git-ignored
- `README.md` — human-facing product front page AND the one home of feature
  status (roadmap table; exempt from no-restating: may summarize)

When recording something new, place it in its home and update — don't append copies.

## Runtime Environment

The project runs directly on the host from this folder — no container:
- `.venv/` at the repository root (Python 3.13), built by `scripts/bootstrap.sh`
- everything is offline after bootstrap; recorded model answers are replayed
