"""
Project Data Enrichment Service
Enriches project data with GPT when information is missing from database.
ONLY enriches projects that exist in the database - never creates new projects.
"""

import logging
from typing import Dict, List, Any, Optional
from openai import OpenAI
from config import settings
from services.sales_agent_prompt import SALES_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url
)


class ProjectEnrichmentService:
    """
    Service to enrich project data with GPT-generated information.
    Only enriches projects verified to exist in database.
    """
    
    def __init__(self):
        pass
    
    async def enrich_project(
        self,
        project: Dict[str, Any],
        enrichment_types: List[str],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enrich project with GPT-generated information.
        Only enriches projects verified to exist in database.
        
        Args:
            project: Project dictionary from database
            enrichment_types: List of types to enrich ["amenities", "nearby_places", "connectivity"]
            query: Optional user query for context
        
        Returns:
            Enriched project dictionary
        """
        # Verify project exists (has required fields)
        if not project.get('name') or not project.get('location'):
            logger.warning(f"Cannot enrich project without name/location: {project}")
            return project
        
        enriched = project.copy()
        
        for enrichment_type in enrichment_types:
            try:
                if enrichment_type == "amenities":
                    enriched = await self._enrich_amenities(enriched, query)
                elif enrichment_type == "nearby_places":
                    enriched = await self._enrich_nearby_places(enriched, query)
                elif enrichment_type == "connectivity":
                    enriched = await self._enrich_connectivity(enriched, query)
                elif enrichment_type == "neighborhood_info":
                    enriched = await self._enrich_neighborhood(enriched, query)
                else:
                    logger.warning(f"Unknown enrichment type: {enrichment_type}")
            except Exception as e:
                logger.error(f"Error enriching {enrichment_type} for {project.get('name')}: {e}")
                # Continue with other enrichments even if one fails
        
        return enriched
    
    async def _enrich_amenities(
        self,
        project: Dict[str, Any],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enrich amenities information using GPT."""
        
        # If amenities already exist and are detailed, skip
        existing_amenities = project.get('amenities', '')
        if existing_amenities and len(existing_amenities) > 50:
            return project
        
        project_name = project.get('name', '')
        location = project.get('location', '')
        configuration = project.get('configuration', '')
        budget_min = project.get('budget_min', 0) / 100 if project.get('budget_min') else 0
        
        prompt = f"""Generate relevant amenities for a real estate project.

Project: {project_name}
Location: {location}
Configuration: {configuration}
Price Range: ₹{budget_min:.2f} Cr onwards

Generate 5-8 relevant amenities that would be appropriate for this project type and location.
Format as bullet points (•), each ≤ 1 line, actionable.

Example format:
• Swimming pool
• Gymnasium
• Children's play area
• Clubhouse
• Landscaped gardens"""

        try:
            response = client.chat.completions.create(
                model=settings.effective_gpt_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""{SALES_AGENT_SYSTEM_PROMPT}

⸻

TASK: Generate amenities for a real estate project.
- Bullet points only (•)
- Each bullet ≤ 1 line
- Relevant to project type and location
- No marketing fluff"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            amenities = response.choices[0].message.content.strip()
            project['amenities'] = amenities
            logger.info(f"Enriched amenities for {project_name}")
            
        except Exception as e:
            logger.error(f"Error enriching amenities: {e}")
        
        return project
    
    async def _enrich_nearby_places(
        self,
        project: Dict[str, Any],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enrich nearby places information using GPT."""
        
        project_name = project.get('name', '')
        location = project.get('location', '')
        
        prompt = f"""List nearby places and landmarks for this real estate project.

Project: {project_name}
Location: {location}

Generate 4-6 nearby places (schools, hospitals, malls, IT parks, metro stations, etc.)
Format as bullet points (•), each ≤ 1 line with distance if possible.

Example format:
• Whitefield Metro Station (2 km)
• Phoenix Mall (3 km)
• International School (1.5 km)"""

        try:
            response = client.chat.completions.create(
                model=settings.effective_gpt_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""{SALES_AGENT_SYSTEM_PROMPT}

⸻

TASK: Generate nearby places for a real estate project.
- Bullet points only (•)
- Each bullet ≤ 1 line with distance
- Focus on schools, hospitals, malls, connectivity
- No marketing fluff"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            nearby_places = response.choices[0].message.content.strip()
            project['nearby_places'] = nearby_places
            logger.info(f"Enriched nearby places for {project_name}")
            
        except Exception as e:
            logger.error(f"Error enriching nearby places: {e}")
        
        return project
    
    async def _enrich_connectivity(
        self,
        project: Dict[str, Any],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enrich connectivity information using GPT."""
        
        project_name = project.get('name', '')
        location = project.get('location', '')
        
        prompt = f"""Describe connectivity advantages for this real estate project.

Project: {project_name}
Location: {location}

Generate 3-5 connectivity points (metro, highways, airport, IT corridors, etc.)
Format as bullet points (•), each ≤ 1 line with distance/time.

Example format:
• 5 mins from ORR
• 15 mins to Whitefield IT Park
• 30 mins to Airport"""

        try:
            response = client.chat.completions.create(
                model=settings.effective_gpt_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""{SALES_AGENT_SYSTEM_PROMPT}

⸻

TASK: Generate connectivity information for a real estate project.
- Bullet points only (•)
- Each bullet ≤ 1 line with distance/time
- Focus on metro, highways, IT parks, airport
- No marketing fluff"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            connectivity = response.choices[0].message.content.strip()
            project['connectivity'] = connectivity
            logger.info(f"Enriched connectivity for {project_name}")
            
        except Exception as e:
            logger.error(f"Error enriching connectivity: {e}")
        
        return project
    
    async def _enrich_neighborhood(
        self,
        project: Dict[str, Any],
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enrich neighborhood information using GPT."""
        
        project_name = project.get('name', '')
        location = project.get('location', '')
        
        prompt = f"""Describe the neighborhood and area advantages for this real estate project.

Project: {project_name}
Location: {location}

Generate 3-4 neighborhood insights (emerging area, infrastructure, growth potential, etc.)
Format as bullet points (•), each ≤ 1 line.

Example format:
• Emerging residential hub with new infrastructure
• Close to IT corridor with high rental demand
• Well-planned layout with good connectivity"""

        try:
            response = client.chat.completions.create(
                model=settings.effective_gpt_model,
                messages=[
                    {
                        "role": "system",
                        "content": f"""{SALES_AGENT_SYSTEM_PROMPT}

⸻

TASK: Generate neighborhood insights for a real estate project.
- Bullet points only (•)
- Each bullet ≤ 1 line
- Focus on area growth, infrastructure, investment potential
- No marketing fluff"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=200
            )
            
            neighborhood = response.choices[0].message.content.strip()
            project['neighborhood_info'] = neighborhood
            logger.info(f"Enriched neighborhood info for {project_name}")
            
        except Exception as e:
            logger.error(f"Error enriching neighborhood: {e}")
        
        return project


# Global instance
project_enrichment = ProjectEnrichmentService()
