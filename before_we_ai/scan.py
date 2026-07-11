"""Phase 0–1 orchestration: connect, normalize, fingerprint, measure.

``scan(root)`` is the seam the M8 CLI command will wrap. It reads the
source declarations from ``before-ai.yaml``, builds the disposable
analysis catalog in ``cache/``, records every normalization decision as
declaration evidence, saves Source metadata and column profiles, and
writes the candidate matrix. It creates **no claims** — scanning is
measurement, and measurement cannot promote anything.

Idempotent: re-scanning refreshes profiles and matrix in place (stable
IDs per source/table/column) and appends declarations only for decisions
not already on record for the same source fingerprint.
"""

from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import yaml

from before_we_ai.model.enums import Actor, EvidenceType
from before_we_ai.model.objects import EvidenceRecord, Source
from before_we_ai.profile.candidates import build_matrix, write_matrix
from before_we_ai.profile.columns import profile_view
from before_we_ai.sources.attach import SourceSpec, build_catalog
from before_we_ai.store.layout import CONFIG_FILE
from before_we_ai.store.repository import ProjectStore


@dataclass
class ScanResult:
    source_ids: dict[str, str] = field(default_factory=dict)  # source name -> id
    views: list[str] = field(default_factory=list)
    profiles_written: int = 0
    declarations_added: int = 0
    candidates: int = 0
    matrix_path: Path | None = None
    warnings: list[str] = field(default_factory=list)


def load_specs(root: Path) -> list[SourceSpec]:
    config = yaml.safe_load((root / CONFIG_FILE).read_text(encoding="utf-8")) or {}
    return [SourceSpec.model_validate(entry) for entry in config.get("sources", [])]


def scan(root: str | Path) -> ScanResult:
    root = Path(root)
    store = ProjectStore(root)
    specs = load_specs(root)
    result = ScanResult()

    (root / "cache").mkdir(exist_ok=True)
    con = duckdb.connect(str(root / "cache" / "analysis.duckdb"))
    try:
        entries = build_catalog(root, specs, con)

        sources_by_name = {s.name: s for s in store.sources.values()}
        profile_ids = {
            (p.source_id, p.table, p.column): p.id for p in store.profiles.values()
        }
        existing_declarations = {
            (str(e.payload), str(e.source_fingerprints))
            for e in store.evidence.values()
            if e.type is EvidenceType.DECLARATION
        }

        all_profiles = []
        for entry in entries:
            spec = entry.spec
            fingerprint = {"file": entry.file_fingerprint, "tables": entry.views}
            existing = sources_by_name.get(spec.name)
            source = (
                existing.model_copy(update={"fingerprint": fingerprint})
                if existing
                else Source(
                    name=spec.name, kind=spec.kind,
                    location=spec.location, fingerprint=fingerprint,
                )
            )
            store.save_source(source)
            result.source_ids[spec.name] = source.id

            stamp = {spec.name: entry.file_fingerprint["sha256"]}
            for decision in entry.decisions:
                payload = {"source": spec.name, **decision}
                if (str(payload), str(stamp)) in existing_declarations:
                    continue
                store.add_evidence(EvidenceRecord(
                    type=EvidenceType.DECLARATION,
                    actor=Actor.SYSTEM,
                    payload=payload,
                    source_fingerprints=stamp,
                ))
                result.declarations_added += 1

            for view in entry.views:
                result.views.append(view)
                for profile in profile_view(con, view, source.id):
                    known = profile_ids.get((source.id, profile.table, profile.column))
                    if known:
                        profile = profile.model_copy(update={"id": known})
                    store.save_profile(profile)
                    all_profiles.append(profile)
                    result.profiles_written += 1

        matrix = build_matrix(con, all_profiles)
        result.matrix_path = write_matrix(matrix, root / "profiles")
        result.candidates = len(matrix["candidates"])
        result.warnings = list(matrix["warnings"])
    finally:
        con.close()
    return result
