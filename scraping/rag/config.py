"""
RAG pipeline configuration.
"""

# Input: cleaned Wikipedia articles
INPUT_FILE = "scraping/data/wikipedia_clean.jsonl"

# Output: chunked passages ready for embedding
CHUNKS_FILE = "scraping/data/chunks.jsonl"

# Token limit of the embedding model (sentence-transformers/all-MiniLM-L6-v2).
# Anything beyond this is silently truncated by the model at embed time, so the
# chunker must keep chunks under it. embed.py sets this on the model explicitly
# and audits how many chunks would still overflow.
EMBED_MAX_TOKENS = 256

# Maximum characters per chunk. The embedder counts *tokens*, not chars; English
# Wikipedia prose runs ~3.5–4.2 chars/token, so 850 chars maps to roughly
# 200–245 tokens — comfortably under EMBED_MAX_TOKENS, unlike the old 1000 (which
# sat right at the 256-token edge and, combined with an overlap bug, overshot it).
# chunk_article guarantees no emitted chunk exceeds this length.
MAX_CHUNK_CHARS = 850

# Overlap between consecutive chunks, in characters. Carried as a trailing-text
# budget (not whole paragraphs), so it can never push a chunk over MAX_CHUNK_CHARS.
CHUNK_OVERLAP_CHARS = 130

# Minimum chunk size — discard anything shorter than this
MIN_CHUNK_CHARS = 100
