"""Build the QLoRA instruction-tuning dataset (grounded RAG-reader examples).

For each sampled chunk we ask the teacher (``llama3.1:8b``) for a natural player
question plus a concise answer grounded *only* in that chunk. Each example is
then assembled to mirror the server's runtime prompt exactly:

    system:    VideoGameWizard instructions + "Context:\n{chunk}"
    user:      {question}
    assistant: {grounded answer}

So the model trains on the same shape it will see in production — it learns to
*use* retrieved context, not to memorise facts (RAG supplies those).

Chunks are reservoir-sampled with a fixed seed, **excluding** every chunk used
in the retrieval eval set, so train and eval never overlap. Output is written in
``messages`` format (one JSON object per line), split into train/val.

Run from ``scraping/`` (needs Ollama serving ``llama3.1:8b``):

    py -m finetune.prepare_data --n 1500 --seed 42
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys
from pathlib import Path

import httpx

from finetune import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prepare_data")

_GEN_PROMPT = """You are creating training data for a video-game expert assistant.

Read the passage below and produce:
1. A natural question a player might ask, answerable from this passage. Name the \
game/subject explicitly; never write "this game", "the article", or "the passage".
2. A concise, accurate answer (one or two sentences) grounded ONLY in the passage.

Respond with ONLY a JSON object: {{"question": "...", "answer": "..."}}

Passage (from the Wikipedia article "{title}"):
\"\"\"
{content}
\"\"\""""


def load_excluded_ids(path: Path) -> set[str]:
    """Chunk ids used by the retrieval eval set — held out of training."""
    if not path.exists():
        log.warning("Eval set not found at %s; no chunks will be excluded.", path)
        return set()
    ids: set[str] = set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                ids.add(json.loads(line)["gold_chunk_id"])
    log.info("Excluding %d eval chunk ids from training", len(ids))
    return ids


def sample_chunks(path: Path, n: int, seed: int, min_chars: int, exclude: set[str]) -> list[dict]:
    """Reservoir-sample ``n`` eligible chunks in one pass (Algorithm R)."""
    rng = random.Random(seed)
    reservoir: list[dict] = []
    seen = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chunk = json.loads(line)
            if chunk["id"] in exclude or len(chunk.get("content", "")) < min_chars:
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


def generate_example(client: httpx.Client, model: str, url: str, chunk: dict) -> dict | None:
    """Build one ``messages`` training example from ``chunk``; None on failure."""
    prompt = _GEN_PROMPT.format(title=chunk["title"], content=chunk["content"])
    try:
        resp = client.post(
            f"{url}/api/chat",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.3},
            },
        )
        resp.raise_for_status()
        qa = json.loads(resp.json()["message"]["content"])
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("Generation failed for chunk %s: %s", chunk["id"], exc)
        return None

    question = str(qa.get("question", "")).strip()
    answer = str(qa.get("answer", "")).strip()
    if not question or not answer:
        return None

    system = config.SYSTEM_PROMPT_TEMPLATE.format(context=chunk["content"])
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer},
        ],
        # Provenance (handy for auditing; ignored by the trainer).
        "source_chunk_id": chunk["id"],
        "source_title": chunk["title"],
    }


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the QLoRA instruction dataset.")
    parser.add_argument("--n", type=int, default=config.DEFAULT_N_EXAMPLES)
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    parser.add_argument("--val-fraction", type=float, default=config.DEFAULT_VAL_FRACTION)
    parser.add_argument("--min-chars", type=int, default=config.DEFAULT_MIN_CHARS)
    parser.add_argument("--model", default=config.OLLAMA_MODEL)
    parser.add_argument("--ollama-url", default=config.OLLAMA_URL)
    args = parser.parse_args()

    if not config.CHUNKS_PATH.exists():
        log.error("Chunks file not found: %s", config.CHUNKS_PATH)
        return 1

    excluded = load_excluded_ids(config.EVAL_SET_PATH)
    chunks = sample_chunks(config.CHUNKS_PATH, args.n, args.seed, args.min_chars, excluded)

    rows: list[dict] = []
    with httpx.Client(timeout=120.0) as client:
        for i, chunk in enumerate(chunks, 1):
            example = generate_example(client, args.model, args.ollama_url, chunk)
            if example is not None:
                rows.append(example)
            if i % 50 == 0 or i == len(chunks):
                log.info("  %d/%d processed (%d kept)", i, len(chunks), len(rows))

    if not rows:
        log.error("No examples generated — is Ollama serving '%s'?", args.model)
        return 1

    # Deterministic shuffle + split.
    random.Random(args.seed).shuffle(rows)
    n_val = max(1, round(len(rows) * args.val_fraction))
    val, train = rows[:n_val], rows[n_val:]

    write_jsonl(config.TRAIN_PATH, train)
    write_jsonl(config.VAL_PATH, val)
    log.info("Wrote %d train -> %s", len(train), config.TRAIN_PATH)
    log.info("Wrote %d val   -> %s", len(val), config.VAL_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
