"""
Response formatting service for sales-optimized output.
Formats property search results as structured lists vs general answers as formatted text.
"""

from typing import Dict, List, Any, Literal, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

ResponseFormat = Literal["structured_list", "formatted_text", "comparison_table"]


class FormattedResponse(BaseModel):
    """Unified response format for all query types"""
    format_type: ResponseFormat
    answer: str  # Formatted text (for all responses)
    structured_data: Optional[Dict] = None  # For property lists
    sources: List[Dict]
    confidence: str
    intent: str


class ResponseFormatter:
    """Format responses optimally for sales executives during client calls"""

    def format_property_search_results(
        self,
        projects: List[Dict],
        query: str,
        filters: Dict
    ) -> FormattedResponse:
        """
        Format property search results as structured cards.

        Args:
            projects: List of matching projects with units
            query: Original user query
            filters: Extracted filters used for search

        Returns:
            FormattedResponse with structured list format
        """
        project_count = len(projects)
        filter_desc = self._describe_filters(filters)

        if project_count == 0:
            answer = "🔍 **No matching properties found.**\n\n"
            answer += "Please try:\n"
            answer += "• Adjusting your budget range\n"
            answer += "• Different unit configurations\n"
            answer += "• Alternative locations\n\n"
            answer += "*Contact our sales team for more options and personalized assistance.*"

            return FormattedResponse(
                format_type="structured_list",
                answer=answer,
                structured_data={"projects": [], "total_count": 0, "filters_applied": filters},
                sources=[],
                confidence="Low",
                intent="property_search"
            )

        # Create summary header
        answer = f"🏠 **Found {project_count} matching project{'s' if project_count != 1 else ''}"
        if filter_desc:
            answer += f" {filter_desc}"
        answer += ":**\n\n"

        # Format each project as a card
        for idx, project in enumerate(projects[:3], 1):
            answer += f"**{idx}. {project['project_name']}**"
            if project.get('developer_name'):
                answer += f" by {project['developer_name']}"
            answer += "\n"

            # Location
            if project.get('location'):
                answer += f"📍 {project['location']}\n"

            # Price range
            if project.get('price_range'):
                answer += f"💰 {project['price_range']['min_display']} - {project['price_range']['max_display']}\n"

            # Unit count
            answer += f"🏗️ {project['matching_unit_count']} matching unit{'s' if project['matching_unit_count'] != 1 else ''}\n"

            # Show sample units
            sample_units = project.get('sample_units', [])
            for unit in sample_units[:2]:
                unit_line = f"  • {unit['bedrooms']}BHK"
                if unit.get('price_display'):
                    unit_line += f": {unit['price_display']}"
                if unit.get('carpet_area_sqft'):
                    unit_line += f" | {unit['carpet_area_sqft']} sqft"
                if unit.get('possession'):
                    unit_line += f" | {unit['possession']}"
                answer += unit_line + "\n"

            if project.get('can_expand') and project['matching_unit_count'] > 2:
                remaining = project['matching_unit_count'] - 2
                answer += f"  ➕ *+{remaining} more unit{'s' if remaining != 1 else ''} available*\n"

            # RERA number if available
            if project.get('rera_number'):
                answer += f"📋 RERA: {project['rera_number']}\n"

            answer += "\n"

        # Footer if more projects available
        if project_count > 3:
            answer += f"*Showing top 3 projects. {project_count - 3} more project{'s' if project_count - 3 != 1 else ''} match{'es' if project_count - 3 == 1 else ''} your criteria.*\n"

        return FormattedResponse(
            format_type="structured_list",
            answer=answer,
            structured_data={
                "projects": projects,
                "total_count": project_count,
                "filters_applied": filters
            },
            sources=[],  # Property searches use structured data, not chunk sources
            confidence="High" if project_count > 0 else "Low",
            intent="property_search"
        )

    def format_general_answer(
        self,
        answer: str,
        sources: List[Dict],
        confidence: str,
        intent: str
    ) -> FormattedResponse:
        """
        Format general Q&A responses (existing emoji style from answer_generator).

        Args:
            answer: Already formatted answer from answer_generator
            sources: List of source chunks
            confidence: Confidence level
            intent: Query intent

        Returns:
            FormattedResponse with formatted_text type
        """
        return FormattedResponse(
            format_type="formatted_text",
            answer=answer,  # Already formatted by answer_generator
            structured_data=None,
            sources=sources,
            confidence=confidence,
            intent=intent
        )

    def _describe_filters(self, filters: Dict) -> str:
        """
        Create human-readable filter description.

        Args:
            filters: Extracted filters dict

        Returns:
            String description like "for 2BHK under ₹3 Cr in Bangalore"
        """
        parts = []

        # Bedroom filter
        if filters.get("bedrooms"):
            bhk_list = filters["bedrooms"]
            if len(bhk_list) == 1:
                parts.append(f"for {bhk_list[0]}BHK")
            else:
                parts.append(f"for {', '.join(str(b) + 'BHK' for b in bhk_list)}")

        # Price filter
        if filters.get("max_price_inr"):
            price = self._format_price(filters["max_price_inr"])
            parts.append(f"under {price}")
        elif filters.get("min_price_inr"):
            price = self._format_price(filters["min_price_inr"])
            parts.append(f"above {price}")
        elif filters.get("budget_inr"):
            price = self._format_price(filters["budget_inr"])
            parts.append(f"around {price}")

        # Location filter
        if filters.get("locality"):
            parts.append(f"in {filters['locality']}")
        elif filters.get("city"):
            parts.append(f"in {filters['city']}")

        # Status filter
        if filters.get("status"):
            status_map = {"completed": "ready to move", "ongoing": "under construction"}
            status_desc = status_map.get(filters["status"][0], filters["status"][0])
            parts.append(status_desc)

        # Possession filter
        if filters.get("possession_year"):
            parts.append(f"possession {filters['possession_year']}")

        return " ".join(parts) if parts else ""

    def _format_price(self, amount_inr: int) -> str:
        """
        Format price in Indian numbering system.

        Args:
            amount_inr: Amount in INR

        Returns:
            Formatted string like "₹3.0 Cr" or "₹50 Lac"
        """
        if amount_inr >= 10000000:  # Crores (1 crore = 1,00,00,000)
            cr = amount_inr / 10000000
            return f"₹{cr:.1f} Cr"
        elif amount_inr >= 100000:  # Lakhs (1 lakh = 1,00,000)
            lac = amount_inr / 100000
            if lac >= 10:
                return f"₹{lac:.0f} Lac"
            else:
                return f"₹{lac:.1f} Lac"
        else:
            return f"₹{amount_inr:,}"


# Global instance
response_formatter = ResponseFormatter()
