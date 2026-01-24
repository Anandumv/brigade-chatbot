import pandas as pd
import json
import os

excel_path = "GPT Projects (1).xlsx"
json_path = "backend/data/seed_projects.json"

try:
    # 1. Read Excel
    df = pd.read_excel(excel_path)
    # Mapping: 'Project Name' -> 'Broucher'
    # Use fillna to handle missing values
    excel_data = df[['Project Name', 'Broucher']].dropna(subset=['Project Name', 'Broucher']).to_dict('records')
    url_map = {row['Project Name'].strip().lower(): row['Broucher'].strip() for row in excel_data}
    
    # 2. Read JSON
    with open(json_path, 'r') as f:
        projects = json.load(f)
    
    # 3. Update JSON
    updates = 0
    for p in projects:
        name_key = p['name'].strip().lower()
        if name_key in url_map:
            p['brochure_url'] = url_map[name_key]
            updates += 1
            print(f"Updated: {p['name']} -> {p['brochure_url']}")
        else:
            # Fuzzy match attempt for minor spelling differences
            match_found = False
            for excel_name, url in url_map.items():
                # Primitive fuzzy: if one is substring of other (e.g. "Mana Dale" in "Mana Dale Phase 1")
                if excel_name in name_key or name_key in excel_name:
                    p['brochure_url'] = url
                    updates += 1
                    print(f"Fuzzy Updated: {p['name']} (matched '{excel_name}') -> {p['brochure_url']}")
                    match_found = True
                    break
            
            if not match_found:
                print(f"No match for: {p['name']}")

    # 4. Save JSON
    if updates > 0:
        with open(json_path, 'w') as f:
            json.dump(projects, f, indent=2)
        print(f"\nSuccessfully updated {updates} brochure URLs.")
    else:
        print("\nNo updates made. Check mapping.")

except Exception as e:
    print(f"Error: {e}")
