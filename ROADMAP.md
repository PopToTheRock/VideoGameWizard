# VideoGameWizard — Portfolio Roadmap

This document tracks the work to bring VideoGameWizard from a working prototype to a
portfolio-grade project that credibly demonstrates **mobile**, **ML**, and **backend**
engineering at a high bar.

**The pitch we are building toward:**

> A full-stack, fully-local AI assistant: an Android (Jetpack Compose) chat app backed by a
> self-hosted RAG pipeline over ~190k Wikipedia chunks and a QLoRA-fine-tuned Llama 3.1 8B —
> no cloud APIs, runs entirely on consumer hardware.

Legend: ✅ done · 🚧 in progress · ⬜ not started

---

## Milestone 1 — First impressions & quick wins
*Goal: a stranger landing on the repo immediately gets it and respects it.*

- 🚧 **README.md** — hero, demo media, architecture diagram, feature list, quick start
- ✅ **LICENSE** (MIT)
- ✅ **Rebrand package** `com.example.videogamewizard` → `dev.alexn.videogamewizard`
- ✅ **Code-review fixes** (from `CLAUDE.md`):
  - ✅ Issue 6 — externalize UI strings to `strings.xml`
  - ✅ Issue 7 — `LaunchedEffect` keyed on last-message id + typing state (not `size`)
  - ✅ Issue 8 — `BASE_URL` via `buildConfigField`
  - ✅ Issue 9 — WelcomeScreen button respects font scaling
  - ✅ Issue 10 — `@Immutable` on `ChatMessage` and `HomeUiState`
- ⬜ **Commit hygiene** going forward (Conventional Commits). Decision: keep existing history, write clean commits from here.

## Milestone 2 — Engineering rigor: tests + CI + linting
*Goal: green checkmarks and a visible testing discipline.*

- ⬜ **Android unit tests** (JUnit + MockK + Turbine + coroutines-test): `HomeViewModel`
  (success / network-error / timeout / cancellation / validation / concurrent-send guard),
  `ChatRepository` (mapping, `Result`, cancellation), error-message classifier
- ⬜ **Python tests** (pytest): chunker pure functions + edge cases, cleaner regex,
  fetcher helpers, FastAPI endpoints with mocked Ollama + ChromaDB
- ⬜ **GitHub Actions CI**: Android build + test + lint; Python lint + test; coverage badge
- ⬜ **Linting/formatting**: Spotless + ktlint and detekt (Kotlin); ruff + black (Python);
  `.editorconfig`
- ⬜ **`requirements.txt` / `pyproject.toml`** with pinned versions

## Milestone 3 — Backend hardening
*Goal: `server.py` goes from "demo script" to "service".*

- ⬜ Refactor `server.py`: async `httpx` for Ollama, `lifespan` context manager,
  Pydantic `BaseSettings` (env-driven config), input validation, CORS, rate limiting,
  structured logging + request IDs, retry on transient failures, `/stats` endpoint,
  graceful zero-retrieval handling
- ⬜ **OpenAPI/Swagger** docs surfaced and documented
- ⬜ **Dockerize** the RAG server (`Dockerfile` + `docker-compose`)
- ⬜ **Hilt** dependency injection in the Android app
- ⬜ **Room** local chat-history persistence (history survives app restart)

## Milestone 4 — ML depth: evaluation + QLoRA fine-tuning *(the headline)*
*Goal: prove you can measure and improve a model, not just wire one up.*

- ⬜ **RAG evaluation harness**: Q&A eval set; retrieval hit-rate / MRR; cross-encoder
  reranking with before/after metrics; optional RAGAS (faithfulness, answer-relevancy)
- ⬜ **Fine-tuning data prep**: `chunks.jsonl` → instruction/response pairs in Llama-3 chat
  format; train/val split
- ⬜ **QLoRA training**: Unsloth + `SFTTrainer` in WSL2 (bf16 on RTX 5070 Ti); capture loss curve
- ⬜ **GGUF export**: merge adapter → GGUF → Ollama `Modelfile` → swap model in `server.py`
- ⬜ **Model card**: training config, loss curve, base-vs-fine-tuned outputs, eval delta

## Milestone 5 — Presentation & polish
*Goal: make it effortless to be impressed.*

- ⬜ **Polished demo video** + screenshots embedded in README
- ⬜ **`docs/ARCHITECTURE.md`** technical deep-dive (user-facing version of `CLAUDE.md`)
- ⬜ **`CHANGELOG.md`**, badges (CI, license, coverage), final repo metadata pass

---

## Suggested sequencing
- **M1 + M2** deliver ~80% of the recruiter-facing payoff — do them first.
- **M3 + M4** can proceed in parallel (different code paths).
- Rough shape: **Week 1** M1 + start M2 · **Week 2** finish M2 + M3 · **Weeks 3–4** M4 + M5.
