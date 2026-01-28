"""
RAG retrieval: embed query, run vector search (and optional hybrid), return hits.
Supports pgvector and Qdrant via config.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.utils.rag_config_loader import RAGConfig, load_rag_config

logger = logging.getLogger(__name__)

# Minimum length for a "term" when re-ranking by overlap (skip "a", "is", etc.)
_MIN_TERM_LEN = 2


def _rerank_by_term_overlap(hits: List[Dict[str, Any]], search_query: str) -> None:
    """Sort hits in place: prefer chunks whose title/text/doc_id contain more query terms."""
    if not hits or not search_query.strip():
        return
    terms = {t.lower() for t in search_query.split() if len(t) >= _MIN_TERM_LEN}

    def overlap_score(h: Dict[str, Any]) -> float:
        p = h.get("payload") or {}
        combined = " ".join(
            str(p.get(k, "")) for k in ("title", "text", "doc_id", "section_heading")
        ).lower()
        return sum(1 for t in terms if t in combined)

    def sort_key(h: Dict[str, Any]) -> tuple:
        ov = overlap_score(h)
        sc = float(h.get("score") or 0)
        return (-ov, -sc)

    hits.sort(key=sort_key)


def _embedder_from_config(cfg: RAGConfig):
    from src.rag.embeddings.embedder import (
        GeminiEmbedder,
        OllamaEmbedder,
        OpenAIEmbedder,
        SentenceTransformersEmbedder,
    )

    p = cfg.embeddings.provider.lower()
    if p == "sentence_transformers":
        return SentenceTransformersEmbedder(model_name=cfg.embeddings.model)
    if p == "openai":
        return OpenAIEmbedder(model=cfg.embeddings.model)
    if p == "gemini":
        return GeminiEmbedder(model=cfg.embeddings.model, api_key_env=cfg.embeddings.api_key_env)
    if p == "ollama":
        return OllamaEmbedder(model=cfg.embeddings.model, base_url=cfg.embeddings.base_url or "http://localhost:11434")
    raise ValueError(f"Unknown embeddings provider: {cfg.embeddings.provider}")


def _vector_store_from_config(cfg: RAGConfig):
    from src.rag.integrations.pgvector_store import PgVectorStore
    from src.rag.integrations.qdrant_store import QdrantVectorStore

    p = cfg.vector_store.provider.lower()
    coll = cfg.vector_store.collection or "old_mutual_chunks"
    if p == "pgvector":
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError("DATABASE_URL is required when vector_store.provider is pgvector")
        return PgVectorStore(table_name=coll, connection_string=url)
    if p in ("qdrant_local", "qdrant_http"):
        path = (cfg.vector_store.path or "data/qdrant") if p == "qdrant_local" else None
        host = cfg.vector_store.host or "localhost"
        port = cfg.vector_store.port or 6333
        if path:
            return QdrantVectorStore.from_local_path(collection=coll, path=path)
        return QdrantVectorStore.from_http(collection=coll, host=host, port=port)
    raise ValueError(f"Unknown vector_store.provider: {cfg.vector_store.provider}")


def retrieve_context(
    question: str,
    cfg: RAGConfig,
    *,
    top_k: int = 5,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Embed the question, run vector search, optionally merge with BM25 (hybrid), return hits.
    Each hit is {"id", "score", "payload"}.
    Expands the query with synonym/keyword mappings so e.g. "Somesa Plan" also matches
    "Somesa Education Plan" / "SOMESA Plus" in the index.
    """
    from src.utils.synonym_expander import SynonymExpander

    expander = SynonymExpander()
    search_query = expander.expand_query(question)

    embedder = _embedder_from_config(cfg)
    store = _vector_store_from_config(cfg)

    store_class = type(store).__name__
    if store_class == "PgVectorStore" and hasattr(store, "ensure_table"):
        store.ensure_table(embedder.dim)

    # Fetch extra candidates so we can re-rank by product-term overlap (e.g. "Somesa" in chunk)
    fetch_k = min(top_k * 2, 20)
    qvec = embedder.embed_query(search_query)
    if store_class == "PgVectorStore":
        hits = store.search(query_vector=qvec, limit=fetch_k, filters=filters)
    elif store_class == "QdrantVectorStore":
        kw: Dict[str, Any] = {"query_vector": qvec, "limit": fetch_k}
        if filters:
            from qdrant_client.http import models as qm

            conditions = [qm.FieldCondition(key=k, match=qm.MatchValue(value=v)) for k, v in filters.items() if v is not None]
            if conditions:
                kw["filter"] = qm.Filter(must=conditions)
        hits = store.search(**kw)
    else:
        hits = store.search(query_vector=qvec, limit=fetch_k, filters=filters or {})

    if cfg.retrieval.hybrid.enabled:
        from src.rag.keyword_search import BM25KeywordSearch

        bm25 = BM25KeywordSearch()
        if bm25.load_index():
            bm25_hits = bm25.search(query=search_query, top_k=fetch_k, filters=filters)
            seen = {h["id"] for h in hits}
            for h in bm25_hits:
                if h["id"] not in seen and len(hits) < fetch_k:
                    hits.append(h)
                    seen.add(h["id"])
            hits = hits[:fetch_k]

    # Re-rank: prefer chunks that contain query/product terms (e.g. "Somesa" in title/text)
    _rerank_by_term_overlap(hits, search_query)
    return hits[:top_k]


def get_vector_table_count(cfg: RAGConfig) -> Optional[int]:
    """Return row count for the vector table when using pgvector (for diagnostics)."""
    try:
        if cfg.vector_store.provider.lower() != "pgvector":
            return None
        store = _vector_store_from_config(cfg)
        if hasattr(store, "count"):
            return store.count()
    except Exception:
        pass
    return None
