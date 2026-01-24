"""
/assist Endpoint Router (Spec-Compliant)
Main endpoint for Real Estate Sales Copilot with Redis context persistence.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Optional

from models.copilot_request import AssistRequest
from models.copilot_response import CopilotResponse
from services.redis_context import get_redis_context_manager
from services.copilot_formatter import copilot_formatter
from services.flow_engine import FlowState, FlowRequirements, execute_flow

logger = logging.getLogger(__name__)


router = APIRouter()

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

        # 2. Map Redis Context to FlowState (Global State)
        # Note: Redis uses Lakhs (int), FlowEngine uses Crores (float)
        last_budget_cr = (ctx.get("last_budget") / 100.0) if ctx.get("last_budget") else None
        
        flow_state = FlowState(
            requirements=FlowRequirements(
                configuration=ctx.get("last_configuration"),
                location=ctx.get("last_location"),
                budget_max=last_budget_cr,
                project_name=ctx.get("active_project")
            ),
            last_shown_projects=ctx.get("last_results", []),
            last_intent=ctx.get("last_intent"),
            selected_project_name=ctx.get("active_project")
        )

        # 3. Execute Unified Flow (Intent -> Search -> Radius -> Formatting)
        # This one call replaces the manual pipeline below
        flow_response = execute_flow(flow_state, request.query)
        logger.info(f"🚀 Unified Flow Output: {flow_response.current_node} (Intent: {flow_state.last_intent})")

        # 4. Map FlowResponse to CopilotResponse (Frontend Protocol)
        # Reuse formatter's converter for DB rows -> ProjectInfo
        project_infos = copilot_formatter._convert_to_project_infos(flow_response.projects)
        
        response = CopilotResponse(
            projects=project_infos,
            answer=flow_response.answer_bullets or [flow_response.system_action],
            pitch_help=flow_response.pitch_help or "I recommend these options based on your preferences.",
            next_suggestion=flow_response.next_suggestion or "Would you like to schedule a site visit?",
            coaching_point=flow_response.coaching_point or "Build trust by highlighting project ROI and location benefits."
        )

        # 5. Sync Back to Redis Context
        reqs = flow_response.extracted_requirements
        
        # Convert budget back to Lakhs for Redis
        budget_lakhs = int(reqs.get("budget_max") * 100) if reqs.get("budget_max") else ctx.get("last_budget")
        
        ctx.update({
            "active_project": flow_state.selected_project_name or reqs.get("project_name") or ctx.get("active_project"),
            "last_budget": budget_lakhs,
            "last_location": reqs.get("location") or ctx.get("last_location"),
            "last_configuration": reqs.get("configuration") or ctx.get("last_configuration"),
            "last_results": flow_response.projects or ctx.get("last_results"),
            "last_intent": flow_state.last_intent,
            "last_filters": reqs # Flow engine requirements are the source of truth for filters now
        })

        redis_manager.save_context(request.call_id, ctx)
        logger.info(f"💾 Updated context with Radius/Flow State for call_id={request.call_id}")

        return response

    except Exception as e:
        logger.error(f"❌ /assist endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
