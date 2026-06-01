# VideoGameWizard: Master Technical Learning Plan

Topics marked **[CRITICAL PATH]** are prerequisites for later phases.
Topics marked **[OPTIONAL DEPTH]** deepen expertise but are not blockers.
Each phase builds on the previous — do not skip critical-path items.

---

## Phase 0: Foundations

### 0.1 Kotlin Language Mastery [CRITICAL PATH]

**Topics:**
- Type system: nullability (`?`, `!!`, `?.`, `?:`), smart casts, `Nothing`, variance (`in`/`out`/`*`)
- Coroutines and structured concurrency: `CoroutineScope`, `Job`, `SupervisorJob`, `CoroutineContext`, `Dispatchers`
- `Flow`: cold vs hot flows, `StateFlow`, `SharedFlow`, backpressure, terminal operators (`collect`, `first`, `toList`)
- Suspend functions: how the compiler transforms them into continuation-passing style (CPS) state machines
- Extension functions/properties: compile to static JVM methods — how they actually work under the hood
- Sealed classes and sealed interfaces: exhaustive `when` expressions, difference from enums
- Data classes: `copy()`, `componentN()`, structural equality vs referential equality
- `object` declarations vs companion objects vs anonymous objects
- Delegation: `by lazy`, `by viewModels()`, interface delegation with `by`
- Inline functions and `reified` generics: why type erasure requires `reified`, performance implications
- Kotlin Serialization: `@Serializable`, `@SerialName`, polymorphic serialization, custom serializers

**Connection to VideoGameWizard:**
- `HomeViewModel` uses `viewModelScope` to launch `sendMessage()` as a coroutine
- `HomeUiState` is a data class mutated via `copy()` inside `StateFlow`
- `RagApi.kt` uses suspend functions for the Retrofit network call
- `RagModels.kt` uses `@Serializable` and `@SerialName` for JSON mapping

**Resources:**
- _Kotlin in Action_ (Jemerov & Isakova) — chapters 1–10
- JetBrains Kotlin Coroutines Guide (official docs)
- Roman Elizarov's coroutines talks (KotlinConf)
- Kotlin Serialization official docs

**Success Criteria:**
- Explain continuation-passing style without looking it up
- Write a `StateFlow`-backed ViewModel from scratch with error handling
- Implement a custom `@Serializable` with a manual serializer

---

### 0.2 JVM & Android Runtime Basics [CRITICAL PATH]

**Topics:**
- Android process model: app process, main thread (UI thread), binder IPC
- Activity / Fragment lifecycle vs Compose lifecycle
- `ViewModel` scoping: `viewModelScope`, `SavedStateHandle`
- `Looper` / `Handler` vs coroutine `Dispatchers.Main`
- ProGuard / R8 shrinking and how it affects Kotlin reflection
- Gradle build system: `build.gradle.kts`, dependency resolution, `buildConfigField`, build variants
- `minSdk`, `targetSdk`, `compileSdk` — what each controls and why they differ

**Connection to VideoGameWizard:**
- `HomeViewModel` survives configuration changes because it is scoped to the NavBackStackEntry
- `buildConfigField` is the recommended fix for the hardcoded `BASE_URL` (Issue 8 in CLAUDE.md)
- `minSdk = 24`, `targetSdk = 36` affect which APIs are available

**Resources:**
- Android Developer docs: App architecture guide
- _Android Programming: The Big Nerd Ranch Guide_
- Gradle docs: Kotlin DSL primer

**Success Criteria:**
- Add a `buildConfigField` to expose `BASE_URL` without hardcoding it in source
- Explain what happens to a `ViewModel` across screen rotation

---

## Phase 1: Android UI — Jetpack Compose

### 1.1 Compose Fundamentals [CRITICAL PATH]

**Topics:**
- The Compose compiler plugin: how `@Composable` functions are transformed
- Recomposition: what triggers it, what skips it, slot table internals
- `remember`, `rememberSaveable`, `derivedStateOf` — when to use each
- `State<T>` vs `MutableState<T>`: unidirectional data flow
- `LaunchedEffect`, `SideEffect`, `DisposableEffect` — lifecycle-aware side effects
- `key()` composable: forcing recomposition of specific subtrees
- `@Stable` and `@Immutable` annotations: how the Compose compiler uses them to skip recomposition
- `Modifier` system: order matters, how modifiers chain as a linked list

