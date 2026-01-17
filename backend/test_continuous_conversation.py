"""Test continuous conversation routing"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.gpt_intent_classifier import classify_intent_gpt_first


def test_continuous_conversation():
    """Test that continuous conversation queries go to GPT, not database"""

    print("=" * 80)
    print("Testing Continuous Conversation Routing")
    print("=" * 80)
    print()

    test_cases = [
        # Continuous conversation - should go to GPT
        {
            "query": "tell me more",
            "session_state": {"last_intent": "property_search"},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "Follow-up after property search"
        },
        {
            "query": "more",
            "session_state": {"last_intent": "property_search"},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "Simple 'more' continuation"
        },
        {
            "query": "tell me more about the amenities",
            "session_state": {"last_intent": "property_search"},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "Elaborate on amenities (no specific project)"
        },
        {
            "query": "give me more details",
            "session_state": {"last_intent": "property_search"},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "Request more details (continuation)"
        },
        {
            "query": "what else",
            "session_state": {"last_intent": "property_search"},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "What else (continuation)"
        },

        # Specific project queries - should go to database
        {
            "query": "Tell me about Brigade Avalon",
            "session_state": {},
            "expected_intent": "project_facts",
            "expected_source": "database",
            "description": "Specific project details request"
        },
        {
            "query": "Details of Brigade Citrine",
            "session_state": {},
            "expected_intent": "project_facts",
            "expected_source": "database",
            "description": "Details about specific project"
        },
        {
            "query": "Amenities in Brigade Citrine",
            "session_state": {},
            "expected_intent": "project_facts",
            "expected_source": "database",
            "description": "Amenities of specific project"
        },

        # Advisory/conversational - should go to GPT
        {
            "query": "Too expensive",
            "session_state": {},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "Objection handling"
        },
        {
            "query": "How can I afford this?",
            "session_state": {},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "Budget advice"
        },
        {
            "query": "Why should I buy in Whitefield?",
            "session_state": {},
            "expected_intent": "sales_conversation",
            "expected_source": "gpt_generation",
            "description": "Location advice"
        },
    ]

    passed = 0
    failed = 0
    failures = []

    for test in test_cases:
        query = test["query"]
        session_state = test["session_state"]
        expected_intent = test["expected_intent"]
        expected_source = test["expected_source"]
        description = test["description"]

        try:
            result = classify_intent_gpt_first(
                query=query,
                conversation_history=[],
                session_state=session_state
            )

            intent = result.get("intent", "")
            source = result.get("data_source", "")

            is_correct = (intent == expected_intent and source == expected_source)
            status = "✅" if is_correct else "❌"

            if is_correct:
                passed += 1
            else:
                failed += 1
                failures.append({
                    "query": query,
                    "description": description,
                    "expected": f"{expected_intent} → {expected_source}",
                    "got": f"{intent} → {source}",
                    "reasoning": result.get("reasoning", "N/A")
                })

            print(f"{status} {description}")
            print(f"   Query: \"{query}\"")
            print(f"   Expected: {expected_intent} → {expected_source}")
            print(f"   Got: {intent} → {source}")
            if not is_correct:
                print(f"   Reasoning: {result.get('reasoning', 'N/A')}")
            print()

        except Exception as e:
            failed += 1
            failures.append({
                "query": query,
                "description": description,
                "expected": f"{expected_intent} → {expected_source}",
                "got": f"ERROR: {str(e)}",
                "reasoning": ""
            })
            print(f"❌ {description}")
            print(f"   Query: \"{query}\"")
            print(f"   Error: {e}")
            print()

    print("=" * 80)
    print(f"Test Results: {passed} passed, {failed} failed out of {len(test_cases)} total")
    print("=" * 80)

    if failures:
        print("\n❌ FAILED TESTS:")
        print("-" * 80)
        for failure in failures:
            print(f"❌ {failure['description']}")
            print(f"   Query: \"{failure['query']}\"")
            print(f"   Expected: {failure['expected']}")
            print(f"   Got: {failure['got']}")
            if failure['reasoning']:
                print(f"   Reasoning: {failure['reasoning']}")
            print()
    else:
        print("\n🎉 ALL TESTS PASSED!")
        print()
        print("Routing Summary:")
        print("✅ 'tell me more' (no project) → GPT (continuous conversation)")
        print("✅ 'Tell me about Brigade Avalon' → Database (specific project)")
        print("✅ Objections/advice → GPT (sales conversation)")
        print()
        print("Continuous Conversation Flow:")
        print("1. User: 'Show me 2BHK in Whitefield' → Database (search)")
        print("2. User: 'tell me more' → GPT (elaborate on results)")
        print("3. User: 'Tell me about Brigade Citrine' → Database (specific project)")
        print("4. User: 'Too expensive' → GPT (objection handling)")
        print("5. User: 'How can I afford this?' → GPT (budget advice)")

    return failed == 0


if __name__ == "__main__":
    success = test_continuous_conversation()
    sys.exit(0 if success else 1)
