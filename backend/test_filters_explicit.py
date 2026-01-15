import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_explicit_filters():
    print("🔹 Testing Explicit Filters Payload...")
    
    # Case 1: Vague Query + Explicit Filter
    payload1 = {
        "query": "Show me flats",
        "filters": {
            "configuration": "3", # 3BHK
            "location": "whitefield"
        }
    }
    response1 = requests.post(f"{BASE_URL}/api/chat/query", json=payload1)
    if response1.status_code == 200:
        data = response1.json()
        print("\nTest 1: Vague Query ('Show me flats') + Filter (3BHK, Whitefield)")
        print(f"Status: {response1.status_code}")
        print(f"Intent: {data.get('intent')}")
        print(f"Answer Preview: {data.get('answer')[:100]}...")
        if "3BHK" in data.get('answer') or "Whitefield" in data.get('answer'):
            print("✅ PASS: Filters applied")
        else:
            print("⚠️ CHECK: Filters might not be applied")
    else:
        print(f"❌ FAIL: {response1.text}")

    # Case 2: Conflict (Filter should override NLP)
    payload2 = {
        "query": "Show me 2BHKs in Koramangala",
        "filters": {
            "configuration": "3", # Override with 3BHK
            "location": "whitefield" # Override with Whitefield
        }
    }
    response2 = requests.post(f"{BASE_URL}/api/chat/query", json=payload2)
    if response2.status_code == 200:
        data = response2.json()
        print("\nTest 2: Conflict ('2BHK in Koramangala') + Filter (3BHK, Whitefield)")
        print(f"Status: {response2.status_code}")
        print(f"Intent: {data.get('intent')}")
        print(f"Answer Preview: {data.get('answer')[:100]}...")
        # Should find Whitefield 3BHKs, not Koramangala 2BHKs
        if "Whitefield" in data.get('answer'):
             print("✅ PASS: Location Filter overrode NLP")
        else:
             print("⚠️ CHECK: Location Filter failed to override")
    else:
        print(f"❌ FAIL: {response2.text}")

if __name__ == "__main__":
    # Wait for server to restart
    print("Waiting for server...")
    time.sleep(5)
    try:
        test_explicit_filters()
    except Exception as e:
        print(f"Error: {e}")
