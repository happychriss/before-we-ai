"""Pydantic OUTPUT schemas of the LLM contracts.

These are the response contracts: the model's answer must validate
against them or the call is retried once with the errors fed back.
``extra="forbid"`` everywhere — an answer with fields we did not ask for
is a wrong answer. Predicate and template names are Literals over the
controlled vocabulary, so free-form inventions fail here, not downstream.

Schema validation is syntactic; the *semantic* checks (do the referenced
columns exist, do params fit the predicate/template contract) live in
``mapping`` and feed the same retry loop.
"""

from pydantic import BaseModel, ConfigDict, model_validator

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

    @model_validator(mode="after")
    def _check_kind(self) -> "Hypothesis":
        if self.kind not in ("rule", "concept"):
            raise ValueError(f"kind must be 'rule' or 'concept', got {self.kind!r}")
        if self.kind == "concept" and not (self.term and self.definition):
            raise ValueError("a concept hypothesis requires term and definition")
        return self


class HypothesisBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hypotheses: list[Hypothesis]


class RoleBindingProposal(BaseModel):
    """One candidate binding of a domain role to concrete columns."""

    model_config = ConfigDict(extra="forbid")

    role: str  # must name a role from the supplied role list (semantic check)
    binding: dict[str, str]  # role part -> "view" or "view.column"
    rationale: str

    @model_validator(mode="after")
    def _check_binding(self) -> "RoleBindingProposal":
        if not self.binding:
            raise ValueError("a role binding proposal must bind at least one part")
        return self


class RoleBindingBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposals: list[RoleBindingProposal]  # competing candidates per role are welcome


class ProbeBinding(BaseModel):
    """The V2 answer for one claim: a template instance, or an honest 'none'."""

    model_config = ConfigDict(extra="forbid")

    claim_id: str  # the claim's label exactly as given in the input (semantic check)
    template: TemplateName | None = None  # None = no suitable template
    params: dict[str, ParamValue] = {}
    no_template_reason: str | None = None

    @model_validator(mode="after")
    def _check_template(self) -> "ProbeBinding":
        if self.template is None and not self.no_template_reason:
            raise ValueError("template=null requires no_template_reason")
        if self.template is not None and self.no_template_reason:
            raise ValueError("no_template_reason is only valid with template=null")
        return self


class BindingBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bindings: list[ProbeBinding]
