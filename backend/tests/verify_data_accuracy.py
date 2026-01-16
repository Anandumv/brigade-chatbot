
import requests
import json
import time

BASE_URL = "https://brigade-chatbot-production.up.railway.app"
HEADERS = {"Content-Type": "application/json"}

# Ground Truth Mapping based on seed_projects.json
EXPECTED_RESULTS = {
    # Query: [List of expected substrings in project names]
    "North Bangalore": [
        "L&T Elara Celestia", 
        "Brigade Eternia", 
        "Sattva Park Cubix" 
    ],
    "East Bangalore": [
        "Mana Skanda", 
        "Birla Evara", 
        "Sobha Neopolis"
    ],
    "Whitefield": [
        "Sumadhura Folium", 
        "Vaswani Satrlight", 
        "Prestige Glenbrook"
    ],
    "Possession by 2030": [
        "Brigade Eternia", # 2030
        "Merusri Sunscape", # 2030
        "Prestige City 2.0" # 2030
    ],
    "Villas": [
        "JRC Palladio", 
        "Adarsh Welkin Park", 
        "Merusri Sunscape"
    ]
}

def verify_query_accuracy(scenario_name, query, expected_names):
    print(f"Testing Accuracy: {scenario_name} ('{query}')...", end=" ", flush=True)
    
    payload = {"query": f"Show me {query}", "session_id": f"acc-{scenario_name.lower().replace(' ', '-')}"}
    
    try:
        response = requests.post(f"{BASE_URL}/api/chat/filtered-search", json=payload, headers=HEADERS, timeout=30)
        data = response.json()
        
        projects = data.get("projects", [])
        project_names = [p.get("project_name", "") for p in projects]
        
        # Check if ALL expected names are present in the returned list
        missing = []
        for expected in expected_names:
            found = False
            for actual in project_names:
                if expected.lower() in actual.lower():
                    found = True
                    break
            if not found:
                missing.append(expected)
        
        if not missing:
            print(f"PASSED (Found all {len(expected_names)} expected)")
            return True
        else:
            print(f"FAILED")
            print(f"  Expected to find: {expected_names}")
            print(f"  Actually returned: {project_names[:5]}... ({len(project_names)} total)")
            print(f"  Missing: {missing}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=== DATA ACCURACY VERIFICATION ===")
    
    success = True
    
    # Run checks defined in EXPECTED_RESULTS
    for key, expected_list in EXPECTED_RESULTS.items():
        if not verify_query_accuracy(key, f"projects in {key}" if "Possession" not in key and "Villas" not in key else f"{key}", expected_list):
            success = False
            
    print("\n=== OVERALL RESULT ===")
    if success:
        print("ALL DATA ACCURACY CHECKS PASSED ✅")
    else:
        print("SOME CHECKS FAILED ❌")
