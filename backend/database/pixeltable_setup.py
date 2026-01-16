"""
Pixeltable Setup and Table Definitions
Creates tables for documents, projects, and FAQ responses with computed columns.
Updated for Pixeltable v0.3+ API.
"""

import pixeltable as pxt
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)


def _dir_exists(name: str) -> bool:
    """Check if a directory exists in Pixeltable."""
    try:
        dirs = pxt.list_dirs()
        # dirs is a list of Dir objects, we need to check .path or .name
        return any(d.path == name or d.name == name for d in dirs) if dirs else False
    except:
        return False


def _table_exists(name: str) -> bool:
    """Check if a table exists in Pixeltable."""
    try:
        # Tables might be in directories, e.g. 'brigade.projects'
        tables = pxt.list_tables()
        if not tables:
            return False
        # Check for exact path match
        for t in tables:
            if t.path == name or t.name == name:
                return True
        return False
    except:
        return False


def initialize_pixeltable():
    """Initialize Pixeltable with required tables and indexes."""
    
    # Check for external DB configuration (Render/Production)
    db_url = os.getenv("PIXELTABLE_DB_URL")
    if db_url:
        logger.info(f"Initializing Pixeltable with external DB: {db_url}")
        # Note: If Pixeltable officially supports this via env var, it might happen automatically.
        # But explicit init is safer if the library allows it. 
        # Assuming standard pxt configuration or init pattern.
        # If pxt.init() isn't standard, we rely on the env var being picked up by the library
        # or we set it in os.environ before import if needed.
        pass 
    
    # Enable logging
    logging.getLogger('pixeltable').setLevel(logging.INFO)

    # Create directory namespace for Brigade chatbot
    if not _dir_exists('brigade'):
        try:
            pxt.create_dir('brigade')
            logger.info("Created 'brigade' directory namespace")
        except Exception as e:
            logger.warning(f"Could not create directory 'brigade' (might exist): {e}")
    
    # Initialize tables
    _create_projects_table()
    _create_query_logs_table()  # Query logging
    
    logger.info("Pixeltable initialization complete")


def _create_projects_table():
    """Create structured projects table matching filter requirements."""
    
    if _table_exists('brigade.projects'):
        logger.info("Projects table already exists")
        return pxt.get_table('brigade.projects')
    
    projects = pxt.create_table('brigade.projects', {
        'project_id': pxt.String,
        'name': pxt.String,
        'developer': pxt.String,
        'location': pxt.String,
        'zone': pxt.String,              # New: "East Bangalore", "North Bangalore"
        'configuration': pxt.String,     # "2BHK", "3BHK", "2,3 BHK"
        'budget_min': pxt.Int,           # In lakhs (e.g., 50 = 50L = 5000000)
        'budget_max': pxt.Int,
        'possession_year': pxt.Int,
        'possession_quarter': pxt.String,
        'status': pxt.String,            # "Ready to Move", "Under Construction"
        'rera_number': pxt.String,
        'description': pxt.String,
        'amenities': pxt.String,         # JSON array as string
        'usp': pxt.String,               # Unique selling points
    })
    
    logger.info("Created brigade.projects table")
    
    # Seed verification data
    _seed_projects_data(projects)
    
    return projects


def _create_documents_table():
    """Create documents table with auto-chunking and embeddings."""
    
    if _table_exists('brigade.documents'):
        logger.info("Documents table already exists")
        return pxt.get_table('brigade.documents')
    
    # Main documents table
    docs = pxt.create_table('brigade.documents', {
        'doc': pxt.Document,
        'project_name': pxt.String,
        'document_type': pxt.String,     # 'brochure', 'price_list', 'floor_plan'
        'source_type': pxt.String,       # 'internal', 'external'
        'uploaded_at': pxt.Timestamp,
    })
    
    logger.info("Created brigade.documents table")
    
    # Create view with auto-chunking
    if not _table_exists('brigade.doc_chunks'):
        chunks = pxt.create_view(
            'brigade.doc_chunks',
            docs,
            iterator=DocumentSplitter.create(
                document=docs.doc,
                separators='sentence,token_limit',
                metadata='page',
                overlap=100,        # Token overlap between chunks
                limit=500,          # Max tokens per chunk
            )
        )
        
        # Add embedding index for similarity search
        chunks.add_embedding_index(
            'text',
            string_embed=openai.Embedding.create,
            model_name='text-embedding-3-small'
        )
        
        logger.info("Created brigade.doc_chunks view with embedding index")
    
    return docs


