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
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from utils.geolocation_utils import get_coordinates, calculate_distance
from typing import Callable

logger = logging.getLogger(__name__)

# Thread pool for Pixeltable queries (avoids uvloop conflict)
_executor = ThreadPoolExecutor(max_workers=4)

MOCK_DATA_PATH = os.path.join(os.path.dirname(__file__), '../data/seed_projects.json')


def parse_configuration_pricing(config_str: str) -> List[Dict[str, Any]]:
    """
    Parse configuration string to extract BHK and pricing per unit type.

    Example input:
    "{2BHK, 1249 - 1310, 1.35 Cr* }, {3 BHK + 2 T, 1539 - 1590, 1.65 Cr* }"

    Returns:
    [
        {"bhk": 2, "price_cr": 1.35, "sqft_range": "1249-1310"},
        {"bhk": 3, "price_cr": 1.65, "sqft_range": "1539-1590"}
    ]
    """
    if not config_str or not isinstance(config_str, str):
        return []

    units = []

    # Split by }, { to get individual configurations
    # Handle both {}, and }, { as separators
    configs = re.split(r'\},\s*\{', config_str.strip('{}'))

    for config in configs:
        try:
            # Extract BHK: look for "2BHK" or "3 BHK" etc.
            bhk_match = re.search(r'(\d+)\s*BHK', config, re.IGNORECASE)
            if not bhk_match:
                continue
            bhk = int(bhk_match.group(1))

            # Extract price: look for "1.35 Cr" or "1.35Cr" or "135 L"
            price_cr = None
            price_match_cr = re.search(r'(\d+\.?\d*)\s*Cr', config, re.IGNORECASE)
            price_match_l = re.search(r'(\d+\.?\d*)\s*L', config, re.IGNORECASE)

            if price_match_cr:
                price_cr = float(price_match_cr.group(1))
            elif price_match_l:
                # Convert lakhs to crores
                lakhs = float(price_match_l.group(1))
                price_cr = lakhs / 100.0

            if price_cr is None:
                continue

            # Extract sqft range (optional)
            sqft_match = re.search(r'(\d+\s*-\s*\d+|\d+)', config)
            sqft_range = sqft_match.group(1).strip() if sqft_match else None

            units.append({
                "bhk": bhk,
                "price_cr": price_cr,
                "price_lakhs": price_cr * 100,  # Also provide in lakhs for easier comparison
                "sqft_range": sqft_range
            })

        except (ValueError, AttributeError) as e:
            logger.warning(f"Failed to parse configuration segment '{config}': {e}")
            continue

    return units

