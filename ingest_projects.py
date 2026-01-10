import pandas as pd
import re
import os
import sys
import logging
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from config import settings
from database.supabase_client import supabase_client
from supabase import create_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use Service Key for Admin Access
if settings.supabase_service_key:
    logger.info("Using Supabase Service Key for Admin Access")
    supabase_client.client = create_client(
        settings.supabase_url,
        settings.supabase_service_key
    )
else:
    logger.warning("No Service Key found. RLS reference error expected if not admin.")

def parse_price(price_str):
    """Parse price string like '1.48 Cr*' or '80 Lac' to integer INR."""
    try:
        clean = price_str.replace('*', '').strip()
        parts = clean.split()
        val = float(parts[0])
        unit = parts[1].lower() if len(parts) > 1 else ""
        
        if 'cr' in unit:
            return int(val * 10000000)
        elif 'lac' in unit or 'l' in unit:
            return int(val * 100000)
        return int(val)
    except Exception as e:
        logger.warning(f"Failed to parse price: {price_str} ({e})")
        return None

def parse_area(area_str):
    """Parse area '1486-1617' to numeric (taking min)."""
    try:
        clean = area_str.replace('Sq.ft', '').strip()
        if '-' in clean:
            return float(clean.split('-')[0])
        return float(clean)
    except:
        return 0.0

def parse_bhk(bhk_str):
    """Parse '3 BHK' to 3."""
    try:
        return int(bhk_str.split()[0])
    except:
        return 0

def clean_configurations(config_str):
    """Parse string like '{3 BHK, 1486-1617 Sq.ft, 1.48Cr*}, {...}'."""
    units = []
    # Split by }, { to handle multiple
    items = re.findall(r'\{(.*?)\}', config_str)
    for item in items:
        # Expected format: "3 BHK, 1486-1617 Sq.ft, 1.48Cr*"
        parts = [p.strip() for p in item.split(',')]
        if len(parts) >= 3:
            bhk = parse_bhk(parts[0])
            area = parse_area(parts[1])
            price = parse_price(parts[2])
            units.append({
                "type_name": parts[0], # e.g. "3 BHK"
                "bedrooms": bhk,
                "super_builtup_area_sqft": area,
                "base_price_inr": price
            })
    return units

async def ingest_row(row):
    # 1. Developer
    dev_name = row['Builder Name']
    dev_resp = supabase_client.client.table("developers").select("id").eq("name", dev_name).execute()
    if dev_resp.data:
        dev_id = dev_resp.data[0]['id']
    else:
        logger.info(f"Creating developer: {dev_name}")
        dev_id = supabase_client.client.table("developers").insert({"name": dev_name}).execute().data[0]['id']

    # 2. Project
    proj_name = row['Project Name']
    proj_data = {
        "name": proj_name,
        "developer_id": dev_id,
        "location": row.get('Location/Area', ''),
        "city": 'Bangalore', # Defaulting based on inspection
        "locality": row.get('City'), # Excel has 'City' as 'East Bangalore' which is more like area/locality
        "status": 'ongoing', # row['Project Status'] maps to enum? 'Underconstruction' -> 'ongoing'
        "possession_start_year": int(row['Possession Timeline']) if pd.notna(row['Possession Timeline']) else None
    }
    
    # Check existing project
    proj_resp = supabase_client.client.table("projects").select("id").eq("name", proj_name).execute()
    if proj_resp.data:
        proj_id = proj_resp.data[0]['id']
        # Update? Skip for now.
    else:
        logger.info(f"Creating project: {proj_name}")
        proj_id = supabase_client.client.table("projects").insert(proj_data).execute().data[0]['id']

    # 3. Unit Types
    config_str = row['Configuration']
    if pd.notna(config_str):
        unit_configs = clean_configurations(config_str)
        for u in unit_configs:
            u['project_id'] = proj_id
            u['possession_year'] = proj_data['possession_start_year']
            # Insert unit type
            try:
                supabase_client.client.table("unit_types").insert(u).execute()
            except Exception as e:
                logger.error(f"Error inserting unit for {proj_name}: {e}")

async def main():
    file_path = "Test - Projects.xlsx"
    if not os.path.exists(file_path):
        logger.error("File not found.")
        return

    df = pd.read_excel(file_path)
    logger.info(f"Found {len(df)} projects to ingest.")
    
    for _, row in df.iterrows():
        try:
            await ingest_row(row)
        except Exception as e:
            logger.error(f"Failed row: {row['Project Name']} - {e}")

if __name__ == "__main__":
    asyncio.run(main())
