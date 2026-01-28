"""
Embedding backends used by the RAG pipeline (RAG namespace).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Protocol, Sequence


class Embedder(Protocol):
    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]: ...

    def embed_query(self, text: str) -> List[float]: ...

    @property
    def dim(self) -> int: ...


@dataclass
class SentenceTransformersEmbedder:
    model_name: str

    def __post_init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(self.model_name)
        self._dim = int(self._model.get_sentence_embedding_dimension())

    @property
    def dim(self) -> int:
        return self._dim

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        vectors = self._model.encode(list(texts), normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> List[float]:
        v = self._model.encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        return v.tolist()


@dataclass
class OpenAIEmbedder:
    model: str

    def __post_init__(self) -> None:
        import os

        from openai import OpenAI

        if not os.environ.get("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set")
        self._client = OpenAI()
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            raise RuntimeError("OpenAIEmbedder.dim is not known until after first embedding call")
        return self._dim

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        resp = self._client.embeddings.create(model=self.model, input=list(texts))
        vectors = [d.embedding for d in resp.data]
        if vectors and self._dim is None:
            self._dim = len(vectors[0])
        return vectors

    def embed_query(self, text: str) -> List[float]:
        resp = self._client.embeddings.create(model=self.model, input=[text])
        v = resp.data[0].embedding
        if self._dim is None:
            self._dim = len(v)
        return v


@dataclass
class OllamaEmbedder:
    """
    Ollama embeddings via local HTTP API.

    Requires an Ollama server running (default: http://localhost:11434).
    Uses:
    - POST /api/embed (preferred, supports batching) when available
    - POST /api/embeddings (fallback, single prompt) otherwise
    """

    model: str
    base_url: str = "http://localhost:11434"
    timeout_s: float = 60.0

    def __post_init__(self) -> None:
        import requests

        self._requests = requests
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            raise RuntimeError("OllamaEmbedder.dim is not known until after first embedding call")
        return self._dim

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        texts_list = list(texts)
        if not texts_list:
            return []

        # Try /api/embed first (batch)
        try:
            r = self._requests.post(
                f"{self.base_url.rstrip('/')}/api/embed",
                json={"model": self.model, "input": texts_list},
                timeout=self.timeout_s,
            )
            if r.status_code == 200:
                data = r.json()
                # Ollama returns {"embeddings": [[...], ...]}
                vectors = data.get("embeddings") or []
                if vectors and self._dim is None:
                    self._dim = len(vectors[0])
                return vectors
        except Exception:
            # Fall back to /api/embeddings below
            pass

        # Fallback: /api/embeddings per text
        out: List[List[float]] = []
        for t in texts_list:
            v = self.embed_query(t)
            out.append(v)
        return out

    def embed_query(self, text: str) -> List[float]:
        r = self._requests.post(
            f"{self.base_url.rstrip('/')}/api/embeddings",
            json={"model": self.model, "prompt": text},
            timeout=self.timeout_s,
        )
        r.raise_for_status()
        data = r.json()
        v = data.get("embedding")
        if not isinstance(v, list):
            raise RuntimeError(f"Unexpected Ollama embeddings response: {data}")
        if self._dim is None:
            self._dim = len(v)
        return v


@dataclass
class GeminiEmbedder:
    """
    Google Gemini embeddings via google-generativeai (AI Studio).

    Requires env var with your API key, e.g. GEMINI_API_KEY.
    Use model "models/gemini-embedding-001" (text-embedding-004 is deprecated for embedContent).
    """

    model: str
    api_key_env: str = "GEMINI_API_KEY"

    def __post_init__(self) -> None:
        import os

        import google.generativeai as genai

        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(f"{self.api_key_env} is not set")
        genai.configure(api_key=key)
        self._genai = genai
        self._dim: int | None = None

    @property
    def dim(self) -> int:
        if self._dim is None:
            raise RuntimeError("GeminiEmbedder.dim is not known until after first embedding call")
        return self._dim

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        out: List[List[float]] = []
        for t in texts:
            v = self.embed_query(t)
            out.append(v)
        return out

    def embed_query(self, text: str) -> List[float]:
        # task_type improves retrieval embeddings
        resp = self._genai.embed_content(
            model=self.model,
            content=text,
            task_type="retrieval_query",
        )
        v = resp.get("embedding")
        if not isinstance(v, list):
            raise RuntimeError(f"Unexpected Gemini embedding response: {resp}")
        if self._dim is None:
            self._dim = len(v)
        return v
