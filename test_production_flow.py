import requests
import json
import time
import sys

# Production URL from test_phase1_fixes.sh
BASE_URL = "https://brigade-chatbot-production.up.railway.app/api/assist/"
CALL_ID = f"prod-test-{int(time.time())}"

R = "\033[91m"
G = "\033[92m"
Y = "\033[93m"
RESET = "\033[0m"

def send_message(query):
    print(f"\n{Y}User: {query}{RESET}")
    payload = {
        "call_id": CALL_ID,
        "query": query
    }
    start = time.time()
    try:
        res = requests.post(BASE_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=60)
        dur = time.time() - start
        if res.status_code == 200:
            data = res.json()
            # The API returns 'system_action' or text in some field? 
            # Based on flow_engine, it returns FlowResponse, but likely wrapped by API.
            # Let's inspect raw response if needed.
            # Assuming standard structure based on previous tests.
            print(f"{G}Bot ({dur:.2f}s):{RESET} {json.dumps(data, indent=2)}")
            return data
        else:
            print(f"{R}Error {res.status_code}: {res.text}{RESET}")
            return None
    except Exception as e:
        print(f"{R}Exception: {e}{RESET}")
        return None

def run_flow():
    print(f"Starting Production Flow Test on {BASE_URL}")
    print(f"Session ID: {CALL_ID}")

    # 1. Discovery
    # Expect: List of projects in Whitefield
    resp = send_message("Show me 3BHK flats in Whitefield under 2 Cr")
    target_project = "Brigade Sanctuary" # Default
    
    if resp and "Whitefield" in str(resp):
        print(f"{G}✓ Context Set: Location=Whitefield{RESET}")
        # Try to extract a valid project name from response to use in next step
        try:
            # Look for project name in "answer" or "projects"
            if "projects" in resp and len(resp["projects"]) > 0:
                target_project = resp["projects"][0]["name"]
                print(f"  Selected Project for details: {target_project}")
            elif "answer" in resp and isinstance(resp["answer"], list):
                # Naive parse from text "Prestige Glenbrook offers..."
                import re
                m = re.search(r'\*\*(.*?)\*\*', resp["answer"][0])
                if m:
                    target_project = m.group(1)
                    print(f"  Selected Project from text: {target_project}")
        except:
            pass
    else:
        print(f"{R}✗ Failed to set context{RESET}")

    # 2. Radius Search (Contextual)
    # Expect: "Nearby" results using Whitefield context
    resp = send_message("Anything nearby?")
    if resp and ("within" in str(resp) or "nearby" in str(resp) or "distance" in str(resp)):
        print(f"{G}✓ Radius Search worked (Context maintained){RESET}")
    else:
        print(f"{R}✗ Radius Search failed or Context lost{RESET}")

    # 3. Specific Pitch
    # Expect: Details of a specific project found in previous steps
    resp = send_message(f"Tell me about {target_project}")
    if resp and ("Amenities" in str(resp) or "Price" in str(resp) or "Location" in str(resp)):
        print(f"{G}✓ Specific Pitch retrieved for {target_project}{RESET}")
    else:
        print(f"{R}✗ Specific Pitch failed for {target_project}{RESET}")

    # 4. Comparison
    # Expect: Persuasive text
    resp = send_message(f"Compare {target_project} with Sarjapur")
    if resp and "Sarjapur" in str(resp):
         print(f"{G}✓ Comparison logic worked{RESET}")
    else:
         print(f"{R}✗ Comparison failed{RESET}")

if __name__ == "__main__":
    run_flow()
