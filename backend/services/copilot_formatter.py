"""
Copilot Formatter Service
Generates strict JSON responses with bullets using GPT-4.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

from config import settings
from models.copilot_response import CopilotResponse, BudgetRelaxationResponse, ProjectInfo
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
            base_url=settings.openai_base_url
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
        intent: Optional[str] = None
    ) -> CopilotResponse:
        """
        Generate copilot response in strict JSON format.

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
        # Prepare payload for GPT
        payload = {
            "query": query,
            "context": context,
            "db_projects": db_projects or [],
            "relaxed_projects": relaxed_projects or [],
            "applied_step": applied_step,
            "filters": filters or {},
            "intent": intent
        }

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": COPILOT_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, indent=2)}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"},  # Force JSON output
                max_tokens=settings.max_tokens
            )

            json_response = json.loads(response.choices[0].message.content)

            # Log token usage
            usage = response.usage
            logger.info(
                f"GPT-4 tokens: {usage.total_tokens} "
                f"(prompt: {usage.prompt_tokens}, completion: {usage.completion_tokens})"
            )

            # If budget relaxation was applied, return extended model
            if applied_step and applied_step > 1.0:
                return BudgetRelaxationResponse(
                    **json_response,
                    relaxation_applied=True,
                    relaxation_step=applied_step,
                    original_budget=context.get("last_budget"),
                    relaxed_budget=int(context.get("last_budget", 0) * applied_step) if context.get("last_budget") else None
                )

            # Standard response
            return CopilotResponse(**json_response)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT response as JSON: {e}")
            # Return fallback response
            return self._fallback_response(query, db_projects or relaxed_projects)

        except Exception as e:
            logger.error(f"Copilot formatter error: {e}", exc_info=True)
            return self._fallback_response(query, db_projects or relaxed_projects)

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
            next_suggestion="Ask about specific project details or schedule a site visit"
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
    intent: Optional[str] = None
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
        intent=intent
    )
