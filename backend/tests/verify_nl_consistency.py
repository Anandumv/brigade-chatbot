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
        # response.raise_for_status() # Don't raise yet
        
        try:
            data = response.json()
        except:
            print(f"{RED}FAILED{RESET} (Non-JSON response)")
            print(f"Status: {response.status_code}")
            print(f"Body: {response.text[:500]}")
            return False

        if response.status_code != 200:
             print(f"{RED}FAILED{RESET} (HTTP {response.status_code})")
             print(f"  Response: {json.dumps(data, indent=2)}")
             return False
             
        if expected_check(data):
            print(f"{GREEN}PASSED{RESET} (Count: {len(data.get('projects') or [])})")
            return True
        else:
            print(f"{RED}FAILED{RESET}")
            print(f"  Response: {json.dumps(data, indent=2)}")
            return False
    except Exception as e:
        print(f"{RED}ERROR{RESET}: {e}")
        return False

def check_project_count(min_count):
    def _check(data):
        projects = data.get("projects", [])
        if not projects:
            # Fallback to checking answer text if projects structure is empty (shouldn't happen with new update)
            return False
        return len(projects) >= min_count
    return _check

def check_projects_match(structured_projects):
    """
    Returns a check function that verifies if the NL query returns 
    a similar set of projects as the structured query.
    """
    def _check(data):
        projects = data.get("projects") or []
        nl_projects = {p['project_name'] for p in projects}
        structured_names = {p['project_name'] for p in structured_projects}
        
        # We expect significant overlap. NL might be slightly fuzzier, but core matches should exist.
        intersection = nl_projects.intersection(structured_names)
        
        # If structured returned nothing, NL should likely return nothing too
        if not structured_names:
            return not nl_projects
            
        # Check if we found at least 70% of the structured projects or if structured is subset of NL
        match_ratio = len(intersection) / len(structured_names) if structured_names else 0
        
        if match_ratio < 0.7:
             print(f"\n  NL Found: {nl_projects}")
             print(f"  Structured Found: {structured_names}")
             print(f"  Overlap: {intersection}")
             return False
        return True
    return _check

def get_projects_from_backend(payload):
    try:
        response = requests.post(BASE_URL, json=payload)
        # response.raise_for_status() 
        if response.status_code != 200:
             print(f"{RED}Backend Error ({response.status_code}){RESET}: {response.text[:200]}")
             return {"projects": []}
             
        data = response.json()
        if data.get("projects") is None:
             print(f"{RED}Warning: Backend returned 'projects': None{RESET}")
             return {"projects": []}
             
        return data
    except Exception as e:
        print(f"{RED}Request Failed{RESET}: {e}")
        return {"projects": []}

def get_projects_for_structured_query(filters):
    # Helper to get "ground truth" from structured query
    payload = {
        "query": "Show me available apartments", # content to pass intent classifier
        "filters": filters
    }
    data = get_projects_from_backend(payload)
    return data.get("projects", [])

def main():
    print("Running NL Query vs Structured Filter Consistency Tests...\n")
    
    test_cases = [
        # 1. Positive Match Test (from Mock Data)
        {
            "name": "Project: Mana Skanda in Sarjapur",
            "nl_query": "Show me apartments in Mana Skanda in Sarjapur Road",
            "structured_filters": {
                "locality": "Sarjapur Road"
            }
        },
        {
            "name": "NL: 2BHK in Whitefield under 1.5 Cr",
            "nl_query": "Show me 2BHK flats in Whitefield for less than 1.5 crores",
            "structured_filters": {
                "location": "Whitefield", 
                "budget_max": 15000000,
                "bedrooms": [2]
            }
        },
        {
            "name": "NL: Villas in North Bangalore",
            "nl_query": "I am looking for villas in North Bangalore",
            "structured_filters": {
                "area": "North Bangalore",
                "property_type": ["Villa"]
            }
        },
        {
            "name": "NL: Ready to move near Jakkur",
            "nl_query": "Show me Ready to move projects near Jakkur",
            "structured_filters": {
                "location": "Jakkur",
                "possession": ["Ready to Move"]
            }
        },
         {
            "name": "NL: Budget Range 80L to 1.2Cr",
            "nl_query": "Show me Apartments between 80 lakhs and 1.2 cr",
            "structured_filters": {
                "budget_min": 8000000,
                "budget_max": 12000000,
                "property_type": ["Apartment"]
            }
        }
    ]
    
    # We can't perfectly predict structured filters structure without knowing exactly how frontend sends it.
    # But we can assume the backend's `filter_extractor` produces a dictionary. 
    # Actually, `ChatQueryRequest` has `filters` (input) and `filter_extractor` produces filters from `query`.
    # The goal is: Does `query="2BHK..."` produces same output as `query="..."` + `filters={...}`?
    # NO, the goal is: Does `query="2BHK..."` (where backend extracts filters) produce same output as 
    # IF we manually sent the correct filters?
    
    # Actually, simpler: verify that NL queries RETURN PROJECTS.
    # And verify they return "correct" projects (sanity check).
    
    # Better approach for this script:
    # 1. Define a complex NL query.
    # 2. Define the expected extracted filters (conceptually) OR just the expected project keywords.
    
    failures = 0
    
    pass_cnt = 0
    total_cnt = 0

    for case in test_cases:
        total_cnt += 1
        
        # 1. Run Structured Query first to get baseline
        print(f"--- Scenario: {case['name']} ---")
        
        # We manually construct what we *think* the filters should be, to see what the direct retrieval gives
        structured_projects = get_projects_for_structured_query(case['structured_filters'])
        print(f"  [Baseline] Structured query found {len(structured_projects) if structured_projects else 0} projects.")
    
        if not structured_projects:
            print(f"  {RED}WARNING: Baseline found 0 projects. Consistency check might be trivial.{RESET}")

        # 2. Run NL Query (filters=None, rely on extraction)
        payload = {"query": case['nl_query']}
        
        if run_test(case['name'], payload, check_projects_match(structured_projects or [])):
            pass_cnt += 1
        else:
            failures += 1
            
    print(f"\nSummary: {pass_cnt}/{total_cnt} Passed.")
    if failures > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
