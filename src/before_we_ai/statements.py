"""The human's voice entering the store — ``tell`` and the mirror loop.

Three voices write here: checks, the AI, and the human. The AI's is
capped at ``proposed`` by construction and the checks' is mechanical.
This module is the third, and it is the only one that can settle
anything, so it is also the one that has to be hardest on itself.

Two operations, and the distance between them is the whole point:

``tell`` takes free background knowledge — "we only supply pharmacies and
wholesalers", "the fiscal year runs May to April" — and stores it
**verbatim** as testimonial evidence. A testimonial promotes nothing. It
records that somebody said something, which is a different fact from the
thing being true, and the store keeps them different.

``answer_question`` is where a human settles something, and it is
deliberately narrow: a confirmation of a testimonial claim requires an
explicit scope. That rule is not enforced here — ``core.transitions``
owns it — and this module simply cannot get round it. "Does it hold for
every company?" is the question the mirror loop exists to ask, because a
statement made about one entity, confirmed globally, is a wrong answer
with a human's signature on it.

The statement itself becomes a searchable passage, so a statement that
structures into no claim is not lost — it is parked, findable, and
carrying no weight, which is what the spec asks for.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import duckdb

from before_we_ai.core.enums import Actor, EvidenceType
from before_we_ai.core.objects import (
    Claim,
    EvidenceRecord,
    MappingClaim,
    Scope,
)
from before_we_ai.core.transitions import admit_evidence, attach_evidence
from before_we_ai.documents.chunk import Chunk
from before_we_ai.documents.index import build_chunk_index, load_chunks
from before_we_ai.store.repository import ProjectStore

# Statements live under one pseudo-document so they are searchable beside
# the real ones. The name is a source name like any other, which is what
# lets an anchor point into a statement exactly as it points into a PDF.
STATEMENTS = "statements"


@dataclass
class Mirror:
    """What the system understood, offered back for confirmation.

    ``needs_scope`` is the mirror loop's actual question. A statement
    stored without one is not half-confirmed — it is unconfirmed, and the
    claim it produced stays proposed until somebody says who it is about.
    """

    statement: str
    claim_ids: list[str] = field(default_factory=list)
    understood: list[str] = field(default_factory=list)
    scope: Scope | None = None
    needs_scope: bool = True
    parked: bool = False

    def question(self) -> str:
        """The sentence to put in front of the person who spoke."""
        if self.parked:
            return (f"Nothing in “{self.statement}” could be structured into a "
                    "claim, so it is stored as a searchable note and carries "
                    "no weight. Is that right?")
        heard = "; ".join(u.rstrip(".") for u in self.understood)
        if self.needs_scope:
            return (f"Understood as: {heard}. Which companies, periods or "
                    "segments does this hold for? A confirmation without a "
                    "scope cannot be accepted.")
        return (f"Understood as: {heard}, for {self.scope.label()}. "
                "Is that right?")


def statement_chunk(store: ProjectStore, text: str) -> Chunk:
    """The statement as a passage, numbered after the ones already stored."""
    existing = [c for c in _stored_chunks(store.root) if c.source == STATEMENTS]
    return Chunk(
        id=f"{STATEMENTS}:p1:{len(existing)}",
        source=STATEMENTS,
        page=1,
        seq=len(existing),
        # A person speaking is prose. Not a table, and emphatically not a
        # chart: the multi-anchor rule must treat a sentence somebody said
        # as the kind of thing it is.
        kind="text",
        text=text,
        start=0,
        end=len(text),
    )


def _stored_chunks(root: Path) -> list[Chunk]:
    con = duckdb.connect(str(Path(root) / "cache" / "analysis.duckdb"))
    try:
        return load_chunks(con)
    except duckdb.CatalogException:
        return []  # nothing has been read yet
    finally:
        con.close()


def _index(root: Path, chunks: list[Chunk]) -> None:
    (Path(root) / "cache").mkdir(exist_ok=True)
    con = duckdb.connect(str(Path(root) / "cache" / "analysis.duckdb"))
    try:
        build_chunk_index(con, chunks)
    finally:
        con.close()


def record_statement(store: ProjectStore, text: str, *,
                     by: Actor = Actor.HUMAN) -> Chunk:
    """Store the statement verbatim as a searchable passage.

    Called before anything is made of it, so that a statement nobody can
    structure is still on the record rather than discarded.
    """
    if not text.strip():
        raise ValueError("an empty statement says nothing — nothing is stored")
    chunk = statement_chunk(store, text.strip())
    _index(store.root, [c for c in _stored_chunks(store.root)] + [chunk])
    return chunk


def attest(store: ProjectStore, claim: Claim, statement: str, *,
           by: Actor = Actor.HUMAN) -> EvidenceRecord:
    """Attach the verbatim statement to a claim as testimonial evidence.

    Testimonial evidence carries the words, not their truth: it leaves the
    claim ``proposed``, and its only power is that a contradicting check
    later pulls the claim to ``unresolved`` rather than quietly winning.
    """
    record = EvidenceRecord(
        type=EvidenceType.TESTIMONIAL,
        actor=by,
        claim_id=claim.id,
        statement=statement,
    )
    existing = store.evidence_for(claim)
    admit_evidence(claim, record, existing)
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, existing))
    return record


def confirm_claim(store: ProjectStore, claim_id: str, *,
                  by: Actor = Actor.HUMAN, scope: Scope | None = None,
                  note: str = "") -> EvidenceRecord:
    """A human settles one claim.

    Raises ``PromotionError`` when the claim rests on a testimonial and no
    explicit scope is given — the mirror-loop rule, enforced in
    ``core.transitions`` and unreachable from here. Nothing in this
    function may soften it: the whole reason the rule sits in the core is
    that the convenient place to break it is exactly here.
    """
    claim = store.claims[claim_id]
    record = EvidenceRecord(
        type=EvidenceType.CONFIRMATION,
        actor=by,
        claim_id=claim_id,
        scope=scope,
        payload={"note": note} if note else {},
    )
    existing = store.evidence_for(claim)
    admit_evidence(claim, record, existing)
    store.add_evidence(record)
    store.save_claim(attach_evidence(claim, record, existing))
    return record


def rival_claims(store: ProjectStore,
                 claim_ids: Sequence[str]) -> dict[str, tuple[str, ...]]:
    """role -> the claims on this card competing to play it.

    Two mapping claims naming the same role are alternatives: a role is
    played by one thing, so at most one of them can be true. That is a
    property of the claims themselves, readable without the domain guide —
    which matters, because this module must not need one to know whether
    it is being asked to confirm a set or to make a choice.
    """
    by_role: dict[str, list[str]] = defaultdict(list)
    for claim_id in claim_ids:
        claim = store.claims[claim_id]
        if isinstance(claim, MappingClaim):
            by_role[claim.role].append(claim_id)
    return {role: tuple(ids) for role, ids in by_role.items() if len(ids) > 1}


def answer_question(store: ProjectStore, card_id: str, *,
                    pick: str | None = None,
                    by: Actor = Actor.HUMAN, scope: Scope | None = None,
                    note: str = "") -> list[EvidenceRecord]:
    """A human answers a clarification question, settling what it rests on.

    A card names every claim its answer would touch, and answering it
    confirms all of them together — that is what made the card one
    question rather than several. If any of them refuses the confirmation,
    the whole answer is refused: half an answer would leave the reader
    believing they had settled something they had not.

    **Unless the card is a choice.** "Which of the proposed candidates is
    the 'account'?" lists three bindings for one role, and exactly one of
    them can be right. Confirming all three was the reading this function
    shipped with — it was only ever called on ``tell`` cards, where every
    claim comes from the one statement and settling them together is the
    whole point, so nothing caught it. On a role card it would have put a
    human's signature on two bindings they had just been asked to choose
    between, and ``ReadinessMap`` would then have elected whichever came
    first. A wrong answer with a signature on it is the failure this
    product exists to prevent, so a card offering rivals refuses to be
    answered without ``pick``.

    Confirming the pick says nothing about the losers: they stay
    ``proposed``. The human said which one plays the role, not that the
    others are false, and recording a refutation nobody stated would be
    inventing agreement.
    """
    card = store.questions[card_id]
    if not card.claim_ids:
        raise ValueError(
            f"question {card_id} rests on no claim, so answering it would "
            "settle nothing"
        )
    rivals = rival_claims(store, card.claim_ids)
    contested = {claim_id for group in rivals.values() for claim_id in group}

    if pick is not None and pick not in card.claim_ids:
        raise ValueError(
            f"claim {pick} is not one of the candidates on question "
            f"{card_id}, so picking it would answer a different question"
        )
    if rivals and pick is None:
        offered = "; ".join(
            f"{role}: {len(ids)} candidates" for role, ids in sorted(rivals.items())
        )
        raise ValueError(
            f"question {card_id} offers a choice ({offered}) — a role is "
            "played by one thing, so answering it means naming which one. "
            "Pass pick=<claim id>."
        )
    if pick is not None and not rivals:
        raise ValueError(
            f"question {card_id} offers no choice: its claims settle "
            "together or not at all, so a pick would confirm less than the "
            "answer covers"
        )

    # the pick, plus everything on the card that was never contested
    targets = [claim_id for claim_id in card.claim_ids
               if claim_id == pick or claim_id not in contested]
    for claim_id in targets:
        claim = store.claims[claim_id]
        admit_evidence(
            claim,
            EvidenceRecord(type=EvidenceType.CONFIRMATION, actor=by,
                           claim_id=claim_id, scope=scope),
            store.evidence_for(claim),
        )
    return [
        confirm_claim(store, claim_id, by=by, scope=scope, note=note)
        for claim_id in targets
    ]


def mirror(store: ProjectStore, statement: str, claim_ids: list[str], *,
           scope: Scope | None = None) -> Mirror:
    """What to say back to the person who spoke."""
    if not claim_ids:
        return Mirror(statement=statement, parked=True, needs_scope=False)
    return Mirror(
        statement=statement,
        claim_ids=list(claim_ids),
        understood=[store.claims[cid].statement for cid in claim_ids],
        scope=scope,
        needs_scope=scope is None or not scope.is_explicit(),
    )


@dataclass
class TellReport:
    """What became of one statement."""

    chunk_id: str
    mirror: Mirror
    claims_created: list[str] = field(default_factory=list)
    testimonials: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    failure: str | None = None
    # Where the verbatim call landed, so a recording session can turn this
    # into a fixture and the walkthrough can point a reader at the bytes.
    log_refs: list[str] = field(default_factory=list)


def tell(root, statement: str, *, guide, by: Actor = Actor.HUMAN,
         scope: Scope | None = None, client=None,
         store: ProjectStore | None = None, scenario: str = "default"
         ) -> TellReport:
    """Take a person's background knowledge into the store.

    The order matters and is the design. The words are recorded **first**,
    verbatim and searchable, before anything is made of them — so a
    statement the model cannot structure is parked rather than lost. Only
    then does V3 read it, exactly as it reads a document: same quote
    validation, same anchoring, same inability to promote. Each resulting
    claim carries the testimonial, which records that somebody said this
    and not that it is true.

    What comes back is the mirror: what was understood, and the scope
    question. Confirming it is a separate act, by
    ``answer_question``/``confirm_claim``, and it is refused without an
    explicit scope.
    """
    from before_we_ai.llm.call_log import CallLogger
    from before_we_ai.llm.config import LLMConfig, build_client
    from before_we_ai.llm.v3_documents import (
        V3Report,
        open_rule_items,
        read_passages,
    )
    from before_we_ai.store.proposals import ProposalStore

    root = Path(root)
    project = store or ProjectStore(root)
    chunk = record_statement(project, statement, by=by)

    config = LLMConfig.from_project(root)
    client = client or build_client(config)
    report = V3Report()
    read_passages(
        ProposalStore(project), project, guide, client, config,
        CallLogger(root), report, STATEMENTS, "", [chunk],
        open_rule_items(project, guide), scenario,
    )

    project = ProjectStore(root)
    if report.claims_created:
        for claim_id in report.claims_created:
            attest(project, project.claims[claim_id], chunk.text, by=by)
    else:
        # Nothing could be structured from it, and the words are still
        # evidence: somebody said this, on a date, and the spec stores that
        # unconditionally. A claim-less record is ordinary here — every
        # normalization declaration is one — and it keeps a parked
        # statement visible in the decision log instead of leaving only a
        # searchable note nobody thinks to search for.
        project.add_evidence(EvidenceRecord(
            type=EvidenceType.TESTIMONIAL, actor=by, statement=chunk.text,
        ))

    told = TellReport(
        chunk_id=chunk.id,
        mirror=mirror(project, chunk.text, report.claims_created, scope=scope),
        claims_created=list(report.claims_created),
        questions=list(report.questions),
        skipped=list(report.skipped),
        failure=report.failures[0][1] if report.failures else None,
        log_refs=list(report.log_refs),
    )
    told.testimonials = [
        e.id for e in project.evidence.values()
        if e.type is EvidenceType.TESTIMONIAL and e.statement == chunk.text
    ]
    return told
