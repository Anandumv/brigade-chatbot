import pandas as pd
import pixeltable as pxt
import re
import uuid
import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.pixeltable_setup import get_projects_table

FILE_PATH = "/Users/anandumv/Downloads/chatbot/GPT Projects (1).xlsx"

def parse_price_range(config_str):
    """
    Parses '1.35 Cr', '1.65 Cr' from string.
    Returns (min_lakhs, max_lakhs).
    """
    # Regex to find N.NN Cr
    prices = re.findall(r'([\d\.]+)\s*Cr', str(config_str), re.IGNORECASE)
    if not prices:
        # Check for Lakhs/L
        lakhs = re.findall(r'([\d\.]+)\s*L', str(config_str), re.IGNORECASE)
        if lakhs:
            vals = [float(x) for x in lakhs]
            return int(min(vals)), int(max(vals))
        return 0, 0
    
    vals = [float(x) for x in prices]
    # Convert Cr to Lakhs
    return int(min(vals) * 100), int(max(vals) * 100)

def ingest_data():
    try:
        df = pd.read_excel(FILE_PATH)
        projects_table = get_projects_table()
        
        rows_to_insert = []
        
        for _, row in df.iterrows():
            project_name = str(row.get('Project Name', '')).strip()
            if not project_name or pd.isna(project_name):
                continue
                
            # Clean fields
            builder = str(row.get('Builder Name', '')).strip()
            status_raw = str(row.get('Project Status', '')).strip()
            status = "Under Construction" if "Under" in status_raw else "Ready to Move"
            
            location = str(row.get('Location/Area', '')).strip()
            zone = str(row.get('City', '')).strip() # Capture Zone
            
            # Combine logic? Maybe "Sarjapur Road, East Bangalore"
            full_location = f"{location}, {zone}" if zone and zone != location else location
            
            config_str = str(row.get('Configuration', ''))
            b_min, b_max = parse_price_range(config_str)
            
            poss_year_raw = row.get('Possession Timeline')
            try:
                poss_year = int(float(str(poss_year_raw).replace('Onwards', '').strip()))
            except:
                poss_year = 2029 # Default fallback
            
            amenities = str(row.get('Amenities', ''))
            desc = str(row.get('Location Proximity / Key Highlitghts', ''))
            
            # Generate ID
            project_id = project_name.lower().replace(' ', '-').replace('/', '-')
            
            data = {
                "project_id": project_id[:50], 
                "name": project_name,
                "developer": builder,
                "location": full_location, 
                "zone": zone, # New Field
                "configuration": config_str, 
                "budget_min": b_min,
                "budget_max": b_max,
                "possession_year": poss_year,
                "possession_quarter": "Q4", 
                "status": status,
                "rera_number": "Pending",
                "description": desc,
                "amenities": amenities,
                "usp": ""
            }
            rows_to_insert.append(data)
            
        # Drop existing to force schema update
        try:
             pxt.drop_table('brigade.projects', force=True)
             print("Dropped old projects table.")
        except Exception as e:
             print(f"Drop failed (might not exist): {e}")
             
        # Create Table Locally to ensure Schema
        schema = {
            'project_id': pxt.String,
            'name': pxt.String,
            'developer': pxt.String,
            'location': pxt.String,
            'zone': pxt.String,
            'configuration': pxt.String,
            'budget_min': pxt.Int,
            'budget_max': pxt.Int,
            'possession_year': pxt.Int,
            'possession_quarter': pxt.String,
            'status': pxt.String,
            'rera_number': pxt.String,
            'description': pxt.String,
            'amenities': pxt.String,
            'usp': pxt.String,
        }
        
        projects_table = pxt.create_table('brigade.projects', schema)
        print("Created new projects table with Zone schema.")
        
        projects_table.insert(rows_to_insert)
        print(f"Successfully inserted {len(rows_to_insert)} projects with Zone data!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    ingest_data()
