"""
Response formatting service for sales-optimized output.
Formats property search results with EMI, pitch points, and sales tools.
"""

from typing import Dict, List, Any, Literal, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Import sales intelligence for EMI calculation
try:
    from services.sales_intelligence import sales_intelligence
except ImportError:
    sales_intelligence = None

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
        Format property search results as rich sales cards.
        Includes amenities, highlights, possession, and CTA.
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

        # Format each project as a rich sales card
        for idx, project in enumerate(projects[:3], 1):
            answer += f"**{idx}. {project['project_name']}**"
            if project.get('developer_name'):
                answer += f" by {project['developer_name']}"
            answer += "\n"

            # Location with link if available
            loc = project.get('location') or project.get('city', '')
            if loc:
                answer += f"📍 {loc}"
                if project.get('total_land_area'):
                    answer += f" | {project['total_land_area']}"
                answer += "\n"

            # Price range with EMI
            if project.get('price_range'):
                price_range = project['price_range']
                answer += f"💰 {price_range['min_display']} - {price_range['max_display']}"
                
                # Calculate EMI for minimum price
                min_price = price_range.get('min', 0)
                if min_price and min_price > 0 and sales_intelligence:
                    try:
                        emi_info = sales_intelligence.calculate_emi(int(min_price * 10000000))
                        answer += f" | EMI: **{emi_info['emi_display']}**"
                    except:
                        pass
                answer += "\n"

            # Possession timeline
            if project.get('possession_year'):
                answer += f"📅 Possession: {project['possession_year']}\n"

            # Config & status
            if project.get('config_summary'):
                answer += f"🏗️ {project['config_summary']}"
                if project.get('status'):
                    answer += f" | {project['status']}"
                answer += "\n"

            # Show sample units
            sample_units = project.get('matching_units', [])
            unit_count = project.get('unit_count', len(sample_units))
            for unit in sample_units[:2]:
                unit_line = f"  • {unit.get('type_name', str(unit.get('bedrooms', '?')) + 'BHK')}"
                if unit.get('price_display'):
                    unit_line += f": {unit['price_display']}"
                if unit.get('carpet_area_sqft') or unit.get('area_display'):
                    area = unit.get('area_display') or f"{unit.get('carpet_area_sqft')} sqft"
                    unit_line += f" | {area}"
                answer += unit_line + "\n"

            if unit_count > 2:
                answer += f"  ➕ *+{unit_count - 2} more units*\n"

            # KEY HIGHLIGHTS for sales pitch
            if project.get('highlights'):
                highlights = project['highlights'][:200]  # Truncate long text
                if highlights:
                    answer += f"\n✨ **Pitch Points:** {highlights}\n"

            # AMENITIES summary
            if project.get('amenities'):
                amenities = project['amenities'][:150]  # Truncate
                if amenities:
                    answer += f"🎯 **Amenities:** {amenities}\n"

            # SALES ACTION - RM Contact & Brochure
            answer += "\n📞 **Quick Actions:**\n"
            if project.get('rm_contact'):
                answer += f"  • Call RM: {project['rm_contact']}\n"
            if project.get('brochure_link'):
                answer += f"  • [Download Brochure]({project['brochure_link']})\n"
            if project.get('location_link'):
                answer += f"  • [View on Map]({project['location_link']})\n"

            answer += "\n---\n\n"

        # CTA at the end
        answer += "🤝 **Ready to help!** Would you like me to:\n"
        answer += "• Schedule a **site visit** for any project?\n"
        answer += "• Arrange a **meeting** with our sales team?\n"
        answer += "• Get **detailed pricing** for a specific unit?\n"

        return FormattedResponse(
            format_type="structured_list",
            answer=answer,
            structured_data={
                "projects": projects,
                "total_count": project_count,
                "filters_applied": filters
            },
            sources=[],
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
