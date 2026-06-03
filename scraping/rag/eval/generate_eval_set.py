"""Generate a synthetic gold eval set for retrieval evaluation.

Strategy (the trick that makes retrieval measurable without hand labelling):

1. Sample chunks from ``chunks.jsonl`` with a fixed seed (reproducible).
2. For each chunk, ask the LLM to write one specific question answerable *only*
   from that chunk, plus a short answer.
3. The chunk we started from **is** the gold document — so every question comes
   with its correct ``gold_chunk_id`` for free.

Each output row: ``{question, answer, gold_chunk_id, gold_title, gold_chunk_index}``.

Run from ``scraping/rag/`` (needs Ollama serving ``llama3.1:8b``):

    py -m eval.generate_eval_set --n 150 --seed 42

The generated set is committed as the canonical benchmark; regenerate only when
the corpus changes.
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import httpx

from eval import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("generate_eval_set")

_PROMPT_TEMPLATE = """You are building a quiz to test a video-game knowledge retrieval system.

Read the passage below and write ONE specific, factual question that can be \
answered using ONLY this passage, together with a short answer.

Rules:
- Make the question specific enough that this passage is clearly the source: \
name the game/subject explicitly. Never write "this game", "the article", or \
"the passage".
- The question must be answerable from the passage alone.
- The answer must be concise (a few words, not a sentence).
- Respond with ONLY a JSON object: {{"question": "...", "answer": "..."}}

Passage (from the Wikipedia article "{title}"):
\"\"\"
{content}
\"\"\""""


def sample_chunks(path: Path, n: int, seed: int, min_chars: int) -> list[dict]:
    """Reservoir-sample ``n`` chunks (>= ``min_chars``) in a single pass.

    Algorithm R: O(n) memory, and reproducible for a fixed seed because the file
    is read in a stable order.
    """
    rng = random.Random(seed)
    reservoir: list[dict] = []
    seen = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            if len(chunk.get("content", "")) < min_chars:
                continue
            seen += 1
            if len(reservoir) < n:
                reservoir.append(chunk)
            else:
                j = rng.randint(0, seen - 1)
                if j < n:
                    reservoir[j] = chunk
    log.info("Sampled %d chunks (from %d eligible, >= %d chars)", len(reservoir), seen, min_chars)
    return reservoir


def generate_qa(client: httpx.Client, model: str, url: str, chunk: dict) -> dict | None:
    """Ask the LLM for one Q&A grounded in ``chunk``; return None on failure."""
    prompt = _PROMPT_TEMPLATE.format(title=chunk["title"], content=chunk["content"])
    try:
        resp = client.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
            },
        )
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        qa = json.loads(content)
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("Generation failed for chunk %s: %s", chunk["id"], exc)
        return None

    question = str(qa.get("question", "")).strip()
    answer = str(qa.get("answer", "")).strip()
    if not question or not answer:
        log.warning("Empty question/answer for chunk %s; skipping", chunk["id"])
        return None

    return {
        "question": question,
        "answer": answer,
        "gold_chunk_id": chunk["id"],
        "gold_title": chunk["title"],
        "gold_chunk_index": chunk["chunk_index"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a synthetic RAG eval set.")
    parser.add_argument("--n", type=int, default=config.DEFAULT_N_QUESTIONS)
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    parser.add_argument("--min-chars", type=int, default=config.DEFAULT_MIN_CHARS)
    parser.add_argument("--model", default=config.OLLAMA_MODEL)
    parser.add_argument("--ollama-url", default=config.OLLAMA_URL)
    parser.add_argument("--out", type=Path, default=config.EVAL_SET_PATH)
    args = parser.parse_args()

    if not config.CHUNKS_PATH.exists():
        log.error("Chunks file not found: %s", config.CHUNKS_PATH)
        return 1

    chunks = sample_chunks(config.CHUNKS_PATH, args.n, args.seed, args.min_chars)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    with httpx.Client(timeout=120.0) as client:
        for i, chunk in enumerate(chunks, 1):
            row = generate_qa(client, args.model, args.ollama_url, chunk)
            if row is not None:
                rows.append(row)
            if i % 10 == 0 or i == len(chunks):
                log.info("  %d/%d processed (%d kept)", i, len(chunks), len(rows))

    with open(args.out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    log.info("Wrote %d eval questions -> %s", len(rows), args.out)
    if not rows:
        log.error("No questions generated — is Ollama serving '%s'?", args.model)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
