"""
RAG configuration loader (embeddings, vector store, retrieval, generation).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class EmbeddingsConfig(BaseModel):
    backend: Literal["sentence_transformers", "openai", "ollama", "gemini"] = "sentence_transformers"
    model: str = "sentence-transformers/all-MiniLM-L6-v2"
    batch_size: int = Field(default=32, ge=1, le=1024)
    base_url: str = "http://localhost:11434"
    api_key_env: str = "GEMINI_API_KEY"


class VectorStoreConfig(BaseModel):
    provider: Literal["qdrant_local", "qdrant_http"] = "qdrant_local"
    collection: str = "oldmutual_website"
    path: str = "data/embeddings/qdrant"
    host: str = "localhost"
    port: int = Field(default=6333, ge=1, le=65535)


class RetrievalConfig(BaseModel):
    top_k: int = Field(default=8, ge=1, le=100)


class GenerationConfig(BaseModel):
    enabled: bool = False
    backend: Literal["openai", "gemini"] = "openai"
    model: str = "gpt-4o-mini"
    api_key_env: str = "GEMINI_API_KEY"


class RAGConfig(BaseModel):
    embeddings: EmbeddingsConfig = Field(default_factory=EmbeddingsConfig)
    vector_store: VectorStoreConfig = Field(default_factory=VectorStoreConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)


def load_rag_config(config_path: Optional[Path] = None) -> RAGConfig:
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "rag_config.yml"

    if not config_path.exists():
        raise FileNotFoundError(f"RAG config file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    try:
        cfg = RAGConfig(**data)
        logger.info("Successfully loaded RAG config from %s", config_path)
        return cfg
    except ValidationError as e:
        logger.error("RAG config validation failed: %s", e)
        raise

