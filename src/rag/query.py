"""
RAG retrieval: embed query, run vector search (and optional hybrid), return hits.
Supports pgvector and Qdrant via config.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from src.utils.rag_config_loader import RAGConfig

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
        combined = " ".join(str(p.get(k, "")) for k in ("title", "text", "doc_id", "section_heading")).lower()
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
        return GeminiEmbedder(
            model=cfg.embeddings.model,
            api_key_env=cfg.embeddings.api_key_env,
            output_dimensionality=cfg.embeddings.output_dimensionality,
        )
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

    try:
        expander = SynonymExpander()
        search_query = expander.expand_query(question)
        logger.debug(f"Expanded query: '{question}' -> '{search_query}'")

        logger.info(f"Initializing embedder with provider: {cfg.embeddings.provider}")
        embedder = _embedder_from_config(cfg)

        logger.info(f"Initializing vector store with provider: {cfg.vector_store.provider}")
        store = _vector_store_from_config(cfg)

        # Fetch extra candidates so we can re-rank by product-term overlap (e.g. "Somesa" in chunk)
        fetch_k = min(top_k * 2, 20)

        logger.debug(f"Embedding query: {search_query[:100]}...")
        qvec = embedder.embed_query(search_query)
        logger.debug(f"Query vector shape: {len(qvec)}")

        store_class = type(store).__name__
        logger.info(f"Searching with {store_class}, fetch_k={fetch_k}")

        if store_class == "PgVectorStore":
            # Table/collection creation is handled during ingest/startup; avoid
            # running DDL on every query to keep latency low.
            hits = store.search(query_vector=qvec, limit=fetch_k, filters=filters)
        elif store_class == "QdrantVectorStore":
            kw: Dict[str, Any] = {"query_vector": qvec, "limit": fetch_k}
            if filters:
                from qdrant_client.http import models as qm

                conditions: List[qm.FieldCondition] = []
                for k, v in filters.items():
                    if v is None:
                        continue
                    # Our public filter API uses filters["products"] = [doc_id, ...]
                    # to restrict results by payload.doc_id.
                    if k == "products" and isinstance(v, (list, tuple)):
                        vals = [x for x in v if x]
                        if not vals:
                            continue
                        # Qdrant payload is flat (doc_id stored at top level in payload).
                        # Use MatchAny for lists.
                        if hasattr(qm, "MatchAny"):
                            conditions.append(qm.FieldCondition(key="doc_id", match=qm.MatchAny(any=vals)))
                        else:  # pragma: no cover - very old qdrant-client
                            # Fallback: OR as should-clause
                            any_conditions = [qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=x)) for x in vals]
                            kw["filter"] = qm.Filter(should=any_conditions)
                            conditions = []
                            break
                        continue

                    # Scalar filters (category, type, chunk_type, etc.)
                    conditions.append(qm.FieldCondition(key=k, match=qm.MatchValue(value=v)))
                if conditions:
                    kw["filter"] = qm.Filter(must=conditions)
            hits = store.search(**kw)
        else:
            hits = store.search(query_vector=qvec, limit=fetch_k, filters=filters or {})

        logger.info(f"Retrieved {len(hits)} hits from vector store")

        if cfg.retrieval.hybrid.enabled:
            from src.rag.keyword_search import BM25KeywordSearch

            logger.info("Hybrid search enabled, merging with BM25 results")
            bm25 = BM25KeywordSearch()
            if bm25.load_index():
                bm25_hits = bm25.search(query=search_query, top_k=fetch_k, filters=filters)
                logger.info(f"BM25 returned {len(bm25_hits)} hits")
                seen = {h["id"] for h in hits}
                for h in bm25_hits:
                    if h["id"] not in seen and len(hits) < fetch_k:
                        hits.append(h)
                        seen.add(h["id"])
                hits = hits[:fetch_k]
            else:
                logger.warning("BM25 index not found, skipping hybrid merge")

        # Re-rank: prefer chunks that contain query/product terms (e.g. "Somesa" in title/text)
        _rerank_by_term_overlap(hits, search_query)
        final_hits = hits[:top_k]
        logger.info(f"Returning {len(final_hits)} hits after reranking")
        return final_hits

    except Exception as e:
        logger.error(f"Error during retrieval for question '{question}': {type(e).__name__}: {e}", exc_info=True)
        return []  # Return empty list instead of raising, so generation can handle gracefully


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
