"""
Query pipeline: embed question -> retrieve from Qdrant.
Supports both semantic (vector) and hybrid (semantic + keyword) retrieval.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from qdrant_client.http import models as qm

from src.rag.embeddings.embedder import GeminiEmbedder, OllamaEmbedder, OpenAIEmbedder, SentenceTransformersEmbedder
from src.rag.integrations.qdrant_store import QdrantVectorStore
from src.rag.keyword_search import BM25KeywordSearch
from src.utils.rag_config_loader import RAGConfig
from src.utils.synonym_expander import SynonymExpander

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


def retrieve_context(
    question: str,
    cfg: RAGConfig,
    *,
    top_k: int | None = None,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-k chunks using semantic search, or hybrid search if enabled.

    Args:
        question: The user's question
        cfg: RAG configuration
        top_k: Override default top_k from config
        filters: Optional filters dict with keys like:
            - "category": filter by category
            - "type": filter by document type (product, article, info_page)
            - "chunk_type": filter by chunk type (overview, benefits, faq, etc.)
            - "products": list of product IDs to filter by

    Returns:
        List of retrieved chunks with scores and payloads
    """
    k = top_k or cfg.retrieval.top_k

    # Check if hybrid search is enabled
    if cfg.retrieval.hybrid.enabled:
        return _hybrid_retrieve(question, cfg, top_k=k, filters=filters)

    # Standard semantic search
    return _semantic_retrieve(question, cfg, top_k=k, filters=filters)


def _semantic_retrieve(
    question: str,
    cfg: RAGConfig,
    *,
    top_k: int,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Retrieve using semantic (vector) search with optional query expansion."""
    embedder, store = _build_clients(cfg)

    # Expand query with synonyms if enabled
    search_query = question
    if cfg.retrieval.query_expansion.enabled:
        expander = SynonymExpander()
        search_query = expander.expand_query(question)
        if search_query != question:
            logger.debug("Expanded semantic query: '%s' -> '%s'", question, search_query)

    qv = embedder.embed_query(search_query)

    # Build Qdrant filter if filters are provided
    qdrant_filter = None
    if filters:
        conditions = []

        if "category" in filters:
            conditions.append(qm.FieldCondition(key="category", match=qm.MatchValue(value=filters["category"])))

        if "type" in filters:
            conditions.append(qm.FieldCondition(key="type", match=qm.MatchValue(value=filters["type"])))

        if "chunk_type" in filters:
            conditions.append(qm.FieldCondition(key="chunk_type", match=qm.MatchValue(value=filters["chunk_type"])))

        if "products" in filters and filters["products"]:
            # Filter by doc_id matching any of the product IDs
            product_ids = filters["products"]
            conditions.append(
                qm.FieldCondition(
                    key="doc_id",
                    match=qm.MatchAny(any=product_ids),
                )
            )

        if conditions:
            if len(conditions) == 1:
                qdrant_filter = qm.Filter(must=conditions)
            else:
                qdrant_filter = qm.Filter(must=conditions)

    hits = store.search(query_vector=qv, limit=top_k, filter=qdrant_filter)
    return hits


def _hybrid_retrieve(
    question: str,
    cfg: RAGConfig,
    *,
    top_k: int,
    filters: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: combine semantic and keyword search results.

    Uses weighted combination of scores from both methods.
    """
    # Get semantic results
    semantic_hits = _semantic_retrieve(question, cfg, top_k=top_k * 2, filters=filters)

    # Get keyword results
    use_synonyms = cfg.retrieval.query_expansion.enabled
    keyword_search = BM25KeywordSearch(use_synonyms=use_synonyms)
    chunks_file = Path("data/processed/website_chunks.jsonl")
    if not keyword_search.load_index() and chunks_file.exists():
        # Build index if it doesn't exist
        keyword_search.build_index(chunks_file)

    keyword_hits = keyword_search.search(question, top_k=top_k * 2, filters=filters)

    # Normalize scores and combine
    semantic_scores = {h["id"]: h["score"] for h in semantic_hits}
    keyword_scores = {h["id"]: h["score"] for h in keyword_hits}

    # Normalize scores to [0, 1] range
    def normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
        if not scores:
            return {}
        max_score = max(scores.values())
        min_score = min(scores.values())
        if max_score == min_score:
            return {k: 0.5 for k in scores}
        return {k: (v - min_score) / (max_score - min_score) for k, v in scores.items()}

    semantic_norm = normalize_scores(semantic_scores)
    keyword_norm = normalize_scores(keyword_scores)

    # Combine scores with weights
    combined_scores: Dict[str, float] = {}
    all_ids = set(semantic_scores.keys()) | set(keyword_scores.keys())

    for chunk_id in all_ids:
        sem_score = semantic_norm.get(chunk_id, 0.0)
        kw_score = keyword_norm.get(chunk_id, 0.0)
        combined = cfg.retrieval.hybrid.semantic_weight * sem_score + cfg.retrieval.hybrid.keyword_weight * kw_score
        combined_scores[chunk_id] = combined

    # Get metadata from both sources
    all_hits: Dict[str, Dict[str, Any]] = {}
    for h in semantic_hits:
        all_hits[h["id"]] = h
    for h in keyword_hits:
        if h["id"] not in all_hits:
            all_hits[h["id"]] = h

    # Sort by combined score and return top_k
    sorted_ids = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results: List[Dict[str, Any]] = []
    for chunk_id, combined_score in sorted_ids:
        hit = all_hits.get(chunk_id)
        if hit:
            # Update score to combined score
            hit["score"] = combined_score
            results.append(hit)

    logger.debug(
        "Hybrid retrieval: %d semantic, %d keyword, %d combined results",
        len(semantic_hits),
        len(keyword_hits),
        len(results),
    )

    return results
