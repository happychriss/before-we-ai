"""The stage spine — the pipeline as data, one home.

A **stage** is a change in what is known, with one actor responsible. Three
surfaces describe the same seven stages: the readiness report's process
diagram and section headings, the validation walkthrough's scripts, and
`docs/architecture.md`. They disagreed once; this is the fix, and it is the
same one `glossary.py` applies to the vocabulary — state the fact once, as
data, and let every surface render it.

Stages **0 and 6 are the frame**; 1–5 are the middle, which runs bottom-up.
The question opens the frame because it bounds the work — what the answer
does not depend on, nobody has to know — and the verdict closes it.

The **actor boundary** falls between *proposed* and *tested*. That is not a
drawing convention: `Actor.AI` structurally cannot author promoting
evidence, so nothing left of the line can change what is believed.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Stage:
    """One stage: who is responsible, what it reads, what it leaves behind."""

    number: str
    name: str  # the one word every surface uses
    heading: str  # report section heading, after "N · Name — "
    title: str  # what happens here, in the diagram
    actor: str  # who is responsible — the diagram prints this verbatim
    reads: str
    produces: str

    @property
    def label(self) -> str:
        return f"{self.number} · {self.name}"


STAGES: tuple[Stage, ...] = (
    Stage("0", "request", "the question, and what it requires",
          "A human asks", "human asks · AI structures",
          "one business question + the domain guide's definitions",
          "AnswerRequest, RequiredKnowledge"),
    Stage("1", "inputs", "what a human declared",
          "Humans declare", "human",
          "before-ai.yaml, the domain guide file, the check registry",
          "the declared sources, business objects and domain laws"),
    Stage("2", "measured", "what the data says about itself",
          "The data describes itself", "no model involved",
          "the declared sources",
          "data profiles, the candidate matrix"),
    Stage("3", "proposed", "what the AI guessed",
          "The AI guesses", "AI — proposals only",
          "profiles, the candidate matrix, the domain guide",
          "claims, mapping candidates, check plans — all proposed"),
    Stage("4", "tested", "what the checks settled",
          "The checks judge", "check — may promote",
          "check plans, the data",
          "evidence, derived statuses, scoped elections"),
    Stage("5", "clarification", "what only a human can answer",
          "Humans decide the rest", "human — may promote",
          "what the checks could not settle",
          "clarification questions, and the answers that close them"),
    Stage("6", "readiness", "what may be answered",
          "What may be answered", "derived — never stored",
          "the required knowledge, and every claim and status under it",
          "the ReadinessMap: ready / ready_with_limitations / blocked"),
)

BY_NAME = {stage.name: stage for stage in STAGES}

# The stage the actor boundary is drawn before: left of it everything is a
# proposal, and no proposal may promote itself.
BOUNDARY_BEFORE = "tested"
BOUNDARY_TEXT = "no proposal may promote itself"

# Stages that frame the middle rather than belonging to it.
FRAME = ("request", "readiness")
