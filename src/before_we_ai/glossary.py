"""The core terms — the canonical vocabulary as data, one home.

Every owner-facing surface that defines the terms (the readiness report, the
validation LLM-call log) renders THIS list, so the definitions cannot
drift apart. The full human-facing explanation of the flow lives in
docs/before-ai-concept.md; this is the short subset shown where it is
read. No synonyms, ever — these are the only words.

**Domain-neutral by rule.** These terms are rendered into every project's
report, whatever its domain. No entry may use an example from one domain to
explain a general term: a shipyard reading that a business object is "a
journal, a subledger, an intercompany" learns the wrong thing. The concrete
nouns of a domain live in that domain's guide, which is where the report
quotes them from. (Enforced by
``tests/unit/test_glossary.py::test_the_core_terms_carry_no_domain_examples``.)
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
    ("domain guide", "the curated per-domain starting vocabulary: business "
     "objects with their fields, one definition each and a declared "
     "settlement path (decided_by) — data, never code"),
    ("business object", "what a domain law judges: a thing of the domain "
     "that a table can be — named and defined by the domain guide, never "
     "by this glossary"),
    ("field", "something a business object carries — settled inside its "
     "object's law as a slot, or by a clarification question; a field never "
     "declares a law of its own"),
    ("role", "any guide entry — object or field — that a table/column can "
     "play; what a mapping claim binds"),
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
    ("domain law", "a conservation law of one domain, written as code and "
     "shipped with that domain's pack — decides which candidate wins a "
     "business object, and settles its slot fields with the columns the "
     "passing run consumed"),
    ("clarification question", "a drafted question to the humans when data "
     "alone cannot decide"),
    ("readiness report", "the rendered state of knowledge — what is known, "
     "what is assumed, what is unknown — derived live from the store; one "
     "self-contained page, disposable, the YAML underneath is the truth"),
    ("answer request", "the structured form of one business question: the "
     "requested output and its scope; it bounds the work — what the answer "
     "does not depend on, nobody has to know"),
    ("required knowledge", "the objects, fields and rules one answer depends "
     "on, each carrying the request's scope; drafted by the model, pruned by "
     "a human. Objects and fields resolve through the domain guide's scoped "
     "election; a rule has no guide entry, so it is answered only by a claim "
     "explicitly linked to it — the link routes, it never vouches"),
    ("readiness map", "per required-knowledge item: its claim, evidence and "
     "remaining gap, and how each satisfied item is satisfied; grounds the "
     "verdict ready / ready_with_limitations / blocked, which always names "
     "the dependency it rests on — derived on every read, never stored"),
    ("scope", "the entity, period or segment a claim, question or request is "
     "about; roles are elected once per scope, so two parts of a landscape "
     "can each own their occupant without competing"),
]

# Reserved for a milestone that has not shipped: the words exist in one place
# before the objects do. Emptied when M6 landed; the next reservation goes
# here. See docs/before-ai-concept.md.
PLANNED: list[tuple[str, str]] = []

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
