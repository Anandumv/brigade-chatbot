import requests
import json
import sys

BASE_URL = "http://localhost:8000/api/chat/query"

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"

def run_test(name, payload, expected_check):
    print(f"Testing: {name}...", end=" ")
    try:
        response = requests.post(BASE_URL, json=payload)
        # response.raise_for_status() 
        try:
            data = response.json()
        except:
             print(f"{RED}FAILED{RESET} (Non-JSON)")
             return False
             
        if response.status_code != 200:
             print(f"{RED}FAILED{RESET} (HTTP {response.status_code})")
             if "detail" in data:
                 print(f"  Error: {data['detail']}")
             return False

        if expected_check(data):
            print(f"{GREEN}PASSED{RESET}")
            return True
        else:
            print(f"{RED}FAILED{RESET}")
            return False
    except Exception as e:
        print(f"{RED}ERROR{RESET}: {e}")
        return False

def check_projects_contain(keywords):
    def _check(data):
        projects = data.get("projects") or []
        if not projects:
            print(f"  No projects returned.")
            return False
            
        found_names = [p['project_name'] for p in projects]
        # Check if ANY of the keywords match ANY project name (substring)
        # Or simpler: Ensure we found something relevant
        print(f"  Found: {found_names}")
        
        for k in keywords:
            if any(k.lower() in p.lower() for p in found_names):
                return True
        print(f"  Expected one of {keywords}")
        return False
    return _check

def check_answer_keywords(keywords):
    def _check(data):
        answer = data.get("answer", "").lower()
        if any(k.lower() in answer for k in keywords):
            return True
        print(f"  Answer: {answer}")
        print(f"  Expected keyword: {keywords}")
        return False
    return _check

def main():
    print("Running Deep Backend Corner Case Tests...\n")
    
    test_cases = [
        {
            "name": "Redundant/Duplicate Filters",
            "payload": {"query": "2BHK 2BHK in Whitefield Whitefield"},
            "check": check_projects_contain(["Brigade", "Whitefield"]) 
        },
        {
            "name": "Ambiguous Location: Near Airport",
            "payload": {"query": "Apartments near airport"},
            "check": check_projects_contain(["Avalon", "Oasis", "Devanahalli"])
        },
        {
            "name": "Complex Budget: 1.5cr to 2.5cr",
            "payload": {"query": "Flats between 1.5cr and 2.5 cr"},
            "check": check_projects_contain(["Citrine", "Neopolis", "Evara"])
        },
         {
            "name": "Property Type: Villas",
            "payload": {"query": "Show me villas"},
            "check": check_projects_contain(["Oasis", "Atmosphere"]) # Oasis is plots, Atmosphere matches?
            # Atmosphere is villas.
        },
        {
            "name": "Status: Ready to Move",
            "payload": {"query": "Ready to move projects"},
            "check": check_projects_contain(["Oasis"]) # Oasis is RTM
        },
        {
            "name": "Negative constraint (not supported usually but testing safety)",
            "payload": {"query": "Not in Whitefield"}, 
            "check": lambda d: True # Just ensure it doesn't crash 500
        }
    ]
    
    failures = 0
    passed = 0
    
    for case in test_cases:
        if run_test(case['name'], case['payload'], case['check']):
            passed += 1
        else:
            failures += 1
    
    print(f"\nSummary: {passed}/{len(test_cases)} Passed.")
    if failures > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
