"""Blocks → chunks: the unit a quote is validated against.

Two properties are load-bearing and everything here exists to keep them.

**Deterministic.** Identical PDF bytes must produce identical chunk ids and
identical chunk text, because chunks go into V3's prompt and the drift
guard pins that prompt's hash. A chunker that drifted would turn offline
replay into a coin flip.

**Kind-pure.** A chunk never mixes a chart label with the paragraph next to
it, because the chunk is what tells an anchor where it came from. Mixing
would let a chart figure enter the store wearing a text anchor's authority
— which is exactly the trap F23 sets.
"""

from dataclasses import dataclass

from before_we_ai.documents.extract import Block, read_pdf

# Small enough that a quote's neighbourhood stays readable, large enough
# that a policy paragraph is not cut into fragments a model must reassemble.
TARGET_CHARS = 1200
JOIN = "\n"


@dataclass(frozen=True)
class Chunk:
    """A contiguous run of same-kind text with its position on the page."""

    id: str
    source: str
    page: int
    seq: int  # chunk order within the page
    kind: str
    text: str
    start: int  # char span within the page text …
    end: int  # … which is the page's chunks joined by JOIN

    @property
    def label(self) -> str:
        """How a reader is told where this is — never a ULID."""
        return f"{self.source} p.{self.page}"


def _pack(blocks: list[Block]) -> list[list[Block]]:
    """Greedy runs of one kind, split when the target size is exceeded."""
    runs: list[list[Block]] = []
    current: list[Block] = []
    size = 0
    for block in blocks:
        if current and (block.kind != current[-1].kind
                        or size + len(block.text) > TARGET_CHARS):
            runs.append(current)
            current, size = [], 0
        current.append(block)
        size += len(block.text) + len(JOIN)
    if current:
        runs.append(current)
    return runs


def chunk_blocks(blocks: list[Block], source: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    pages = sorted({block.page for block in blocks})
    for page in pages:
        cursor = 0
        on_page = [block for block in blocks if block.page == page]
        for seq, run in enumerate(_pack(on_page)):
            text = JOIN.join(block.text for block in run)
            chunks.append(Chunk(
                id=f"{source}:p{page}:{seq}",
                source=source,
                page=page,
                seq=seq,
                kind=run[0].kind,
                text=text,
                start=cursor,
                end=cursor + len(text),
            ))
            cursor += len(text) + len(JOIN)
    return chunks


def chunk_pdf(path, source: str) -> list[Chunk]:
    return chunk_blocks(read_pdf(path), source)


def page_text(chunks: list[Chunk], page: int) -> str:
    """The text a chunk's span indexes into — built the way it was measured."""
    return JOIN.join(c.text for c in chunks if c.page == page)
