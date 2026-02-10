from types import SimpleNamespace

import pytest

import src.rag.generate as generate_mod
import src.rag.query as query_mod


class DummyModels:
    def __init__(self):
        self.last_contents = None

    def generate_content(self, model, contents, config):
        self.last_contents = contents
        return SimpleNamespace(text="ok")


class DummyClient:
    def __init__(self, *args, **kwargs):
        self.models = DummyModels()


@pytest.mark.asyncio
async def test_generate_includes_summary_and_history(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(generate_mod.genai, "Client", DummyClient)

    mia = generate_mod.MiaGenerator()
    history = [
        {"role": "user", "content": "Tell me about travel insurance"},
        {"role": "assistant", "content": "It covers trips and emergencies."},
        {"role": "user", "content": "How much does it cost?"},
    ]

    hits = [
        {"id": "1", "score": 0.9, "payload": {"title": "Doc", "text": "Some text"}},
    ]

    await mia.generate("How much does it cost?", hits, history)
    prompt = mia.client.models.last_contents

    assert "Conversation Summary" in prompt
    assert "Recent Conversation" in prompt
    assert "User asked about" in prompt


def test_retrieve_context_uses_cache(monkeypatch):
    class DummyEmbedder:
        def __init__(self):
            self.calls = 0

        def embed_query(self, text):
            self.calls += 1
            return [0.1, 0.2, 0.3]

    class DummyStore:
        def __init__(self):
            self.calls = 0

        def search(self, query_vector, limit, filters=None):
            self.calls += 1
            return [
                {"id": "1", "score": 0.9, "payload": {"title": "Doc", "text": "Some text"}},
            ]

    class DummyExpander:
        def expand_query(self, q):
            return q

    embedder = DummyEmbedder()
    store = DummyStore()

    monkeypatch.setattr(query_mod, "_embedder_from_config", lambda cfg: embedder)
    monkeypatch.setattr(query_mod, "_vector_store_from_config", lambda cfg: store)
    monkeypatch.setattr("src.utils.synonym_expander.SynonymExpander", DummyExpander)

    query_mod._EMBEDDING_CACHE.clear()
    query_mod._RETRIEVAL_CACHE.clear()

    cfg = SimpleNamespace(
        embeddings=SimpleNamespace(provider="gemini", model="test", api_key_env="GEMINI_API_KEY", output_dimensionality=1536),
        vector_store=SimpleNamespace(provider="pgvector", collection="old_mutual_chunks", path=None, host=None, port=None),
        retrieval=SimpleNamespace(hybrid=SimpleNamespace(enabled=False), top_k=3),
    )

    result1 = query_mod.retrieve_context("test query", cfg, top_k=3)
    result2 = query_mod.retrieve_context("test query", cfg, top_k=3)

    assert result1
    assert result2
    assert embedder.calls == 1
    assert store.calls == 1
