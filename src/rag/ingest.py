"""
Ingestion pipeline: from processed chunks JSONL -> embeddings -> Qdrant.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable, Optional

from src.rag.embeddings.embedder import GeminiEmbedder, OllamaEmbedder, OpenAIEmbedder, SentenceTransformersEmbedder
from src.rag.integrations.qdrant_store import QdrantVectorStore
from src.utils.rag_config_loader import RAGConfig

logger = logging.getLogger(__name__)


def _iter_jsonl(path: Path) -> Iterable[dict]:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def ingest_chunks_to_qdrant(chunks_file: Path, cfg: RAGConfig, *, limit: Optional[int] = None) -> int:
    """
    Read chunks JSONL, embed texts, and upsert into Qdrant.

    Returns number of chunks ingested.
    """
    if cfg.embeddings.backend == "openai":
        embedder = OpenAIEmbedder(model=cfg.embeddings.model)
    elif cfg.embeddings.backend == "gemini":
        embedder = GeminiEmbedder(model=cfg.embeddings.model, api_key_env=cfg.embeddings.api_key_env)
    elif cfg.embeddings.backend == "ollama":
        embedder = OllamaEmbedder(model=cfg.embeddings.model, base_url=cfg.embeddings.base_url)
    else:
        embedder = SentenceTransformersEmbedder(model_name=cfg.embeddings.model)

    if cfg.vector_store.provider == "qdrant_http":
        store = QdrantVectorStore.from_http(
            collection=cfg.vector_store.collection,
            host=cfg.vector_store.host,
            port=cfg.vector_store.port,
        )
    else:
        store = QdrantVectorStore.from_local_path(
            collection=cfg.vector_store.collection,
            path=cfg.vector_store.path,
        )

    batch_texts: list[str] = []
    batch_ids: list[str] = []
    batch_payloads: list[dict] = []
    total = 0

    def flush() -> None:
        nonlocal batch_texts, batch_ids, batch_payloads
        if not batch_texts:
            return
        vectors = embedder.embed_texts(batch_texts)
        if not vectors:
            batch_texts.clear()
            batch_ids.clear()
            batch_payloads.clear()
            return
        # Ensure Qdrant collection exists once we know embedding dimension
        store.ensure_collection(vector_size=len(vectors[0]))
        store.upsert(ids=batch_ids, vectors=vectors, payloads=batch_payloads)
        batch_texts.clear()
        batch_ids.clear()
        batch_payloads.clear()

    for obj in _iter_jsonl(chunks_file):
        chunk_id = obj.get("id")
        text = obj.get("text", "")
        if not chunk_id or not text:
            continue

        payload = {
            "text": text,
            "doc_id": obj.get("doc_id"),
            "type": obj.get("type"),
            "chunk_type": obj.get("chunk_type"),
            "url": obj.get("url"),
            "title": obj.get("title"),
            "category": obj.get("category"),
            "subcategory": obj.get("subcategory"),
            "section_heading": obj.get("section_heading"),
        }

        batch_ids.append(str(chunk_id))
        batch_texts.append(text)
        batch_payloads.append(payload)
        total += 1

        if limit and total >= limit:
            break
        if len(batch_texts) >= cfg.embeddings.batch_size:
            flush()

    flush()
    logger.info("Embedded and stored %s chunks into Qdrant collection '%s'", total, cfg.vector_store.collection)
    return total
