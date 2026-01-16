from services.filter_extractor import filter_extractor

queries = [
    "2BHK 2BHK in Whitefield Whitefield",
    "Apartments near airport",
    "Flats between 1.5cr and 2.5 cr",
    "Show me villas",
    "Ready to move projects",
    "2BHK in Whitefield under 1.5 Cr"
]

print("Verifying Filter Extraction:\n")
for q in queries:
    print(f"Query: '{q}'")
    filters = filter_extractor.extract_filters(q)
    print(f"  Filters: {filters.dict(exclude_none=True)}")
    print("-" * 20)
