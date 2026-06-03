"""Merge the trained LoRA adapter into a standalone 16-bit model.

QLoRA training leaves us with a small adapter on top of the 4-bit base. To serve
it through Ollama we merge the adapter back into the base weights and save a
plain 16-bit Hugging Face checkpoint (safetensors). From there, Ollama imports
the directory and quantizes it on the fly — no llama.cpp build required:

    ollama create vgw-rag:8b --quantize q4_K_M -f finetune/Modelfile

`import unsloth` MUST come first. Run inside the WSL venv, from scraping/ :

    python -m finetune.export_merged
"""

from __future__ import annotations

# ruff: noqa: I001  (import order is load-bearing: unsloth must precede transformers)
import unsloth  # noqa: F401

from unsloth import FastLanguageModel

from finetune import config
from finetune.train_qlora import ADAPTER_DIR, MAX_SEQ_LENGTH

MERGED_DIR = config.FINETUNE_DIR / "outputs" / "merged"


def main() -> int:
    if not ADAPTER_DIR.exists():
        raise FileNotFoundError(f"Adapter not found: {ADAPTER_DIR}. Train first.")

    # Loading the adapter dir pulls in its base model and applies the LoRA.
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(ADAPTER_DIR),
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )

    MERGED_DIR.mkdir(parents=True, exist_ok=True)
    # merged_16bit: dequantize base + fold in the adapter -> portable fp16 weights.
    model.save_pretrained_merged(str(MERGED_DIR), tokenizer, save_method="merged_16bit")

    print(f"\nMerged 16-bit model -> {MERGED_DIR}")
    print("Next (from a Windows shell with Ollama):")
    print("  ollama create vgw-rag:8b --quantize q4_K_M -f finetune/Modelfile")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
