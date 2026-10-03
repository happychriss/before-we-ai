# Run B, as it was recorded

The store the live run of 2026-10-03 left behind — claims, evidence, check
plans, questions, the request — plus every prompt and answer verbatim
(`llm_log/`) and the per-stage summaries of the three arms. Nothing here was
edited after the run.

- `project/` — the main arm's store, without its disposable `cache/`
- `llm_log/` — the model calls, verbatim, with the sha256 of each input
- `summary.json` — main arm; `summary-request.json`, `summary-control.json` —
  the other two

The statuses in `project/` are the ones the engine derived **on the day**,
before the four changes Run B led to. The demo web app loads a copy of this
store and re-runs the deterministic stages over it with the current engine, so
what it shows is the same proposals judged by today's rules. Both readings are
in `../results-run-b.md`.

Model stages cannot be replayed from here: a recording answers the input it
was recorded for.
