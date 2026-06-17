import json

import httpx
import server
from fastapi.testclient import TestClient


class FakeEmbedder:
    """Returns one fixed vector per input text (plain list, no numpy needed)."""

    def encode(self, texts, normalize_embeddings=False):
        return [[0.0, 0.1, 0.2] for _ in texts]


class FakeCollection:
    def __init__(self, documents, metadatas, count=42):
        self._documents = documents
        self._metadatas = metadatas
        self._count = count

    def query(self, query_embeddings, n_results, include):
        return {"documents": [self._documents], "metadatas": [self._metadatas]}

    def count(self):
        return self._count


class FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://ollama/api/chat")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    def json(self):
        return self._json


class FakeStreamResponse:
    """Async-context-manager stand-in for ``httpx.AsyncClient.stream(...)``."""

    def __init__(self, lines, status_code=200, enter_exc=None):
        self._lines = lines
        self.status_code = status_code
        self._enter_exc = enter_exc

    async def __aenter__(self):
        if self._enter_exc is not None:
            raise self._enter_exc
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "http://ollama/api/chat")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError("error", request=request, response=response)

    async def aiter_lines(self):
        for line in self._lines:
            yield line


class FakeAsyncClient:
    def __init__(
        self,
        response=None,
        exc=None,
        stream_lines=None,
        stream_status=200,
        stream_exc=None,
    ):
        self._response = response
        self._exc = exc
        self._stream_lines = stream_lines or []
        self._stream_status = stream_status
        self._stream_exc = stream_exc
        self.calls = []
        self.stream_calls = []

    async def post(self, url, json=None):
        self.calls.append({"url": url, "json": json})
        if self._exc is not None:
            raise self._exc
        return self._response

    def stream(self, method, url, json=None):
        # httpx returns the context manager synchronously (not a coroutine).
        self.stream_calls.append({"method": method, "url": url, "json": json})
        return FakeStreamResponse(self._stream_lines, self._stream_status, self._stream_exc)


def build_client(
    *,
    documents=None,
    metadatas=None,
    ollama_json=None,
    ollama_exc=None,
    stream_lines=None,
    stream_status=200,
    stream_exc=None,
    feedback_path=None,
    count=42,
):
    if documents is None:
        documents = ["Chunk about Hyrule.", "Chunk about bombs."]
    if metadatas is None:
        metadatas = [{"title": "Zelda"}, {"title": "Mario"}]
    if ollama_json is None:
        ollama_json = {"message": {"content": "Use bombs on the cracked wall."}}

    settings = (
        server.Settings(feedback_path=feedback_path)
        if feedback_path is not None
        else server.Settings()
    )
    app = server.create_app(settings)
    fake_http = FakeAsyncClient(
        response=FakeResponse(ollama_json),
        exc=ollama_exc,
        stream_lines=stream_lines,
        stream_status=stream_status,
        stream_exc=stream_exc,
    )
    app.dependency_overrides[server.get_embedder] = lambda: FakeEmbedder()
    app.dependency_overrides[server.get_collection] = lambda: FakeCollection(
        documents, metadatas, count
    )
    app.dependency_overrides[server.get_http_client] = lambda: fake_http
    return TestClient(app), fake_http


def test_health_returns_chunk_count():
    client, _ = build_client(count=123)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "chunks": 123}


def test_stats_reports_model_and_config():
    client, _ = build_client(count=7)
    resp = client.get("/stats")
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "llama3.1:8b"
    assert body["chunks"] == 7
    assert body["top_k"] == 5


