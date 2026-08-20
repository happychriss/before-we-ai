"""A fresh project declared over the frozen corpus — the one construction.

Three callers need it and none of them is a test: the owner walkthrough
(`validation/scripts/_steps.py`) and the two online tools that live under
`src/tests/eval/` (`refresh_fixtures.py`, `seeded_recall.py`, run as scripts,
never collected). Keeping it here rather than under `tests/` is what stops
owner-facing validation from depending on test-internal code.

The landscape it points at is `corpora/finance/` — frozen, and the one thing
every offline run measures against. Which files that is, and what each one is
described as, is the manifest's business, not this module's.
"""

from pathlib import Path

import yaml

from before_we_ai import scan
from before_we_ai.domains import packaged
from before_we_ai.store import init_project

from corpora import load as load_landscape

FINANCE = load_landscape("finance")
SRC = Path(__file__).resolve().parents[2] / "src"
CORPUS = FINANCE.data
FIXTURES = SRC / "tests" / "fixtures" / "llm"
DOMAIN_GUIDE_FILE = packaged(FINANCE.guide_packaged)
EXPECTED_VERDICTS = FINANCE.answer_key

# The source list is the landscape's, declared in corpora/finance/manifest.yaml
# — names, kinds, and the descriptions that reach the model. It used to be a
# literal here, which meant the same twelve facts also lived in the drift
# guard's PDF list and in the walkthrough's config.
#
# The three noise documents are declared *deliberately*: a document pipeline
# that only ever sees relevant documents has not been tested. Their presence is
# the precision measurement — F26's divested-unit press release must be read
# and refused, not absent.
SOURCES = FINANCE.declarations()



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
