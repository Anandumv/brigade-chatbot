import requests
import uuid
import time
import json
import sys

# PRODUCTION URL
BASE_URL = "https://chatbot-production-aaa8.up.railway.app/api/chat/query"

class FlowVerifier:
    def __init__(self, scenario_name):
        self.session_id = str(uuid.uuid4())
        self.scenario_name = scenario_name
        self.step_count = 0
        print(f"\n==================================================")
        print(f"🧪 SCENARIO: {scenario_name}")
        print(f"   Session ID: {self.session_id}")
        print(f"==================================================")

    def step(self, user_input, expected_description=None):
        self.step_count += 1
        print(f"\n[Step {self.step_count}] User: \"{user_input}\"")
        
        payload = {
            "query": user_input,
            "session_id": self.session_id,
            "user_id": "verifier_bot"
        }
        
        try:
            start = time.time()
            response = requests.post(BASE_URL, json=payload, timeout=30)
            duration = round(time.time() - start, 2)
            
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', '')
                intent = data.get('intent', 'unknown')
                
                print(f"   Bot ({duration}s): {answer}")
                print(f"   Intent: ► {intent}")
                
                if expected_description:
                    print(f"   (Expected: {expected_description})")
                
                return intent
            else:
                print(f"❌ Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Crash: {e}")
            return None

def run_all():
    print(f"🚀 RUNNING DEEP SYSTEM TEST (Using Live Data: 'Sattva Songbird')\n")

    # --- SCENARIO 1: The Happy Path (Exact Match) ---
    s1 = FlowVerifier("Happy Path (Node 1 -> Node 2)")
    # 1. Provide Details -> Should trigger Node 2 (Matches)
    # Data: Sattva Songbird is 2BHK ~1.4Cr in Budigere Cross
    s1.step("I want a 2BHK in Budigere Cross under 1.6 Cr", "Show 'Sattva Songbird'")


    # --- SCENARIO 2: Budget Objection (Upsell -> Pitch) ---
    s2 = FlowVerifier("Budget Negotiation Flow")
    # 1. Ask for something too cheap for the area/config
    # 3BHK in Sattva is ~1.95 Cr. We ask for 1.2 Cr.
    s2.step("Show me 3BHK in Budigere Cross under 1.2 Cr", "No Matches / Upsell")
    
    # 2. Bot might show Upsell (Node 4) or Fail.
    # User objects to price if shown, or just says "Too expensive" generally.
    s2.step("That is too expensive, I have strict budget", "Suggest Budget Stretch")
    
    # 3. Acceptance -> Node 5 (Persuasion)
    s2.step("Why should I stretch my budget?", "Persuasion Pitch (ROI/EMI)")


    # --- SCENARIO 3: Possession Objection (UC vs RTM) ---
    s3 = FlowVerifier("Possession Timeline Flow")
    # 1. Ask for specific project (known Under Construction - 2029)
    s3.step("Is Sattva Songbird ready to move?", "Show Status / Node 2")
    
    # 2. Reject UC -> Node 9 (Pitch UC Benefits)
    s3.step("I cannot wait till 2029, I need immediate possession", "Pitch UC Benefits (Price/Appreciation)")


    # --- SCENARIO 4: The 'Vague' Entry ---
    s4 = FlowVerifier("Vague Entry -> Requirement Gathering")
    s4.step("I am looking for an apartment", "Ask Config/Loc/Budget (Node 1)")
    s4.step("In East Bangalore", "Update State, Ask Missing")

if __name__ == "__main__":
    run_all()
