import requests
import uuid
import time
import json

BASE_URL = "http://localhost:8000/api/chat/query"

class ConversationTester:
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        print(f"🔹 Starting new conversation session: {self.session_id}")

    def send_message(self, query):
        payload = {
            "query": query,
            "session_id": self.session_id,
            "user_id": "test_user"
        }
        start = time.time()
        try:
            response = requests.post(BASE_URL, json=payload)
            duration = round(time.time() - start, 2)
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n👤 User: {query}")
                print(f"🤖 Bot ({duration}s): {data.get('answer')[:150]}...")
                print(f"   [Intent: {data.get('intent')}]")
                return data
            else:
                print(f"❌ Error {response.status_code}: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return None

def run_tests():
    print("🚀 STARTING COMPLETENESS TEST (FLOWCHART SCENARIOS)\n")
    
    # --- SCENARIO 1: Budget Flow ---
    print("\n📝 SCENARIO 1: Budget Negotiation Flow")
    tester = ConversationTester()
    
    # 1. Ask for property
    tester.send_message("I am looking for 3BHK flats in Whitefield")
    
    # 2. Raise Objection (Budget)
    tester.send_message("That is above my budget of 1 Cr")
    
    # 3. Bot should Suggest Stretch -> User Agrees
    tester.send_message("Okay, how can I stretch my budget?")
    
    
    # --- SCENARIO 2: Location Switch Flow ---
    print("\n📝 SCENARIO 2: Location Switch Flow")
    tester = ConversationTester()
    
    # 1. Ask for expensive location
    tester.send_message("Show me apartments in Indiranagar")
    
    # 2. Bot likely shows nothing or expensive -> User complains
    tester.send_message("This location is too congested and expensive")
    
    # 3. Bot Pitches Alternative (Growth) -> User Hesitates
    # 4. CTA: Site Visit
    tester.send_message("I prefer Indiranagar though")


    # --- SCENARIO 3: Under Construction Flow ---
    print("\n📝 SCENARIO 3: Under Construction vs Ready Flow")
    tester = ConversationTester()
    
    # 1. Ask for Ready
    tester.send_message("Show me ready to move 2BHK in North Bangalore")
    
    # 2. Objection to UC
    tester.send_message("I don't want under construction, I need it now")
    
    # 3. Bot Pitches UC Benefits -> CTA
    
    
    # --- SCENARIO 4: Trust/Meeting Flow ---
    print("\n📝 SCENARIO 4: Trust & Meeting Flow")
    tester = ConversationTester()
    
    # 1. Ask about Pinclick
    tester.send_message("Why should I buy through Pinclick?")
    
    # 2. Ask for details on WhatsApp (Avoid meeting)
    tester.send_message("Can't you just send details on WhatsApp?")
    
    # 3. Bot Pitches F2F -> User Agrees
    tester.send_message("Okay let's meet tomorrow")

if __name__ == "__main__":
    run_tests()
