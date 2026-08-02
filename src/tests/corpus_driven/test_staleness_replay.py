"""M7 acceptance (spec :69): mutate the corpus, watch the flags travel.

The frozen corpus is the one data set whose truth is known, so it is where
the staleness loop has to be shown end to end rather than on a fixture
built to make it work. The story is the one an analyst actually lives
through:

1. The journal balances per document — the Z4 invariant passes and the
   role binding is *test-supported*.
2. Somebody posts a correction. One amount changes; the row count, the
   columns and the latest date do not.
3. The next scan notices. The passing reading is marked stale, the binding
   falls back to *proposed*, and the reason names the table.
4. The re-run judges the data as it now is: the journal no longer
   balances, the binding is *contradicted*, and a question card carries
   the size of the problem.
5. The correction is reversed. The failing reading goes stale and the card
   says the number on it is out of date.
6. The re-run clears it.

The mutation is chosen by seed, not by hand: the point is that any posting
does this, not that one carefully picked one does. The corpus files
themselves are never touched — the project works on a copy, and the frozen
originals stay frozen.
"""

import random
import shutil
from pathlib import Path

import duckdb
import pytest
import yaml

from before_we_ai import scan
from before_we_ai.core import Actor, ClaimStatus, EvidenceType
from before_we_ai.core.objects import CheckPlan, MappingClaim
from before_we_ai.engine import run_ready
from before_we_ai.sources import open_catalog
from before_we_ai.store import ProjectStore, init_project

pytestmark = pytest.mark.acceptance

CORPUS = Path(__file__).resolve().parents[2] / "corpus" / "data"
JOURNAL = "de_erp__gl_postings"
SEED = 7


@pytest.fixture(scope="module")
def project(tmp_path_factory):
    """The DE entity, copied so the corpus stays frozen, scanned once."""
    root = init_project(tmp_path_factory.mktemp("replay") / "corpus-replay",
                        name="corpus-replay")
    database = root / "sources" / "erp.duckdb"
    shutil.copy(CORPUS / "DE" / "erp.duckdb", database)
    config = yaml.safe_load((root / "before-ai.yaml").read_text(encoding="utf-8"))
    config["sources"] = [
        {"name": "de_erp", "kind": "duckdb", "location": "sources/erp.duckdb"},
    ]
    (root / "before-ai.yaml").write_text(yaml.safe_dump(config, sort_keys=False),
                                         encoding="utf-8")
    scan(root)

    store = ProjectStore(root)
    binding = store.add_claim(MappingClaim(
        statement=f"Rolle journal = {JOURNAL}", created_by=Actor.AI, role="journal",
        binding={"table": JOURNAL, "amount_local": "amount_local_currency",
                 "doc_ref": "document_reference"},
    ))
    store.save_check_plan(CheckPlan(
        template="balance", claim_id=binding.id,
        params={"journal": JOURNAL, "amount": "amount_local_currency",
                "group_column": "document_reference"},
    ))
    _sweep(root)
    return root, binding.id, database


def _sweep(root: Path) -> None:
    con = open_catalog(root)
    try:
        run_ready(ProjectStore(root), con)
    finally:
        con.close()


def _correction(database: Path, seed: int) -> float:
    """Post a correction to one posting, chosen by seed.

    Returns the amount it had before, so the test can put it back — the
    reverse of a real correction, and the only honest way to show that the
    loop closes rather than merely moves on.
    """
    con = duckdb.connect(str(database))
    try:
        ids = [row[0] for row in con.execute(
            "SELECT posting_id FROM gl_postings ORDER BY posting_id").fetchall()]
        posting = random.Random(seed).choice(ids)
        before = con.execute(
            "SELECT amount_local_currency FROM gl_postings WHERE posting_id = ?",
            [posting]).fetchone()[0]
        con.execute(
            "UPDATE gl_postings SET amount_local_currency = ? WHERE posting_id = ?",
            [float(before) + 100.0, posting])
        return posting, before
    finally:
        con.close()


def _restore(database: Path, posting: str, amount: float) -> None:
    con = duckdb.connect(str(database))
    try:
        con.execute(
            "UPDATE gl_postings SET amount_local_currency = ? WHERE posting_id = ?",
            [amount, posting])
    finally:
        con.close()


def _live_results(store: ProjectStore, claim_id: str):
    return [record for record in store.evidence_for(store.claims[claim_id])
            if record.type is EvidenceType.CHECK_RESULT and not record.stale]


def _card(store: ProjectStore):
    return next((card for card in store.questions.values()
                 if JOURNAL in card.question), None)


def test_the_staleness_loop_end_to_end(project):
    """One test, deliberately: this is a sequence, and a sequence split
    into six independent tests stops being the thing that was promised."""
    root, claim_id, database = project

    # 1 — the invariant holds, and the binding rests on it.
    store = ProjectStore(root)
    assert store.claims[claim_id].status is ClaimStatus.TEST_SUPPORTED
    assert _card(store) is None

    # 2/3 — a correction lands, and the next scan sees past it.
    posting, before = _correction(database, SEED)
    flagged = scan(root).stale
    reasons = [reason for _id, reason in flagged.flagged]
    assert f'values in "{JOURNAL}" have changed since this ran' in reasons

    store = ProjectStore(root)
    assert store.claims[claim_id].status is ClaimStatus.PROPOSED
    assert _live_results(store, claim_id) == []

    # 4 — the re-run judges the data as it now is.
    _sweep(root)
    store = ProjectStore(root)
    assert store.claims[claim_id].status is ClaimStatus.CONTRADICTED
    card = _card(store)
    assert card is not None and card.finding and not card.stale

    # 5 — the correction is reversed; the failing reading is outrun in turn
    #     and the card admits its number is from a reading nobody took since.
    _restore(database, posting, before)
    assert scan(root).stale.questions_flagged == [card.id]
    assert ProjectStore(root).questions[card.id].stale

    # 6 — and the re-run clears it.
    _sweep(root)
    store = ProjectStore(root)
    assert not store.questions[card.id].stale
    assert store.claims[claim_id].status is ClaimStatus.TEST_SUPPORTED


def test_the_corpus_itself_was_never_touched(project):
    """The mutation edits a copy. If this ever fails, every other corpus
    test in the suite has been measuring something else."""
    root, _claim_id, database = project
    frozen = duckdb.connect(str(CORPUS / "DE" / "erp.duckdb"), read_only=True)
    try:
        total = frozen.execute(
            "SELECT round(sum(amount_local_currency), 2) FROM gl_postings").fetchone()[0]
    finally:
        frozen.close()
    assert total == pytest.approx(0.0, abs=0.01)
