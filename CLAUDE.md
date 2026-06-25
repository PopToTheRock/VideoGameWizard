# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

This is an Android project built with Gradle. Use Android Studio or the Gradle wrapper:

```bash
# Build debug APK
./gradlew assembleDebug

# Install on connected device/emulator
./gradlew installDebug

# Run all instrumented (UI) tests on connected device
./gradlew connectedAndroidTest

# Run a single instrumented test class
./gradlew connectedAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=dev.alexn.videogamewizard.NavigationTest

# Run unit tests (currently none exist)
./gradlew test
```

## Running the Full Stack

Three processes must be running for the app to work:

```bash
# 1. Start Ollama (serves Llama 3.1 8B on port 11434)
ollama serve

# 2. Start the RAG server (port 8000) — from scraping/rag/
#    Loopback default (emulator). For a physical device on the LAN, bind 0.0.0.0
#    and set VGW_API_KEY (client sends it as X-API-Key); see the RAG Server section.
uvicorn server:app --host 127.0.0.1 --port 8000

# 3. Run the Android app on emulator or physical device
```

Health check: `http://localhost:8000/health`

**Physical device**: override the `BASE_URL` `buildConfigField` in `app/build.gradle.kts` (surfaced via `BuildConfig.BASE_URL`) with your PC's local IP, e.g. `192.168.1.42`.

---

## Android Architecture

The app is a single-module Android project (`app`) using **Jetpack Compose** and **Navigation Compose**, structured with MVVM.

### Package Structure

```
dev.alexn.videogamewizard/
├── MainActivity.kt
├── navigation/
│   ├── AppNavGraph.kt          # NavHost with Welcome + Home routes
│   └── Route.kt                # Type-safe sealed interface routes
├── data/
│   ├── model/
│   │   ├── ChatMessage.kt      # data class (id, author, text)
│   │   └── ChatAuthor.kt       # enum USER / AI
│   ├── network/
│   │   ├── RagApi.kt           # Retrofit interface — POST /chat
│   │   ├── RagModels.kt        # ChatRequest, ChatResponse, HistoryMessage
│   │   └── RetrofitClient.kt   # Singleton Retrofit + OkHttp client
│   └── repository/
│       └── ChatRepository.kt   # Calls RagApi, converts ChatMessage → HistoryMessage
└── ui/
    ├── screens/
    │   ├── WelcomeScreen.kt
    │   ├── HomeScreen.kt
    │   ├── HomeViewModel.kt     # Calls ChatRepository, handles success/error
    │   └── HomeUiState.kt       # messages, input, isAiTyping
    ├── components/
    │   ├── ChatBubble.kt
    │   ├── TypingIndicatorBubble.kt
    │   └── UserChatFieldComposer.kt
    └── theme/
        ├── Color.kt, Theme.kt, Type.kt
```

### Data Flow

```
User types message
        ↓
HomeViewModel.sendMessage()
        ↓
ChatRepository.streamMessage(message, history) → Flow<ChatStreamEvent>
        ↓
RagApi.chatStream() via Retrofit @Streaming (POST http://10.0.2.2:8000/chat/stream)
  └── reads the NDJSON body line-by-line on Dispatchers.IO, emitting Sources/Token events
        ↓
RAG Server (FastAPI, port 8000)
  ├── Embeds query (sentence-transformers)
  ├── Queries ChromaDB → top 5 relevant chunks
  ├── Builds system prompt with context
  └── Calls Ollama POST /api/chat
        ↓
Ollama (llama3.1:8b, port 11434)  ← called with stream=True; tokens proxied as they arrive
        ↓
Tokens stream back to HomeViewModel → grow a transient partial bubble → persisted to
Room once on completion (zero per-token DB writes). A Stop button cancels mid-stream,
keeping the partial (persisted under NonCancellable).
```

### Key Dependencies

- Kotlin + Compose BOM
- `androidx.navigation.compose` for navigation
- `androidx.compose.material.icons.extended` for icons
- `retrofit2` + `okhttp3` for HTTP
- `kotlinx-serialization-json` for JSON
- `retrofit2-kotlinx-serialization-converter` (JakeWharton) for Retrofit ↔ kotlinx.serialization
- `androidx.room` (runtime/ktx + kapt compiler) for local chat-history persistence
- `minSdk = 24`, `targetSdk = 36`, Java 21

### Persistence & Dependency Injection

- **Room is the single source of truth for chat messages.** `ChatDao.observeAll()` exposes a
  `Flow<List<ChatMessageEntity>>` that `HomeViewModel` maps and `combine`s with transient UI
  state (input, typing) into `HomeUiState`. Sending/clearing writes through `ChatHistoryRepository`
  (Room-backed), so the conversation survives app restart. Code: `data/local/` + `data/repository/`.
