import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_dynamic_chips():
    print("🔹 Testing Dynamic Chips (Suggested Actions)...")
    
    # helper to test query and check for chips
    def check_query(query, expected_chip_partial):
        print(f"\nSending Query: '{query}'")
        try:
            response = requests.post(f"{BASE_URL}/api/chat/query", json={"query": query})
            if response.status_code == 200:
                data = response.json()
                intent = data.get('intent')
                actions = data.get('suggested_actions', [])
                print(f"Status: {response.status_code}")
                print(f"Intent: {intent}")
                print(f"Suggested Actions: {actions}")
                
                if actions and any(expected_chip_partial.lower() in a.lower() for a in actions):
                    print(f"✅ PASS: Found chip containing '{expected_chip_partial}'")
                    return True
                else:
                    print(f"⚠️ FAIL: Did not find chip containing '{expected_chip_partial}'")
                    return False
            else:
                print(f"❌ ERROR: {response.text}")
                return False
        except Exception as e:
            print(f"❌ EXCEPTION: {e}")
            return False

    # Test 1: Budget Objection
    check_query("It is too expensive for me", "Stick to budget")

    # Test 2: Location FAQ
    check_query("Suggest another location", "Stick to my location")

    # Test 3: Site Visit
    check_query("I want to visit", "Send Location")

if __name__ == "__main__":
    print("Waiting for server...")
    time.sleep(5)
    test_dynamic_chips()
