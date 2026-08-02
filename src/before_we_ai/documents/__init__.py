"""Stage 2c — reading the documents, which is measurement, not belief.

``read_documents(root)`` is the document twin of ``scan(root)``: it takes
every source declared as ``kind: pdf``, extracts its text with the origin
of each passage attached, chunks it deterministically, indexes it for
retrieval, and writes one profile per document. Like ``scan``, it creates
**no claims** — reading a policy does not make its rule true, it makes it
available to be proposed, which is the next stage's job.

The two seams stay separate because a reader can inspect them separately:
a wrong number in a profile is a measurement bug, a wrong reading of a
sentence is a model proposal, and running them under one command would
blur the only boundary this product really has.
"""

from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pymupdf

from before_we_ai.core.objects import DocumentProfile, Source
from before_we_ai.documents.chunk import Chunk, chunk_pdf
from before_we_ai.documents.index import (
    CHUNK_TABLE,
    FullTextSearchUnavailable,
    build_chunk_index,
    load_chunks,
    retrieve,
    search,
)
from before_we_ai.sources.attach import load_specs
from before_we_ai.sources.fingerprint import file_fingerprint
from before_we_ai.store.repository import ProjectStore

# The library prints a one-off suggestion to install its layout add-on the
# first time a page is analysed. Walkthrough output is read by a human
# looking for surprises, so a message that is not about their data is noise.
pymupdf.no_recommend_layout()

__all__ = [
    "CHUNK_TABLE",
    "Chunk",
    "DocumentsResult",
    "FullTextSearchUnavailable",
    "chunk_pdf",
    "load_chunks",
    "read_documents",
    "retrieve",
    "search",
]


@dataclass
class DocumentsResult:
    source_ids: dict[str, str] = field(default_factory=dict)  # name -> id
    chunks: int = 0
    pages: int = 0
    profiles_written: int = 0
    kinds: dict[str, int] = field(default_factory=dict)


def read_documents(root: str | Path) -> DocumentsResult:
    root = Path(root)
    store = ProjectStore(root)
    specs = [s for s in load_specs(root) if s.kind == "pdf"]
    result = DocumentsResult()

    sources_by_name = {s.name: s for s in store.sources.values()}
    profiles_by_document = {p.document: p.id for p in store.documents.values()}

    all_chunks: list[Chunk] = []
    for spec in specs:
        path = spec.resolve(root)
        chunks = chunk_pdf(path, spec.name)
        all_chunks.extend(chunks)

        existing = sources_by_name.get(spec.name)
        fingerprint = file_fingerprint(path)
        source = (
            existing.model_copy(update={"fingerprint": fingerprint,
                                        "scope": spec.scope})
            if existing
            else Source(name=spec.name, kind=spec.kind, location=spec.location,
                        scope=spec.scope, fingerprint=fingerprint)
        )
        store.save_source(source)
        result.source_ids[spec.name] = source.id

        kinds: dict[str, int] = {}
        for chunk in chunks:
            kinds[chunk.kind] = kinds.get(chunk.kind, 0) + 1
        pages = len({c.page for c in chunks})
        profile = DocumentProfile(
            source_id=source.id,
            document=spec.name,
            pages=pages,
            chunk_count=len(chunks),
            char_count=sum(len(c.text) for c in chunks),
            kinds=kinds,
        )
        known = profiles_by_document.get(spec.name)
        if known:  # re-reading a document keeps its profile's identity
            profile = profile.model_copy(update={"id": known})
        store.save_document_profile(profile)

        result.profiles_written += 1
        result.pages += pages
        for kind, count in kinds.items():
            result.kinds[kind] = result.kinds.get(kind, 0) + count

    (root / "cache").mkdir(exist_ok=True)
    con = duckdb.connect(str(root / "cache" / "analysis.duckdb"))
    try:
        result.chunks = build_chunk_index(con, all_chunks)
    finally:
        con.close()
    return result