def _create_faq_table():
    """Create FAQ table with pre-computed GPT responses for sales training."""
    
    if _table_exists('brigade.faq'):
        logger.info("FAQ table already exists")
        return pxt.get_table('brigade.faq')
    
    faq = pxt.create_table('brigade.faq', {
        'faq_type': pxt.String,          # Category of FAQ
        'question': pxt.String,          # Customer question/objection
        'context': pxt.String,           # Additional context
        'priority': pxt.Int,             # Response priority
    })
    
    # Add computed column for LLM response
    faq.add_computed_column(
        response=openai.chat_completions(
            messages=[
                {
                    "role": "system",
                    "content": """You are Pinclick Genie, an expert real estate sales consultant.
                    
Your role is to handle customer objections and FAQs with empathy and persuasive responses.

Guidelines:
1. For BUDGET objections: Explain EMI options, value appreciation potential, hidden costs of renting
2. For LOCATION objections: Highlight connectivity improvements, upcoming infrastructure, lifestyle benefits
3. For UNDER-CONSTRUCTION objections: Explain price advantage (10-15% less), customization options, payment flexibility
4. For MEETING requests: Emphasize personalized service, site visits, detailed walkthroughs
5. For PINCLICK value: Highlight end-to-end support, verified projects, negotiation assistance

ALWAYS end with a soft call-to-action suggesting a meeting or site visit.
Keep responses concise but persuasive (100-150 words max).
Use friendly emojis where appropriate."""
                },
                {
                    "role": "user",
                    "content": faq.question
                }
            ],
            model='gpt-4o-mini'
        ).choices[0].message.content
    )
    
    logger.info("Created brigade.faq table with computed response column")
    
    # Pre-populate with core FAQs from flowchart
    _seed_faq_data(faq)
    
    return faq


def _seed_faq_data(faq_table):
    """Seed FAQ table with the 6 core FAQs from flowchart."""
    
    core_faqs = [
        {
            "faq_type": "budget",
            "question": "How to stretch the budget? My budget is 1 crore but property costs 1.2 crore.",
            "context": "Customer interested but budget is slightly short",
            "priority": 1
        },
        {
            "faq_type": "location",
            "question": "How to convince customer for other location? They want Whitefield but we have better options in Sarjapur.",
            "context": "Customer fixated on specific location",
            "priority": 2
        },
        {
            "faq_type": "possession",
            "question": "How to convince customer for under construction project when they want ready to move?",
            "context": "Customer prefers immediate possession",
            "priority": 3
        },
        {
            "faq_type": "meeting",
            "question": "Why should I schedule a face-to-face meeting? What's the benefit?",
            "context": "Customer hesitant about meeting",
            "priority": 4
        },
        {
            "faq_type": "site_visit",
            "question": "Why should I do a site visit? Can't I just see photos online?",
            "context": "Customer wants convenience over visit",
            "priority": 5
        },
        {
            "faq_type": "pinclick_value",
            "question": "What values does Pinclick add in customer home buying journey?",
            "context": "Customer questioning intermediary value",
            "priority": 6
        }
    ]
    
    faq_table.insert(core_faqs)
    logger.info(f"Seeded {len(core_faqs)} core FAQs into brigade.faq table")


