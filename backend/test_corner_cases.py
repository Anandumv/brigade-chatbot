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

class CornerCaseTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        print(f"🔹 Session: {self.session_id}")

    def test(self, name, query, expected_intent=None, allowed_intents=None):
        print(f"\n{YELLOW}--- {name} ---{RESET}")
        print(f"Query: {query}")
        
        payload = {
            "query": query,
            "session_id": self.session_id,
            "user_id": "test_user_corner"
        }
        
        try:
            start = time.time()
            response = requests.post(BASE_URL, json=payload)
            duration = round(time.time() - start, 2)
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                intent = data.get('intent', 'unknown')
                
                print(f"Status: {GREEN}200 OK{RESET} ({duration}s)")
                print(f"Intent: {intent}")
                print(f"Answer Snippet: {answer[:100]}...")
                
                # Logic to validate result
                passed = False
                if expected_intent and intent == expected_intent:
                    passed = True
                elif allowed_intents and intent in allowed_intents:
                    passed = True
                elif not expected_intent and not allowed_intents:
                    passed = True # Just checking for crash
                    
                if passed:
                    print(f"{GREEN}✅ PASS{RESET}")
                else:
                    print(f"{RED}⚠️ CHECK: Got '{intent}' (Expected: {expected_intent or allowed_intents}){RESET}")
                
            else:
                print(f"{RED}❌ ERROR {response.status_code}: {response.text[:200]}{RESET}")

        except Exception as e:
            print(f"{RED}❌ EXCEPTION: {e}{RESET}")

def run_suite():
    t = CornerCaseTester()
    
    # 1. Spelling & Typos
    t.test("Typos", "Show me flats in Whiefield Banglore", expected_intent="property_search")
    
    # 2. Slang / Colloquial logic
    t.test("Slang Budget", "I have 80 big ones", expected_intent="property_search") # Likely fails extraction but intent should be search/sales
    
    # 3. Compound Objection
    t.test("Compound Obj", "It's too far and way too expensive", allowed_intents=["intelligent_sales_objection", "sales_objection"])
    
    # 4. Negation (Hardest for NLP)
    t.test("Negation", "I do NOT want under construction", allowed_intents=["intelligent_sales_faq", "intelligent_sales_objection", "sales_objection"])
    
    # 5. Vague / Broad
    t.test("Vague", "I need a place to live", allowed_intents=["property_search", "sales_faq"])
    
    # 6. Emotional / Subjective
    t.test("Emotional", "I am scared the project will be delayed", expected_intent="intelligent_sales_objection")
    
    # 7. Comparison
    t.test("Comparison", "Is Brigade better or Prestige?", expected_intent="comparison")
    
    # 8. Mixed Intent (Price + Opinion)
    t.test("Mixed Intent", "What is the price of 3BHK and is it a good investment?", allowed_intents=["project_fact", "sales_faq", "unsupported"])

if __name__ == "__main__":
    run_suite()
