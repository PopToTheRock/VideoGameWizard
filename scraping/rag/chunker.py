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


def chunk_article(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """
    Split article text into overlapping chunks aligned to paragraph boundaries.
    Returns a list of chunk strings.
    """
    # Split into paragraphs, discarding blank lines
    raw_paragraphs = [p.strip() for p in text.split("\n\n")]
    paragraphs: list[str] = []
    for para in raw_paragraphs:
        if not para:
            continue
        if len(para) > max_chars:
            paragraphs.extend(split_long_paragraph(para, max_chars))
        else:
            paragraphs.append(para)

    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)

        if current_len + para_len > max_chars and current_parts:
            # Emit current chunk
            chunks.append("\n\n".join(current_parts))

            # Build overlap: walk back through parts until we have overlap_chars
            overlap_parts: list[str] = []
            overlap_len = 0
            for part in reversed(current_parts):
                if overlap_len >= overlap_chars:
                    break
                overlap_parts.insert(0, part)
                overlap_len += len(part)

            current_parts = overlap_parts
            current_len = overlap_len

        current_parts.append(para)
        current_len += para_len

    # Emit any remaining content
    if current_parts:
        chunks.append("\n\n".join(current_parts))

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
    log.info("Output: %s", output_path.resolve())


if __name__ == "__main__":
    main()