def _seed_projects_data(projects_table):
    """Seed projects table with verified Brigade properties."""
    
    # Check if table is empty
    count = projects_table.count()
    if count > 0:
        logger.info(f"Projects table already has {count} entries, skipping seed.")
        return

    seed_projects = [
        {
            "project_id": "brigade-citrine",
            "name": "Brigade Citrine",
            "developer": "Brigade Group",
            "location": "Budigere Cross",
            "configuration": "2BHK, 3BHK, 4BHK",
            "budget_min": 120,
            "budget_max": 250,
            "possession_year": 2027,
            "possession_quarter": "Q4",
            "status": "Under Construction",
            "rera_number": "PRM/KA/RERA/1251/446/PR/230522/006437",
            "description": "Luxury apartments in Budigere Cross with forest views.",
            "amenities": "['Clubhouse', 'Swimming Pool', 'Gym', 'Forest Trail']",
            "usp": "Forest themed luxury living"
        },
        {
            "project_id": "brigade-avalon",
            "name": "Brigade Avalon",
            "developer": "Brigade Group",
            "location": "Devanahalli",
            "configuration": "1BHK, 2BHK, 3BHK",
            "budget_min": 65,
            "budget_max": 150,
            "possession_year": 2026,
            "possession_quarter": "Q2",
            "status": "Under Construction",
            "rera_number": "PRM/KA/RERA/1250/303/PR/200618/003456",
            "description": "Apartments within Brigade Orchards integrated township.",
            "amenities": "['Sports Arena', 'School', 'Hospital', 'Retail']",
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
            "description": "Premium plotted development near Airport.",
            "amenities": "['Landscaped Gardens', 'Underground Utilities', 'Clubhouse']",
            "usp": "Premium plots with great appreciation potential"
        },
        {
            "project_id": "brigade-calista",
            "name": "Brigade Calista",
            "developer": "Brigade Group",
            "location": "Budigere Cross",
            "configuration": "1.5BHK, 2BHK, 3BHK",
            "budget_min": 75,
            "budget_max": 140,
            "possession_year": 2027,
            "possession_quarter": "Q1",
            "status": "Under Construction",
            "rera_number": "PRM/KA/RERA/1251/446/PR/230302/005763",
            "description": "Vibrant community living with focus on green spaces.",
            "amenities": "['Grand Central Courtyard', 'Eco-friendly features', 'Sports']",
            "usp": "Green living with central courtyard"
        }
    ]
    
    projects_table.insert(seed_projects)
    logger.info(f"Seeded {len(seed_projects)} projects into brigade.projects table")


def get_projects_table():
    """Get the projects table handle."""
    return pxt.get_table('brigade.projects')


def get_documents_table():
    """Get the documents table handle."""
    return pxt.get_table('brigade.documents')


def get_chunks_view():
    """Get the document chunks view with embeddings."""
    return pxt.get_table('brigade.doc_chunks')


def get_faq_table():
    """Get the FAQ table handle."""
    return pxt.get_table('brigade.faq')


# Utility functions for common operations
def add_project(project_data: dict):
    """Add a new project to the projects table."""
    projects = get_projects_table()
    projects.insert([project_data])
    logger.info(f"Added project: {project_data.get('name', 'Unknown')}")


def add_document(file_path: str, project_name: str, doc_type: str = 'brochure'):
    """Add a document to be automatically chunked and indexed."""
    from datetime import datetime
    
    docs = get_documents_table()
    docs.insert([{
        'doc': file_path,
        'project_name': project_name,
        'document_type': doc_type,
        'source_type': 'internal',
        'uploaded_at': datetime.now(),
    }])
    logger.info(f"Added document: {file_path} for project {project_name}")


def search_similar(query: str, project_filter: Optional[str] = None, top_k: int = 5):
    """Search for similar chunks using vector similarity."""
    chunks = get_chunks_view()
    
    # Build query with similarity
    sim = chunks.text.similarity(query)
    
    results = chunks.select(
        chunks.text,
        chunks.page,
        chunks.project_name,
        similarity=sim
    ).order_by(sim, asc=False)
    
    # Apply project filter if provided
    if project_filter:
        results = results.where(chunks.project_name == project_filter)
    
    return results.limit(top_k).collect()

