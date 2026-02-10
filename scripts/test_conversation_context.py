#!/usr/bin/env python3
"""
Test conversation context awareness
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from src.utils.rag_config_loader import load_rag_config
from src.rag.query import retrieve_context
from src.rag.generate import MiaGenerator


async def test_conversation_context():
    """Test that the LLM uses conversation history for context-aware responses"""
    print("=" * 80)
    print("Testing Conversation Context Awareness")
    print("=" * 80)
    
    cfg = load_rag_config()
    mia = MiaGenerator()
    
    # Simulate a conversation
    conversation_history = []
    
    # Turn 1: Ask about travel insurance
    print("\n[Turn 1] User: What are the benefits of travel insurance?")
    query1 = "What are the benefits of travel insurance?"
    hits1 = retrieve_context(query1, cfg, top_k=3)
    answer1 = await mia.generate(query1, hits1, conversation_history)
    print(f"Assistant: {answer1[:200]}...")
    
    # Add to history
    conversation_history.append({"role": "user", "content": query1})
    conversation_history.append({"role": "assistant", "content": answer1})
    
    # Turn 2: Follow-up question (should understand "it" refers to travel insurance)
    print("\n[Turn 2] User: How much does it cost?")
    query2 = "How much does it cost?"
    hits2 = retrieve_context(query2, cfg, top_k=3)
    answer2 = await mia.generate(query2, hits2, conversation_history)
    print(f"Assistant: {answer2}")
    
    # Add to history
    conversation_history.append({"role": "user", "content": query2})
    conversation_history.append({"role": "assistant", "content": answer2})
    
    # Turn 3: Another follow-up (should maintain context)
    print("\n[Turn 3] User: Tell me more about the coverage")
    query3 = "Tell me more about the coverage"
    hits3 = retrieve_context(query3, cfg, top_k=3)
    answer3 = await mia.generate(query3, hits3, conversation_history)
    print(f"Assistant: {answer3}")
    
    print("\n" + "=" * 80)
    print("✓ Conversation context test completed")
    print("=" * 80)
    
    # Test without history for comparison
    print("\n[COMPARISON] Same question WITHOUT history:")
    query_no_context = "How much does it cost?"
    hits_no_context = retrieve_context(query_no_context, cfg, top_k=3)
    answer_no_context = await mia.generate(query_no_context, hits_no_context, None)
    print(f"Assistant: {answer_no_context}")
    print("\nNote: Without history, the LLM doesn't know what 'it' refers to.")


if __name__ == "__main__":
    asyncio.run(test_conversation_context())