- **Source citations (DB v2).** An AI reply persists its grounding source titles in a `sources`
  column (JSON-encoded; (de)serialised in `RoomChatHistoryRepository`). The streamed `sources`
  event is held in transient UI state and rendered as tappable chips under the reply (`ChatBubble`
  → Wikipedia article), then persisted on completion and carried into the `/feedback` record.
  Schema bumped 1→2 with a real `MIGRATION_1_2` (`AppDatabase`); destructive fallback kept as a backstop.
- **Manual dependency injection** (no Hilt yet — its Gradle plugin lags AGP 9.0): `VideoGameWizardApp`
  builds a `DefaultAppContainer` (`di/`) holding the Room DB + repositories, and
  `HomeViewModel.Factory` pulls them via `APPLICATION_KEY`. Unit tests inject fakes/mocks directly.

---

## AI Infrastructure

### Strategy
Self-hosted AI model running locally on the developer's machine. The Android app communicates via a local RAG server (not directly to Ollama). No external AI APIs.

### Architecture

```
Scraping Pipeline
└── Wikipedia  → MediaWiki API (scraping/wikipedia/)
        ↓
Data Cleaning (scraping/wikipedia/wikipedia_cleaner.py)
        ↓
Chunking (scraping/rag/chunker.py)
  └── 1000-char chunks, 150-char overlap, paragraph-aligned
        ↓
Embedding + ChromaDB (scraping/rag/embed.py)
  └── sentence-transformers/all-MiniLM-L6-v2 → 191,193 chunks
        ↓
RAG Server (scraping/rag/server.py) — FastAPI on port 8000
  ├── POST /chat — embed query → ChromaDB retrieval → Ollama call
  └── GET /health — liveness check
        ↓
Ollama — llama3.1:8b on port 11434
        ↓ REST API (Retrofit)
Android App
```

### Model
- **Llama 3.1 8B** via Ollama (base default; `vgw-rag:8b` is the QLoRA fine-tune)
- ✅ Fine-tuned with **QLoRA** (Unsloth + TRL) into a grounded RAG reader — see `finetune/`
- RAG with **ChromaDB** + **sentence-transformers/all-MiniLM-L6-v2**

### Developer Machine Specs
- GPU: RTX 5070 Ti — 16GB VRAM (Blackwell architecture)
- CUDA: 13.2
- Python: 3.14 (Windows)
- All training and inference runs locally — no cloud/Colab needed

### Installed Software
- NVIDIA drivers (up to date)
- CUDA 13.2
- Ollama — model pulled: `llama3.1:8b` (served at `http://localhost:11434`)
- VS Code
- WSL2 (required for Unsloth fine-tuning — Ubuntu installed, nvidia-smi working)
- Python 3.14

### Python Packages Installed (Windows)
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install sentence-transformers chromadb
pip install fastapi uvicorn requests
pip install scrapy beautifulsoup4
```

**WSL2 (fine-tuning — not yet installed):**
```bash
pip install torch --index-url https://download.pytorch.org/whl/cu128
pip install unsloth transformers peft datasets trl
```

---

## Scraping Pipeline

### Data Sources (Final Decisions)
| Source | Status | Reason |
|--------|--------|--------|
| Wikipedia | ✅ Used | CC BY-SA, API allows it, 18,019 articles |
| Reddit | ❌ Skipped | Explicitly bans AI training use |
| YouTube | ❌ Skipped for now | — |
| Fandom wikis | ❌ Skipped | CC BY-NC-SA blocks future monetisation |
| wiki.gg | ❌ Skipped | Only 2 relevant wikis; API issues |

### Wikipedia Fetcher (`scraping/wikipedia/`)
- Uses MediaWiki Action API — no scraping, no auth needed
- **Critical**: TextExtracts API enforces `exlimit=1` for full articles → `BATCH_SIZE = 1`
- Enumerates articles via category members, recurses into subcategories (`CATEGORY_DEPTH=2`)
- 18,019 articles written, 520 skipped (stubs/disambig)
- Output: `scraping/data/wikipedia_raw.jsonl`

```bash
cd scraping/wikipedia
py wikipedia_fetcher.py          # full run (~2.5 hours)
py wikipedia_fetcher.py --limit 10   # test run
py wikipedia_fetcher.py --dry-run    # enumerate only
```

### Wikipedia Cleaner (`scraping/wikipedia/wikipedia_cleaner.py`)
- Removes boilerplate tail sections (References, See also, External links, etc.)
- Removes MediaWiki template remnants (`{{cite book}}`, CS1 maint notices)
- Removes citation markers `[1]`, Unicode replacement chars
- Normalises whitespace
- Output: `scraping/data/wikipedia_clean.jsonl` (17,825 articles after cleaning)

```bash
cd scraping/wikipedia && py wikipedia_cleaner.py
```

---

## RAG Pipeline (`scraping/rag/`)

### Chunker (`chunker.py`)
- Splits articles on paragraph boundaries (`\n\n`)
- **Max 850 chars/chunk, 130-char overlap** — sized to stay under the embedder's
  256-token limit (`config.EMBED_MAX_TOKENS`). `chunk_article` **guarantees** no chunk
  exceeds the cap (overlap is a trailing-char budget, not whole paragraphs); `main()`
  asserts it. (Was 1000/150, which overshot ~2x and silently truncated ~69% of chunks
  at embed time — see `docs/AUDIT.md` H6/H7.)
- Paragraphs longer than the cap are split at sentence boundaries
- Stable MD5 chunk IDs from `title::chunk_index`
- Output: `scraping/data/chunks.jsonl`. **Chunk count changes when re-chunked** at the new
  size — rebuild with `py chunker.py` then re-embed with `py embed.py` (embed.py now
  pins `max_seq_length` and logs the token-length distribution + any residual overflow).

```bash
cd scraping/rag && py chunker.py
```

### Embedder (`embed.py`)
- Model: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, 256-token limit)
- Deduplicates by chunk ID upfront before embedding
- Embeds all chunks in one GPU pass (`EMBED_BATCH_SIZE=2048`)
- Inserts into ChromaDB in batches of 5000 (max allowed by ChromaDB is 5461)
- ChromaDB store: `scraping/data/chromadb/`, collection: `game_knowledge`, cosine distance
- **PyTorch CUDA note**: must use `pip install torch --index-url https://download.pytorch.org/whl/cu128 --force-reinstall`

