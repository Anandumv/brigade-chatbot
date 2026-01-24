import sys
import os

# Ensure we can import backend modules
sys.path.append(os.path.abspath("backend"))

try:
    from backend.database.pixeltable_setup import get_projects_table
    import pixeltable as pxt

    print("--- Connecting to Pixeltable ---")
    t = get_projects_table()
    
    print(f"Total Projects: {t.count()}")
    
    # Check for Whitefield projects
    print("\n--- Searching for 'Whitefield' in Location ---")
    whitefield_projects = t.where(t.location.contains('Whitefield')).select(t.name, t.location, t.budget_min, t.budget_max).collect()
    
    if whitefield_projects:
        print(f"Found {len(whitefield_projects)} projects in Whitefield:")
        for p in whitefield_projects:
            print(f" - {p['name']} ({p['location']}): {p['budget_min']/100:.2f} Cr - {p['budget_max']/100:.2f} Cr")
    else:
        print("❌ No projects found with 'Whitefield' in location.")
        
    # List all locations to see what's available
    print("\n--- All Project Locations ---")
    all_projects = t.select(t.name, t.location).collect()
    for p in all_projects:
        print(f" - {p['name']}: {p['location']}")

except Exception as e:
    print(f"Error: {e}")
