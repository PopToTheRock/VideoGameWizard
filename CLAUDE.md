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
./gradlew connectedAndroidTest -Pandroid.testInstrumentationRunnerArguments.class=com.example.videogamewizard.NavigationTest

# Run unit tests (currently none exist)
./gradlew test
```

## Running the Full Stack

Three processes must be running for the app to work:

```bash
# 1. Start Ollama (serves Llama 3.1 8B on port 11434)
ollama serve

# 2. Start the RAG server (port 8000) — from scraping/rag/
uvicorn server:app --host 0.0.0.0 --port 8000

# 3. Run the Android app on emulator or physical device
```

Health check: `http://localhost:8000/health`

**Physical device**: change `BASE_URL` in `data/network/RetrofitClient.kt` from `10.0.2.2` to your PC's local IP.

---

## Android Architecture

The app is a single-module Android project (`app`) using **Jetpack Compose** and **Navigation Compose**, structured with MVVM.

### Package Structure

```
com.example.videogamewizard/
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
ChatRepository.sendMessage(message, history)
        ↓
RagApi.chat() via Retrofit (POST http://10.0.2.2:8000/chat)
        ↓
RAG Server (FastAPI, port 8000)
  ├── Embeds query (sentence-transformers)
  ├── Queries ChromaDB → top 5 relevant chunks
  ├── Builds system prompt with context
  └── Calls Ollama POST /api/chat
        ↓
Ollama (llama3.1:8b, port 11434)
        ↓
Response flows back to HomeViewModel → UI
```

### Key Dependencies

- Kotlin + Compose BOM
- `androidx.navigation.compose` for navigation
- `androidx.compose.material.icons.extended` for icons
- `retrofit2` + `okhttp3` for HTTP
- `kotlinx-serialization-json` for JSON
- `retrofit2-kotlinx-serialization-converter` (JakeWharton) for Retrofit ↔ kotlinx.serialization
- `minSdk = 24`, `targetSdk = 36`, Java 21

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
  └── sentence-transformers/all-MiniLM-L6-v2 → 189,958 chunks
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
- **Llama 3.1 8B** via Ollama
- Fine-tuning with **QLoRA** (Unsloth + HuggingFace PEFT) — **not done yet, next step**
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
- Max 1000 chars per chunk, 150-char overlap
- Paragraphs longer than 1000 chars split at sentence boundaries
- Stable MD5 chunk IDs from `title::chunk_index`
- Output: `scraping/data/chunks.jsonl` — 189,958 unique chunks (avg 11.2/article)

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
- FastAPI app, port 8000
- `POST /chat` — receives `{message, history}`, retrieves top-5 chunks, calls Ollama
- `GET /health` — returns chunk count
- Loads ChromaDB + embedding model at startup (takes ~10s)

```bash
cd scraping/rag
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## Build Order

1. ✅ Scraping pipeline (Wikipedia)
2. ✅ Data cleaning & chunking
3. ✅ RAG pipeline (ChromaDB + embeddings)
4. ✅ Wire up Ollama + Android app via RAG server
5. ⬜ Fine-tuning (QLoRA via Unsloth in WSL2)

---

## Pending Code Review Issues

These were identified in a full code review and are not yet implemented. Address them before shipping.

### High Priority

**Issue 6 — Hardcoded UI strings**
`ChatBubble.kt`, `TypingIndicatorBubble.kt`, `HomeScreen.kt` contain hardcoded strings (`"Wizard AI"`, `"You"`, `"Typing…"`). These should be extracted to `res/values/strings.xml` so they are localisation-ready and easy to update in one place.

**Issue 7 — `LaunchedEffect` auto-scroll keyed on wrong value**
`HomeScreen.kt` keys its auto-scroll `LaunchedEffect` on `messages.size`. This misses the case where a message is replaced (e.g. an error message replaces a typing indicator) because the size doesn't change. Key on the ID of the last message instead:
```kotlin
val lastId = messages.lastOrNull()?.id
LaunchedEffect(lastId) { /* scroll to bottom */ }
```

**Issue 8 — `BASE_URL` hardcoded in `RetrofitClient.kt`**
`"http://10.0.2.2:8000/"` only works on the emulator. On a physical device you must edit the source. Move the URL to a `BuildConfig` field via `buildConfigField` in `build.gradle.kts`, or at minimum document it prominently and provide a `BuildVariant`-based override so physical-device testing doesn't require a code edit.

**Issue 9 — Fixed-size button ignores accessibility in `WelcomeScreen.kt`**
`Modifier.width(200.dp).height(50.dp)` prevents the button from scaling with the user's font-size preference. Use `Modifier.fillMaxWidth(fraction)` and let the button height be driven by padding instead of a hard-coded size, so it respects large-text accessibility settings.

**Issue 10 — Missing `@Stable` / `@Immutable` annotations**
`ChatMessage` and `HomeUiState` are used as Compose state but lack `@Immutable` / `@Stable` annotations. Without them the Compose compiler conservatively re-composes on every state update. Add `@Immutable` to both (they are fully immutable data classes):
```kotlin
@Immutable data class ChatMessage(...)
@Immutable data class HomeUiState(...)
```

### Lower Priority (Nice to Have)

- **No unit tests** — `HomeViewModel` and `ChatRepository` have zero unit test coverage. Add JUnit 5 + MockK / Turbine tests for `sendMessage` success/failure/cancellation paths and the `errorMessage` classifier.
- **No dependency injection** — `HomeViewModel` constructs `ChatRepository()` directly, and `ChatRepository` constructs `RetrofitClient.ragApi` directly. Introduce Hilt (or manual constructor injection for now) so these dependencies can be swapped in tests without reflection hacks.
- **Timeout magic numbers** — `connectTimeout(10, ...)` and `readTimeout(120, ...)` in `RetrofitClient.kt` are unexplained constants. Extract them to named constants or a config object with a comment explaining why 120s (LLM generation time).
- **No accessibility `contentDescription`** — Icon buttons (send, clear, etc.) in `UserChatFieldComposer.kt` likely lack `contentDescription`. Screen readers will announce them as unlabelled. Add descriptive strings.
- **No spacing/typography design system** — padding and text sizes are scattered magic numbers. Consider a `Spacing` object (`object Spacing { val sm = 8.dp; val md = 16.dp ... }`) for consistency.

---

## Must Have Goals

- Engineering at the level of the best Google engineers in the world
- Ensuring best practices of all relevant programming languages, frameworks and third party software for this app
- Always evaluate any decisions made against what a top level Google engineer would do
