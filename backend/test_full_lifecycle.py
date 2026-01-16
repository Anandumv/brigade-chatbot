
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

async def full_lifecycle_test():
    session_id = "lifecycle_test_final"
    flow_engine.reset_session(session_id)
    
    steps = [
        ("Init", "I'm looking for a 3BHK in Whitefield"),
        ("Filter1", "My budget is around 1.5Cr"),
        ("Repeat", "Actually, make it 3BHK in Whitefield under 1.5Cr"), # Repetitive typing
        ("Selection", "Tell me more about Prestige Glenbrook"), # Assuming it matches
        ("Objection", "It's too far in the future. I want something ready to move."),
        ("Pivot", "Explain more about why Under Construction is better?"), # Testing Node 10
        ("Change Filter", "What if I look in Sarjapur Road instead?"), # Multi-filter refinement
        ("Radius", "Any more options nearby?"), # Radius pivot
        ("Conversion", "Okay, show me the best one. I want to visit.")
    ]
    
    print(f"=== Starting Salesman Lifecycle Verification: {session_id} ===")
    
    for label, user_input in steps:
        print(f"\n[{label}] User: {user_input}")
        resp = flow_engine.process(session_id, user_input)
        print(f"Node: {resp.current_node} -> {resp.next_redirection}")
        # print(f"Requirements: {resp.extracted_requirements}")
        # print(f"Bot: {resp.system_action[:100]}...")
        
    print("\n=== Test Completed ===")

if __name__ == "__main__":
    asyncio.run(full_lifecycle_test())
