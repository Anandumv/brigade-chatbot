"""Test routing after intent classification fix"""

import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.gpt_intent_classifier import classify_intent_gpt_first


def test_routing():
    """Test that queries are routed correctly to database vs GPT"""

    test_cases = [
        # Database routes - Project Search
        ("Show me 2BHK in Whitefield under 2 Cr", "property_search", "database"),
        ("Find 3BHK apartments in Sarjapur", "property_search", "database"),
        ("Looking for flats in Marathahalli", "property_search", "database"),

        # Database routes - Project Facts (NEW - should be database, not GPT)
        ("Tell me about Brigade Avalon", "project_facts", "database"),
        ("Details of Brigade Citrine", "project_facts", "database"),
        ("Amenities in Brigade Citrine", "project_facts", "database"),
        ("Features of Prestige Neopolis", "project_facts", "database"),
        ("Price of Brigade Avalon", "project_facts", "database"),
        ("RERA number of Sobha Neopolis", "project_facts", "database"),
        ("Possession date of Brigade Citrine", "project_facts", "database"),

        # GPT routes - Conversational/Advisory
        ("Too expensive", "sales_conversation", "gpt_generation"),
        ("How to stretch my budget?", "sales_conversation", "gpt_generation"),
        ("Investment potential of Whitefield", "sales_conversation", "gpt_generation"),
        ("Whitefield vs Sarjapur comparison", "sales_conversation", "gpt_generation"),
        ("How far is airport from Avalon?", "sales_conversation", "gpt_generation"),
        ("Nearby schools to Citrine", "sales_conversation", "gpt_generation"),
        ("Why should I buy in Whitefield?", "sales_conversation", "gpt_generation"),
    ]

    print("=" * 80)
    print("Testing Intent Classification Routing After Fix")
    print("=" * 80)
    print()

    passed = 0
    failed = 0
    failures = []

    for query, expected_intent, expected_source in test_cases:
        try:
            result = classify_intent_gpt_first(
                query=query,
                conversation_history=[],
                session_state={}
            )

            intent = result.get("intent", "")
            source = result.get("data_source", "")

            is_correct = (intent == expected_intent and source == expected_source)
            status = "✅" if is_correct else "❌"

            if is_correct:
                passed += 1
            else:
                failed += 1
                failures.append((query, expected_intent, expected_source, intent, source))

            print(f"{status} Query: {query}")
            print(f"   Expected: {expected_intent} → {expected_source}")
            print(f"   Got: {intent} → {source}")

            if not is_correct:
                print(f"   Reasoning: {result.get('reasoning', 'N/A')}")

            print()

        except Exception as e:
            failed += 1
            failures.append((query, expected_intent, expected_source, "ERROR", str(e)))
            print(f"❌ Query: {query}")
            print(f"   Error: {e}")
            print()

    print("=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed out of {len(test_cases)} total")
    print("=" * 80)

    if failures:
        print("\n❌ FAILED TESTS:")
        print("-" * 80)
        for query, exp_intent, exp_source, got_intent, got_source in failures:
            print(f"Query: {query}")
            print(f"  Expected: {exp_intent} → {exp_source}")
            print(f"  Got: {got_intent} → {got_source}")
            print()
    else:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Project search queries → database")
        print("✅ Project detail queries (NEW) → database")
        print("✅ Conversational queries → GPT")
        print()
        print("Cost Savings:")
        print("- Project detail queries no longer waste GPT calls")
        print("- Database returns structured data instantly")
        print("- GPT reserved for true advisory conversations")

    return failed == 0


if __name__ == "__main__":
    success = test_routing()
    sys.exit(0 if success else 1)
