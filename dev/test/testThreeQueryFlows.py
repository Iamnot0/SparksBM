#!/usr/bin/env python3
"""
Test script for three query flows:
1. ISMS Operations
2. Document Operations  
3. Knowledge Queries

Tests that patterns are loaded from JSON correctly.
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'Agentic Framework'))

def test_isms_operations():
    """Test ISMS operation detection"""
    print("\n" + "="*60)
    print("TEST 1: ISMS OPERATIONS FLOW")
    print("="*60)
    
    from agents.instructions import (
        VERINICE_OBJECT_TYPES,
        VERINICE_CREATE_PATTERNS,
        VERINICE_LIST_PATTERNS,
    )
    
    # Test patterns loaded from JSON
    assert len(VERINICE_OBJECT_TYPES) > 0, "VERINICE_OBJECT_TYPES should not be empty"
    assert len(VERINICE_CREATE_PATTERNS) > 0, "VERINICE_CREATE_PATTERNS should not be empty"
    assert len(VERINICE_LIST_PATTERNS) > 0, "VERINICE_LIST_PATTERNS should not be empty"
    
    print(f"✅ VERINICE_OBJECT_TYPES: {len(VERINICE_OBJECT_TYPES)} types")
    print(f"   Examples: {VERINICE_OBJECT_TYPES[:4]}")
    print(f"✅ VERINICE_CREATE_PATTERNS: {len(VERINICE_CREATE_PATTERNS)} patterns")
    print(f"   Examples: {VERINICE_CREATE_PATTERNS[:3]}")
    print(f"✅ VERINICE_LIST_PATTERNS: {len(VERINICE_LIST_PATTERNS)} patterns")
    print(f"   Examples: {VERINICE_LIST_PATTERNS[:3]}")
    
    # Test detection logic (import mainAgent)
    try:
        from agents.mainAgent import MainAgent
        agent = MainAgent()
        
        # Test ISMS detection
        test_messages = [
            "create scope TestScope",
            "list assets",
            "get asset Server1",
            "update scope TestScope description to Updated",
            "delete asset OldAsset"
        ]
        
        print("\n📋 Testing ISMS Detection:")
        for msg in test_messages:
            result = agent._detectVeriniceOp(msg)
            if result:
                print(f"   ✅ '{msg}' → {result}")
            else:
                print(f"   ⚠️  '{msg}' → None (not detected)")
        
        return True
    except Exception as e:
        print(f"   ❌ Error testing ISMS detection: {e}")
        return False


def test_document_operations():
    """Test document operation patterns"""
    print("\n" + "="*60)
    print("TEST 2: DOCUMENT OPERATIONS FLOW")
    print("="*60)
    
    from agents.instructions import (
        SUPPORTED_FILE_EXTENSIONS,
        BULK_IMPORT_TRIGGERS,
    )
    
    # Test file extensions
    assert len(SUPPORTED_FILE_EXTENSIONS) > 0, "SUPPORTED_FILE_EXTENSIONS should not be empty"
    assert '.pdf' in SUPPORTED_FILE_EXTENSIONS, "PDF should be in supported extensions"
    
    print(f"✅ SUPPORTED_FILE_EXTENSIONS: {SUPPORTED_FILE_EXTENSIONS}")
    print(f"✅ BULK_IMPORT_TRIGGERS: {len(BULK_IMPORT_TRIGGERS)} triggers")
    print(f"   Examples: {BULK_IMPORT_TRIGGERS[:5]}")
    
    # Test bulk import detection
    try:
        from agents.mainAgent import MainAgent
        agent = MainAgent()
        
        test_messages = [
            "yes",
            "import assets",
            "create assets",
            "bulk import",
            "ii"  # Should be in triggers
        ]
        
        print("\n📋 Testing Bulk Import Detection:")
        for msg in test_messages:
            # Check if message contains any bulk trigger
            msg_lower = msg.lower()
            is_bulk = any(trigger in msg_lower for trigger in BULK_IMPORT_TRIGGERS)
            if is_bulk:
                print(f"   ✅ '{msg}' → Bulk import trigger detected")
            else:
                print(f"   ⚠️  '{msg}' → Not detected as bulk trigger")
        
        return True
    except Exception as e:
        print(f"   ❌ Error testing document operations: {e}")
        return False


def test_knowledge_queries():
    """Test knowledge query patterns"""
    print("\n" + "="*60)
    print("TEST 3: KNOWLEDGE QUERIES FLOW")
    print("="*60)
    
    from agents.instructions import (
        KNOWLEDGE_QUESTION_STARTERS,
        KNOWLEDGE_QUESTION_PHRASES,
        KNOWLEDGE_WHAT_PATTERNS,
        KNOWLEDGE_HOW_TO_CREATE_PATTERNS,
    )
    
    # Test patterns loaded from JSON
    assert len(KNOWLEDGE_QUESTION_STARTERS) > 0, "KNOWLEDGE_QUESTION_STARTERS should not be empty"
    assert len(KNOWLEDGE_QUESTION_PHRASES) > 0, "KNOWLEDGE_QUESTION_PHRASES should not be empty"
    
    print(f"✅ KNOWLEDGE_QUESTION_STARTERS: {len(KNOWLEDGE_QUESTION_STARTERS)} starters")
    print(f"   Examples: {KNOWLEDGE_QUESTION_STARTERS[:5]}")
    print(f"✅ KNOWLEDGE_QUESTION_PHRASES: {len(KNOWLEDGE_QUESTION_PHRASES)} phrases")
    print(f"   Examples: {KNOWLEDGE_QUESTION_PHRASES[:5]}")
    print(f"✅ KNOWLEDGE_WHAT_PATTERNS: {KNOWLEDGE_WHAT_PATTERNS}")
    print(f"✅ KNOWLEDGE_HOW_TO_CREATE_PATTERNS: {KNOWLEDGE_HOW_TO_CREATE_PATTERNS}")
    
    # Test knowledge detection
    try:
        from agents.mainAgent import MainAgent
        agent = MainAgent()
        
        test_messages = [
            "what is ISMS?",
            "how do I create a scope?",
            "explain asset management",
            "what can you do?",
            "tell me about ISO 27001"
        ]
        
        print("\n📋 Testing Knowledge Question Detection:")
        for msg in test_messages:
            msg_lower = msg.lower().strip()
            
            # Check question starters
            is_knowledge = any(starter in msg_lower for starter in KNOWLEDGE_QUESTION_STARTERS) or msg_lower.endswith('?')
            
            # Check if filtered by ISMS detection (should return None for questions)
            isms_result = agent._detectVeriniceOp(msg)
            
            if is_knowledge:
                if isms_result is None:
                    print(f"   ✅ '{msg}' → Knowledge question (correctly filtered from ISMS)")
                else:
                    print(f"   ⚠️  '{msg}' → Detected as ISMS (should be knowledge)")
            else:
                print(f"   ⚠️  '{msg}' → Not detected as knowledge question")
        
        # Test fallback answer
        print("\n📋 Testing Knowledge Base Fallback:")
        fallback_tests = [
            "what is asset?",
            "what is scope?",
            "how do I create an asset?",
            "how do I create a scope?"
        ]
        
        for msg in fallback_tests:
            answer = agent._getFallbackAnswer(msg)
            if answer:
                print(f"   ✅ '{msg}' → Found in knowledge base ({len(answer)} chars)")
            else:
                print(f"   ⚠️  '{msg}' → Not found in knowledge base")
        
        return True
    except Exception as e:
        print(f"   ❌ Error testing knowledge queries: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_typo_normalization():
    """Test typo normalization"""
    print("\n" + "="*60)
    print("TEST 4: TYPO NORMALIZATION")
    print("="*60)
    
    from agents.instructions import TYPO_VARIATIONS
    
    print(f"✅ TYPO_VARIATIONS loaded: {len(TYPO_VARIATIONS)} entries")
    for correct, typos in list(TYPO_VARIATIONS.items())[:5]:
        print(f"   {correct} → {typos}")
    
    return True


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("THREE QUERY FLOWS TEST")
    print("="*60)
    print("Testing: ISMS Operations, Document Operations, Knowledge Queries")
    
    results = []
    
    try:
        results.append(("ISMS Operations", test_isms_operations()))
    except Exception as e:
        print(f"❌ ISMS Operations test failed: {e}")
        results.append(("ISMS Operations", False))
    
    try:
        results.append(("Document Operations", test_document_operations()))
    except Exception as e:
        print(f"❌ Document Operations test failed: {e}")
        results.append(("Document Operations", False))
    
    try:
        results.append(("Knowledge Queries", test_knowledge_queries()))
    except Exception as e:
        print(f"❌ Knowledge Queries test failed: {e}")
        results.append(("Knowledge Queries", False))
    
    try:
        results.append(("Typo Normalization", test_typo_normalization()))
    except Exception as e:
        print(f"❌ Typo Normalization test failed: {e}")
        results.append(("Typo Normalization", False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Patterns successfully externalized to JSON.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Review errors above.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
