import logging
from typing import Dict, Any, List, Optional
import re

logger = logging.getLogger(__name__)

class SalesFormatter:
    """
    Formatter optimized for Live Sales Calls.
    Focus: Concise, Actionable, Bold Stats, Minimal Junk.
    """

    def format_project_card(self, project: Dict[str, Any], detailed: bool = False) -> str:
        """
        Formats a single project into a high-impact 'Card'.
        Example:
        **Birla Evara** | Under Construction
        📍 Sarjapur Road | 3BHK, 4BHK
        💰 ₹2.20 Cr - ₹2.90 Cr
        """
        name = project.get('name', 'Unknown Project')
        status = project.get('status', 'Status N/A')
        location = project.get('location', 'Loc N/A')
        
        # Format Price
        min_p = project.get('budget_min', 0) / 100
        max_p = project.get('budget_max', 0) / 100
        price_str = f"₹{min_p:.2f} Cr - ₹{max_p:.2f} Cr" if min_p and max_p else "Price on Request"
        
        # Clean Config
        raw_config = str(project.get('configuration', ''))
        # Extract just 2BHK, 3BHK etc
        configs = re.findall(r"(\d+(?:\.\d+)?\s*BHK)", raw_config, re.IGNORECASE)
        config_str = ", ".join(sorted(list(set(configs)))) if configs else "Config N/A"

        # Base Card
        lines = [
            f"**{name}** | {status}",
            f"📍 {location} | {config_str}",
            f"💰 {price_str}"
        ]

        # Add details if requested (pitch mode)
        if detailed:
            # USP/Highlights
            if project.get('usp'):
                lines.append(f"\n✨ **Why this?** {str(project.get('usp')).strip()}")
            
            # Amenities (Top 3)
            amenities = str(project.get('amenities', '')).replace("[", "").replace("]", "").replace("'", "")
            am_list = [a.strip() for a in amenities.split(',') if a.strip()]
            if am_list:
                lines.append(f"🎯 **Amenities**: {', '.join(am_list[:3])} + {len(am_list)-3} more")
            
            # Possession
            lines.append(f"📅 **Possession**: {project.get('possession_quarter', '')} {project.get('possession_year', '')}")
            
            # Actionable Links
            links = []
            if project.get('brochure_url'):
                links.append(f"[📄 Brochure]({project.get('brochure_url')})")
            if project.get('rm_details'):
                links.append(f"📞 RM: {project.get('rm_details')}")
            else:
                 links.append("📞 RM: +91-9988776655")
            
            lines.append(" | ".join(links))

        return "\n".join(lines) + "\n"

    def format_list_response(self, projects: List[Dict[str, Any]], context_msg: str = "") -> str:
        """
        Formats a list of projects.
        """
        if not projects:
            return "No matching projects found."

        parts = []
        if context_msg:
            parts.append(context_msg + "\n")

        for idx, p in enumerate(projects, 1):
            parts.append(f"{idx}. " + self.format_project_card(p, detailed=False))
        
        parts.append("\n👉 *Say 'Details of [Project]' for deeper pitch*")
        return "\n".join(parts)

    def format_pitch_response(self, project: Dict[str, Any]) -> str:
        """
        Detailed pitch for a single project.
        """
        return self.format_project_card(project, detailed=True)

sales_formatter = SalesFormatter()
