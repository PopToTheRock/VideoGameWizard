# RAG Evaluation Harness

Measures how well the retrieval half of the RAG pipeline actually works — and
quantifies the lift from **cross-encoder reranking** — on a reproducible,
synthetically-generated gold set. Retrieval quality is the ceiling on answer
quality: the LLM can only ground its answer in what we retrieve, so this is
where the system is won or lost.

Everything runs **fully locally** (no cloud APIs): the embedding model and
ChromaDB for retrieval, a local cross-encoder for reranking, and `llama3.1:8b`
via Ollama only to *author* the eval set.

## How the gold set is built (synthetic, self-labelling)

Hand-labelling "which chunk answers this question" for thousands of chunks is
infeasible. Instead we exploit a simple trick that yields gold labels for free:

1. Sample chunks from `chunks.jsonl` with a **fixed seed** (reproducible).
2. For each chunk, ask `llama3.1:8b` to write one specific question answerable
   *only* from that chunk, plus a short answer.
3. The chunk we started from **is** the gold document — so every question ships
   with its correct `gold_chunk_id` and `gold_title`.

```bash
# from scraping/rag/  (needs Ollama serving llama3.1:8b)
py -m eval.generate_eval_set --n 150 --seed 42
```

The generated `data/eval_set.jsonl` is committed as the canonical benchmark;
regenerate only when the corpus changes.

## Metrics

Each question has exactly one gold chunk, so recall@k collapses to hit@k. We
report the three metrics that carry signal in that regime, at two granularities:

| Metric | Question it answers |
|--------|---------------------|
| **hit-rate@k** | Was the gold result anywhere in the top *k*? (Did we find it at all?) |
| **MRR** | Mean of 1/rank of the gold result. (How *high* did we rank it?) |
| **nDCG@k** | Rank-discounted gain; 1.0 if gold is at rank 1, decaying with depth. |

- **Chunk-level** — the *exact* source chunk must be retrieved (strict).
- **Article-level** — *any* chunk from the source article counts. This is closer
  to what actually matters: the server feeds the LLM the top-k chunks, and any
  chunk from the right article is relevant grounding context.

Why both? A fact's "source" chunk is often *not* the closest semantic match to
the question — sibling chunks of the same article frequently are. Chunk-level
alone understates retrieval quality; the gap between the two levels is itself
informative.

## Reranking

First-stage retrieval is a **bi-encoder**: query and chunks are embedded
independently, which is fast enough to scan ~190k chunks but blind to
fine-grained query–document interaction. A **cross-encoder** scores each
`(query, chunk)` pair jointly — much more accurate, too slow for the full
corpus. So we use the standard pattern: retrieve a top-20 shortlist cheaply,
then rerank just those 20. Because reranking only *reorders* the shortlist, it
can't raise hit-rate@k beyond what retrieval already found — its payoff is
**ordering** (MRR, nDCG, hit@1).

```bash
# from scraping/rag/
py -m eval.run_eval                  # full set, baseline vs. reranked
py -m eval.run_eval --limit 20       # quick smoke test
py -m eval.run_eval --no-rerank      # baseline only
```

## Results

150 synthetic questions · top-20 candidates · seed 42 · embeddings
`all-MiniLM-L6-v2` · reranker `cross-encoder/ms-marco-MiniLM-L-6-v2`
(recorded 2026-06-25, over the **191,193-chunk** corpus — chunks capped at 850
chars so all but 0.09% fit the embedder's 256-token window; see `embed.py`'s
token audit).

**Article-level** (any chunk from the source article — the metric that tracks
grounding quality):

| metric | baseline | +rerank | Δ |
|--------|---------:|--------:|----:|
| hit-rate@1 | 0.533 | **0.680** | +0.147 |
| hit-rate@3 | 0.673 | 0.767 | +0.093 |
| hit-rate@5 | 0.713 | 0.793 | +0.080 |
| hit-rate@10 | 0.793 | 0.800 | +0.007 |
| nDCG@10 | 0.660 | 0.745 | +0.086 |
| **MRR** | 0.619 | **0.728** | +0.109 |

**Chunk-level** (exact source chunk — strict):

| metric | baseline | +rerank | Δ |
|--------|---------:|--------:|----:|
| hit-rate@1 | 0.293 | **0.473** | +0.180 |
| hit-rate@5 | 0.493 | 0.613 | +0.120 |
| hit-rate@10 | 0.573 | 0.613 | +0.040 |
| nDCG@10 | 0.425 | 0.553 | +0.127 |
| **MRR** | 0.383 | **0.532** | +0.150 |

**Takeaways**

- Reranking improves **every** metric at both granularities. The largest wins are
  at **hit-rate@1** — chunk-level **0.29 → 0.47 (+61% relative)**, article-level
  **0.53 → 0.68 (+28%)** — and MRR (+0.11–0.15). The retrieve-shortlist-then-rerank
  pattern pays off exactly where it should: pushing the right context to rank 1.
- hit-rate@10 barely moves (+0.01–0.04) — as expected, since reranking only
  reorders the already-retrieved shortlist.
- **On the corrected corpus vs. the earlier 1000-char run:** chunk-level (exact
  source) *improved* (baseline hit@1 0.24 → 0.29, reranked 0.33 → 0.47) — smaller,
  fully-embedded chunks are easier to pinpoint now that chunk tails are no longer
  silently truncated. Article-level dipped slightly (baseline 0.60 → 0.53): the old
  oversized chunks carried heavy paragraph overlap, so an article's chunks were
  near-duplicates that *inflated* "any chunk from the article" hits. The leaner
  corpus has less redundancy — a lower but more honest number. (This is a freshly
  regenerated gold set, so treat it as a new benchmark, not a like-for-like delta.)
- The chunk-vs-article gap still shows first-stage retrieval finds the right
  *topic* more reliably than the exact source chunk — the motivation for the
  reranker, and a baseline for the fine-tuning work.

## Files

| File | Purpose |
|------|---------|
| `config.py` | Shared paths, model names, defaults (mirrors `server.Settings`) |
| `generate_eval_set.py` | Build the synthetic gold set via Ollama |
| `retriever.py` | Offline retriever — same embed model + cosine collection as the server |
| `rerank.py` | Cross-encoder reranker |
| `metrics.py` | Pure, dependency-free metric functions (unit-tested in `../tests/`) |
| `run_eval.py` | Orchestrates retrieval → metrics → rerank → report |
| `data/eval_set.jsonl` | The committed benchmark (150 questions) |
| `results/` | Timestamped JSON reports (gitignored) |
