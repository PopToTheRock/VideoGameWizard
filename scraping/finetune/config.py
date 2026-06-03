"""Shared configuration for the QLoRA fine-tuning pipeline.

Paths are derived from this file's location so scripts work from any CWD. The
system-prompt template is kept byte-for-byte in sync with ``server.py`` — the
fine-tune only helps the deployed pipeline if it trains on the exact prompt the
server uses at inference time.
"""

from __future__ import annotations

from pathlib import Path

# .../scraping  (finetune/ -> scraping/)
_SCRAPING = Path(__file__).resolve().parents[1]

# --- Inputs ---
CHUNKS_PATH = _SCRAPING / "data" / "chunks.jsonl"
# Retrieval eval gold set — its source chunks are held OUT of training so the two
# never overlap.
EVAL_SET_PATH = _SCRAPING / "rag" / "eval" / "data" / "eval_set.jsonl"

# --- Outputs ---
FINETUNE_DIR = Path(__file__).resolve().parent
DATA_DIR = FINETUNE_DIR / "data"
TRAIN_PATH = DATA_DIR / "train.jsonl"
VAL_PATH = DATA_DIR / "val.jsonl"

# --- Generation (teacher) ---
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"

# --- Dataset defaults (overridable via CLI) ---
DEFAULT_SEED = 42
DEFAULT_N_EXAMPLES = 1500
DEFAULT_VAL_FRACTION = 0.1
DEFAULT_MIN_CHARS = 400

# System prompt — MUST match server.py's grounded-context branch verbatim.
SYSTEM_PROMPT_TEMPLATE = (
    "You are VideoGameWizard, an expert AI assistant for video games. "
    "Use the context below to answer the user's question accurately and "
    "concisely. If the context does not contain relevant information, use "
    "your general knowledge.\n\nContext:\n{context}"
)
