"""A fresh project declared over the frozen corpus — the one construction.

Three callers need it and none of them is a test: the owner walkthrough
(`validation/scripts/_steps.py`) and the two online tools that live under
`src/tests/eval/` (`refresh_fixtures.py`, `seeded_recall.py`, run as scripts,
never collected). Keeping it here rather than under `tests/` is what stops
owner-facing validation from depending on test-internal code.

The corpus *data* it points at is still `src/corpus/data/` — frozen, and the
one thing every offline run measures against.
"""

from pathlib import Path

import yaml

from before_we_ai import scan
from before_we_ai.domains import packaged
from before_we_ai.store import init_project

SRC = Path(__file__).resolve().parents[2] / "src"
CORPUS = SRC / "corpus" / "data"
FIXTURES = SRC / "tests" / "fixtures" / "llm"
DOMAIN_GUIDE_FILE = packaged("finance")
EXPECTED_VERDICTS = CORPUS / "expected_verdicts.yaml"

SOURCES = [
    {"name": "de_erp", "kind": "duckdb", "location": str(CORPUS / "DE" / "erp.duckdb")},
    {"name": "us_erp", "kind": "duckdb", "location": str(CORPUS / "US" / "erp.duckdb")},
    {"name": "kunden_migration", "kind": "xlsx", "location": str(CORPUS / "kunden_migration.xlsx")},
    {"name": "marketing_grouping", "kind": "xlsx", "location": str(CORPUS / "marketing_grouping.xlsx")},
    {"name": "kontakte_aussendienst", "kind": "xlsx",
     "location": str(CORPUS / "kontakte_aussendienst.xlsx")},
    {"name": "buchungen_report", "kind": "csv", "location": str(CORPUS / "buchungen_report.csv")},
    {"name": "management_report", "kind": "pdf", "location": str(CORPUS / "management_report.pdf")},
]


def build_corpus_project(root: Path, *, offline: bool,
                         scan_now: bool = True) -> Path:
    """Declare a fresh project over the frozen corpus, and scan it.

    ``scan_now=False`` stops after the declarations — the walkthrough needs
    that split, because its stage 0 (the request) and stage 1 (the declared
    inputs) both come before anything is measured.
    """
    init_project(root, name="seeded-recall")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = SOURCES
    llm_block = {"domain_guide_file": str(DOMAIN_GUIDE_FILE)}
    if offline:
        llm_block |= {"offline": True, "fixtures_dir": str(FIXTURES)}
    config["llm"] = llm_block
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    if scan_now:
        scan(root)
    return root
