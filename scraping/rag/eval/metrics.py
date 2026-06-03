"""Retrieval-quality metrics for the RAG evaluation harness.

Every function here is **pure and dependency-free** (no torch / chromadb), so the
test suite runs them in CI under ``requirements-test.txt``.

Each eval question has exactly one gold chunk. With a single relevant document,
recall@k collapses to hit@k, so we report the three metrics that actually carry
signal in that regime:

* **hit-rate@k** — was the gold chunk anywhere in the top *k*? (Did we find it?)
* **MRR** — mean of 1/rank of the gold chunk. (How *high* did we rank it?)
* **nDCG@k** — rank-discounted gain; with one gold doc of gain 1 the ideal DCG
  is 1, so nDCG@k = 1/log2(rank+1) when the gold doc is within *k*, else 0.

A "ranking" is the ordered list of retrieved chunk ids, best first.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence


def rank_of(ranked_ids: Sequence[str], gold_id: str) -> int | None:
    """1-based rank of ``gold_id`` in ``ranked_ids``, or ``None`` if absent."""
    for i, cid in enumerate(ranked_ids):
        if cid == gold_id:
            return i + 1
    return None


def hit_at_k(ranked_ids: Sequence[str], gold_id: str, k: int) -> bool:
    """True if the gold chunk is within the top ``k`` results."""
    return gold_id in ranked_ids[:k]


def reciprocal_rank(ranked_ids: Sequence[str], gold_id: str) -> float:
    """1/rank of the gold chunk, or 0.0 if it was not retrieved at all."""
    rank = rank_of(ranked_ids, gold_id)
    return 0.0 if rank is None else 1.0 / rank


def ndcg_at_k(ranked_ids: Sequence[str], gold_id: str, k: int) -> float:
    """nDCG@k for a single relevant document (ideal DCG = 1)."""
    rank = rank_of(ranked_ids[:k], gold_id)
    if rank is None:
        return 0.0
    return 1.0 / math.log2(rank + 1)


def mean(values: Iterable[float]) -> float:
    """Arithmetic mean; 0.0 for an empty sequence (booleans count as 0/1)."""
    vals = [float(v) for v in values]
    return sum(vals) / len(vals) if vals else 0.0


def aggregate(
    rankings: Sequence[tuple[Sequence[str], str]],
    ks: Sequence[int] = (1, 3, 5, 10),
) -> dict[str, float]:
    """Aggregate metrics over ``(ranked_ids, gold_id)`` pairs.

    Returns a flat dict: ``hit_rate@k`` and ``ndcg@k`` for each ``k``, plus ``mrr``.
    """
    summary: dict[str, float] = {}
    for k in ks:
        summary[f"hit_rate@{k}"] = mean(hit_at_k(r, g, k) for r, g in rankings)
        summary[f"ndcg@{k}"] = mean(ndcg_at_k(r, g, k) for r, g in rankings)
    summary["mrr"] = mean(reciprocal_rank(r, g) for r, g in rankings)
    return summary
