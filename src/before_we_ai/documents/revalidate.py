"""Re-reading a changed document: which quotes survived it.

Staleness is one-way — an anchor whose passage was rewritten stays marked,
because that reading really was taken against text that is gone. But most
edits to a document leave most of it alone, and a policy sentence that is
still there, word for word, is still true. Making a human re-confirm it,
or spending a model call to find it again, would be a cost imposed by our
bookkeeping rather than by their change.

So the flagged anchors get one deterministic second look: is this exact
quote still in this passage? If yes, a fresh anchor is appended — new
record, new fingerprints, live. If no, the flag stands and the claim has
lost its documentary support, which is a thing the reader must see.

No model is involved and none may be: this decides nothing about meaning,
only about whether a string is still present.
"""

from before_we_ai.core.enums import EvidenceType
from before_we_ai.core.objects import EvidenceRecord
from before_we_ai.documents.chunk import Chunk
from before_we_ai.store.proposals import ProposalStore, QuoteNotFound
from before_we_ai.store.repository import ProjectStore


def revalidate_anchors(
    store: ProjectStore, chunks: list[Chunk]
) -> list[EvidenceRecord]:
    """Re-anchor every stale anchor whose quote is still where it was."""
    by_id = {chunk.id: chunk for chunk in chunks}
    proposals = ProposalStore(store)
    fresh: list[EvidenceRecord] = []

    for record in list(store.evidence.values()):
        if record.type is not EvidenceType.DOCUMENT_ANCHOR or not record.stale:
            continue
        if record.claim_id not in store.claims:
            continue
        chunk = by_id.get(record.payload.get("chunk_id"))
        if chunk is None:
            continue
        try:
            # Everything but the quote is re-derived from the document as
            # it is now: the page it sits on and the kind of passage it is
            # are properties of the current page, never of the old record.
            fresh.append(proposals.anchor(
                record.claim_id,
                quote=record.payload["quote"],
                chunk_id=chunk.id,
                chunk_text=chunk.text,
                kind=chunk.kind,
                source=record.payload["source"],
                page=chunk.page,
            ))
        except QuoteNotFound:
            continue  # the sentence is gone; the flag is the right answer

    return fresh
