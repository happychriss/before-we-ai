---
name: project-setup
description: Working conventions for this project — folder structure, knowledge flow, and development workflow
---

# Project Setup

## 0. Environment Setup

Run once to ensure `~/.local/bin` (where tools like `claude` install) is on the PATH:

```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

This is required when `claude install` warns that the install location is not in PATH.

---

## 0b. Running the tests — the lanes

```bash
cd <clone root> && source .venv/bin/activate
python -m pytest -q                    # the gate: everything must pass
python -m pytest -m unit -q            # ~0.5s — pure logic
python -m pytest -m "unit or integration" -q
python -m pytest -m contract -q        # prompts, schemas, fixtures, drift
python -m pytest -m acceptance -q      # the frozen corpus, ~12s
```

**The full suite is the release gate and nothing replaces it.** The lanes
exist so a red test says what *class* of thing broke, and so an edit to pure
logic does not wait on the corpus. What each lane owns is registered in
`pyproject.toml` at the clone root; the rule of thumb:

| lane | owns | run it when you touched |
|------|------|-------------------------|
| `unit` | pure functions, validation, derivation | core, semantics, expansion, glossary, stages |
| `integration` | package boundaries over a temp project store | store, engine, readiness, the report |
| `contract` | the model-facing interface | prompts, schemas, fixtures — **includes the drift guard** |
| `acceptance` | the product promise on the frozen corpus | anything, before pushing |

Two things to know:

- **Every test module declares one lane** (`pytestmark = pytest.mark.<lane>`
  under the imports), and `tests/unit/test_lanes.py` fails if one does not.
  A module in no lane would be silently skipped by every lane run — a green
  nobody earned.
- **`--strict-markers` catches a typo in a declaration**, not in the command.
  `pytest -m unt` does not fail; it deselects everything and reports
  "460 deselected". Read the count, not just the colour.

`tests/eval/` holds runnable tools, not tests — `refresh_fixtures.py` and
`seeded_recall.py` talk to a live model and cost money. They carry no
`test_` prefix and are never collected.

---

## 1. Folder Structure

`/workspace` is the git repo root (one repo for everything):

```
/workspace/
├── CLAUDE.md        # bootstrap + one-fact-one-home rule (canonical folder definitions)
├── README.md        # human-facing product front page
├── pyproject.toml   # package + pytest config (install/test from the root)
├── src/             # all code (Python package, corpus, tests)
├── docs/            # everything about the software:
│   ├── architecture.md   #   confirmed design decisions & gotchas
│   ├── corpus.md         #   frozen corpus facts
│   ├── before-ai-concept.md  #   plain-language walkthrough of the flow
│   └── spec/             #   authoritative external spec (read-only, never edit)
├── meta/            # how we work: this file, conventions.md, memory.md, env notes
└── scripts/         # (added later) self-contained ops scripts: start, viewer, cleanup
```

Do not create READMEs inside `docs/`, `meta/`, or `scripts/` — folder purposes are
defined once, in `CLAUDE.md` ("one fact, one home"), and the files are self-describing.

---

## 2. Knowledge Flow

This is the rule for where project knowledge lives:

```
docs/spec/            →    docs/*.md              →    meta/memory.md
(reference material)       (confirmed facts)           (live state only)
```

### docs/spec/
- Drop zone for external material: specs, API docs, vendor docs
- Never edit these files
- When the user adds a file here, analyse it and create or update the corresponding `docs/` note

### docs/ (architecture.md, corpus.md, topic files)
- The single source of truth — not memory.md
- Knowledge learned from working on this project, mistakes made and how they were fixed

### meta/memory.md
- Live state only: current focus + open items that change session to session
- Gotchas and confirmed detail belong in `docs/`; feature status in the `README.md` roadmap table

---

## 3. Analysing a New Doc

When the user adds a file to `docs/spec/`:

1. Read it fully
2. Extract: key concepts, configuration, API details, any quirks or caveats
3. Create `docs/<topic>.md` with structured notes
4. Mark unconfirmed values clearly: `# unconfirmed — from docs`
5. Tell the user what was captured and what needs validation

---

## 4. Write-Back Rule

At the end of any session where behaviour was confirmed experimentally:
1. Update the relevant `docs/` file with the confirmed values
2. Trim `meta/memory.md` back to live state — no detail that now has a durable home