```bash
cd scraping/rag && py embed.py
```

### RAG Server (`server.py`)
- FastAPI app, port 8000. **Async throughout** — Ollama is called via `httpx.AsyncClient`.
- **Env-driven config** via pydantic-settings (`Settings`, `VGW_` prefix). Resources
  (ChromaDB collection, embedding model, HTTP client) load in a `lifespan` and are supplied
  by **dependency injection** — which is what makes the endpoints unit-testable.
- `POST /chat` — `{message, history}` → top-k chunks → Ollama. Validates input (non-blank,
  message + each history turn ≤4096 chars; history ≤50 turns; roles must be
  `user`/`assistant`); returns 502 on Ollama failure. Buffered (full answer in one
  response); retained for scripts/eval/tests.
- `POST /chat/stream` — same contract, streamed as **NDJSON** (`application/x-ndjson`):
  one `{"type":"sources",...}` line, then `{"type":"token",...}` per token, then
  `{"type":"done"}` (or `{"type":"error","message":...}` if generation fails mid-stream —
  the 200 headers have already flushed, so failures are reported in-band). Request
  *validation* still fails fast with 422. Retrieval + prompt-building are shared with `/chat`
  via `retrieve_context()` / `build_messages()`. This is the path the Android app uses.
- `POST /feedback` — records a thumbs `up`/`down` on an answer to `data/feedback.jsonl`
  (one `{timestamp, rating, model, query, answer, sources}` line per tap). A preference
  dataset for later DPO/RLHF or quality analysis; the blocking append is offloaded to a
  threadpool. `data/` is gitignored, so the log stays local.
- `GET /health` — chunk count (always open) · `GET /stats` — model/collection/config · `/docs` — OpenAPI UI
- **Optional auth**: set `VGW_API_KEY` to require a matching `X-API-Key` header on
  `/chat`, `/chat/stream`, `/feedback`, `/stats` (`/health` stays open). Unset = off
  (loopback-only default). Bind 127.0.0.1 for the emulator; only use `--host 0.0.0.0`
  (physical-device/LAN) together with a key.
- Heavy imports (chromadb, sentence-transformers) are deferred to `lifespan` so the module
  imports without the ML stack — tests run on just `requirements-test.txt`.
- Tests: `scraping/rag/tests/` (pytest, mocked ChromaDB + Ollama). Lint/format: `ruff` (see `ruff.toml`).

```bash
cd scraping/rag
uvicorn server:app --host 127.0.0.1 --port 8000   # add VGW_API_KEY + --host 0.0.0.0 for LAN
```

### Evaluation Harness (`eval/`)
- Measures **retrieval quality** and the lift from **cross-encoder reranking** on a
  synthetic, seed-reproducible gold set. Fully local (Ollama only authors the eval set).