**Connection to VideoGameWizard:**
- `HomeScreen.kt`: `LaunchedEffect(messages.size)` is a known bug — should be keyed on `lastId` (Issue 7)
- `ChatMessage` and `HomeUiState` lack `@Immutable` annotations (Issue 10), causing unnecessary recomposition
- `ChatBubble.kt`, `TypingIndicatorBubble.kt`, `UserChatFieldComposer.kt` are leaf composables that should be stable

**Resources:**
- Android Compose official docs (developer.android.com/jetpack/compose)
- _Jetpack Compose internals_ (Jorge Castillo)
- Compose compiler metrics (enable with Gradle flags to see which composables skip)

**Success Criteria:**
- Add `@Immutable` to `ChatMessage` and `HomeUiState` and verify via compiler metrics that recomposition is reduced
- Fix the `LaunchedEffect` bug in `HomeScreen.kt`
- Explain the slot table to someone without reading any docs

---

### 1.2 Compose Layouts & Material 3 [CRITICAL PATH]

**Topics:**
- `Box`, `Column`, `Row`, `LazyColumn`, `LazyRow` — layout algorithms
- `LazyListState`: programmatic scrolling, `animateScrollToItem`
- Material 3 components: `Scaffold`, `TopAppBar`, `TextField`, `IconButton`, `Card`
- Custom `Shape`, `Color`, theming with `MaterialTheme`
- `WindowInsets` and IME insets (keyboard avoidance)

**Connection to VideoGameWizard:**
- `HomeScreen.kt` uses `LazyColumn` + `LazyListState` for the chat message list
- `UserChatFieldComposer.kt` is the input bar — IME insets are needed for it to not hide behind the keyboard
- `WelcomeScreen.kt` uses hardcoded `width(200.dp).height(50.dp)` which violates accessibility (Issue 9)

**Resources:**
- Compose layout documentation
- Material 3 component catalog (m3.material.io)

**Success Criteria:**
- Fix `WelcomeScreen.kt` button to use `fillMaxWidth(fraction)` + padding instead of fixed dimensions
- Implement proper IME inset handling so keyboard doesn't cover the input field

---

### 1.3 Navigation Compose [CRITICAL PATH]

**Topics:**
- `NavHost`, `NavController`, `NavBackStackEntry`
- Type-safe routes with sealed interfaces (Kotlin serialization-based)
- Passing arguments between destinations
- Nested navigation graphs
- `rememberNavController` scoping
- Deep links

**Connection to VideoGameWizard:**
- `AppNavGraph.kt` defines the Welcome → Home navigation
- `Route.kt` uses a sealed interface for type-safe routes

**Resources:**
- Navigation Compose official docs
- Android Now in Android sample (demonstrates type-safe nav)

**Success Criteria:**
- Add a third screen (e.g., Settings) and navigate to it with a typed argument

---

### 1.4 Accessibility [OPTIONAL DEPTH]

**Topics:**
- `contentDescription` on `IconButton` and images
- `semantics {}` modifier: custom actions, roles, state descriptions
- Font scaling: `sp` vs `dp`, why fixed `dp` heights break large text
- TalkBack: how the accessibility tree is constructed from composables
- `LocalConfiguration.current.fontScale` for adaptive layouts

**Connection to VideoGameWizard:**
- Issue 6: hardcoded strings in `ChatBubble.kt` etc. should move to `strings.xml`
- Issue 9: fixed-size button in `WelcomeScreen.kt`
- Issue re: missing `contentDescription` on icon buttons in `UserChatFieldComposer.kt`

**Success Criteria:**
- Pass a TalkBack audit of `HomeScreen` with zero unlabelled interactive elements

---

## Phase 2: Android Networking

### 2.1 HTTP Fundamentals [CRITICAL PATH]

