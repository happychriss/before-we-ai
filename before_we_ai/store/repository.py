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

from before_we_ai.model.objects import (
    Claim,
    ColumnProfile,
    ConceptClaim,
    EvidenceRecord,
    QuestionCard,
    RoleBindingClaim,
    Source,
)
from before_we_ai.store.layout import CONFIG_FILE, init_project

_CLAIM_TYPES = {
    "Claim": Claim,
    "ConceptClaim": ConceptClaim,
    "RoleBindingClaim": RoleBindingClaim,
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
        self.questions: dict[str, QuestionCard] = {}
        self.sources: dict[str, Source] = {}
        self.profiles: dict[str, ColumnProfile] = {}
        self._load()

    # -- loading ---------------------------------------------------------

    def _load(self) -> None:
        self.claims = {
            o.id: o for o in self._read_dir("claims", self._parse_claim, keep_type=True)
        }
        self.evidence = {
            o.id: o for o in self._read_dir("evidence", EvidenceRecord.model_validate)
        }
        self.questions = {
            o.id: o for o in self._read_dir("questions", QuestionCard.model_validate)
        }
        self.sources = {
            o.id: o for o in self._read_dir("sources_meta", Source.model_validate)
        }
        self.profiles = {
            o.id: o for o in self._read_dir("profiles", ColumnProfile.model_validate)
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

    # -- writing ---------------------------------------------------------

    def _write(self, dirname: str, obj: BaseModel) -> None:
        directory = self.root / dirname
        directory.mkdir(exist_ok=True)
        _atomic_write(directory / f"{obj.id}.yaml", _dump(obj))

    def save_claim(self, claim: Claim) -> None:
        self._write("claims", claim)
        self.claims[claim.id] = claim

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

    def save_question(self, card: QuestionCard) -> None:
        self._write("questions", card)
        self.questions[card.id] = card

    def save_source(self, source: Source) -> None:
        # metadata about a source, not the dropped file itself (sources/)
        self._write("sources_meta", source)
        self.sources[source.id] = source

    def save_profile(self, profile: ColumnProfile) -> None:
        self._write("profiles", profile)
        self.profiles[profile.id] = profile

    # -- convenience -----------------------------------------------------

    def evidence_for(self, claim: Claim) -> list[EvidenceRecord]:
        return [self.evidence[eid] for eid in claim.evidence_ids if eid in self.evidence]
