import requests
import json
import time

BASE_URL = "http://localhost:8000/api/chat/query"

test_cases = [
    # --- Filter Flow Tests ---
    {
        "name": "Filter - Villa & Location",
        "query": "Show me 4BHK villas in Whitefield",
        "expected_checks": lambda r: "villa" in str(r.get('answer', '')).lower() or "brigade" in str(r.get('answer', '')).lower()
    },
    {
        "name": "Filter - Budget & Status",
        "query": "Ready to move flats under 1.5 Cr in Bangalore",
        "expected_checks": lambda r: "1.5" in str(r) or "ready" in str(r)
    },
    {
        "name": "Filter - Plot",
        "query": "Any plots available near Airport?",
        "expected_checks": lambda r: "plot" in str(r).lower()
    },
    
    # --- Response Flow / FAQ Tests ---
    {
        "name": "FAQ - Budget Objection",
        "query": "This is too expensive for me, I have a tight budget",
        "expected_checks": lambda r: "stretch" in r.get('answer', '').lower() or "emi" in r.get('answer', '').lower()
    },
    {
        "name": "FAQ - Under Construction Objection",
        "query": "I don't want under construction, I need immediate possession",
        "expected_checks": lambda r: "appreciation" in r.get('answer', '').lower() or "save" in r.get('answer', '').lower()
    },
    {
        "name": "FAQ - Location Switch",
        "query": "I prefer Indiranagar, this is too far",
        "expected_checks": lambda r: "commute" in r.get('answer', '').lower() or "growth" in r.get('answer', '').lower()
    },
    {
        "name": "FAQ - Face to Face",
        "query": "Why do I need to meet you? Can't you send details on WhatsApp?",
        "expected_checks": lambda r: "personalized" in r.get('answer', '').lower() or "exclusive" in r.get('answer', '').lower()
    },
    {
        "name": "FAQ - Pinclick Value",
        "query": "Why should I buy through Pinclick and not directly?",
        "expected_checks": lambda r: "unbiased" in r.get('answer', '').lower() or "0%" in r.get('answer', '').lower() or "free" in r.get('answer', '').lower()
    }
]

print(f"Running {len(test_cases)} tests against {BASE_URL}...\n")

for i, test in enumerate(test_cases):
    print(f"Test {i+1}: {test['name']}")
    print(f"Query: {test['query']}")
    
    try:
        start_time = time.time()
        response = requests.post(
            BASE_URL, 
            json={"query": test['query']},
            headers={"Content-Type": "application/json"}
        )
        duration = round(time.time() - start_time, 2)
        
        if response.status_code == 200:
            result = response.json()
            answer = result.get('answer', 'No answer')
            print(f"Status: {response.status_code} ({duration}s)")
            print(f"Intent: {result.get('intent', 'N/A')}")
            print(f"Answer Snippet: {answer[:150]}...")
            
            # Simple validation check
            try:
                if test['expected_checks'](result):
                    print("✅ PASS")
                else:
                    print("⚠️  CHECK - content might differ from expectation")
            except Exception as e:
                print(f"⚠️  Check failed: {e}")
                
        else:
            print(f"❌ FAIL: Status {response.status_code}")
            print(response.text)
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        
    print("-" * 50)
    time.sleep(1)
