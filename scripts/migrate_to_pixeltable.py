#!/usr/bin/env python3
"""
Migration Script: Migrate existing data to Pixeltable
Copies projects and documents from Supabase to Pixeltable tables.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def check_dependencies():
    """Check if required packages are installed."""
    try:
        import pixeltable as pxt
        logger.info(f"Pixeltable version: {pxt.__version__ if hasattr(pxt, '__version__') else 'installed'}")
        return True
    except ImportError:
        logger.error("Pixeltable not installed. Run: pip install pixeltable")
        return False


def initialize_pixeltable():
    """Initialize Pixeltable tables."""
    from database.pixeltable_setup import initialize_pixeltable as init_pt
    init_pt()
    logger.info("Pixeltable tables initialized")


def migrate_projects():
    """Migrate projects from Supabase to Pixeltable."""
    import pixeltable as pxt
    from database.supabase_client import supabase_client
    from database.pixeltable_setup import get_projects_table
    
    logger.info("Starting project migration...")
    
    # Get existing projects from Supabase
    try:
        result = supabase_client.client.table("projects").select("*").execute()
        projects = result.data
    except Exception as e:
        logger.warning(f"Could not fetch from Supabase: {e}")
        projects = []
    
    if not projects:
        logger.info("No projects found in Supabase, creating sample projects")
        projects = [
            {
                "project_id": "citrine-001",
                "name": "Brigade Citrine",
                "developer": "Brigade Group",
                "location": "Whitefield, Bangalore",
                "configuration": "2,3,4 BHK",
                "budget_min": 100,  # 1 Cr
                "budget_max": 400,  # 4 Cr
                "possession_year": 2027,
                "possession_quarter": "Q2",
                "status": "Under Construction",
                "rera_number": "PRM/KA/RERA/1250/304/PR/131224/007287",
                "description": "India's First Net Zero Community",
                "amenities": "Clubhouse, Pool, Gym, Tennis Court, Basketball Court",
                "usp": "Net Zero, IGBC Platinum, EV Charging, Solar Powered"
            },
            {
                "project_id": "avalon-001",
                "name": "Brigade Avalon",
                "developer": "Brigade Group",
                "location": "Mysore Road, Bangalore",
                "configuration": "2,3 BHK",
                "budget_min": 80,  # 80L
                "budget_max": 250,  # 2.5 Cr
                "possession_year": 2026,
                "possession_quarter": "Q4",
                "status": "Under Construction",
                "rera_number": None,
                "description": "Premium residential project on Mysore Road",
                "amenities": "Clubhouse, Pool, Gym, Kids Play Area, Jogging Track",
                "usp": "Prime Location, NICE Road Access, Metro Connectivity"
            }
        ]
    
    # Insert into Pixeltable
    projects_table = get_projects_table()
    
    # Transform Supabase format to Pixeltable format
    pt_projects = []
    for p in projects:
        pt_project = {
            "project_id": str(p.get("id", p.get("project_id", ""))),
            "name": p.get("name", ""),
            "developer": p.get("developer", "Brigade Group"),
            "location": p.get("location", ""),
            "configuration": p.get("configuration", p.get("configurations", "")),
            "budget_min": p.get("budget_min", 0),
            "budget_max": p.get("budget_max", 0),
            "possession_year": p.get("possession_year", 2027),
            "possession_quarter": p.get("possession_quarter", "Q4"),
            "status": p.get("status", "Under Construction"),
            "rera_number": p.get("rera_number"),
            "description": p.get("description", ""),
            "amenities": p.get("amenities", ""),
            "usp": p.get("usp", ""),
        }
        pt_projects.append(pt_project)
    
    projects_table.insert(pt_projects)
    logger.info(f"Migrated {len(pt_projects)} projects to Pixeltable")


def migrate_documents():
    """Migrate PDF documents to Pixeltable for auto-chunking."""
    from database.pixeltable_setup import add_document
    
    # Find PDF files in project root
    project_root = Path(__file__).parent.parent.parent
    pdf_files = list(project_root.glob("*.pdf"))
    
    logger.info(f"Found {len(pdf_files)} PDF files to migrate")
    
    # Document to project mapping
    doc_mapping = {
        "brigade citrine": "Brigade Citrine",
        "citrine": "Brigade Citrine",
        "avalon": "Brigade Avalon",
    }
    
    for pdf_path in pdf_files:
        # Determine project name from filename
        filename_lower = pdf_path.stem.lower()
        project_name = "Unknown"
        
        for key, name in doc_mapping.items():
            if key in filename_lower:
                project_name = name
                break
        
        # Determine document type
        doc_type = "brochure"
        if "price" in filename_lower:
            doc_type = "price_list"
        elif "floor" in filename_lower:
            doc_type = "floor_plan"
        
        try:
            add_document(str(pdf_path), project_name, doc_type)
            logger.info(f"Added document: {pdf_path.name} -> {project_name}")
        except Exception as e:
            logger.error(f"Failed to add document {pdf_path.name}: {e}")


def verify_migration():
    """Verify migration was successful."""
    import pixeltable as pxt
    from database.pixeltable_setup import get_projects_table, get_chunks_view, get_faq_table
    
    logger.info("Verifying migration...")
    
    # Check projects
    projects = get_projects_table()
    project_count = len(projects.collect())
    logger.info(f"Projects in Pixeltable: {project_count}")
    
    # Check chunks
    try:
        chunks = get_chunks_view()
        chunk_count = len(chunks.collect())
        logger.info(f"Document chunks in Pixeltable: {chunk_count}")
    except Exception as e:
        logger.warning(f"Could not count chunks: {e}")
        chunk_count = 0
    
    # Check FAQs
    faq = get_faq_table()
    faq_count = len(faq.collect())
    logger.info(f"FAQ entries in Pixeltable: {faq_count}")
    
    # Test similarity search
    if chunk_count > 0:
        from database.pixeltable_setup import search_similar
        results = search_similar("2BHK amenities in Whitefield", top_k=3)
        logger.info(f"Test search returned {len(results)} results")
    
    return {
        "projects": project_count,
        "chunks": chunk_count,
        "faqs": faq_count
    }


def main():
    """Run full migration."""
    print("=" * 60)
    print("PIXELTABLE MIGRATION SCRIPT")
    print("=" * 60)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Initialize tables
    print("\n1. Initializing Pixeltable tables...")
    initialize_pixeltable()
    
    # Migrate projects
    print("\n2. Migrating projects...")
    migrate_projects()
    
    # Migrate documents
    print("\n3. Migrating documents...")
    migrate_documents()
    
    # Verify
    print("\n4. Verifying migration...")
    stats = verify_migration()
    
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"Projects: {stats['projects']}")
    print(f"Document Chunks: {stats['chunks']}")
    print(f"FAQ Entries: {stats['faqs']}")
    print("\nTo use Pixeltable retrieval, set: USE_PIXELTABLE=true")
    print("=" * 60)


if __name__ == "__main__":
    main()