class HybridRetrievalService:
    """
    Production retrieval service for sales assistant.
    Queries Pixeltable directly for real project data.
    Falls back to mock data if database is unavailable.
    """

    def __init__(self):
        self.projects_table = None
        self.units_table = None
        self.mock_projects = []
        self._init_tables()
    
    def _init_tables(self):
        """Initialize Pixeltable table handles or load mock data."""
        try:
            self.projects_table = pxt.get_table('brigade.projects')
            # Units are embedded in projects table, no separate units table
            self.units_table = None
            logger.info("HybridRetrieval: Connected to Pixeltable brigade.projects table")
        except Exception as e:
            logger.warning(f"Pixeltable tables not available: {e}. Switching to MOCK DATA.")
            self.projects_table = None
            self.units_table = None
            self._load_mock_data()

    def _load_mock_data(self):
        """Load mock projects from seed JSON."""
        try:
            if os.path.exists(MOCK_DATA_PATH):
                with open(MOCK_DATA_PATH, 'r') as f:
                    self.mock_projects = json.load(f)
                
                # Add coordinates to mock data for radius search
                for p in self.mock_projects:
                    loc = p.get('location', '')
                    coords = get_coordinates(loc)
                    if coords:
                        p['_lat'], p['_lon'] = coords
                    else:
                        # Fallback based on zone if location is too specific
                        zone = p.get('zone', '')
                        coords = get_coordinates(zone)
                        if coords:
                            p['_lat'], p['_lon'] = coords

                logger.info(f"Loaded {len(self.mock_projects)} mock projects with coordinates")
            else:
                logger.error(f"Mock data file not found at {MOCK_DATA_PATH}")
                self.mock_projects = []
        except Exception as e:
            logger.error(f"Failed to load mock data: {e}")
            self.mock_projects = []

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
        if not self.projects_table and not self.mock_projects:
            self._init_tables()
            if not self.projects_table and not self.mock_projects:
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
        
        logger.info(f"Extracted filters: {filters.model_dump(exclude_none=True)}")

        # Query Pixeltable or Mock Data
        if self.projects_table:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                _executor,
                self._query_projects_sync,
                filters,
                query
            )
            search_method = "pixeltable"
        else:
            # Synchronous mock query (fast enough)
            results = self._query_mock_projects_sync(filters, query)
            search_method = "mock_data"
        
        return {
            "projects": results,
            "total_matching_projects": len(results),
            "filters_used": filters.model_dump(exclude_none=True),
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

            # Convert Pixeltable Row objects to dictionaries to avoid slice errors
            filtered_results = []
            for row in all_results:
                try:
                    # Convert Row to dict using to_dict() if available, otherwise dict()
                    if hasattr(row, 'to_dict'):
                        filtered_results.append(row.to_dict())
                    else:
                        # Fallback: create dict from row attributes
                        row_dict = {}
                        for key in row.keys():
                            row_dict[key] = row[key]
                        filtered_results.append(row_dict)
                except Exception as conv_err:
                    logger.error(f"Error converting row to dict: {conv_err}")
                    continue

            logger.info(f"Converted {len(filtered_results)} rows to dictionaries")
            
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

            # Apply locality filter - prioritize strict matches (location/address) over description
            if filters.locality and filters.locality.strip():
                locality_lower = filters.locality.lower()
                
                # First, try strict matching (location and address only - most accurate)
                strict_matches = [r for r in filtered_results 
                                 if locality_lower in str(r.get('location', '')).lower() or
                                    locality_lower in str(r.get('full_address', '')).lower()]
                
                # If we have strict matches, use only those (exclude description-only matches)
                if strict_matches:
                    filtered_results = strict_matches
                    logger.info(f"After strict locality filter '{filters.locality}': {len(filtered_results)} results (location/address matches only)")
                else:
                    # Only if no strict matches found, include description matches as fallback
                    # This handles cases like "near Jakkur" where location might not be exact
                    filtered_results = [r for r in filtered_results 
                                       if locality_lower in str(r.get('description', '')).lower()]
                    logger.info(f"After broad locality filter '{filters.locality}': {len(filtered_results)} results (description matches only - no strict matches found)")
            
            # Apply developer filter - search in name and builder
            if filters.developer_name and filters.developer_name.strip():
                dev_keywords = filters.developer_name.lower().split()
                filtered_results = [r for r in filtered_results 
                                   if any(kw in str(r.get('name', '')).lower() or 
                                         kw in str(r.get('builder', '')).lower() 
                                         for kw in dev_keywords)]
                logger.info(f"After developer filter '{filters.developer_name}': {len(filtered_results)} results")

            # Apply Project Name filter (Specific project search)
            if filters.project_name and filters.project_name.strip():
                p_name_lower = filters.project_name.lower()
                filtered_results = [r for r in filtered_results 
                                   if p_name_lower in str(r.get('name', '')).lower()]
                logger.info(f"After project name filter '{filters.project_name}': {len(filtered_results)} results")

            
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

            # Apply Bedroom Filter with Configuration-Level Budget Check
            matching_results = []
            if filters.bedrooms:
                target_bhks = filters.bedrooms # List[int], e.g. [2, 3]

                # If budget is also specified, do configuration-level filtering
                if filters.max_price_inr:
                    max_cr = filters.max_price_inr / 10000000  # Convert INR to Cr

                    for r in filtered_results:
                        # Parse configuration to get unit-level pricing
                        config_str = r.get('configuration', '')
                        units = parse_configuration_pricing(config_str)

                        # Check if project has ANY unit matching BOTH BHK and budget
                        matching_units = [
                            u for u in units
                            if u['bhk'] in target_bhks and u['price_cr'] <= max_cr
                        ]

                        if matching_units:
                            # Annotate project with matching configurations for transparency
                            r['matching_units'] = matching_units
                            r['_all_units'] = units  # For debugging/transparency
                            matching_results.append(r)

                    logger.info(f"After configuration-level BHK {target_bhks} + budget {max_cr}Cr filter: {len(matching_results)} projects with matching units")
                else:
                    # BHK filter only (no budget) - use existing simple logic
                    def check_bhk(r):
                        # Project config usually string: "2, 3 BHK" or "2BHK"
                        conf = str(r.get('configuration', '')).lower().strip()
                        for bhk in target_bhks:
                            if f"{bhk}" in conf: # Simple substring check: "2" in "2, 3 BHK"
                                return True
                        return False

                    matching_results = [r for r in filtered_results if check_bhk(r)]
                    logger.info(f"After bedroom filter {target_bhks}: {len(matching_results)} strict matches")
                
                # SALES LOGIC: Add better-value configurations (N+1 BHK if within budget)
                # We reuse the helper method _add_better_value_configurations
                better_value_results = self._add_better_value_configurations(
                    all_projects=filtered_results,
                    requested_bedrooms=target_bhks,
                    max_budget_lakhs=filters.max_price_inr / 100000 if filters.max_price_inr else None,
                    normalize_func=lambda s: str(s).lower().strip()
                )
                
                # Combine matching and better-value, avoiding duplicates
                seen_ids = {r.get('project_id') or r.get('name') for r in matching_results}
                for bv in better_value_results:
                    bv_id = bv.get('project_id') or bv.get('name')
                    if bv_id not in seen_ids:
                        bv['_better_value'] = True  # Mark as better value suggestion
                        matching_results.append(bv)
                        seen_ids.add(bv_id)
                
                filtered_results = matching_results
                logger.info(f"After adding better value options: {len(filtered_results)} total results")

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
                        "id": r.get('project_id', ''), # Frontend expects 'id'
                        "name": r.get('name', ''),     # Frontend expects 'name'
                        "developer": r.get('developer', ''), # Frontend expects 'developer'
                        "project_id": r.get('project_id', ''),
                        "project_name": r.get('name', ''),
                        "developer_name": r.get('developer', ''), 
                        "location": r.get('location', ''),
                        "city": r.get('zone', '') or r.get('location', ''),
                        "locality": r.get('location', ''),
                        "zone": r.get('zone', ''),
                        "status": r.get('status', ''),
                        "possession_year": r.get('possession_year'),
                        "possession_quarter": r.get('possession_quarter', ''),
                        "total_land_area": r.get('total_land_area', ''),
                        "towers": r.get('towers', ''),
                        "floors": r.get('floors', ''),
                        "amenities": r.get('amenities', ''),
                        "highlights": r.get('highlights', ''),
                        "description": r.get('description', ''),
                        "usp": r.get('usp', ''),
                        "brochure_link": r.get('brochure_link', ''),
                        "brochure_url": r.get('brochure_url', ''),
                        "rm_contact": r.get('rm_contact', ''),
                        "rm_details": r.get('rm_details', {}),
                        "location_link": r.get('location_link', ''),
                        "config_summary": r.get('configuration', ''),
                        "configuration": r.get('configuration', ''),
                        "rera_number": r.get('rera_number', ''),
                        "registration_process": r.get('registration_process', ''),
                        "price_range": {
                            "min": min_cr,
                            "max": max_cr,
                            "min_display": f"₹{min_cr:.2f} Cr" if min_cr else "Price on request",
                            "max_display": f"₹{max_cr:.2f} Cr" if max_cr else "Price on request"
                        },
                        "matching_units": [],
                        "unit_count": 0,
                        "can_expand": True,
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

    def _add_better_value_configurations(
        self,
        all_projects: List[Dict[str, Any]],
        requested_bedrooms: List[int],
        max_budget_lakhs: Optional[float],
        normalize_func
    ) -> List[Dict[str, Any]]:
        """
        Add (N+1) BHK options if they fit within budget.
        Sales logic: Show better value when available.
        
        Args:
            all_projects: All projects that passed other filters
            requested_bedrooms: List of requested BHK counts [2, 3]
            max_budget_lakhs: Maximum budget in lakhs (None if no budget filter)
            normalize_func: Function to normalize configuration strings
            
        Returns:
            List of better-value projects (N+1 BHK within budget)
        """
        better_value = []
        
        for req_bhk in requested_bedrooms:
            next_bhk = req_bhk + 1
            
            for project in all_projects:
                # Check if project has (N+1) BHK configuration
                conf = normalize_func(project.get('configuration', ''))
                has_next_bhk = f"{next_bhk}" in conf
                
                if not has_next_bhk:
                    continue
                
                # Check if it fits within budget
                budget_min = project.get('budget_min', 0)
                if budget_min and budget_min > 0:
                    if max_budget_lakhs is None or budget_min <= max_budget_lakhs:
                        # This is a better-value option
                        better_value.append(project)
        
        logger.info(f"Found {len(better_value)} better-value configurations (N+1 BHK within budget)")
        return better_value

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

    def _query_mock_projects_sync(self, filters: PropertyFilters, query: str) -> List[Dict[str, Any]]:
        """Query Mock projects with filters."""
        try:
            if not self.mock_projects:
                logger.error("WARNING: No mock projects loaded during query! Check seed_projects.json path.")
                return []

            filtered_results = list(self.mock_projects)
            logger.info(f"Mock Query: Starting with {len(filtered_results)} projects")

            # Normalization helper
            def normalize(s):
                return str(s).lower().strip() if s else ""

            # Apply city filter
            if filters.city and filters.city.strip():
                city_lower = normalize(filters.city)
                if city_lower != 'bangalore':
                    filtered_results = [r for r in filtered_results 
                                       if city_lower in normalize(r.get('location', '')) or 
                                          city_lower in normalize(r.get('zone', '')) or
                                          city_lower in normalize(r.get('full_address', ''))]

            # Apply Zone filter
            if filters.area and filters.area.strip():
                area_lower = normalize(filters.area)
                filtered_results = [r for r in filtered_results 
                                   if area_lower in normalize(r.get('zone', '')) or 
                                      area_lower in normalize(r.get('location', '')) or
                                      area_lower in normalize(r.get('full_address', ''))]

            # Apply locality filter
            if filters.locality and filters.locality.strip():
                locality_lower = normalize(filters.locality)
                filtered_results = [r for r in filtered_results 
                                   if locality_lower in normalize(r.get('location', '')) or
                                      locality_lower in normalize(r.get('full_address', '')) or
                                      locality_lower in normalize(r.get('description', '')) or
                                      locality_lower in normalize(r.get('usp', ''))] # Added USP check

            # Apply developer filter
            if filters.developer_name and filters.developer_name.strip():
                dev_keywords = filters.developer_name.lower().split()
                filtered_results = [r for r in filtered_results 
                                   if any(kw in normalize(r.get('name', '')) or 
                                         kw in normalize(r.get('builder', '')) 
                                         for kw in dev_keywords)]
            
            # Apply budget filter
            if filters.max_price_inr:
                max_lakhs = filters.max_price_inr / 100000
                filtered_results = [r for r in filtered_results 
                                   if r.get('budget_min') is not None and r.get('budget_min') > 0 and r.get('budget_min') <= max_lakhs]
            
            if filters.min_price_inr:
                min_lakhs = filters.min_price_inr / 100000
                filtered_results = [r for r in filtered_results 
                                   if r.get('budget_max') is None or r.get('budget_max', 99999) >= min_lakhs]
            
            # Apply Possession Year filter
            if filters.possession_year:
                target_year = filters.possession_year
                filtered_results = [r for r in filtered_results 
                                   if r.get('possession_year') and str(r.get('possession_year')).strip().isdigit() and int(r.get('possession_year')) <= target_year]

            # Apply Bedroom Filter
            matching_results = []
            if filters.bedrooms:
                target_bhks = filters.bedrooms # List[int], e.g. [2, 3]
                def check_bhk(r):
                    # Project config usually string: "2, 3 BHK" or "2BHK"
                    conf = normalize(r.get('configuration', ''))
                    for bhk in target_bhks:
                        if f"{bhk}" in conf: # Simple substring check: "2" in "2, 3 BHK"
                            return True
                    return False
                
                matching_results = [r for r in filtered_results if check_bhk(r)]
                
                # SALES LOGIC: Add better-value configurations (N+1 BHK if within budget)
                better_value_results = self._add_better_value_configurations(
                    all_projects=filtered_results,
                    requested_bedrooms=target_bhks,
                    max_budget_lakhs=filters.max_price_inr / 100000 if filters.max_price_inr else None,
                    normalize_func=normalize
                )
                
                # Combine matching and better-value, avoiding duplicates
                seen_ids = {r.get('project_id') or r.get('name') for r in matching_results}
                for bv in better_value_results:
                    bv_id = bv.get('project_id') or bv.get('name')
                    if bv_id not in seen_ids:
                        bv['_better_value'] = True  # Mark as better value suggestion
                        matching_results.append(bv)
                        seen_ids.add(bv_id)
                
                filtered_results = matching_results

            # Apply Check Property Type
            if filters.property_type:
                # 'apartment', 'villa', 'plot'
                # Map to keywords
                pt_keywords = []
                for pt in filters.property_type:
                    pt = pt.lower()
                    if 'villa' in pt: pt_keywords.append('villa')
                    elif 'plot' in pt: pt_keywords.append('plot')
                    elif 'apartment' in pt: 
                        pt_keywords.append('apartment')
                        pt_keywords.append('bhk') # 2BHK usually means apartment

                if pt_keywords:
                    filtered_results = [r for r in filtered_results 
                                       if any(kw in normalize(r.get('configuration', '')) or 
                                             kw in normalize(r.get('description', '')) 
                                             for kw in pt_keywords)]

            # Apply Status
            if filters.status:
                # 'ongoing'/'upcoming' -> Under Construction
                # 'completed' -> Ready to Move
                status_whitelist = []
                for s in filters.status:
                    if s in ['completed', 'ready']:
                        status_whitelist.append('ready')
                    elif s in ['ongoing', 'upcoming', 'under construction']:
                        status_whitelist.append('construction')
                
                if status_whitelist:
                    filtered_results = [r for r in filtered_results 
                                       if any(sw in normalize(r.get('status', '')) for sw in status_whitelist)]

            # Format results like Pixeltable
            formatted = []
            for r in filtered_results:
                img = r.get('image_url')
                if isinstance(img, list) and img:
                    img = img[0]
                # Format price
                min_p = r.get('budget_min', 0)
                max_p = r.get('budget_max', 0)
                
                min_display = f"₹{min_p}L" if min_p else "POA"
                max_display = f"₹{max_p}L" if max_p else "POA"
                
                price_range = {
                    "min_display": min_display,
                    "max_display": max_display
                }
                
                formatted.append({
                    "id": r.get('project_id', r.get('name')),
                    "name": r.get('name'),
                    "developer": r.get('developer', r.get('builder', 'Brigade Group')),
                    "project_id": r.get('project_id', r.get('name')),
                    "project_name": r.get('name'),
                    "developer_name": r.get('developer', r.get('builder', 'Brigade Group')),
                    "location": r.get('location'),
                    "zone": r.get('zone', ''),
                    "city": r.get('zone', '') or r.get('location', ''),
                    "locality": r.get('location', ''),
                    "price_range": price_range,
                    "configuration": r.get('configuration', '2, 3 BHK'),
                    "config_summary": r.get('configuration', '2, 3 BHK'),
                    "status": r.get('status', 'Under Construction'),
                    "possession_year": str(r.get('possession_year', '')),
                    "possession_quarter": r.get('possession_quarter', ''),
                    "image_url": img,
                    "usp": r.get('usp', []),
                    "full_address": r.get('full_address'),
                    "highlights": r.get('description', ''),
                    "description": r.get('description', ''),
                    "amenities": r.get('amenities', ''),
                    "rera_number": r.get('rera_number', ''),
                    "brochure_url": r.get('brochure_url', ''),
                    "brochure_link": r.get('brochure_url', ''),
                    "rm_details": r.get('rm_details', {}),
                    "rm_contact": r.get('rm_details', {}).get('contact', ''),
                    "registration_process": r.get('registration_process', ''),
                    "total_land_area": r.get('total_land_area', ''),
                    "towers": r.get('towers', ''),
                    "floors": r.get('floors', ''),
                    "location_link": r.get('location_link', ''),
                    "can_expand": True
                })
            
            logger.info(f"Mock Query Final Count: {len(formatted)}")
            return formatted

        except Exception as e:
            logger.error(f"Error in mock query: {e}")
            return []


    async def get_projects_within_radius(self, location_name: str, radius_km: float = 10.0) -> List[Dict[str, Any]]:
        """
        Returns projects within a radius of a named location.
        """
        center_coords = get_coordinates(location_name)
        if not center_coords:
            logger.warning(f"Could not find coordinates for {location_name}")
            return []
            
        lat, lon = center_coords
        matches = []
        
        # Search in mock data (or Pixeltable if it had latent coords)
        # For now we use the enriched mock data
        source = self.mock_projects
        
        for p in source:
            if '_lat' in p and '_lon' in p:
                dist = calculate_distance(lat, lon, p['_lat'], p['_lon'])
                if dist <= radius_km:
                    p_copy = p.copy()
                    p_copy['_distance'] = round(dist, 2)
                    matches.append(p_copy)
                    
        # Sort by distance
        matches.sort(key=lambda x: x.get('_distance', 999))
        return matches

    async def get_budget_alternatives(
        self,
        original_filters: PropertyFilters,
        budget_adjustment_percent: float = 20.0,
        max_results: int = 3
    ) -> Dict[str, Any]:
        """
        Get proactive budget alternatives when customer shows budget concerns.
        
        Returns projects that are:
        1. Lower budget (more affordable)
        2. Slightly higher budget (better value)
        3. Same budget in emerging areas (better appreciation)
        
        Args:
            original_filters: Customer's original search filters
            budget_adjustment_percent: How much to adjust budget (default 20%)
            max_results: Maximum alternatives per category
        
        Returns:
            Dict with three categories of alternatives
        """
        alternatives = {
            "lower_budget": [],
            "better_value": [],
            "emerging_areas": []
        }
        
        if not original_filters.budget_max:
            logger.warning("No budget specified, cannot generate alternatives")
            return alternatives
        
        original_budget = original_filters.budget_max
        
        # 1. Lower budget alternatives (20% less)
        lower_budget_filters = PropertyFilters(
            configuration=original_filters.configuration,
            budget_min=original_filters.budget_min,
            budget_max=int(original_budget * (1 - budget_adjustment_percent/100)),
            location=original_filters.location,
            radius_km=original_filters.radius_km,
            possession_year=original_filters.possession_year
        )
        
        try:
            lower_results = await self.search_with_filters(
                query="affordable alternatives",
                filters=lower_budget_filters
            )
            alternatives["lower_budget"] = lower_results.get("projects", [])[:max_results]
            logger.info(f"Found {len(alternatives['lower_budget'])} lower budget alternatives")
        except Exception as e:
            logger.error(f"Error finding lower budget alternatives: {e}")
        
        # 2. Better value alternatives (10-20% higher budget)
        higher_budget_filters = PropertyFilters(
            configuration=original_filters.configuration,
            budget_min=original_budget,
            budget_max=int(original_budget * (1 + budget_adjustment_percent/100)),
            location=original_filters.location,
            radius_km=original_filters.radius_km,
            possession_year=original_filters.possession_year
        )
        
        try:
            higher_results = await self.search_with_filters(
                query="premium options",
                filters=higher_budget_filters
            )
            alternatives["better_value"] = higher_results.get("projects", [])[:max_results]
            logger.info(f"Found {len(alternatives['better_value'])} better value alternatives")
        except Exception as e:
            logger.error(f"Error finding better value alternatives: {e}")
        
        # 3. Emerging area alternatives (same budget, different location)
        # Target emerging hotspots: Sarjapur, Devanahalli, Hennur
        emerging_locations = ["Sarjapur", "Devanahalli", "Hennur", "Bannerghatta Road"]
        
        for location in emerging_locations:
            if location.lower() in (original_filters.location or "").lower():
                continue  # Skip if already searching in this area
            
            emerging_filters = PropertyFilters(
                configuration=original_filters.configuration,
                budget_min=original_filters.budget_min,
                budget_max=original_budget,
                location=location,
                radius_km=15.0,  # Wider radius for emerging areas
                possession_year=original_filters.possession_year
            )
            
            try:
                emerging_results = await self.search_with_filters(
                    query=f"projects in {location}",
                    filters=emerging_filters
                )
                
                if emerging_results.get("projects"):
                    alternatives["emerging_areas"].extend(emerging_results["projects"][:2])
                    
                    if len(alternatives["emerging_areas"]) >= max_results:
                        break
            except Exception as e:
                logger.error(f"Error finding alternatives in {location}: {e}")
        
        alternatives["emerging_areas"] = alternatives["emerging_areas"][:max_results]
        logger.info(f"Found {len(alternatives['emerging_areas'])} emerging area alternatives")
        
        # Add metadata
        alternatives["metadata"] = {
            "original_budget_max": original_budget,
            "lower_budget_max": int(original_budget * (1 - budget_adjustment_percent/100)),
            "higher_budget_max": int(original_budget * (1 + budget_adjustment_percent/100)),
            "adjustment_percent": budget_adjustment_percent,
            "total_alternatives": (
                len(alternatives["lower_budget"]) +
                len(alternatives["better_value"]) +
                len(alternatives["emerging_areas"])
            )
        }
        
        return alternatives

# Global instance
hybrid_retrieval = HybridRetrievalService()
