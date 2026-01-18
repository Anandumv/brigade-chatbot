"""
Intelligent Fallback Service
Provides nearby budget-friendly alternatives when no exact matches are found.
Uses location proximity and value-focused sales pitches.
"""

from typing import Dict, List, Any, Optional, Tuple
from services.filter_extractor import PropertyFilters
from services.hybrid_retrieval import hybrid_retrieval
from utils.geolocation_utils import get_coordinates, calculate_distance
from openai import OpenAI
from config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url
)


class IntelligentFallbackService:
    """
    Service to find and present intelligent alternatives when no exact matches exist.
    Focus: Nearby locations + budget-friendly options with compelling sales pitches.
    """
    
    def __init__(self):
        self.max_radius_km = 10.0  # Default search within 10km
        self.max_alternatives = 3   # Return up to 3 alternatives
        
    async def find_intelligent_alternatives(
        self,
        filters: PropertyFilters,
        original_query: str,
        max_results: int = 3,
        aggressive_mode: bool = False
    ) -> Dict[str, Any]:
        """
        Find intelligent alternatives when no exact match exists.
        
        Strategy:
        1. Find projects within radius (10km default, 20km in aggressive mode)
        2. Filter by budget (affordable or slightly above, wider range in aggressive mode)
        3. Rank by budget fit, proximity, and configuration match
        4. Generate value-focused sales pitches
        
        Args:
            filters: PropertyFilters with search criteria
            original_query: Original user query
            max_results: Maximum number of alternatives to return
            aggressive_mode: If True, expand radius to 20km and budget range to 2x
        
        Returns:
            Dict with: alternatives (list), answer (string with pitches), projects (list), sources (list)
        """
        try:
            logger.info(f"Finding intelligent alternatives for: {original_query} (aggressive_mode={aggressive_mode})")
            logger.info(f"Filters: {filters.model_dump(exclude_none=True)}")
            
            # Step 1: Extract location and get coordinates
            location_name = self._extract_location(filters)
            if not location_name:
                logger.info("No location specified, cannot find alternatives")
                return self._empty_response()
            
            center_coords = get_coordinates(location_name)
            if not center_coords:
                logger.info(f"Could not geocode location: {location_name}")
                return self._empty_response()
            
            # Step 2: Get projects within radius (expand in aggressive mode)
            search_radius = 20.0 if aggressive_mode else self.max_radius_km
            logger.info(f"Searching within {search_radius}km radius")
            nearby_projects = await hybrid_retrieval.get_projects_within_radius(
                location_name=location_name,
                radius_km=search_radius
            )
            
            if not nearby_projects:
                logger.info(f"No projects found within {self.max_radius_km}km of {location_name}")
                return self._empty_response()
            
            logger.info(f"Found {len(nearby_projects)} projects within radius")
            
            # Step 3: Filter by budget (wider range in aggressive mode)
            affordable_projects = self._filter_by_budget(nearby_projects, filters, aggressive_mode=aggressive_mode)
            logger.info(f"After budget filter: {len(affordable_projects)} projects")
            
            if not affordable_projects:
                logger.info("No affordable alternatives found")
                return self._empty_response()
            
            # Step 3.5: SALES LOGIC - Add better-value configurations (N+1 BHK if within budget)
            if filters.bedrooms:
                better_value_projects = self._add_better_value_configurations(
                    all_projects=affordable_projects,
                    requested_bedrooms=filters.bedrooms,
                    max_budget_lakhs=filters.max_price_inr / 100000 if filters.max_price_inr else None
                )
                
                # Combine affordable and better-value, avoiding duplicates
                seen_ids = {p.get('project_id') or p.get('name') for p in affordable_projects}
                for bv in better_value_projects:
                    bv_id = bv.get('project_id') or bv.get('name')
                    if bv_id not in seen_ids:
                        bv['_better_value'] = True
                        affordable_projects.append(bv)
                        seen_ids.add(bv_id)
                
                logger.info(f"After better-value addition: {len(affordable_projects)} projects")
            
            # Step 4: Rank and select top alternatives
            ranked_projects = self._rank_alternatives(affordable_projects, filters, center_coords)
            top_alternatives = ranked_projects[:max_results]
            
            logger.info(f"Returning {len(top_alternatives)} alternatives")
            
            # Step 5: Generate value-focused sales pitches
            answer = await self._generate_answer_with_pitches(
                original_query=original_query,
                alternatives=top_alternatives,
                filters=filters,
                location_name=location_name
            )
            
            # Step 6: Format response
            return {
                "alternatives": top_alternatives,
                "answer": answer,
                "projects": self._format_projects(top_alternatives),
                "sources": self._create_sources(top_alternatives)
            }
            
        except Exception as e:
            logger.error(f"Error in intelligent fallback: {e}", exc_info=True)
            return self._empty_response()
    
    def _extract_location(self, filters: PropertyFilters) -> Optional[str]:
        """Extract location name from filters."""
        # Priority: locality > area > city
        if filters.locality:
            return filters.locality
        if filters.area:
            return filters.area
        if filters.city:
            return filters.city
        return None
    
    def _filter_by_budget(
        self,
        projects: List[Dict[str, Any]],
        filters: PropertyFilters,
        aggressive_mode: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Filter projects by budget - prioritize affordable options but also include
        slightly above budget options if no affordable ones exist.
        
        In aggressive_mode:
        - Shows properties from 0.5x to 2x requested budget
        - Prioritizes showing something over nothing
        """
        affordable = []
        slightly_above = []
        wider_range = []
        
        # Extract requested budget (in lakhs)
        requested_budget_lakhs = None
        if filters.max_price_inr:
            requested_budget_lakhs = filters.max_price_inr / 100000  # Convert INR to lakhs
        elif filters.budget_inr:
            requested_budget_lakhs = filters.budget_inr / 100000
        
        for project in projects:
            budget_min = project.get('budget_min', 0)  # Already in lakhs
            
            if not budget_min or budget_min <= 0:
                # Skip projects with no price info
                continue
            
            if requested_budget_lakhs:
                if budget_min <= requested_budget_lakhs:
                    affordable.append(project)
                elif budget_min <= requested_budget_lakhs * 1.5:
                    # Include projects up to 50% above budget as "slightly above"
                    slightly_above.append(project)
                elif aggressive_mode and budget_min <= requested_budget_lakhs * 2.0:
                    # In aggressive mode, include up to 2x budget
                    wider_range.append(project)
                
                # In aggressive mode, also include properties slightly below budget
                # (if user asked for "under 70 lacs", show 50-70 lacs range too)
                if aggressive_mode and budget_min >= requested_budget_lakhs * 0.5 and budget_min < requested_budget_lakhs:
                    if project not in affordable:
                        affordable.append(project)
            else:
                # No budget specified, include all
                affordable.append(project)
        
        # Priority: affordable > slightly_above > wider_range (aggressive mode only)
        if affordable:
            return affordable
        
        if slightly_above:
            logger.info(f"No affordable alternatives, showing {len(slightly_above)} slightly above budget")
            return slightly_above
        
        if aggressive_mode and wider_range:
            logger.info(f"No affordable or slightly above alternatives, showing {len(wider_range)} in wider range (up to 2x budget)")
            return wider_range
        
        return []
    
    def _rank_alternatives(
        self,
        projects: List[Dict[str, Any]],
        filters: PropertyFilters,
        center_coords: Tuple[float, float]
    ) -> List[Dict[str, Any]]:
        """
        Rank alternatives by: budget fit (40%) + proximity (40%) + configuration match (20%).
        """
        scored_projects = []
        
        for project in projects:
            score = self._calculate_score(project, filters, center_coords)
            project['_score'] = score
            scored_projects.append(project)
        
        # Sort by score (higher is better)
        scored_projects.sort(key=lambda x: x.get('_score', 0), reverse=True)
        
        return scored_projects
    
    def _add_better_value_configurations(
        self,
        all_projects: List[Dict[str, Any]],
        requested_bedrooms: List[int],
        max_budget_lakhs: Optional[float]
    ) -> List[Dict[str, Any]]:
        """
        Add (N+1) BHK options if they fit within budget.
        Sales logic: Show better value when available.
        """
        better_value = []
        
        def normalize(s):
            return str(s).lower().strip() if s else ""
        
        for req_bhk in requested_bedrooms:
            next_bhk = req_bhk + 1
            
            for project in all_projects:
                # Check if project has (N+1) BHK configuration
                conf = normalize(project.get('configuration', ''))
                has_next_bhk = f"{next_bhk}" in conf
                
                if not has_next_bhk:
                    continue
                
                # Check if it fits within budget
                budget_min = project.get('budget_min', 0)
                if budget_min and budget_min > 0:
                    if max_budget_lakhs is None or budget_min <= max_budget_lakhs:
                        # This is a better-value option
                        better_value.append(project)
        
        logger.info(f"Found {len(better_value)} better-value configurations in fallback")
        return better_value

    def _calculate_score(
        self,
        project: Dict[str, Any],
        filters: PropertyFilters,
        center_coords: Tuple[float, float]
    ) -> float:
        """Calculate ranking score for a project."""
        score = 0.0
        
        # Budget fit score (40 points max)
        # Lower budget = higher score (better value)
        requested_budget_lakhs = None
        if filters.max_price_inr:
            requested_budget_lakhs = filters.max_price_inr / 100000
        elif filters.budget_inr:
            requested_budget_lakhs = filters.budget_inr / 100000
        
        if requested_budget_lakhs:
            budget_min = project.get('budget_min', 0)
            if budget_min > 0:
                # Score inversely proportional to price
                budget_ratio = budget_min / requested_budget_lakhs
                if budget_ratio <= 1.0:
                    score += 40 * (1.0 - budget_ratio)  # Cheaper = better score
        else:
            score += 20  # No budget filter = moderate score
        
        # Proximity score (40 points max)
        distance = project.get('_distance', 999)
        if distance <= self.max_radius_km:
            # Closer = higher score
            proximity_score = 40 * (1.0 - (distance / self.max_radius_km))
            score += proximity_score
        
        # Configuration match score (20 points max)
        if filters.bedrooms:
            project_config = project.get('configuration', '').lower()
            for bedroom_count in filters.bedrooms:
                if f"{bedroom_count}bhk" in project_config or f"{bedroom_count} bhk" in project_config:
                    score += 20
                    break
        else:
            score += 10  # No config filter = moderate score
        
        return score
    
    async def _generate_answer_with_pitches(
        self,
        original_query: str,
        alternatives: List[Dict[str, Any]],
        filters: PropertyFilters,
        location_name: str
    ) -> str:
        """
        Generate comprehensive answer with value-focused sales pitches for each alternative.
        """
        # Build context for LLM
        context_parts = [
            f"Customer searched for: {original_query}",
            f"No exact matches found in {location_name}.",
            f"\nAlternatives found ({len(alternatives)} nearby projects):\n"
        ]
        
        for idx, project in enumerate(alternatives, 1):
            budget_min = project.get('budget_min', 0) / 100  # Convert lakhs to Cr
            budget_max = project.get('budget_max', 0) / 100
            distance = project.get('_distance', 'N/A')
            
            context_parts.append(f"""
{idx}. {project.get('name')}
   - Location: {project.get('location')} ({distance} km from {location_name})
   - Budget: ₹{budget_min:.2f} - ₹{budget_max:.2f} Cr
   - Configuration: {project.get('configuration', 'N/A')}
   - Amenities: {project.get('amenities', 'N/A')}
   - USP: {project.get('usp', 'N/A')}
   - Status: {project.get('status')}
   - Possession: {project.get('possession_quarter')} {project.get('possession_year')}
""")
        
        # Calculate budget savings if applicable
        requested_budget_lakhs = None
        if filters.max_price_inr:
            requested_budget_lakhs = filters.max_price_inr / 100000
        elif filters.budget_inr:
            requested_budget_lakhs = filters.budget_inr / 100000
        
        budget_context = ""
        if requested_budget_lakhs:
            budget_context = f"\nCustomer's budget: Up to ₹{requested_budget_lakhs} Lakhs"
        
        context = "".join(context_parts) + budget_context
        
        # Generate sales pitch using LLM
        prompt = f"""You are a professional real estate sales consultant. Generate a compelling response for a customer whose search didn't match exactly, but we have great alternatives.

{context}

Generate a response that:
1. Opens with empathy ("While we don't have exact matches in {location_name}...")
2. Introduces alternatives positively ("...here are 3 excellent nearby options that offer great value:")
3. For EACH alternative, write **Why consider this:** as 2-4 **bullet points**. **Bold** project name, price, key benefit. No paragraphs.

Format as:
🏠 **[Project Name]** ([distance] km from {location_name})
📍 [Location]
💰 Starting at ₹[price] ([configuration])

**Why consider this:**
• [Bullet 1 – **bold** main point]
• [Bullet 2 – **bold** key benefit]
• [Bullet 3 – value/proximity]

---

**FORMATTING: For sales people on calls. Use bullets (•) for every point. Bold main points. No long sentences.**

Use emojis, be enthusiastic but professional. End with: "Would you like to schedule a site visit to any of these projects?"

Focus on VALUE and BENEFITS. No paragraphs."""

        try:
            response = client.chat.completions.create(
                model=settings.effective_gpt_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are Pinclick Genie, an expert real estate sales consultant. Your goal is to present alternatives persuasively while being honest about why the exact match wasn't available."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,  # Slightly higher for engaging sales language
                max_tokens=800
            )
            
            answer = response.choices[0].message.content
            return answer
            
        except Exception as e:
            logger.error(f"Error generating pitch: {e}")
            # Fallback to template
            return self._template_answer(original_query, alternatives, location_name)
    
    def _template_answer(
        self,
        original_query: str,
        alternatives: List[Dict[str, Any]],
        location_name: str
    ) -> str:
        """Fallback template if LLM fails."""
        lines = [
            f"• 🔍 No exact matches for '{original_query}' in **{location_name}**; here are {len(alternatives)} excellent alternatives:\n"
        ]
        
        for idx, project in enumerate(alternatives, 1):
            budget_min = project.get('budget_min', 0) / 100
            distance = project.get('_distance', 'N/A')
            
            lines.append(f"\n{idx}. 🏠 **{project.get('name')}** ({distance} km away)")
            lines.append(f"   • 📍 {project.get('location')}")
            lines.append(f"   • 💰 Starting at **₹{budget_min:.2f} Cr**")
            lines.append(f"   • 🏗️ {project.get('status')} | Possession: {project.get('possession_quarter')} {project.get('possession_year')}\n")
        
        lines.append("\n• Would you like more details or a **site visit** for any of these? 📞")
        
        return "".join(lines)
    
    def _format_projects(self, alternatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Format projects for frontend display."""
        formatted = []
        
        for project in alternatives:
            formatted.append({
                "project_id": project.get('project_id'),
                "project_name": project.get('name'),
                "name": project.get('name'),
                "developer": project.get('developer'),
                "developer_name": project.get('developer'),
                "location": project.get('location'),
                "zone": project.get('zone'),
                "configuration": project.get('configuration'),
                "config_summary": project.get('configuration'),
                "budget_min": project.get('budget_min'),
                "budget_max": project.get('budget_max'),
                "price_range": f"₹{project.get('budget_min', 0)/100:.2f} - ₹{project.get('budget_max', 0)/100:.2f} Cr",
                "possession_year": project.get('possession_year'),
                "possession_quarter": project.get('possession_quarter'),
                "status": project.get('status'),
                "rera_number": project.get('rera_number'),
                "description": project.get('description'),
                "amenities": project.get('amenities'),
                "usp": project.get('usp'),
                "brochure_url": project.get('brochure_url'),
                "brochure_link": project.get('brochure_url'),
                "rm_details": project.get('rm_details', {}),
                "rm_contact": project.get('rm_details', {}).get('contact', ''),
                "registration_process": project.get('registration_process', ''),
                "total_land_area": project.get('total_land_area', ''),
                "towers": project.get('towers', ''),
                "floors": project.get('floors', ''),
                "location_link": project.get('location_link', ''),
                "can_expand": True,
                "_distance": project.get('_distance'),  # Include distance for reference
                "_score": project.get('_score')  # Include score for debugging
            })
        
        return formatted
    
    def _create_sources(self, alternatives: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create source references for alternatives."""
        sources = []
        
        for project in alternatives:
            sources.append({
                "document": f"{project.get('name')} Project Data",
                "section": "Alternative Suggestions",
                "page": None,
                "excerpt": f"Located in {project.get('location')}, starting at ₹{project.get('budget_min', 0)/100:.2f} Cr",
                "similarity": 0.7  # Medium confidence for alternatives
            })
        
        return sources
    
    def _empty_response(self) -> Dict[str, Any]:
        """Return empty response when no alternatives found."""
        return {
            "alternatives": [],
            "answer": "",
            "projects": [],
            "sources": []
        }


# Global instance
intelligent_fallback = IntelligentFallbackService()
