#!/usr/bin/env python3
"""
Verification script for sales chatbot implementation.
Tests the sales conversation handler without requiring API keys.
"""

import sys
sys.path.insert(0, '/Users/anandumv/Downloads/chatbot/backend')

from services.sales_conversation import (
    sales_conversation, 
    SalesIntent, 
    get_filter_options,
    FAQ_RESPONSES,
    OBJECTION_RESPONSES
)

def test_faq_detection():
    """Test FAQ intent detection"""
    print("=" * 60)
    print("TEST 1: FAQ INTENT DETECTION")
    print("=" * 60)
    
    test_cases = [
        ("How can I stretch my budget?", SalesIntent.FAQ_BUDGET_STRETCH),
        ("Why should I consider other locations?", SalesIntent.FAQ_OTHER_LOCATION),
        ("Tell me about under construction projects", SalesIntent.FAQ_UNDER_CONSTRUCTION),
        ("Why is face to face meeting important?", SalesIntent.FAQ_FACE_TO_FACE_MEETING),
        ("Can you arrange a site visit?", SalesIntent.FAQ_SITE_VISIT),
        ("What does Pinclick do?", SalesIntent.FAQ_PINCLICK_VALUE),
    ]
    
    passed = 0
    for query, expected in test_cases:
        result = sales_conversation.classify_sales_intent(query)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        print(f"{status} '{query}' -> {result.value}")
    
    print(f"\nFAQ Detection: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_objection_detection():
    """Test objection intent detection"""
    print("\n" + "=" * 60)
    print("TEST 2: OBJECTION DETECTION")
    print("=" * 60)
    
    test_cases = [
        ("This is too expensive", SalesIntent.OBJECTION_BUDGET),
        ("I can't afford this price", SalesIntent.OBJECTION_BUDGET),
        ("The location is too far", SalesIntent.OBJECTION_LOCATION),
        ("I need immediate possession", SalesIntent.OBJECTION_POSSESSION),
        ("I don't trust under construction projects", SalesIntent.OBJECTION_UNDER_CONSTRUCTION),
    ]
    
    passed = 0
    for query, expected in test_cases:
        result = sales_conversation.classify_sales_intent(query)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        print(f"{status} '{query}' -> {result.value}")
    
    print(f"\nObjection Detection: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


def test_faq_responses():
    """Test FAQ response generation"""
    print("\n" + "=" * 60)
    print("TEST 3: FAQ RESPONSES")
    print("=" * 60)
    
    all_passed = True
    for intent in [
        SalesIntent.FAQ_BUDGET_STRETCH,
        SalesIntent.FAQ_OTHER_LOCATION,
        SalesIntent.FAQ_UNDER_CONSTRUCTION,
        SalesIntent.FAQ_FACE_TO_FACE_MEETING,
        SalesIntent.FAQ_SITE_VISIT,
        SalesIntent.FAQ_PINCLICK_VALUE,
    ]:
        if intent in FAQ_RESPONSES:
            response = FAQ_RESPONSES[intent]
            has_content = len(response) > 100
            has_emoji = any(ord(c) > 127 for c in response)
            has_cta = "?" in response.split("\n")[-3:]  # Has question at end
            
            status = "✅" if has_content and has_emoji else "❌"
            if not (has_content and has_emoji):
                all_passed = False
            print(f"{status} {intent.value}: {len(response)} chars, emoji={has_emoji}")
        else:
            print(f"❌ {intent.value}: Missing response!")
            all_passed = False
    
    return all_passed


def test_filter_options():
    """Test filter options"""
    print("\n" + "=" * 60)
    print("TEST 4: FILTER OPTIONS")
    print("=" * 60)
    
    options = get_filter_options()
    
    checks = [
        ("configurations", len(options["configurations"]) == 6),
        ("budget_ranges", len(options["budget_ranges"]) == 8),
        ("possession_years", len(options["possession_years"]) == 8),
        ("north_bangalore areas", len(options["locations"]["north_bangalore"]["areas"]) >= 6),
        ("east_bangalore areas", len(options["locations"]["east_bangalore"]["areas"]) >= 5),
    ]
    
    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        if not passed:
            all_passed = False
        print(f"{status} {name}: {'OK' if passed else 'FAIL'}")
    
    return all_passed


def test_handler_integration():
    """Test handler returns proper responses"""
    print("\n" + "=" * 60)
    print("TEST 5: HANDLER INTEGRATION")
    print("=" * 60)
    
    test_cases = [
        ("stretch budget", False),  # Should return response, not fallback
        ("schedule a meeting", False),
        ("too expensive", False),
        ("random question about weather", True),  # Should fallback
    ]
    
    passed = 0
    for query, expected_fallback in test_cases:
        response, intent, should_fallback = sales_conversation.handle_sales_query(query)
        
        if should_fallback == expected_fallback:
            passed += 1
            status = "✅"
        else:
            status = "❌"
        
        print(f"{status} '{query}': fallback={should_fallback} (expected {expected_fallback})")
    
    print(f"\nHandler Integration: {passed}/{len(test_cases)} passed")
    return passed == len(test_cases)


if __name__ == "__main__":
    print("\n🧪 SALES CHATBOT VERIFICATION TESTS\n")
    
    results = []
    results.append(("FAQ Detection", test_faq_detection()))
    results.append(("Objection Detection", test_objection_detection()))
    results.append(("FAQ Responses", test_faq_responses()))
    results.append(("Filter Options", test_filter_options()))
    results.append(("Handler Integration", test_handler_integration()))
    
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_passed = False
        print(f"{status}: {name}")
    
    print("\n" + ("🎉 ALL TESTS PASSED!" if all_passed else "⚠️ SOME TESTS FAILED"))
    sys.exit(0 if all_passed else 1)
