"""YAML object repository with an in-memory index.

One file per object, filename = ULID. Loading a project reads everything
into memory (project scale allows it). Writes are atomic (tmp + rename).
Evidence is append-only: re-writing an existing evidence ID raises; the
single permitted mutation is marking a record stale.
"""

import os
import tempfile
from pathlib import Path

import yaml
from pydantic import BaseModel

from before_we_ai.core.objects import (
    AnswerRequest,
    Claim,
    DataProfile,
    ConceptClaim,
    EvidenceRecord,
    CheckPlan,
    ClarificationQuestion,
    MappingClaim,
    RequiredKnowledge,
    Source,
)
from before_we_ai.core.semantics import claim_key
from before_we_ai.store.layout import CONFIG_FILE, init_project

_CLAIM_TYPES = {
    "Claim": Claim,
    "ConceptClaim": ConceptClaim,
    "MappingClaim": MappingClaim,
}

# answers/ holds a request and the knowledge it requires side by side —
# they are one story and are read together.
_ANSWER_TYPES = {
    "AnswerRequest": AnswerRequest,
    "RequiredKnowledge": RequiredKnowledge,
}


class AppendOnlyViolation(Exception):
    """Raised on any attempt to overwrite an existing evidence record."""


def _dump(obj: BaseModel) -> str:
    data = obj.model_dump(mode="json", exclude_none=True)
    data["object_type"] = type(obj).__name__
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class ProjectStore:
    """Repository over one project directory."""

    def __init__(self, root: str | Path, create: bool = False):
        self.root = Path(root)
        if create:
            init_project(self.root)
        if not (self.root / CONFIG_FILE).is_file():
            raise FileNotFoundError(f"not a before-we-ai project: {self.root}")
        self.claims: dict[str, Claim] = {}
        self.evidence: dict[str, EvidenceRecord] = {}
        self.questions: dict[str, ClarificationQuestion] = {}
        self.sources: dict[str, Source] = {}
        self.profiles: dict[str, DataProfile] = {}
        self.checks: dict[str, CheckPlan] = {}
        self.requests: dict[str, AnswerRequest] = {}
        self.required: dict[str, RequiredKnowledge] = {}
        self._load()

    # -- loading ---------------------------------------------------------

    def _load(self) -> None:
        self.claims = {
            o.id: o for o in self._read_dir("claims", self._parse_claim, keep_type=True)
        }
        self._claims_by_key = {}
        for claim in self.claims.values():
            key = claim_key(claim)
            if key:
                self._claims_by_key[key] = claim.id
        self.evidence = {
            o.id: o for o in self._read_dir("evidence", EvidenceRecord.model_validate)
        }
        self.questions = {
            o.id: o for o in self._read_dir("questions", ClarificationQuestion.model_validate)
        }
        self.sources = {
            o.id: o for o in self._read_dir("sources_meta", Source.model_validate)
        }
        self.profiles = {
            o.id: o for o in self._read_dir("profiles", DataProfile.model_validate)
        }
        self.checks = {
            o.id: o for o in self._read_dir("checks", CheckPlan.model_validate)
        }
        answers = self._read_dir("answers", self._parse_answer, keep_type=True)
        self.requests = {
            o.id: o for o in answers if isinstance(o, AnswerRequest)
        }
        self.required = {
            o.id: o for o in answers if isinstance(o, RequiredKnowledge)
        }

    def _read_dir(self, dirname: str, parse, keep_type: bool = False) -> list:
        directory = self.root / dirname
        if not directory.is_dir():
            return []
        objects = []
        for path in sorted(directory.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not keep_type:
                data.pop("object_type", None)
            objects.append(parse(data))
        return objects

    @staticmethod
    def _parse_claim(data: dict) -> Claim:
        cls = _CLAIM_TYPES.get(data.pop("object_type", "Claim"), Claim)
        return cls.model_validate(data)

    @staticmethod
    def _parse_answer(data: dict) -> AnswerRequest | RequiredKnowledge:
        name = data.pop("object_type", "AnswerRequest")
        if name not in _ANSWER_TYPES:
            raise ValueError(f"answers/ holds no object of type {name!r}")
        return _ANSWER_TYPES[name].model_validate(data)

    # -- writing ---------------------------------------------------------

    def _write(self, dirname: str, obj: BaseModel) -> None:
        directory = self.root / dirname
        directory.mkdir(exist_ok=True)
        _atomic_write(directory / f"{obj.id}.yaml", _dump(obj))

    def save_claim(self, claim: Claim) -> None:
        self._write("claims", claim)
        self.claims[claim.id] = claim
        key = claim_key(claim)
        if key:
            self._claims_by_key[key] = claim.id

    def add_claim(self, claim: Claim) -> Claim:
        """Save a claim, deduplicating on its semantic identity.

        If a claim with the same key (predicate + scope + validity +
        sources) already exists, that claim is returned and nothing is
        written — the same rule proposed twice is one claim, whatever its
        wording. Free-text claims (no predicate) always save.
        """
        key = claim_key(claim)
        if key and key in self._claims_by_key:
            return self.claims[self._claims_by_key[key]]
        self.save_claim(claim)
        return claim

    def find_claim(self, key: str) -> Claim | None:
        cid = self._claims_by_key.get(key)
        return self.claims.get(cid) if cid else None

    def add_evidence(self, record: EvidenceRecord) -> None:
        path = self.root / "evidence" / f"{record.id}.yaml"
        if record.id in self.evidence or path.exists():
            raise AppendOnlyViolation(
                f"evidence {record.id} already exists — records are append-only"
            )
        self._write("evidence", record)
        self.evidence[record.id] = record

    def mark_evidence_stale(self, evidence_id: str) -> EvidenceRecord:
        """The single permitted evidence mutation."""
        record = self.evidence[evidence_id]
        updated = record.model_copy(update={"stale": True})
        self._write("evidence", updated)
        self.evidence[evidence_id] = updated
        return updated

    def save_question(self, card: ClarificationQuestion) -> None:
        self._write("questions", card)
        self.questions[card.id] = card

    def find_question(self, card: ClarificationQuestion) -> ClarificationQuestion | None:
        """The existing card this one would duplicate, or None.

        Identity is wording *within a scope*: the same question asked about
        two entities is two questions, and the second must never collapse
        into the first — that would be the silence the product forbids.
        """
        key = card.dedup_key()
        for existing in self.questions.values():
            if existing.dedup_key() == key:
                return existing
        return None

    def save_request(self, request: AnswerRequest) -> None:
        self._write("answers", request)
        self.requests[request.id] = request

    def save_required_knowledge(self, required: RequiredKnowledge) -> None:
        self._write("answers", required)
        self.required[required.id] = required

    def knowledge_for(self, request_id: str) -> RequiredKnowledge | None:
        for required in self.required.values():
            if required.request_id == request_id:
                return required
        return None

    def save_source(self, source: Source) -> None:
        # metadata about a source, not the dropped file itself (sources/)
        self._write("sources_meta", source)
        self.sources[source.id] = source

    def save_profile(self, profile: DataProfile) -> None:
        self._write("profiles", profile)
        self.profiles[profile.id] = profile

    def save_check_plan(self, check: CheckPlan) -> None:
        self._write("checks", check)
        self.checks[check.id] = check

    # -- convenience -----------------------------------------------------

    def evidence_for(self, claim: Claim) -> list[EvidenceRecord]:
        return [self.evidence[eid] for eid in claim.evidence_ids if eid in self.evidence]
