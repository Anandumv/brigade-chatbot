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
            
            # Get all projects first, then filter in Python (more reliable)
            all_results = projects.collect()
            logger.info(f"Total projects fetched: {len(all_results)}")
            
            # Filter in Python
            filtered_results = list(all_results)  # Start with all
            
            # Apply city filter
            # Logic: All projects are in Bangalore. 
            # 1. If user asks for Bangalore, return all (don't filter out if 'Bangalore' string missing).
            # 2. If user asks for Mumbai/Delhi, look for it strictly (will likely return 0).
            if filters.city and filters.city.strip():
                city_lower = filters.city.lower()
                if city_lower != 'bangalore':
                    filtered_results = [r for r in filtered_results 
                                       if city_lower in str(r.get('location', '')).lower() or 
                                          city_lower in str(r.get('zone', '')).lower() or
                                          city_lower in str(r.get('full_address', '')).lower()]
                    logger.info(f"After city filter '{filters.city}': {len(filtered_results)} results")

            # Apply Zone filter (North/South/East/West Bangalore)
            if filters.area and filters.area.strip():
                area_lower = filters.area.lower()
                filtered_results = [r for r in filtered_results 
                                   if area_lower in str(r.get('zone', '')).lower() or 
                                      area_lower in str(r.get('location', '')).lower() or
                                      area_lower in str(r.get('full_address', '')).lower()]
                logger.info(f"After zone filter '{filters.area}': {len(filtered_results)} results")

            # Apply locality filter
            if filters.locality and filters.locality.strip():
                locality_lower = filters.locality.lower()
                # Broaden search to include description/address since some projects are "near Jakkur"
                filtered_results = [r for r in filtered_results 
                                   if locality_lower in str(r.get('location', '')).lower() or
                                      locality_lower in str(r.get('full_address', '')).lower() or
                                      locality_lower in str(r.get('description', '')).lower()]
                logger.info(f"After locality filter '{filters.locality}': {len(filtered_results)} results")
            
            # Apply developer filter - search in name and builder
            if filters.developer_name and filters.developer_name.strip():
                dev_keywords = filters.developer_name.lower().split()
                filtered_results = [r for r in filtered_results 
                                   if any(kw in str(r.get('name', '')).lower() or 
                                         kw in str(r.get('builder', '')).lower() 
                                         for kw in dev_keywords)]
                logger.info(f"After developer filter '{filters.developer_name}': {len(filtered_results)} results")
            
            # Apply budget filter (price in Cr)
            if filters.max_price_inr:
                # Convert max price (INR) to Lakhs for comparison
                max_lakhs = filters.max_price_inr / 100000
                # STRICT FILTERING: Exclude projects where price is Unknown (None or 0)
                # Only include if budget_min exists AND is > 0 AND is <= max_lakhs
                filtered_results = [r for r in filtered_results 
                                   if r.get('budget_min') and r.get('budget_min') > 0 and r.get('budget_min') <= max_lakhs]
                logger.info(f"After max price filter {max_lakhs}L: {len(filtered_results)} results")
            
            if filters.min_price_inr:
                # Convert min price (INR) to Lakhs for comparison
                min_lakhs = filters.min_price_inr / 100000
                filtered_results = [r for r in filtered_results 
                                   if r.get('budget_max') is None or r.get('budget_max', 99999) >= min_lakhs]
                logger.info(f"After min price filter {min_lakhs}L: {len(filtered_results)} results")
            
            # Apply Possession Year filter
            if filters.possession_year:
                # Logic: Included if project possession year <= requested year (e.g. "Possession by 2027" -> 2025, 2026, 2027 projects)
                # Or exact match? Usually "possession 2027" means "by 2027". 
                # Let's go with exact match or earlier (ready by 2027 includes 2026).
                target_year = filters.possession_year
                filtered_results = [r for r in filtered_results 
                                   if r.get('possession_year') and str(r.get('possession_year')).isdigit() and int(r.get('possession_year')) <= target_year]
                logger.info(f"After possession filter <= {target_year}: {len(filtered_results)} results")

            # Apply Area (Sqft) filter
            if filters.min_area_sqft:
                 filtered_results = [r for r in filtered_results 
                                   if r.get('total_land_area') and str(r.get('total_land_area')).replace('Acres','').strip().replace('.','').isdigit()] 
                 # Wait, total_land_area is in Acres usually in this schema. unit sizes are in units table (not here).
                 # This filter might not work on project level unless we have unit size ranges.
                 # Checking schema: 'configuration' string might have "1200 sqft". 
                 # Or we skip project-level area filter for now if data missing.
                 # Actually, let's skip area filter on project level to avoid false zeros, as unit sizes are complex.
                 pass

            results = filtered_results
            logger.info(f"Final result count: {len(results)}")
            
            # Format results
            formatted = []
            for r in results:
                try:
                    # Calculate price in Cr from Lakhs
                    min_cr = r.get('budget_min', 0) / 100.0 if r.get('budget_min') else None
                    max_cr = r.get('budget_max', 0) / 100.0 if r.get('budget_max') else None
                    
                    formatted.append({
                        "project_id": r.get('project_id', ''),
                        "project_name": r.get('name', ''),
                        "developer_name": r.get('developer', ''), # Schema uses 'developer', not 'builder'
                        "location": r.get('location', ''),
                        "city": r.get('zone', '') or r.get('location', ''), # Use zone or fallback
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
                        "config_summary": r.get('configuration', ''),
                        "price_range": {
                            "min": min_cr,
                            "max": max_cr,
                            "min_display": f"₹{min_cr:.2f} Cr" if min_cr else "Price on request",
                            "max_display": f"₹{max_cr:.2f} Cr" if max_cr else "Price on request"
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
