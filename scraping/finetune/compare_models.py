"""Side-by-side comparison: base vs. fine-tuned model on held-out questions.

Sends the *same* grounded prompt (system context + question) from the validation
split to both the base model and the fine-tuned model via Ollama, and writes a
Markdown table of their answers next to the reference answer. This is the
qualitative half of the model card — it shows what the fine-tune changed.

Run from ``scraping/`` after the fine-tuned model is registered in Ollama:

    py -m finetune.compare_models --finetuned vgw-rag:8b --n 8
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from finetune import config

OUT_PATH = config.FINETUNE_DIR / "comparison.md"


def ask(client: httpx.Client, url: str, model: str, messages: list[dict]) -> str:
    """One non-streaming Ollama chat turn; returns the assistant text."""
    resp = client.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2},
        },
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare base vs fine-tuned answers.")
    parser.add_argument("--base", default=config.OLLAMA_MODEL)
    parser.add_argument("--finetuned", default="vgw-rag:8b")
    parser.add_argument("--ollama-url", default=config.OLLAMA_URL)
    parser.add_argument("--n", type=int, default=8)
    parser.add_argument("--val", type=Path, default=config.VAL_PATH)
    args = parser.parse_args()

    rows = [json.loads(line) for line in open(args.val, encoding="utf-8") if line.strip()][: args.n]

    blocks: list[str] = [
        f"# Base vs. fine-tuned — {len(rows)} held-out questions\n",
        f"- **Base:** `{args.base}`  ·  **Fine-tuned:** `{args.finetuned}`",
        "- Identical grounded prompt (system context + question) to both.\n",
    ]
    with httpx.Client(timeout=120.0) as client:
        for i, row in enumerate(rows, 1):
            prompt = row["messages"][:2]  # system + user (drop the gold answer)
            question = row["messages"][1]["content"]
            reference = row["messages"][2]["content"]
            base_ans = ask(client, args.ollama_url, args.base, prompt)
            ft_ans = ask(client, args.ollama_url, args.finetuned, prompt)
            blocks.append(
                f"### {i}. {question}\n"
                f"**Reference:** {reference}\n\n"
                f"**Base ({args.base}):** {base_ans}\n\n"
                f"**Fine-tuned ({args.finetuned}):** {ft_ans}\n"
            )
            print(f"  compared {i}/{len(rows)}")

    OUT_PATH.write_text("\n".join(blocks), encoding="utf-8")
    print(f"\nWrote comparison -> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
