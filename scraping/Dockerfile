# Container image for the VideoGameWizard RAG server.
# Build context: the scraping/ directory.
#
#   docker build -t videogamewizard-rag scraping/
#
# The ChromaDB index is mounted at runtime (see docker-compose.yml) rather than
# baked in — build the pipeline first (chunker.py -> embed.py) to produce it.
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code.
COPY rag/ ./rag/

# Defaults (override at run time). The ChromaDB index and the embedding-model
# cache are expected on mounted volumes.
ENV VGW_CHROMA_PATH=/data/chromadb \
    HF_HOME=/models \
    PYTHONUNBUFFERED=1

EXPOSE 8000
WORKDIR /app/rag
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
