"""Pydantic OUTPUT schemas of the LLM contracts.

These are the response contracts: the model's answer must validate
against them or the call is retried once with the errors fed back.
``extra="forbid"`` everywhere — an answer with fields we did not ask for
is a wrong answer. Predicate and template names are Literals over the
controlled vocabulary, so free-form inventions fail here, not downstream.

Schemas stay purely *structural* (types, Literals, forbidden extras):
a schema failure is fatal for the whole batch, so anything item-level —
cross-field consistency, do the referenced columns exist, do params fit
the predicate/template contract — lives in ``mapping``'s semantic checks
instead, which feed the same retry loop but skip per item. (Learned from
the first real run: 56 hypotheses died over two items missing a term.)
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from before_we_ai.llm.vocabulary import PredicateName, TemplateName

ParamValue = str | int | float | bool | list[str] | list[dict[str, str]]


class HypothesisScope(BaseModel):
    """Mirror of the core ``Scope`` — spelled out here so the answer schema
    is self-contained and forbids extras."""

    model_config = ConfigDict(extra="forbid")

    entity: str | None = None
    period: str | None = None
    segment: str | None = None


class Hypothesis(BaseModel):
    """One proposed rule about the data landscape (V1)."""

    model_config = ConfigDict(extra="forbid")

    statement: str  # one human-readable sentence
    predicate: PredicateName
    params: dict[str, ParamValue] = {}
    columns: list[str] = []  # "view.column" references grounding the rule
    kind: str = "rule"  # "rule" | "concept"
    term: str | None = None  # concept only
    definition: str | None = None  # concept only
    scope: HypothesisScope | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    rationale: str  # why the profiles suggest this — logged, never stored on the claim


class HypothesisBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypotheses: list[Hypothesis]


class MappingProposal(BaseModel):
    """One candidate binding of a domain role to concrete columns."""

    model_config = ConfigDict(extra="forbid")

    role: str  # must name a role from the supplied role list (semantic check)
    binding: dict[str, str]  # role part -> "view" or "view.column"
    rationale: str


class MappingProposalBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposals: list[MappingProposal]  # competing candidates per role are welcome


class CheckPlanProposal(BaseModel):
    """The V2 answer for one claim: a template instance, or an honest 'none'."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str  # the claim's label exactly as given in the input (semantic check)
    template: TemplateName | None = None  # None = no suitable template
    params: dict[str, ParamValue] = {}
    no_template_reason: str | None = None


class BindingBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bindings: list[CheckPlanProposal]


class KnowledgeItemProposal(BaseModel):
    """One thing the requested answer depends on (V4)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["object", "field", "rule"]
    name: str  # an object/field of the supplied vocabulary, or a rule's name
    of_object: str | None = None  # fields only (semantic check)
    why: str  # the dependency in business words — what the human prunes on


class AnswerRequestDraft(BaseModel):
    """The V4 answer: one business question, structured, plus its dependencies.

    ``required_knowledge`` is a *draft*. The human prunes it, and pruning is
    only possible if every item says why it is there — hence the required
    ``why`` on each one.
    """

    model_config = ConfigDict(extra="forbid")

    requested_output: str  # what the answer must deliver, in one line
    scope: HypothesisScope | None = None  # only when the question names one
    required_knowledge: list[KnowledgeItemProposal]
    rationale: str  # why this decomposition — logged, never stored
