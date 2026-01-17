"""
Main FastAPI application for Real Estate Sales Intelligence Chatbot.
Powered by Pixeltable - No Supabase Required!
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import logging
from contextlib import asynccontextmanager
import sys
import os
# Add the vendor directory to sys.path to allow importing local packages (e.g. patched pixeltable)
# We add it at the BEGINNING of sys.path to ensure local versions take precedence
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'vendor')))

import nest_asyncio
import json
import asyncio


# Apply nest_asyncio to allow re-entrant event loops
# Wrap in try-except because it fails with 'uvloop' (default on Render)
logging.info("Starting up application...")
try:
    nest_asyncio.apply()
    logging.info("nest_asyncio applied successfully")
except Exception as e:
    logging.warning(f"Could not patch event loop: {e}")

logging.info("Imports completed. Initializing FastAPI app...")

from config import settings
from services.flow_engine import FlowEngine, flow_engine
from services.retrieval import retrieval_service # Deferred import to prevent hang
from services.intelligent_fallback import intelligent_fallback

from services.confidence_scorer import confidence_scorer
from services.refusal_handler import refusal_handler
from services.answer_generator import answer_generator
from services.multi_project_retrieval import multi_project_retrieval
from services.persona_pitch import persona_pitch_generator
from services.web_search import web_search_service
from services.hybrid_retrieval import hybrid_retrieval
from services.filter_extractor import filter_extractor
from services.response_formatter import response_formatter
from services.query_preprocessor import query_preprocessor
from services.sales_conversation import sales_conversation, get_filter_options, SalesIntent
from services.intelligent_sales import intelligent_sales, ConversationContext, SalesIntent as AISalesIntent
from services.sales_intelligence import sales_intelligence
from services.intent_classifier import intent_classifier  # Legacy fallback
from services.gpt_intent_classifier import classify_intent_gpt_first  # GPT-first primary
from services.gpt_content_generator import generate_insights, enhance_with_gpt
from services.gpt_sales_consultant import generate_consultant_response  # Unified consultant handler
from services.session_manager import session_manager

# Pixeltable-only mode - replacing Supabase
from database.pixeltable_client import pixeltable_client

# Force reload triggers
# Last updated: Migrated to Pixeltable-only architecture

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# === Routing Helper Functions ===

def is_property_search_query(query: str, intent: str, filters: Optional[Dict] = None) -> bool:
    """
    Determine if query should route to PATH 1: Property Search.

    Returns True if:
    - Intent is "property_search"
    - Has explicit filters (config/budget/location)
    - Contains search phrases like "show me", "find", "search for"
    """
    # Convert Pydantic model to dict if needed
    if filters and hasattr(filters, 'model_dump'):
        filters = filters.model_dump()
    
    # Explicit property search intent
    if intent == "property_search":
        return True

    # Has filters from UI or extraction
    if filters and isinstance(filters, dict) and any(filters.values()):
        return True

    # Search phrases
    search_phrases = ["show me", "find", "search for", "looking for", "need", "want"]
    query_lower = query.lower()
    if any(phrase in query_lower for phrase in search_phrases):
        # Must also have property indicators (bhk, property, apartment, etc.)
        property_indicators = ["bhk", "property", "properties", "apartment", "flat", "villa", "project"]
        if any(indicator in query_lower for indicator in property_indicators):
            return True

    return False


def is_project_details_query(query: str, intent: str) -> bool:
    """
    Determine if query should route to PATH 2: Project Details/Facts.

    Returns True if:
    - Intent is "project_details" or "project_fact"
    - Factual query already handled (this is checked earlier in pipeline)
    """
    return intent in ["project_details", "project_fact"]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    logger.info("Starting Real Estate Sales Intelligence Chatbot API v1.1...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Similarity threshold: {settings.similarity_threshold}")
    logger.info(f"Embedding model: {settings.embedding_model}")
    logger.info("Vector fallback enabled for property search")
    
    # Auto-seed projects if table is empty
    try:
        from database.pixeltable_setup import get_projects_table, initialize_pixeltable
        import json
        import os
        import pixeltable as pxt
        
        # Ensure tables exist
        initialize_pixeltable()
        
        projects_table = get_projects_table()
        count = projects_table.count()
        logger.info(f"Projects table has {count} rows.")
        
        if count == 0:
            seed_file = os.path.join(os.path.dirname(__file__), 'data', 'seed_projects.json')
            if os.path.exists(seed_file):
                with open(seed_file, 'r') as f:
                    seed_data = json.load(f)
                projects_table.insert(seed_data)
                logger.info(f"Seeded {len(seed_data)} projects from seed_projects.json")
            else:
                logger.warning(f"Seed file not found: {seed_file}")
    except Exception as e:
        logger.error(f"Auto-seed failed: {e}")
    
    yield
    logger.info("Shutting down API...")


# Initialize FastAPI app
app = FastAPI(
    title="Real Estate Sales Intelligence Chatbot",
    description="Grounded, non-hallucinatory chatbot for real estate sales teams",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Request/Response Models ===

class ChatQueryRequest(BaseModel):
    """Request model for chat query."""
    query: str
    project_id: Optional[str] = None
    user_id: Optional[str] = None  # Required for logging
    session_id: Optional[str] = None  # For multi-turn conversations
    persona: Optional[str] = None  # Phase 2: persona-based pitches
    filters: Optional[Dict[str, Any]] = None  # UI-selected filters


class SourceInfo(BaseModel):
    """Source information for answer."""
    document: str
    section: Optional[str] = "General"
    page: Optional[int] = None
    excerpt: str
    similarity: float


class ChatQueryResponse(BaseModel):
    """Response model for chat query."""
    answer: str
    sources: List[SourceInfo]
    confidence: str  # 'High', 'Medium', or 'Not Available'
    intent: str
    refusal_reason: Optional[str] = None
    response_time_ms: int
    data: Optional[Dict[str, Any]] = None
    projects: List[Dict[str, Any]] = []  # Default to empty list instead of None
    suggested_actions: Optional[List[str]] = None  # Dynamic quick reply chips


class ProjectInfo(BaseModel):
    """Project information."""
    id: str
    name: str
    location: str
    status: str
    rera_number: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    environment: str
    version: str


# === API Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": "1.0.0"
    }


@app.post("/admin/refresh-projects")
async def admin_refresh_projects(x_admin_key: str = Header(None)):
    """
    Admin endpoint to force re-seed/update project data from seed_projects.json.
    """
    import json
    import os
    import pixeltable as pxt
    
    # Use dedicated ADMIN_KEY env var
    expected_key = os.getenv("ADMIN_KEY", "secret")
    
    if not x_admin_key or x_admin_key != expected_key:
         raise HTTPException(status_code=403, detail="Invalid Admin Key")

    try:
        # Drop existing and recreate with fresh data
        try:
            pxt.drop_table('brigade.projects', force=True)
            logger.info("Dropped existing projects table")
        except Exception as e:
            logger.warning(f"Could not drop table: {e}")
        
        # Create fresh table with schema
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
            'rm_details': pxt.Json,
            'brochure_url': pxt.String,
            'registration_process': pxt.String,
        }
        
        projects = pxt.create_table('brigade.projects', schema)
        logger.info("Created fresh projects table")
        
        # Load from JSON
        seed_file = os.path.join(os.path.dirname(__file__), 'data', 'seed_projects.json')
        if os.path.exists(seed_file):
            with open(seed_file, 'r') as f:
                seed_data = json.load(f)
            projects.insert(seed_data)
            return {"status": "success", "message": f"Loaded {len(seed_data)} projects"}
        else:
            return {"status": "error", "message": f"Seed file not found: {seed_file}"}
            
    except Exception as e:
        logger.error(f"Admin refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/query", response_model=ChatQueryResponse)
async def chat_query(request: ChatQueryRequest):
    """
        ChatQueryResponse with answer, sources, and metadata
    """
    start_time = time.time()

    try:
        logger.info(f"Processing query: {request.query[:100]}...")

        # Step 0: Preprocess Query
        original_query = request.query
        normalized_query = query_preprocessor.preprocess(request.query)
        request.query = normalized_query
        logger.info(f"Normalized query: '{original_query}' -> '{normalized_query}'")

        # Step 0.5: Get or Create Session and Load Context
        session = None
        context_summary_dict = {}
        if request.session_id:
            session = session_manager.get_or_create_session(request.session_id)
            context_summary_dict = session_manager.get_context_summary(request.session_id)
        
        # Step 0.6: Context Injection - Enrich vague queries with session context
        from services.context_injector import (
            enrich_query_with_context, 
            inject_context_metadata,
            should_use_gpt_fallback
        )
        
        enriched_query = request.query
        was_enriched = False
        
        if session:
            enriched_query, was_enriched = enrich_query_with_context(request.query, session)
            if was_enriched:
                logger.info(f"Query enriched: '{request.query}' → '{enriched_query}'")
                # Use enriched query for classification
                request.query = enriched_query

        # Get full context metadata
        context_metadata = inject_context_metadata(original_query, session)

        # Step 1: GPT-First Intent Classification with Intelligent Data Source Routing
        # Get conversation history and session state for context
        conversation_history = []
        session_state = {}
        if session:
            # Format messages for GPT context (now 10 turns for better context)
            conversation_history = [
                {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                for msg in session.messages[-10:]
            ]
            session_state = {
                "selected_project_name": session.interested_projects[-1] if session.interested_projects else None,
                "requirements": session.current_filters,
                "last_intent": session.last_intent,
                "last_topic": session.last_topic,
                "conversation_phase": session.conversation_phase
            }
        
        # GPT-first classification with data source selection and enhanced context
        gpt_result = classify_intent_gpt_first(
            query=request.query,
            conversation_history=conversation_history,
            session_state=session_state,
            context_summary=context_summary_dict.get("summary")
        )
        
        intent = gpt_result.get("intent", "unsupported")
        data_source = gpt_result.get("data_source", "database")
        gpt_confidence = gpt_result.get("confidence", 0.0)
        extraction = gpt_result.get("extraction", {})
        
        # Initialize project_name early to avoid UnboundLocalError in property_search handler
        project_name = extraction.get("project_name") if extraction else None
        
        logger.info(f"GPT Classification: intent={intent}, data_source={data_source}, confidence={gpt_confidence}")
        
        # Fallback to keyword classifier if GPT confidence is too low AND no context
        if gpt_confidence < 0.5 and not context_metadata.get("has_context"):
            logger.warning(f"GPT confidence too low ({gpt_confidence}), falling back to keyword classifier")
            intent = intent_classifier.classify_intent(request.query)
            data_source = "database"  # Default to database for fallback
            logger.info(f"Keyword fallback intent: {intent}")
        
        # CRITICAL: Check if we should use GPT fallback instead of specific handlers
        # This prevents asking clarifying questions when context exists
        use_gpt_fallback = False
        if session and should_use_gpt_fallback(original_query, session, gpt_confidence):
            use_gpt_fallback = True
            logger.info("Routing to GPT fallback to maintain conversation flow")
        
        # If we're using GPT fallback, generate response directly
        if use_gpt_fallback:
            from services.gpt_content_generator import generate_contextual_response_with_full_history
            
            response_text = generate_contextual_response_with_full_history(
                query=original_query,
                conversation_history=conversation_history,
                session_context=context_summary_dict,
                goal="Continue the conversation naturally without asking clarifying questions"
            )
            
            # Update session
            if session:
                session_manager.add_message(request.session_id, "user", original_query)
                session_manager.add_message(request.session_id, "assistant", response_text[:500])
                session.last_intent = intent
                if extraction.get("topic"):
                    session.last_topic = extraction["topic"]
                session_manager.save_session(session)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return ChatQueryResponse(
                answer=response_text,
                sources=[],
                confidence="High",
                intent="gpt_contextual_fallback",
                refusal_reason=None,
                response_time_ms=response_time_ms,
                suggested_actions=["Schedule site visit", "Compare projects", "Get more details"]
            )

        # Contextual Override for "Show More" / "Tell me more"
        # If user asks to elaborate on a previous non-search topic, force it to 'more_info_request'
        show_more_patterns = ["show more", "tell me more", "more details", "elaborate", "continue", "go on"]
        is_show_more = any(p in request.query.lower() for p in show_more_patterns) and len(request.query.split()) < 5
        
        if is_show_more and request.session_id:
             session = session_manager.get_or_create_session(request.session_id)
             if session.last_intent in ["sales_faq", "sales_objection", "more_info_request", "faq_budget_stretch", "faq_pinclick_value"]:
                 logger.info(f"Contextual Override: 'Show more' mapped to more_info_request (prev: {session.last_intent})")
                 intent = "more_info_request"
                 # Start specific logic for elaboration
                 # We rely on intelligent sales handler or more_info_request handler to pick this up

        # Step 1.5: FACTUAL QUERY INTERCEPTOR - Fetch real database facts BEFORE classification
        # This prevents GPT from making up information about project facts
        from services.project_fact_extractor import detect_project_fact_query, get_project_fact, format_fact_response
        
        fact_query_detection = detect_project_fact_query(original_query)
        if fact_query_detection and fact_query_detection.get("is_factual_query"):
            logger.info(f"Detected factual query: {fact_query_detection}")
            
            # Fetch REAL data from database
            fact_data = get_project_fact(
                project_name=fact_query_detection["project_name"],
                fact_type=fact_query_detection["fact_type"],
                bhk_type=fact_query_detection.get("bhk_type")
            )
            
            if fact_data:
                # Format response using ONLY database facts
                fact_response = format_fact_response(fact_data, original_query)
                
                if fact_response:
                    response_time_ms = int((time.time() - start_time) * 1000)
                    
                    # Update session
                    if session:
                        session_manager.add_message(request.session_id, "user", original_query)
                        session_manager.add_message(request.session_id, "assistant", fact_response[:500])
                        session.last_intent = f"factual_{fact_query_detection['fact_type']}"
                        if fact_query_detection["project_name"]:
                            session_manager.record_interest(request.session_id, fact_query_detection["project_name"])
                        session_manager.save_session(session)
                    
                    logger.info(f"Returned database fact for {fact_query_detection['project_name']}: {fact_query_detection['fact_type']}")
                    
                    return ChatQueryResponse(
                        answer=fact_response,
                        sources=[{
                            "document": "projects_table",
                            "excerpt": f"Database fact: {fact_query_detection['fact_type']} for {fact_query_detection['project_name']}",
                            "similarity": 1.0
                        }],
                        confidence="High",
                        intent=f"factual_{fact_query_detection['fact_type']}",
                        refusal_reason=None,
                        response_time_ms=response_time_ms,
                        suggested_actions=["Schedule site visit", "View similar projects", "Get more details"]
                    )
        
        # Step 1.6: LOCATION COMPARISON INTERCEPTOR
        # Prevent location comparison questions from triggering property searches
        from services.context_injector import is_location_comparison_query
        
        if is_location_comparison_query(original_query):
            logger.info(f"Detected location comparison query: {original_query}")
            
            # Generate generic comparison answer using GPT
            from services.gpt_content_generator import generate_contextual_response_with_full_history
            
            response_text = generate_contextual_response_with_full_history(
                query=original_query,
                conversation_history=conversation_history if session else [],
                session_context={},
                goal="Provide a generic, informative comparison of Bangalore locations/areas. Discuss factors like connectivity, IT hub proximity, infrastructure, appreciation potential, and lifestyle. Keep it neutral and educational, NOT project-specific. End with: 'Would you like to explore properties in any of these areas?'"
            )
            
            # Update session
            if session:
                session_manager.add_message(request.session_id, "user", original_query)
                session_manager.add_message(request.session_id, "assistant", response_text[:500])
                session.last_intent = "location_comparison_generic"
                session_manager.save_session(session)
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            return ChatQueryResponse(
                answer=response_text,
                sources=[],
                confidence="High",
                intent="location_comparison_generic",
                refusal_reason=None,
                response_time_ms=response_time_ms,
                suggested_actions=["Explore properties in these areas", "Learn about other locations", "Get personalized recommendations"]
            )
        
        # Step 1.7: FUZZY PROJECT NAME DETECTION
        # Intercept queries like "need details of avalon" or "more info on folium"
        from services.fuzzy_matcher import (
            extract_project_name_from_query, 
            get_project_from_database, 
            is_project_detail_request
        )
        
        if is_project_detail_request(request.query):
            matched_project_name = extract_project_name_from_query(request.query)
            project = None  # Safe initialization

            if matched_project_name:
                logger.info(f"Fuzzy matched project: '{matched_project_name}'")
                project = get_project_from_database(matched_project_name)
                
            # Determine if this is a generic request or a specific question
            # Simple heuristic: if query length is short and contains "details", "info", "about", it's generic.
            # If it contains specific keywords like "price", "location", "amenities", "distance", etc., let GPT handle it.
            is_general_request = is_project_detail_request(request.query) and len(request.query.split()) < 10

            if is_general_request and project:
                # Override intent to project_details and show project info
                intent = "project_details"
                extraction["project_name"] = project.get("name")
                logger.info(f"Overriding to project_details for: {project.get('name')}")
                
                # Generate project details response directly
                from services.flow_engine import clean_configuration_string, format_configuration_table
                
                proj = project
                response_parts = [f"🏠 **{proj.get('name')}** - Here's everything you need to know:\n\n"]
                
                if proj.get('developer'):
                    response_parts.append(f"**🏗️ Developer:** {proj.get('developer')}\n")
                
                response_parts.append(f"**📍 Location:** {proj.get('location')}\n")
                
                budget_min = proj.get('budget_min', 0) / 100 if proj.get('budget_min') else 0
                budget_max = proj.get('budget_max', 0) / 100 if proj.get('budget_max') else 0
                response_parts.append(f"**💰 Price Range:** ₹{budget_min:.2f} - ₹{budget_max:.2f} Cr\n")
                
                if proj.get('configuration'):
                    config_table = format_configuration_table(proj.get('configuration', ''))
                    response_parts.append(f"**🛏️ Configurations:**\n{config_table}\n")
                
                response_parts.append(f"**📊 Status:** {proj.get('status')}\n")
                response_parts.append(f"**📅 Possession:** {proj.get('possession_quarter', '')} {proj.get('possession_year', '')}\n")
                
                if proj.get('rera_number'):
                    response_parts.append(f"**📋 RERA:** {proj.get('rera_number')}\n")
                
                if proj.get('usp') and len(proj.get('usp', '')) > 5:
                    response_parts.append(f"\n**✨ Why this property?**\n{proj.get('usp')}\n")
                
                if proj.get('amenities'):
                    amenities = proj.get('amenities', '').replace("[", "").replace("]", "").replace("'", "")
                    response_parts.append(f"\n**🎯 Key Amenities:** {amenities}\n")
                
                # Brochure Download
                if proj.get('brochure_url'):
                    response_parts.append(f"\n[📄 **Download Brochure**]({proj.get('brochure_url')})\n")
                
                # RM Details
                rm = proj.get('rm_details', {})
                if rm:
                    response_parts.append(f"\n👤 **Relationship Manager:** {rm.get('name', 'Expert')} ({rm.get('contact', '')})\n")
                
                # Registration Process
                if proj.get('registration_process'):
                    response_parts.append(f"\n📝 **Registration Process:**\n{proj.get('registration_process')}\n")
                
                response_parts.append("\n👉 **Ready to see it in person? Schedule a site visit!**")
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Record interest
                try:
                    # Logging interaction (stubbed out as record_interaction is not available)
                    pass 
                    # flow_engine.record_interaction(
                    #     session_id=request.session_id,
                    #     user_query=request.query,
                    #     intent="project_details",
                    #     response="\n".join(response_parts),
                    #     project_name=project.get("name")
                    # )
                except Exception as e:
                    logger.error(f"Failed to record interaction: {e}")

                return ChatQueryResponse(
                    answer="\n".join(response_parts),
                    sources=[{
                        "document": "projects_table",
                        "excerpt": f"Details for {project.get('name')}",
                        "similarity": 1.0
                    }],
                    confidence="High",
                    intent="project_details",
                    refusal_reason=None,
                    response_time_ms=0, # Calculated later if needed or placeholder
                    suggested_actions=[]
                )
            elif project:
                # Specific question ("distance of airport from avalon")
                # Route to GPT but inject project name so generator knows context
                logger.info(f"Specific project question detected for: {project.get('name')}")
                intent = "more_info_request"
                data_source = "gpt_generation"
                extraction["project_name"] = project.get("name")
                extraction["topic"] = "specific_query"

        # Extract and merge filters early (needed for context and search)
        filters = filter_extractor.extract_filters(request.query)
        if request.filters:
            logger.info(f"Merging explicit UI filters: {request.filters}")
            filters = filter_extractor.merge_filters(filters, request.filters)
        
        # Create conversation context
        context = ConversationContext(
            session_id=request.session_id or "",
            current_filters=request.filters or {},
            last_intent=intent.value if hasattr(intent, 'value') else str(intent)
        )


        # ========================================
        # SIMPLIFIED 2-PATH ROUTING
        # ========================================
        # Route based on data_source (not intent!)
        # PATH 1: Database → Property search & facts
        # PATH 2: GPT Sales Consultant → Everything else (DEFAULT)
        # ========================================

        # Check if unified consultant is enabled (feature flag)
        USE_UNIFIED_CONSULTANT = os.getenv("USE_UNIFIED_CONSULTANT", "true").lower() == "true"

        # PATH 1: Database Queries (property_search or project_facts)
        if data_source == "database":
            if intent == "property_search":
                logger.info("🔹 PATH 1: Database - Property Search")

                # Perform Hybrid Retrieval
                search_results = await hybrid_retrieval.search_with_filters(
                    query=request.query,
                    filters=filters
                )

                # Update session with shown projects
                if session:
                    session.last_shown_projects = search_results["projects"]
                    session.last_intent = "property_search"
                    session_manager.save_session(session)
                    logger.info(f"Updated session with {len(search_results['projects'])} shown projects")

                response_time_ms = int((time.time() - start_time) * 1000)

                # Log the interaction
                if request.user_id:
                    await pixeltable_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent="property_search",
                        answered=True,
                        confidence_score="High",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )

                return ChatQueryResponse(
                    answer=f"I found {len(search_results['projects'])} projects matching your criteria. Here are the details:",
                    projects=search_results["projects"],
                    sources=[],
                    confidence="High",
                    intent="property_search",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=[]
                )
            
            elif intent == "project_facts":
                logger.info("🔹 PATH 1: Database - Project Facts (handled by factual interceptor above)")
                # This is already handled by the factual query interceptor earlier (lines 438-505)
                # If we reach here, fall through to GPT consultant
                pass

        # PATH 2: GPT Sales Consultant (DEFAULT for everything else)
        # Handles: amenities, distances, advice, FAQs, objections, "more", greetings, all conversational queries
        logger.info(f"🔹 PATH 2: GPT Sales Consultant - intent={intent}")

        # Generate conversational response using unified consultant
        response_text = await generate_consultant_response(
            query=request.query,
            session=session,
            intent=intent
        )

        # Update session
        if session and request.session_id:
            session_manager.add_message(request.session_id, "user", request.query)
            session_manager.add_message(request.session_id, "assistant", response_text[:500])
            session.last_intent = intent if intent != "unsupported" else "sales_conversation"
            
            # Update last_topic if provided in extraction
            if extraction and extraction.get("topic"):
                session.last_topic = extraction["topic"]
                logger.info(f"Updated session.last_topic to: {session.last_topic}")
            
            session_manager.save_session(session)

        response_time_ms = int((time.time() - start_time) * 1000)

        # Log the interaction
        if request.user_id:
            await pixeltable_client.log_query(
                user_id=request.user_id,
                query=request.query,
                intent=intent,
                answered=True,
                confidence_score="High",
                response_time_ms=response_time_ms,
                project_id=request.project_id
            )

        return ChatQueryResponse(
            answer=response_text,
            sources=[],
            confidence="High",
            intent=intent,
            refusal_reason=None,
            response_time_ms=response_time_ms,
            suggested_actions=[]
        )

        # ========================================
        # FALLBACK TO OLD ROUTING (if feature flag disabled)
        # ========================================
        else:
            logger.info("Using legacy routing (unified consultant disabled)")

        # Step 1.5: Handle greetings immediately without RAG (LEGACY)
        if not USE_UNIFIED_CONSULTANT and intent == "greeting":
            response_time_ms = int((time.time() - start_time) * 1000)
            greeting_response = """👋 **Hello!** Welcome to Pinclick Genie!

