"""Which recorded answer is pinned by which guard — the one list.

The drift guard is only as good as its coverage, and coverage used to be
asserted by a **prefix**: `test_no_fixture_escapes_the_drift_guard` waved
through anything called `v3_documents__*` on the grounds that the
documents file pinned it. It did not. That file's project declares the
three PDFs its acceptance traps need, so three of the six recorded
document answers were checked by nobody, and the two `tell` fixtures
shipped unpinned for the same reason — a statement is not a document, so
iterating ``store.documents`` never reached them.

A prefix cannot express "and something actually checks it". So the two
sides now meet on one list: the guards iterate what is declared here, and
the escape guard asserts the shipped files are exactly the names this
module produces. A new fixture is then either declared and checked, or
red — never silently inherited.

This is not a test module. It holds no assertions; it holds the facts
both test modules have to agree on.
"""

from pathlib import Path

import yaml

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"
FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "llm"

# Every PDF a document fixture was recorded for — the walkthrough's six,
# not the acceptance file's three. The recorder writes one call per
# document, so this list and the fixture directory are the same fact
# twice, and the escape guard is what keeps them that way.
PDF_SOURCES = [
    {"name": "management_report", "kind": "pdf",
     "location": str(CORPUS / "management_report.pdf")},
    {"name": "buchhaltungsrichtlinie", "kind": "pdf",
     "location": str(CORPUS / "buchhaltungsrichtlinie.pdf")},
    {"name": "rabattvertrag", "kind": "pdf",
     "location": str(CORPUS / "rabattvertrag.pdf")},
    {"name": "lieferantenkatalog", "kind": "pdf",
     "location": str(CORPUS / "noise" / "lieferantenkatalog.pdf")},
    {"name": "pressemitteilung_2022_divested_unit", "kind": "pdf",
     "location": str(CORPUS / "noise" / "pressemitteilung_2022_divested_unit.pdf")},
    {"name": "reisekostenrichtlinie", "kind": "pdf",
     "location": str(CORPUS / "noise" / "reisekostenrichtlinie.pdf")},
]

STATEMENTS_SPEC = CORPUS / "tell_statements.yaml"

# The questions the pipeline is recorded against, and the scenario each one
# is filed under. One home for them: the recorder asks them, the drift guard
# rebuilds their inputs, and the two used to be separate constants held
# byte-identical by a comment asking nicely.
#
# Two of them, and that is the point. With one answer type declared,
# classification had nothing to get wrong — every question landed on the only
# entry there was. The second question is deliberately a near neighbour: also
# about money in the ledger, naming no table, sharing three of its
# dependencies with the first.
REQUEST_SCENARIOS: list[tuple[str, str]] = [
    ("corpus", "Can these files reliably produce actual P&L by entity and month?"),
    ("corpus_receivables", "What is still outstanding from our customers?"),
]

# The contracts whose fixtures are pinned in test_llm_offline_corpus.py.
GUARDED_IN_THE_LLM_FILE = frozenset(
    {f"request__{scenario}" for scenario, _ in REQUEST_SCENARIOS}
    | {
        "v1_hypotheses__corpus",
        "role_binding__corpus",
        "v2_bind__corpus_roles",
        "v2_bind__corpus_claims",
    }
)


def question(scenario: str) -> str:
    """The question one request scenario was recorded for."""
    return next(text for name, text in REQUEST_SCENARIOS if name == scenario)


def statement_scenarios() -> list[tuple[str, str]]:
    """The K8 statements, id and text, in the order the corpus lists them."""
    spec = yaml.safe_load(STATEMENTS_SPEC.read_text(encoding="utf-8"))
    return [(entry["id"], entry["text"]) for entry in spec["statements"]]


def document_fixture(document: str) -> str:
    return f"v3_documents__corpus__{document}"


def statement_fixture(statement_id: str) -> str:
    return f"v3_documents__corpus_{statement_id.lower()}__statements"


def guarded_in_the_documents_file() -> frozenset[str]:
    """Every fixture test_documents_offline_corpus.py pins, by name.

    Derived from the same two lists its guards iterate, so it cannot claim
    coverage the guards do not deliver — that was the whole defect.
    """
    return frozenset(
        {document_fixture(source["name"]) for source in PDF_SOURCES}
        | {statement_fixture(sid) for sid, _ in statement_scenarios()}
    )


def all_guarded() -> frozenset[str]:
    return GUARDED_IN_THE_LLM_FILE | guarded_in_the_documents_file()