def test_chat_success_returns_answer_and_sorted_unique_sources():
    client, fake_http = build_client(
        metadatas=[{"title": "Zelda"}, {"title": "Mario"}, {"title": "Zelda"}],
    )
    resp = client.post("/chat", json={"message": "How do I beat the boss?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["response"] == "Use bombs on the cracked wall."
    assert body["sources"] == ["Mario", "Zelda"]  # de-duplicated + sorted

    sent = fake_http.calls[0]["json"]
    assert sent["model"] == "llama3.1:8b"
    assert sent["messages"][0]["role"] == "system"
    assert sent["messages"][-1] == {"role": "user", "content": "How do I beat the boss?"}


def test_chat_forwards_conversation_history():
    client, fake_http = build_client()
    resp = client.post(
        "/chat",
        json={
            "message": "and the second boss?",
            "history": [
                {"role": "user", "content": "first boss?"},
                {"role": "assistant", "content": "use fire."},
            ],
        },
    )
    assert resp.status_code == 200
    roles = [m["role"] for m in fake_http.calls[0]["json"]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_chat_handles_zero_retrieval_without_a_context_block():
    client, fake_http = build_client(documents=[], metadatas=[])
    resp = client.post("/chat", json={"message": "hello"})
    assert resp.status_code == 200
    assert resp.json()["sources"] == []
    system_prompt = fake_http.calls[0]["json"]["messages"][0]["content"]
    assert "Context:" not in system_prompt


def test_chat_rejects_empty_message():
    client, _ = build_client()
    assert client.post("/chat", json={"message": ""}).status_code == 422


def test_chat_rejects_blank_message():
    client, _ = build_client()
    assert client.post("/chat", json={"message": "    "}).status_code == 422


def test_chat_rejects_oversized_message():
    client, _ = build_client()
    huge = "a" * (server.MAX_MESSAGE_CHARS + 1)
    assert client.post("/chat", json={"message": huge}).status_code == 422


def test_chat_rejects_invalid_history_role():
    client, _ = build_client()
    resp = client.post(
        "/chat",
        json={"message": "hi", "history": [{"role": "system", "content": "x"}]},
    )
    assert resp.status_code == 422


def test_chat_returns_502_when_ollama_unreachable():
    client, _ = build_client(ollama_exc=httpx.ConnectError("connection refused"))
    assert client.post("/chat", json={"message": "hi"}).status_code == 502


def test_chat_returns_502_on_malformed_ollama_response():
    client, _ = build_client(ollama_json={"unexpected": "shape"})
    assert client.post("/chat", json={"message": "hi"}).status_code == 502


# ---------------------------------------------------------------------------
# Streaming endpoint (/chat/stream)
# ---------------------------------------------------------------------------


def _parse_ndjson(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _ollama_stream_lines(*tokens):
    """Build Ollama-style NDJSON lines: one token per line, a final done line."""
    lines = [json.dumps({"message": {"content": t}, "done": False}) for t in tokens]
    lines.append(json.dumps({"message": {"content": ""}, "done": True}))
    return lines


def test_chat_stream_emits_sources_then_tokens_then_done():
    client, fake_http = build_client(
        metadatas=[{"title": "Zelda"}, {"title": "Mario"}, {"title": "Zelda"}],
        stream_lines=_ollama_stream_lines("Use ", "bombs."),
    )
    resp = client.post("/chat/stream", json={"message": "How do I beat the boss?"})

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/x-ndjson")

    events = _parse_ndjson(resp.text)
    assert events[0] == {"type": "sources", "sources": ["Mario", "Zelda"]}
    tokens = [e["token"] for e in events if e["type"] == "token"]
    assert "".join(tokens) == "Use bombs."
    assert events[-1] == {"type": "done"}

    # The upstream call asked Ollama to stream, with the user turn last.
    sent = fake_http.stream_calls[0]["json"]
    assert sent["stream"] is True
    assert sent["messages"][-1] == {"role": "user", "content": "How do I beat the boss?"}


def test_chat_stream_forwards_history():
    client, fake_http = build_client(stream_lines=_ollama_stream_lines("ok"))
    client.post(
        "/chat/stream",
        json={
            "message": "and the second boss?",
            "history": [
                {"role": "user", "content": "first boss?"},
                {"role": "assistant", "content": "use fire."},
            ],
        },
    )
    roles = [m["role"] for m in fake_http.stream_calls[0]["json"]["messages"]]
    assert roles == ["system", "user", "assistant", "user"]


def test_chat_stream_reports_ollama_failure_as_in_band_error_event():
    # Headers flush before generation, so the failure can't be an HTTP error code.
    client, _ = build_client(stream_exc=httpx.ConnectError("connection refused"))
    resp = client.post("/chat/stream", json={"message": "hi"})

    assert resp.status_code == 200
    events = _parse_ndjson(resp.text)
    assert events[0]["type"] == "sources"
    assert events[-1]["type"] == "error"


def test_chat_stream_reports_http_status_error_as_error_event():
    client, _ = build_client(stream_status=500, stream_lines=_ollama_stream_lines("x"))
    resp = client.post("/chat/stream", json={"message": "hi"})
    events = _parse_ndjson(resp.text)
    assert events[-1]["type"] == "error"


def test_chat_stream_rejects_blank_message():
    client, _ = build_client()
    assert client.post("/chat/stream", json={"message": "   "}).status_code == 422


# ---------------------------------------------------------------------------
# Feedback endpoint (/feedback)
# ---------------------------------------------------------------------------


def test_feedback_appends_a_jsonl_record(tmp_path):
    path = tmp_path / "feedback.jsonl"
    client, _ = build_client(feedback_path=str(path))

    resp = client.post(
        "/feedback",
        json={
            "query": "How do I beat the boss?",
            "answer": "Use bombs.",
            "rating": "up",
            "sources": ["Zelda"],
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "recorded"}

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["rating"] == "up"
    assert record["query"] == "How do I beat the boss?"
    assert record["answer"] == "Use bombs."
    assert record["sources"] == ["Zelda"]
    assert record["model"] == "llama3.1:8b"
    assert "timestamp" in record


def test_feedback_appends_multiple_records(tmp_path):
    path = tmp_path / "feedback.jsonl"
    client, _ = build_client(feedback_path=str(path))

    client.post("/feedback", json={"query": "q1", "answer": "a1", "rating": "up"})
    client.post("/feedback", json={"query": "q2", "answer": "a2", "rating": "down"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["rating"] for line in lines] == ["up", "down"]


def test_feedback_rejects_invalid_rating(tmp_path):
    client, _ = build_client(feedback_path=str(tmp_path / "f.jsonl"))
    resp = client.post("/feedback", json={"query": "q", "answer": "a", "rating": "meh"})
    assert resp.status_code == 422


def test_feedback_rejects_blank_query(tmp_path):
    client, _ = build_client(feedback_path=str(tmp_path / "f.jsonl"))
    resp = client.post("/feedback", json={"query": "   ", "answer": "a", "rating": "up"})
    assert resp.status_code == 422