**Topics:**
- HTTP/1.1 vs HTTP/2: multiplexing, header compression, connection reuse
- Request/response anatomy: headers, body, status codes
- Connection pooling: how OkHttp manages it
- Timeouts: connect timeout vs read timeout vs write timeout — why 120s read timeout is needed for LLM inference
- TLS / cleartext: `network_security_config.xml` cleartext allowance for local dev
- JSON: serialization vs deserialization, schema evolution

**Connection to VideoGameWizard:**
- `RetrofitClient.kt`: 10s connect timeout, 120s read timeout (LLM generation is slow)
- `network_security_config.xml`: allows cleartext to `10.0.2.2` (emulator host)

**Resources:**
- OkHttp documentation
- HTTP/2 RFC (skim for concepts)

---

### 2.2 Retrofit + Kotlin Serialization [CRITICAL PATH]

**Topics:**
- Retrofit interface design: `@POST`, `@GET`, `@Body`, `@Path`, `@Query`
- Suspend function support in Retrofit 2.6+
- Converter factories: how JakeWharton's `kotlinx-serialization-converter` hooks into Retrofit
- Error handling: `Response<T>` wrapper vs exceptions, `HttpException`
- Singleton pattern for `RetrofitClient` — why it matters for connection pooling
- `OkHttpClient.Builder`: interceptors (logging, auth), timeouts

**Connection to VideoGameWizard:**
- `RagApi.kt`: `suspend fun chat(@Body request: ChatRequest): ChatResponse`
- `RetrofitClient.kt`: singleton OkHttp client with timeouts
- `ChatRepository.kt`: calls `RagApi`, converts between `ChatMessage` and `HistoryMessage`

**Resources:**
- Retrofit2 documentation
- JakeWharton retrofit2-kotlinx-serialization-converter README

**Success Criteria:**
- Add an HTTP logging interceptor to `RetrofitClient` for debug builds only
- Implement proper error handling in `ChatRepository` that distinguishes network errors from server errors

---

## Phase 3: Android Architecture

### 3.1 MVVM + Unidirectional Data Flow [CRITICAL PATH]

**Topics:**
- ViewModel: what it is, what it is not (not a silver bullet for all state)
- `StateFlow` vs `LiveData`: why `StateFlow` is preferred in Compose
- `UiState` sealed class pattern: `Loading`, `Success`, `Error` states
- `viewModelScope`: cancellation on ViewModel clear
- Repository pattern: single source of truth, offline-first thinking
- `Result<T>` / `kotlin.Result`: wrapping success and failure

**Connection to VideoGameWizard:**
- `HomeViewModel` → `HomeUiState` → `StateFlow` → `HomeScreen` `collectAsStateWithLifecycle()`
- `ChatRepository` is the single place that knows about the network layer

**Resources:**
- Android Architecture Guide (developer.android.com)
- _Android Architecture Blueprints_ (GitHub sample)

**Success Criteria:**
- Refactor `HomeUiState` to have explicit `Loading` / `Success` / `Error` sub-states

---

### 3.2 Dependency Injection with Hilt [OPTIONAL DEPTH]

**Topics:**
- DI fundamentals: constructor injection vs field injection, dependency graphs
- Hilt: `@HiltAndroidApp`, `@AndroidEntryPoint`, `@HiltViewModel`
- `@Module`, `@InstallIn`, `@Provides`, `@Binds`
- Scopes: `SingletonComponent`, `ViewModelComponent`, `ActivityComponent`
- Testing with Hilt: `@TestInstallIn`, replacing modules in tests

**Connection to VideoGameWizard:**
- Current code: `HomeViewModel` directly constructs `ChatRepository()` — untestable
- Fix: inject `ChatRepository` into `HomeViewModel` via Hilt

**Resources:**
- Hilt official documentation
- _Dependency Injection in Android with Dagger and Hilt_ (course)

**Success Criteria:**
- Migrate `HomeViewModel` and `ChatRepository` to Hilt-injected dependencies

---

### 3.3 Testing [OPTIONAL DEPTH]

**Topics:**
- Unit tests: JUnit 5, MockK for mocking Kotlin classes/suspend functions
- Turbine: testing `Flow` emissions (from `app.cash.turbine`)
- Instrumented tests: `connectedAndroidTest`, `ComposeTestRule`
- `TestDispatcher` (UnconfinedTestDispatcher, StandardTestDispatcher) for coroutine testing
- Fake vs Mock: when to use each

