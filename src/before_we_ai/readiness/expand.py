"""An answer type becomes a dependency list — deterministically.

This is the seam the whole answer-type design rests on. Before it, the model
was asked what an answer depends on and wrote the list itself; what it forgot
was invisible, because a dependency nobody lists is one nobody can test,
waive or clarify. Now the model makes a far smaller claim — *this question is
of that family* — and the list follows from a guide entry a human reviewed.

Nothing here decides anything, and nothing here reads a store. Given the same
answer type and the same guide it returns the same items in the same order,
which is what makes the list safe to derive on every read instead of storing
it (see ``readiness.assemble``).

The engine never asks where an answer type came from — a hand-written guide,
a starter pack, a template library, or one day a guide builder that proposes
one from documents. That is the point of the seam.
"""

from before_we_ai.core.enums import KnowledgeKind, Provenance
from before_we_ai.core.objects import KnowledgeItem, Scope
from before_we_ai.llm.domain_guide import DomainGuide


class UnknownAnswerType(Exception):
    """The request names an answer type this guide does not declare.

    Reachable when a guide is edited after a question was classified against
    it. It is an error and not an empty list on purpose: expanding to nothing
    is precisely the silent under-listing this design exists to prevent.
    """


def expand(answer_type: str, guide: DomainGuide, scope: Scope) -> list[KnowledgeItem]:
    """The items one answer type requires, in the order the guide lists them.

    Scope follows the same rule as everywhere: objects and fields inherit the
    request's scope, because for them it *selects* which table or column
    plays the role. A rule has nothing to select among, so it carries none —
    where a rule holds lives on the claim that states it.
    """
    spec = guide.answer_types.get(answer_type)
    if spec is None:
        raise UnknownAnswerType(
            f"answer type {answer_type!r} is not declared by the "
            f"{guide.domain!r} guide (it has "
            f"{sorted(guide.answer_types) or 'none'})"
        )
    return [_item(require, scope) for require in spec.requires]


def _item(require, scope: Scope) -> KnowledgeItem:
    if require.kind == "field":
        of_object, _, name = require.ref.partition(".")
        return KnowledgeItem(
            kind=KnowledgeKind.FIELD, name=name, of_object=of_object,
            why=require.why, provenance=Provenance.CONTRACT, scope=scope,
        )
    if require.kind == "object":
        return KnowledgeItem(
            kind=KnowledgeKind.OBJECT, name=require.ref, why=require.why,
            provenance=Provenance.CONTRACT, scope=scope,
        )
    return KnowledgeItem(
        kind=KnowledgeKind.RULE, name=require.ref, why=require.why,
        provenance=Provenance.CONTRACT,  # scope: a rule carries none
    )
