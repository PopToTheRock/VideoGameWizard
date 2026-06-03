"""Offline retriever for the evaluation harness.

Mirrors the server's retrieval contract exactly — same embedding model, same
cosine-distance collection, ``normalize_embeddings=True`` — but runs
synchronously, with none of the FastAPI / threadpool machinery. Keeping it
separate means the eval can run as a plain script while still measuring the same
retrieval the server performs.

Heavy imports (chromadb, sentence-transformers) are deferred to construction so
that importing this module stays cheap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eval import config


@dataclass(frozen=True)
class Candidate:
    """A retrieved chunk: its id, text, source article title, and raw score."""

    id: str
    document: str
    title: str
    score: float


class Retriever:
    """Embeds queries and fetches the nearest chunks from ChromaDB."""

    def __init__(
        self,
        chroma_path: str | None = None,
        embed_model: str = config.EMBED_MODEL,
        collection_name: str = config.COLLECTION_NAME,
    ) -> None:
        import chromadb
        from sentence_transformers import SentenceTransformer

        self._embedder = SentenceTransformer(embed_model)
        client = chromadb.PersistentClient(path=str(chroma_path or config.CHROMA_PATH))
        self._collection = client.get_collection(collection_name)

    def count(self) -> int:
        return self._collection.count()

    def retrieve(self, query: str, n_results: int) -> list[Candidate]:
        """Return the top ``n_results`` chunks for ``query``, best first.

        ChromaDB returns cosine *distance* (smaller = closer); we expose
        ``score = 1 - distance`` so higher is better, matching the reranker.
        """
        embedding = self._embedder.encode([query], normalize_embeddings=True)[0]
        query_vec = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

        results: dict[str, Any] = self._collection.query(
            query_embeddings=[query_vec],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )
        ids: list[str] = (results.get("ids") or [[]])[0]
        documents: list[str] = (results.get("documents") or [[]])[0]
        metadatas: list[dict[str, Any]] = (results.get("metadatas") or [[]])[0]
        distances: list[float] = (results.get("distances") or [[]])[0]

        return [
            Candidate(
                id=cid,
                document=doc,
                title=(meta or {}).get("title", ""),
                score=1.0 - dist,
            )
            for cid, doc, meta, dist in zip(ids, documents, metadatas, distances, strict=True)
        ]