**Connection to VideoGameWizard:**
- `HomeViewModel.sendMessage()`: test success, network error, and cancellation paths
- `ChatRepository`: test that it maps `ChatMessage` → `HistoryMessage` correctly
- Navigation: `NavigationTest.kt` already exists as an instrumented test

**Resources:**
- Kotlin coroutines testing guide
- MockK documentation
- Turbine README (GitHub)

**Success Criteria:**
- Write unit tests for `HomeViewModel` covering success, error, and loading states using `TestDispatcher` + `Turbine`

---

## Phase 4: Python Backend — RAG Server

### 4.1 Python Async Web Servers [CRITICAL PATH]

**Topics:**
- ASGI vs WSGI: why async matters for I/O-bound LLM calls
- FastAPI: path operations, request/response models with Pydantic v2
- Pydantic: `BaseModel`, validators, `model_config`, serialization
- Uvicorn: event loop, worker processes, `--host 0.0.0.0` binding
- Lifespan events: `@asynccontextmanager` startup/shutdown for loading models
- Dependency injection in FastAPI: `Depends()`
- Error handling: `HTTPException`, custom exception handlers

**Connection to VideoGameWizard:**
- `server.py`: FastAPI app with `POST /chat` and `GET /health`
- ChromaDB and embedding model are loaded at startup
- Ollama is called via `requests` (sync — could be made async with `httpx`)

**Resources:**
- FastAPI official docs (excellent)
- Uvicorn docs
- Pydantic v2 docs

**Success Criteria:**
- Add a `GET /stats` endpoint that returns collection size, model name, and server uptime
- Migrate the Ollama call from `requests` to `httpx` with async

---

### 4.2 Embeddings & Vector Search [CRITICAL PATH]

**Topics:**
- Word embeddings → sentence embeddings: how all-MiniLM-L6-v2 produces 384-dim dense vectors
- Cosine similarity: why normalized dot product works for semantic similarity
- HNSW (Hierarchical Navigable Small World): the approximate nearest-neighbor algorithm ChromaDB uses
- ChromaDB internals: collections, metadata filtering, distance metrics (`cosine`, `l2`, `ip`)
- `sentence_transformers` API: `SentenceTransformer.encode()`, batch encoding, GPU acceleration
- Embedding truncation: all-MiniLM-L6-v2 has a 256-token limit — what happens to longer chunks

**Connection to VideoGameWizard:**
- `embed.py`: GPU batch encoding at `EMBED_BATCH_SIZE=2048`
- `server.py`: single query embedding → ChromaDB `collection.query()` → top-5 results
- 189,958 chunks indexed at 384 dimensions each

**Resources:**
- Sentence-Transformers docs + SBERT.net papers
- ChromaDB documentation
- HNSW paper (Malkov & Yashunin 2018) — read abstract + algorithm sections

**Success Criteria:**
- Explain why cosine similarity is preferred over L2 for text embeddings
- Experiment with `n_results=3` vs `n_results=10` and observe response quality difference

---

### 4.3 Text Chunking Strategies [CRITICAL PATH]

**Topics:**
- Why chunking is necessary: context window limits, retrieval precision
- Fixed-size vs paragraph-aligned chunking: trade-offs
- Overlap: why 150-char overlap prevents answer truncation at chunk boundaries
- Chunk size vs retrieval quality: smaller chunks = more precise retrieval but less context
- Stable chunk IDs: MD5 of `title::chunk_index` for deduplication
- Sentence boundary detection vs naive splitting

**Connection to VideoGameWizard:**
- `chunker.py`: paragraph-aligned, max 1000 chars, 150-char overlap, sentence fallback for long paragraphs
- 189,958 chunks from 17,825 articles (avg 10.7 chunks/article)

**Resources:**
- LangChain chunking docs (conceptual reference, not the library)
- _Building LLM-Powered Applications_ (Valentina Alto)

**Success Criteria:**
- Implement a sliding-window chunker with a different overlap strategy and compare retrieval quality

