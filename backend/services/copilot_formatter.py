"""
Copilot Formatter Service
Generates strict JSON responses with bullets using GPT-4.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from config import settings
from models.copilot_response import CopilotResponse, BudgetRelaxationResponse, ProjectInfo, LiveCallStructure
from prompts.sales_copilot_system import COPILOT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class CopilotFormatter:
    """
    Formats copilot responses using GPT-4 with strict JSON output.
    Enforces bullet-point format for reasoning and DB facts for projects.
    """

    def __init__(self):
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=10.0  # 10 second timeout for API calls
        )
        self.model = settings.effective_gpt_model
        self.temperature = 0.3  # Low temp for consistent formatting

    def format_response(
        self,
        query: str,
        context: Dict[str, Any],
        db_projects: List[Dict[str, Any]],
        relaxed_projects: List[Dict[str, Any]],
        applied_step: Optional[float],
        filters: Dict[str, Any],
        intent: Optional[str] = None,
        live_call_mode: bool = False
    ) -> CopilotResponse:
        """
        Generate copilot response in strict JSON format.
        
        CRITICAL FIX: Always include actual database projects in response.
        GPT is only used for generating coaching content, NOT for returning projects.

        Args:
            query: User query string
            context: Redis context dict
            db_projects: Projects from database (exact match)
            relaxed_projects: Projects from budget relaxation
            applied_step: Relaxation multiplier (1.0, 1.1, 1.2, 1.3)
            filters: Applied quick filters
            intent: Detected intent (optional)

        Returns:
            CopilotResponse object (validated Pydantic model)
        """
        # FIX: Always include database projects in response
        # Choose which projects to return (relaxed takes precedence if available)
        projects_to_return = relaxed_projects if relaxed_projects else db_projects
        
        # Convert database projects to ProjectInfo models FIRST
        project_infos = self._convert_to_project_infos(projects_to_return or [])
        
        logger.info(f"📦 Converting {len(projects_to_return or [])} database projects to response format")
        
        # Prepare payload for GPT (for coaching content only)
        payload = {
            "query": query,
            "context": context,
            "db_projects": db_projects or [],
            "relaxed_projects": relaxed_projects or [],
            "applied_step": applied_step,
            "filters": filters or {},
            "intent": intent,
            "live_call_mode": live_call_mode
        }
        
        # Update system prompt if live call mode is enabled
        system_prompt = COPILOT_SYSTEM_PROMPT
        if live_call_mode:
            system_prompt += "\n\n⚠️ LIVE CALL MODE ENABLED: Generate live_call_structure with all 6 parts."

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(payload, indent=2)}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},  # Force JSON output
                max_tokens=settings.max_tokens
            )

            json_response = json.loads(response.choices[0].message.content)

            # Validate coaching_point is present
            if 'coaching_point' not in json_response or not json_response['coaching_point']:
                logger.warning("GPT response missing coaching_point, adding default")
                json_response['coaching_point'] = "Listen actively and address customer's specific needs with relevant project details"

            # Log token usage
            usage = response.usage
            logger.info(
                f"GPT-4 tokens: {usage.total_tokens} "
                f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
            )
            
            # CRITICAL FIX: Override GPT's projects with actual database projects
            # GPT should only provide coaching content, not project data
            json_response['projects'] = project_infos
            logger.info(f"✅ Injected {len(project_infos)} real database projects into response")
            
            # Handle live_call_structure if present and live_call_mode is enabled
            live_call_structure = None
            if live_call_mode and 'live_call_structure' in json_response:
                try:
                    live_call_structure = LiveCallStructure(**json_response['live_call_structure'])
                    logger.info("✅ Generated live_call_structure for live call scenario")
                except Exception as e:
                    logger.warning(f"Failed to parse live_call_structure: {e}")
                    live_call_structure = None
            
            # Remove live_call_structure from json_response before passing to model
            json_response.pop('live_call_structure', None)

            # If budget relaxation was applied, return extended model
            if applied_step and applied_step > 1.0:
                return BudgetRelaxationResponse(
                    **json_response,
                    live_call_structure=live_call_structure,
                    relaxation_applied=True,
                    relaxation_step=applied_step,
                    original_budget=context.get("last_budget"),
                    relaxed_budget=int(context.get("last_budget", 0) * applied_step) if context.get("last_budget") else None
                )

            # Standard response
            return CopilotResponse(**json_response, live_call_structure=live_call_structure)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response as JSON: {e}")
            # Return fallback response with actual projects
            return self._fallback_response(query, projects_to_return or [])

        except Exception as e:
            logger.error(f"Copilot formatter error: {e}", exc_info=True)
            return self._fallback_response(query, projects_to_return or [])
    
    def _convert_to_project_infos(self, projects: List[Dict[str, Any]]) -> List[ProjectInfo]:
        """
        Convert database project dicts to ProjectInfo Pydantic models.
        
        Args:
            projects: List of project dicts from database
            
        Returns:
            List of ProjectInfo models
        """
        project_infos = []
        
        for proj in projects:
            try:
                # Extract amenities - handle different formats
                amenities = proj.get("amenities", [])
                if isinstance(amenities, str):
                    # Split string amenities by comma or newline
                    amenities = [a.strip() for a in amenities.replace('\n', ',').split(',') if a.strip()]
                elif not isinstance(amenities, list):
                    amenities = []
                
                project_infos.append(ProjectInfo(
                    name=proj.get("name") or proj.get("project_name") or "Unknown Project",
                    location=proj.get("location") or proj.get("locality") or "Location not available",
                    price_range=self._format_price_range(proj.get("budget_min"), proj.get("budget_max")),
                    bhk=proj.get("configuration") or proj.get("config_summary") or "Configuration not available",
                    amenities=amenities[:5],  # Limit to top 5 amenities
                    status=proj.get("status") or "Status not available",
                    # NEW: Include all additional fields
                    brochure_url=proj.get("brochure_url") or proj.get("brochure_link"),
                    rm_details=proj.get("rm_details") or {},
                    registration_process=proj.get("registration_process"),
                    zone=proj.get("zone"),
                    rera_number=proj.get("rera_number"),
                    developer=proj.get("developer") or proj.get("developer_name"),
                    possession_year=proj.get("possession_year"),
                    possession_quarter=proj.get("possession_quarter"),
                    matching_units=proj.get("matching_units")
                ))
            except Exception as e:
                logger.error(f"Failed to convert project to ProjectInfo: {e}")
                # Continue with other projects
                continue
        
        return project_infos

    def _fallback_response(self, query: str, projects: List[Dict[str, Any]]) -> CopilotResponse:
        """
        Fallback response when GPT fails.
        Returns minimal valid response with database facts.
        """
        logger.warning("Using fallback response due to GPT error")

        # Convert DB projects to ProjectInfo models
        project_infos = []
        for proj in projects[:3]:  # Limit to 3 projects
            try:
                project_infos.append(ProjectInfo(
                    name=proj.get("name", "Unknown Project"),
                    location=proj.get("location", "Location not available"),
                    price_range=self._format_price_range(proj.get("budget_min"), proj.get("budget_max")),
                    bhk=proj.get("configuration", "Configuration not available"),
                    amenities=proj.get("amenities", []) if isinstance(proj.get("amenities"), list) else [],
                    status=proj.get("status", "Status not available")
                ))
            except Exception as e:
                logger.error(f"Failed to convert project to ProjectInfo: {e}")

        return CopilotResponse(
            projects=project_infos,
            answer=[
                "I found some projects matching your criteria",
                "Please review the project details above",
                "Let me know if you need more information"
            ],
            pitch_help="These projects offer competitive pricing and good amenities for the location",
            next_suggestion="Ask about specific project details or schedule a site visit",
            coaching_point="Present these options confidently and ask which features matter most to the customer"
        )

    def _format_price_range(self, min_price: Optional[int], max_price: Optional[int]) -> str:
        """
        Format price range in lakhs/crores.
        Example: 7000000, 13000000 -> "70L - 1.3Cr"
        """
        if not min_price or not max_price:
            return "Price not available"

        def format_price(price: int) -> str:
            if price >= 10000000:  # 1 crore+
                crores = price / 10000000
                if crores == int(crores):
                    return f"{int(crores)}Cr"
                return f"{crores:.1f}Cr"
            else:  # lakhs
                lakhs = price / 100000
                if lakhs == int(lakhs):
                    return f"{int(lakhs)}L"
                return f"{lakhs:.1f}L"

        return f"{format_price(min_price)} - {format_price(max_price)}"


# Global instance
copilot_formatter = CopilotFormatter()


def format_copilot_response(
    query: str,
    context: Dict[str, Any],
    db_projects: List[Dict[str, Any]],
    relaxed_projects: List[Dict[str, Any]],
    applied_step: Optional[float],
    filters: Dict[str, Any],
    intent: Optional[str] = None,
    live_call_mode: bool = False
) -> CopilotResponse:
    """
    Convenience function to call global copilot_formatter instance.
    """
    return copilot_formatter.format_response(
        query=query,
        context=context,
        db_projects=db_projects,
        relaxed_projects=relaxed_projects,
        applied_step=applied_step,
        filters=filters,
        intent=intent,
        live_call_mode=live_call_mode
    )
