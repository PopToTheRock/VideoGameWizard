"""
RAG server — middleware between the Android app and Ollama.

For each incoming chat message:
  1. Embeds the query using sentence-transformers
  2. Retrieves the top-k most relevant chunks from ChromaDB
  3. Builds a system prompt with the retrieved context
  4. Calls Ollama /api/chat with the conversation history
  5. Returns the AI response to the Android app

Run from scraping/rag/:
    uvicorn server:app --host 0.0.0.0 --port 8000

Requirements:
    pip install fastapi uvicorn requests
    (sentence-transformers and chromadb already installed)

Endpoints:
    GET  /health  — liveness check
    POST /chat    — main chat endpoint
"""

import logging
from pathlib import Path

import chromadb
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1:8b"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME = "game_knowledge"
TOP_K = 5  # number of context chunks to retrieve per query

# ---------------------------------------------------------------------------
# Startup — load models and DB once at process start
# ---------------------------------------------------------------------------

project_root = Path(__file__).resolve().parent.parent.parent
chroma_path = project_root / "scraping" / "data" / "chromadb"

log.info(f"Loading ChromaDB from {chroma_path}...")
_chroma_client = chromadb.PersistentClient(path=str(chroma_path))
_collection = _chroma_client.get_collection(COLLECTION_NAME)
log.info(f"Collection '{COLLECTION_NAME}': {_collection.count():,} chunks")

log.info(f"Loading embedding model: {EMBED_MODEL}...")
_embed_model = SentenceTransformer(EMBED_MODEL)
log.info("Ready.")

app = FastAPI(title="VideoGameWizard RAG Server")

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class HistoryMessage(BaseModel):
    role: str     # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: list[HistoryMessage] = []

class ChatResponse(BaseModel):
    response: str
    sources: list[str] = []

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "chunks": _collection.count()}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    # 1. Embed the query
    query_vec = _embed_model.encode(
        [request.message], normalize_embeddings=True
    )[0].tolist()

    # 2. Retrieve top-k relevant chunks
    results = _collection.query(
        query_embeddings=[query_vec],
        n_results=TOP_K,
        include=["documents", "metadatas"],
    )
    context_chunks: list[str] = results["documents"][0]
    sources: list[str] = list(
        {m["title"] for m in results["metadatas"][0]}
    )

    # 3. Build system prompt with retrieved context
    context_text = "\n\n---\n\n".join(context_chunks)
    system_prompt = (
        "You are VideoGameWizard, an expert AI assistant for video games. "
        "Use the context below to answer the user's question accurately and concisely. "
        "If the context does not contain relevant information, use your general knowledge.\n\n"
        f"Context:\n{context_text}"
    )

    # 4. Build full message list for Ollama
    messages = [{"role": "system", "content": system_prompt}]
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": request.message})

    # 5. Call Ollama
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error(f"Ollama request failed: {e}")
        raise HTTPException(status_code=502, detail=f"Ollama unreachable: {e}")

    ai_text: str = resp.json()["message"]["content"]
    log.info(f"Query: '{request.message[:60]}...' | Sources: {sources}")

    return ChatResponse(response=ai_text, sources=sources)
