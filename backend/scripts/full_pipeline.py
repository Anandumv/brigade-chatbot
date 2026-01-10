"""
Full pipeline: Create projects, process PDFs, generate embeddings, store in Supabase.
Run this from the backend directory with venv activated.
"""

import sys
import os
from pathlib import Path

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from supabase import create_client, Client
from scripts.process_documents import PDFProcessor, DocumentChunk
from typing import List
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")  # Use service key to bypass RLS
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

# Initialize clients
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

def create_project(name: str, location: str = "Bangalore") -> str:
    """Create a project in the database and return its ID."""
    try:
        # Check if project exists
        result = supabase.table("projects").select("id").eq("name", name).execute()
        if result.data:
            logger.info(f"Project '{name}' already exists with ID: {result.data[0]['id']}")
            return result.data[0]["id"]
        
        # Create new project
        result = supabase.table("projects").insert({
            "name": name,
            "location": location,
            "status": "ongoing"
        }).execute()
        
        project_id = result.data[0]["id"]
        logger.info(f"Created project '{name}' with ID: {project_id}")
        return project_id
    except Exception as e:
        logger.error(f"Error creating project {name}: {e}")
        raise

def create_document(project_id: str, title: str, doc_type: str = "brochure", file_path: str = "") -> str:
    """Create a document record and return its ID."""
    try:
        # Check if document exists
        result = supabase.table("documents").select("id").eq("title", title).execute()
        if result.data:
            logger.info(f"Document '{title}' already exists with ID: {result.data[0]['id']}")
            return result.data[0]["id"]
        
        result = supabase.table("documents").insert({
            "project_id": project_id,
            "title": title,
            "type": doc_type,
            "version": "1.0",
            "file_path": file_path or f"/documents/{title}"
        }).execute()
        
        doc_id = result.data[0]["id"]
        logger.info(f"Created document '{title}' with ID: {doc_id}")
        return doc_id
    except Exception as e:
        logger.error(f"Error creating document {title}: {e}")
        raise

def generate_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenRouter/OpenAI."""
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
            encoding_format="float"
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise

def insert_chunk_with_embedding(
    chunk: DocumentChunk,
    project_id: str,
    document_id: str,
    embedding: List[float]
) -> bool:
    """Insert a chunk with its embedding into Supabase."""
    try:
        result = supabase.table("document_chunks").insert({
            "document_id": document_id,
            "project_id": project_id,
            "content": chunk.content,
            "embedding": embedding,
            "section": chunk.metadata.get("section", ""),
            "source_type": "internal",
            "confidence_weight": 1.0,
            "chunk_index": chunk.chunk_index,
            "metadata": chunk.metadata
        }).execute()
        return True
    except Exception as e:
        logger.error(f"Error inserting chunk {chunk.chunk_index}: {e}")
        return False

def process_pdf_full_pipeline(pdf_path: str, project_name: str):
    """Full pipeline: process PDF, create records, generate embeddings, store."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing: {project_name}")
    logger.info(f"PDF: {pdf_path}")
    logger.info(f"{'='*60}\n")
    
    # 1. Create project
    project_id = create_project(project_name)
    
    # 2. Process PDF into chunks
    processor = PDFProcessor(chunk_size=800, overlap=100)
    pages = processor.extract_text_from_pdf(pdf_path)
    chunks = processor.chunk_document(
        pages=pages,
        document_name=Path(pdf_path).stem,
        doc_type="brochure",
        project_name=project_name
    )
    logger.info(f"Extracted {len(pages)} pages, created {len(chunks)} chunks")
    
    # 3. Create document record
    document_id = create_document(project_id, Path(pdf_path).stem, "brochure")
    
    # 4. Generate embeddings and insert chunks
    success_count = 0
    for i, chunk in enumerate(chunks):
        try:
            logger.info(f"Processing chunk {i+1}/{len(chunks)}...")
            embedding = generate_embedding(chunk.content)
            if insert_chunk_with_embedding(chunk, project_id, document_id, embedding):
                success_count += 1
        except Exception as e:
            logger.error(f"Failed chunk {i+1}: {e}")
    
    logger.info(f"\n✅ Successfully stored {success_count}/{len(chunks)} chunks for {project_name}")
    return success_count

def main():
    # Define PDF paths relative to chatbot folder
    chatbot_folder = Path(__file__).parent.parent.parent
    
    pdfs_to_process = [
        (chatbot_folder / "Brigade Citrine E_Brochure 01-1.pdf", "Brigade Citrine"),
        (chatbot_folder / "E Brochure - Avalon.pdf", "Brigade Avalon"),
    ]
    
    total_chunks = 0
    for pdf_path, project_name in pdfs_to_process:
        if pdf_path.exists():
            try:
                count = process_pdf_full_pipeline(str(pdf_path), project_name)
                total_chunks += count
            except Exception as e:
                logger.error(f"Failed to process {project_name}: {e}")
        else:
            logger.warning(f"PDF not found: {pdf_path}")
    
    logger.info(f"\n{'='*60}")
    logger.info(f"🎉 COMPLETE! Total chunks stored: {total_chunks}")
    logger.info(f"{'='*60}")

if __name__ == "__main__":
    main()
