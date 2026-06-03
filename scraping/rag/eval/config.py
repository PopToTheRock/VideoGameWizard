"""Shared configuration for the RAG evaluation harness.

Paths are derived from this file's location so the harness works regardless of
the current working directory. Model/collection names intentionally mirror the
server's defaults (``server.Settings``) — the eval must retrieve through the
exact same embedding model and collection it serves from, or the numbers lie.
"""

from __future__ import annotations

from pathlib import Path

# .../scraping  (eval/ -> rag/ -> scraping/)
_SCRAPING = Path(__file__).resolve().parents[2]

# --- Corpus + vector store (inputs) ---
CHUNKS_PATH = _SCRAPING / "data" / "chunks.jsonl"
CHROMA_PATH = _SCRAPING / "data" / "chromadb"

# --- Harness artifacts (outputs) ---
EVAL_DIR = Path(__file__).resolve().parent
DATA_DIR = EVAL_DIR / "data"  # generated gold set lives here
RESULTS_DIR = EVAL_DIR / "results"  # timestamped metric reports
EVAL_SET_PATH = DATA_DIR / "eval_set.jsonl"

# --- Models (mirror server.Settings) ---
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "game_knowledge"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"

# --- Defaults (overridable via CLI) ---
DEFAULT_SEED = 42
DEFAULT_N_QUESTIONS = 150
# Only sample chunks with enough text to anchor a specific question.
DEFAULT_MIN_CHARS = 400
# How deep to retrieve before reranking. The reranker only reorders these N, so
# this caps the best achievable hit-rate; 20 >> top_k=5 leaves room to improve.
DEFAULT_N_CANDIDATES = 20
# Cutoffs at which hit-rate / nDCG are reported.
DEFAULT_KS = (1, 3, 5, 10)
