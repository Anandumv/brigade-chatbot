"""
Import Projects from Excel to Pixeltable
Production script for importing real project data.
"""

import pandas as pd
import pixeltable as pxt
import re
import logging
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EXCEL_PATH = "/Users/anandumv/Downloads/chatbot/Test - Projects.xlsx"


def parse_configuration(config_str: str) -> List[Dict[str, Any]]:
    """
    Parse configuration string into structured unit data.
    Format: {3 BHK, 1127 - 1461, 2.20 Cr*}, {4 BHK,1733 - 1759, 2.90 Cr*}
    """
    if not config_str or pd.isna(config_str):
        return []
    
    units = []
    # Match patterns like {3 BHK, 1127 - 1461, 2.20 Cr*}
    pattern = r'\{(\d+(?:\.\d+)?)\s*BHK?,?\s*([\d\s\-]+)?,?\s*([\d\.]+)\s*(?:Cr|CR|cr)\*?\}'
    matches = re.findall(pattern, str(config_str))
    
    for match in matches:
        bhk = match[0]
        area = match[1].strip() if match[1] else ""
        price_cr = float(match[2])
        
        # Parse area range
        min_area = max_area = None
        if area:
            area_parts = re.findall(r'\d+', area)
            if len(area_parts) >= 1:
                min_area = int(area_parts[0])
            if len(area_parts) >= 2:
                max_area = int(area_parts[1])
            else:
                max_area = min_area
        
        units.append({
            "bhk": int(float(bhk)),
            "min_sqft": min_area,
            "max_sqft": max_area,
            "price_cr": price_cr,
            "price_inr": int(price_cr * 10000000)  # Convert to INR
        })
    
    return units


def parse_possession(poss_str: str) -> int:
    """Extract year from possession timeline."""
    if not poss_str or pd.isna(poss_str):
        return 2030
    
    # Find 4-digit year
    match = re.search(r'20\d{2}', str(poss_str))
    return int(match.group()) if match else 2030


def init_pixeltable_schema():
    """Initialize Pixeltable with production schema."""
    
    # Check if directory exists
    try:
        dirs = pxt.list_dirs()
        dir_names = [d.name for d in dirs] if dirs else []
        if 'sales' not in dir_names:
            pxt.create_dir('sales')
            logger.info("Created 'sales' directory")
    except:
        pxt.create_dir('sales')
        logger.info("Created 'sales' directory")
    
    # Drop existing tables for clean import
    try:
        tables = pxt.list_tables()
        table_names = [t.name for t in tables] if tables else []
        
        if 'sales.projects' in table_names:
            pxt.drop_table('sales.projects')
            logger.info("Dropped existing sales.projects table")
            
        if 'sales.units' in table_names:
            pxt.drop_table('sales.units')
            logger.info("Dropped existing sales.units table")
    except Exception as e:
        logger.warning(f"Error checking tables: {e}")
    
    # Create projects table
    projects = pxt.create_table('sales.projects', {
        'project_id': pxt.String,
        'name': pxt.String,
        'builder': pxt.String,
        'status': pxt.String,
        'city': pxt.String,
        'location': pxt.String,
        'location_link': pxt.String,
        'total_land_area': pxt.String,
        'towers': pxt.String,
        'floors': pxt.String,
        'possession_year': pxt.Int,
        'amenities': pxt.String,
        'highlights': pxt.String,
        'brochure_link': pxt.String,
        'rm_contact': pxt.String,
        'lead_link': pxt.String,
        # Denormalized unit info for quick search
        'config_summary': pxt.String,  # "2BHK, 3BHK, 4BHK"
        'min_price_cr': pxt.Float,
        'max_price_cr': pxt.Float,
        'min_sqft': pxt.Int,
        'max_sqft': pxt.Int,
    })
    logger.info("Created sales.projects table")
    
    # Create units table for detailed config
    units = pxt.create_table('sales.units', {
        'unit_id': pxt.String,
        'project_id': pxt.String,
        'project_name': pxt.String,
        'bhk': pxt.Int,
        'min_sqft': pxt.Int,
        'max_sqft': pxt.Int,
        'price_cr': pxt.Float,
        'price_inr': pxt.Int,
    })
    logger.info("Created sales.units table")
    
    return projects, units


