"""
Query pipeline: embed question -> retrieve from Qdrant.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from src.rag.embeddings.embedder import GeminiEmbedder, OllamaEmbedder, OpenAIEmbedder, SentenceTransformersEmbedder
from src.rag.integrations.qdrant_store import QdrantVectorStore
from src.utils.rag_config_loader import RAGConfig

logger = logging.getLogger(__name__)


def _build_clients(cfg: RAGConfig):
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
    return embedder, store


def retrieve_context(question: str, cfg: RAGConfig, *, top_k: int | None = None) -> List[Dict[str, Any]]:
    """
    Retrieve top-k chunks from Qdrant for a given question.
    """
    k = top_k or cfg.retrieval.top_k
    embedder, store = _build_clients(cfg)
    qv = embedder.embed_query(question)
    hits = store.search(query_vector=qv, limit=k)
    return hits
