#!/usr/bin/env python3
"""Check an answer's figures against the ledger, claim by claim.

    python scripts/check-answer.py <project-dir> <claims.json>

The project must have been scanned (its catalog holds the views). No model
is called. See `before_we_ai/answer_check.py` for what is and is not checked.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from before_we_ai.answer_check import check_answer  # noqa: E402
from before_we_ai.sources import open_catalog  # noqa: E402
from before_we_ai.store import ProjectStore  # noqa: E402

MARK = {"verified": "data ", "document": "quote", "unsupported": "NONE ",
        "refuted": "WRONG"}


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    root, claims = Path(sys.argv[1]), Path(sys.argv[2])
    store = ProjectStore(root)
    documents = {s.name: Path(s.location) for s in store.sources.values()
                 if s.kind == "pdf"}
    con = open_catalog(root)
    try:
        result = check_answer(con, json.loads(claims.read_text()), documents)
    finally:
        con.close()

    print("claims")
    for c in result.claims:
        print(f"  [{MARK[c.status]}] {c.id:4s} {c.says}")
        print(f"          {c.found}")
    print("\nfigures")
    for f in result.figures:
        rests = ", ".join(f"{n} by {k}" for k, n in sorted(f.rests_on.items()))
        state = "reproduced" if f.reproduced else (
            f"NOT reproduced: the ledger and these corrections give "
            f"{f.computed:,.0f}")
        print(f"  {f.label}")
        print(f"      stated {f.stated:>12,.0f}   ledger {f.base:>12,.0f}   "
              f"{state}")
        print(f"      rests on: {rests or 'the ledger total alone'}")
    for problem in result.problems:
        print(f"\n  problem: {problem}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
