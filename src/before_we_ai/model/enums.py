"""Enumerations of the epistemic core.

The five claim statuses and five evidence types are the fixed vocabulary
of the system; new values require an architecture decision, not a patch.
"""

from enum import Enum


class ClaimStatus(str, Enum):
    """The five epistemic statuses a claim can hold."""

    PROPOSED = "proposed"
    TEST_SUPPORTED = "test-supported"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"
    BUSINESS_CONFIRMED = "business-confirmed"


class Actor(str, Enum):
    """Who authored a claim or a piece of evidence.

    Structurally, AI can only create ``proposed`` claims: no evidence
    authored by ``AI`` ever changes a status. Promotion belongs to checks
    and humans.
    """

    AI = "ai"
    CHECK = "check"
    HUMAN = "human"
    SYSTEM = "system"  # deterministic tooling (e.g. ingestion declarations)


class EvidenceType(str, Enum):
    """The five evidence types.

    check_result — a check run (rendered SQL, raw result, verdict)
    document_anchor — a located passage/number in a document
    confirmation — a human confirmation (``confirm``, mirror-loop)
    testimonial — a verbatim user statement (``tell``)
    declaration — a declared processing decision (e.g. normalization)
    """

    CHECK_RESULT = "check_result"
    DOCUMENT_ANCHOR = "document_anchor"
    CONFIRMATION = "confirmation"
    TESTIMONIAL = "testimonial"
    DECLARATION = "declaration"


class CheckVerdict(str, Enum):
    """Outcome of a check run, carried on its EvidenceRecord.

    Deterministic verdict *functions* arrive with the check engine (M3);
    the core only needs the resulting value.
    """

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
