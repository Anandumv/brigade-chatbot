import requests
import uuid
import time
import json
import sys

BASE_URL = "http://localhost:8000/api/chat/query"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"

class ComprehensiveTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        print(f"🔹 Test Session ID: {self.session_id}")
        self.results = []

    def log_result(self, name, passed, details=""):
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"[{status}] {name} {details}")
        self.results.append(passed)

    def test_query(self, name, query, filters=None, expected_intent=None, expected_chips=None, allowed_intents=None):
        print(f"\n{CYAN}--- {name} ---{RESET}")
        print(f"Query: \"{query}\"")
        if filters:
            print(f"Filters: {filters}")
        
        payload = {
            "query": query,
            "session_id": self.session_id,
            "user_id": "test_user_comprehensive",
            "filters": filters
        }
        
        try:
            start = time.time()
            response = requests.post(BASE_URL, json=payload)
            duration = round(time.time() - start, 2)
            
            if response.status_code == 200:
                data = response.json()
                intent = data.get('intent', 'unknown')
                actions = data.get('suggested_actions', [])
                answer = data.get('answer', '')
                
                print(f"Response Intent: {YELLOW}{intent}{RESET}")
                print(f"Chips: {actions}")
                print(f"Time: {duration}s")
                
                # Validation
                passed = True
                fail_reason = ""
                
                # 1. Intent Check
                if expected_intent and intent != expected_intent:
                    # Allow fuzzy match for intelligent intents
                    if "intelligent" in intent and expected_intent in intent:
                        pass
                    else:
                        passed = False
                        fail_reason += f"Expected intent {expected_intent}, got {intent}. "
                
                if allowed_intents and intent not in allowed_intents:
                     passed = False
                     fail_reason += f"Intent {intent} not in allowed list. "

                # 2. Chips Check
                if expected_chips:
                    found_chip = False
                    for chip in expected_chips:
                        if any(chip.lower() in a.lower() for a in actions):
                            found_chip = True
                            break
                    if not found_chip:
                        passed = False
                        fail_reason += f"Missing expected chips {expected_chips}. Got {actions}. "

                self.log_result(name, passed, fail_reason)
                return passed
            else:
                self.log_result(name, False, f"HTTP {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            self.log_result(name, False, f"Exception: {e}")
            return False

def run_suite():
    t = ComprehensiveTester()
    
    print(f"\n{YELLOW}=== PART 1: CORE SALES FLOWS & CHIPS ==={RESET}")
    # 1. Budget Objection
    t.test_query("Flow: Budget Objection", 
                 "That is too expensive for me", 
                 expected_intent="intelligent_sales_objection",
                 expected_chips=["Stick to budget", "Show slightly higher"])

    # 2. Location FAQ
    t.test_query("Flow: Location Concern", 
                 "Suggest another location please", 
                 expected_intent="intelligent_sales_faq",
                 expected_chips=["Stick to my location", "Show nearby areas"])

    # 3. Under Construction Objection
    t.test_query("Flow: Under Construction", 
                 "I am scared of construction delays", 
                 expected_intent="intelligent_sales_objection", 
                 expected_chips=["Show Ready Options", "Show RERA Proof"])

    # 4. Site Visit
    t.test_query("Flow: Site Visit Request", 
                 "I want to visit the site", 
                 expected_intent="intelligent_sales_faq", 
                 expected_chips=["Send Location", "Schedule Visit"])

    print(f"\n{YELLOW}=== PART 2: CORNER CASES ==={RESET}")
    # 5. Typos
    t.test_query("Case: Typos", 
                 "Show me aprtments in bngalore", 
                 expected_intent="property_search")

    # 6. Negation
    t.test_query("Case: Negation", 
                 "I do NOT want ready to move", 
                 allowed_intents=["intelligent_sales_objection", "intelligent_sales_faq"],
                 expected_chips=["Show RERA details", "Explain payment plan"]) # Should map to UC FAQ/Objection

    # 7. Slang (Constraint)
    t.test_query("Case: Slang", 
                 "I'm broke, give me cheap options", 
                 allowed_intents=["intelligent_sales_objection", "intelligent_sales_faq"])

    print(f"\n{YELLOW}=== PART 3: EXPLICIT FILTERS ==={RESET}")
    # 8. Filter Override
    t.test_query("Case: Filter Override", 
                 "Show me properties in Koramangala", 
                 filters={"location": "whitefield"},
                 expected_intent="property_search")
                 # Note: Verification of actual filter application requires mock DB check or robust answer parsing
                 # Here we just check it doesn't crash and returns search intent

    # Summary
    total = len(t.results)
    passed = sum(t.results)
    print("\n" + "="*40)
    print(f"FINAL SCORE: {passed}/{total} Passed")
    print("="*40)
    
    if passed == total:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    # Wait briefly for server if needed
    time.sleep(1)
    run_suite()
