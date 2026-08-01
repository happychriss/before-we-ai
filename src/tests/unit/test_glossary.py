"""The canonical vocabulary must survive leaving its first domain.

`glossary.py` is rendered into every project's readiness report and LLM-call
log, whatever domain that project is in. A general term explained by a
finance example teaches a shipyard the wrong thing — and the concrete nouns
of a domain already have a home: that domain's guide, which the report
quotes from.
"""

import re

import pytest

from before_we_ai.glossary import GERMAN_TERMS, GLOSSARY, PLANNED

pytestmark = pytest.mark.unit

# Nouns of the one domain the product has a pack for today. They are correct
# in `checks/library.py`, in `tests/fixtures/domain_guide_finance.yaml` and in
# the corpus — and wrong in a definition of a general term.
FINANCE_NOUNS = (
    "journal", "ledger", "subledger", "posting", "debit", "credit",
    "intercompany", "invoice", "voucher", "fiscal", "accrual",
)


def test_the_core_terms_carry_no_domain_examples():
    offenders = {}
    for term, text in GLOSSARY + PLANNED:
        hits = sorted({
            noun for noun in FINANCE_NOUNS
            if re.search(rf"\b{noun}", text, re.IGNORECASE)
        })
        if hits:
            offenders[term] = hits
    assert not offenders, (
        "domain nouns in the canonical vocabulary: "
        + "; ".join(f"{term} -> {hits}" for term, hits in offenders.items())
        + ". Explain the general term generally; the domain guide names the "
          "concrete things."
    )


def test_the_german_table_is_exempt_because_it_translates_the_spec():
    """The owner's spec is German and finance; that table maps its terms of
    art onto the English vocabulary, so its left-hand side is domain-bound
    by definition. It exists precisely so the rest stays clean."""
    assert GERMAN_TERMS
    assert all(english for _, english in GERMAN_TERMS)


def test_every_term_is_defined_once():
    terms = [term for term, _ in GLOSSARY + PLANNED]
    assert len(terms) == len(set(terms)), "one term, one definition"
