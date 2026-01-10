"""
Complete Data Vectorization Script for Sales RAG
Converts ALL project data (Excel + PDFs) into searchable vector chunks
"""
import pandas as pd
import os
import sys
import logging
import asyncio

sys.path.append(os.path.join(os.getcwd(), 'backend'))

from config import settings
from database.supabase_client import supabase_client
from supabase import create_client
import openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use Service Key
if settings.supabase_service_key:
    logger.info("Using Supabase Service Key")
    supabase_client.client = create_client(
        settings.supabase_url,
        settings.supabase_service_key
    )

openai.api_key = settings.openai_api_key

def generate_embedding(text: str):
    """Generate embedding for text using OpenAI."""
    try:
        response = openai.embeddings.create(
            model=settings.embedding_model,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return None

def create_project_summary(row) -> str:
    """Create a rich text summary from Excel row for vectorization."""
    summary = f"""
Project: {row.get('Project Name', 'N/A')}
Developer: {row.get('Builder Name', 'N/A')}
Location: {row.get('Location/Area', 'N/A')}
City: {row.get('City', 'Bangalore')}
Status: {row.get('Project Status', 'N/A')}
Total Land Area: {row.get('Total Land Area', 'N/A')}
Number of Towers: {row.get('No. Of Towers/Blocks', 'N/A')}
Floors: {row.get('Floors', 'N/A')}
Configurations: {row.get('Configuration', 'N/A')}
Possession Timeline: {row.get('Possession Timeline', 'N/A')}
Amenities: {row.get('Amenities', 'N/A')}
Location Highlights: {row.get('Location Proximity / Key Highlitghts', 'N/A')}
Contact: {row.get('RM Contact Number', 'N/A')}
""".strip()
    return summary

async def vectorize_excel_data():
    """Vectorize all data from Excel into document_chunks."""
    file_path = "Test - Projects.xlsx"
    if not os.path.exists(file_path):
        logger.error("Excel file not found")
        return
    
    df = pd.read_excel(file_path)
    logger.info(f"Processing {len(df)} projects from Excel...")
    
    for _, row in df.iterrows():
        project_name = row.get('Project Name', 'Unknown')
        
        # Get project_id
        proj_resp = supabase_client.client.table("projects").select("id").eq("name", project_name).execute()
        if not proj_resp.data:
            logger.warning(f"Project not found: {project_name}")
            continue
        
        project_id = proj_resp.data[0]['id']
        
        # Create comprehensive text chunk
        summary_text = create_project_summary(row)
        
        # Generate embedding
        embedding = generate_embedding(summary_text)
        if not embedding:
            continue
        
        # Check if already exists
        existing = supabase_client.client.table("document_chunks").select("id").eq("project_id", project_id).eq("section", "Project Summary").execute()
        
        if existing.data:
            # Update
            supabase_client.client.table("document_chunks").update({
                "content": summary_text,
                "embedding": embedding
            }).eq("id", existing.data[0]['id']).execute()
            logger.info(f"Updated: {project_name}")
        else:
            # Insert new chunk
            # First get or create a document record
            doc_resp = supabase_client.client.table("documents").select("id").eq("project_id", project_id).execute()
            if doc_resp.data:
                doc_id = doc_resp.data[0]['id']
            else:
                doc_resp = supabase_client.client.table("documents").insert({
                    "project_id": project_id,
                    "title": f"{project_name} Data",
                    "type": "brochure",
                    "file_path": "excel_import"
                }).execute()
                doc_id = doc_resp.data[0]['id']
            
            supabase_client.client.table("document_chunks").insert({
                "document_id": doc_id,
                "project_id": project_id,
                "content": summary_text,
                "embedding": embedding,
                "section": "Project Summary",
                "source_type": "internal",
                "chunk_index": 0,
                "metadata": {"source": "Excel Import"}
            }).execute()
            logger.info(f"Inserted: {project_name}")
        
        # Also create separate chunks for amenities and location
        amenities = row.get('Amenities', '')
        if pd.notna(amenities) and amenities:
            amenity_text = f"Amenities at {project_name}: {amenities}"
            amenity_embedding = generate_embedding(amenity_text)
            if amenity_embedding:
                existing_amenity = supabase_client.client.table("document_chunks").select("id").eq("project_id", project_id).eq("section", "Amenities").execute()
                if not existing_amenity.data:
                    supabase_client.client.table("document_chunks").insert({
                        "document_id": doc_id,
                        "project_id": project_id,
                        "content": amenity_text,
                        "embedding": amenity_embedding,
                        "section": "Amenities",
                        "source_type": "internal",
                        "chunk_index": 1,
                        "metadata": {"source": "Excel Import"}
                    }).execute()
        
        # Location chunk
        location_info = row.get('Location Proximity / Key Highlitghts', '')
        if pd.notna(location_info) and location_info:
            location_text = f"Location highlights for {project_name}: {location_info}"
            location_embedding = generate_embedding(location_text)
            if location_embedding:
                existing_loc = supabase_client.client.table("document_chunks").select("id").eq("project_id", project_id).eq("section", "Location").execute()
                if not existing_loc.data:
                    supabase_client.client.table("document_chunks").insert({
                        "document_id": doc_id,
                        "project_id": project_id,
                        "content": location_text,
                        "embedding": location_embedding,
                        "section": "Location",
                        "source_type": "internal",
                        "chunk_index": 2,
                        "metadata": {"source": "Excel Import"}
                    }).execute()
    
    logger.info("Excel vectorization complete!")

async def verify_data():
    """Verify data in document_chunks."""
    resp = supabase_client.client.table("document_chunks").select("id, project_id, section, content").limit(5).execute()
    logger.info(f"Sample chunks in database: {len(resp.data)}")
    for chunk in resp.data:
        logger.info(f"  - Section: {chunk.get('section')}, Content preview: {chunk.get('content', '')[:100]}...")

async def main():
    await vectorize_excel_data()
    await verify_data()
    logger.info("RAG data ready!")

if __name__ == "__main__":
    asyncio.run(main())
