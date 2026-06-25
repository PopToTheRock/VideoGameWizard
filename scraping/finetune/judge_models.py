"""Quantitative head-to-head: base vs. fine-tuned model, scored by an LLM judge.

Where ``compare_models.py`` produces a *qualitative* side-by-side table, this
script produces a *number*: a held-out win-rate. For each validation question it
sends the identical grounded prompt to both models, then asks a judge model which
answer is better on **grounding (faithfulness to the retrieved context + the
reference) and conciseness**, and aggregates the verdicts into a win-rate.

This closes the loop the project is built to demonstrate — *measure a model,
improve it, re-measure* — for the headline fine-tune (the retrieval side is
already measured by ``rag/eval``). See ``docs/AUDIT.md`` finding H5.

Methodology / bias controls:
  * **Deterministic** — generation and judging both run at temperature 0 with a
    fixed seed, so the win-rate is reproducible.
  * **Position bias** — the two answers are presented to the judge as "A"/"B"
    with the assignment alternating by item index, and the judge is told the
    order is randomised; results are de-anonymised afterward.
  * **Self-preference bias** — the judge SHOULD be a different (ideally stronger)
    model than either contestant. ``--judge`` defaults to the base model for a
    zero-setup run, but the script warns when the judge equals a contestant;
    pass e.g. ``--judge llama3.1:70b`` (or another local model) for a fairer read.

Run from ``scraping/`` after the fine-tuned model is registered in Ollama:

    py -m finetune.judge_models --finetuned vgw-rag:8b --n 50 --judge llama3.1:70b
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import httpx

from finetune import config

OUT_MD = config.FINETUNE_DIR / "judge_results.md"
OUT_JSON = config.FINETUNE_DIR / "judge_results.json"

_JUDGE_SYSTEM = (
    "You are a strict, impartial evaluation judge for a video-game question-"
    "answering assistant. You are given the CONTEXT an answer was supposed to use, "
    "a REFERENCE answer, and two candidate answers labelled A and B. Decide which "
    "candidate is better, judging on two criteria in priority order:\n"
    "1. Grounding/faithfulness: supported by the CONTEXT and consistent with the "
    "REFERENCE; no invented or contradicted facts.\n"
    "2. Conciseness: direct and free of padding while still complete.\n"
    "The A/B order is randomised and must NOT influence your decision. If the two "
    'are genuinely equivalent, answer "tie".\n'
    'Respond with ONLY a compact JSON object: {"winner": "A" | "B" | "tie", '
    '"reason": "<one short sentence>"}'
)


def ask(
    client: httpx.Client,
    url: str,
    model: str,
    messages: list[dict],
    seed: int,
) -> str:
    """One deterministic, non-streaming Ollama chat turn; returns assistant text."""
    resp = client.post(
        f"{url}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.0, "seed": seed},
        },
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def _parse_verdict(text: str) -> dict:
    """Extract the judge's JSON object, tolerant of surrounding prose/code fences."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return {"winner": "tie", "reason": f"unparseable judge output: {text[:80]!r}"}
    try:
        obj = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"winner": "tie", "reason": f"invalid judge JSON: {text[:80]!r}"}
    winner = str(obj.get("winner", "tie")).strip().upper()
    obj["winner"] = winner if winner in {"A", "B"} else "tie"
    obj.setdefault("reason", "")
    return obj


