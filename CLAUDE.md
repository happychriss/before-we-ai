# CLAUDE.md

## Session Bootstrap

At the start of every session — and after any context compaction — read, in order:

1. `docs/requirements.md` — what is being built + per-feature status (canonical)
2. `meta/*.md` — process conventions, project rules, live state (`meta/memory.md`)
3. `docs/architecture.md` + `docs/corpus.md` — confirmed design decisions and gotchas

These are sufficient to resume work with full context.

## Repository layout & one fact, one home

Every piece of information has exactly one canonical file; other files may link to it
but never restate it:

- `src/` — all code (Python package, corpus, tests; `pyproject.toml` lives here —
  install/test from `src/`)
- `docs/` — everything about the software: `requirements.md` (WHAT + status),
  `architecture.md` / `corpus.md` (confirmed design facts & gotchas),
  `SIMPLE-README.md` (plain-German explainer, grows per milestone),
  `spec/` (authoritative German spec — read-only, never edit)
- `meta/` — how we work, not what we build: `project-setup.md` (workflow),
  `conventions.md` (project rules), `memory.md` (live state only — slim it when
  items become durable), environment notes
- `scripts/` — (reserved, added later) self-contained ops scripts: start the
  process, claim viewer, cleanup of stale processes; runnable directly after login
- `README.md` — human-facing product front page (exempt: may summarize)

When recording something new, place it in its home and update — don't append copies.

## Runtime Environment

You are running inside a **Docker dev container** (Ubuntu, non-root user `ubuntu`):
- You have direct access to the filesystem and shell
