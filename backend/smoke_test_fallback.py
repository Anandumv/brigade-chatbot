"""
Quick smoke test to verify the intelligent fallback is working end-to-end.
Run this after deployment to ensure the feature is functioning.
"""

import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'vendor')))

from services.intelligent_fallback import intelligent_fallback
from services.filter_extractor import filter_extractor


async def smoke_test():
    """Quick smoke test - the exact query from the user's screenshot."""
    print("\n🔥 SMOKE TEST: Intelligent Fallback Suggestions")
    print("=" * 80)
    print("\n📋 Testing the exact query from user's screenshot:")
    print('   Query: "projects under 70 lacs in north bangalore"\n')
    
    query = "projects under 70 lacs in north bangalore"
    
    # Extract filters
    filters = filter_extractor.extract_filters(query)
    print(f"✅ Filters extracted: {filters.model_dump(exclude_none=True)}\n")
    
    # Find alternatives
    print("🔍 Finding intelligent alternatives...")
    result = await intelligent_fallback.find_intelligent_alternatives(
        filters=filters,
        original_query=query,
        max_results=3
    )
    
    alternatives = result.get("alternatives", [])
    answer = result.get("answer", "")
    
    if alternatives:
        print(f"✅ SUCCESS: Found {len(alternatives)} alternatives!\n")
        print("📊 Alternatives:")
        for idx, alt in enumerate(alternatives, 1):
            print(f"\n  {idx}. {alt.get('name')}")
            print(f"     📍 {alt.get('location')}")
            print(f"     💰 ₹{alt.get('budget_min', 0)/100:.2f} - ₹{alt.get('budget_max', 0)/100:.2f} Cr")
            print(f"     📏 {alt.get('_distance', 'N/A')} km away")
        
        print("\n" + "=" * 80)
        print("💬 Generated Sales Pitch (preview):")
        print("=" * 80)
        print(answer[:600] if len(answer) > 600 else answer)
        if len(answer) > 600:
            print("...\n(truncated)")
        print("=" * 80)
        
        print("\n✅ SMOKE TEST PASSED")
        print("   The intelligent fallback system is working correctly!")
        print("   User will now see suggestions instead of '0 results'.\n")
        return True
    else:
        print("\n❌ SMOKE TEST FAILED")
        print("   No alternatives found - fallback system may not be working.\n")
        return False


if __name__ == "__main__":
    success = asyncio.run(smoke_test())
    sys.exit(0 if success else 1)