---

## Phase 5: Large Language Models

### 5.1 Transformer Architecture [CRITICAL PATH]

**Topics:**
- Attention mechanism: scaled dot-product attention, multi-head attention
- Positional encodings: sinusoidal vs rotary (RoPE, used in Llama)
- Decoder-only transformers: autoregressive generation
- KV cache: why it makes inference fast for long contexts
- Context window: tokens vs characters, how tokenization works (BPE)
- Temperature, top-p, top-k sampling: how they affect output diversity
- System prompts vs user messages vs assistant messages in chat format

**Connection to VideoGameWizard:**
- Llama 3.1 8B is a decoder-only transformer with RoPE positional encoding
- `server.py` builds a system prompt with retrieved chunks and passes it to Ollama
- History is passed as `HistoryMessage` list — each counts against the context window

**Resources:**
- _Attention Is All You Need_ (Vaswani et al. 2017) — the foundational paper
- Andrej Karpathy's "Let's build GPT from scratch" (YouTube)
- Llama 3 technical report (Meta)

**Success Criteria:**
- Explain why KV cache makes the second token faster than the first
- Calculate approximately how many tokens fit in Llama 3.1 8B's context window given the history format

---

### 5.2 Ollama & Local Inference [CRITICAL PATH]

**Topics:**
- Ollama architecture: model runner, REST API, model storage (`.ollama/models/`)
- GGUF format: quantized model weights, how Q4_K_M differs from Q8_0
- Quantization: INT4 vs INT8 vs FP16 — quality vs memory trade-offs
- Ollama API: `POST /api/chat`, `POST /api/generate`, streaming responses
- GPU memory management: VRAM usage for 8B model at different quantizations
- `Modelfile`: `FROM`, `SYSTEM`, `PARAMETER` directives

**Connection to VideoGameWizard:**
- Ollama serves `llama3.1:8b` on port 11434
- `server.py` calls `POST http://localhost:11434/api/chat`
- RTX 5070 Ti has 16GB VRAM — 8B at Q4_K_M fits easily (~5GB)

**Resources:**
- Ollama documentation (ollama.com/docs)
- GGUF format spec (llama.cpp GitHub)
- _The Quantization Guide_ (Hugging Face blog)

**Success Criteria:**
- Pull a different quantization of Llama 3.1 and compare generation speed vs quality
- Write a Modelfile with a custom system prompt baked in

---

### 5.3 RAG Architecture End-to-End [CRITICAL PATH]

