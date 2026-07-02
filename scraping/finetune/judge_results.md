# Fine-tune win-rate — 150 held-out questions

- **Base:** `llama3.1:8b`  ·  **Fine-tuned:** `vgw-rag:8b`
- **Judge:** `qwen2.5:7b`  ·  Deterministic (temp 0, seed 42)
- A/B order alternated per item to neutralise position bias.

| Metric | Value |
|--------|-------|
| Fine-tuned wins | 67 |
| Base wins | 49 |
| Ties | 34 |
| **FT win-rate (overall)** | **44.7%** |
| FT win-rate (excl. ties) | 57.8% |
