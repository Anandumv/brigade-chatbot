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
from services.project_enrichment import project_enrichment
from services.context_understanding import context_understanding

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
# from services.intent_classifier import intent_classifier  # DEPRECATED: Legacy keyword-based classifier - no longer used
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
    Trust GPT intent classification - no keyword matching.
    """
    # Convert Pydantic model to dict if needed
    if filters and hasattr(filters, 'model_dump'):
        filters = filters.model_dump()
    
    # Trust GPT intent classification
    if intent == "property_search":
        return True

    # Has filters from UI or extraction (GPT extracted these)
    if filters and isinstance(filters, dict) and any(filters.values()):
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


async def _generate_no_alternatives_message(
    original_query: str,
    filters: Any
) -> str:
    """
    Generate a helpful, sales-friendly message when no alternatives are found.
    Uses GPT to suggest budget/location/configuration adjustments.
    """
    try:
        from openai import OpenAI
        from config import settings
        
        client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        
        # Extract filter details for context
        filter_details = []
        if hasattr(filters, 'max_price_inr') and filters.max_price_inr:
            budget_lakhs = filters.max_price_inr / 100000
            filter_details.append(f"Budget: Up to ₹{budget_lakhs:.1f} Lakhs")
        if hasattr(filters, 'locality') and filters.locality:
            filter_details.append(f"Location: {filters.locality}")
        if hasattr(filters, 'bedrooms') and filters.bedrooms:
            filter_details.append(f"Configuration: {', '.join(map(str, filters.bedrooms))}BHK")
        
        context = f"Customer searched for: {original_query}"
        if filter_details:
            context += f"\nFilters: {', '.join(filter_details)}"
        
        prompt = f"""You are a professional real estate sales consultant. A customer searched for properties but we couldn't find any matches, even after expanding the search radius and budget range.

{context}

Generate a helpful, sales-friendly response that:
1. Acknowledges their search criteria positively
2. Suggests 2-3 specific adjustments (budget range, location, configuration)
3. Offers to help them explore alternatives
4. Maintains enthusiasm and doesn't feel like a dead end

Format as bullet points (•) with **bold** main points. Be concise and actionable.

Example structure:
• I understand you're looking for [criteria]
• Here are some suggestions to find great options:
  - **Expand budget** to [suggested range] for more choices
  - **Consider nearby areas** like [suggestions] with similar connectivity
  - **Explore different configurations** that might offer better value
• I'm here to help you find the perfect property. What would you like to adjust?"""

        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are Pinclick Genie, an expert real estate sales consultant. Your goal is to help customers find properties by suggesting helpful adjustments when exact matches aren't available."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error generating no-alternatives message: {e}")
        # Fallback to template message
        suggestions = []
        if hasattr(filters, 'max_price_inr') and filters.max_price_inr:
            budget_lakhs = filters.max_price_inr / 100000
            suggestions.append(f"• **Expand your budget** to ₹{budget_lakhs * 1.3:.1f} Lakhs for more options")
        if hasattr(filters, 'locality') and filters.locality:
            suggestions.append(f"• **Try nearby areas** with similar connectivity to {filters.locality}")
        suggestions.append("• **Explore different configurations** that might offer better value")
        suggestions.append("• I'm here to help you find the perfect property. What would you like to adjust?")
        
        return "\n".join(suggestions) if suggestions else "I couldn't find exact matches. Would you like to adjust your search criteria?"


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

    # Initialize Redis Context Manager
    try:
        from services.redis_context import init_redis_context_manager
        redis_manager = init_redis_context_manager(
            redis_url=settings.redis_url,
            ttl_seconds=settings.redis_ttl_seconds
        )
        logger.info("✅ Redis context manager initialized")
        health = redis_manager.health_check()
        logger.info(f"Redis status: {health['status']}")
    except Exception as e:
        logger.error(f"Redis initialization failed: {e}")
        logger.warning("⚠️ Context will use in-memory fallback")

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

