"""
Article chunker for the RAG pipeline.

Reads wikipedia_clean.jsonl and splits each article into overlapping
text chunks suitable for embedding. Outputs chunks.jsonl.

Chunking strategy:
  - Split article on paragraph boundaries (blank lines)
  - Accumulate paragraphs into a chunk up to MAX_CHUNK_CHARS
  - When a chunk is full, start a new one beginning with an overlap
    window taken from the end of the previous chunk
  - Paragraphs longer than MAX_CHUNK_CHARS are split at sentence
    boundaries to avoid exceeding the embedding model's token limit

Run from scraping/rag/:
    py chunker.py
"""

import hashlib
import json
import logging
import re
from pathlib import Path

import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Sentence boundary: end of sentence followed by whitespace
_RE_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_long_paragraph(para: str, max_chars: int) -> list[str]:
    """Split a paragraph that exceeds max_chars at sentence boundaries.

    Sentences that are themselves longer than max_chars are hard-split, so no
    returned piece ever exceeds max_chars (regardless of input shape).
    """
    sentences = _RE_SENTENCE_SPLIT.split(para)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        # A single sentence longer than the limit can never fit the buffer:
        # flush what we have and hard-split it into max_chars-sized pieces.
        if len(sentence) > max_chars:
            if current:
                pieces.append(current)
                current = ""
            for i in range(0, len(sentence), max_chars):
                pieces.append(sentence[i : i + max_chars])
        elif not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= max_chars:
            current += " " + sentence
        else:
            pieces.append(current)
            current = sentence
    if current:
        pieces.append(current)
    return pieces


_SEP = "\n\n"


def _tail_overlap(text: str, overlap_chars: int) -> str:
    """Return up to ``overlap_chars`` trailing characters of ``text``.

    Snapped to a word boundary so the overlap never begins mid-word. This is a
    character *budget*: unlike re-using whole paragraphs (the previous approach),
    it can never push the next chunk over the size limit.
    """
    if overlap_chars <= 0 or not text:
        return ""
    if len(text) <= overlap_chars:
        return text.strip()
    tail = text[-overlap_chars:]
    # Drop a leading partial word (everything up to and including the first space).
    space = tail.find(" ")
    if space != -1:
        tail = tail[space + 1 :]
    return tail.strip()


def chunk_article(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Split article text into overlapping chunks aligned to paragraph boundaries.

    **Every returned chunk is guaranteed to be at most ``max_chars`` characters.**
    The overlap is carried as a trailing-character budget rather than whole
    paragraphs, so it can never push a chunk past the limit (the previous version
    re-inserted whole paragraphs and routinely produced ~2x-oversize chunks).
    """
    # Split into paragraphs; hard-split any paragraph that alone exceeds max_chars
    # so the accumulation loop only ever sees pieces that can fit.
    raw_paragraphs = [p.strip() for p in text.split(_SEP)]
    paragraphs: list[str] = []
    for para in raw_paragraphs:
        if not para:
            continue
        if len(para) > max_chars:
            paragraphs.extend(split_long_paragraph(para, max_chars))
        else:
            paragraphs.append(para)

    chunks: list[str] = []
    buf = ""

    for para in paragraphs:
        candidate = para if not buf else buf + _SEP + para
        if len(candidate) <= max_chars:
            buf = candidate
            continue

        # `para` doesn't fit: emit the current chunk, then start a new one seeded
        # with a trailing overlap of the emitted text — but only when there is room
        # (drop the overlap rather than exceed max_chars).
        chunks.append(buf)
        overlap = _tail_overlap(buf, overlap_chars)
        seeded = overlap + _SEP + para if overlap else para
        buf = seeded if len(seeded) <= max_chars else para

    if buf:
        chunks.append(buf)

    return chunks


def make_chunk_id(title: str, chunk_index: int) -> str:
    """Stable unique ID for a chunk based on article title + position."""
    raw = f"{title}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    input_path = project_root / config.INPUT_FILE
    output_path = project_root / config.CHUNKS_FILE

    if not input_path.exists():
        log.error(f"Input file not found: {input_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    total_articles = total_chunks = skipped_chunks = 0
    max_chunk_len = 0

    with (
        open(input_path, encoding="utf-8") as in_f,
        open(output_path, "w", encoding="utf-8") as out_f,
    ):
        for raw_line in in_f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue

            article = json.loads(raw_line)
            total_articles += 1

            chunks = chunk_article(
                article["content"],
                max_chars=config.MAX_CHUNK_CHARS,
                overlap_chars=config.CHUNK_OVERLAP_CHARS,
            )

            for i, chunk_text in enumerate(chunks):
                # Invariant: chunk_article must never exceed the configured cap
                # (this is what keeps chunks under the embedder's token limit).
                assert len(chunk_text) <= config.MAX_CHUNK_CHARS, (
                    f"chunk {i} of {article['title']!r} is {len(chunk_text)} chars "
                    f"(> {config.MAX_CHUNK_CHARS})"
                )
                max_chunk_len = max(max_chunk_len, len(chunk_text))

                if len(chunk_text) < config.MIN_CHUNK_CHARS:
                    skipped_chunks += 1
                    continue

                record = {
                    "id": make_chunk_id(article["title"], i),
                    "source": article["source"],
                    "title": article["title"],
                    "url": article["url"],
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "content": chunk_text,
                    "categories": article.get("categories", []),
                }
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                total_chunks += 1

            if total_articles % 2000 == 0:
                log.info(
                    "  Processed %d articles -> %d chunks so far...",
                    total_articles,
                    total_chunks,
                )

    avg = total_chunks / total_articles if total_articles else 0
    log.info(
        "Done. Articles: %d, Chunks: %d (avg %.1f/article), Skipped: %d",
        total_articles,
        total_chunks,
        avg,
        skipped_chunks,
    )
    log.info("Max chunk: %d chars (cap %d)", max_chunk_len, config.MAX_CHUNK_CHARS)
    log.info("Output: %s", output_path.resolve())


if __name__ == "__main__":
    main()
