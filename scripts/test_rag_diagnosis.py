#!/usr/bin/env python3
"""
Diagnostic script to test RAG system components:
1. Embeddings generation
2. Vector database connectivity
3. Gemini API connectivity
4. End-to-end retrieval and generation
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()


def test_embeddings():
    """Test embeddings generation"""
    print("\n" + "="*80)
    print("TEST 1: Embeddings Generation")
    print("="*80)
    
    try:
        from src.utils.rag_config_loader import load_rag_config
        from src.rag.query import _embedder_from_config
        
        cfg = load_rag_config()
        logger.info(f"Loaded config. Embeddings provider: {cfg.embeddings.provider}")
        
        embedder = _embedder_from_config(cfg)
        logger.info(f"Initialized embedder: {type(embedder).__name__}")
        
        test_query = "What are the benefits of Old Mutual Travel Sure Plus?"
        query_vec = embedder.embed_query(test_query)
        
        logger.info(f"✓ Successfully generated query embedding")
        logger.info(f"  Query: {test_query}")
        logger.info(f"  Vector shape: {len(query_vec)} dimensions")
        logger.info(f"  First 5 values: {query_vec[:5]}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Embeddings test FAILED: {type(e).__name__}: {e}", exc_info=True)
        return False


def test_vector_store():
    """Test vector store connectivity and search"""
    print("\n" + "="*80)
    print("TEST 2: Vector Store Connectivity")
    print("="*80)
    
    try:
        from src.utils.rag_config_loader import load_rag_config
        from src.rag.query import _vector_store_from_config, _embedder_from_config
        
        cfg = load_rag_config()
        logger.info(f"Vector store provider: {cfg.vector_store.provider}")
        
        embedder = _embedder_from_config(cfg)
        store = _vector_store_from_config(cfg)
        logger.info(f"✓ Initialized vector store: {type(store).__name__}")
        
        # Try a test search
        test_query = "travel insurance"
        query_vec = embedder.embed_query(test_query)
        
        hits = store.search(query_vector=query_vec, limit=3)
        logger.info(f"✓ Successfully queried vector store")
        logger.info(f"  Query: {test_query}")
        logger.info(f"  Found {len(hits)} hits")
        
        for i, hit in enumerate(hits[:3], 1):
            score = hit.get("score", "N/A")
            title = (hit.get("payload") or {}).get("title", "N/A")
            logger.info(f"  Hit {i}: score={score:.4f}, title={title}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Vector store test FAILED: {type(e).__name__}: {e}", exc_info=True)
        return False


def test_gemini_api():
    """Test Gemini API connectivity"""
    print("\n" + "="*80)
    print("TEST 3: Gemini API Connectivity")
    print("="*80)
    
    try:
        import asyncio
        from src.rag.generate import MiaGenerator
        
        logger.info("Initializing MiaGenerator...")
        mia = MiaGenerator()
        logger.info("✓ MiaGenerator initialized successfully")
        
        # Test with mock context
        mock_context = [
            {
                "id": "test1",
                "score": 0.95,
                "payload": {
                    "title": "Travel Sure Plus Overview",
                    "text": "Travel Sure Plus is a comprehensive travel insurance product...",
                    "doc_id": "travel_plus_001"
                }
            }
        ]
        
        async def test_generation():
            result = await mia.generate(
                "What is Travel Sure Plus?",
                mock_context
            )
            return result
        
        result = asyncio.run(test_generation())
        logger.info(f"✓ Successfully generated response from Gemini")
        logger.info(f"  Response preview: {result[:200]}...")
        
        return True
    except Exception as e:
        logger.error(f"✗ Gemini API test FAILED: {type(e).__name__}: {e}", exc_info=True)
        return False


def test_retrieve_context():
    """Test full retrieve_context function"""
    print("\n" + "="*80)
    print("TEST 4: Full Retrieval Pipeline")
    print("="*80)
    
    try:
        from src.utils.rag_config_loader import load_rag_config
        from src.rag.query import retrieve_context
        
        cfg = load_rag_config()
        
        test_query = "What are the key benefits of Old Mutual travel insurance?"
        logger.info(f"Running retrieval for: {test_query}")
        
        hits = retrieve_context(test_query, cfg, top_k=5)
        logger.info(f"✓ Successfully retrieved {len(hits)} hits")
        
        for i, hit in enumerate(hits[:3], 1):
            score = hit.get("score", "N/A")
            title = (hit.get("payload") or {}).get("title", "N/A")
            doc_id = (hit.get("payload") or {}).get("doc_id", "N/A")
            logger.info(f"  Hit {i}: score={score}, doc_id={doc_id}, title={title}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Retrieve context test FAILED: {type(e).__name__}: {e}", exc_info=True)
        return False


def test_full_rag_pipeline():
    """Test full RAG pipeline (retrieve + generate)"""
    print("\n" + "="*80)
    print("TEST 5: Full RAG Pipeline (Retrieve + Generate)")
    print("="*80)
    
    try:
        import asyncio
        from src.utils.rag_config_loader import load_rag_config
        from src.rag.query import retrieve_context
        from src.rag.generate import MiaGenerator
        
        cfg = load_rag_config()
        
        test_query = "What is the coverage for Travel Sure Plus?"
        logger.info(f"Testing full pipeline with: {test_query}")
        
        # Step 1: Retrieve
        logger.info("Step 1: Retrieving context...")
        hits = retrieve_context(test_query, cfg, top_k=5)
        logger.info(f"✓ Retrieved {len(hits)} hits")
        
        # Step 2: Generate
        logger.info("Step 2: Generating response...")
        mia = MiaGenerator()
        
        async def test_gen():
            answer = await mia.generate(test_query, hits)
            return answer
        
        answer = asyncio.run(test_gen())
        logger.info(f"✓ Generated response:")
        logger.info(f"  {answer}")
        
        return True
    except Exception as e:
        logger.error(f"✗ Full RAG pipeline test FAILED: {type(e).__name__}: {e}", exc_info=True)
        return False


def main():
    print("\n" + "="*80)
    print("RAG SYSTEM DIAGNOSTIC TEST SUITE")
    print("="*80)
    
    results = {}
    
    # Run tests
    results["Embeddings"] = test_embeddings()
    results["Vector Store"] = test_vector_store()
    results["Gemini API"] = test_gemini_api()
    results["Retrieve Context"] = test_retrieve_context()
    results["Full RAG Pipeline"] = test_full_rag_pipeline()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    all_passed = all(results.values())
    print("="*80)
    if all_passed:
        print("✓ ALL TESTS PASSED - RAG system is working correctly!")
        return 0
    else:
        print("✗ SOME TESTS FAILED - See logs above for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
