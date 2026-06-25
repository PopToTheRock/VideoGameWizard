# VideoGameWizard — Professional Code Audit (Google-bar review)

**Date:** 2026-06-25 · **Method:** 16-dimension multi-agent audit, every finding adversarially verified against source, plus a completeness critic. 109 agents, 794 tool calls.
**Result:** 92 candidate issues → **91 verified, 1 refuted** → **8 high, 30 medium, 44 low, 16 nit. Zero critical.**

---

## Verdict

This is genuinely strong, senior-level work. Clean MVVM, correct coroutine/cancellation handling, a real RAG + eval + QLoRA pipeline, CI on both stacks, no committed secrets or model weights. There is **no critical bug and no crash/data-loss defect anywhere in the codebase.**

What separates it from a top-bar portfolio piece is a small number of things:

1. **One real correctness bug chain in the RAG core** (chunker overshoots its size cap → ~69% of chunks are silently truncated at embed time). This invisibly degrades the headline feature and the eval harness structurally can't see it. *This is the single most important fix.*
2. **A stream-robustness bug** (a malformed line from Ollama crashes the streaming endpoint instead of reporting in-band).
3. **The marquee feature is invisible** — sources are retrieved, streamed, decoded… then thrown away. The app looks like a thin LLM wrapper.
4. **Release/security hardening gaps** — R8 disabled on "release", no auth on a 0.0.0.0-bound server, cleartext permitted globally, CC BY-SA attribution missing.
5. **The fine-tune's value is asserted, not measured** — only val loss vs. the teacher, no downstream task metric.

Grade: **strong B+/A−.** Fix the items in "Fix First" and the headline claims become defensible end-to-end.

---

## Fix First (the handful that actually matter)

| # | Issue | Why it matters | Effort |
|---|-------|----------------|--------|
| H6+H7 | Chunker exceeds 1000-char cap (74% over, mean 1300, max 3766) → ~69% of chunks truncated at MiniLM's 256-token limit | Core retrieval quality silently degraded; eval can't detect it | 0.5–1 day (+ re-embed) |
| H8 | Malformed NDJSON line crashes the streaming endpoint | Breaks the one path the app uses; violates documented in-band-error contract | 1 hr |
| H4 | Source citations captured then discarded (`is Sources -> Unit`) | The "grounded RAG / anti-hallucination" story is invisible | 0.5 day |
| H1 | Release build ships `isMinifyEnabled = false` | "Release" build = debug minus debuggable; needs keep-rules for kotlinx-serialization | 0.5 day |
| H3 | No auth/rate-limit on a 0.0.0.0-bound inference server | LAN resource abuse + unbounded `/feedback` disk writes | 0.5 day |
| H2 | CC BY-SA corpus shipped under MIT with no attribution | Licensing-compliance + credibility | 1 hr |
| H5 | Fine-tune "helps" never shown with a downstream metric | Headline ML milestone lacks a number | 1 day |

---

## HIGH (8)

**H1 — Release build ships with R8 disabled.** `app/build.gradle.kts:49-56` sets `isMinifyEnabled = false`: no shrink, no resource-shrink, no obfuscation. Flip to `true` + `isShrinkResources = true`, **but not as a one-liner** — R8 will strip the kotlinx-serialization `@Serializable` models (`RagModels.kt`) and Retrofit interface; add keep rules and then *actually run a release build and exercise a chat round-trip*. `proguard-rules.pro` is currently empty.

**H2 — CC BY-SA corpus under an MIT banner, no attribution.** Repo declares MIT; the corpus + `train.jsonl`/`val.jsonl`/`eval_set.jsonl`/ChromaDB are derivatives of Wikipedia (CC BY-SA 4.0, share-alike + attribution). Add a `NOTICE`/`ATTRIBUTION.md`, clarify in README/LICENSE that **MIT covers code only, data is CC BY-SA**, and surface per-answer attribution (title + URL — already in chunk metadata). Pairs with H4.

