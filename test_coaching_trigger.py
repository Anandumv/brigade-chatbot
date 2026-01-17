"""Test script to verify coaching triggers"""

import requests
import json

# Your deployed backend URL
BACKEND_URL = "https://chatbot-production-c158.up.railway.app"

# Create a session to maintain cookies/session_id
session = requests.Session()

def test_coaching():
    """Test coaching with multiple messages"""
    
    print("=" * 60)
    print("Testing Sales Coaching System")
    print("=" * 60)
    
    # Test 1: First query (should be discovery stage)
    print("\n📝 Test 1: Initial query (discovery stage)")
    response1 = session.post(
        f"{BACKEND_URL}/api/chat/query",
        json={
            "query": "Show me 2BHK apartments in Whitefield under 2 Cr",
            "user_id": "test_salesman_123",
            "session_id": "coaching_test_session_001"
        }
    )
    
    print(f"Status: {response1.status_code}")
    data1 = response1.json()
    print(f"Answer preview: {data1.get('answer', '')[:100]}...")
    print(f"Coaching prompt: {data1.get('coaching_prompt')}")
    
    # Test 2: Ask about specific project (evaluation stage)
    print("\n📝 Test 2: Ask about specific project")
    response2 = session.post(
        f"{BACKEND_URL}/api/chat/query",
        json={
            "query": "Tell me about Brigade Citrine",
            "user_id": "test_salesman_123",
            "session_id": "coaching_test_session_001"
        }
    )
    
    print(f"Status: {response2.status_code}")
    data2 = response2.json()
    print(f"Answer preview: {data2.get('answer', '')[:100]}...")
    print(f"Coaching prompt: {data2.get('coaching_prompt')}")
    
    # Test 3: Ask detailed question (high engagement)
    print("\n📝 Test 3: Detailed question (high engagement)")
    response3 = session.post(
        f"{BACKEND_URL}/api/chat/query",
        json={
            "query": "What are the amenities in Brigade Citrine?",
            "user_id": "test_salesman_123",
            "session_id": "coaching_test_session_001"
        }
    )
    
    print(f"Status: {response3.status_code}")
    data3 = response3.json()
    print(f"Answer preview: {data3.get('answer', '')[:100]}...")
    print(f"Coaching prompt: {data3.get('coaching_prompt')}")
    
    # Test 4: Another project (should trigger multi-project coaching)
    print("\n📝 Test 4: View another project")
    response4 = session.post(
        f"{BACKEND_URL}/api/chat/query",
        json={
            "query": "Tell me about Prestige Lakeside Habitat",
            "user_id": "test_salesman_123",
            "session_id": "coaching_test_session_001"
        }
    )
    
    print(f"Status: {response4.status_code}")
    data4 = response4.json()
    print(f"Answer preview: {data4.get('answer', '')[:100]}...")
    print(f"Coaching prompt: {data4.get('coaching_prompt')}")
    
    # Test 5: Ask about possession (should trigger site visit coaching)
    print("\n📝 Test 5: Ask about possession (should trigger site visit)")
    response5 = session.post(
        f"{BACKEND_URL}/api/chat/query",
        json={
            "query": "When is the possession date?",
            "user_id": "test_salesman_123",
            "session_id": "coaching_test_session_001"
        }
    )
    
    print(f"Status: {response5.status_code}")
    data5 = response5.json()
    print(f"Answer preview: {data5.get('answer', '')[:100]}...")
    print(f"Coaching prompt: {data5.get('coaching_prompt')}")
    
    # Test 6: Budget objection
    print("\n📝 Test 6: Budget objection")
    response6 = session.post(
        f"{BACKEND_URL}/api/chat/query",
        json={
            "query": "This seems too expensive",
            "user_id": "test_salesman_123",
            "session_id": "coaching_test_session_001"
        }
    )
    
    print(f"Status: {response6.status_code}")
    data6 = response6.json()
    print(f"Answer preview: {data6.get('answer', '')[:100]}...")
    print(f"Coaching prompt: {data6.get('coaching_prompt')}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_coaching()
