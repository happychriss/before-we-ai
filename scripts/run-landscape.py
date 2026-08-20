#!/usr/bin/env python3
"""Read a landscape with the deterministic stages only, and report what it is.

    python scripts/run-landscape.py vessel [--out DIR]

Declares the landscape's sources into a fresh project, scans them, profiles
every column, builds the candidate matrix, and chunks the documents. **No model
call, no API key**, so it costs nothing and gives the same answer every time —
running it twice over untouched bytes is itself the determinism check.

This is stage 0 and stage 2 of the spine and nothing else. It cannot say
whether the tool is *right* about a landscape; it says whether the tool can
read it at all, which is the question worth asking first about data nobody has
pointed it at before.

The answer key is never opened. Neither is the generator.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

import yaml  # noqa: E402

from corpora import load as load_landscape, names as landscape_names  # noqa: E402
from before_we_ai import read_documents, scan  # noqa: E402
from before_we_ai.profile.candidates import load_matrix  # noqa: E402
from before_we_ai.sources import open_catalog  # noqa: E402
from before_we_ai.store import ProjectStore, init_project  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("landscape", choices=landscape_names())
    parser.add_argument("--out", metavar="DIR",
                        help="build the project here and keep it (default: temp)")
    parser.add_argument("--top", type=int, default=25,
                        help="candidate matrix rows to print (default 25)")
    args = parser.parse_args()

    landscape = load_landscape(args.landscape)
    workdir = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="landscape-"))
    root = workdir / "project"
    if root.exists():
        shutil.rmtree(root)

    init_project(root, name=f"{landscape.name}-read")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = landscape.declarations()
    if landscape.guide_file:
        config["llm"] = {"domain_guide_file": str(landscape.guide_file)}
    elif landscape.guide_packaged:
        config["llm"] = {"domain_guide_file": landscape.guide_packaged}
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")

    print("=" * 78)
    print(f"{landscape.name}: {len(landscape.sources)} sources, domain "
          f"{landscape.domain}, guide "
          f"{landscape.guide_file.name if landscape.guide_file else landscape.guide_packaged}")
    print("=" * 78)

    scan(root)
    store = ProjectStore(root)

    print("\n## Tables ingested")
    con = open_catalog(root)
    try:
        views = [r[0] for r in con.execute(
            "select view_name from duckdb_views() where not internal "
            "order by view_name").fetchall()]
        columns: dict[str, list[str]] = {}
        for view in views:
            rows = con.execute(f'select count(*) from "{view}"').fetchone()[0]
            columns[view] = [d[0] for d in
                             con.execute(f'select * from "{view}" limit 0').description]
            print(f"  {view:56s} {rows:>7,} rows  {len(columns[view]):>3} cols")
        print(f"\n  {len(views)} tables from {len(landscape.sources)} sources")
    finally:
        con.close()

    print("\n## Column names, verbatim")
    for view, cols in columns.items():
        print(f"\n  {view}\n    " + " | ".join(cols))

    print("\n## Measured value classes")
    classes = Counter()
    for profile in store.profiles.values():
        stats = getattr(profile, "stats", None) or {}
        if "value_class" in stats:
            classes[stats["value_class"]] += 1
    print("  " + "  ".join(f"{k}={v}" for k, v in sorted(classes.items())))

    print("\n## Normalization declarations (evidence, actor=system)")
    for (etype, actor), n in sorted(Counter(
            (e.type.value, e.actor.value) for e in store.evidence.values()).items()):
        print(f"  {n:4d} × {etype} by {actor}")

    print(f"\n## Claims created by the scan: {len(store.claims)}"
          "   (must be 0 — nothing is proposed before a model runs)")

    print("\n## Candidate matrix — measured value overlap, never a judgement")
    matrix = load_matrix(root)
    print(f"  pairs examined: {matrix['pairs_examined']}   kept at containment "
          f"≥ {matrix['threshold']}: {len(matrix['candidates'])}")
    for warning in matrix["warnings"]:
        print(f"  WARNING: {warning}")
    for c in sorted(matrix["candidates"], key=lambda c: -c["containment"])[:args.top]:
        print(f"    {c['left']:46s} {c['right']:46s} "
              f"ov={c['overlap']:>6} cont={c['containment']:>6} jac={c['jaccard']:>6}")

    print("\n## Documents")
    result = read_documents(root)
    print(f"  profiled: {result.profiles_written}   pages: {result.pages}")
    store = ProjectStore(root)
    for profile in sorted(store.documents.values(), key=lambda d: d.document):
        kinds = ", ".join(f"{n} {k}" for k, n in sorted(profile.kinds.items()) if n)
        print(f"  {profile.document:48s} {profile.pages:>2}p  "
              f"{profile.chunk_count:>4} passages  ({kinds})")

    print(f"\nproject kept at: {root}" if args.out else "\n(temporary project)")
    if not args.out:
        shutil.rmtree(workdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
