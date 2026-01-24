"""
/assist Endpoint Router (Spec-Compliant)
Main endpoint for Real Estate Sales Copilot with Redis context persistence.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from models.copilot_request import AssistRequest, QuickFilters
from models.copilot_response import CopilotResponse
from services.redis_context import get_redis_context_manager
from services.gpt_intent_classifier import classify_intent_gpt_first
from services.hybrid_retrieval import hybrid_retrieval
from services.budget_relaxer import budget_relaxer
from services.copilot_formatter import format_copilot_response
from services.filter_extractor import PropertyFilters, filter_extractor

logger = logging.getLogger(__name__)

router = APIRouter()




# Adapter for Redis Dict -> ConversationSession object
class SessionAdapter:
    def __init__(self, ctx: dict):
        self.session_id = ctx.get("call_id", "unknown")
        self.messages = ctx.get("messages", [])
        self.last_shown_projects = ctx.get("last_results", [])
        self.current_filters = ctx.get("last_filters", {})
        self.interested_projects = ctx.get("interested_projects", [])
        self.objections_raised = ctx.get("objections_raised", [])
        self.last_topic = ctx.get("last_topic")
        self.conversation_phase = ctx.get("conversation_phase")

# 🆕 Inject Sales Conversation Logic
async def _handle_sales_intervention(query: str, ctx: dict) -> Optional[CopilotResponse]:
    """Check if query needs Sales Coach intervention and return response if so."""
    from services.sales_conversation import sales_conversation
    from services.gpt_sales_consultant import generate_consultant_response
    
    if not sales_conversation.should_handle(query):
        return None
        
    response_text, intent, fallback, actions = sales_conversation.handle_sales_query(query)
    
    if fallback:
        # Route to GPT Consultant (Sales Coach)
        logger.info(f"🚀 Routing to Sales Coach (Intent: {intent})")
        session_obj = SessionAdapter(ctx)
        coach_response = await generate_consultant_response(
            query=query,
            session=session_obj,
            intent=intent
        )
        
        # Convert text block to bullets (heuristic split)
        bullets = [line.strip().lstrip('-•').strip() for line in coach_response.split('\n') if line.strip() and (line.strip().startswith('-') or line.strip().startswith('•') or line[0].isdigit())]
        if not bullets:
            bullets = [coach_response] # Fallback if no bullets found
            
        return CopilotResponse(
            projects=[], # No specific project focus for general advice
            answer=bullets, 
            pitch_help="Read the script above to the client.",
            next_suggestion="Ask: 'Does that make sense for your investment goals?'",
            coaching_point="Use the 'Cost of Waiting' to create urgency." if "budget" in str(intent) else "Focus on value over price."
        )
        
    elif response_text:
         # Static response (e.g. scheduling)
         return CopilotResponse(
            projects=[],
            answer=[line.strip() for line in response_text.split('\n') if line.strip()],
            pitch_help="Coordinate the meeting time.",
            next_suggestion="Confirm the slot.",
            coaching_point="Lock in the meeting immediately."
         )
         
    return None

@router.post("/", response_model=CopilotResponse)
async def assist(request: AssistRequest):
    """
    Main /assist endpoint for Sales Copilot.
    """
    try:
        # 1. Load context from Redis
        redis_manager = get_redis_context_manager()
        ctx = redis_manager.load_context(request.call_id)
        logger.info(f"📥 Loaded context for call_id={request.call_id}")

        # 🆕 CHECK SALES INTERVENTION FIRST
        intervention = await _handle_sales_intervention(request.query, ctx)
        if intervention:
            return intervention

        # 2. Classify intent with GPT
        # Pass ctx as comprehensive_context (not conversation_history which expects List[Dict])
        intent_result = classify_intent_gpt_first(
            query=request.query,
            comprehensive_context={"session": ctx}  # Wrap in expected format
        )
        logger.info(f"🎯 Intent: {intent_result.get('intent')} (confidence: {intent_result.get('confidence')})")

        # 3. Extract entities from intent result
        extraction = intent_result.get('extraction', {})

        project = extraction.get("project_name") or ctx.get("active_project")
        budget = extraction.get("budget_max") or extraction.get("budget") or ctx.get("last_budget")
        location = extraction.get("location") or ctx.get("last_location")
        configuration = extraction.get("configuration") or ctx.get("last_configuration")

        logger.info(f"🔍 Entities: project={project}, budget={budget}, location={location}, bhk={configuration}")

        # 4. Merge filters (request overrides context)
        context_filters = ctx.get("last_filters", {})
        request_filters = request.filters.model_dump(exclude_none=True) if request.filters else {}
        merged_filters_dict = {**context_filters, **request_filters}

        # Convert to PropertyFilters object
        merged_filters = _convert_to_property_filters(merged_filters_dict, budget, location, configuration)

        logger.info(f"🎛️ Merged filters: {merged_filters.model_dump(exclude_none=True)}")

        # 5. Query database with filters
        db_result = await hybrid_retrieval.search_with_filters(
            query=request.query,
            filters=merged_filters,
            use_llm_extraction=False
        )
        db_projects = db_result.get("projects", [])

        logger.info(f"📊 Database returned {len(db_projects)} projects")

        # 6. Apply budget relaxation if no results and budget exists
        relaxed_projects, relaxation_step = [], None
        if budget_relaxer.should_apply_relaxation(db_projects, budget):
            logger.info("🔄 Applying budget relaxation...")
            relaxed_projects, relaxation_step = await budget_relaxer.relax_and_find(
                budget=budget,
                location=location,
                filters=merged_filters,
                query=request.query
            )
            logger.info(f"💰 Relaxation result: {len(relaxed_projects)} projects at {relaxation_step}x")

        # 7. Format response with GPT (strict JSON + bullets)
        response = format_copilot_response(
            query=request.query,
            context=ctx,
            db_projects=db_projects,
            relaxed_projects=relaxed_projects,
            applied_step=relaxation_step,
            filters=merged_filters_dict,
            intent=intent_result.get('intent', 'unknown')
        )

        logger.info(f"✅ Formatted response with {len(response.projects)} projects, {len(response.answer)} bullets")

        # 8. Update context in Redis
        ctx.update({
            "active_project": project or ctx.get("active_project"),
            "last_budget": budget or ctx.get("last_budget"),
            "last_location": location or ctx.get("last_location"),
            "last_configuration": configuration or ctx.get("last_configuration"),
            "last_results": relaxed_projects or db_projects,
            "last_filters": merged_filters_dict,
            # Update signals based on intent and behavior
            "signals": {
                "price_sensitive": relaxation_step is not None or ctx.get("signals", {}).get("price_sensitive", False),
                "upgrade_intent": intent_result.get('intent') == "comparison" or ctx.get("signals", {}).get("upgrade_intent", False)
            }
        })

        redis_manager.save_context(request.call_id, ctx)
        logger.info(f"💾 Updated context for call_id={request.call_id}")

        return response

    except Exception as e:
        logger.error(f"❌ /assist endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


def _convert_to_property_filters(
    filters_dict: dict,
    budget: Optional[int],
    location: Optional[str],
    configuration: Optional[str] = None
) -> PropertyFilters:
    """
    Convert merged filters dict to PropertyFilters object.

    Handles conversion of spec-compliant quick filters to PropertyFilters.
    Maps:
    - price_range [min, max] → min_price_inr, max_price_inr
    - bhk ["2BHK", "3BHK"] → bedrooms [2, 3]
    - configuration "2BHK" → bedrooms [2]  # NEW: from entity extraction
    - status → status
    - amenities → required_amenities
    - possession_window → possession_year

    Args:
        filters_dict: Merged filters dictionary
        budget: Budget from entity extraction
        location: Location from entity extraction
        configuration: Configuration (BHK) from entity extraction

    Returns:
        PropertyFilters object
    """
    property_filters = PropertyFilters()

    # Price range handling
    if "price_range" in filters_dict and filters_dict["price_range"]:
        price_range = filters_dict["price_range"]
        # Ensure it's a list, not a slice object
        if isinstance(price_range, (list, tuple)) and len(price_range) >= 2:
            property_filters.min_price_inr = int(price_range[0]) if price_range[0] is not None else None
            property_filters.max_price_inr = int(price_range[1]) if price_range[1] is not None else None
    elif budget:
        # Budget comes from GPT in lakhs, convert to INR (1 lakh = 100,000)
        property_filters.max_price_inr = int(budget * 100000) if budget is not None else None
        logger.info(f"💰 Converted budget from {budget}L to {property_filters.max_price_inr} INR")

    # BHK handling: Convert "2BHK" to bedroom count
    # Priority: request filters > entity extraction > context
    if "bhk" in filters_dict and filters_dict["bhk"]:
        bedrooms = []
        for bhk_str in filters_dict["bhk"]:
            if isinstance(bhk_str, str):
                # Extract number from "2BHK", "3BHK", etc.
                import re
                match = re.search(r'(\d+)', bhk_str)
                if match:
                    bedrooms.append(int(match.group(1)))
        if bedrooms:
            property_filters.bedrooms = bedrooms
    elif configuration:  # NEW: Use extracted configuration if no filter provided
        # Extract number from "2BHK", "3BHK", etc.
        import re
        match = re.search(r'(\d+)', configuration)
        if match:
            property_filters.bedrooms = [int(match.group(1))]
            logger.info(f"🏠 Extracted BHK from configuration: {configuration} → bedrooms={property_filters.bedrooms}")

    # Status handling
    if "status" in filters_dict and filters_dict["status"]:
        property_filters.status = filters_dict["status"]

    # Amenities handling
    if "amenities" in filters_dict and filters_dict["amenities"]:
        property_filters.required_amenities = filters_dict["amenities"]

    # Possession window
    if "possession_window" in filters_dict and filters_dict["possession_window"]:
        property_filters.possession_year = filters_dict["possession_window"]

    # Location handling
    if location:
        if not property_filters.locality:
            property_filters.locality = location
        if not property_filters.area:
            property_filters.area = location

    return property_filters


@router.get("/health")
async def health_check():
    """
    Health check endpoint for /assist router.
    Verifies Redis connection and service availability.
    """
    try:
        redis_manager = get_redis_context_manager()
        redis_health = redis_manager.health_check()

        return {
            "status": "healthy",
            "endpoint": "/api/assist",
            "redis": redis_health
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "endpoint": "/api/assist",
            "error": str(e)
        }
