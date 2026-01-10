"""
Hybrid Retrieval Service
Combines SQL structured filtering with vector similarity search for efficient multi-project search
"""

from typing import Dict, List, Any, Optional
from services.filter_extractor import PropertyFilters, filter_extractor
from services.retrieval import retrieval_service
from database.supabase_client import supabase_client
from config import settings
import logging

logger = logging.getLogger(__name__)


class HybridRetrievalService:
    """
    Combines structured SQL filtering with vector similarity search.

    Search Strategy:
    1. Extract filters from natural language query
    2. SQL query to find matching units/projects (500 projects → 50 matches)
    3. Vector search ONLY within filtered projects
    4. Group results by project for presentation
    """

    def __init__(self):
        self.supabase = supabase_client.client
        self.similarity_threshold = 0.65  # Lower threshold for broader matching

    async def search_with_filters(
        self,
        query: str,
        filters: Optional[PropertyFilters] = None,
        use_llm_extraction: bool = False
    ) -> Dict[str, Any]:
        """
        Hybrid search combining SQL filtering and vector search.

        Args:
            query: Natural language query ("2bhk under 3cr in Bangalore")
            filters: Pre-extracted filters (optional, will extract from query if not provided)
            use_llm_extraction: Use GPT-4 for filter extraction (slower but more accurate)

        Returns:
            {
                "projects": [
                    {
                        "project_id": "uuid",
                        "project_name": "Brigade Citrine",
                        "developer_name": "Brigade Group",
                        "location": "Old Madras Road, Bangalore",
                        "matching_units": [
                            {
                                "bedrooms": 2,
                                "price_inr": 25000000,
                                "carpet_area_sqft": 1100,
                                "possession": "2027 Q2"
                            }
                        ],
                        "relevant_chunks": [...],
                        "unit_count": 12
                    }
                ],
                "total_matching_projects": 15,
                "filters_used": {...},
                "search_method": "hybrid" | "vector_only"
            }
        """
        logger.info(f"Hybrid search for query: {query}")

        # Step 1: Extract filters if not provided
        if filters is None:
            if use_llm_extraction:
                filters = filter_extractor.extract_with_llm_fallback(query)
            else:
                filters = filter_extractor.extract_filters(query)

        # Step 2: Decide search strategy
        if not filters.has_filters():
            # No structured filters, fall back to pure vector search
            logger.info("No structured filters found, using vector-only search")
            return await self._vector_only_search(query)

        # Step 3: SQL filtering to narrow down projects
        matching_units = await self._sql_filter_units(filters)

        if not matching_units:
            logger.info("No units match SQL filters, falling back to vector search")
            return await self._vector_only_search(query)

        logger.info(f"SQL filter found {len(matching_units)} matching units")

        # Step 4: Get unique project IDs
        project_ids = list(set(unit['project_id'] for unit in matching_units))
        logger.info(f"Matching units span {len(project_ids)} projects")

        # Step 5: Vector search within filtered projects
        query_embedding = retrieval_service.generate_query_embedding(query)

        chunks_by_project = {}
        for project_id in project_ids[:50]:  # Limit to top 50 projects for performance
            chunks = await supabase_client.search_similar_chunks(
                query_embedding=query_embedding,
                filter_project_id=project_id,
                match_threshold=self.similarity_threshold,
                match_count=3  # Top 3 most relevant chunks per project
            )
            if chunks:
                chunks_by_project[project_id] = chunks

        logger.info(f"Vector search found relevant chunks in {len(chunks_by_project)} projects")

        # Step 6: Enrich and group results by project
        results = await self._build_project_results(
            matching_units=matching_units,
            chunks_by_project=chunks_by_project
        )

        return {
            "projects": results,
            "total_matching_projects": len(results),
            "filters_used": filters.dict(exclude_none=True),
            "search_method": "hybrid"
        }

    async def _sql_filter_units(self, filters: PropertyFilters) -> List[Dict[str, Any]]:
        """
        Execute SQL query to find matching units using structured filters.

        Uses the materialized view for optimal performance.
        """
        try:
            # Build SQL conditions
            conditions, params = filters.to_sql_conditions()

            if not conditions:
                logger.warning("No SQL conditions generated from filters")
                return []

            where_clause = " AND ".join(conditions)

            # Query the materialized view for fast results
            sql = f"""
            SELECT
                unit_id,
                project_id,
                project_name,
                project_location,
                city,
                locality,
                project_status,
                rera_number,
                developer_id,
                developer_name,
                type_name,
                bedrooms,
                toilets,
                balconies,
                base_price_inr,
                price_per_sqft,
                carpet_area_sqft,
                super_builtup_area_sqm,
                possession_year,
                possession_quarter,
                available_units
            FROM project_units_view
            WHERE {where_clause}
            ORDER BY base_price_inr ASC
            LIMIT 100
            """

            logger.info(f"Executing SQL with filters: {filters.dict(exclude_none=True)}")

            # Execute using Supabase RPC (for parameterized queries)
            rpc_params = {
                "p_bedrooms": filters.bedrooms,
                "p_max_price": filters.max_price_inr,
                "p_min_price": filters.min_price_inr,
                "p_city": filters.city,
                "p_locality": filters.locality,
                "p_possession_year": filters.possession_year,
                "p_status": filters.status,
                "p_developer_name": filters.developer_name,
                "p_limit": 100
            }

            # Remove None values
            rpc_params = {k: v for k, v in rpc_params.items() if v is not None}

            response = self.supabase.rpc("execute_filtered_search", rpc_params).execute()

            if response.data:
                logger.info(f"SQL query returned {len(response.data)} units")
                return response.data
            else:
                # Fallback to direct table query if RPC not available
                logger.info("Attempting fallback query without parameterization")
                return await self._fallback_sql_query(filters)

        except Exception as e:
            logger.error(f"Error in SQL filtering: {e}", exc_info=True)
            return []

    async def _fallback_sql_query(self, filters: PropertyFilters) -> List[Dict[str, Any]]:
        """
        Fallback query using Supabase table API when RPC unavailable.
        """
        try:
            query = self.supabase.table("project_units_view").select("*")

            # Apply filters
            if filters.bedrooms:
                query = query.in_("bedrooms", filters.bedrooms)

            if filters.max_price_inr:
                query = query.lte("base_price_inr", filters.max_price_inr)

            if filters.min_price_inr:
                query = query.gte("base_price_inr", filters.min_price_inr)

            if filters.city:
                query = query.ilike("city", f"%{filters.city}%")

            if filters.locality:
                query = query.ilike("locality", filters.locality)

            if filters.possession_year:
                query = query.eq("possession_year", filters.possession_year)

            if filters.status:
                query = query.in_("project_status", filters.status)

            if filters.developer_name:
                query = query.ilike("developer_name", f"%{filters.developer_name}%")

            response = query.limit(100).execute()

            return response.data if response.data else []

        except Exception as e:
            logger.error(f"Fallback SQL query failed: {e}", exc_info=True)
            return []

    async def _vector_only_search(self, query: str) -> Dict[str, Any]:
        """
        Fallback to pure vector search when no structured filters extracted.

        Used for queries like:
        - "Tell me about Brigade Citrine"
        - "What amenities are available?"
        - "Show me luxury apartments"
        """
        logger.info("Performing vector-only search")

        query_embedding = retrieval_service.generate_query_embedding(query)

        # Search across all projects
        chunks = await supabase_client.search_similar_chunks(
            query_embedding=query_embedding,
            match_threshold=0.75,  # Higher threshold for quality
            match_count=10
        )

        if not chunks:
            return {
                "projects": [],
                "total_matching_projects": 0,
                "filters_used": {},
                "search_method": "vector_only"
            }

        # Group chunks by project
        chunks_by_project = {}
        for chunk in chunks:
            project_id = chunk.get("project_id")
            if project_id:
                if project_id not in chunks_by_project:
                    chunks_by_project[project_id] = []
                chunks_by_project[project_id].append(chunk)

        # Build project results (without unit data)
        results = []
        for project_id, project_chunks in chunks_by_project.items():
            project_data = await supabase_client.get_project_by_id(project_id)

            if project_data:
                results.append({
                    "project_id": project_id,
                    "project_name": project_data.get("name"),
                    "developer_name": await self._get_developer_name(project_data.get("developer_id")),
                    "location": project_data.get("location"),
                    "city": project_data.get("city"),
                    "locality": project_data.get("locality"),
                    "rera_number": project_data.get("rera_number"),
                    "status": project_data.get("status"),
                    "relevant_chunks": project_chunks,
                    "matching_units": [],  # No unit filtering in vector-only mode
                    "unit_count": 0
                })

        return {
            "projects": results,
            "total_matching_projects": len(results),
            "filters_used": {},
            "search_method": "vector_only"
        }

    async def _build_project_results(
        self,
        matching_units: List[Dict[str, Any]],
        chunks_by_project: Dict[str, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """
        Build final project results with units and chunks grouped by project.
        """
        results = []

        # Group units by project
        units_by_project = {}
        for unit in matching_units:
            project_id = unit['project_id']
            if project_id not in units_by_project:
                units_by_project[project_id] = []
            units_by_project[project_id].append(unit)

        # Build result for each project
        for project_id, units in units_by_project.items():
            # Use first unit for project metadata
            sample_unit = units[0]

            # Format units
            formatted_units = []
            for unit in units[:10]:  # Limit to 10 units per project for display
                formatted_units.append({
                    "unit_id": unit.get("unit_id"),
                    "type_name": unit.get("type_name"),
                    "bedrooms": unit.get("bedrooms"),
                    "toilets": unit.get("toilets"),
                    "balconies": unit.get("balconies"),
                    "price_inr": unit.get("base_price_inr"),
                    "price_display": self._format_indian_currency(unit.get("base_price_inr")),
                    "price_per_sqft": unit.get("price_per_sqft"),
                    "carpet_area_sqft": unit.get("carpet_area_sqft"),
                    "super_builtup_area_sqm": unit.get("super_builtup_area_sqm"),
                    "possession": f"{unit.get('possession_year', 'TBD')} {unit.get('possession_quarter', '')}".strip(),
                    "available_units": unit.get("available_units")
                })

            results.append({
                "project_id": project_id,
                "project_name": sample_unit.get("project_name"),
                "developer_name": sample_unit.get("developer_name"),
                "location": sample_unit.get("project_location"),
                "city": sample_unit.get("city"),
                "locality": sample_unit.get("locality"),
                "rera_number": sample_unit.get("rera_number"),
                "status": sample_unit.get("project_status"),
                "price_range": {
                    "min": min(u.get("base_price_inr", 0) for u in units),
                    "max": max(u.get("base_price_inr", 0) for u in units),
                    "min_display": self._format_indian_currency(min(u.get("base_price_inr", 0) for u in units)),
                    "max_display": self._format_indian_currency(max(u.get("base_price_inr", 0) for u in units))
                },
                "matching_units": formatted_units,
                "unit_count": len(units),
                "can_expand": len(units) > 10,
                "relevant_chunks": chunks_by_project.get(project_id, [])
            })

        # Sort by price (lowest first)
        results.sort(key=lambda x: x["price_range"]["min"])

        return results

    async def _get_developer_name(self, developer_id: Optional[str]) -> Optional[str]:
        """Get developer name from ID"""
        if not developer_id:
            return None

        try:
            response = self.supabase.table("developers").select("name").eq("id", developer_id).execute()
            return response.data[0]["name"] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching developer name: {e}")
            return None

    def _format_indian_currency(self, amount_inr: Optional[int]) -> str:
        """
        Format INR amount in Indian numbering system.

        Examples:
        - 30000000 → "₹3.0 Cr"
        - 5000000 → "₹50 Lac"
        - 500000 → "₹5 Lac"
        """
        if amount_inr is None or amount_inr == 0:
            return "Price on request"

        if amount_inr >= 10000000:  # Crores (1 crore = 1,00,00,000)
            cr = amount_inr / 10000000
            return f"₹{cr:.2f} Cr"
        elif amount_inr >= 100000:  # Lakhs (1 lakh = 1,00,000)
            lac = amount_inr / 100000
            return f"₹{lac:.2f} Lac"
        else:
            return f"₹{amount_inr:,}"


# Global instance
hybrid_retrieval = HybridRetrievalService()
