
import asyncio
import logging
import sys
from services.flow_engine import flow_engine

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def test_project_selection():
    print("=== Testing Interactive Project Selection & Pitching ===")
    session_id = "test_selection_session"
    flow_engine.reset_session(session_id)
    
    # 1. Initial Query (3BHK in Whitefield under 2.5Cr - will have matches like Sumadhura Folium)
    print("\nTurn 1: Requesting 3BHK in Whitefield under 2.5 Cr")
    resp = flow_engine.process(session_id, "Show me 3BHK flats in Whitefield under 2.5 Cr")
    print(f"Node Path: {resp.current_node} -> {resp.next_redirection}")
    
    # 2. Select a project (e.g., "Prestige Glenbrook")
    print("\nTurn 2: Selecting 'Prestige Glenbrook'")
    resp = flow_engine.process(session_id, "Tell me more about Prestige Glenbrook")
    
    # The interceptor sets next_redirection to NODE 2B
    if resp.next_redirection == "NODE 2B":
         print("Pivoting to Node 2B (Deep-Dive)...")
         resp = flow_engine.process(session_id, "Go")
         
    print(f"Node Path: {resp.current_node} -> {resp.next_redirection}")
    print("\n--- Project Deep-Dive Pitch ---")
    print(resp.system_action)
    
    # 3. Follow-up and Site Visit
    print("\nTurn 3: Requesting site visit")
    resp = flow_engine.process(session_id, "Sounds great, I'd like to visit")
    print(f"Node Path: {resp.current_node} -> {resp.next_redirection}")
    print("\n--- Final Bot Response ---")
    print(resp.system_action)
    
    # Verification
    if "Sumadhura Folium" in resp.system_action and resp.next_redirection == "FACE_TO_FACE":
        print("\n✅ SUCCESS: Project selection and deep-dive pitch working correctly!")
    else:
        print("\n❌ FAILURE: Project selection or pitching failed.")

if __name__ == "__main__":
    asyncio.run(test_project_selection())
