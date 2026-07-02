# Container image for the VideoGameWizard RAG server.
# Build context: the scraping/ directory.
#
#   docker build -t videogamewizard-rag scraping/
#
# The ChromaDB index is mounted at runtime (see docker-compose.yml) rather than
# baked in — build the pipeline first (chunker.py -> embed.py) to produce it.
FROM python:3.14-slim

WORKDIR /app

# Install pinned runtime dependencies (first, for better layer caching). The
# lock is compiled for Linux/py3.12 and pins the CPU-only torch wheel (+cpu) —
# a plain `pip install torch` on Linux would pull the CUDA build plus ~5-7 GB
# of nvidia-* wheels a GPU-less container can never use. Regenerate with the
# pip-compile command in the lock's header. Source of intent (floors):
# requirements-server.txt.
COPY requirements-server.lock .
RUN pip install --no-cache-dir -r requirements-server.lock

# Application code.
COPY rag/ ./rag/

# Run as a non-root user. /models must exist and be owned by it so the named
# volume (hf-cache) inherits writable ownership on first creation.
RUN useradd --create-home appuser \
    && mkdir -p /models \
    && chown appuser /models

# Defaults (override at run time). The ChromaDB index and the embedding-model
# cache are expected on mounted volumes.
ENV VGW_CHROMA_PATH=/data/chromadb \
    HF_HOME=/models \
    PYTHONUNBUFFERED=1

EXPOSE 8000
WORKDIR /app/rag
USER appuser

# The server ships a purpose-built GET /health; generous start period because
# lifespan loads the embedding model (a download on first run).
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"]

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