**Topics:**
- RAG vs fine-tuning: when to use each, why not always fine-tune
- Retrieval pipeline: query embedding → ANN search → reranking → context assembly
- Prompt engineering for RAG: how to structure retrieved chunks in the system prompt
- Context stuffing: ordering chunks, handling irrelevant retrievals
- Hallucination: why RAG reduces (but doesn't eliminate) it
- Evaluation metrics: RAGAS (faithfulness, answer relevancy, context precision/recall)
- Advanced RAG: HyDE (hypothetical document embeddings), query rewriting, parent-child chunking

**Connection to VideoGameWizard:**
- `server.py`: top-5 chunks are concatenated into the system prompt
- The quality of the response depends entirely on retrieval quality

**Resources:**
- _RAG from Scratch_ (LangChain YouTube series)
- RAGAS paper (arxiv)
- Jerry Liu's _Building LLM Applications_ (LlamaIndex)

**Success Criteria:**
- Implement a reranking step using a cross-encoder model (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`)
- Add logging to measure retrieval quality: log top-5 chunk titles for each query

---

## Phase 6: Fine-Tuning

### 6.1 Transfer Learning & PEFT [CRITICAL PATH]

**Topics:**
- Pre-training vs fine-tuning vs RLHF: what each step does
- Full fine-tuning: why it requires as much VRAM as pre-training
- Parameter-Efficient Fine-Tuning (PEFT): only train a small adapter, freeze base weights
- LoRA (Low-Rank Adaptation): mathematical basis — decompose weight updates as `BA` where rank `r << d`
- QLoRA: quantize base model to 4-bit (NF4), keep adapter in fp16/bf16
- Rank `r` and alpha `α`: how they control adapter capacity
- Target modules: which layers to attach LoRA adapters to (q_proj, v_proj, k_proj, o_proj)

**Connection to VideoGameWizard:**
- QLoRA via Unsloth is the planned fine-tuning approach
- Base model: `llama3.1:8b` (already pulled in Ollama)
- WSL2 environment is set up with Unsloth installed

**Resources:**
- LoRA paper (Hu et al. 2021)
- QLoRA paper (Dettmers et al. 2023)
- Unsloth documentation (unsloth.ai)

**Success Criteria:**
- Explain why NF4 quantization preserves more information than INT4 for normally distributed weights

---

### 6.2 Training Data Preparation [CRITICAL PATH]

**Topics:**
- Instruction tuning format: `{"instruction": ..., "input": ..., "output": ...}` (Alpaca format)
- Chat format: `<|im_start|>system\n...<|im_end|>` (ChatML), `[INST]...[/INST]` (Llama 2)
- Llama 3 chat template: `<|begin_of_text|><|start_header_id|>...`
- Generating synthetic training data from `chunks.jsonl`
- Data quality vs quantity: why 1000 high-quality pairs beat 100k noisy ones
- Train/val split: stratified sampling, preventing data leakage
- `datasets` library: `Dataset.from_list()`, `map()`, tokenization

**Connection to VideoGameWizard:**
- Next step: convert `chunks.jsonl` (189,958 chunks) into instruction/response pairs
- Each chunk becomes training examples: Q&A pairs generated about that game/topic

**Resources:**
- HuggingFace `datasets` documentation
- Unsloth fine-tuning notebooks (GitHub)
- _Supervised Fine-tuning Trainer_ (TRL docs)

**Success Criteria:**
- Write a script that reads `chunks.jsonl` and outputs 10,000 instruction-response pairs in Llama 3 chat format

---

### 6.3 QLoRA Training with Unsloth [CRITICAL PATH]

**Topics:**
- `FastLanguageModel.from_pretrained()`: loading quantized base model
- `get_peft_model()`: attaching LoRA adapters
- `SFTTrainer` (TRL): supervised fine-tuning trainer, `TrainingArguments`
- Key hyperparameters: `learning_rate`, `num_train_epochs`, `per_device_train_batch_size`, `gradient_accumulation_steps`
- Gradient checkpointing: trades compute for VRAM
- `bf16` vs `fp16`: Blackwell (RTX 50 series) supports `bf16` natively
- Loss monitoring: training loss curve, overfitting detection

**Connection to VideoGameWizard:**
- RTX 5070 Ti (16GB VRAM) can run Llama 3.1 8B QLoRA with batch_size=2, gradient_accumulation=4
- WSL2 Ubuntu environment with `nvidia-smi` verified

**Resources:**
- Unsloth fine-tuning docs + official notebooks
- TRL `SFTTrainer` documentation
- _Fine-tuning LLMs_ (HuggingFace course)

**Success Criteria:**
- Run a 100-step training loop on a small subset and observe loss decreasing

---

### 6.4 GGUF Export & Ollama Integration [CRITICAL PATH]

**Topics:**
- Merging LoRA adapters back into base weights: `model.merge_and_unload()`
- Saving in GGUF format: `model.save_pretrained_gguf()` via Unsloth
- Quantization levels for GGUF: Q4_K_M (recommended), Q8_0 (higher quality, more VRAM)
- Ollama Modelfile: `FROM ./model.gguf`, `SYSTEM`, `PARAMETER`
- `ollama create` + `ollama run` with the new model

**Connection to VideoGameWizard:**
- Final step replaces `llama3.1:8b` in `server.py` with the fine-tuned model name
- No Android code changes needed — only the model name in `server.py` changes

**Resources:**
- Unsloth GGUF export docs
- Ollama Modelfile reference

**Success Criteria:**
- Export a fine-tuned model, create an Ollama model from it, and query it through the full stack (Android → RAG server → Ollama)

---

## Phase 7: Data Engineering

### 7.1 Web Scraping & APIs [OPTIONAL DEPTH]

**Topics:**
- HTTP vs headless browser scraping: when each is appropriate
- MediaWiki Action API: `action=query`, `prop=extracts`, `generator=categorymembers`
- Rate limiting: `time.sleep()` vs token bucket vs exponential backoff
- Pagination: `continue` tokens in MediaWiki API
- `robots.txt` and Terms of Service: legal/ethical constraints
- Data serialization: JSONL format, why it's preferred over JSON arrays for large datasets

**Connection to VideoGameWizard:**
- `wikipedia_fetcher.py`: MediaWiki API, `exlimit=1` constraint, category recursion
- `wikipedia_cleaner.py`: regex-based boilerplate removal, Unicode normalization

**Resources:**
- MediaWiki Action API docs
- _Web Scraping with Python_ (Ryan Mitchell)

---

### 7.2 Data Cleaning & NLP Preprocessing [OPTIONAL DEPTH]

**Topics:**
- Regex for structured text cleanup: template markers, citation brackets, section headers
- Unicode normalization: NFC vs NFD, replacement character `\ufffd`
- Whitespace normalization: `\n\n` paragraph boundaries, `\t`, non-breaking spaces
- Section filtering: removing References, See Also, External Links tail sections
- Quality filtering: minimum article length, stub detection

**Connection to VideoGameWizard:**
- `wikipedia_cleaner.py` removes MediaWiki template syntax, citation markers, boilerplate tail sections
- 18,019 raw → 17,825 clean articles after filtering

**Resources:**
- _Natural Language Processing with Python_ (NLTK book, free online)

---

## Phase 8: Infrastructure & DevOps

### 8.1 WSL2 & GPU Passthrough [OPTIONAL DEPTH]

**Topics:**
- WSL2 architecture: Hyper-V lightweight VM, virtio-gpu
- CUDA in WSL2: WDDM driver passthrough, `nvidia-smi` in WSL2
- PyTorch CUDA wheels: `cu118` vs `cu121` vs `cu128` — what the suffix means
- VENV management in WSL2: isolating Python environments
- File system performance: WSL2 `/home/` vs Windows `/mnt/c/` — always work in Linux FS

**Connection to VideoGameWizard:**
- WSL2 fine-tuning venv at `~/venv/finetune`
- PyTorch cu128 installed and `torch.cuda.is_available()` verified

---

### 8.2 Android Testing Infrastructure [OPTIONAL DEPTH]

**Topics:**
- Instrumented tests vs unit tests: what runs on device/emulator vs JVM
- `connectedAndroidTest` Gradle task
- `ComposeTestRule`: `onNodeWithText`, `onNodeWithContentDescription`, `performClick`
- `MockWebServer` (OkHttp): intercepting HTTP calls in instrumented tests
- Test sharding for CI speed

**Connection to VideoGameWizard:**
- `NavigationTest.kt` exists as an instrumented test
- No unit tests exist yet (identified gap)

---

## Learning Path Summary

```
Phase 0: Kotlin + JVM Basics
    ↓
Phase 1: Jetpack Compose (UI)
    ↓
Phase 2: Retrofit Networking
    ↓
Phase 3: MVVM Architecture
    ↓ (parallel tracks)
Phase 4: Python Backend ←→ Phase 5: LLMs & Ollama
    ↓
Phase 5.3: RAG End-to-End (requires both 4 and 5)
    ↓
Phase 6: Fine-Tuning (requires Phase 5)
    ↓ (optional)
Phase 7 & 8: Data Engineering + DevOps
```

## Immediate Next Actions (Priority Order)

1. **Fix Issue 7** (`LaunchedEffect` keyed on `lastId`) — 15 min, high impact
2. **Fix Issue 10** (add `@Immutable` to `ChatMessage` + `HomeUiState`) — 10 min
3. **Fix Issue 9** (WelcomeScreen button accessibility) — 20 min
4. **Fix Issue 8** (`BASE_URL` via `buildConfigField`) — 30 min
5. **Fix Issue 6** (extract strings to `strings.xml`) — 30 min
6. **Prepare fine-tuning data** (convert `chunks.jsonl` to instruction pairs) — Phase 6.2
