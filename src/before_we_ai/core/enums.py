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


class KnowledgeKind(str, Enum):
    """What a required-knowledge item points at.

    The three things a business answer can depend on: a business object of
    the domain guide, one of that object's fields, or a rule (a claim about
    how the data behaves). Nothing else bounds discovery.
    """

    OBJECT = "object"
    FIELD = "field"
    RULE = "rule"


class Provenance(str, Enum):
    """Where a required-knowledge item came from.

    The distinction the reader needs before trusting a dependency list:
    ``contract`` items were expanded from an answer type a human reviewed in
    the domain guide, ``proposed`` items were drafted by the model for this
    one question, ``added`` items were written by a human who found the list
    incomplete. A list of nothing but ``contract`` items is the only kind
    that was ever reviewed as a whole.
    """

    CONTRACT = "contract"
    PROPOSED = "proposed"
    ADDED = "added"


class ActKind(str, Enum):
    """What a human (or the AI, for links) did to a dependency list.

    The list itself is derived; these acts are the only part that is
    stored, so they are the complete record of every decision taken about
    it. Append-only: an act is never edited, only answered by a later one
    (``require_again`` after ``waive``).
    """

    WAIVE = "waive"
    REQUIRE_AGAIN = "require_again"
    LINK = "link"
    ADD = "add"
    CONFIRM = "confirm"


class CheckVerdict(str, Enum):
    """Outcome of a check run, carried on its EvidenceRecord.

    Deterministic verdict *functions* arrive with the check engine (M3);
    the core only needs the resulting value.
    """

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
