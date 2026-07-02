"""
RAG server — middleware between the Android app and Ollama.

For each incoming chat message it:
  1. Embeds the query with sentence-transformers
  2. Retrieves the top-k most relevant chunks from ChromaDB
  3. Builds a system prompt grounded in the retrieved context
  4. Calls Ollama /api/chat (async) with the conversation history
  5. Returns the answer plus the source article titles

Run from scraping/rag/ (loopback only — safe default for the emulator workflow):
    uvicorn server:app --host 127.0.0.1 --port 8000

To reach the server from a physical device on your LAN, bind 0.0.0.0 *and* set a
shared secret so the inference/feedback routes aren't open to the whole subnet:
    VGW_API_KEY=$(openssl rand -hex 16) uvicorn server:app --host 0.0.0.0 --port 8000
(clients send it as the ``X-API-Key`` header; note the Android app does not send
one yet, so a keyed server currently serves scripts/curl only).

Configuration is environment-driven (see ``Settings``); every value has a
sensible local-dev default and can be overridden with a ``VGW_`` env var, e.g.
    VGW_OLLAMA_MODEL=llama3.1:70b uvicorn server:app ...

Endpoints:
    GET  /health       — liveness + chunk count
    GET  /stats        — model / collection / config info
    POST /chat         — buffered chat (full answer in one response)
    POST /chat/stream  — streaming chat (NDJSON: sources, token…, done/error)
    POST /feedback     — record a thumbs up/down on an answer (JSONL preference log)
"""

from __future__ import annotations

import json
import logging
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
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
# Cap conversation history so a long session (or a crafted request) can't blow the
# model's context window or ship an unbounded payload to Ollama.
MAX_HISTORY_MESSAGES = 50
# Feedback payload bounds: answers are model output (longer than user messages,
# but not unbounded — an uncapped field is a disk-fill vector on the append-only
# feedback log); sources are short article titles.
MAX_ANSWER_CHARS = 16384
MAX_FEEDBACK_SOURCES = 20
MAX_SOURCE_TITLE_CHARS = 512

_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_DEFAULT_CHROMA_PATH = _DEFAULT_DATA_DIR / "chromadb"
_DEFAULT_FEEDBACK_PATH = _DEFAULT_DATA_DIR / "feedback.jsonl"


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
    feedback_path: str = str(_DEFAULT_FEEDBACK_PATH)
    # Optional shared secret. When non-empty, protected routes (chat / stream /
    # feedback / stats) require a matching ``X-API-Key`` header. Empty (the
    # default) disables auth — fine for the local 127.0.0.1 emulator workflow.
    # Set ``VGW_API_KEY`` whenever the server is bound to a LAN interface (0.0.0.0).
    api_key: str = ""
    # Browser origins allowed by CORS. The Android client is a native HTTP
    # client and is unaffected by CORS — this only matters for browser callers
    # (e.g. the Swagger docs or a future web UI). Override for other hosts via
    # VGW_ALLOWED_ORIGINS (a JSON list, e.g. '["http://192.168.1.42:5173"]').
    allowed_origins: list[str] = [
        "http://localhost",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:8000",
    ]


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[HistoryMessage] = Field(default_factory=list, max_length=MAX_HISTORY_MESSAGES)

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


class FeedbackRequest(BaseModel):
    """A user's thumbs up/down on one answer — a preference signal for later DPO."""

    query: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_CHARS)
    rating: Literal["up", "down"]
    sources: list[Annotated[str, Field(max_length=MAX_SOURCE_TITLE_CHARS)]] = Field(
        default_factory=list, max_length=MAX_FEEDBACK_SOURCES
    )

    @field_validator("query", "answer")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value


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


