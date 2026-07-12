"""Shared setup for the online eval tools: corpus project construction.

Corpus knowledge stays test-side — these tools live under tests/ and are
run as scripts from src/ (``python tests/eval/seeded_recall.py``), never
collected by pytest (no ``test_`` prefix).
"""

from pathlib import Path

import yaml

from before_we_ai import scan
from before_we_ai.store import init_project

SRC = Path(__file__).resolve().parents[2]
CORPUS = SRC / "corpus" / "data"
FIXTURES = SRC / "tests" / "fixtures" / "llm"
ROLES_FILE = SRC / "tests" / "fixtures" / "roles_finance.yaml"
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


def build_corpus_project(root: Path, *, offline: bool) -> Path:
    """Init + scan a fresh project over the frozen corpus."""
    init_project(root, name="seeded-recall")
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = SOURCES
    llm_block = {"roles_file": str(ROLES_FILE)}
    if offline:
        llm_block |= {"offline": True, "fixtures_dir": str(FIXTURES)}
    config["llm"] = llm_block
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    scan(root)
    return root
