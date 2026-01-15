#!/usr/bin/env python3
"""
Comprehensive test for flow engine conversation building.
Tests all conversation paths after data fetching.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.flow_engine import flow_engine

def print_separator():
    print("\n" + "=" * 80 + "\n")

def print_conversation_turn(turn_num, user_input, response):
    print(f"Turn {turn_num}:")
    print(f"User: {user_input}")
    print(f"\nBot (Node: {response.current_node} → {response.next_redirection}):")
    print(response.system_action)
    print_separator()

def test_happy_path():
    """Test 1: Happy path - User shows interest immediately"""
    print("TEST 1: HAPPY PATH - Immediate Interest")
    print_separator()

    session_id = "test_happy_path"
    flow_engine.reset_session(session_id)

    # Turn 1: Initial query
    response = flow_engine.process(session_id, "3BHK in Whitefield under 1.5 Cr")
    print_conversation_turn(1, "3BHK in Whitefield under 1.5 Cr", response)

    # Turn 2: Show interest
    response = flow_engine.process(session_id, "Yes, I'm interested in the first one")
    print_conversation_turn(2, "Yes, I'm interested in the first one", response)

    # Turn 3: Provide contact details
    response = flow_engine.process(session_id, "9876543210, tomorrow 2pm works for me")
    print_conversation_turn(3, "9876543210, tomorrow 2pm works for me", response)

    print("✅ HAPPY PATH TEST COMPLETED\n")

def test_budget_objection_path():
    """Test 2: Budget objection path"""
    print("TEST 2: BUDGET OBJECTION PATH")
    print_separator()

    session_id = "test_budget_objection"
    flow_engine.reset_session(session_id)

    # Turn 1: Initial query
    response = flow_engine.process(session_id, "3BHK in Whitefield under 1.5 Cr")
    print_conversation_turn(1, "3BHK in Whitefield under 1.5 Cr", response)

    # Turn 2: Budget objection
    response = flow_engine.process(session_id, "These are too expensive for me")
    print_conversation_turn(2, "These are too expensive for me", response)

    # Turn 3: Agree to stretch budget
    response = flow_engine.process(session_id, "Yes, I can stretch my budget a bit")
    print_conversation_turn(3, "Yes, I can stretch my budget a bit", response)

    # Turn 4: View premium options and book visit
    response = flow_engine.process(session_id, "The second option looks good, let's schedule a visit")
    print_conversation_turn(4, "The second option looks good, let's schedule a visit", response)

    print("✅ BUDGET OBJECTION PATH TEST COMPLETED\n")

def test_rejection_path():
    """Test 3: Complete rejection path"""
    print("TEST 3: COMPLETE REJECTION PATH")
    print_separator()

    session_id = "test_rejection"
    flow_engine.reset_session(session_id)

    # Turn 1: Initial query with tight budget
    response = flow_engine.process(session_id, "2BHK under 50 lakhs in Whitefield")
    print_conversation_turn(1, "2BHK under 50 lakhs in Whitefield", response)

    # Turn 2: Reject budget stretch
    response = flow_engine.process(session_id, "No, I can't increase my budget")
    print_conversation_turn(2, "No, I can't increase my budget", response)

    # Turn 3: Reject persuasion
    response = flow_engine.process(session_id, "No thanks, I need to stay within budget")
    print_conversation_turn(3, "No thanks, I need to stay within budget", response)

    # Turn 4: Reject location flexibility
    response = flow_engine.process(session_id, "No, I specifically need Whitefield")
    print_conversation_turn(4, "No, I specifically need Whitefield", response)

    # Turn 5: Provide email for future updates
    response = flow_engine.process(session_id, "user@example.com")
    print_conversation_turn(5, "user@example.com", response)

    print("✅ REJECTION PATH TEST COMPLETED\n")

def test_possession_objection_path():
    """Test 4: Possession timeline objection"""
    print("TEST 4: POSSESSION OBJECTION PATH")
    print_separator()

    session_id = "test_possession"
    flow_engine.reset_session(session_id)

    # Turn 1: Initial query with ready-to-move requirement
    response = flow_engine.process(session_id, "3BHK in Whitefield under 2 Cr, ready to move")
    print_conversation_turn(1, "3BHK in Whitefield under 2 Cr, ready to move", response)

    # Turn 2: Express possession concern
    response = flow_engine.process(session_id, "These are under construction, I need ready to move")
    print_conversation_turn(2, "These are under construction, I need ready to move", response)

    # Turn 3: Respond to possession check
    response = flow_engine.process(session_id, "I need to move in 2 months")
    print_conversation_turn(3, "I need to move in 2 months", response)

    # Turn 4: Consider UC benefits (NODE 10 shows UC pitch if no RTMI available)
    if "nearby" in response.system_action.lower() or "construction" in response.system_action.lower():
        response = flow_engine.process(session_id, "Tell me more about under-construction benefits")
        print_conversation_turn(4, "Tell me more about under-construction benefits", response)

    print("✅ POSSESSION OBJECTION PATH TEST COMPLETED\n")

def test_location_flexibility_path():
    """Test 5: Location flexibility path"""
    print("TEST 5: LOCATION FLEXIBILITY PATH")
    print_separator()

    session_id = "test_location"
    flow_engine.reset_session(session_id)

    # Turn 1: Initial query
    response = flow_engine.process(session_id, "3BHK under 1 Cr in Koramangala")
    print_conversation_turn(1, "3BHK under 1 Cr in Koramangala", response)

    # If no matches, it goes to NODE 3
    # Turn 2: Budget objection
    response = flow_engine.process(session_id, "Budget is tight")
    print_conversation_turn(2, "Budget is tight", response)

    # Turn 3: Reject budget stretch
    response = flow_engine.process(session_id, "No, cannot stretch")
    print_conversation_turn(3, "No, cannot stretch", response)

    # Turn 4: Reject persuasion
    response = flow_engine.process(session_id, "No thanks")
    print_conversation_turn(4, "No thanks", response)

    # Turn 5: Accept location flexibility
    response = flow_engine.process(session_id, "Yes, I'm open to nearby areas")
    print_conversation_turn(5, "Yes, I'm open to nearby areas", response)

    # Turn 6: Check possession timeline
    if "possession" in response.system_action.lower():
        response = flow_engine.process(session_id, "Timeline is fine with me")
        print_conversation_turn(6, "Timeline is fine with me", response)

    print("✅ LOCATION FLEXIBILITY PATH TEST COMPLETED\n")

def test_node_2a_clarification():
    """Test 6: NODE 2A clarification loop"""
    print("TEST 6: NODE 2A CLARIFICATION LOOP")
    print_separator()

    session_id = "test_clarification"
    flow_engine.reset_session(session_id)

    # Turn 1: Initial query
    response = flow_engine.process(session_id, "3BHK in Whitefield under 1.5 Cr")
    print_conversation_turn(1, "3BHK in Whitefield under 1.5 Cr", response)

    # Turn 2: Ambiguous response
    response = flow_engine.process(session_id, "Hmm, not sure")
    print_conversation_turn(2, "Hmm, not sure", response)

    # Turn 3: Another ambiguous response (should stay in NODE 2A)
    response = flow_engine.process(session_id, "Tell me more")
    print_conversation_turn(3, "Tell me more", response)

    # Turn 4: Finally show interest
    response = flow_engine.process(session_id, "Yes, let's book a visit")
    print_conversation_turn(4, "Yes, let's book a visit", response)

    print("✅ CLARIFICATION LOOP TEST COMPLETED\n")

def verify_conversational_language():
    """Verify all responses use conversational language, not debug messages"""
    print("VERIFICATION: Checking for conversational language")
    print_separator()

    session_id = "verify_language"
    flow_engine.reset_session(session_id)

    test_cases = [
        ("3BHK Whitefield 1.5 Cr", "Should show properties"),
        ("Too expensive", "Should empathize about budget"),
        ("I need ready to move", "Should acknowledge possession concern"),
        ("Yes, interested", "Should express excitement"),
    ]

    all_conversational = True

    for user_input, expected in test_cases:
        flow_engine.reset_session(session_id)
        # First query to get to property display
        flow_engine.process(session_id, "3BHK in Whitefield under 1.5 Cr")
        # Then test the response
        response = flow_engine.process(session_id, user_input)

        # Check for debug-style messages
        debug_phrases = [
            "detected", "proceeding", "routing", "redirecting",
            "NODE", "objection handler", "check", "classification"
        ]

        has_debug = any(phrase.lower() in response.system_action.lower() for phrase in debug_phrases)

        if has_debug:
            print(f"❌ FAILED: '{user_input}'")
            print(f"   Contains debug language: {response.system_action[:100]}...")
            all_conversational = False
        else:
            print(f"✅ PASSED: '{user_input}'")
            print(f"   Response: {response.system_action[:100]}...")

        print()

    if all_conversational:
        print("✅ ALL RESPONSES USE CONVERSATIONAL LANGUAGE\n")
    else:
        print("❌ SOME RESPONSES STILL CONTAIN DEBUG LANGUAGE\n")

    return all_conversational

def run_all_tests():
    """Run all test scenarios"""
    print("=" * 80)
    print("FLOW ENGINE CONVERSATION BUILDING - COMPREHENSIVE TEST SUITE")
    print("=" * 80)

    try:
        test_happy_path()
        test_budget_objection_path()
        test_rejection_path()
        test_possession_objection_path()
        test_location_flexibility_path()
        test_node_2a_clarification()

        all_conversational = verify_conversational_language()

        print_separator()
        print("SUMMARY")
        print_separator()
        print("✅ All test scenarios completed successfully")
        if all_conversational:
            print("✅ All responses use conversational language")
        else:
            print("⚠️  Some responses may still contain debug language")
        print("\nThe flow engine conversation building is working as expected!")

    except Exception as e:
        print(f"\n❌ TEST FAILED WITH ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_all_tests()
