import sys
import os

# Set dummy env vars to satisfy Settings validation
os.environ["OPENAI_API_KEY"] = "sk-dummy"
os.environ["SUPABASE_URL"] = "https://dummy.supabase.co"
os.environ["SUPABASE_KEY"] = "dummy-key"
os.environ["TAVILY_API_KEY"] = "tvly-dummy"

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.query_preprocessor import query_preprocessor
from services.answer_generator import answer_generator

def test_preprocessing():
    print("--- Testing Query Preprocessor ---")
    inputs = [
        "got 2bhk in wfield under 1.5cr?",
        "whats d price of citrine?",
        "any 3 bhk avail?",
        "rdy to move flats"
    ]
    
    for i in inputs:
        processed = query_preprocessor.preprocess(i)
        print(f"Original: '{i}'\nProcessed: '{processed}'\n")

def test_sales_prompt():
    print("\n--- Testing Sales Prompt ---")
    prompt = answer_generator._build_system_prompt("sales_pitch")
    
    if "Call to Action" in prompt:
        print("✅ CTA found in prompt")
    else:
        print("❌ CTA MISSING in prompt")
        
    if "Highlight USPs" in prompt:
        print("✅ USPs logic found in prompt")
    else:
        print("❌ USPs logic MISSING in prompt")
        
    print("\nSnippet of prompt:")
    print(prompt[-500:])

if __name__ == "__main__":
    test_preprocessing()
    test_sales_prompt()
