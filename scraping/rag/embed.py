"""
Embedding + ChromaDB ingestion script.

Reads chunks.jsonl, embeds all chunks in one GPU pass, then ingests
into ChromaDB in large batches to minimise HNSW index overhead.

Run from scraping/rag/:
    py embed.py

Requirements (Windows env):
    pip install sentence-transformers chromadb

Note: this is a one-shot batch script, run manually to (re)build the vector
index. It is intentionally outside the automated test suite — it imports the
full ML stack and operates on the on-disk corpus rather than exposing unit-
testable units.
"""

import json
import logging
import time
from pathlib import Path

import chromadb
import config
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "game_knowledge"

# Chunks per GPU forward pass — large batches maximise GPU utilisation.
EMBED_BATCH_SIZE = 2048

# Chunks per ChromaDB add() call.
# ChromaDB's internal max is ~41 666; staying at 40 000 keeps us safely under.
# Fewer, larger batches = less HNSW index overhead.
CHROMA_BATCH_SIZE = 5000


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent.parent
    chunks_path = project_root / config.CHUNKS_FILE
    chroma_path = project_root / "scraping/data/chromadb"

    if not chunks_path.exists():
        log.error(f"Chunks file not found: {chunks_path}")
        return

    # ------------------------------------------------------------------ device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log.info(f"Device: {device}")
    if device == "cuda":
        log.info(f"GPU: {torch.cuda.get_device_name(0)}")

    # ---------------------------------------------------------- embedding model
    log.info(f"Loading model: {EMBED_MODEL}")
    model = SentenceTransformer(EMBED_MODEL, device=device)
    # Pin the sequence length explicitly rather than relying on the model default.
    # Tokens beyond this are truncated at embed time (the chunk tail then never
    # contributes to its vector), so the chunker caps chunk size to stay under it.
    model.max_seq_length = config.EMBED_MAX_TOKENS

    # ------------------------------------------------------------------ chunks
    log.info(f"Loading and deduplicating chunks from {chunks_path}...")
    seen: dict[str, dict] = {}
    with open(chunks_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                c = json.loads(line)
                seen[c["id"]] = c  # last occurrence wins for any duplicates

    chunks = list(seen.values())
    log.info(f"Loaded {len(chunks):,} unique chunks")

    # ----------------------------------------------------------------- ChromaDB
    # Delete and recreate the collection for a clean run.
    chroma_path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(chroma_path))
    try:
        client.delete_collection(COLLECTION_NAME)
        log.info(f"Deleted existing collection '{COLLECTION_NAME}'")
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    # ------------------------------------------------------ phase 1: embed all
    log.info(f"Embedding {len(chunks):,} chunks (batch_size={EMBED_BATCH_SIZE})...")
    texts = [c["content"] for c in chunks]

    # Audit token lengths so any residual truncation is visible, not silent. A
    # chunk over EMBED_MAX_TOKENS still serves its full text as context but only
    # its first EMBED_MAX_TOKENS tokens shape its embedding (and thus retrieval).
    tok_lens = np.array(
        [len(ids) for ids in model.tokenizer(texts, add_special_tokens=True)["input_ids"]]
    )
    over = int((tok_lens > config.EMBED_MAX_TOKENS).sum())
    p50, p95, p99, p100 = np.percentile(tok_lens, [50, 95, 99, 100])
    log.info(
        "Token lengths — median %.0f, p95 %.0f, p99 %.0f, max %.0f",
        p50,
        p95,
        p99,
        p100,
    )
    if over:
        log.warning(
            "%d/%d chunks (%.2f%%) exceed the %d-token limit and will be truncated — "
            "lower MAX_CHUNK_CHARS or use a longer-context embedding model.",
            over,
            len(texts),
            100 * over / len(texts),
            config.EMBED_MAX_TOKENS,
        )
    else:
        log.info("All chunks fit within the %d-token embedding limit.", config.EMBED_MAX_TOKENS)

    t0 = time.time()
    embeddings: np.ndarray = model.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    embed_secs = time.time() - t0
    log.info(f"Embedding done in {embed_secs:.1f}s ({len(chunks) / embed_secs:.0f} chunks/s)")

    # ---------------------------------------------------- phase 2: ingest all
    log.info(f"Ingesting into ChromaDB in batches of {CHROMA_BATCH_SIZE:,}...")
    total = len(chunks)
    t0 = time.time()

    for start in range(0, total, CHROMA_BATCH_SIZE):
        batch_chunks = chunks[start : start + CHROMA_BATCH_SIZE]
        batch_embeddings = embeddings[start : start + CHROMA_BATCH_SIZE]
        end = start + len(batch_chunks)

        collection.add(
            ids=[c["id"] for c in batch_chunks],
            embeddings=batch_embeddings.tolist(),
            documents=[c["content"] for c in batch_chunks],
            metadatas=[
                {
                    "source": c["source"],
                    "title": c["title"],
                    "url": c["url"],
                    "chunk_index": c["chunk_index"],
                    "total_chunks": c["total_chunks"],
                    "categories": " | ".join(c.get("categories", [])),
                }
                for c in batch_chunks
            ],
        )
        log.info(f"  Ingested {end:,}/{total:,} ({100 * end / total:.1f}%)")

    ingest_secs = time.time() - t0
    log.info(f"Ingestion done in {ingest_secs:.1f}s")
    log.info(f"Collection '{COLLECTION_NAME}': {collection.count():,} chunks")
    log.info(f"Store: {chroma_path.resolve()}")


if __name__ == "__main__":
    main()
