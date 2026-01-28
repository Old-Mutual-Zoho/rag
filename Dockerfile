# Slim image for Railway (target < 4 GB). Uses requirements-prod.txt only.
# Set embeddings.provider to "gemini" or "openai" in config; do not use sentence_transformers.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime deps only (no torch, sentence-transformers, spacy, etc.)
COPY requirements-prod.txt .
RUN pip install --upgrade pip && pip install -r requirements-prod.txt

COPY src/ ./src/
COPY config/ ./config/

EXPOSE 8000
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
