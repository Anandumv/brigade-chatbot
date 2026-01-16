
import asyncio
from services.flow_engine import flow_engine

async def test_radius_pivot_valid():
    print("=== Testing 10km Radius Location Pivot (Sarjapur Road -> Gunjur) ===")
    session_id = "test_radius_valid_session"
    flow_engine.reset_session(session_id)
    
    # 1. Initial Query in Sarjapur Road under 1.2Cr (No exact matches, Mana Skanda is 1.35Cr)
    print("\nTurn 1: Requesting Sarjapur Road under 1.2 Cr")
    resp = flow_engine.process(session_id, "3BHK in Sarjapur Road under 1.2 Cr")
    print(f"Node Path: {resp.current_node} -> {resp.next_redirection}")
    
    # 2. Use Shortcut: "Show me nearby locations"
    print("\nTurn 2: Requesting nearby locations (Shortcut)")
    resp = flow_engine.process(session_id, "Show me nearby areas within 10km")
    
    # The interceptor sets next_redirection to NODE 7
    if resp.next_redirection == "NODE 7":
         print("Pivoting to Node 7...")
         resp = flow_engine.process(session_id, "Go")
         
    print(f"Node Path: {resp.current_node} -> {resp.next_redirection}")
    print("\n--- Project List ---")
    print(resp.system_action)
    
    # Verification: Should find Goyal And Co Orchid Life (Gunjur)
    if "Goyal And Co Orchid Life" in resp.system_action or "Gunjur" in resp.system_action:
        print("\n✅ SUCCESS: Found Gunjur project within 10km of Sarjapur Road!")
    else:
        print("\n❌ FAILURE: Could not find expected nearby project (Goyal/Gunjur).")

if __name__ == "__main__":
    asyncio.run(test_radius_pivot_valid())
