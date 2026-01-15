import requests
import uuid
import time
import json
import sys

BASE_URL = "http://localhost:8000/api/chat/query"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RESET = "\033[0m"

class SpectrumTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        print(f"🔹 Test Session ID: {self.session_id}")

    def test_query(self, category, query, expected_intent=None, min_len=10):
        print(f"\n{YELLOW}--- Testing {category} ---{RESET}")
        print(f"Query: {query}")
        
        payload = {
            "query": query,
            "session_id": self.session_id,
            "user_id": "test_user_spectrum"
        }
        
        start = time.time()
        try:
            response = requests.post(BASE_URL, json=payload)
            duration = round(time.time() - start, 2)
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                intent = data.get('intent', 'unknown')
                
                print(f"Status: {GREEN}200 OK{RESET} ({duration}s)")
                print(f"Intent: {intent}")
                print(f"Answer Snippet: {answer[:100]}...")
                
                # Validation
                passed = True
                if expected_intent and intent != expected_intent:
                    print(f"{RED}FAILED: Expected intent '{expected_intent}', got '{intent}'{RESET}")
                    passed = False
                
                if len(answer) < min_len:
                    print(f"{RED}FAILED: Answer too short ({len(answer)} chars){RESET}")
                    passed = False
                    
                if passed:
                    print(f"{GREEN}✅ PASS{RESET}")
                    return True
                else:
                    return False
            else:
                print(f"{RED}ERROR: Status {response.status_code}{RESET}")
                print(response.text)
                return False
                
        except Exception as e:
            print(f"{RED}EXCEPTION: {e}{RESET}")
            return False

def run_suite():
    tester = SpectrumTester()
    results = []

    # 1. SIMPLE: Greeting
    results.append(tester.test_query(
        "Level 1: Greeting", 
        "Hi, good morning!", 
        expected_intent="greeting"
    ))

    # 2. SIMPLE: Project Fact (RAG Validation)
    results.append(tester.test_query(
        "Level 2: Factual Question", 
        "Where is Brigade Citrine located?", 
        expected_intent="project_fact" # Or property_search depending on classifier config
    ))

    # 3. INTERMEDIATE: Simple Search
    results.append(tester.test_query(
        "Level 3: Simple Filter", 
        "Show me 2BHK flats in Whitefield", 
        expected_intent="property_search"
    ))

    # 4. ADVANCED: Complex Filtering
    results.append(tester.test_query(
        "Level 4: Complex Filter", 
        "Villas under 3 Cr near Airport ready to move", 
        expected_intent="property_search"
    ))

    # 5. COMPLEX: Objection Handling (Budget)
    results.append(tester.test_query(
        "Level 5: Objection (Budget)", 
        "That is way too expensive for me", 
        expected_intent="intelligent_sales_objection"
    ))

    # 6. COMPLEX: Conversational Context (Follow-up)
    results.append(tester.test_query(
        "Level 6: Contextual Follow-up", 
        "How can I stretch my budget then?", 
        expected_intent="intelligent_sales_faq"
    ))

    print("\n" + "="*30)
    print(f"TEST SUMMARY: {sum(results)}/{len(results)} PASSED")
    print("="*30)
    
    if all(results):
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    run_suite()
