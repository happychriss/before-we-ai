"""The core terms — the canonical vocabulary as data, one home.

Every owner-facing surface that defines the terms (the claim viewer, the
validation LLM-call log) renders THIS list, so the definitions cannot
drift apart. The full human-facing glossary with code links lives in
docs/SIMPLE-README.md; this is the short subset shown where it is read.
No synonyms, ever — these are the only words.
"""

GLOSSARY: list[tuple[str, str]] = [
    ("hypothesis", "one proposed rule, the model's raw output (V1); accepted "
     "ones become claims"),
    ("claim", "a rule about the data, stored with author and evidence — "
     "the 'index card'"),
    ("status", "inferred / tested / contradicted / unresolved / "
     "business-confirmed — always derived from evidence; the model's claims "
     "start at 'inferred' and the model cannot promote them"),
    ("role", "a domain noun a table/column can play (journal, subledger …); "
     "each role declares how it can ever be settled (decided_by)"),
    ("role-binding candidate", "a claim that one view plays a role; competing "
     "candidates are wanted — the domain-law probes elect the winner"),
    ("binding", "the assignment claim → probe template + parameters (V2); "
     "strictly validated, 'template: null' = not testable"),
    ("probe", "a deterministic SQL spot-check — with humans, the only path to "
     "a better status; never runs inside a model call"),
    ("domain-law template", "a conservation law as code (balance, "
     "subledger=GL, IC symmetry) — decides which candidate wins a role"),
    ("Fachfrage", "a drafted question to the humans when data alone cannot "
     "decide"),
]
