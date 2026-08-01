"""Shared support for owner-facing runs over the frozen corpus.

Not tests, and not product code. The walkthrough (`validation/scripts/`) and
the two online tools (`src/tests/eval/refresh_fixtures.py`,
`seeded_recall.py`) all need the same thing: a fresh project declared over
`src/corpus/data/`. That construction used to live under `tests/eval/`, which
made owner-facing validation depend on test-internal code — the wrong
direction. It lives here instead, where its consumers are.

`src/before_we_ai/` must never import this (guarded by
`tests/unit/test_layering.py`): the product does not know the corpus exists.
"""
