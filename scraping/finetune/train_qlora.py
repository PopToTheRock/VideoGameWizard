"""QLoRA fine-tuning of Llama 3.1 8B into a grounded RAG reader (Unsloth + TRL).

Runs in WSL2 on the RTX 5070 Ti (Blackwell, sm_120). Loads the 4-bit base
Instruct model, attaches LoRA adapters, and trains on the messages-format
dataset with assistant-only loss (the prompt — including the retrieved context —
is masked, so the model is graded only on the answer it should produce).

Outputs:
  * LoRA adapter + tokenizer  -> outputs/adapter/        (gitignored, large)
  * loss curve                -> loss_curve.png          (committed, model card)
  * training log + summary    -> training_summary.json   (committed, model card)

`import unsloth` MUST come first so it can patch transformers/peft/trl.

Run inside the WSL venv, from scraping/ :
    python -m finetune.train_qlora --epochs 1
"""

# ruff: noqa: I001  (import order is load-bearing: unsloth must precede trl/transformers)
from __future__ import annotations

import unsloth  # noqa: F401  (must be imported before trl/transformers/peft)

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: render straight to a file
import matplotlib.pyplot as plt
from datasets import load_dataset
from trl import SFTConfig, SFTTrainer
from unsloth import FastLanguageModel
from unsloth.chat_templates import get_chat_template, train_on_responses_only

from finetune import config

# Base model: the Instruct variant that Ollama serves as llama3.1:8b, so the
# fine-tune drops straight into the existing pipeline after GGUF export.
BASE_MODEL = "unsloth/Meta-Llama-3.1-8B-Instruct-bnb-4bit"
MAX_SEQ_LENGTH = 2048

# Llama-3.1 chat-template markers that delimit the assistant turn — used to mask
# everything but the response when computing the loss.
_INSTRUCTION_PART = "<|start_header_id|>user<|end_header_id|>\n\n"
_RESPONSE_PART = "<|start_header_id|>assistant<|end_header_id|>\n\n"

OUTPUT_DIR = config.FINETUNE_DIR / "outputs"
ADAPTER_DIR = OUTPUT_DIR / "adapter"
LOSS_CURVE_PATH = config.FINETUNE_DIR / "loss_curve.png"
SUMMARY_PATH = config.FINETUNE_DIR / "training_summary.json"


def build_dataset(tokenizer):
    """Load train/val JSONL and render each chat into a single `text` field."""
    data_files = {"train": str(config.TRAIN_PATH), "validation": str(config.VAL_PATH)}
    dataset = load_dataset("json", data_files=data_files)

    def to_text(batch: dict) -> dict:
        texts = [
            tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=False)
            for msgs in batch["messages"]
        ]
        return {"text": texts}

    return dataset.map(to_text, batched=True, remove_columns=dataset["train"].column_names)


def plot_loss_curve(log_history: list[dict], path: Path) -> None:
    train = [(e["step"], e["loss"]) for e in log_history if "loss" in e]
    evals = [(e["step"], e["eval_loss"]) for e in log_history if "eval_loss" in e]
    if not train:
        return
    plt.figure(figsize=(8, 5))
    plt.plot(*zip(*train, strict=True), label="train loss", linewidth=1.5)
    if evals:
        plt.plot(*zip(*evals, strict=True), label="val loss", marker="o", linewidth=1.5)
    plt.xlabel("step")
    plt.ylabel("loss")
    plt.title("QLoRA fine-tuning — Llama 3.1 8B grounded RAG reader")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="QLoRA fine-tune the RAG reader.")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--grad-accum", type=int, default=4)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--lora-r", type=int, default=16)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not config.TRAIN_PATH.exists():
        raise FileNotFoundError(f"Training data not found: {config.TRAIN_PATH}")

    # --- Model + LoRA -----------------------------------------------------
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,  # auto: bf16 on Blackwell
        load_in_4bit=True,
    )
    tokenizer = get_chat_template(tokenizer, chat_template="llama-3.1")
    model = FastLanguageModel.get_peft_model(
        model,
        r=args.lora_r,
        lora_alpha=args.lora_r,
        lora_dropout=0.0,
        bias="none",
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        use_gradient_checkpointing="unsloth",
        random_state=args.seed,
    )

    # --- Data -------------------------------------------------------------
    dataset = build_dataset(tokenizer)

    # --- Trainer ----------------------------------------------------------
    sft_config = SFTConfig(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        dataset_text_field="text",
        max_length=MAX_SEQ_LENGTH,
        packing=False,
        per_device_train_batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        warmup_ratio=0.03,
        num_train_epochs=args.epochs,
        learning_rate=args.lr,
        bf16=True,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        logging_steps=5,
        eval_strategy="steps",
        eval_steps=40,
        seed=args.seed,
        report_to="none",
    )
    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        args=sft_config,
    )
    # Mask the prompt (system context + question); train only on the answer.
    trainer = train_on_responses_only(
        trainer,
        instruction_part=_INSTRUCTION_PART,
        response_part=_RESPONSE_PART,
    )

    train_result = trainer.train()

    # --- Persist outputs --------------------------------------------------
    ADAPTER_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ADAPTER_DIR))
    tokenizer.save_pretrained(str(ADAPTER_DIR))

    plot_loss_curve(trainer.state.log_history, LOSS_CURVE_PATH)

    final_eval = trainer.evaluate()
    summary = {
        "base_model": BASE_MODEL,
        "n_train": len(dataset["train"]),
        "n_val": len(dataset["validation"]),
        "epochs": args.epochs,
        "effective_batch_size": args.batch_size * args.grad_accum,
        "learning_rate": args.lr,
        "lora_r": args.lora_r,
        "max_seq_length": MAX_SEQ_LENGTH,
        "train_runtime_sec": round(train_result.metrics.get("train_runtime", 0.0), 1),
        "final_train_loss": round(train_result.metrics.get("train_loss", 0.0), 4),
        "final_val_loss": round(final_eval.get("eval_loss", 0.0), 4),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== training summary ===")
    print(json.dumps(summary, indent=2))
    print(f"\nadapter -> {ADAPTER_DIR}\nloss curve -> {LOSS_CURVE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