- `generate_eval_set.py` — reservoir-samples chunks (fixed seed) and has `llama3.1:8b`
  write one question per chunk; the source chunk *is* the gold label (`data/eval_set.jsonl`,
  committed as the benchmark). `retriever.py` mirrors the server's embed+cosine-collection
  contract offline; `rerank.py` wraps `cross-encoder/ms-marco-MiniLM-L-6-v2`; `metrics.py`
  holds pure hit-rate@k / MRR / nDCG@k fns (unit-tested in `tests/test_eval_metrics.py`).
- `run_eval.py` reports baseline vs. reranked at **chunk-level** (exact source chunk) and
  **article-level** (any chunk from the source article). Run with the **full ML env** (base
  `py`), not the `.venv` (which is the lint/test env). Results table + methodology:
  `eval/README.md`. Timestamped `results/*.json` are gitignored.

```bash
cd scraping/rag
py -m eval.generate_eval_set --n 150 --seed 42   # needs Ollama
py -m eval.run_eval                               # baseline vs reranked
```

### QLoRA Fine-tuning (`finetune/`)
- Adapts Llama 3.1 8B into a **grounded RAG reader** (answer from retrieved context,
  concisely, in the VGW voice). Fine-tuning teaches skill/format/style; RAG still supplies
  facts. Full model card: `finetune/README.md`.
- `prepare_data.py` (Windows + Ollama) → `data/train.jsonl`/`val.jsonl`: grounded
  (context+Q→A) examples in `messages` format matching the server prompt; **assistant-only
  loss**; eval chunks excluded. `train_qlora.py` (**WSL2 venv** `~/vgw-finetune`: Unsloth +
  TRL, torch cu128 on sm_120) → adapter + `loss_curve.png` + `training_summary.json`.
  `export_merged.py` (WSL2) merges the adapter to 16-bit; Ollama then quantizes on import.
  `compare_models.py` produces the qualitative base-vs-fine-tuned `comparison.md`;
  `judge_models.py` produces the **quantitative** downstream win-rate (LLM-judge over
  the val split, deterministic, position-bias-controlled) → `judge_results.md`/`.json`.
- **`import unsloth` must precede trl/transformers** in training scripts. GGUF quantization
  is routed through `ollama create --quantize` (no llama.cpp/cmake build). `outputs/`
  (adapter, merged model) is gitignored; the dataset + results are committed.
- The fine-tuned model is registered as `vgw-rag:8b`; serve it with
  `VGW_OLLAMA_MODEL=vgw-rag:8b`. Server default stays `llama3.1:8b`.

```bash
# WSL2: source ~/vgw-finetune/bin/activate ; cd scraping
python -m finetune.train_qlora --epochs 1     # then: python -m finetune.export_merged
ollama create vgw-rag:8b --quantize q4_K_M -f finetune/Modelfile   # Windows
```

---

## Build Order

1. ✅ Scraping pipeline (Wikipedia)
2. ✅ Data cleaning & chunking
3. ✅ RAG pipeline (ChromaDB + embeddings)
4. ✅ Wire up Ollama + Android app via RAG server
5. ✅ Fine-tuning (QLoRA via Unsloth in WSL2) — `vgw-rag:8b`

---

## Pending Code Review Issues

These were identified in a full code review. See `ROADMAP.md` for the broader portfolio plan.

### Resolved (Milestone 1)

- ✅ **Issue 6 — Hardcoded UI strings**: all UI strings extracted to `res/values/strings.xml` and read via `stringResource(...)`.
- ✅ **Issue 7 — `LaunchedEffect` auto-scroll**: now keyed on the last message id and `isAiTyping` (catches in-place replacements and the typing indicator), not `messages.size`.
- ✅ **Issue 8 — `BASE_URL` hardcoded**: moved to a `buildConfigField` in `app/build.gradle.kts`, read via `BuildConfig.BASE_URL`.
- ✅ **Issue 9 — Fixed-size button**: `WelcomeScreen` button no longer hard-codes width/height; it sizes to content + padding so it scales with font-size settings.
- ✅ **Issue 10 — Missing `@Immutable`**: added to `ChatMessage` and `HomeUiState`.
- ✅ **Timeout magic numbers**: `RetrofitClient` timeouts extracted to named constants with a comment.

### Still open (tracked in ROADMAP.md)

- **No unit tests** — `HomeViewModel` and `ChatRepository` have zero unit coverage (Milestone 2).
- **No dependency injection** — `HomeViewModel` constructs `ChatRepository()` directly. Introduce Hilt (Milestone 3).
- **No spacing/typography design system** — padding and text sizes are scattered magic numbers. Consider a `Spacing` object for consistency.

---

## Must Have Goals

- Engineering at the level of the best Google engineers in the world
- Ensuring best practices of all relevant programming languages, frameworks and third party software for this app
- Always evaluate any decisions made against what a top level Google engineer would do
