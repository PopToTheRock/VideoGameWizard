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
(recorded 2026-06-03).

**Article-level** (any chunk from the source article — the metric that tracks
grounding quality):

| metric | baseline | +rerank | Δ |
|--------|---------:|--------:|----:|
| hit-rate@1 | 0.600 | **0.753** | +0.153 |
| hit-rate@3 | 0.787 | 0.820 | +0.033 |
| hit-rate@5 | 0.813 | 0.827 | +0.013 |
| hit-rate@10 | 0.827 | 0.847 | +0.020 |
| nDCG@10 | 0.724 | 0.803 | +0.079 |
| **MRR** | 0.693 | **0.790** | +0.097 |

**Chunk-level** (exact source chunk — strict):

| metric | baseline | +rerank | Δ |
|--------|---------:|--------:|----:|
| hit-rate@1 | 0.240 | **0.327** | +0.087 |
| hit-rate@5 | 0.573 | 0.627 | +0.053 |
| hit-rate@10 | 0.600 | 0.647 | +0.047 |
| nDCG@10 | 0.428 | 0.502 | +0.074 |
| **MRR** | 0.375 | **0.454** | +0.079 |

**Takeaways**

- Reranking improves **every** metric at both granularities. The largest win is
  **hit-rate@1**: the right article is surfaced at the very top **60% → 75%** of
  the time (+26% relative), and MRR climbs +0.10.
- hit-rate@10 barely moves (+0.01–0.02) — as expected, since reranking only
  reorders the already-retrieved shortlist. The gain is concentrated where it
  matters for a top-k prompt: pushing the right context toward rank 1.
- The chunk-vs-article gap shows first-stage retrieval reliably finds the right
  *topic* (article hit@5 ≈ 0.81) but is noisier at pinpointing the exact source
  chunk — motivating the reranker, and a useful baseline for the upcoming
  fine-tuning work.

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
