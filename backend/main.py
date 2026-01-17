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
import re
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


def _get_coaching_for_response(
    session,
    request_session_id: str,
    current_query: str,
    intent: str,
    search_performed: bool,
    data_source: str,
    budget_alternatives_shown: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Get coaching prompt for a response. Used by PATH 2 and early-return paths.
    """
    if not session or not request_session_id:
        return None
    try:
        from services.conversation_director import get_conversation_director
        director = get_conversation_director()
        session_dict = session.model_dump() if hasattr(session, 'model_dump') else session.dict()
        ctx = {
            "search_performed": search_performed,
            "budget_alternatives_shown": budget_alternatives_shown,
            "real_data_used": data_source == "database" or search_performed,
            "query_type": intent
        }
        # Enrich from last shown project when available
        proj = None
        if session_dict.get("last_shown_projects"):
            proj = session_dict["last_shown_projects"][0] if isinstance(session_dict["last_shown_projects"], list) else None
        # Provide template vars for rules that use them (avoid KeyError and ugly placeholders)
        ctx["template_vars"] = {
            "market_data_provided": "Share locality insights if available.",
            "urgency_context": "Limited units / price revision expected.",
            "location": (proj.get("location") or proj.get("full_address") or session_dict.get("current_filters", {}).get("location") or "this locality") if proj else (session_dict.get("current_filters", {}).get("location") or "this locality"),
            "connectivity_info": "metro and highway",
            "appreciation_rate": "8–12",
            "rera_number": (proj.get("rera_number") or "RERA registered") if proj else "RERA registered",
            "developer_name": (proj.get("developer") or proj.get("builder") or "The developer") if proj else "The developer",
            "savings_percentage": "15–20"
        }
        prompt = director.get_coaching_prompt(session=session_dict, current_query=current_query, context=ctx)
        if prompt and request_session_id:
            session_manager.track_coaching_prompt(request_session_id, prompt["type"])
        return prompt
    except Exception as e:
        logger.error(f"Coaching error: {e}")
        return None


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
    
    # Initialize Railway PostgreSQL database
    try:
        import os
        if os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL'):
            logger.info("🚀 Initializing Railway PostgreSQL database...")
            from database.init_db import init_database
            success = init_database()
            if success:
                logger.info("✅ Database initialization successful")
            else:
                logger.warning("⚠️ Database initialization encountered errors")
        else:
            logger.info("ℹ️ No DATABASE_URL configured - using in-memory storage")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        logger.warning("⚠️ Falling back to in-memory storage")
    
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
    coaching_prompt: Optional[Dict[str, Any]] = None  # Real-time sales coaching for salesman


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


# ========================================
# 🆕 SCHEDULING API ENDPOINTS
# Site Visit & Callback Scheduling
# ========================================

class SiteVisitScheduleRequest(BaseModel):
    """Request to schedule a site visit"""
    user_id: str
    session_id: Optional[str] = None
    project_id: str
    project_name: str
    contact_name: str
    contact_phone: str
    contact_email: Optional[str] = None
    requested_date: Optional[str] = None  # ISO format: YYYY-MM-DD
    requested_time_slot: Optional[str] = "morning"  # morning/afternoon/evening
    user_notes: Optional[str] = None


class CallbackScheduleRequest(BaseModel):
    """Request to schedule a callback"""
    user_id: str
    session_id: Optional[str] = None
    contact_name: str
    contact_phone: str
    contact_email: Optional[str] = None
    callback_reason: str = "general_inquiry"
    user_notes: Optional[str] = None
    urgency_level: str = "medium"  # low/medium/high/urgent
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None


@app.post("/api/schedule/site-visit")
async def schedule_site_visit(request: SiteVisitScheduleRequest):
    """
    Schedule a site visit
    
    User requests to visit a property in person
    """
    try:
        from services.scheduling_service import get_scheduling_service, SiteVisitRequest, TimeSlot
        from services.user_profile_manager import get_profile_manager
        from datetime import date
        
        scheduling_service = get_scheduling_service()
        profile_manager = get_profile_manager()
        
        # Parse requested date
        requested_date_obj = None
        if request.requested_date:
            try:
                requested_date_obj = date.fromisoformat(request.requested_date)
            except:
                logger.warning(f"Invalid date format: {request.requested_date}")
        
        # Parse time slot
        time_slot = None
        if request.requested_time_slot:
            time_slot = TimeSlot(request.requested_time_slot)
        
        # Get user's lead score
        lead_score = None
        try:
            profile = profile_manager.get_or_create_profile(request.user_id)
            lead_scores = profile_manager.calculate_lead_score(request.user_id)
            lead_score = lead_scores.get('total_score', 0)
        except:
            pass
        
        # Create site visit request
        visit_request = SiteVisitRequest(
            user_id=request.user_id,
            session_id=request.session_id,
            project_id=request.project_id,
            project_name=request.project_name,
            contact_name=request.contact_name,
            contact_phone=request.contact_phone,
            contact_email=request.contact_email,
            requested_date=requested_date_obj,
            requested_time_slot=time_slot,
            user_notes=request.user_notes,
            source="api_request",
            lead_score=lead_score
        )
        
        # Schedule visit
        result = scheduling_service.schedule_site_visit(visit_request)
        
        # Track in user profile
        profile_manager.track_site_visit_scheduled(request.user_id)
        
        logger.info(f"✅ SITE VISIT SCHEDULED via API: {request.project_name} for {request.user_id}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error scheduling site visit: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schedule/callback")
async def schedule_callback(request: CallbackScheduleRequest):
    """
    Request a callback from sales team
    
    User requests to be called back for discussion
    """
    try:
        from services.scheduling_service import get_scheduling_service, CallbackRequest, UrgencyLevel
        from services.user_profile_manager import get_profile_manager
        from datetime import date, time as time_obj
        
        scheduling_service = get_scheduling_service()
        profile_manager = get_profile_manager()
        
        # Parse dates/times
        preferred_date_obj = None
        if request.preferred_date:
            try:
                preferred_date_obj = date.fromisoformat(request.preferred_date)
            except:
                pass
        
        preferred_time_obj = None
        if request.preferred_time:
            try:
                preferred_time_obj = time_obj.fromisoformat(request.preferred_time)
            except:
                pass
        
        # Parse urgency
        urgency = UrgencyLevel(request.urgency_level)
        
        # Get lead score
        lead_score = None
        try:
            profile = profile_manager.get_or_create_profile(request.user_id)
            lead_scores = profile_manager.calculate_lead_score(request.user_id)
            lead_score = lead_scores.get('total_score', 0)
        except:
            pass
        
        # Create callback request
        callback_request = CallbackRequest(
            user_id=request.user_id,
            session_id=request.session_id,
            contact_name=request.contact_name,
            contact_phone=request.contact_phone,
            contact_email=request.contact_email,
            callback_reason=request.callback_reason,
            user_notes=request.user_notes,
            urgency_level=urgency,
            preferred_date=preferred_date_obj,
            preferred_time=preferred_time_obj,
            source="api_request",
            lead_score=lead_score
        )
        
        # Request callback
        result = scheduling_service.request_callback(callback_request)
        
        # Track in user profile
        profile_manager.track_callback_requested(request.user_id)
        
        logger.info(f"✅ CALLBACK REQUESTED via API: {request.callback_reason} for {request.user_id}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error requesting callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/schedule/user/{user_id}")
async def get_user_schedule(user_id: str):
    """
    Get all scheduled visits and callbacks for a user
    """
    try:
        from services.scheduling_service import get_scheduling_service
        
        scheduling_service = get_scheduling_service()
        
        visits = scheduling_service.get_user_visits(user_id)
        callbacks = scheduling_service.get_user_callbacks(user_id)
        
        return {
            "user_id": user_id,
            "site_visits": visits,
            "callbacks": callbacks,
            "total_scheduled": len(visits) + len(callbacks)
        }
    
    except Exception as e:
        logger.error(f"Error getting user schedule: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Admin endpoints for schedule management
@app.get("/api/admin/schedule/visits")
async def admin_get_all_visits(
    status: Optional[str] = None,
    date_from: Optional[str] = None,
    x_admin_key: str = Header(None)
):
    """
    Get all scheduled visits (admin only)
    
    Filters:
    - status: pending/confirmed/completed/cancelled
    - date_from: YYYY-MM-DD
    """
    import os
    expected_key = os.getenv("ADMIN_KEY", "secret")
    
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid Admin Key")
    
    try:
        from services.scheduling_service import get_scheduling_service
        
        scheduling_service = get_scheduling_service()
        
        # Get all visits
        all_visits = list(scheduling_service.scheduled_visits.values())
        
        # Apply filters
        if status:
            all_visits = [v for v in all_visits if v['status'] == status]
        
        if date_from:
            from datetime import date
            date_filter = date.fromisoformat(date_from)
            all_visits = [v for v in all_visits if v.get('requested_date') and v['requested_date'] >= date_filter]
        
        return {
            "total": len(all_visits),
            "visits": all_visits
        }
    
    except Exception as e:
        logger.error(f"Error getting visits: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/schedule/callbacks")
async def admin_get_all_callbacks(
    status: Optional[str] = None,
    urgency: Optional[str] = None,
    x_admin_key: str = Header(None)
):
    """
    Get all callback requests (admin only)
    
    Filters:
    - status: pending/contacted/completed
    - urgency: low/medium/high/urgent
    """
    import os
    expected_key = os.getenv("ADMIN_KEY", "secret")
    
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid Admin Key")
    
    try:
        from services.scheduling_service import get_scheduling_service
        
        scheduling_service = get_scheduling_service()
        
        # Get all callbacks
        all_callbacks = list(scheduling_service.callbacks.values())
        
        # Apply filters
        if status:
            all_callbacks = [c for c in all_callbacks if c['status'] == status]
        
        if urgency:
            all_callbacks = [c for c in all_callbacks if c['urgency_level'] == urgency]
        
        # Sort by urgency and created_at
        urgency_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        all_callbacks.sort(key=lambda c: (urgency_order.get(c['urgency_level'], 4), c['created_at']))
        
        return {
            "total": len(all_callbacks),
            "callbacks": all_callbacks
        }
    
    except Exception as e:
        logger.error(f"Error getting callbacks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/admin/schedule/visit/{visit_id}/status")
async def admin_update_visit_status(
    visit_id: str,
    status: str,
    notes: Optional[str] = None,
    x_admin_key: str = Header(None)
):
    """Update visit status (admin only)"""
    import os
    expected_key = os.getenv("ADMIN_KEY", "secret")
    
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid Admin Key")
    
    try:
        from services.scheduling_service import get_scheduling_service, SchedulingStatus
        
        scheduling_service = get_scheduling_service()
        
        success = scheduling_service.update_visit_status(
            visit_id,
            SchedulingStatus(status),
            notes
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Visit not found")
        
        return {"success": True, "visit_id": visit_id, "new_status": status}
    
    except Exception as e:
        logger.error(f"Error updating visit status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/admin/schedule/callback/{callback_id}/status")
async def admin_update_callback_status(
    callback_id: str,
    status: str,
    notes: Optional[str] = None,
    call_duration: Optional[int] = None,
    x_admin_key: str = Header(None)
):
    """Update callback status (admin only)"""
    import os
    expected_key = os.getenv("ADMIN_KEY", "secret")
    
    if not x_admin_key or x_admin_key != expected_key:
        raise HTTPException(status_code=403, detail="Invalid Admin Key")
    
    try:
        from services.scheduling_service import get_scheduling_service, SchedulingStatus
        
        scheduling_service = get_scheduling_service()
        
        success = scheduling_service.update_callback_status(
            callback_id,
            SchedulingStatus(status),
            notes,
            call_duration
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Callback not found")
        
        return {"success": True, "callback_id": callback_id, "new_status": status}
    
    except Exception as e:
        logger.error(f"Error updating callback status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        
        # 🆕 Step 0.55: Load or Create User Profile (Cross-Session Memory)
        user_profile = None
        welcome_back_message = None
        
        if request.user_id:
            try:
                from services.user_profile_manager import get_profile_manager
                
                profile_manager = get_profile_manager()
                user_profile = profile_manager.get_or_create_profile(request.user_id)
                
                # Increment session count
                profile_manager.increment_session_count(request.user_id, request.session_id or "default")
                
                # Get welcome back message for returning users
                if user_profile.total_sessions > 1:
                    welcome_back_message = profile_manager.get_welcome_back_message(request.user_id)
                    logger.info(f"👋 RETURNING USER: {request.user_id} (session #{user_profile.total_sessions})")
                else:
                    logger.info(f"🆕 NEW USER: {request.user_id}")
                
                # Calculate lead score
                lead_score = profile_manager.calculate_lead_score(request.user_id)
                logger.info(f"📊 LEAD SCORE: {lead_score['lead_temperature']} "
                           f"(engagement: {lead_score['engagement_score']}/10, "
                           f"intent: {lead_score['intent_to_buy_score']}/10)")
                
            except Exception as e:
                logger.error(f"Error loading user profile: {e}")
                # Continue without profile
        
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
                    
                    coaching_prompt = _get_coaching_for_response(
                        session, request.session_id, request.query, f"factual_{fact_query_detection['fact_type']}",
                        search_performed=False, data_source="database", budget_alternatives_shown=False
                    )
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
                        suggested_actions=["Schedule site visit", "View similar projects", "Get more details"],
                        coaching_prompt=coaching_prompt
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
            
            coaching_prompt = _get_coaching_for_response(
                session, request.session_id, request.query, "location_comparison_generic",
                search_performed=False, data_source="gpt_generation", budget_alternatives_shown=False
            )
            return ChatQueryResponse(
                answer=response_text,
                sources=[],
                confidence="High",
                intent="location_comparison_generic",
                refusal_reason=None,
                response_time_ms=response_time_ms,
                suggested_actions=["Explore properties in these areas", "Learn about other locations", "Get personalized recommendations"],
                coaching_prompt=coaching_prompt
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

                answer_text = "\n".join(response_parts)
                
                # Update session with messages
                if session and request.session_id:
                    session_manager.add_message(request.session_id, "user", original_query)
                    session_manager.add_message(request.session_id, "assistant", answer_text[:500])
                    session.last_intent = "project_details"
                    session_manager.save_session(session)
                
                coaching_prompt = _get_coaching_for_response(
                    session, request.session_id, request.query, "project_details",
                    search_performed=False, data_source="database", budget_alternatives_shown=False
                )
                return ChatQueryResponse(
                    answer=answer_text,
                    sources=[{
                        "document": "projects_table",
                        "excerpt": f"Details for {project.get('name')}",
                        "similarity": 1.0
                    }],
                    confidence="High",
                    intent="project_details",
                    refusal_reason=None,
                    response_time_ms=0, # Calculated later if needed or placeholder
                    suggested_actions=[],
                    coaching_prompt=coaching_prompt
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
        
        # ========================================
        # 🆕 CONTEXT PERSISTENCE - Always update session context
        # ========================================
        # CRITICAL: Always update session context when filters are used
        if filters and session:
            if not hasattr(session, 'current_filters') or not session.current_filters:
                session.current_filters = {}
            # Convert filters to dict if needed
            filters_dict = filters.model_dump(exclude_none=True) if hasattr(filters, 'model_dump') else (filters if isinstance(filters, dict) else {})
            session.current_filters.update(filters_dict)
            session_manager.save_session(session)
            logger.info(f"✅ Context preserved: Updated current_filters")
        
        # ========================================
        # 🆕 INTENT UNDERSTANDING & CONTEXT EXTRACTION
        # Understand what user is asking and where context is
        # ========================================
        
        def parse_location_string(location_str: str) -> Optional[str]:
            """Parse location string to extract main locality name."""
            if not location_str:
                return None
            # Split by comma and take first part
            location_parts = location_str.split(',')
            location_name = location_parts[0].strip()
            # Remove common suffixes
            location_name = location_name.replace(' Road', '').replace(' road', '')
            location_name = location_name.replace(' Phase 1', '').replace(' Phase 2', '')
            return location_name.strip()
        
        def extract_question_topic(query_lower: str) -> Optional[str]:
            """Extract topic from specific question."""
            if 'school' in query_lower:
                return "schools"
            elif 'amenit' in query_lower:
                return "amenities"
            elif 'distance' in query_lower or 'far' in query_lower or 'near' in query_lower:
                return "distance"
            elif 'airport' in query_lower:
                return "airport"
            elif 'metro' in query_lower:
                return "metro"
            return None
        
        def understand_query_intent(query: str, conversation_context: dict) -> dict:
            """
            Understand what user is asking for ANY query type.
            Returns intent information with context requirements.
            """
            query_lower = query.lower()
            
            # Nearby/More Options Intent
            if any(re.search(pattern, query_lower) for pattern in [
                r"(what|show|find|any|tell).*?(else|other|more).*?(nearby|around|close|near|available)",
                r"(available|option|property).*?(nearby|around|close|near)",
                r"similar.*?(location|area|place)"
            ]):
                return {
                    "intent_type": "nearby_properties",
                    "intent_subtype": None,
                    "needs_context": True,
                    "context_type": "location",
                    "confidence": 0.8,
                    "reasoning": "User wants nearby properties or more options"
                }
            
            # More Details Intent
            if any(re.search(pattern, query_lower) for pattern in [
                r"(tell|give|show).*?(more|details|information)",
                r"continue",
                r"expand"
            ]):
                return {
                    "intent_type": "more_details",
                    "intent_subtype": None,
                    "needs_context": True,
                    "context_type": "project",
                    "confidence": 0.8,
                    "reasoning": "User wants more details about last shown project/topic"
                }
            
            # Specific Question Intent
            if any(word in query_lower for word in ["school", "amenit", "distance", "far", "near", "airport", "metro"]):
                return {
                    "intent_type": "specific_question",
                    "intent_subtype": extract_question_topic(query_lower),
                    "needs_context": True,
                    "context_type": "project",
                    "confidence": 0.7,
                    "reasoning": f"User asking about specific aspect: {extract_question_topic(query_lower)}"
                }
            
            # Similar/Comparison Intent
            if any(re.search(pattern, query_lower) for pattern in [
                r"similar",
                r"alternative",
                r"compare",
                r"like.*?(this|that)"
            ]):
                return {
                    "intent_type": "similar_properties",
                    "intent_subtype": None,
                    "needs_context": True,
                    "context_type": "project",
                    "confidence": 0.7,
                    "reasoning": "User wants similar or alternative properties"
                }
            
            # General query (fallback)
            return {
                "intent_type": "general_query",
                "intent_subtype": None,
                "needs_context": False,
                "context_type": None,
                "confidence": 0.5,
                "reasoning": "General query, no specific intent detected"
            }
        
        def extract_query_context(session, conversation_history, request, intent_result: dict) -> dict:
            """
            Extract relevant context for ANY query type based on intent.
            CRITICAL: Always check persistent context first - it should NEVER be lost.
            """
            context = {
                "location": None,
                "project": None,
                "topic": None,
                "filters": None,
                "source": None,
                "confidence": 0.0,
                "context_persisted": False
            }
            
            # If intent needs location context
            if intent_result.get("context_type") == "location":
                # Priority 1: Last shown projects (PERSISTENT CONTEXT - should always be available)
                if session and hasattr(session, 'last_shown_projects') and session.last_shown_projects:
                    last_project = session.last_shown_projects[0]
                    if last_project and isinstance(last_project, dict):
                        project_location = last_project.get('location') or last_project.get('full_address')
                        if project_location:
                            context["location"] = parse_location_string(project_location)
                            context["project"] = last_project
                            context["source"] = "last_shown_projects"
                            context["confidence"] = 0.9
                            context["context_persisted"] = True
                            logger.info(f"✅ Using PERSISTENT context: location from last_shown_projects")
                
                # Priority 2: Current filters (PERSISTENT CONTEXT - should always be available)
                if not context["location"] and session and hasattr(session, 'current_filters'):
                    context["location"] = session.current_filters.get('location') or session.current_filters.get('locality')
                    if context["location"]:
                        context["filters"] = session.current_filters
                        context["source"] = "current_filters"
                        context["confidence"] = 0.7
                        context["context_persisted"] = True
                        logger.info(f"✅ Using PERSISTENT context: location from current_filters")
            
            # If intent needs project context
            elif intent_result.get("context_type") == "project":
                # Priority 1: Last shown projects (PERSISTENT CONTEXT - should always be available)
                if session and hasattr(session, 'last_shown_projects') and session.last_shown_projects:
                    context["project"] = session.last_shown_projects[0]
                    project_location = context["project"].get('location') or context["project"].get('full_address')
                    if project_location:
                        context["location"] = parse_location_string(project_location)
                    context["source"] = "last_shown_projects"
                    context["confidence"] = 0.9
                    context["context_persisted"] = True
                    logger.info(f"✅ Using PERSISTENT context: project from last_shown_projects")
            
            # If intent needs topic context
            elif intent_result.get("context_type") == "topic":
                if session and hasattr(session, 'last_topic'):
                    context["topic"] = session.last_topic
                    context["source"] = "session_last_topic"
                    context["confidence"] = 0.8
                    context["context_persisted"] = True
            
            return context
        
        # Understand intent for this query
        intent_result = understand_query_intent(request.query, {
            "last_shown_projects": session.last_shown_projects if session else None,
            "conversation_history": conversation_history,
            "last_topic": session.last_topic if session else None
        })
        
        logger.info(f"🧠 Intent understood: {intent_result['intent_type']} (confidence: {intent_result['confidence']}, reasoning: {intent_result['reasoning']})")
        
        # Handle intent-based queries with context extraction
        if intent_result["needs_context"]:
            # Extract context based on intent
            context_result = extract_query_context(session, conversation_history, request, intent_result)
            
            # Handle nearby properties intent
            if intent_result["intent_type"] == "nearby_properties":
                logger.info("🔍 Detected nearby properties intent")
                
                # Extract location - use context first, then explicit mention
                location_name = context_result.get("location")
                
                # Check for explicit location in query (takes priority)
                query_lower = request.query.lower()
                location_patterns = [
                    r"(nearby|around|near|close to)\s+([\w\s]+?)(?:\s|$)",
                    r"within 10km\s+of\s+([\w\s]+)",
                    r"within 10 km\s+of\s+([\w\s]+)"
                ]
                for pattern in location_patterns:
                    match = re.search(pattern, query_lower, re.IGNORECASE)
                    if match:
                        explicit_location = match.group(2 if len(match.groups()) > 1 else 1).strip()
                        if explicit_location:
                            location_name = parse_location_string(explicit_location)
                            logger.info(f"Extracted explicit location from query: {location_name}")
                            break
                
                # If location found, perform radius search
                if location_name:
                    try:
                        from services.hybrid_retrieval import hybrid_retrieval
                        from utils.geolocation_utils import get_coordinates
                    
                        # Verify location has coordinates
                        coords = get_coordinates(location_name)
                        if not coords:
                            logger.warning(f"Could not find coordinates for location: {location_name}")
                            # Try to find similar location
                            location_name_lower = location_name.lower()
                            for key in ['whitefield', 'sarjapur', 'marathahalli', 'bellandur', 'koramangala', 
                                       'hebbal', 'yelahanka', 'electronic city', 'bannerghatta']:
                                if key in location_name_lower or location_name_lower in key:
                                    location_name = key
                                    coords = get_coordinates(location_name)
                                    if coords:
                                        logger.info(f"Found similar location: {location_name}")
                                        break
                        
                        if coords:
                            logger.info(f"🔍 Searching for projects within 10km of {location_name}")
                            
                            # Get projects within 10km radius
                            nearby_projects = await hybrid_retrieval.get_projects_within_radius(
                                location_name=location_name,
                                radius_km=10.0
                            )
                            
                            # Exclude current/reference project if we have one
                            if session and hasattr(session, 'last_shown_projects') and session.last_shown_projects:
                                if isinstance(session.last_shown_projects, list) and len(session.last_shown_projects) > 0:
                                    ref_project = session.last_shown_projects[0]
                                    if isinstance(ref_project, dict):
                                        ref_name = ref_project.get('name')
                                        if ref_name:
                                            nearby_projects = [p for p in nearby_projects if p.get('name') != ref_name]
                                            logger.info(f"Excluded reference project: {ref_name}")
                            
                            # Apply additional filters if provided (budget, configuration)
                            if filters:
                                filtered_projects = []
                                for project in nearby_projects:
                                    # Budget filter
                                    if hasattr(filters, 'max_price_inr') and filters.max_price_inr:
                                        project_price = project.get('budget_min', 0) * 100000  # Convert lakhs to INR
                                        if project_price > filters.max_price_inr:
                                            continue
                                    
                                    # Configuration filter
                                    if hasattr(filters, 'configuration') and filters.configuration:
                                        config = project.get('configuration', '').lower()
                                        filter_config = filters.configuration.lower()
                                        if filter_config not in config:
                                            continue
                                    
                                    filtered_projects.append(project)
                                
                                nearby_projects = filtered_projects
                            
                            if nearby_projects:
                                logger.info(f"✅ Found {len(nearby_projects)} projects within 10km of {location_name}")
                                
                                # CRITICAL: Always update session context when projects are shown
                                if session:
                                    # ALWAYS update last_shown_projects (never lose this context)
                                    session.last_shown_projects = nearby_projects
                                    session.last_intent = "property_search"
                                    # Also update current_filters with location if not already set
                                    if not hasattr(session, 'current_filters') or not session.current_filters:
                                        session.current_filters = {}
                                    if location_name and 'location' not in session.current_filters:
                                        session.current_filters['location'] = location_name
                                    session_manager.save_session(session)
                                    logger.info(f"✅ Context preserved: Updated last_shown_projects with {len(nearby_projects)} nearby projects")
                                
                                response_time_ms = int((time.time() - start_time) * 1000)
                                
                                # Log interaction
                                if request.user_id:
                                    try:
                                        await pixeltable_client.log_query(
                                            user_id=request.user_id,
                                            query=request.query,
                                            intent="property_search",
                                            answered=True,
                                            confidence_score="High",
                                            response_time_ms=response_time_ms,
                                            project_id=request.project_id
                                        )
                                    except Exception as e:
                                        logger.error(f"Failed to log query: {e}")
                                
                                # Format response
                                distance_info = f" (closest: {nearby_projects[0].get('_distance', 'N/A')} km)"
                                answer_text = f"I found {len(nearby_projects)} properties within 10km of {location_name}{distance_info}. Here are the details:"
                                
                                # Update session with messages
                                if session and request.session_id:
                                    session_manager.add_message(request.session_id, "user", original_query)
                                    session_manager.add_message(request.session_id, "assistant", answer_text[:500])
                                    session.last_intent = "property_search"
                                    session_manager.save_session(session)
                                
                                coaching_prompt = _get_coaching_for_response(
                                    session, request.session_id, request.query, "property_search",
                                    search_performed=True, data_source="database", budget_alternatives_shown=False
                                )
                                return ChatQueryResponse(
                                    answer=answer_text,
                                    projects=nearby_projects,
                                    sources=[],
                                    confidence="High",
                                    intent="property_search",
                                    refusal_reason=None,
                                    response_time_ms=response_time_ms,
                                    suggested_actions=[],
                                    coaching_prompt=coaching_prompt
                                )
                            else:
                                logger.info(f"No projects found within 10km of {location_name}")
                                # Fall through to GPT consultant to handle gracefully
                        else:
                            logger.warning(f"Could not find coordinates for location: {location_name}")
                            # Fall through to GPT consultant
                    except Exception as e:
                        logger.error(f"Error in nearby search: {e}", exc_info=True)
                        # Fall through to GPT consultant
                else:
                    # No location found in context
                    logger.info("No location found in context for nearby search")
                    response_time_ms = int((time.time() - start_time) * 1000)
                    answer_text = "• I'd be happy to show you **nearby properties**.\n• Please specify the **location** (e.g. **Whitefield**, **Sarjapur**).\n• Try: *'what else is available near Whitefield'* or *'show me properties around Sarjapur'*."
                    
                    # Update session with messages
                    if session and request.session_id:
                        session_manager.add_message(request.session_id, "user", original_query)
                        session_manager.add_message(request.session_id, "assistant", answer_text[:500])
                        session.last_intent = "property_search"
                        session_manager.save_session(session)
                    
                    coaching_prompt = _get_coaching_for_response(
                        session, request.session_id, request.query, "property_search",
                        search_performed=False, data_source="gpt_generation", budget_alternatives_shown=False
                    )
                    return ChatQueryResponse(
                        answer=answer_text,
                        projects=[],
                        sources=[],
                        confidence="Medium",
                        intent="property_search",
                        refusal_reason=None,
                        response_time_ms=response_time_ms,
                        suggested_actions=[],
                        coaching_prompt=coaching_prompt
                    )
            
            # Handle other intent types (more_details, specific_question, similar_properties)
            # For now, let them fall through to GPT consultant with context
            elif intent_result["intent_type"] in ["more_details", "specific_question", "similar_properties"]:
                # Context is already extracted in context_result
                # These will be handled by GPT consultant with context injection
                logger.info(f"🧠 Intent '{intent_result['intent_type']}' will be handled by GPT consultant with context")
                if context_result.get("context_persisted"):
                    logger.info(f"✅ Context available for intent: {context_result.get('source')}")
        
        # CRITICAL: Always preserve context when generating responses
        # Even if query doesn't explicitly mention location/project, use context
        if session:
            if hasattr(session, 'last_shown_projects') and session.last_shown_projects:
                logger.info(f"✅ Context available: {len(session.last_shown_projects)} projects in context")
            if hasattr(session, 'current_filters') and session.current_filters:
                logger.info(f"✅ Context available: Filters = {session.current_filters}")
        
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
                try:
                    search_results = await hybrid_retrieval.search_with_filters(
                        query=request.query,
                        filters=filters
                    )
                except (NameError, AttributeError) as e:
                    # If hybrid_retrieval is not available, import it
                    logger.warning(f"hybrid_retrieval not available, re-importing: {e}")
                    from services.hybrid_retrieval import hybrid_retrieval
                    search_results = await hybrid_retrieval.search_with_filters(
                        query=request.query,
                        filters=filters
                    )

                # CRITICAL: Always update session context when projects are shown
                if session:
                    # ALWAYS update last_shown_projects (never lose this context)
                    session.last_shown_projects = search_results["projects"]
                    session.last_intent = "property_search"
                    # Also update current_filters if filters were used
                    if filters:
                        if not hasattr(session, 'current_filters') or not session.current_filters:
                            session.current_filters = {}
                        filters_dict = filters.model_dump(exclude_none=True) if hasattr(filters, 'model_dump') else (filters if isinstance(filters, dict) else {})
                        session.current_filters.update(filters_dict)
                    session_manager.save_session(session)
                    logger.info(f"✅ Context preserved: Updated last_shown_projects with {len(search_results['projects'])} projects")

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

                answer_text = f"I found {len(search_results['projects'])} projects matching your criteria. Here are the details:"
                
                # Update session with messages
                if session and request.session_id:
                    session_manager.add_message(request.session_id, "user", original_query)
                    session_manager.add_message(request.session_id, "assistant", answer_text[:500])
                    session.last_intent = "property_search"
                    session_manager.save_session(session)
                
                coaching_prompt = _get_coaching_for_response(
                    session, request.session_id, request.query, "property_search",
                    search_performed=True, data_source="database", budget_alternatives_shown=False
                )
                return ChatQueryResponse(
                    answer=answer_text,
                    projects=search_results["projects"],
                    sources=[],
                    confidence="High",
                    intent="property_search",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=[],
                    coaching_prompt=coaching_prompt
                )
            
            elif intent == "project_facts":
                logger.info("🔹 PATH 1: Database - Project Facts")
                # Extract project name from GPT classification
                project_name = context_metadata.get("extraction", {}).get("project_name")

                if not project_name:
                    # Try to extract from query directly
                    from services.project_fact_extractor import detect_project_fact_query
                    fact_detection = detect_project_fact_query(request.query)
                    if fact_detection:
                        project_name = fact_detection.get("project_name")

                if project_name:
                    logger.info(f"Fetching project details for: {project_name}")

                    # Fetch project from database
                    from database.pixeltable_setup import get_projects_table
                    projects_table = get_projects_table()

                    try:
                        # Query for project by name
                        results = list(projects_table.where(
                            projects_table.name.contains(project_name)
                        ).limit(1).collect())

                        if results:
                            project = results[0]

                            # Format structured project response
                            response_parts = []
                            response_parts.append(f"# {project.get('name', 'Unknown Project')}")

                            if project.get('developer'):
                                response_parts.append(f"**Developer**: {project['developer']}")

                            if project.get('location'):
                                response_parts.append(f"**Location**: {project['location']}")

                            if project.get('configuration'):
                                response_parts.append(f"**Configurations**: {project['configuration']}")

                            if project.get('price_range'):
                                price = project['price_range']
                                if isinstance(price, dict):
                                    response_parts.append(f"**Price Range**: ₹{price.get('min_display', 'N/A')} - ₹{price.get('max_display', 'N/A')}")
                                else:
                                    response_parts.append(f"**Price**: {price}")

                            if project.get('possession_year'):
                                response_parts.append(f"**Possession**: Q{project.get('possession_quarter', '')} {project['possession_year']}")

                            if project.get('amenities'):
                                response_parts.append(f"\n**Amenities**:\n{project['amenities']}")

                            if project.get('highlights'):
                                response_parts.append(f"\n**Highlights**:\n{project['highlights']}")

                            if project.get('usp'):
                                usp = project['usp']
                                if isinstance(usp, list):
                                    response_parts.append(f"\n**USP**:\n" + "\n".join(f"• {u}" for u in usp))
                                else:
                                    response_parts.append(f"\n**USP**: {usp}")

                            if project.get('rera_number'):
                                response_parts.append(f"\n**RERA**: {project['rera_number']}")

                            if project.get('brochure_url'):
                                response_parts.append(f"\n📄 [View Brochure]({project['brochure_url']})")

                            response_text = "\n\n".join(response_parts)
                            response_time_ms = int((time.time() - start_time) * 1000)

                            # Update session
                            if session:
                                session_manager.add_message(request.session_id, "user", original_query)
                                session_manager.add_message(request.session_id, "assistant", response_text[:500])
                                session.last_intent = "project_facts"
                                session_manager.record_interest(request.session_id, project.get('name'))
                                session_manager.save_session(session)

                            logger.info(f"✅ Returned database project details for: {project.get('name')}")

                            coaching_prompt = _get_coaching_for_response(
                                session, request.session_id, request.query, "project_facts",
                                search_performed=False, data_source="database", budget_alternatives_shown=False
                            )
                            return ChatQueryResponse(
                                answer=response_text,
                                sources=[],
                                confidence="High",
                                intent="project_facts",
                                refusal_reason=None,
                                response_time_ms=response_time_ms,
                                suggested_actions=["Schedule site visit", "View similar projects", "Get brochure"],
                                projects=[project],
                                coaching_prompt=coaching_prompt
                            )
                    except Exception as e:
                        logger.error(f"Error fetching project details: {e}")

                # If no project found, fall through to GPT
                logger.info("Project not found in database, falling back to GPT consultant")

        # PATH 2: GPT Sales Consultant (DEFAULT for everything else)
        # Handles: amenities, distances, advice, FAQs, objections, "more", greetings, all conversational queries
        logger.info(f"🔹 PATH 2: GPT Sales Consultant - intent={intent}")

        # ========================================
        # 🆕 SENTIMENT ANALYSIS
        # Analyze customer sentiment and adapt tone
        # ========================================
        sentiment_analysis = None
        
        if session and request.session_id:
            try:
                from services.sentiment_analyzer import get_sentiment_analyzer
                
                analyzer = get_sentiment_analyzer()
                
                # Quick sentiment analysis (fast, always runs)
                sentiment_analysis = analyzer.analyze_sentiment_quick(request.query)
                
                logger.info(f"😊 SENTIMENT: {sentiment_analysis['sentiment']} "
                           f"(frustration: {sentiment_analysis['frustration_level']}/10, "
                           f"engagement: {sentiment_analysis['engagement_level']:.1f}/10)")
                
                # Check if human escalation needed
                should_escalate, escalation_reason = analyzer.should_escalate_to_human(
                    sentiment=sentiment_analysis['sentiment'],
                    frustration_level=sentiment_analysis['frustration_level'],
                    conversation_length=len(session.messages)
                )
                
                if should_escalate:
                    logger.warning(f"🚨 ESCALATION RECOMMENDED: {escalation_reason}")
                    # Store escalation flag in session for follow-up
                    session.escalation_recommended = True
                    session.escalation_reason = escalation_reason
                
            except Exception as e:
                logger.error(f"Sentiment analysis error: {e}")
                # Continue without sentiment analysis

        # Generate conversational response using unified consultant with sentiment
        response_text = await generate_consultant_response(
            query=request.query,
            session=session,
            intent=intent,
            sentiment_analysis=sentiment_analysis
        )
        
        # 🆕 Add welcome back message for returning users (prepend to response)
        if welcome_back_message and user_profile and user_profile.total_sessions == 2:
            # Only show on second session to avoid repetition
            response_text = f"{welcome_back_message}\n\n{response_text}"
            logger.info(f"✅ Added welcome back message for user {request.user_id}")

        # ========================================
        # CONVERSATION COACHING INTEGRATION
        # Real-time sales coaching based on conversation patterns
        # ========================================
        coaching_prompt = None
        urgency_signals = []
        market_insights = None
        
        if session and request.session_id:
            try:
                from services.conversation_director import get_conversation_director
                from services.market_intelligence import get_market_intelligence
                from services.urgency_engine import get_urgency_engine
                
                director = get_conversation_director()
                market_intel = get_market_intelligence()
                urgency = get_urgency_engine()
                
                # Track objections if detected
                objection_type = director.track_objection(
                    session=session.model_dump() if hasattr(session, 'model_dump') else session.dict(),
                    query=request.query
                )
                if objection_type:
                    session_manager.record_objection(request.session_id, objection_type)
                    logger.info(f"💡 Objection detected: {objection_type}")
                
                # Get coaching prompt via helper (includes template_vars and track)
                coaching_prompt = _get_coaching_for_response(
                    session, request.session_id, request.query, intent,
                    search_performed=(data_source == "database"), data_source=data_source, budget_alternatives_shown=False
                )
                if coaching_prompt:
                    logger.info(f"💡 COACHING: {coaching_prompt['type']} - {coaching_prompt['message']}")
                    # If high-priority coaching with suggested script, enhance response
                    if coaching_prompt.get('priority') in ['high', 'critical'] and coaching_prompt.get('suggested_script'):
                        response_text += f"\n\n{coaching_prompt['suggested_script']}"
                        logger.info(f"✅ Enhanced response with coaching script")
                
                # Get market intelligence for shown projects
                if session.last_shown_projects:
                    for project in session.last_shown_projects[:3]:  # Top 3 projects
                        locality = project.get("location", "")
                        if locality:
                            # Get locality insights
                            locality_insights = market_intel.get_locality_insights(locality)
                            
                            # Get urgency signals
                            project_urgency = urgency.get_urgency_signals(
                                project=project,
                                locality_data=locality_insights
                            )
                            
                            if project_urgency:
                                urgency_signals.extend(project_urgency)
                                logger.info(f"⚡ Urgency signals for {project.get('name')}: {len(project_urgency)}")
                
                # If budget objection detected, proactively offer alternatives
                if objection_type == "budget" and session.current_filters:
                    try:
                        # hybrid_retrieval already imported at top of file
                        
                        # Get budget alternatives
                        alternatives = await hybrid_retrieval.get_budget_alternatives(
                            original_filters=session.current_filters,
                            budget_adjustment_percent=20.0,
                            max_results=2
                        )
                        
                        if alternatives["metadata"]["total_alternatives"] > 0:
                            # Add alternatives context to response
                            alt_text = "\n\n💰 **Budget-Friendly Alternatives:**\n"
                            
                            if alternatives["lower_budget"]:
                                alt_text += f"\n**More Affordable Options** (₹{alternatives['metadata']['lower_budget_max']/100:.1f} Cr):\n"
                                for proj in alternatives["lower_budget"][:2]:
                                    alt_text += f"• {proj['name']} in {proj['location']}\n"
                            
                            if alternatives["emerging_areas"]:
                                alt_text += f"\n**Emerging Areas** (Better Appreciation):\n"
                                for proj in alternatives["emerging_areas"][:2]:
                                    alt_text += f"• {proj['name']} in {proj['location']}\n"
                            
                            response_text += alt_text
                            logger.info(f"✅ Added {alternatives['metadata']['total_alternatives']} budget alternatives to response")
                    
                    except Exception as e:
                        logger.error(f"Error getting budget alternatives: {e}")
                
                # 🆕 Add human escalation if needed
                if sentiment_analysis and sentiment_analysis.get('sentiment') == 'frustrated':
                    frustration_level = sentiment_analysis.get('frustration_level', 0)
                    
                    if frustration_level >= 7:
                        # Add escalation offer to response
                        tone_adjustment = analyzer.get_tone_adjustment(
                            sentiment_analysis['sentiment'],
                            frustration_level
                        )
                        
                        if tone_adjustment.get('escalation_recommended'):
                            escalation_msg = tone_adjustment.get('escalation_message', 
                                "Would you like to speak with our senior consultant for personalized assistance?")
                            response_text += f"\n\n{escalation_msg}"
                            logger.warning(f"🚨 HUMAN ESCALATION OFFERED (frustration: {frustration_level}/10)")
                
                # 🆕 Track user profile interactions
                if user_profile and request.user_id:
                    try:
                        profile_manager = get_profile_manager()
                        
                        # Track properties viewed
                        if session and session.last_shown_projects:
                            for project in session.last_shown_projects[:5]:  # Track top 5
                                profile_manager.track_property_viewed(
                                    request.user_id,
                                    project.get("id", project.get("project_id", "")),
                                    project.get("name", ""),
                                    project
                                )
                        
                        # Track sentiment
                        if sentiment_analysis:
                            profile_manager.track_sentiment(
                                request.user_id,
                                sentiment_analysis['sentiment'],
                                sentiment_analysis.get('frustration_level', 0)
                            )
                        
                        # Track objections
                        if objection_type:
                            profile_manager.track_objection(request.user_id, objection_type)
                        
                        # Update preferences from current filters
                        if session and session.current_filters:
                            filters = session.current_filters
                            profile_manager.update_preferences(
                                request.user_id,
                                budget_min=filters.get('budget_min'),
                                budget_max=filters.get('budget_max'),
                                configurations=[filters.get('configuration')] if filters.get('configuration') else None,
                                locations=[filters.get('location')] if filters.get('location') else None
                            )
                        
                        logger.info(f"✅ Updated user profile for {request.user_id}")
                    
                    except Exception as e:
                        logger.error(f"Error updating user profile: {e}")
                
                # ========================================
                # 🆕 PROACTIVE NUDGING
                # Detect patterns and generate smart nudges
                # ========================================
                detected_nudge = None  # Store nudge for structured data return
                try:
                    from services.proactive_nudger import get_proactive_nudger
                    
                    nudger = get_proactive_nudger()
                    detected_nudge = nudger.detect_patterns_and_nudge(
                        user_profile=user_profile,
                        session=session,
                        current_query=request.query
                    )
                    
                    if detected_nudge:
                        # Add nudge to response
                        nudge_message = f"\n\n{detected_nudge['message']}"
                        response_text += nudge_message
                        
                        logger.info(f"🎯 PROACTIVE NUDGE SHOWN: {detected_nudge['type']} (priority: {detected_nudge['priority']})")
                
                except Exception as e:
                    logger.error(f"Error in proactive nudging: {e}")
                    # Don't fail the request if nudging fails
                
                # ========================================
                # 🆕 SCHEDULING INTENT DETECTION
                # Detect if user wants to schedule visit/callback
                # ========================================
                try:
                    # Check if user expressed interest in scheduling
                    scheduling_keywords = {
                        'visit': ['visit', 'see', 'tour', 'inspect', 'viewing'],
                        'callback': ['call', 'callback', 'call back', 'speak', 'talk', 'discuss', 'contact']
                    }
                    
                    query_lower = request.query.lower()
                    
                    # Check for scheduling intent
                    wants_visit = any(keyword in query_lower for keyword in scheduling_keywords['visit'])
                    wants_callback = any(keyword in query_lower for keyword in scheduling_keywords['callback'])
                    
                    # Check for confirmation words
                    is_confirmation = any(word in query_lower for word in ['yes', 'sure', 'ok', 'okay', 'great', 'perfect', 'definitely', 'absolutely'])
                    
                    # If user just confirmed and there's a recent nudge about scheduling
                    if is_confirmation and session and hasattr(session, 'nudges_shown'):
                        recent_nudges = session.nudges_shown[-3:] if session.nudges_shown else []
                        has_scheduling_nudge = any(
                            nudge.get('type') in ['repeat_views', 'abandoned_interest']
                            for nudge in recent_nudges
                        )
                        
                        if has_scheduling_nudge and (wants_visit or 'visit' in response_text.lower()):
                            # Add scheduling offer
                            scheduling_prompt = ("\n\n📅 **Let's schedule your visit!**\n\n"
                                               "Please provide:\n"
                                               "1. Your name\n"
                                               "2. Phone number\n"
                                               "3. Preferred date (e.g., tomorrow, this weekend, next Monday)\n"
                                               "4. Preferred time (morning/afternoon/evening)\n\n"
                                               "I'll connect you with our Relationship Manager right away!")
                            
                            response_text += scheduling_prompt
                            logger.info("📅 SCHEDULING PROMPT ADDED (visit confirmation detected)")
                    
                    # If explicit scheduling request
                    elif (wants_visit or wants_callback) and is_confirmation:
                        if wants_visit:
                            response_text += ("\n\n📅 **Great! Let's schedule your site visit.**\n\n"
                                            "Please share:\n"
                                            "• Your name\n"
                                            "• Phone number\n"
                                            "• Preferred date and time\n\n"
                                            "Our Relationship Manager will confirm within 1 hour!")
                        elif wants_callback:
                            response_text += ("\n\n📞 **I'll arrange a callback for you.**\n\n"
                                            "Please provide:\n"
                                            "• Your name\n"
                                            "• Phone number\n"
                                            "• Best time to call\n\n"
                                            "Our team will reach you within 1-2 hours!")
                        
                        logger.info(f"📅 SCHEDULING PROMPT ADDED ({'visit' if wants_visit else 'callback'})")
                
                except Exception as e:
                    logger.error(f"Error in scheduling detection: {e}")
                    # Don't fail the request
                
            except Exception as e:
                logger.error(f"Error in conversation coaching: {e}")
                # Don't fail the request if coaching fails

        # Update session
        if session and request.session_id:
            session_manager.add_message(request.session_id, "user", request.query)
            session_manager.add_message(request.session_id, "assistant", response_text[:500])
            session.last_intent = intent if intent != "unsupported" else "sales_conversation"
            
            # 🆕 Store sentiment in session for tracking
            if sentiment_analysis:
                session.last_sentiment = sentiment_analysis['sentiment']
                session.last_frustration_level = sentiment_analysis.get('frustration_level', 0)
            
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
            suggested_actions=[],
            coaching_prompt=coaching_prompt if 'coaching_prompt' in locals() else None
        )

        # Step 1.5: Handle greetings immediately without RAG (LEGACY - unreachable code)
        # This code is kept for reference but is unreachable due to the return statement above
        if False and not USE_UNIFIED_CONSULTANT and intent == "greeting":
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
                            
                            # Update session with messages
                            if session and request.session_id:
                                session_manager.add_message(request.session_id, "user", original_query)
                                session_manager.add_message(request.session_id, "assistant", response_text[:500])
                                session.last_intent = "more_info_request"
                                if extraction and extraction.get("topic"):
                                    session.last_topic = extraction["topic"]
                                session_manager.save_session(session)
                            
                            coaching_prompt = _get_coaching_for_response(
                                session, request.session_id, request.query, "more_info_request",
                                search_performed=False, data_source="gpt_generation", budget_alternatives_shown=False
                            )
                            return ChatQueryResponse(
                                answer=response_text,
                                sources=[],
                                confidence="High",
                                intent="gpt_more_info",
                                refusal_reason=None,
                                response_time_ms=response_time_ms,
                                suggested_actions=[],
                                coaching_prompt=coaching_prompt
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
                    answer="• I'm here to help with **property search**, **project details**, and **site visits**.\n• How can I assist you today?",
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
            try:
                search_results = await hybrid_retrieval.search_with_filters(
                    query=request.query,
                    filters=filters
                )
            except (NameError, AttributeError) as e:
                # If hybrid_retrieval is not available, import it
                logger.warning(f"hybrid_retrieval not available, re-importing: {e}")
                from services.hybrid_retrieval import hybrid_retrieval
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

        # ========================================
        # 🆕 PREPARE ENHANCED UX DATA FOR FRONTEND
        # Collect all structured data for Phase 2 components
        # ========================================
        enhanced_ux_data = {}
        
        # 1. Proactive Nudge (if generated)
        if detected_nudge:
            enhanced_ux_data["nudge"] = detected_nudge
            logger.info(f"📦 Returning nudge in structured data: {detected_nudge['type']}")
        
        # 2. Sentiment Data (if analyzed)
        try:
            if sentiment_analysis:
                sentiment_data = {
                    "sentiment": sentiment_analysis.get("sentiment", "neutral"),
                    "frustration_score": sentiment_analysis.get("frustration_level", 0),
                    "escalation_recommended": sentiment_analysis.get("frustration_level", 0) >= 7,
                    "escalation_reason": None,
                    "confidence": sentiment_analysis.get("confidence", 0.8),
                }
                
                # Get escalation reason if recommended
                if sentiment_data["escalation_recommended"]:
                    from services.sentiment_analyzer import get_sentiment_analyzer
                    analyzer = get_sentiment_analyzer()
                    tone_adjustment = analyzer.get_tone_adjustment(
                        sentiment_data["sentiment"],
                        sentiment_data["frustration_score"]
                    )
                    if tone_adjustment.get("escalation_recommended"):
                        sentiment_data["escalation_reason"] = tone_adjustment.get(
                            "escalation_message",
                            "High frustration level detected. Human assistance recommended."
                        )
                
                enhanced_ux_data["sentiment"] = sentiment_data
                logger.info(f"📦 Returning sentiment in structured data: {sentiment_data['sentiment']}")
        except Exception as e:
            logger.error(f"Error preparing sentiment data: {e}")
        
        # 3. Urgency Signals (if generated)
        try:
            if urgency_signals and len(urgency_signals) > 0:
                # Convert to frontend format
                formatted_signals = []
                for signal in urgency_signals[:2]:  # Top 2 signals
                    formatted_signals.append({
                        "type": signal.get("type", "low_inventory"),
                        "message": signal.get("message", ""),
                        "priority_score": signal.get("priority_score", 5),
                        "icon": signal.get("icon"),
                    })
                enhanced_ux_data["urgency_signals"] = formatted_signals
                logger.info(f"📦 Returning {len(formatted_signals)} urgency signals in structured data")
        except Exception as e:
            logger.error(f"Error preparing urgency signals data: {e}")
        
        # 4. User Profile Data (if available)
        try:
            if user_profile and request.user_id:
                profile_data = {
                    "is_returning_user": user_profile.viewed_projects_count > 0 if hasattr(user_profile, 'viewed_projects_count') else False,
                    "last_visit_date": user_profile.last_visit_date.isoformat() if hasattr(user_profile, 'last_visit_date') and user_profile.last_visit_date else None,
                    "viewed_projects_count": user_profile.viewed_projects_count if hasattr(user_profile, 'viewed_projects_count') else 0,
                    "interests": user_profile.interests if hasattr(user_profile, 'interests') else [],
                    "lead_score": user_profile.lead_score if hasattr(user_profile, 'lead_score') else None,
                }
                enhanced_ux_data["user_profile"] = profile_data
                logger.info(f"📦 Returning user profile in structured data: returning_user={profile_data['is_returning_user']}")
        except Exception as e:
            logger.error(f"Error preparing user profile data: {e}")

        return ChatQueryResponse(
            answer=result["answer"],
            sources=[SourceInfo(**source) for source in result["sources"]],
            confidence=result["confidence"],
            intent=intent,
            refusal_reason=None,
            response_time_ms=response_time_ms,
            projects=full_projects,
            data=enhanced_ux_data if enhanced_ux_data else None  # Include enhanced UX data
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
        try:
            search_results = await hybrid_retrieval.search_with_filters(
                query=request.query,
                filters=filters
            )
        except (NameError, AttributeError) as e:
            # If hybrid_retrieval is not available, import it
            logger.warning(f"hybrid_retrieval not available, re-importing: {e}")
            from services.hybrid_retrieval import hybrid_retrieval
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
