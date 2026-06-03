"""Cross-encoder reranker for the evaluation harness.

The first-stage retriever (a bi-encoder) embeds the query and every chunk
*independently*, which is fast enough to scan 190k chunks but blind to
fine-grained query-document interaction. A **cross-encoder** instead feeds the
``(query, chunk)`` pair through the model together and scores relevance directly
— far more accurate, but too slow to run over the whole corpus. So we use it the
standard way: retrieve a shortlist cheaply, then rerank just that shortlist.

The model (``ms-marco-MiniLM-L-6-v2``) is loaded lazily on construction.
"""

from __future__ import annotations

from eval import config
from eval.retriever import Candidate


class CrossEncoderReranker:
    """Re-scores retrieved candidates by direct query-document relevance."""

    def __init__(self, model_name: str = config.RERANK_MODEL) -> None:
        from sentence_transformers import CrossEncoder

        self._model = CrossEncoder(model_name)

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        """Return ``candidates`` reordered best-first by cross-encoder score.

        Each returned ``Candidate`` carries its new relevance score; the input
        order (first-stage retrieval) is discarded.
        """
        if not candidates:
            return []

        pairs = [[query, c.document] for c in candidates]
        scores = self._model.predict(pairs)

        rescored = [
            Candidate(id=c.id, document=c.document, title=c.title, score=float(s))
            for c, s in zip(candidates, scores, strict=True)
        ]
        rescored.sort(key=lambda c: c.score, reverse=True)
        return rescored
