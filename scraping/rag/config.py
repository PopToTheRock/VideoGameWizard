"""
RAG pipeline configuration.
"""

# Input: cleaned Wikipedia articles
INPUT_FILE = "scraping/data/wikipedia_clean.jsonl"

# Output: chunked passages ready for embedding
CHUNKS_FILE = "scraping/data/chunks.jsonl"

# Maximum characters per chunk.
# ~1000 chars ≈ 250 tokens — safely within the 256-token limit of
# sentence-transformers/all-MiniLM-L6-v2 (our embedding model).
MAX_CHUNK_CHARS = 1000

# Overlap between consecutive chunks in characters.
# Including the tail of the previous chunk helps preserve context
# across chunk boundaries during retrieval.
CHUNK_OVERLAP_CHARS = 150

# Minimum chunk size — discard anything shorter than this
MIN_CHUNK_CHARS = 100
