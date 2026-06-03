"""Run the RAG retrieval evaluation and report baseline vs. reranked metrics.

For every question in the gold set:

1. Retrieve the top-N candidate chunks (first-stage bi-encoder + ChromaDB).
2. Score the **baseline** ranking (retrieval order) against the gold chunk.
3. Rerank those same N with the cross-encoder and score again.

Because the reranker only reorders the retrieved shortlist, hit-rate@k for
k <= N is identical before and after — reranking can't conjure a chunk retrieval
missed. Where it pays off is *ordering*: MRR and nDCG, i.e. pushing the right
chunk toward the top. That is exactly the lift we want to quantify.

Run from ``scraping/rag/``:

    py -m eval.run_eval                  # full set, with reranking
    py -m eval.run_eval --limit 20       # quick smoke test
    py -m eval.run_eval --no-rerank      # baseline only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from eval import config, metrics
from eval.retriever import Retriever

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("run_eval")


def load_eval_set(path: Path, limit: int | None) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(
            f"Eval set not found: {path}\nGenerate it first: py -m eval.generate_eval_set"
        )
    rows: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows[:limit] if limit else rows


def _format_table(baseline: dict[str, float], reranked: dict[str, float] | None) -> str:
    keys = list(baseline)
    width = max(len(k) for k in keys)
    if reranked is None:
        lines = [f"{'metric':<{width}}   value", f"{'-' * width}   -----"]
        lines += [f"{k:<{width}}   {baseline[k]:.4f}" for k in keys]
        return "\n".join(lines)

    header = f"{'metric':<{width}}   baseline   +rerank     delta"
    rule = f"{'-' * width}   --------   -------   -------"
    lines = [header, rule]
    for k in keys:
        b, r = baseline[k], reranked[k]
        lines.append(f"{k:<{width}}   {b:>8.4f}   {r:>7.4f}   {r - b:>+7.4f}")
    return "\n".join(lines)


def evaluate(
    eval_set: list[dict],
    retriever: Retriever,
    n_candidates: int,
    ks: tuple[int, ...],
    do_rerank: bool,
) -> dict:
    """Score retrieval at two gold granularities, before and after reranking.

    * **chunk-level** — the exact source chunk must be retrieved (strict).
    * **article-level** — any chunk from the source article counts (this is what
      actually feeds the LLM as relevant context, so it matters more in practice).

    The same metric functions serve both: we just match a ranked list of chunk
    ids against ``gold_chunk_id``, or a ranked list of titles against ``gold_title``.
    """
    reranker = None
    if do_rerank:
        from eval.rerank import CrossEncoderReranker

        log.info("Loading reranker: %s", config.RERANK_MODEL)
        reranker = CrossEncoderReranker()

    # (ranked_keys, gold_key) pairs, per granularity and per stage.
    base_chunk: list[tuple[list[str], str]] = []
    base_article: list[tuple[list[str], str]] = []
    rr_chunk: list[tuple[list[str], str]] = []
    rr_article: list[tuple[list[str], str]] = []

    for i, row in enumerate(eval_set, 1):
        gold_id, gold_title = row["gold_chunk_id"], row["gold_title"]
        candidates = retriever.retrieve(row["question"], n_results=n_candidates)
        base_chunk.append(([c.id for c in candidates], gold_id))
        base_article.append(([c.title for c in candidates], gold_title))

        if reranker is not None:
            reranked = reranker.rerank(row["question"], candidates)
            rr_chunk.append(([c.id for c in reranked], gold_id))
            rr_article.append(([c.title for c in reranked], gold_title))

        if i % 25 == 0 or i == len(eval_set):
            log.info("  evaluated %d/%d", i, len(eval_set))

    def level(base: list, rr: list) -> dict:
        out = {"baseline": metrics.aggregate(base, ks)}
        if reranker is not None:
            out["reranked"] = metrics.aggregate(rr, ks)
        return out

    return {
        "n_questions": len(eval_set),
        "n_candidates": n_candidates,
        "ks": list(ks),
        "chunk_level": level(base_chunk, rr_chunk),
        "article_level": level(base_article, rr_article),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval quality.")
    parser.add_argument("--eval-set", type=Path, default=config.EVAL_SET_PATH)
    parser.add_argument("--n-candidates", type=int, default=config.DEFAULT_N_CANDIDATES)
    parser.add_argument("--limit", type=int, default=None, help="evaluate only the first N")
    parser.add_argument("--no-rerank", action="store_true", help="baseline retrieval only")
    args = parser.parse_args()

    try:
        eval_set = load_eval_set(args.eval_set, args.limit)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 1
    if not eval_set:
        log.error("Eval set is empty: %s", args.eval_set)
        return 1
    log.info("Loaded %d eval questions", len(eval_set))

    log.info("Loading retriever (embedder + ChromaDB) ...")
    retriever = Retriever()
    log.info("Collection holds %s chunks", f"{retriever.count():,}")

    result = evaluate(
        eval_set,
        retriever,
        n_candidates=args.n_candidates,
        ks=config.DEFAULT_KS,
        do_rerank=not args.no_rerank,
    )

    print(
        f"\nRAG retrieval evaluation - {result['n_questions']} questions, "
        f"top-{result['n_candidates']} candidates"
    )
    for level_key, title in (
        ("chunk_level", "Chunk-level (exact source chunk)"),
        ("article_level", "Article-level (any chunk from the source article)"),
    ):
        level = result[level_key]
        print(f"\n{title}")
        print(_format_table(level["baseline"], level.get("reranked")) + "\n")

    # Persist a timestamped report (json) for the record / writeup.
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = config.RESULTS_DIR / f"eval_{stamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    log.info("Wrote results -> %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