# Register /assist router (spec-compliant copilot endpoint)
from routes.assist import router as assist_router
app.include_router(assist_router, prefix="/api/assist", tags=["copilot"])


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
        
        # Create fresh table with schema (matches pixeltable_setup.py schema)
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
            'latitude': pxt.Float,           # Geolocation for distance filtering
            'longitude': pxt.Float,          # Geolocation for distance filtering
        }
        
        projects = pxt.create_table('brigade.projects', schema)
        logger.info("Created fresh projects table")
        
        # Load from JSON
        seed_file = os.path.join(os.path.dirname(__file__), 'data', 'seed_projects.json')
        if os.path.exists(seed_file):
            with open(seed_file, 'r') as f:
                seed_data = json.load(f)
            projects.insert(seed_data)

            # CRITICAL: Clear hybrid_retrieval cache after refresh
            # This ensures fresh queries will fetch the new data
            try:
                from services.hybrid_retrieval import _all_projects_cache
                _all_projects_cache["data"] = None
                _all_projects_cache["timestamp"] = 0
                logger.info("✅ Cache cleared after admin refresh")
            except Exception as cache_err:
                logger.warning(f"Could not clear cache: {cache_err}")

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
        
        # CRITICAL: Get list of all projects from database for GPT to match against
        available_projects = []
        try:
            from database.pixeltable_setup import get_projects_table
            projects_table = get_projects_table()
            if projects_table:
                all_projects = projects_table.select(
                    projects_table.name,
                    projects_table.location
                ).collect()
                available_projects = [
                    {"name": p.get("name"), "location": p.get("location")}
                    for p in all_projects
                ]
                logger.info(f"✅ Loaded {len(available_projects)} projects for GPT matching")
        except Exception as e:
            logger.warning(f"Could not load projects for GPT: {e}")
        
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
                "conversation_phase": session.conversation_phase,
                # CRITICAL: Add last_shown_projects and interested_projects for context
                "last_shown_projects": session.last_shown_projects if hasattr(session, 'last_shown_projects') and session.last_shown_projects else [],
                "interested_projects": session.interested_projects,
                # CRITICAL: Add available projects list for GPT to match against
                "available_projects": available_projects
            }
        
        # Build comprehensive context for understanding ALL queries
        comprehensive_context = context_understanding.build_comprehensive_context(
            query=request.query,
            session=session,
            conversation_history=conversation_history
        )
        
        # Enrich query with context if needed (auto-complete incomplete queries)
        enriched_query = context_understanding.enrich_query_with_context(
            query=request.query,
            context=comprehensive_context
        )
        
        if enriched_query != request.query:
            logger.info(f"Query enriched: '{request.query}' → '{enriched_query}'")
            # Use enriched query for classification
            query_for_classification = enriched_query
        else:
            query_for_classification = request.query
        
        # GPT-first classification with data source selection and comprehensive context
        gpt_result = classify_intent_gpt_first(
            query=query_for_classification,
            conversation_history=conversation_history,
            session_state=session_state,
            context_summary=context_summary_dict.get("summary"),
            comprehensive_context=comprehensive_context
        )
        
        intent = gpt_result.get("intent", "unsupported")
        data_source = gpt_result.get("data_source", "database")
        gpt_confidence = gpt_result.get("confidence", 0.0)
        extraction = gpt_result.get("extraction", {})
        
        # Initialize project_name early to avoid UnboundLocalError in property_search handler
        project_name = extraction.get("project_name") if extraction else None
        
        # CRITICAL: If GPT extracted a project name, save it to session context
        if project_name and session and request.session_id:
            # Save to interested_projects
            if project_name not in session.interested_projects:
                session_manager.record_interest(request.session_id, project_name)
                logger.info(f"✅ Saved project '{project_name}' to interested_projects")
            
            # Also try to get full project details and save to last_shown_projects
            try:
                from database.pixeltable_setup import get_projects_table
                projects_table = get_projects_table()
                if projects_table:
                    results = list(projects_table.where(
                        projects_table.name.contains(project_name)
                    ).limit(1).collect())
                    if results:
                        project_dict = dict(results[0])
                        if not hasattr(session, 'last_shown_projects') or not session.last_shown_projects:
                            session.last_shown_projects = []
                        existing_names = {p.get('name') for p in session.last_shown_projects if isinstance(p, dict) and p.get('name')}
                        if project_dict.get('name') and project_dict.get('name') not in existing_names:
                            session.last_shown_projects.insert(0, project_dict)
                            session_manager.save_session(session)
                            logger.info(f"✅ Saved project '{project_name}' to last_shown_projects")
            except Exception as e:
                logger.warning(f"Could not save project to last_shown_projects: {e}")
        
        logger.info(f"GPT Classification: intent={intent}, data_source={data_source}, confidence={gpt_confidence}")

        # TRUST GPT: GPT is intelligent enough to understand queries from context
        # No keyword-based overrides needed - GPT handles all query understanding

        # SALES LOGIC: Apply intelligent routing based on intent and context
        # Handle special cases with sales logic
        if comprehensive_context:
            intent_hints = comprehensive_context.get("inferred_intent_hints", [])
            
            # If query asks for "minimum budget" or "starting price", ensure we calculate it
            # GPT will classify this correctly, no keyword check needed
            if "price_query" in intent_hints and intent == "property_search":
                # Will be handled in property_search handler - ensure we calculate min
                logger.info("💰 Minimum budget query detected - will calculate from results")
            
            # If query is a follow-up ("more", "what else"), ensure we continue from last search
            if "follow_up_query" in intent_hints:
                if intent == "property_search":
                    # Use last search filters/context
                    logger.info("🔄 Follow-up query detected - continuing from last search")
                elif intent == "nearby_properties":
                    # Use last location from context
                    logger.info("📍 Follow-up nearby query - using location from context")
        
        # Trust GPT always - no keyword fallback
        # If confidence is low, log warning but still use GPT result
        if gpt_confidence < 0.5:
            logger.warning(f"GPT confidence is low ({gpt_confidence}), but trusting GPT result. Intent: {intent}, Data source: {data_source}")
        
        # CRITICAL: Only use GPT fallback for unsupported intents
        # If GPT has classified with a specific intent (property_search, project_facts, etc.), 
        # trust it and use the proper handlers - DO NOT route to fallback
        use_gpt_fallback = False
        valid_intents = ["property_search", "project_facts", "nearby_properties", "sales_conversation", "greeting"]
        
        if intent not in valid_intents:
            # Intent is unsupported or unknown - check if we should use GPT fallback
            if session and should_use_gpt_fallback(original_query, session, gpt_confidence):
                use_gpt_fallback = True
                logger.info(f"Routing unsupported intent '{intent}' to GPT fallback (confidence={gpt_confidence})")
        else:
            # GPT has classified with a valid intent - ALWAYS use proper handlers, never fallback
            use_gpt_fallback = False
            logger.info(f"✅ GPT classified as '{intent}' (confidence={gpt_confidence}) - using proper handler, NOT fallback")
        
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

        # GPT will handle "show more" / "tell me more" queries through intent classification
        # No pattern matching needed - GPT understands context and intent

        # Step 1.5: FACTUAL QUERY INTERCEPTOR - Fetch real database facts AFTER GPT classification
        # GPT classification will extract project_name and fact_type - use that instead of keyword matching
        # This prevents GPT from making up information about project facts
        from services.project_fact_extractor import get_project_fact, format_fact_response
        
        # Check if GPT already classified this as project_facts with extraction
        # We'll handle this after GPT classification, not before
        fact_query_detection = None
        if False:  # Disabled - will use GPT extraction instead
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
        # GPT intent classifier handles location comparison detection - no keyword matching needed
        # Check if intent is sales_conversation with location comparison topic
        if intent == "sales_conversation" and (extraction.get("topic") in ["location_comparison", "location_benefits"] or "location" in extraction.get("topic", "").lower()):
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
        
        # Step 1.7: REMOVED - Keyword-based fuzzy project detection
        # GPT now handles ALL project detection as the primary method
        # Fuzzy matching is only used as a fallback AFTER GPT classification (see project_facts handler)
        # This ensures GPT is always the first method, with fuzzy matching as backup

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
        
        # Removed extract_question_topic and understand_query_intent functions
        # GPT intent classifier handles all query understanding - no pattern matching needed
        # All intent handling is done by GPT classification above - legacy code removed
        
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
                    logger.warning(f"hybrid_retrieval not available: {e}")
                    # Import module and use directly to avoid scoping issues
                    import services.hybrid_retrieval as hr_module
                    hr_instance = hr_module.hybrid_retrieval
                    try:
                        search_results = await hr_instance.search_with_filters(
                            query=request.query,
                            filters=filters
                        )
                    except Exception as e2:
                        logger.error(f"Failed to use hybrid_retrieval after re-import: {e2}")
                        # Return empty results to trigger fallback
                        search_results = {"projects": [], "sources": []}
                except Exception as e:
                    # For other exceptions, just log and return empty results
                    logger.error(f"hybrid_retrieval search failed: {e}")
                    search_results = {"projects": [], "sources": []}

                # Check if zero results - trigger intelligent fallback
                if len(search_results["projects"]) == 0:
                    logger.info("🔍 Zero results found, triggering intelligent fallback with aggressive mode...")
                    
                    # Try intelligent fallback with aggressive mode (expanded radius and budget)
                    fallback_results = await intelligent_fallback.find_intelligent_alternatives(
                        filters=filters,
                        original_query=request.query,
                        max_results=5,  # Show more alternatives
                        aggressive_mode=True  # Expand radius to 20km and budget to 2x
                    )
                    
                    if fallback_results.get("alternatives"):
                        # Found alternatives - use fallback results
                        logger.info(f"✅ Found {len(fallback_results['alternatives'])} fallback alternatives")
                        answer_text = fallback_results["answer"]
                        projects = fallback_results["projects"]
                        confidence = "Medium"
                        budget_alternatives_shown = True
                        
                        # Update session with fallback projects
                        if session:
                            session.last_shown_projects = projects
                            session.last_intent = "property_search"
                            if filters:
                                if not hasattr(session, 'current_filters') or not session.current_filters:
                                    session.current_filters = {}
                                filters_dict = filters.model_dump(exclude_none=True) if hasattr(filters, 'model_dump') else (filters if isinstance(filters, dict) else {})
                                session.current_filters.update(filters_dict)
                            session_manager.save_session(session)
                            logger.info(f"✅ Context preserved: Updated last_shown_projects with {len(projects)} fallback projects")
                    else:
                        # No alternatives found even with aggressive search - generate helpful message
                        logger.info("⚠️ No alternatives found even with aggressive search")
                        answer_text = await _generate_no_alternatives_message(request.query, filters)
                        projects = []
                        confidence = "Medium"
                        budget_alternatives_shown = False
                        
                        # Still update session context
                        if session:
                            session.last_intent = "property_search"
                            if filters:
                                if not hasattr(session, 'current_filters') or not session.current_filters:
                                    session.current_filters = {}
                                filters_dict = filters.model_dump(exclude_none=True) if hasattr(filters, 'model_dump') else (filters if isinstance(filters, dict) else {})
                                session.current_filters.update(filters_dict)
                            session_manager.save_session(session)
                    
                    response_time_ms = int((time.time() - start_time) * 1000)
                    
                    # Log the interaction
                    if request.user_id:
                        await pixeltable_client.log_query(
                            user_id=request.user_id,
                            query=request.query,
                            intent="property_search",
                            answered=True,
                            confidence_score=confidence,
                            response_time_ms=response_time_ms,
                            project_id=request.project_id
                        )
                    
                    # Update session with messages
                    if session and request.session_id:
                        session_manager.add_message(request.session_id, "user", original_query)
                        session_manager.add_message(request.session_id, "assistant", answer_text[:500])
                        session.last_intent = "property_search"
                        session_manager.save_session(session)
                    
                    coaching_prompt = _get_coaching_for_response(
                        session, request.session_id, request.query, "property_search",
                        search_performed=True, data_source="database", budget_alternatives_shown=budget_alternatives_shown
                    )
                    return ChatQueryResponse(
                        answer=answer_text,
                        projects=projects,
                        sources=fallback_results.get("sources", []) if fallback_results.get("alternatives") else [],
                        confidence=confidence,
                        intent="property_search",
                        refusal_reason=None,
                        response_time_ms=response_time_ms,
                        suggested_actions=[],
                        coaching_prompt=coaching_prompt
                    )
                
                # Normal flow: results found
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

                # Enrich projects with missing data (amenities, nearby places, etc.)
                # NOTE: Enrichment is disabled for now to prevent timeouts
                # Each enrichment makes GPT calls (5-10s each), and with multiple projects
                # this easily exceeds 60s timeout. Can re-enable with async batching later.
                projects_list = search_results["projects"]
                
                # Skip enrichment for now to prevent timeouts
                # TODO: Re-enable with async batching or make it optional
                # enriched_projects = []
                # for project in projects_list:
                #     enrichment_types = []
                #     
                #     # Check what needs enrichment
                #     if not project.get('amenities') or len(str(project.get('amenities', ''))) < 30:
                #         enrichment_types.append("amenities")
                #     if not project.get('nearby_places'):
                #         enrichment_types.append("nearby_places")
                #     if not project.get('connectivity'):
                #         enrichment_types.append("connectivity")
                #     
                #     # Enrich if needed
                #     if enrichment_types:
                #         try:
                #             enriched = await project_enrichment.enrich_project(
                #                 project=project,
                #                 enrichment_types=enrichment_types,
                #                 query=request.query
                #             )
                #             enriched_projects.append(enriched)
                #         except Exception as e:
                #             logger.error(f"Error enriching project {project.get('name')}: {e}")
                #             enriched_projects.append(project)  # Use original if enrichment fails
                #     else:
                #         enriched_projects.append(project)
                # 
                # # Update projects list with enriched data
                # projects_list = enriched_projects
                
                # Check if this is a minimum budget query and calculate answer
                min_budget_answer = None
                query_lower = request.query.lower()
                min_price_keywords = ["minimum budget", "min budget", "starting price", "lowest price", "cheapest", "least expensive", "start from", "starts from", "start price"]
                
                if projects_list and any(kw in query_lower for kw in min_price_keywords):
                    # Calculate minimum budget from results
                    min_price_proj = min(projects_list, key=lambda x: x.get('budget_min', float('inf')) if x.get('budget_min') else float('inf'))
                    min_price_val = min_price_proj.get('budget_min', 0)
                    if min_price_val and min_price_val > 0:
                        min_price_val_cr = min_price_val / 100  # Convert lakhs to crores
                        min_budget_answer = f"💡 **The minimum budget required starts at ₹{min_price_val_cr:.2f} Cr** with {min_price_proj.get('name', 'available projects')}.\n\n"
                
                # Check for better-value configurations and format response
                better_value_count = sum(1 for p in projects_list if p.get("_better_value", False))
                regular_count = len(projects_list) - better_value_count
                
                # Build answer text with sales logic
                if min_budget_answer:
                    # Direct answer for minimum budget queries
                    answer_text = min_budget_answer
                    answer_text += f"• Found {len(projects_list)} project{'s' if len(projects_list) != 1 else ''} matching your criteria\n"
                    answer_text += "• Here are all options:"
                elif better_value_count > 0:
                    # Sales pitch: Highlight better-value options
                    answer_text = f"• Found {regular_count} project{'s' if regular_count != 1 else ''} matching your criteria\n"
                    answer_text += f"• **Great news!** Also found {better_value_count} better-value option{'s' if better_value_count != 1 else ''} (higher BHK in same budget)\n"
                    answer_text += "• Here are all options:"
                else:
                    answer_text = f"• Found {len(projects_list)} project{'s' if len(projects_list) != 1 else ''} matching your criteria\n"
                    answer_text += "• Here are the details:"
                
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
                    projects=projects_list,  # Use enriched projects
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
                    # GPT extraction should have project_name - if not, try fuzzy matching as fallback
                    logger.warning(f"GPT classified as project_facts but didn't extract project_name. Query: {request.query}")
                    logger.info("Attempting fuzzy matching fallback...")
                    
                    # Try fuzzy matching from query
                    from services.fuzzy_matcher import extract_project_name_from_query
                    available_projects = session_state.get("available_projects", [])
                    if available_projects:
                        # Extract project names as strings for fuzzy matching
                        project_names = []
                        for p in available_projects:
                            if isinstance(p, dict):
                                project_names.append(p.get('name', ''))
                            else:
                                project_names.append(str(p))
                        project_name = extract_project_name_from_query(request.query, project_names)
                        if project_name:
                            logger.info(f"✅ Fuzzy matched project: '{project_name}' from query: '{request.query}'")
                        else:
                            # Try from session context
                            if session and hasattr(session, 'last_shown_projects') and session.last_shown_projects:
                                last_project = session.last_shown_projects[0] if isinstance(session.last_shown_projects[0], dict) else None
                                if last_project:
                                    project_name = last_project.get('name')
                                    logger.info(f"✅ Using last shown project from context: '{project_name}'")
                            elif session and hasattr(session, 'interested_projects') and session.interested_projects:
                                project_name = session.interested_projects[-1] if isinstance(session.interested_projects[-1], str) else None
                                if project_name:
                                    logger.info(f"✅ Using interested project from context: '{project_name}'")

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
                            project_dict = dict(project)  # Convert to dict for consistency

                            # Format structured project response
                            response_parts = []
                            response_parts.append(f"# {project_dict.get('name', 'Unknown Project')}")

                            if project_dict.get('developer'):
                                response_parts.append(f"**Developer**: {project_dict['developer']}")

                            if project_dict.get('location'):
                                response_parts.append(f"**Location**: {project_dict['location']}")

                            if project_dict.get('configuration'):
                                response_parts.append(f"**Configurations**: {project_dict['configuration']}")

                            if project_dict.get('price_range'):
                                price = project_dict['price_range']
                                if isinstance(price, dict):
                                    response_parts.append(f"**Price Range**: ₹{price.get('min_display', 'N/A')} - ₹{price.get('max_display', 'N/A')}")
                                else:
                                    response_parts.append(f"**Price**: {price}")

                            if project_dict.get('possession_year'):
                                response_parts.append(f"**Possession**: Q{project_dict.get('possession_quarter', '')} {project_dict['possession_year']}")

                            if project_dict.get('amenities'):
                                response_parts.append(f"\n**Amenities**:\n{project_dict['amenities']}")

                            if project_dict.get('highlights'):
                                response_parts.append(f"\n**Highlights**:\n{project_dict['highlights']}")

                            if project_dict.get('usp'):
                                usp = project_dict['usp']
                                if isinstance(usp, list):
                                    response_parts.append(f"\n**USP**:\n" + "\n".join(f"• {u}" for u in usp))
                                else:
                                    response_parts.append(f"\n**USP**: {usp}")

                            if project_dict.get('rera_number'):
                                response_parts.append(f"\n**RERA**: {project_dict['rera_number']}")

                            if project_dict.get('brochure_url'):
                                response_parts.append(f"\n📄 [View Brochure]({project_dict['brochure_url']})")

                            response_text = "\n\n".join(response_parts)
                            response_time_ms = int((time.time() - start_time) * 1000)

                            # Update session
                            if session:
                                session_manager.add_message(request.session_id, "user", original_query)
                                session_manager.add_message(request.session_id, "assistant", response_text[:500])
                                session.last_intent = "project_facts"
                                session_manager.record_interest(request.session_id, project_dict.get('name'))
                                
                                # CRITICAL: Save project to last_shown_projects
                                if project_dict.get('name'):
                                    if not hasattr(session, 'last_shown_projects') or not session.last_shown_projects:
                                        session.last_shown_projects = []
                                    existing_names = {p.get('name') for p in session.last_shown_projects if isinstance(p, dict) and p.get('name')}
                                    if project_dict.get('name') not in existing_names:
                                        session.last_shown_projects.insert(0, project_dict)
                                        logger.info(f"✅ Saved project '{project_dict.get('name')}' to last_shown_projects")
                                
                                session_manager.save_session(session)

                            logger.info(f"✅ Returned database project details for: {project_dict.get('name')}")

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
                                projects=[project_dict],
                                coaching_prompt=coaching_prompt
                            )
                    except Exception as e:
                        logger.error(f"Error fetching project details: {e}")

                # If no project found, fall through to GPT
                logger.info("Project not found in database, falling back to GPT consultant")

            elif intent == "nearby_properties":
                logger.info("🔹 PATH 1: Database - Nearby Properties (10km radius)")
                
                # Get location context from session or extraction
                from utils.geolocation_utils import get_coordinates, calculate_distance
                from database.pixeltable_setup import get_projects_table
                
                target_location = None
                
                # Priority 1: Check GPT extraction for location
                if extraction and extraction.get("location"):
                    target_location = extraction.get("location")
                    logger.info(f"📍 Using location from GPT extraction: {target_location}")
                
                # Priority 2: Check session current_filters
                if not target_location and session:
                    if hasattr(session, 'current_filters') and session.current_filters:
                        target_location = session.current_filters.get('locality') or session.current_filters.get('location')
                        if target_location:
                            logger.info(f"📍 Using location from session filters: {target_location}")
                
                # Priority 3: Check last shown projects
                if not target_location and session:
                    if hasattr(session, 'last_shown_projects') and session.last_shown_projects:
                        first_project = session.last_shown_projects[0]
                        if isinstance(first_project, dict):
                            target_location = first_project.get('location')
                            if target_location:
                                logger.info(f"📍 Using location from last shown project: {target_location}")
                
                if not target_location:
                    logger.warning("No location context found for nearby search")
                    # Fall through to GPT for a helpful response
                else:
                    # Get coordinates for target location
                    center_coords = get_coordinates(target_location)
                    
                    if center_coords:
                        center_lat, center_lon = center_coords
                        logger.info(f"📍 Searching within 10km of {target_location} ({center_lat}, {center_lon})")
                        
                        # Fetch all projects with coordinates
                        projects_table = get_projects_table()
                        nearby_projects = []
                        
                        if projects_table:
                            try:
                                all_projects = projects_table.select(
                                    projects_table.project_id, projects_table.name, projects_table.location,
                                    projects_table.budget_min, projects_table.budget_max,
                                    projects_table.configuration, projects_table.status,
                                    projects_table.possession_year, projects_table.possession_quarter,
                                    projects_table.usp, projects_table.amenities, projects_table.rera_number,
                                    projects_table.latitude, projects_table.longitude
                                ).collect()
                                
                                for proj in all_projects:
                                    p_lat = proj.get('latitude')
                                    p_lon = proj.get('longitude')
                                    
                                    if p_lat and p_lon:
                                        try:
                                            dist = calculate_distance(center_lat, center_lon, float(p_lat), float(p_lon))
                                            if dist <= 10.0:  # 10km radius
                                                proj_copy = dict(proj)
                                                proj_copy['_distance_km'] = round(dist, 1)
                                                nearby_projects.append(proj_copy)
                                        except (ValueError, TypeError) as e:
                                            logger.warning(f"Invalid coordinates for project {proj.get('name')}: {e}")
                                
                                # Sort by distance (nearest first)
                                nearby_projects.sort(key=lambda x: x.get('_distance_km', 999))
                                
                            except Exception as e:
                                logger.error(f"Error fetching projects for nearby search: {e}")
                        
                        if nearby_projects:
                            logger.info(f"✅ Found {len(nearby_projects)} projects within 10km of {target_location}")
                            
                            # Build response with distance info
                            response_parts = [f"🗺️ Found **{len(nearby_projects)} projects** within 10km of **{target_location.title()}**:\n"]
                            
                            for i, proj in enumerate(nearby_projects[:5], 1):  # Show top 5
                                dist_str = f"{proj['_distance_km']} km away"
                                response_parts.append(f"\n**{i}. {proj['name']}** ({proj.get('status', 'N/A')})")
                                response_parts.append(f"   📍 {proj['location']} (*{dist_str}*)")
                                response_parts.append(f"   💰 ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                                response_parts.append(f"   🏠 {proj.get('configuration', 'N/A')}")
                                if proj.get('usp'):
                                    usp_text = proj['usp'][:80] + "..." if len(proj.get('usp', '')) > 80 else proj.get('usp', '')
                                    response_parts.append(f"   ✨ {usp_text}")
                            
                            if len(nearby_projects) > 5:
                                response_parts.append(f"\n\n📋 Plus **{len(nearby_projects) - 5} more options** nearby!")
                            
                            response_parts.append("\n\nWould you like more details about any of these projects? 🏡")
                            
                            answer_text = "\n".join(response_parts)
                            response_time_ms = int((time.time() - start_time) * 1000)
                            
                            # Update session
                            if session:
                                session.last_shown_projects = nearby_projects[:10]
                                session.last_intent = "nearby_properties"
                                session_manager.add_message(request.session_id, "user", original_query)
                                session_manager.add_message(request.session_id, "assistant", answer_text[:500])
                                session_manager.save_session(session)
                            
                            coaching_prompt = _get_coaching_for_response(
                                session, request.session_id, request.query, "nearby_properties",
                                search_performed=True, data_source="database", budget_alternatives_shown=False
                            )
                            return ChatQueryResponse(
                                answer=answer_text,
                                projects=nearby_projects[:5],
                                sources=[],
                                confidence="High",
                                intent="nearby_properties",
                                refusal_reason=None,
                                response_time_ms=response_time_ms,
                                suggested_actions=["Compare projects", "Schedule site visit", "View more options"],
                                coaching_prompt=coaching_prompt
                            )
                        else:
                            logger.info(f"No projects found within 10km of {target_location}")
                            # Fall through to GPT
                    else:
                        logger.warning(f"Could not get coordinates for location: {target_location}")
                        # Fall through to GPT

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
        # 🆕 Pass extraction data (project_name, topic, etc.) to consultant for context
        extraction_data = context_metadata.get("extraction", {}) if context_metadata else {}
        response_text = await generate_consultant_response(
            query=request.query,
            session=session,
            intent=intent,
            sentiment_analysis=sentiment_analysis,
            extraction=extraction_data
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
                    # GPT intent classifier handles scheduling intent detection - no keyword matching needed
                    # Check extraction for scheduling intent hints
                    wants_visit = extraction.get("topic") in ["site_visit", "visit", "scheduling"] or intent == "site_visit"
                    wants_callback = extraction.get("topic") in ["callback", "contact"] or intent == "meeting_request"
                    
                    # GPT will understand confirmation from context
                    is_confirmation = False  # Will be determined by GPT from conversation context
                    
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

        # Log coaching prompt status
        coaching_prompt_value = coaching_prompt if 'coaching_prompt' in locals() else None
        if coaching_prompt_value:
            logger.info(f"✅ Returning coaching_prompt in response: {coaching_prompt_value.get('type')} - {coaching_prompt_value.get('message')[:50]}...")
        else:
            logger.debug(f"⚠️ No coaching_prompt in response for query: {request.query[:50]}")
        
        return ChatQueryResponse(
            answer=response_text,
            sources=[],
            confidence="High",
            intent=intent,
            refusal_reason=None,
            response_time_ms=response_time_ms,
            suggested_actions=[],
            coaching_prompt=coaching_prompt_value
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
        # GPT intent classifier handles "more info" queries - no keyword matching needed
        if intent == "more_info_request" and data_source in ["gpt_generation", "hybrid"]:
            logger.info(f"Routing more_info_request to GPT content generator (data_source={data_source}, is_more_info_query={is_more_info_query})")
            
            # Get project from extraction, query text, or session
            project_name = extraction.get("project_name")
            topic = extraction.get("topic", "general_selling_points")
            
            # GPT extraction already handles project name matching - no keyword matching needed
            # Project name should come from extraction dict or session context
            
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
                logger.warning(f"hybrid_retrieval not available: {e}")
                # Import module and use directly to avoid scoping issues
                import services.hybrid_retrieval as hr_module
                hr_instance = hr_module.hybrid_retrieval
                try:
                    search_results = await hr_instance.search_with_filters(
                        query=request.query,
                        filters=filters
                    )
                except Exception as e2:
                    logger.error(f"Failed to use hybrid_retrieval after re-import: {e2}")
                    raise
            except Exception as e:
                # For other exceptions, just log and re-raise
                logger.error(f"hybrid_retrieval search failed: {e}")
                raise
            
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
async def get_projects(user_id: str = "guest"):
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
            logger.warning(f"hybrid_retrieval not available: {e}")
            # Import module and use directly to avoid scoping issues
            import services.hybrid_retrieval as hr_module
            hr_instance = hr_module.hybrid_retrieval
            try:
                search_results = await hr_instance.search_with_filters(
                    query=request.query,
                    filters=filters
                )
            except Exception as e2:
                logger.error(f"Failed to use hybrid_retrieval after re-import: {e2}")
                search_results = {"projects": [], "sources": []}
        except Exception as e:
            # For other exceptions, just log and return empty results
            logger.error(f"hybrid_retrieval search failed: {e}")
            search_results = {"projects": [], "sources": []}

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
        response = execute_flow(state, request.query, chat_history=session.messages)
        
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
