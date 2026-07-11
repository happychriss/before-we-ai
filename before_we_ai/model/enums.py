"""Enumerations of the epistemic core.

The five claim statuses and five evidence types are the fixed vocabulary
of the system; new values require an architecture decision, not a patch.
"""

from enum import Enum


class ClaimStatus(str, Enum):
    """The five epistemic statuses a claim can hold."""

    INFERRED = "inferred"
    TESTED = "tested"
    CONTRADICTED = "contradicted"
    UNRESOLVED = "unresolved"
    BUSINESS_CONFIRMED = "business-confirmed"


class Actor(str, Enum):
    """Who authored a claim or a piece of evidence.

    Structurally, AI can only create ``inferred`` claims: no evidence
    authored by ``AI`` ever changes a status. Promotion belongs to probes
    and humans.
    """

    AI = "ai"
    PROBE = "probe"
    HUMAN = "human"
    SYSTEM = "system"  # deterministic tooling (e.g. ingestion declarations)


class EvidenceType(str, Enum):
    """The five evidence types.

    probe_result — a probe run (rendered SQL, raw result, verdict)
    document_anchor — a located passage/number in a document
    confirmation — a human confirmation (``confirm``, mirror-loop)
    testimonial — a verbatim user statement (``tell``)
    declaration — a declared processing decision (e.g. normalization)
    """

    PROBE_RESULT = "probe_result"
    DOCUMENT_ANCHOR = "document_anchor"
    CONFIRMATION = "confirmation"
    TESTIMONIAL = "testimonial"
    DECLARATION = "declaration"


class ProbeVerdict(str, Enum):
    """Outcome of a probe run, carried on its EvidenceRecord.

    Deterministic verdict *functions* arrive with the probe engine (M3);
    the core only needs the resulting value.
    """

    PASS = "pass"
    FAIL = "fail"
    INCONCLUSIVE = "inconclusive"
