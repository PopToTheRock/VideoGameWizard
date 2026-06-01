"""
RAG server — middleware between the Android app and Ollama.

For each incoming chat message it:
  1. Embeds the query with sentence-transformers
  2. Retrieves the top-k most relevant chunks from ChromaDB
  3. Builds a system prompt grounded in the retrieved context
  4. Calls Ollama /api/chat (async) with the conversation history
  5. Returns the answer plus the source article titles

Run from scraping/rag/:
    uvicorn server:app --host 0.0.0.0 --port 8000

Configuration is environment-driven (see ``Settings``); every value has a
sensible local-dev default and can be overridden with a ``VGW_`` env var, e.g.
    VGW_OLLAMA_MODEL=llama3.1:70b uvicorn server:app ...

Endpoints:
    GET  /health  — liveness + chunk count
    GET  /stats   — model / collection / config info
    POST /chat    — main chat endpoint
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# Keep in sync with the Android client's MAX_INPUT_LENGTH.
MAX_MESSAGE_CHARS = 4096

_DEFAULT_CHROMA_PATH = Path(__file__).resolve().parent.parent / "data" / "chromadb"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class Settings(BaseSettings):
    """Server configuration. Override any field via a ``VGW_``-prefixed env var."""

    model_config = SettingsConfigDict(env_prefix="VGW_")

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    embed_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    collection_name: str = "game_knowledge"
    chroma_path: str = str(_DEFAULT_CHROMA_PATH)
    top_k: int = 5
    request_timeout_seconds: float = 120.0
    # A single "*" allows all origins — fine for local development.
    allowed_origins: list[str] = ["*"]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[HistoryMessage] = Field(default_factory=list)

    @field_validator("message")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("message must not be blank")
        return trimmed


class ChatResponse(BaseModel):
    response: str
    sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Dependencies (resources live on app.state; tests override these)
# ---------------------------------------------------------------------------


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_collection(request: Request) -> Any:
    return request.app.state.collection


def get_embedder(request: Request) -> Any:
    return request.app.state.embedder


def get_http_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/health")
def health(collection: Any = Depends(get_collection)) -> dict[str, Any]:
    return {"status": "ok", "chunks": collection.count()}


@router.get("/stats")
def stats(
    settings: Settings = Depends(get_settings),
    collection: Any = Depends(get_collection),
) -> dict[str, Any]:
    return {
        "model": settings.ollama_model,
        "embed_model": settings.embed_model,
        "collection": settings.collection_name,
        "chunks": collection.count(),
        "top_k": settings.top_k,
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    embedder: Any = Depends(get_embedder),
    collection: Any = Depends(get_collection),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ChatResponse:
    query = payload.message

    # 1. Embed the query (tolist() for numpy arrays; list() for plain sequences).
    embedding = embedder.encode([query], normalize_embeddings=True)[0]
    query_vec = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

    # 2. Retrieve the top-k relevant chunks.
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=settings.top_k,
        include=["documents", "metadatas"],
    )
    documents: list[str] = (results.get("documents") or [[]])[0]
    metadatas: list[dict[str, Any]] = (results.get("metadatas") or [[]])[0]
    sources = sorted({m.get("title", "") for m in metadatas if m.get("title")})

    # 3. Build the system prompt, gracefully handling zero retrieval.
    if documents:
        context_text = "\n\n---\n\n".join(documents)
        system_prompt = (
            "You are VideoGameWizard, an expert AI assistant for video games. "
            "Use the context below to answer the user's question accurately and "
            "concisely. If the context does not contain relevant information, use "
            f"your general knowledge.\n\nContext:\n{context_text}"
        )
    else:
        system_prompt = (
            "You are VideoGameWizard, an expert AI assistant for video games. "
            "Answer the user's question accurately and concisely using your "
            "general knowledge."
        )

    # 4. Assemble the message list for Ollama.
    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in payload.history]
    messages.append({"role": "user", "content": query})

    # 5. Call Ollama asynchronously (timeout is configured on the client).
    try:
        resp = await http_client.post(
            f"{settings.ollama_url}/api/chat",
            json={"model": settings.ollama_model, "messages": messages, "stream": False},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("Ollama request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Ollama request failed: {exc}") from exc

    try:
        ai_text = resp.json()["message"]["content"]
    except (KeyError, TypeError, ValueError) as exc:
        log.error("Unexpected Ollama response shape: %s", exc)
        raise HTTPException(status_code=502, detail="Unexpected response from Ollama") from exc

    log.info("Query: %r | sources: %s", query[:60], sources)
    return ChatResponse(response=ai_text, sources=sources)


# ---------------------------------------------------------------------------
# App factory + lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the embedding model, ChromaDB collection, and HTTP client once."""
    settings: Settings = app.state.settings

    # Heavy imports are deferred to startup so the module can be imported by the
    # test suite (and linters/CI) without chromadb or torch installed.
    import chromadb
    from sentence_transformers import SentenceTransformer

    log.info("Loading ChromaDB from %s ...", settings.chroma_path)
    chroma_client = chromadb.PersistentClient(path=settings.chroma_path)
    collection = chroma_client.get_collection(settings.collection_name)
    log.info("Collection '%s': %s chunks", settings.collection_name, f"{collection.count():,}")

    log.info("Loading embedding model: %s ...", settings.embed_model)
    embedder = SentenceTransformer(settings.embed_model)

    http_client = httpx.AsyncClient(timeout=settings.request_timeout_seconds)

    app.state.chroma_client = chroma_client
    app.state.collection = collection
    app.state.embedder = embedder
    app.state.http_client = http_client
    log.info("RAG server ready.")
    try:
        yield
    finally:
        await http_client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(title="VideoGameWizard RAG Server", lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
