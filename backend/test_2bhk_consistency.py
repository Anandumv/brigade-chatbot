
import asyncio
from services.hybrid_retrieval import HybridRetrievalService
from services.filter_extractor import FilterExtractor, PropertyFilters

async def test_consistency():
    service = HybridRetrievalService()
    extractor = FilterExtractor()
    
    print("--- 1. Testing Structured Filter (UI) ---")
    # Simulate UI Filter: "2 BHK" -> bedrooms=[2]
    ui_filters = {"configuration": "2"} 
    merged_filters = extractor.merge_filters(PropertyFilters(), ui_filters)
    print(f"UI Mapped Filters: {merged_filters}")
    
    # search_with_filters is async
    structured_results = await service.search_with_filters(
        query="structured_test", 
        filters=merged_filters
    )
    print(f"Structured Results Count: {len(structured_results)}")
    
    print("\n--- 2. Testing Natural Language Query (NL) ---")
    nl_query = "Show me 2BHK flats"
    # extract_filters is SYNC
    nl_filters = extractor.extract_filters(nl_query)
    print(f"NL Extracted Filters: {nl_filters}")
    
    # search_with_filters is async
    nl_results = await service.search_with_filters(
        query=nl_query, 
        filters=nl_filters
    )
    print(f"NL Results Count: {len(nl_results)}")
    
    print("\n--- 3. Comparison ---")
    if len(structured_results) == len(nl_results):
        print("✅ SUCCESS: Counts match!")
    else:
        print("❌ FAILURE: Counts do not match.")

    # Check mapping consistency
    ui_bhk = merged_filters.bedrooms
    nl_bhk = nl_filters.bedrooms
    print(f"UI Bedrooms: {ui_bhk}")
    print(f"NL Bedrooms: {nl_bhk}")
    
    if ui_bhk == nl_bhk:
         print("✅ SUCCESS: Filter Logic Identical (Bedrooms)")
    else:
         print("❌ FAILURE: Filter Logic Diverges")

if __name__ == "__main__":
    asyncio.run(test_consistency())