I'm your AI-powered real estate assistant. I can help you with:

🏠 **Property Search** - "Show me 2BHK in Bangalore under 2 Cr"
🏢 **Project Details** - "Tell me about Brigade Citrine amenities"
💰 **Pricing Info** - "What's the price of 3BHK at Brigade Avalon?"
📍 **Location Info** - "Projects near Whitefield"
🤝 **Sales Support** - "Schedule a site visit" or "Arrange a meeting"

How can I assist you today?"""
            return ChatQueryResponse(
                answer=greeting_response,
                sources=[],
                confidence="High",
                intent="greeting",
                refusal_reason=None,
                response_time_ms=response_time_ms
            )

        # Step 1.6: Handle sales FAQ intents with intelligent GPT-4 handler
        if intent == "sales_faq":
            logger.info("Routing to intelligent sales FAQ handler")

            # Build rich session context for FAQ generation
            session_context_enriched = context_summary_dict.copy() if context_summary_dict else {}

            # CRITICAL: Ensure last_shown_projects is included
            if session and hasattr(session, 'last_shown_projects'):
                session_context_enriched["last_shown_projects"] = session.last_shown_projects
                logger.info(f"Injecting {len(session.last_shown_projects)} shown projects into FAQ context")

            response_text, sales_intent, should_fallback, actions = await intelligent_sales.handle_query(
                query=request.query,
                context=context,
                session_id=request.session_id,
                conversation_history=conversation_history,
                session_context=session_context_enriched  # Pass enriched context
            )
            
            if not should_fallback and response_text:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if request.user_id:
                    await pixeltable_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent=f"intelligent_faq_{sales_intent.value}",
                        answered=True,
                        confidence_score="High",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )
                
                if request.session_id:
                    session = session_manager.get_or_create_session(request.session_id)
                    # Update session with new intent (e.g. faq_budget_stretch) using sales_intent from intelligent handler
                    intent_val = sales_intent.value if hasattr(sales_intent, "value") else "sales_faq"
                    session.last_intent = intent_val
                    if extraction.get("topic"):
                        session.last_topic = extraction["topic"]
                    session_manager.save_session(session)

                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="High",
                    intent="intelligent_sales_faq",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=[]
                )

        # Step 1.6b: Handle meeting_request intent - GPT generates response
        if intent == "meeting_request":
            logger.info("Routing to GPT for meeting request")
            
            try:
                
                # Generate meeting guidance using GPT
                meeting_context = {
                    "name": "Meeting Request",
                    "location": "Bangalore",
                    "amenities": "Office visits, Site visits, Video calls available"
                }
                
                response_text = generate_insights(
                    project_facts=meeting_context,
                    topic="meeting_scheduling",
                    query=request.query,
                    user_requirements=None
                )
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="High",
                    intent="meeting_request",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=[]
                )
            except Exception as e:
                logger.error(f"GPT meeting generation failed: {e}")
                # Fallback to flow engine

        # Step 1.7: Handle sales objection intents with intelligent handler
        if intent == "sales_objection":
            logger.info("Routing to intelligent sales objection handler")

            # Record objection in session
            objection_type = extraction.get("objection_type", "general")
            if request.session_id:
                session_manager.record_objection(request.session_id, objection_type)

            # Build rich session context for objection handling
            session_context_enriched = context_summary_dict.copy() if context_summary_dict else {}

            # CRITICAL: Ensure last_shown_projects is included
            if session and hasattr(session, 'last_shown_projects'):
                session_context_enriched["last_shown_projects"] = session.last_shown_projects
                logger.info(f"Injecting {len(session.last_shown_projects)} shown projects into objection context")

            response_text, sales_intent, should_fallback, actions = await intelligent_sales.handle_query(
                query=request.query,
                context=context,
                session_id=request.session_id,
                conversation_history=conversation_history,
                session_context=session_context_enriched  # Pass enriched context
            )
            
            if not should_fallback and response_text:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if request.user_id:
                    await pixeltable_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent=f"intelligent_objection_{sales_intent.value}",
                        answered=True,
                        confidence_score="High",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )
                
                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="High",
                    intent="intelligent_sales_objection",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=[]
                )

        # Step 1.8: Handle more_info_request with GPT content generation
        # Also catch "more pointers" / "tell me more" queries even if data_source isn't explicitly gpt_generation
        more_info_keywords = ["more pointers", "tell me more", "more about", "more details", "elaborate", "explain more"]
        is_more_info_query = any(kw in request.query.lower() for kw in more_info_keywords)
        
        if (intent == "more_info_request" and data_source in ["gpt_generation", "hybrid"]) or is_more_info_query:
            logger.info(f"Routing more_info_request to GPT content generator (data_source={data_source}, is_more_info_query={is_more_info_query})")
            
            # Get project from extraction, query text, or session
            project_name = extraction.get("project_name")
            topic = extraction.get("topic", "general_selling_points")
            
            # Try to extract project name from query if not in extraction
            if not project_name:
                query_lower = request.query.lower()
                # Common project keywords to match
                # Common project keywords to match
                # Common project keywords to match
                project_keywords = ["avalon", "citrine", "neopolis", "brigade", "sobha", "prestige", "godrej", "birla", "evara", "ojasvi", "woods", "calista", "7 gardens", "panache", "folium", "sumadhura", "eden", "serene"]
                for keyword in project_keywords:
                    if keyword in query_lower:
                        project_name = keyword.title()  # e.g., "avalon" -> "Avalon"
                        if keyword == "avalon":
                            project_name = "Brigade Avalon"
                        elif keyword == "citrine":
                            project_name = "Brigade Citrine"
                        elif keyword == "evara":
                            project_name = "Birla Evara"
                        elif keyword == "folium" or keyword == "sumadhura":
                            project_name = "Sumadhura Folium"
                        elif keyword == "eden":
                            project_name = "Godrej Eden"
                        elif keyword == "serene":
                            project_name = "Godrej Serene"
                        elif keyword == "woods":
                            project_name = "Godrej Woods"
                        break
            
            if not project_name and request.session_id:
                session = session_manager.get_or_create_session(request.session_id)
                if session.interested_projects:
                    project_name = session.interested_projects[-1]
            
            if project_name:
                # Get project facts from database
                try:
                    from database.pixeltable_setup import get_projects_table
                    projects_table = get_projects_table()
                    
                    if projects_table:
                        # Query for project by name
                        results = list(projects_table.where(
                            projects_table.name.contains(project_name)
                        ).limit(1).collect())
                        
                        if results:
                            project_facts = results[0]
                            
                            # Pure GPT generation for insights
                            response_text = generate_insights(
                                project_facts=project_facts,
                                topic=topic,
                                query=request.query,
                                user_requirements=session_state.get("requirements")
                            )
                            
                            response_time_ms = int((time.time() - start_time) * 1000)
                            
                            # Record interest in this project
                            if request.session_id:
                                session_manager.record_interest(request.session_id, project_name)
                            
                            if request.user_id:
                                await pixeltable_client.log_query(
                                    user_id=request.user_id,
                                    query=request.query,
                                    intent=f"gpt_more_info_{topic}",
                                    answered=True,
                                    confidence_score="High",
                                    response_time_ms=response_time_ms,
                                    project_id=request.project_id
                                )
                            
                            return ChatQueryResponse(
                                answer=response_text,
                                sources=[],
                                confidence="High",
                                intent="gpt_more_info",
                                refusal_reason=None,
                                response_time_ms=response_time_ms,
                                suggested_actions=[]
                            )
                        else:
                            # Project name found but no data in DB -> Fallback to Generic GPT
                            logger.warning(f"Project '{project_name}' not found in DB. Falling back to generic GPT.")
                    
                except Exception as e:
                    logger.error(f"GPT content generation failed: {e}")
                    # Fallback to generic GPT (below)

            # Fallback for:
            # 1. Project name not found in query/session
            # 2. Project found in query but not in DB
            # 3. Exception during DB lookup
            
            logger.info("Falling back to generic GPT for more_info_request")
            from services.master_prompt import get_general_prompt
            from services.gpt_content_generator import client, settings
            
            prompt = get_general_prompt(request.query)
            
            try:
                response = client.chat.completions.create(
                    model=settings.effective_gpt_model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7
                )
                response_text = response.choices[0].message.content
                
                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="Medium",
                    intent="gpt_general_fallback",
                    refusal_reason=None,
                    response_time_ms=int((time.time() - start_time) * 1000),
                    suggested_actions=[]
                )
            except Exception as e:
                logger.error(f"Generic GPT fallback failed: {e}")
                # Finally fall through to flow engine if even this fails

        # DISABLED: Legacy flow_engine routing - now handled by unified GPT consultant
        # The unified consultant (lines 703-744) provides better conversational responses
        # Only re-enable this if USE_UNIFIED_CONSULTANT is set to false
        if False and not USE_UNIFIED_CONSULTANT and intent in ["sales_pitch", "project_fact", "project_details", "comparison", "project_selection", "sales_faq", "more_info_request"]:
            logger.info(f"Routing intent '{intent}' to Flow Engine (LEGACY)")
            
            # Use Flow Engine to process the request
            # This handles: Requirement Extraction -> Node Logic -> Pixeltable Query -> Negotiation
            flow_response = flow_engine.process(
                session_id=request.session_id or "default_session",
                user_input=request.query
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Track conversation for continuous loop
            if request.session_id:
                session_manager.add_message(request.session_id, "user", request.query)
                session_manager.add_message(request.session_id, "assistant", flow_response.system_action[:500])
                
                # Update session state with intent and topic
                session = session_manager.get_or_create_session(request.session_id)
                session.last_intent = f"flow_{flow_response.current_node}"
                if extraction.get("topic"):
                    session.last_topic = extraction["topic"]
                if extraction.get("project_name"):
                    session_manager.record_interest(request.session_id, extraction["project_name"])
                
                # CRITICAL: Update last_shown_projects from flow state
                flow_state = flow_engine.get_or_create_session(request.session_id)
                if flow_state.last_shown_projects:
                    session.last_shown_projects = flow_state.last_shown_projects
                    logger.info(f"Updated session with {len(flow_state.last_shown_projects)} shown projects")
                
                session_manager.save_session(session)
            
            # Log the interaction
            if request.user_id:
                await pixeltable_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent=f"flow_{flow_response.current_node}",
                    answered=True,
                    confidence_score="High", # Flow logic is deterministic
                    response_time_ms=response_time_ms,
                    project_id=request.project_id
                )
            
            # Map FlowResponse to ChatQueryResponse
            return ChatQueryResponse(
                answer=flow_response.system_action,
                sources=[],
                confidence="High",
                intent=f"flow_{flow_response.current_node}",
                refusal_reason=None,
                response_time_ms=response_time_ms,
                # Create suggested actions based on the response text to help the user?
                suggested_actions=[] 
            )

        # Step 3: For unsupported/unclear intents, use GPT with context if available
        if intent == "unsupported":
            # If we have session context, use contextual fallback
            if session and context_summary_dict.get("has_context"):
                logger.info("Unsupported intent with context - routing to contextual GPT fallback")
                from services.gpt_content_generator import generate_contextual_response_with_full_history
                
                response_text = generate_contextual_response_with_full_history(
                    query=original_query,
                    conversation_history=conversation_history,
                    session_context=context_summary_dict,
                    goal="Help the user with their query using conversation context"
                )
                
                # Update session
                session_manager.add_message(request.session_id, "user", original_query)
                session_manager.add_message(request.session_id, "assistant", response_text[:500])
                session.last_intent = "contextual_fallback"
                session_manager.save_session(session)
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="Medium",
                    intent="gpt_contextual",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=["Search properties", "Schedule meeting", "Get more info"]
                )
            
            # No context - try general GPT response
            logger.info("Unsupported intent - routing to GPT for helpful response")
            
            try:
                
                # Let GPT try to provide a helpful response
                general_context = {
                    "name": "Pinclick Real Estate",
                    "location": "Bangalore",
                    "amenities": "Property search, site visits, investment advice, meeting scheduling"
                }
                
                response_text = generate_insights(
                    project_facts=general_context,
                    topic="general_selling_points",
                    query=request.query,
                    user_requirements=None
                )
                
                response_time_ms = int((time.time() - start_time) * 1000)
                
                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="Medium",
                    intent="gpt_general",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=[]
                )
            except Exception as e:
                logger.error(f"GPT general response failed: {e}")
                response_time_ms = int((time.time() - start_time) * 1000)
                
                return ChatQueryResponse(
                    answer="I'm here to help with property search, project details, and arranging site visits. How can I assist you today?",
                    sources=[],
                    confidence="Low",
                    intent=intent,
                    refusal_reason=None,
                    response_time_ms=response_time_ms
                )

        # DISABLED: Unsupported intent web search fallback
        # if intent == "unsupported":
        #     logger.info("Unsupported intent, trying web search fallback")
        #     web_result = web_search_service.search_and_answer(
        #         query=request.query,
        #         topic_hint="Brigade Group real estate Bangalore"
        #     )
            
        #     if web_result.get("answer") and web_result.get("is_external", False):
        #         response_time_ms = int((time.time() - start_time) * 1000)
                
        #         # Log as answered with external source
        #         if request.user_id:
        #             await pixeltable_client.log_query(
        #                 user_id=request.user_id,
        #                 query=request.query,
        #                 intent=intent,
        #                 answered=True,
        #                 confidence_score="Low (External)",
        #                 response_time_ms=response_time_ms,
        #                 project_id=request.project_id
        #             )
                
        #         return ChatQueryResponse(
        #             answer=web_result["answer"],
        #             sources=[SourceInfo(**s) for s in web_result.get("sources", [])],
        #             confidence=web_result.get("confidence", "Low"),
        #             intent=intent,
        #             refusal_reason=None,
        #             response_time_ms=response_time_ms
        #         )


        # Context Injection for Continuous Conversation
        # If user asks a follow-up question, use the last interested project from session
        if request.session_id and intent not in ["greeting", "property_search", "unsupported", "sales_faq", "sales_objection"]:
            session = session_manager.get_or_create_session(request.session_id)
            if session.interested_projects:
                last_project = session.interested_projects[-1]
                # If query doesn't mention a project, inject it
                # We check against a few keywords to avoid over-injecting
                if last_project.lower() not in request.query.lower():
                    logger.info(f"Context Injection: Appending '{last_project}' to query '{request.query}'")
                    request.query += f" regarding {last_project}"

        # Step 3: Handle Intent-Specific Logic
        chunks = [] # Initialize chunks to avoid UnboundLocalError
        
        # A. Property Search (Structured)
        if intent == "property_search" or (request.filters and len(request.filters) > 0):
            logger.info("Executing Structured Search for Property Query")
            
            # Extract filters if not already provided
            if not request.filters:
                filters = filter_extractor.extract_filters(request.query)
            else:
                filters = filter_extractor.extract_filters(request.query) 
                # Trust query extraction on backend
                pass 

            # CRITICAL: Inject detected project name if extracted filters missed it
            # 'project_name' is detected earlier in the function via keyword matching
            if project_name and not filters.project_name:
                logger.info(f"Injecting detected project name '{project_name}' into search filters")
                filters.project_name = project_name

            # Perform Hybrid Retrieval
            search_results = await hybrid_retrieval.search_with_filters(
                query=request.query,
                filters=filters
            )
            
            # Structured search doesn't use vector chunks
            chunks = []
            
            # Generate Answer based on projects
            full_projects = search_results["projects"]
            
            # Create a context summary for the LLM
            if full_projects:
                project_context = "\n".join([
                    f"- {p['project_name']} ({p.get('status')}): {p.get('location')}. Price: {p['price_range']['min_display']} - {p['price_range']['max_display']}. Config: {p.get('config_summary')}. {p.get('highlights')}"
                    for p in full_projects[:5] # Limit context
                ])
                system_prompt = f"You are a helpful sales assistant. The user is looking for properties. Here are the matches:\n{project_context}\n\nSummarize these options briefly and ask if they'd like to schedule a visit."
                
                # We can use answer_generator to generate the text, but providing specific context
                # For now, let's use a simple generation or re-use generate_answer with boosted context
                # To keep it simple and robust:
                result = answer_generator.generate_answer(
                    query=request.query,
                    chunks=[], # We rely on project data, not chunks
                    intent=intent,
                    confidence="High"
                )
                # Override answer with a more specific one if needed, or rely on answer_generator to be smart if we passed context.
                # Actually answer_generator uses chunks. We should probably pass project info as chunks or distinct context.
                # Let's keep it simple: Let the frontend render the cards. The answer should be "Here are some projects that match your criteria:"
                result["answer"] = f"I found {len(full_projects)} projects matching your criteria. Here are the details:"
                result["confidence"] = "High"
                
                # Format projects for response (already formatted by hybrid_retrieval? No, search_with_filters returns formatted list relative to schema? 
                # verified: search_with_filters returns dict with "projects": [formatted_dict...]
                # So we can pass it directly.
            else:
                # Try intelligent fallback suggestions
                logger.info("No exact matches found, trying intelligent fallback...")
                fallback_results = await intelligent_fallback.find_intelligent_alternatives(
                    filters=filters,
                    original_query=request.query,
                    max_results=3
                )
                
                if fallback_results["alternatives"]:
                    logger.info(f"Found {len(fallback_results['alternatives'])} fallback alternatives")
                    result = {
                        "answer": fallback_results["answer"],
                        "confidence": "Medium",
                        "sources": fallback_results["sources"]
                    }
                    full_projects = fallback_results["projects"]
                else:
                    # Truly no alternatives available
                    logger.info("No alternatives found either")
                    result = {
                        "answer": "I couldn't find any projects matching those specific criteria. You might want to try broadening your search (e.g., different location or budget).",
                        "confidence": "High",
                        "sources": []
                    }
                    full_projects = []

        # B. Comparison
        elif intent == "comparison":
            # Multi-project comparison
            result = answer_generator.generate_comparison_answer(
                query=request.query,
                chunks=chunks
            )
            full_projects = [] # Could perhaps extract involved projects?
            
        # C. General / Other
        else:
            # Standard answer
            result = answer_generator.generate_answer(
                query=request.query,
                chunks=chunks,
                intent=intent,
                confidence="Medium" # Default confidence for generic
            )
            full_projects = []

        # Step 7: Validate answer (anti-hallucination check)
        # Step 7: Validate answer (anti-hallucination check)
        # Skip validation for property_search as it relies on structured data, not chunks
        if intent != "property_search" and refusal_handler.detect_hallucination_risk(result["answer"], chunks):
            logger.warning("Hallucination risk detected - refusing")
            refusal_response = refusal_handler.get_refusal_response(
                refusal_reason="insufficient_confidence"
            )

            # Log query
            if request.user_id:
                await pixeltable_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent=intent,
                    answered=False,
                    refusal_reason="hallucination_risk",
                    response_time_ms=int((time.time() - start_time) * 1000),
                    project_id=request.project_id
                )

            return ChatQueryResponse(
                **refusal_response,
                response_time_ms=int((time.time() - start_time) * 1000)
            )

        # Step 8: Log successful query
        response_time_ms = int((time.time() - start_time) * 1000)

        if request.user_id:
            confidence_score = result.get("confidence", "Medium")
            await pixeltable_client.log_query(
                user_id=request.user_id,
                query=request.query,
                intent=intent,
                answered=True,
                confidence_score=confidence_score,
                response_time_ms=response_time_ms,
                project_id=request.project_id
            )

        logger.info(f"Query processed successfully in {response_time_ms}ms")

        if full_projects:
             logger.info(f"DEBUG: Returning {len(full_projects)} projects in response.")
        else:
             logger.info("DEBUG: full_projects is empty or None")

        return ChatQueryResponse(
            answer=result["answer"],
            sources=[SourceInfo(**source) for source in result["sources"]],
            confidence=result["confidence"],
            intent=intent,
            refusal_reason=None,
            response_time_ms=response_time_ms,
            projects=full_projects
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/api/projects", response_model=List[ProjectInfo])
async def get_projects(user_id: str):
    """
    Get list of projects accessible by user.

    Args:
        user_id: User ID from authentication

    Returns:
        List of projects the user can query
    """
    try:
        projects = await pixeltable_client.get_user_projects(user_id)

        return [
            ProjectInfo(
                id=p["id"],
                name=p["name"],
                location=p["location"],
                status=p["status"],
                rera_number=p.get("rera_number")
            )
            for p in projects
        ]

    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching projects: {str(e)}")


@app.get("/api/projects/{project_id}", response_model=ProjectInfo)
async def get_project(project_id: str):
    """
    Get details of a specific project.

    Args:
        project_id: Project UUID

    Returns:
        Project information
    """
    try:
        project = await pixeltable_client.get_project_by_id(project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return ProjectInfo(
            id=project["id"],
            name=project["name"],
            location=project["location"],
            status=project["status"],
            rera_number=project.get("rera_number")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching project: {str(e)}")


# === Phase 2 Endpoints ===

@app.get("/api/personas")
async def get_personas():
    """Get list of available buyer personas."""
    try:
        return persona_pitch_generator.get_available_personas()
    except Exception as e:
        logger.error(f"Error fetching personas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/filters/options")
async def get_filter_options_endpoint():
    """
    Get all available filter options for frontend dropdowns.
    
    Returns:
        - configurations: List of BHK options (1-6)
        - locations: Grouped by area (North/East Bangalore)
        - budget_ranges: Price ranges in INR
        - possession_years: Available possession years (2024-2030 + Ready)
    """
    try:
        return get_filter_options()
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/sales")
async def sales_chat_query(request: ChatQueryRequest):
    """
    Intelligent sales-focused chat endpoint powered by GPT-4.
    
    Provides:
    - Highly intelligent, context-aware responses
    - Natural language understanding for sales queries
    - Intelligent objection handling
    - Dynamic response generation
    - Falls back to RAG for property-specific queries
    """
    start_time = time.time()
    
    try:
        logger.info(f"Intelligent sales chat query: {request.query[:100]}...")
        
        # Use the intelligent GPT-4 powered handler
        response_text, sales_intent, should_fallback = await intelligent_sales.handle_query(
            query=request.query
        )
        
        if not should_fallback and response_text:
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if request.user_id:
                await pixeltable_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent=f"intelligent_sales_{sales_intent.value}",
                    answered=True,
                    confidence_score="High",
                    response_time_ms=response_time_ms,
                    project_id=request.project_id
                )
            
            logger.info(f"Intelligent sales response generated in {response_time_ms}ms")
            
            return ChatQueryResponse(
                answer=response_text,
                sources=[],
                confidence="High",
                intent=f"intelligent_sales_{sales_intent.value}",
                refusal_reason=None,
                response_time_ms=response_time_ms
            )
        
        # Fall back to regular chat endpoint for property queries
        logger.info("Falling back to regular chat processing for property/unknown query")
        return await chat_query(request)
        
    except Exception as e:
        logger.error(f"Error in intelligent sales chat: {e}", exc_info=True)
        # Fallback to regular handler on error
        try:
            return await chat_query(request)
        except:
            raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/compare")
async def compare_projects(
    query: str,
    project_ids: Optional[List[str]] = None,
    user_id: Optional[str] = None
):
    """
    Compare multiple projects based on a query.

    Args:
        query: Comparison question
        project_ids: Optional list of project IDs to compare
        user_id: User ID for logging

    Returns:
        Comparison answer with sources from multiple projects
    """
    start_time = time.time()

    try:
        # Retrieve chunks from all or specified projects
        if project_ids and len(project_ids) > 1:
            grouped_chunks = await multi_project_retrieval.retrieve_for_comparison(
                query=query,
                project_ids=project_ids
            )
            # Flatten for answer generation
            chunks = [chunk for chunks_list in grouped_chunks.values() for chunk in chunks_list]
        else:
            # Retrieve from all projects
            chunks = await retrieval_service.retrieve_similar_chunks(query=query)

        # Generate comparison answer
        result = answer_generator.generate_comparison_answer(
            query=query,
            chunks=chunks
        )

        response_time_ms = int((time.time() - start_time) * 1000)

        if user_id:
            await pixeltable_client.log_query(
                user_id=user_id,
                query=query,
                intent="comparison",
                answered=True,
                confidence_score=result["confidence"],
                response_time_ms=response_time_ms
            )

        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "confidence": result["confidence"],
            "response_time_ms": response_time_ms
        }

    except Exception as e:
        logger.error(f"Error in comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/filtered-search")
async def filtered_search(request: ChatQueryRequest):
    """
    Natural language property search across all projects with structured filtering.

    Handles queries like:
    - "2bhk under 3cr in Bangalore"
    - "3bhk ready to move whitefield under 5cr"
    - "affordable 2bhk possession 2027"
    - "show me brigade 3bhk options"

    This endpoint:
    1. Extracts structured filters from natural language
    2. Performs SQL filtering to narrow down projects
    3. Executes vector search within filtered subset
    4. Groups results by project with expandable units
    5. Falls back to web search if no matches found

    Args:
        request: Chat query request with natural language query

    Returns:
        Multiple matching projects with unit details
    """
    start_time = time.time()

    try:
        logger.info(f"Filtered search query: {request.query}")

        # Step 1: Extract filters from query
        filters = filter_extractor.extract_filters(request.query)
        logger.info(f"Extracted filters: {filters.model_dump(exclude_none=True)}")
        


        # Step 2: Hybrid retrieval (SQL + vector search)
        search_results = await hybrid_retrieval.search_with_filters(
            query=request.query,
            filters=filters
        )

        # Step 3: Check if any results found
        if not search_results["projects"]:
            logger.info("No matching projects found in database. Trying intelligent fallback...")
            
            # Try intelligent fallback suggestions
            fallback_results = await intelligent_fallback.find_intelligent_alternatives(
                filters=filters,
                original_query=request.query,
                max_results=3
            )
            
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if fallback_results["alternatives"]:
                logger.info(f"Found {len(fallback_results['alternatives'])} fallback alternatives")
                
                # Format fallback projects for this endpoint's response format
                formatted_fallbacks = []
                for project in fallback_results["projects"]:
                    formatted_fallbacks.append({
                        "project_id": project.get("project_id"),
                        "project_name": project.get("project_name"),
                        "developer_name": project.get("developer_name"),
                        "location": project.get("location"),
                        "full_address": project.get("location"),
                        "rera_number": project.get("rera_number"),
                        "status": project.get("status"),
                        "matching_unit_count": 1,
                        "price_range": {
                            "min_inr": project.get("budget_min", 0) * 100000,  # Convert lakhs to INR
                            "max_inr": project.get("budget_max", 0) * 100000,
                            "min_display": f"₹{project.get('budget_min', 0)/100:.2f} Cr",
                            "max_display": f"₹{project.get('budget_max', 0)/100:.2f} Cr"
                        },
                        "configurations": [project.get("configuration", "N/A")],
                        "highlights": f"Located {project.get('_distance', 'N/A')} km away. {project.get('description', '')}",
                        "amenities": project.get("amenities", ""),
                        "can_expand": True,
                        "_is_fallback": True,  # Mark as fallback suggestion
                        "_distance": project.get("_distance")
                    })
                
                # Log query
                if request.user_id:
                    await pixeltable_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent="structured_search_with_fallback",
                        answered=True,
                        confidence_score="Medium (Fallback)",
                        response_time_ms=response_time_ms
                    )
                
                return {
                    "query": request.query,
                    "filters": filters.model_dump(exclude_none=True),
                    "matching_projects": len(formatted_fallbacks),
                    "projects": formatted_fallbacks,
                    "fallback_message": fallback_results["answer"],
                    "is_fallback": True,
                    "search_method": "intelligent_fallback",
                    "response_time_ms": response_time_ms
                }
            
            # No alternatives either
            logger.info("No alternatives found either")
            
            # Log query
            if request.user_id:
                await pixeltable_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent="structured_search",
                    answered=True, 
                    confidence_score="Low (No Match)",
                    response_time_ms=response_time_ms
                )

            return {
                "query": request.query,
                "filters": filters.model_dump(exclude_none=True),
                "matching_projects": 0,
                "projects": [],
                "web_fallback": None,
                "search_method": "pixeltable", 
                "response_time_ms": response_time_ms
            }

        # Step 4: Format projects for response
        formatted_projects = []
        for project in search_results["projects"]:
            formatted_projects.append({
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "developer_name": project.get("developer_name"),
                "location": f"{project.get('locality', '')}, {project.get('city', '')}".strip(", "),
                "full_address": project.get("location"),
                "rera_number": project.get("rera_number"),
                "status": project.get("status"),
                "matching_unit_count": project["unit_count"],
                "price_range": {
                    "min_inr": project["price_range"]["min"],
                    "max_inr": project["price_range"]["max"],
                    "min_display": project["price_range"]["min_display"],
                    "max_display": project["price_range"]["max_display"]
                },
                "sample_units": project["matching_units"][:3],  # Show first 3
                "all_units": project["matching_units"] if project["unit_count"] <= 10 else None,
                "can_expand": project.get("can_expand", False),
                "relevant_info": [
                    {
                        "content": chunk.get("content", "")[:200] + "...",
                        "section": chunk.get("section", ""),
                        "similarity": chunk.get("similarity", 0)
                    }
                    for chunk in project.get("relevant_chunks", [])[:2]
                ]
            })

        response_time_ms = int((time.time() - start_time) * 1000)

        # Log query
        if request.user_id:
            await pixeltable_client.log_query(
                user_id=request.user_id,
                query=request.query,
                intent="structured_search",
                answered=True,
                confidence_score="High" if search_results["search_method"] == "hybrid" else "Medium",
                response_time_ms=response_time_ms
            )

        return {
            "query": request.query,
            "filters": search_results["filters_used"],
            "matching_projects": search_results["total_matching_projects"],
            "projects": formatted_projects,
            "search_method": search_results["search_method"],
            "response_time_ms": response_time_ms
        }

    except Exception as e:
        logger.error(f"Error in filtered search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# === Admin Endpoints (Phase 2) ===

class QueryAnalytics(BaseModel):
    """Query analytics response."""
    total_queries: int
    answered_queries: int
    refused_queries: int
    refusal_rate: float
    avg_response_time_ms: float
    top_intents: List[Dict[str, Any]]
    recent_refusals: List[Dict[str, Any]]


@app.get("/api/admin/analytics", response_model=QueryAnalytics)
async def get_analytics(user_id: str, days: int = 7):
    """
    Get query analytics for the past N days.

    Args:
        user_id: Admin user ID
        days: Number of days to analyze

    Returns:
        Analytics data
    """
    try:
        # Verify admin role (simplified for now)
        # In production, check user_profiles.role == 'admin'

        # Use Pixeltable analytics
        analytics = pixeltable_client.get_analytics(days)
        
        # Format top intents
        top_intents = [
            {"intent": intent, "count": count}
            for intent, count in analytics.get('top_intents', {}).items()
        ][:5]

        return QueryAnalytics(
            total_queries=analytics.get('total_queries', 0),
            answered_queries=analytics.get('answered_queries', 0),
            refused_queries=analytics.get('refused_queries', 0),
            refusal_rate=round(analytics.get('refusal_rate', 0) * 100, 2),
            avg_response_time_ms=round(analytics.get('avg_response_time_ms', 0), 2),
            top_intents=top_intents,
            recent_refusals=analytics.get('recent_refusals', [])
        )

    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Development Helper Endpoints ===

if settings.environment == "development":
    @app.get("/api/dev/test-retrieval")
    async def test_retrieval(query: str, project_id: Optional[str] = None):
        """Test retrieval without answer generation."""
        try:
            chunks = await retrieval_service.retrieve_similar_chunks(
                query=query,
                project_id=project_id
            )

            return {
                "query": query,
                "chunks_retrieved": len(chunks),
                "chunks": [
                    {
                        "content": chunk["content"][:200] + "...",
                        "similarity": chunk["similarity"],
                        "section": chunk["section"],
                        "project": chunk["project_name"]
                    }
                    for chunk in chunks
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/dev/test-intent")
    async def test_intent(query: str):
        """Test intent classification using GPT-first classifier."""
        try:
            gpt_result = classify_intent_gpt_first(query)
            return {
                "query": query, 
                "intent": gpt_result.get("intent"),
                "data_source": gpt_result.get("data_source"),
                "confidence": gpt_result.get("confidence"),
                "reasoning": gpt_result.get("reasoning"),
                "extraction": gpt_result.get("extraction")
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))



# === Agent Flow Endpoint (STRICT MODE) ===
from services.flow_engine import execute_flow, FlowState, FlowResponse
from services.session_manager import session_manager

@app.post("/api/agent/flow", response_model=FlowResponse)
async def agent_flow_query(request: ChatQueryRequest):
    """
    Strict Flowchart-Driven Agent Logic.
    Does NOT use general RAG. Enforces the 10-node decision tree.
    """
    try:
        session_id = request.session_id or "default_agent_session"
        session = session_manager.get_or_create_session(session_id)
        
        # Load state
        current_state_data = session.flow_state
        if current_state_data:
            state = FlowState(**current_state_data)
        else:
            state = FlowState() # Start at Node 1
            
        # Execute Flow
        response = execute_flow(state, request.query)
        
        # Save state
        session.flow_state = state.model_dump()
        
        return response
        
    except Exception as e:
        logger.error(f"Agent flow error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level="info"
    )
