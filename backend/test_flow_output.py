#!/usr/bin/env python3
"""
Quick test to verify flow engine returns complete property details.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from services.flow_engine import flow_engine

def test_property_search():
    """Test that property search returns complete details."""
    print("=" * 80)
    print("Testing Flow Engine - Property Search with Complete Details")
    print("=" * 80)

    # Test query similar to the screenshot
    test_query = "3BHK in Whitefield under 1.5 Cr"
    session_id = "test_session_123"

    print(f"\nQuery: {test_query}")
    print(f"Session ID: {session_id}")
    print("\n" + "-" * 80)

    # Process the query
    response = flow_engine.process(session_id, test_query)

    print(f"\nCurrent Node: {response.current_node}")
    print(f"Next Redirection: {response.next_redirection}")
    print(f"\nExtracted Requirements:")
    print(response.extracted_requirements)
    print("\n" + "-" * 80)
    print("\nSystem Action (Response to User):")
    print("-" * 80)
    print(response.system_action)
    print("-" * 80)

    # Verify we got detailed information
    action_text = response.system_action
    has_details = any([
        "📍" in action_text,  # Location emoji
        "💰" in action_text,  # Price emoji
        "🏠" in action_text,  # Configuration emoji
        "Location:" in action_text,
        "Price Range:" in action_text,
        "Configuration:" in action_text
    ])

    if has_details:
        print("\n✅ SUCCESS: Response contains detailed property information!")
    else:
        print("\n❌ FAILED: Response lacks detailed property information")
        print("   Expected: Location, Price, Configuration, etc.")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_property_search()
