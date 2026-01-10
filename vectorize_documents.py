import os
import sys
import logging
import asyncio
from typing import List, Dict
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from config import settings
from services.retrieval import retrieval_service
from database.supabase_client import supabase_client
import openai
from PyPDF2 import PdfReader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI
openai.api_key = settings.openai_api_key

# Re-init Supabase with Service Key if available (for Admin access)
if settings.supabase_service_key:
    from supabase import create_client
    logger.info("Using Supabase Service Key for Admin Access")
    supabase_client.client = create_client(
        settings.supabase_url,
        settings.supabase_service_key
    )
else:
    logger.warning("No Service Key found. RLS may block writes.")

async def get_or_create_project(name: str, location: str) -> str:
    """Get project ID or create if not exists."""
    response = supabase_client.client.table("projects").select("id").eq("name", name).execute()
    if response.data:
        return response.data[0]["id"]
    
    # Create new
    logger.info(f"Creating project: {name}")
    data = {"name": name, "location": location, "status": "ongoing"}
    response = supabase_client.client.table("projects").insert(data).execute()
    return response.data[0]["id"]

async def create_document_record(project_id: str, title: str, file_path: str) -> str:
    """Create document record in DB."""
    data = {
        "project_id": project_id,
        "title": title,
        "type": "brochure",
        "file_path": file_path,
        "uploaded_by": None # System upload
    }
    response = supabase_client.client.table("documents").insert(data).execute()
    return response.data[0]["id"]

def extract_text_from_pdf(file_path: str) -> str:
    """Extract clean text from PDF."""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
    """Split text into chunks with overlap."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += (chunk_size - overlap)
    return chunks

async def generate_embeddings(chunks: List[str]) -> List[List[float]]:
    """Generate embeddings using OpenAI."""
    try:
        response = openai.embeddings.create(
            model=settings.embedding_model,
            input=chunks
        )
        return [data.embedding for data in response.data]
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return []

async def process_file(file_path: str, project_name: str, location: str):
    logger.info(f"Processing {file_path} for {project_name}...")
    
    # 1. Project Setup
    project_id = await get_or_create_project(project_name, location)
    logger.info(f"Project ID: {project_id}")
    
    # 2. Document Setup
    doc_id = await create_document_record(project_id, os.path.basename(file_path), file_path)
    logger.info(f"Document ID: {doc_id}")
    
    # 3. Parse
    text = extract_text_from_pdf(file_path)
    logger.info(f"Extracted {len(text)} characters")
    
    # 4. Chunk
    chunks = chunk_text(text)
    logger.info(f"Created {len(chunks)} chunks")
    
    # 5. Embed (Batch processing)
    batch_size = 20
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i:i+batch_size]
        logger.info(f"Embedding batch {i}-{i+len(batch_chunks)}...")
        
        embeddings = await generate_embeddings(batch_chunks)
        
        if not embeddings:
            logger.error("Failed to generate embeddings")
            continue
            
        # 6. Insert
        rows = []
        for j, (chunk, embedding) in enumerate(zip(batch_chunks, embeddings)):
            rows.append({
                "document_id": doc_id,
                "project_id": project_id,
                "content": chunk,
                "embedding": embedding,
                "chunk_index": i + j,
                "source_type": "internal",
                "metadata": {"source": os.path.basename(file_path)}
            })
            
        supabase_client.client.table("document_chunks").insert(rows).execute()
        
    logger.info(f"Successfully vectorized {file_path}")

async def main():
    files_to_process = [
        ("Brigade Citrine E_Brochure 01-1 (1).pdf", "Brigade Citrine", "Budigere Cross"),
        ("E Brochure - Avalon (1).pdf", "Brigade Avalon", "Bangalore North")
    ]
    
    for file, project, loc in files_to_process:
        if os.path.exists(file):
            await process_file(file, project, loc)
        else:
            logger.warning(f"File not found: {file}")

if __name__ == "__main__":
    asyncio.run(main())