def main() -> int:
    parser = argparse.ArgumentParser(description="LLM-judge win-rate: base vs fine-tuned.")
    parser.add_argument("--base", default=config.OLLAMA_MODEL)
    parser.add_argument("--finetuned", default="vgw-rag:8b")
    parser.add_argument(
        "--judge", default=config.OLLAMA_MODEL, help="Judge model (ideally distinct)."
    )
    parser.add_argument("--ollama-url", default=config.OLLAMA_URL)
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=config.DEFAULT_SEED)
    parser.add_argument("--val", type=Path, default=config.VAL_PATH)
    args = parser.parse_args()

    if args.judge in {args.base, args.finetuned}:
        print(
            f"WARNING: judge ({args.judge}) is also a contestant — self-preference bias is "
            "likely. Pass a distinct --judge (e.g. a larger local model) for a fairer read.",
            file=sys.stderr,
        )

    rows = [json.loads(line) for line in open(args.val, encoding="utf-8") if line.strip()][: args.n]

    results: list[dict] = []
    tally = {"finetuned": 0, "base": 0, "tie": 0}

    with httpx.Client(timeout=180.0) as client:
        for i, row in enumerate(rows):
            system_context = row["messages"][0]["content"]
            question = row["messages"][1]["content"]
            reference = row["messages"][2]["content"]
            prompt = row["messages"][:2]  # system + user (drop the gold answer)

            base_ans = ask(client, args.ollama_url, args.base, prompt, args.seed)
            ft_ans = ask(client, args.ollama_url, args.finetuned, prompt, args.seed)

            # Alternate A/B by index to neutralise position bias.
            ft_is_a = i % 2 == 0
            answer_a, answer_b = (ft_ans, base_ans) if ft_is_a else (base_ans, ft_ans)

            judge_user = (
                f"CONTEXT:\n{system_context}\n\n"
                f"QUESTION:\n{question}\n\n"
                f"REFERENCE ANSWER:\n{reference}\n\n"
                f"ANSWER A:\n{answer_a}\n\n"
                f"ANSWER B:\n{answer_b}"
            )
            verdict = _parse_verdict(
                ask(
                    client,
                    args.ollama_url,
                    args.judge,
                    [
                        {"role": "system", "content": _JUDGE_SYSTEM},
                        {"role": "user", "content": judge_user},
                    ],
                    args.seed,
                )
            )

            winner_label = verdict["winner"]
            if winner_label == "tie":
                outcome = "tie"
            else:
                a_is_ft = ft_is_a
                outcome = "finetuned" if (winner_label == "A") == a_is_ft else "base"
            tally[outcome] += 1

            results.append(
                {
                    "question": question,
                    "outcome": outcome,
                    "reason": verdict.get("reason", ""),
                    "ft_was_a": ft_is_a,
                }
            )
            print(f"  judged {i + 1}/{len(rows)} -> {outcome}")

    n = len(results)
    decided = tally["finetuned"] + tally["base"]
    ft_win_rate_overall = tally["finetuned"] / n if n else 0.0
    ft_win_rate_decided = tally["finetuned"] / decided if decided else 0.0

    summary = {
        "n": n,
        "base_model": args.base,
        "finetuned_model": args.finetuned,
        "judge_model": args.judge,
        "seed": args.seed,
        "tally": tally,
        "ft_win_rate_overall": round(ft_win_rate_overall, 3),
        "ft_win_rate_excluding_ties": round(ft_win_rate_decided, 3),
    }

    md = [
        f"# Fine-tune win-rate — {n} held-out questions\n",
        f"- **Base:** `{args.base}`  ·  **Fine-tuned:** `{args.finetuned}`",
        f"- **Judge:** `{args.judge}`  ·  Deterministic (temp 0, seed {args.seed})",
        "- A/B order alternated per item to neutralise position bias.\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Fine-tuned wins | {tally['finetuned']} |",
        f"| Base wins | {tally['base']} |",
        f"| Ties | {tally['tie']} |",
        f"| **FT win-rate (overall)** | **{ft_win_rate_overall:.1%}** |",
        f"| FT win-rate (excl. ties) | {ft_win_rate_decided:.1%} |",
    ]
    if args.judge in {args.base, args.finetuned}:
        md.append("\n> ⚠️ Judge equals a contestant — treat as a weak/biased estimate.")

    OUT_JSON.write_text(
        json.dumps({"summary": summary, "results": results}, indent=2), encoding="utf-8"
    )
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nFT win-rate: {ft_win_rate_overall:.1%} overall ({tally})")
    print(f"Wrote {OUT_MD} and {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
