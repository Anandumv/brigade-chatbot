import asyncio
import logging
from services.hybrid_retrieval import hybrid_retrieval

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_search():
    query = "2BHK in Whitefield under 1.5 Cr"
    print(f"Testing Query: {query}")
    
    try:
        # Force mock mode check
        print(f"Projects Table: {hybrid_retrieval.projects_table}")
        print(f"Mock Projects Loaded: {len(hybrid_retrieval.mock_projects)}")
        
        results = await hybrid_retrieval.search_with_filters(query)
        print("Search Results:", results)
        
        projects = results.get('projects', [])
        print(f"Found {len(projects)} projects")
        for p in projects:
            print(f" - {p['project_name']} ({p['price_range']})")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search())
