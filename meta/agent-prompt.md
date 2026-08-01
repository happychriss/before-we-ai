# Hand-off prompt for an external coding agent

Paste the block below, with `<<PACKAGE>>` replaced by exactly one work
package (`WP4`, `WP5a`, `WP5b`, `WP5c`). **One package per session** — the
gates only mean something if each is reviewed on its own.

---

You are working in the `before-we-ai` repository. Before changing anything,
read in this order: `CLAUDE.md`, then `meta/refactor-workorder.md` (your
assignment), then `meta/conventions.md`.

Your task is **<<PACKAGE>> and nothing else.** Do not start the next package.
Do not do anything the work order lists as out of scope, however obviously
right it looks.

**First, establish the baseline:**

```
cd src && source ../.venv/bin/activate && python -m pytest -q
```

Write that number down. At the end it must be the same or higher — a package
may add tests, never lose them.

**Five things that override any instinct to improve:**

1. **Never make a test pass by changing what it asserts.** Not by relaxing a
   comparison, not by deleting a case, not by adding a skip. If a test is
   red, either your change is wrong or you have found something — both mean
   stop and report.
2. **Never reword a sentence a user can see.** Derived verdicts, `because`
   texts, report prose, glossary entries, the walkthrough's printed
   explanations. These are the product; someone chose every word. Refactors
   *move* sentences. A diff that improves a sentence is a failed diff.
3. **Do not touch** `src/tests/fixtures/**`, `src/before_we_ai/llm/prompts.py`,
   `src/before_we_ai/llm/inputs.py`, or `docs/spec/**`. Prompt bytes are
   frozen; the fixtures prove it.
4. **No new dependencies.** `jinja2`, `pydantic`, `pyyaml`, `duckdb`,
   `openpyxl` are already declared. Nothing else.
5. **English only**, matching the comment density and idiom of the file you
   are in. This codebase explains *why*, not *what* — read the docstrings
   before you move code; they usually say what you are allowed to change.

**Stop and report rather than work around.** Say which file, which test, and
what you were attempting. Do this when:

- a test fails and the cause is not plainly inside your own change;
- the drift guard (`test_fixtures_match_current_inputs`) goes red;
- finishing the package would require rewording something a user sees;
- the work order says something the code contradicts. The work order has
  been wrong before and saying so is the useful outcome, not a failure.

**No drive-by fixes.** If you notice something wrong outside your package,
write it in your final report. Do not fix it. A small reviewable diff is
worth more than a correct one nobody can check.

**Work in visible steps.** Commit per logical step with a message that says
*why*, not *what changed*. Run the full suite before each commit.

**Finish by reporting, in this order:**

1. suite count before and after;
2. each acceptance check from the work order for this package, with the
   command you ran and its output;
3. `git diff --stat` against your starting point;
4. anything you noticed and deliberately did not touch;
5. anything you were unsure about.

An honest "I could not complete step 3 because X" is a good outcome. A green
suite that hides a weakened test is not.
