"""The core terms — the canonical vocabulary as data, one home.

Every owner-facing surface that defines the terms (the claim viewer, the
validation LLM-call log) renders THIS list, so the definitions cannot
drift apart. The full human-facing explanation of the flow lives in
docs/before-ai-concept.md; this is the short subset shown where it is
read. No synonyms, ever — these are the only words.
"""

GLOSSARY: list[tuple[str, str]] = [
    ("hypothesis", "one proposed rule, the model's raw output (V1); accepted "
     "ones become claims"),
    ("claim", "a rule about the data, stored with author and evidence — "
     "the 'index card'"),
    ("mapping claim", "a claim that concrete views/columns play a domain "
     "role; competing candidates are wanted — the domain-law checks elect "
     "the winner"),
    ("status", "proposed / test-supported / contradicted / unresolved / "
     "business-confirmed — always derived from evidence; the model's claims "
     "start at 'proposed' and the model cannot promote them"),
    ("domain guide", "the curated per-domain starting vocabulary: roles with "
     "one definition each and a declared settlement path (decided_by) — "
     "data, never code"),
    ("role", "a domain noun from the domain guide that a table/column can "
     "play (journal, subledger …)"),
    ("data profile", "measured statistics of one column — what the model "
     "sees instead of raw data"),
    ("check definition", "reusable test logic (SQL template + deterministic "
     "verdict function), independent of any concrete file"),
    ("check plan", "a check definition bound to concrete views/columns "
     "(V2); strictly validated, 'template: null' = not testable"),
    ("check run", "the deterministic execution of a check plan — with "
     "humans, the only path to a better status; never runs inside a model "
     "call; its result is stored as evidence"),
    ("evidence", "an append-only record: check result, human confirmation, "
     "verbatim testimonial, document anchor, or declaration"),
    ("domain law", "a conservation law as code (balance, subledger=GL, "
     "IC symmetry) — decides which candidate wins a role"),
    ("clarification question", "a drafted question to the humans when data "
     "alone cannot decide"),
]

# Specified for M6 (question flow) — defined here so the words exist in one
# place before the objects do; see docs/before-ai-concept.md.
PLANNED: list[tuple[str, str]] = [
    ("answer request", "the structured form of one business question: scope "
     "and required output"),
    ("required knowledge", "what must be known before the requested answer "
     "can be produced — derived from the answer request"),
    ("readiness map", "per required-knowledge item: claim, evidence, status, "
     "remaining gap; grounds the verdict ready / ready_with_limitations / "
     "blocked"),
]

# German terms of art from the owner's spec (docs/spec/, German by design)
# mapped to the canonical English vocabulary.
GERMAN_TERMS: list[tuple[str, str]] = [
    ("Fachfrage", "clarification question"),
    ("Sonde / Invarianten-Sonde", "check / invariant check (domain law)"),
    ("Rollenbindung", "mapping claim"),
    ("Befund", "finding (an INCONCLUSIVE check result — never a "
     "falsification)"),
    ("Körnung", "grain (the key set a table is unique on)"),
    ("Datenschnitt", "data cut (a legitimate scope boundary, not an error)"),
]
