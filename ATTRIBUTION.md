# Attribution & Third-Party Licenses

This project combines original code with third-party data and models that carry their
own licenses. **The MIT license in [`LICENSE`](LICENSE) covers the original source code
of this repository only.** The data and models below are licensed separately, as noted.

---

## 1. Knowledge corpus — English Wikipedia (CC BY-SA 4.0)

The RAG knowledge base is built from **English Wikipedia** articles, retrieved via the
MediaWiki Action API (see `scraping/wikipedia/`).

- **Source:** <https://en.wikipedia.org>
- **License:** [Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/),
  also available under the [GNU Free Documentation License (GFDL)](https://www.gnu.org/licenses/fdl-1.3.html).
- **Per-article attribution:** each chunk retains its source article `title` and `url` in
  its metadata. Authorship/history for any article is available at its page history
  (e.g. `https://en.wikipedia.org/wiki/<Title>?action=history`).

CC BY-SA 4.0 is a **copyleft / share-alike** license with a **mandatory attribution**
requirement. The following artifacts are **derivative works of CC BY-SA 4.0 content** and
are therefore themselves distributed under **CC BY-SA 4.0**, *not* MIT:

| Artifact | Description |
|----------|-------------|
| `scraping/data/wikipedia_raw.jsonl`, `wikipedia_clean.jsonl` | Fetched / cleaned articles (gitignored) |
| `scraping/data/chunks.jsonl` | Chunked passages (gitignored) |
| `scraping/data/chromadb/` | The embedded vector index (gitignored) |
| `scraping/finetune/data/train.jsonl`, `val.jsonl` | Q→A pairs grounded verbatim in article passages (**committed**) |
| `scraping/rag/eval/data/eval_set.jsonl` | Synthetic eval questions tied to source chunks (**committed**) |

If you redistribute these files, you must (a) attribute Wikipedia, (b) link the
CC BY-SA 4.0 license, and (c) license your derivative under CC BY-SA 4.0.

> **Attribution in the app:** answers surface their source article titles (and, going
> forward, links) so end users can trace and verify the grounding — this also satisfies
> the CC BY-SA attribution clause at the point of use.

---

## 2. Models

| Model | Role | License |
|-------|------|---------|
| **Llama 3.1 8B Instruct** (Meta) | Base LLM served via Ollama; base for the `vgw-rag:8b` fine-tune | [Llama 3.1 Community License](https://www.llama.com/llama3_1/license/) — includes an Acceptable Use Policy and a naming/branding clause for distributed derivatives |
| **`vgw-rag:8b`** (this project) | QLoRA fine-tune of Llama 3.1 8B | Derivative of Llama 3.1 — subject to the Llama 3.1 Community License. The merged weights and adapter are **gitignored / not distributed** in this repo. |
| **`sentence-transformers/all-MiniLM-L6-v2`** | Query/document embeddings | Apache 2.0 |
| **`cross-encoder/ms-marco-MiniLM-L-6-v2`** | Reranking (eval harness) | Apache 2.0 |

> **Note on the Llama license:** the Llama 3.1 Community License requires distributed
> derivative models to include "Llama" at the start of their name and to ship the license +
> "Built with Llama" notice. The `vgw-rag:8b` fine-tune is **local-only and not
> distributed** here, so that clause is not triggered; if these weights are ever published,
> rename accordingly (e.g. `Llama-3.1-VGW-RAG-8B`) and include the Llama license.

---

## 3. Source-data decisions

For completeness (and recorded in `CLAUDE.md`), other sources were deliberately **excluded**
on licensing grounds: Reddit (bans AI-training use), Fandom wikis (CC BY-NC-SA — the
non-commercial clause conflicts with redistribution), and wiki.gg (limited coverage). Only
CC BY-SA Wikipedia content is used in the active pipeline.
