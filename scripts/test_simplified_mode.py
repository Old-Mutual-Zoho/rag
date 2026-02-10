#!/usr/bin/env python3
"""
Quick test to verify simplified conversational mode works without intent classification.
"""

import sys
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()


async def test_small_talk():
    """Test small talk detection without IntentClassifier"""
    from src.chatbot.intent_classifier import SmallTalkResponder
    
    print("\n" + "="*80)
    print("TEST: SmallTalkResponder")
    print("="*80)
    
    try:
        responder = SmallTalkResponder()
        
        test_messages = [
            ("hi", "GREETING"),
            ("how are you", "SMALL_TALK"),
            ("thanks", "THANKS"),
            ("bye", "GOODBYE"),
        ]
        
        for msg, label in test_messages:
            response = await responder.respond(msg, label)
            print(f"\nMessage: {msg}")
            print(f"Label: {label}")
            print(f"Response: {response}")
        
        print("\n✓ SmallTalkResponder working correctly!")
        return True
    except Exception as e:
        print(f"\n✗ SmallTalkResponder FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_conversational_mode():
    """Test that conversational mode works without _classify_intent"""
    print("\n" + "="*80)
    print("TEST: ConversationalMode Initialization")
    print("="*80)
    
    try:
        from src.api.main import rag_adapter, product_matcher, state_manager
        from src.chatbot.modes.conversational import ConversationalMode
        
        mode = ConversationalMode(rag_adapter, product_matcher, state_manager)
        
        # Verify methods exist
        assert hasattr(mode, '_detect_intent'), "Missing _detect_intent"
        assert hasattr(mode, '_detect_no_retrieval_intent'), "Missing _detect_no_retrieval_intent"
        assert hasattr(mode, '_build_no_retrieval_reply'), "Missing _build_no_retrieval_reply"
        
        # Verify removed methods don't exist
        assert not hasattr(mode, '_classify_intent'), "_classify_intent should be removed"
        assert not hasattr(mode, '_build_overview_summary'), "_build_overview_summary should be removed"
        
        print("✓ ConversationalMode initialized without IntentClassifier")
        print("✓ Removed methods: _classify_intent, _build_overview_summary")
        print("✓ Kept methods: _detect_intent, _detect_no_retrieval_intent")
        
        return True
    except Exception as e:
        print(f"\n✗ ConversationalMode initialization FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    print("\n" + "="*80)
    print("SIMPLIFIED CONVERSATIONAL MODE TEST SUITE")
    print("="*80)
    
    results = {}
    
    results["SmallTalkResponder"] = await test_small_talk()
    results["ConversationalMode"] = await test_conversational_mode()
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{test_name}: {status}")
    
    print("="*80)
    if all(results.values()):
        print("✓ ALL TESTS PASSED - Simplified conversational mode working!")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