def get_faq_response(faq_type: str) -> Optional[str]:
    """Get pre-computed FAQ response by type."""
    faq = get_faq_table()
    
    result = faq.where(faq.faq_type == faq_type).select(
        faq.response
    ).limit(1).collect()
    
    if result:
        return result[0]['response']
    return None


def _create_query_logs_table():
    """Create query logging table to replace Supabase logging."""
    
    if _table_exists('brigade.query_logs'):
        logger.info("Query logs table already exists")
        return pxt.get_table('brigade.query_logs')
    
    logs = pxt.create_table('brigade.query_logs', {
        'query_id': pxt.String,
        'user_id': pxt.String,
        'query': pxt.String,
        'intent': pxt.String,
        'answered': pxt.Bool,
        'confidence_score': pxt.String,
        'refusal_reason': pxt.String,
        'response_time_ms': pxt.Int,
        'project_id': pxt.String,
        'session_id': pxt.String,
        'created_at': pxt.Timestamp,
    })
    
    logger.info("Created brigade.query_logs table")
    return logs


def get_query_logs_table():
    """Get the query logs table handle."""
    return pxt.get_table('brigade.query_logs')


async def log_query(
    user_id: str,
    query: str,
    intent: str,
    answered: bool,
    confidence_score: str = None,
    refusal_reason: str = None,
    response_time_ms: int = 0,
    project_id: str = None,
    session_id: str = None
):
    """Log a query to Pixeltable (async wrapper for compatibility)."""
    from datetime import datetime
    import uuid
    
    try:
        logs = get_query_logs_table()
        logs.insert([{
            'query_id': str(uuid.uuid4()),
            'user_id': user_id or 'anonymous',
            'query': query,
            'intent': intent,
            'answered': answered,
            'confidence_score': confidence_score or '',
            'refusal_reason': refusal_reason or '',
            'response_time_ms': response_time_ms,
            'project_id': project_id or '',
            'session_id': session_id or '',
            'created_at': datetime.now(),
        }])
        logger.debug(f"Logged query: {query[:50]}...")
    except Exception as e:
        logger.error(f"Failed to log query: {e}")


def get_recent_queries(user_id: str = None, limit: int = 100):
    """Get recent queries, optionally filtered by user."""
    logs = get_query_logs_table()
    
    query = logs.select(
        logs.query_id,
        logs.query,
        logs.intent,
        logs.answered,
        logs.confidence_score,
        logs.response_time_ms,
        logs.created_at
    ).order_by(logs.created_at, asc=False)
    
    if user_id:
        query = query.where(logs.user_id == user_id)
    
    return query.limit(limit).collect()


def get_analytics_data(days: int = 7):
    """Get analytics data for dashboard."""
    from datetime import datetime, timedelta
    
    logs = get_query_logs_table()
    cutoff = datetime.now() - timedelta(days=days)
    
    # Get all logs from the period
    results = logs.where(
        logs.created_at >= cutoff
    ).select(
        logs.intent,
        logs.answered,
        logs.refusal_reason,
        logs.response_time_ms
    ).collect()
    
    if not results:
        return {
            'total_queries': 0,
            'answered_queries': 0,
            'refused_queries': 0,
            'refusal_rate': 0,
            'avg_response_time_ms': 0,
            'top_intents': {},
            'recent_refusals': []
        }
    
    total = len(results)
    answered = sum(1 for r in results if r['answered'])
    refused = total - answered
    
    # Count intents
    intent_counts = {}
    for r in results:
        intent = r['intent']
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
    
    # Calculate avg response time
    times = [r['response_time_ms'] for r in results if r['response_time_ms']]
    avg_time = sum(times) / len(times) if times else 0
    
    return {
        'total_queries': total,
        'answered_queries': answered,
        'refused_queries': refused,
        'refusal_rate': refused / total if total > 0 else 0,
        'avg_response_time_ms': avg_time,
        'top_intents': intent_counts,
        'recent_refusals': []  # Can be expanded
    }


if __name__ == "__main__":
    # Initialize tables when run directly
    logging.basicConfig(level=logging.INFO)
    initialize_pixeltable()
    print("Pixeltable tables initialized successfully!")

