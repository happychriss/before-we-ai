# Landscapes

A **landscape** is a body of business data with a known answer. Not a dataset:
a dataset is rows, a landscape is rows *plus* what a person would have to know
to read them correctly, *plus* a record of which of those things were
deliberately made hard.

Two live here.

| | `finance/` | `vessel/` |
|---|---|---|
| what it is | a two-entity ERP export with CSV, Excel and PDFs around it | ten business documents from a shipbuilder, no database at all |
| who built it | the same people who built the tool, **before** the tool existed | someone else, for a different purpose |
| seeded errors | 32 (F1–F29 + 3 the owner holds back) | held in its answer key, not read |
| status | **frozen** — every recorded number is scored against these bytes | **frozen** |
| what it proves | that the machine finds what an author knew to hide | that a good score on `finance/` was not familiarity |

The second one matters more than its size suggests. A tool measured only on the
corpus its authors wrote can always be explained away: of course it does well,
it grew up there. `vessel/` is the control for that, and it is the only reason
any number from `finance/` can be quoted to an outsider.

## What is in a landscape

```
<name>/
  manifest.yaml     everything about it that anything else needs to know
  data/             the business files, exactly as a company would hand them over
  guide/            a domain guide, if this landscape needs its own
  spec/             what the generator was told to build (finance only)
  generator/        the code that built it            ← DO NOT READ
  answer-key/       what the right answers are        ← DO NOT READ
```

`manifest.yaml` is the single home for the facts: the source list with a
description and a sha256 per file, which domain guide reads it, which questions
it is designed to answer, where the answer key lives. Nothing else hardcodes a
path into a landscape — `corpora/__init__.py` resolves it:

```python
from corpora import load
finance = load("finance")
finance.declarations()            # the source block for a before-ai.yaml
finance.path("DE/erp.duckdb")     # a file inside data/
finance.of_kind("pdf")            # the six documents
```

The sha256 per file is the freeze, and
`src/tests/corpus_driven/test_corpus_is_frozen.py` enforces it in both
directions: no pinned file may change, and no file may appear in `data/` that
no manifest pins.

## The reading rule

**Never open `answer-key/` or `generator/`.** Not to check something, not to
confirm a hunch, not "just this one file". Both contain the seeded errors —
the answer key states them, the generator is the code that placed them.

This is not secrecy; the files are committed and anyone can read them. It is
that a measurement made by someone who has seen the answers measures nothing.
The owner cannot be blind to a landscape he commissioned, and does not need to
be — the people and the agents doing the implementation can, and that is where
the value is. Encryption would protect nothing here anyway: the generator has
to stay, or the corpus is not reproducible.

What replaces secrecy is **pre-registration**. Before a scored run, write down
what you expect and what would count as a failure, and commit that first. A
prediction made before the run is evidence; the same sentence written after it
is a story.

## Adding a third landscape

1. `mkdir corpora/<name>/{data,answer-key,generator}` and put the files in.
2. Write `manifest.yaml`. Copy `vessel/manifest.yaml` — it is the shorter of
   the two and the one a new landscape looks like. Required: `name`, `domain`,
   `frozen`, `domain_guide` (either `packaged: <pack>` or
   `file: guide/<file>.yaml`), `answer_key`, `generator`, and `sources` with a
   `name`, `kind`, `path`, `sha256` and `description` each.
   Compute the hashes rather than typing them:
   ```bash
   python - <<'PY'
   import hashlib, pathlib
   for p in sorted(pathlib.Path("corpora/<name>/data").rglob("*")):
       if p.is_file():
           print(p.relative_to(p.parents[1] / "data"),
                 hashlib.sha256(p.read_bytes()).hexdigest())
   PY
   ```
3. Run `pytest -q -k frozen`. The freeze test picks the landscape up by itself;
   if it fails, the manifest and the directory disagree.
4. Run `python scripts/publication-scan.py`. It also picks the landscape up by
   itself, and it will refuse anything that looks like a real identity.

That is the whole procedure. The point of the layout is that step 2 is the only
place a fact about the new landscape gets written down.

## What is *not* here

The grading harness — the invariant checks, the trap-class assertions, the
validation report builder — is code, so it lives in `src/corpus/`. A landscape
is data.
