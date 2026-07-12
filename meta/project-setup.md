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

## 1. Folder Structure

`/workspace` is the git repo root (one repo for everything):

```
/workspace/
├── CLAUDE.md        # bootstrap + one-fact-one-home rule (canonical folder definitions)
├── README.md        # human-facing product front page
├── src/             # all code (pyproject.toml lives here; install/test from src/)
├── docs/            # everything about the software:
│   ├── requirements.md   #   what + status (canonical)
│   ├── architecture.md   #   confirmed design decisions & gotchas
│   ├── corpus.md         #   frozen corpus facts
│   ├── SIMPLE-README.md  #   plain-German explainer, grows per milestone
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
- Gotchas and confirmed detail belong in `docs/`; feature status in `docs/requirements.md`

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
