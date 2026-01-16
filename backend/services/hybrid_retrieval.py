"""
Hybrid Retrieval Service - Production Version
Queries Pixeltable sales.projects table directly with real data.
No mock data - all responses from actual project database.
"""

from typing import Dict, List, Any, Optional
from services.filter_extractor import PropertyFilters, filter_extractor
from config import settings
import pixeltable as pxt
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Thread pool for Pixeltable queries (avoids uvloop conflict)
_executor = ThreadPoolExecutor(max_workers=4)


class HybridRetrievalService:
    """
    Production retrieval service for sales assistant.
    Queries Pixeltable directly for real project data.
    """

    def __init__(self):
        self.projects_table = None
        self.units_table = None
        self._init_tables()
    
    def _init_tables(self):
        """Initialize Pixeltable table handles."""
        try:
            self.projects_table = pxt.get_table('brigade.projects')
            # Units are embedded in projects table, no separate units table
            self.units_table = None
            logger.info("HybridRetrieval: Connected to Pixeltable brigade.projects table")
        except Exception as e:
            logger.warning(f"Pixeltable tables not available: {e}")
            self.projects_table = None
            self.units_table = None

    async def search_with_filters(
        self,
        query: str,
        filters: Optional[PropertyFilters] = None,
        use_llm_extraction: bool = False
    ) -> Dict[str, Any]:
        """
        Search projects using extracted filters from natural language query.
        Returns real data from Pixeltable.
        """
        logger.info(f"Searching for: {query}")

        # Ensure tables are initialized
        if not self.projects_table:
            self._init_tables()
            if not self.projects_table:
                return {
                    "projects": [],
                    "total_matching_projects": 0,
                    "filters_used": {},
                    "search_method": "error",
                    "error": "Database not available"
                }

        # Extract filters from query
        if filters is None:
            filters = filter_extractor.extract_filters(query)
        
        logger.info(f"Extracted filters: {filters.dict(exclude_none=True)}")

        # Query Pixeltable in thread to avoid uvloop conflict
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(
            _executor,
            self._query_projects_sync,
            filters,
            query
        )
        
        return {
            "projects": results,
            "total_matching_projects": len(results),
            "filters_used": filters.dict(exclude_none=True),
            "search_method": "pixeltable"
        }

    def _query_projects_sync(self, filters: PropertyFilters, query: str) -> List[Dict[str, Any]]:
        """Query Pixeltable projects table with filters (runs in thread)."""
        try:
            projects = self.projects_table
            if projects is None:
                logger.error("Projects table is None - cannot query")
                return []
            
            # First, try to get ALL projects to verify table access
            try:
                all_count = len(projects.collect())
                logger.info(f"Total projects in table: {all_count}")
            except Exception as count_err:
                logger.error(f"Cannot access projects table: {count_err}")
                return []
            
            # Start with all projects - simplified query
            q = projects.select()
            
            # Check if query mentions a specific project or developer
            query_lower = query.lower()
            has_filters = False
            
            # Search by project name (highest priority)
            project_keywords = ['birla', 'brigade', 'prestige', 'evara', 'avalon', 'citrine', 'raintree', 'sobha']
            for keyword in project_keywords:
                if keyword in query_lower:
                    q = q.where(projects.name.contains(keyword.title()) | projects.builder.contains(keyword.title()))
                    has_filters = True
                    logger.info(f"Applied keyword filter: {keyword}")
                    break
            
            # Apply standard filters only if no project-specific search
            if not has_filters:
                # Location/locality filter
                if filters.locality:
                    q = q.where(projects.location.contains(filters.locality))
                    has_filters = True
                    logger.info(f"Applied locality filter: {filters.locality}")
                
                # Budget filter (price in Cr)
                if filters.max_price_inr:
                    max_cr = filters.max_price_inr / 10000000
                    q = q.where(projects.min_price_cr <= max_cr)
                    has_filters = True
                    logger.info(f"Applied max price filter: {max_cr} Cr")
                
                if filters.min_price_inr:
                    min_cr = filters.min_price_inr / 10000000
                    q = q.where(projects.max_price_cr >= min_cr)
                    has_filters = True
                    logger.info(f"Applied min price filter: {min_cr} Cr")
                
                # Developer filter
                if filters.developer_name:
                    q = q.where(projects.builder.contains(filters.developer_name))
                    has_filters = True
                    logger.info(f"Applied developer filter: {filters.developer_name}")
            
            # Execute query
            results = q.collect()
            logger.info(f"Query returned {len(results)} results, has_filters={has_filters}")
            
            # If no results with filters but we have projects, return all projects
            if len(results) == 0 and all_count > 0 and has_filters:
                logger.info("No filtered results, returning all projects")
                results = projects.collect()
            
            # Format results
            formatted = []
            for r in results:
                try:
                    formatted.append({
                        "project_id": r.get('project_id', ''),
                        "project_name": r.get('name', ''),
                        "developer_name": r.get('builder', ''),
                        "location": r.get('location', ''),
                        "city": r.get('city', ''),
                        "locality": r.get('location', ''),
                        "status": r.get('status', ''),
                        "possession_year": r.get('possession_year'),
                        "total_land_area": r.get('total_land_area', ''),
                        "towers": r.get('towers', ''),
                        "floors": r.get('floors', ''),
                        "amenities": r.get('amenities', ''),
                        "highlights": r.get('highlights', ''),
                        "brochure_link": r.get('brochure_link', ''),
                        "rm_contact": r.get('rm_contact', ''),
                        "location_link": r.get('location_link', ''),
                        "config_summary": r.get('config_summary', ''),
                        "price_range": {
                            "min": r.get('min_price_cr'),
                            "max": r.get('max_price_cr'),
                            "min_display": f"₹{r.get('min_price_cr', 0):.2f} Cr" if r.get('min_price_cr') else "TBD",
                            "max_display": f"₹{r.get('max_price_cr', 0):.2f} Cr" if r.get('max_price_cr') else "TBD"
                        },
                        "matching_units": [],
                        "unit_count": 0,
                        "can_expand": False,
                        "relevant_chunks": []
                    })
                except Exception as format_err:
                    logger.error(f"Error formatting project: {format_err}")
                    continue
            
            logger.info(f"Found {len(formatted)} matching projects")
            return formatted
            
        except Exception as e:
            logger.error(f"Error querying projects: {e}", exc_info=True)
            return []

    def _get_project_units(self, project_id: str, bhk_filter: List[int] = None) -> List[Dict[str, Any]]:
        """Get units for a specific project."""
        try:
            if not self.units_table:
                return []
            
            units = self.units_table
            q = units.where(units.project_id == project_id).select(
                units.unit_id,
                units.bhk,
                units.min_sqft,
                units.max_sqft,
                units.price_cr,
                units.price_inr
            )
            
            results = q.collect()
            
            formatted = []
            for r in results:
                # Apply BHK filter if specified
                if bhk_filter and r['bhk'] not in bhk_filter:
                    continue
                
                area_str = f"{r['min_sqft']}"
                if r['max_sqft'] and r['max_sqft'] != r['min_sqft']:
                    area_str = f"{r['min_sqft']} - {r['max_sqft']}"
                
                formatted.append({
                    "unit_id": r['unit_id'],
                    "type_name": f"{r['bhk']} BHK",
                    "bedrooms": r['bhk'],
                    "price_display": f"₹{r['price_cr']:.2f} Cr",
                    "price_inr": r['price_inr'],
                    "carpet_area_sqft": r['min_sqft'],
                    "area_display": f"{area_str} sqft",
                    "available_units": 10  # Default
                })
            
            return formatted
            
        except Exception as e:
            logger.error(f"Error getting units: {e}")
            return []

    def _format_indian_currency(self, amount_inr: Optional[int]) -> str:
        """Format INR amount in Indian numbering system."""
        if amount_inr is None or amount_inr == 0:
            return "Price on request"

        if amount_inr >= 10000000:
            cr = amount_inr / 10000000
            return f"₹{cr:.2f} Cr"
        elif amount_inr >= 100000:
            lac = amount_inr / 100000
            return f"₹{lac:.2f} Lac"
        else:
            return f"₹{amount_inr:,}"


# Global instance
hybrid_retrieval = HybridRetrievalService()