def import_from_excel():
    """Import projects from Excel file."""
    
    # Read Excel
    df = pd.read_excel(EXCEL_PATH)
    logger.info(f"Read {len(df)} projects from Excel")
    
    # Initialize schema
    projects_table, units_table = init_pixeltable_schema()
    
    # Process each project
    all_projects = []
    all_units = []
    
    for idx, row in df.iterrows():
        project_id = f"proj_{idx+1}"
        
        # Parse configuration
        config_str = row.get('Configuration', '')
        units = parse_configuration(config_str)
        
        # Calculate summary values
        bhk_list = sorted(set(u['bhk'] for u in units)) if units else []
        config_summary = ", ".join(f"{b}BHK" for b in bhk_list)
        min_price = min(u['price_cr'] for u in units) if units else 0
        max_price = max(u['price_cr'] for u in units) if units else 0
        min_sqft = min(u['min_sqft'] or 0 for u in units) if units else 0
        max_sqft = max(u['max_sqft'] or 0 for u in units) if units else 0
        
        # Project record
        project_record = {
            'project_id': project_id,
            'name': str(row.get('Project Name', '')),
            'builder': str(row.get('Builder Name', '')),
            'status': str(row.get('Project Status', '')),
            'city': str(row.get('City', '')),
            'location': str(row.get('Location/Area', '')),
            'location_link': str(row.get('Location Link', '')),
            'total_land_area': str(row.get('Total Land Area', '')),
            'towers': str(row.get('No. Of Towers/Blocks', '')),
            'floors': str(row.get('Floors', '')),
            'possession_year': parse_possession(row.get('Possession Timeline')),
            'amenities': str(row.get('Amenities', '')),
            'highlights': str(row.get('Location Proximity / Key Highlitghts', '')),
            'brochure_link': str(row.get('Broucher', '')),
            'rm_contact': str(row.get('RM Contact Number', '')),
            'lead_link': str(row.get('Lead Registration Link', '')),
            'config_summary': config_summary,
            'min_price_cr': min_price,
            'max_price_cr': max_price,
            'min_sqft': min_sqft,
            'max_sqft': max_sqft,
        }
        all_projects.append(project_record)
        
        # Unit records
        for i, unit in enumerate(units):
            unit_record = {
                'unit_id': f"{project_id}_unit_{i+1}",
                'project_id': project_id,
                'project_name': str(row.get('Project Name', '')),
                'bhk': unit['bhk'],
                'min_sqft': unit['min_sqft'] or 0,
                'max_sqft': unit['max_sqft'] or 0,
                'price_cr': unit['price_cr'],
                'price_inr': unit['price_inr'],
            }
            all_units.append(unit_record)
    
    # Insert data
    projects_table.insert(all_projects)
    logger.info(f"Inserted {len(all_projects)} projects")
    
    if all_units:
        units_table.insert(all_units)
        logger.info(f"Inserted {len(all_units)} units")
    
    return len(all_projects), len(all_units)


def verify_import():
    """Verify the imported data."""
    projects = pxt.get_table('sales.projects')
    units = pxt.get_table('sales.units')
    
    print("\n=== IMPORTED PROJECTS ===")
    results = projects.select(
        projects.name,
        projects.builder,
        projects.city,
        projects.location,
        projects.config_summary,
        projects.min_price_cr,
        projects.max_price_cr
    ).collect()
    
    for r in results:
        print(f"• {r['name']} by {r['builder']}")
        print(f"  📍 {r['location']}, {r['city']}")
        print(f"  🏠 {r['config_summary']}")
        print(f"  💰 ₹{r['min_price_cr']:.2f} - {r['max_price_cr']:.2f} Cr")
        print()
    
    print(f"\n=== SUMMARY ===")
    print(f"Total Projects: {len(results)}")
    
    unit_results = units.select().collect()
    print(f"Total Units: {len(unit_results)}")


if __name__ == "__main__":
    print("Importing projects from Excel to Pixeltable...")
    num_projects, num_units = import_from_excel()
    print(f"\n✅ Import complete: {num_projects} projects, {num_units} units")
    
    verify_import()
