import sys
import os
import asyncio
from pydantic import BaseModel
from typing import Optional

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.flow_engine import FlowEngine
from config import settings

# Mock the LLM client or just use the real one since it's an extraction test
# We will use the real extraction function if possible, or simulate the flow

async def test_budget_extraction():
    engine = FlowEngine()
    
    queries = [
        "under 150000 Cr",
        "budget 1.5 Cr",
        "max 50000000",
        "budget 150000"
    ]
    
    print("\n--- Testing Budget Extraction ---")
    for q in queries:
        try:
            # We want to access the extraction logic directly if possible
            # But it's private or inside 'process'. 
            # We can use the helper method _extract_requirements_llm if we can access it
            # Or just run the process and check the extracted requirements in the response
            
            # Since _extract_requirements_llm is async and inside the class
            # We'll construct a mock state and call it
            
            # Actually, let's just use the public .process() and inspect the logs or response
            # But .process() requires DB setup.
            # Let's inspect extraction directly if we can import the helper function.
            
            # The function is `extract_requirements_llm` inside `flow_engine.py` but it's not a standalone function
            # It's a method of FlowEngine.
            
            # Let's try to call engine.classify_user_intent or similar? No, extraction is separate.
            
            # We will use a simplified approach: Just import the LLM call logic if possible.
            # OR better, since FlowEngine.process does a lot, maybe we mock `extract_requirements_llm`?
            # No, we want to see what the REAL `extract_requirements_llm` does.
            
            # Let's try to invoke the LLM extraction directly using the prompt logic from flow_engine.py
            # I'll just copy the extraction logic into this script to debug it interacting with OpenAI
             pass
        except Exception as e:
            print(f"Error: {e}")

    # Better yet, let's just modify the `flow_engine.py` temporarily to `print` extraction results 
    # OR run a script that imports FlowEngine and calls the method.
    
    # FlowEngine needs Pixeltable client, which might be hard to mock.
    # Let's look at `extract_requirements_llm` in `flow_engine.py` first using `view_file`.
    pass

if __name__ == "__main__":
    # check extraction logic
    pass
