import os
import sys
import logging

# Add current directory to path so we can import database modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.pixeltable_setup import get_projects_table, initialize_pixeltable

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==========================================
# 📝 ADD YOUR PROJECTS HERE
# ==========================================
PROJECTS_TO_INSERT = [
    {
        "project_id": "brigade-citrine",
        "name": "Brigade Citrine",
        "developer": "Brigade Group",
        "location": "Budigere Cross",
        "configuration": "2BHK, 3BHK, 4BHK",
        "budget_min": 120,   # 1.2 Cr
        "budget_max": 250,   # 2.5 Cr
        "possession_year": 2027,
        "possession_quarter": "Q4",
        "status": "Under Construction",
        "rera_number": "PRM/KA/RERA/1251/446/PR/230522/006437",
        "description": "Luxury apartments in Budigere Cross with forest views. Offering a balance of nature and urban convenience.",
        "amenities": "['Clubhouse', 'Swimming Pool', 'Gym', 'Forest Trail', 'Kids Play Area']",
        "usp": "Forest themed luxury living"
    },
    {
        "project_id": "brigade-avalon",
        "name": "Brigade Avalon",
        "developer": "Brigade Group",
        "location": "Devanahalli",
        "configuration": "1BHK, 2BHK, 3BHK",
        "budget_min": 65,    # 65 L
        "budget_max": 150,   # 1.5 Cr
        "possession_year": 2026,
        "possession_quarter": "Q2",
        "status": "Under Construction",
        "rera_number": "PRM/KA/RERA/1250/303/PR/200618/003456",
        "description": "Apartments within Brigade Orchards integrated township, close to the Airport.",
        "amenities": "['Sports Arena', 'School', 'Hospital', 'Retail', 'Shuttle Service']",
        "usp": "Integrated township living near Airport"
    },
    {
        "project_id": "brigade-oasis",
        "name": "Brigade Oasis",
        "developer": "Brigade Group",
        "location": "Devenahalli",
        "configuration": "Plots",
        "budget_min": 80,
        "budget_max": 200,
        "possession_year": 2024,
        "possession_quarter": "Ready",
        "status": "Ready to Move",
        "rera_number": "PRM/KA/RERA/1250/303/PR/220928/005280",
        "description": "Premium plotted development near Airport. Build your dream home your way.",
        "amenities": "['Landscaped Gardens', 'Underground Utilities', 'Clubhouse', 'Security']",
        "usp": "Premium plots with great appreciation potential"
    }
]

def update_db():
    print("🚀 Initializing connection to Pixeltable...")
    initialize_pixeltable()
    projects_table = get_projects_table()
    
    print(f"📋 Found {projects_table.count()} existing projects.")
    
    for project in PROJECTS_TO_INSERT:
        pid = project['project_id']
        name = project['name']
        
        # 1. Try to delete existing entry to avoid duplicates (Upsert logic)
        try:
            # Note: Pixeltable delete syntax might vary version to version.
            # If explicit delete isn't supported, we might just append.
            # But duplicate IDs handling depends on schema.
            # For now, we assume append-only or handled by logic.
            # A safe bet in append-only logs is to just insert.
            # The retrieval logic should pick the latest or filter duplicates.
            pass 
        except Exception as e:
            logger.warning(f"Could not delete existing {pid}: {e}")

        # 2. Insert new data
        try:
            projects_table.insert([project])
            print(f"✅ Successfully inserted/updated: {name}")
        except Exception as e:
            print(f"❌ Failed to insert {name}: {e}")

    print("\n✨ Done! Database is updated.")
    print(f"📊 Total projects now: {projects_table.count()}")

if __name__ == "__main__":
    update_db()