def require_api_key(
    settings: Settings = Depends(get_settings),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    """Gate protected routes behind ``VGW_API_KEY`` when it is configured.

    No key configured → auth is off (local-dev default). When a key is set, the
    request must carry a matching ``X-API-Key`` header; the comparison is
    constant-time to avoid leaking the secret via timing.
    """
    expected = settings.api_key
    if not expected:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Shared RAG pipeline (used by both the buffered and streaming chat endpoints)
# ---------------------------------------------------------------------------


async def retrieve_context(
    query: str,
    settings: Settings,
    embedder: Any,
    collection: Any,
) -> tuple[list[str], list[str]]:
    """Embed the query, retrieve the top-k chunks, and return (documents, sources).

    Both the embedding and the ChromaDB query are blocking, so each is offloaded
    to a threadpool to keep the event loop free.
    """
    embedding = (await run_in_threadpool(embedder.encode, [query], normalize_embeddings=True))[0]
    query_vec = embedding.tolist() if hasattr(embedding, "tolist") else list(embedding)

    results = await run_in_threadpool(
        collection.query,
        query_embeddings=[query_vec],
        n_results=settings.top_k,
        include=["documents", "metadatas"],
    )
    documents: list[str] = (results.get("documents") or [[]])[0]
    metadatas: list[dict[str, Any]] = (results.get("metadatas") or [[]])[0]
    sources = sorted({m.get("title", "") for m in metadatas if m.get("title")})
    return documents, sources


def build_messages(
    query: str,
    documents: list[str],
    history: list[HistoryMessage],
) -> list[dict[str, str]]:
    """Assemble the Ollama message list, grounding the system prompt in context."""
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

    messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    messages += [{"role": m.role, "content": m.content} for m in history]
    messages.append({"role": "user", "content": query})
    return messages


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

router = APIRouter()


@router.get("/health")
def health(collection: Any = Depends(get_collection)) -> dict[str, Any]:
    return {"status": "ok", "chunks": collection.count()}


@router.get("/stats", dependencies=[Depends(require_api_key)])
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


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(require_api_key)])
async def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    embedder: Any = Depends(get_embedder),
    collection: Any = Depends(get_collection),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> ChatResponse:
    """Buffered chat: retrieve context, call Ollama once, return the full answer.

    Retained for non-streaming callers (eval scripts, curl, tests). Interactive
    clients should prefer ``/chat/stream`` for token-by-token delivery.
    """
    query = payload.message
    documents, sources = await retrieve_context(query, settings, embedder, collection)
    messages = build_messages(query, documents, payload.history)

    # Call Ollama asynchronously (timeout is configured on the client).
    try:
        resp = await http_client.post(
            f"{settings.ollama_url}/api/chat",
            json={"model": settings.ollama_model, "messages": messages, "stream": False},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        # Log the detail; the client gets a generic message (httpx exception
        # strings include the upstream URL — internal topology).
        log.error("Ollama request failed: %s", exc)
        raise HTTPException(status_code=502, detail="Ollama request failed") from exc

    try:
        ai_text = resp.json()["message"]["content"]
    except (KeyError, TypeError, ValueError) as exc:
        log.error("Unexpected Ollama response shape: %s", exc)
        raise HTTPException(status_code=502, detail="Unexpected response from Ollama") from exc

    log.info("Query: %r | sources: %s", query[:60], sources)
    return ChatResponse(response=ai_text, sources=sources)


def _ndjson(event: dict[str, Any]) -> str:
    """Serialise one stream event as a single newline-terminated JSON line."""
    return json.dumps(event, ensure_ascii=False) + "\n"


@router.post("/chat/stream", dependencies=[Depends(require_api_key)])
async def chat_stream(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    embedder: Any = Depends(get_embedder),
    collection: Any = Depends(get_collection),
    http_client: httpx.AsyncClient = Depends(get_http_client),
) -> StreamingResponse:
    """Streaming chat. Emits newline-delimited JSON (NDJSON) events:

        {"type": "sources",  "sources": [...]}   once, before generation
        {"type": "token",    "token": "..."}     per token as Ollama emits it
        {"type": "done"}                          terminal success
        {"type": "error",    "message": "..."}    terminal failure

    The response status is 200 as soon as headers flush, so any failure during
    generation is reported in-band as an ``error`` event rather than an HTTP
    error code (request *validation* still fails fast with 422 before streaming).
    """
    query = payload.message

    async def event_stream() -> AsyncIterator[str]:
        # Retrieval happens before the first token, so sources lead the stream.
        try:
            documents, sources = await retrieve_context(query, settings, embedder, collection)
        except Exception as exc:  # noqa: BLE001 — surfaced in-band, not as a 500
            log.error("Retrieval failed: %s", exc)
            yield _ndjson({"type": "error", "message": "Retrieval failed"})
            return

        yield _ndjson({"type": "sources", "sources": sources})
        messages = build_messages(query, documents, payload.history)

        completed = False
        try:
            async with http_client.stream(
                "POST",
                f"{settings.ollama_url}/api/chat",
                json={"model": settings.ollama_model, "messages": messages, "stream": True},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError as exc:
                        # A non-JSON / truncated upstream line (proxy hiccup, version
                        # skew) must be reported in-band, not crash the generator.
                        log.error("Malformed line from Ollama stream: %s", exc)
                        yield _ndjson(
                            {"type": "error", "message": "Malformed response from Ollama"}
                        )
                        return
                    if isinstance(chunk, dict) and chunk.get("error"):
                        # Ollama reports mid-generation failures (OOM, runner crash,
                        # model unloaded) as an {"error": ...} line on the open 200
                        # stream — without this branch it would fall through to "done".
                        log.error("Ollama in-stream error: %s", chunk["error"])
                        yield _ndjson({"type": "error", "message": "Ollama generation failed"})
                        return
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield _ndjson({"type": "token", "token": token})
                    if chunk.get("done"):
                        completed = True
                        break
        except httpx.HTTPError as exc:
            log.error("Ollama stream failed: %s", exc)
            yield _ndjson({"type": "error", "message": "Ollama request failed"})
            return
        except Exception as exc:  # noqa: BLE001 — e.g. a valid-JSON line of the wrong shape
            log.error("Unexpected error while streaming from Ollama: %s", exc)
            yield _ndjson({"type": "error", "message": "Malformed response from Ollama"})
            return

        if not completed:
            # The upstream stream ended without ever sending done=true: a truncated
            # answer must not masquerade as a successful one.
            log.error("Ollama stream ended without a done marker")
            yield _ndjson({"type": "error", "message": "Response ended unexpectedly"})
            return

        log.info("Streamed query: %r | sources: %s", query[:60], sources)
        yield _ndjson({"type": "done"})

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


def _append_jsonl(path: str, record: dict[str, Any]) -> None:
    """Append one record as a JSON line, creating the parent dir if needed."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


@router.post("/feedback", dependencies=[Depends(require_api_key)])
async def feedback(
    payload: FeedbackRequest,
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    """Record a thumbs up/down on an answer to a JSONL log.

    Each line is a self-contained ``(query, answer, rating)`` record (plus model
    and timestamp) — a preference dataset that can later seed DPO / RLHF or simple
    quality analysis. The blocking file append is offloaded to a threadpool.
    """
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "rating": payload.rating,
        "model": settings.ollama_model,
        "query": payload.query,
        "answer": payload.answer,
        "sources": payload.sources,
    }
    await run_in_threadpool(_append_jsonl, settings.feedback_path, record)
    log.info("Feedback %r recorded for query %r", payload.rating, payload.query[:60])
    return {"status": "recorded"}


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
