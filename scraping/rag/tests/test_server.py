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


class FakeAsyncClient:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    async def post(self, url, json=None):
        self.calls.append({"url": url, "json": json})
        if self._exc is not None:
            raise self._exc
        return self._response


def build_client(
    *,
    documents=None,
    metadatas=None,
    ollama_json=None,
    ollama_exc=None,
    count=42,
):
    if documents is None:
        documents = ["Chunk about Hyrule.", "Chunk about bombs."]
    if metadatas is None:
        metadatas = [{"title": "Zelda"}, {"title": "Mario"}]
    if ollama_json is None:
        ollama_json = {"message": {"content": "Use bombs on the cracked wall."}}

    app = server.create_app(server.Settings())
    fake_http = FakeAsyncClient(response=FakeResponse(ollama_json), exc=ollama_exc)
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