**H3 — No auth/rate-limit on a 0.0.0.0 server.** `server.py:409-420` wires CORS but no auth dependency, no rate limiter, while docs say run `--host 0.0.0.0`. CORS does *not* help (the client and curl aren't browsers). Fix: default the documented command to `127.0.0.1`, require an explicit `VGW_BIND_HOST` to expose; for the physical-device path add a shared-secret header dependency + a small per-IP token bucket. Calibrated *high, not critical* (LAN-local, no secrets behind it).

**H4 — Source citations silently discarded.** `server.py:311` emits `{"type":"sources"}`; `ChatRepository.kt:57` decodes it; `HomeViewModel.kt:104` drops it: `is ChatStreamEvent.Sources -> Unit  // not yet rendered`. The 190k-chunk index produces zero visible payoff. Fix: persist sources on the message (a `sources` JSON column + Room migration, or side table) and render tappable chips under each AI reply. Also un-hardcodes `emptyList()` feedback sources at `HomeViewModel.kt:176`. ROADMAP's own #1 deferred item.

**H5 — Fine-tune value never measured downstream.** Every "result" is either held-out val loss (0.161 — but labels were authored *by the base model*, so it's self-distillation) or an anecdotal qualitative table. No win-rate, no faithfulness/grounding score, no re-run of `eval/` with `vgw-rag:8b`. The README is honest (labels it "Qualitative", has an "Honest limitations" section) — the defect is *missing evidence*, not dishonesty. Fix: a fixed-seed, temp-0 LLM-judge over the val set reporting a base-vs-FT win-rate on grounding+conciseness (reuses `compare_models.py` plumbing).

**H6 — Chunker doesn't cap chunk size.** `chunker.py:91-108`: the size check runs *before* appending, and the overlap rebuild walks back **whole paragraphs** (each up to 1000 chars), so a chunk can hit ~2× the limit. Empirically **148,117 / 199,184 chunks (74%) exceed 1000 chars** (mean 1300, p95 1916, max 3766). The docstring + CLAUDE.md both promise "max 1000 chars" — a contract violation. Fix: cap overlap by *character budget* (trailing substring snapped to a word boundary of the emitted text), re-check size after each append, split if still over, and assert no chunk exceeds the cap. Note: re-chunking changes the MD5 IDs → full re-embed + regenerate `eval_set.jsonl`.

**H7 — ~69% of chunks truncated at the embedder's 256-token limit.** `all-MiniLM-L6-v2` defaults to `max_seq_length=256`; nothing in `embed.py`/`server.py`/`eval/retriever.py` overrides it (zero `max_seq_length` hits). With H6's oversized chunks, **68.9% of a 3000-chunk sample exceeds 256 tokens** (median 317, max 483) — the tail of most chunks is never embedded yet is still handed to the LLM as "context." The config comment "1000 chars is safely within 256 tokens" is doubly wrong (chunks aren't capped *and* 1000 chars ≈ 250 tokens). The eval can't expose this — it retrieves against the same degraded vectors. Fix: chunk to ~230 real tokens, or switch to a 512-token model (bge-base/gte) and set `model.max_seq_length` explicitly. (Verifier note: the query-side citations are harmless — queries are short; the harm is index-side only.)

**H8 — Malformed NDJSON crashes the server stream loop.** `server.py:321-329`: `json.loads(line)` sits inside a `try` that only catches `httpx.HTTPError`. A non-JSON/truncated line (proxy hiccup, version skew) raises `JSONDecodeError` out of the async generator, breaking the `StreamingResponse` mid-flight instead of emitting the documented `{"type":"error"}`. No test feeds a malformed line. Fix: catch `JSONDecodeError`/`ValueError` around the per-line parse, emit an error event, return; add a `stream_lines=["not json"]` test asserting `events[-1]["type"] == "error"`.

---

## MEDIUM (30) — grouped

**RAG / ML correctness & rigor**
- Eval headline advertises cross-encoder reranking (0.60→0.75) the **production server never runs** — `server.retrieve_context()` does a bare top-5 query. Wire it in, or relabel as offline-only. (`server.py:159`, `README.md:149`)
- **Content-independent positional chunk IDs** (`md5(title::index)`) + `embed.py` "last occurrence wins" → two chunks sharing (title, index) silently collapse, content can differ from the ID. Hash the content too. (`chunker.py:117`)
- **Shared embedder + ChromaDB collection mutated concurrently** via the 40-thread anyio pool with no thread-safety guarantee; concurrent CUDA forward passes can race. Serialize behind a lock / single-thread executor, or cap the pool. (`server.py:170`)
- **Synthetic gold set is optimistically circular** — the model authors each question from the chunk it must retrieve, told to "name the subject explicitly." Inflates absolute numbers (rerank *lift* is robust). Disclose in README; add a held-out judge / paraphrase pass / small hand-curated anchor set. (`generate_eval_set.py:41`)
- **Open RAGAS / generation-quality loop** — the "measure→improve→re-measure" story is closed for retrieval, open for the headline fine-tune. Add faithfulness + answer-relevancy deltas (base vs vgw-rag). (`finetune/README.md:60`)
- **Model-card train/val claim is apples-to-oranges** — compares epoch-*mean* train loss (0.192) to converged val (0.161); converged train (~0.14) is actually *below* val (normal). Keep the monotonic-val-descent claim; drop/soften the "val below train = masking" sentence. (`finetune/README.md:49`)

**Backend hardening**
- **Unbounded conversation history** — `ChatRequest.history` has no `max_length`, `HistoryMessage.content` no `max_length` (only the current `message` is capped). Blows the model context window as a session grows / via a crafted request. Cap both + truncate to last-N turns server-side. (`server.py:94`)
- **RAG server binds 0.0.0.0 with no auth** (dup of H3 from the security lens). (`server.py:12`)
- **No prompt-injection defenses** around retrieved Wikipedia content + user history concatenated into the prompt. (`server.py:185`)

**Android**
- **In-band server errors mislabeled** "Couldn't reach the server" — the server *was* reached; it discards `event.message`. Add a `StreamServerException` (not an IOException subtype) + a dedicated branch *before* the IOException branch. (`ChatRepository.kt:59`)
- **One malformed NDJSON line aborts the whole client stream** — wrap `decodeFromString` in try/`continue` on `SerializationException`. (`ChatRepository.kt:55`)
- **Hardcoded `Color.White`/`Purple40` fight `dynamicColor = true`** → possible WCAG contrast failures on Android 12+. Use `onPrimary`/`primaryContainer`/`onPrimaryContainer`; drive Scaffold color from the theme. (`HomeScreen.kt:123-127, 262-263`)
- **Feedback toggle state invisible to TalkBack** — selected state never in the semantics tree. Add `Modifier.semantics { selected = … }` or `toggleable` + role. (`MessageFeedback.kt:34`)
- **Room/DAO layer has zero tests** — `toDomain()` author fallback, ordering, schema all unverified; no `room-testing` dep. Add an in-memory DAO test (+ later a `MigrationTestHelper`). (`RoomChatHistoryRepository.kt:11`, dup at `ChatDao.kt:1`)
- **Cleartext HTTP permitted globally** (all build types) instead of scoped to the dev host. Move a scoped `domain-config` (incl. the LAN subnet) to `src/debug/`. (`network_security_config.xml:8`)

**CI / build / DevOps**
- **Python deps float on `>=`, no lockfile** → non-reproducible CI/Docker, no hash defense. Generate a hashed `requirements-server.lock` (uv/pip-compile), install with `--require-hashes`. (Caveat: the CPU-torch index split needs care.)
- **GitHub Actions pinned to mutable tags**, not SHAs (tj-actions-class supply-chain). Dependabot already configured → pin to SHA with a version comment. (`android-ci.yml:22…`)
- **Dependabot misses pip + Docker** ecosystems. Add both. (`dependabot.yml:1`)
- **Dockerfile runs as root, unpinned base, no HEALTHCHECK** (and `/health` already exists). Add `USER`, pin by digest, add HEALTHCHECK + a compose healthcheck gate on Ollama. (`Dockerfile:8`)
- **CI lint/test gate covers only `rag/`** — `finetune/`, `wikipedia/`, `wikigg/`, `wikis/` are structurally outside every check. Point ruff/pytest at the whole `scraping/` tree. (`android-ci.yml:83`)

**Scraping**
- **Placeholder `your@email.com` User-Agent** violates Wikimedia UA policy (live Wikipedia path). Use the repo URL via env var; don't commit PII. (`wikipedia/config.py:6`)
- **No retry/backoff or `maxlag`** on the ~18k-request crawl → transient 429/503 silently drops articles. (`wikipedia_fetcher.py:57`)
- **Append-only output, no dedup/checkpoint** → re-running duplicates every article (masked later by embed-time dedup). Truncate `w` or track written page_ids. (`wikipedia_fetcher.py:200`)
- **`wikigg/` + `wikis/` are committed dead code** contradicting the "Final Decisions" table (Fandom/wiki.gg skipped). Remove, or add a README marking them experimental + why (licensing). (`wikigg_fetcher.py:1`)
- **Boilerplate truncation cuts at the FIRST matching heading** ("Notes"/"Sources" can appear mid-article) → silent content loss. Take the *last* match or require it in the final ~30%; narrow the set. (`wikipedia_cleaner.py:56`)

**Product (each ~0.5–2 days, high portfolio signal)**
- **No demo media** — README literally says "Demo video and screenshots coming soon." Highest-ROI item: a 20s GIF of streaming + citations. (`README.md:31`)
- **Single hard-coded conversation** — no multiple chats / search / export. A `Conversation` entity + drawer + list-detail nav is exactly the mobile signal reviewers want. (`ChatMessageEntity.kt:10`)
- **No retry/regenerate, no connection awareness** — a failed answer is a dead-end text bubble; the most likely failure (server not running) has no retry affordance and no `/health` indicator. (`HomeViewModel.kt:125`)
- **No observability/rate-limiting** — request-id middleware, per-request latency/token logging, a `/metrics` endpoint (prometheus-fastapi-instrumentator) convert "is this just a script?" into a strength. (`server.py:409`)

---

## LOW (44) — themes (full list in the workflow output)

- **Android arch:** no `SavedStateHandle` for draft/feedback across process death; `SharingStarted.Eagerly` vs `WhileSubscribed`.
- **Persistence:** chat table grows unbounded + full reload per change; `createdAt` written but never used for ordering.
- **Android security:** no signing config (release can't be distributed); `allowBackup=true` with unedited IDE backup/data-extraction templates (chat history backed to cloud); `BASE_URL` hardcoded for all build types.
- **CI:** no CodeQL/SAST or dependency-review; pip not cached; Gradle wrapper not checksum-pinned; CI never builds a release artifact or runs instrumented tests; compose mounts the index RW despite a "read-only" comment + floating image tags.
- **Compose:** O(n) per-item scan in the LazyColumn item lambda; WelcomeScreen theme-blind colors; zero `@Preview`.
- **Server:** `/feedback` unbounded + arbitrary content; context/history concatenated with no injection guard.
- **Python:** swallowed broad except on ChromaDB reset; untyped dict/list generics; duplicated config constants; dead `BATCH_SIZE`; eval writes empty file before checking row count.
- **ML:** "0 overlap verified" describes chunk-level not full independence; `compare_models.py` non-deterministic single-sample; duplicate chunk IDs incl. one exact-duplicate training example; n=150 reported with no confidence intervals (some deltas within noise).
- **Scraping:** API error logged then KeyError drops article; naive title→URL breaks some provenance; attribution URL never surfaced.
- **Testing:** NDJSON parser malformed-line path untested; eval/finetune scripts untested; instrumented tests never run in CI.

## NIT (16) — quick wins
Duplicated `Json{}` config across two files · public `RATING_UP/DOWN` constants + raw-String rating (should be a typed enum/sealed) · `isResponding` duplicated in two state classes · `clearChat` doesn't reset feedback map · full user queries logged at INFO (PII) · `datetime.UTC` vs `timezone.utc` inconsistency · print vs logging · CORS allows all methods/headers · Gradle build/config cache disabled · non-atomic greeting seed.

---

## One refuted finding (verification working)
A finder claimed the chunk-ID scheme "silently drops ~9,200 chunks (mislabeled as dedup)" at **high**. The verifier confirmed the counts (199,184 → 189,958 unique, 9,226 dropped) but **refuted the framing**: those are legitimate duplicate chunks, not lost distinct content. The *real* underlying issue (content-independent IDs) survived separately at **medium (#18)** — so the concern is captured, just correctly severity-rated.

---

## Suggested sequencing

**Week 1 — correctness & the headline (makes the claims true):**
1. Fix the chunker size cap (H6) → re-embed → regenerate eval set (H7). *Then re-run `eval/` and update the README with honest numbers.*
2. Render source citations + persist on message (H4) — unlocks the demo and richer feedback.
3. NDJSON robustness on both server (H8) and client (M).
4. Add the licensing NOTICE + surface attribution (H2).

**Week 2 — release & ML credibility:**
5. Enable R8 with keep-rules + verify a release round-trip; add a signing config (H1).
6. Auth/bind hardening + history caps + scoped cleartext (H3 + M).
7. LLM-judge base-vs-FT win-rate; close the RAGAS loop (H5 + M).
8. Record the demo GIF (M).

**Week 3 — depth & polish:**
9. Multi-conversation + search + export; retry/regenerate + `/health` indicator.
10. Observability (`/metrics`, request-ids, latency logging).
11. CI: broaden lint/test to all of `scraping/`, pin Action SHAs, add lockfile + Dependabot pip/docker, Dockerfile non-root, add a Room DAO test.
12. Sweep the nits (typed rating enum, dedup `Json{}`, stop logging full queries, etc.).
