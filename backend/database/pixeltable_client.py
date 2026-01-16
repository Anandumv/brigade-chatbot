"""
Pixeltable Client - Drop-in replacement for supabase_client.py
Provides all functionality previously handled by Supabase using Pixeltable.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

# Import from pixeltable_setup
from database.pixeltable_setup import (
    initialize_pixeltable,
    get_projects_table,
    get_documents_table,
    get_chunks_view,
    get_faq_table,
    get_query_logs_table,
    search_similar,
    log_query,
    get_analytics_data,
    add_project,
    add_document
)


class PixeltableClient:
    """
    Pixeltable client that provides same interface as SupabaseClient.
    Drop-in replacement for supabase_client.
    """
    
    def __init__(self):
        self.initialized = False
        self._initialize()
    
    def _initialize(self):
        """Initialize Pixeltable tables."""
        try:
            initialize_pixeltable()
            self.initialized = True
            logger.info("PixeltableClient initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Pixeltable: {e}")
            self.initialized = False
    
    async def log_query(
        self,
        user_id: str,
        query: str,
        intent: str,
        answered: bool,
        confidence_score: str = None,
        refusal_reason: str = None,
        response_time_ms: int = 0,
        project_id: str = None,
        session_id: str = None
    ):
        """Log a query - compatible with supabase_client interface."""
        if not self.initialized:
            logger.warning("Pixeltable not initialized, skipping log_query")
            return

        try:
            await log_query(
                user_id=user_id,
                query=query,
                intent=intent,
                answered=answered,
                confidence_score=confidence_score,
                refusal_reason=refusal_reason,
                response_time_ms=response_time_ms,
                project_id=project_id,
                session_id=session_id
            )
        except Exception as e:
            logger.error(f"Failed to log query: {e}")
    
    async def get_user_projects(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all projects (no user filtering in Pixeltable version)."""
        try:
            projects = get_projects_table()
            results = projects.select(
                projects.project_id,
                projects.name,
                projects.location,
                projects.status,
                projects.rera_number
            ).collect()
            
            return [
                {
                    'id': r['project_id'],
                    'name': r['name'],
                    'location': r['location'],
                    'status': r['status'],
                    'rera_number': r.get('rera_number')
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Error getting projects: {e}")
            return []
    
    async def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific project by ID."""
        try:
            projects = get_projects_table()
            results = projects.where(
                projects.project_id == project_id
            ).limit(1).collect()
            
            if results:
                r = results[0]
                return {
                    'id': r['project_id'],
                    'name': r['name'],
                    'location': r['location'],
                    'status': r['status'],
                    'rera_number': r.get('rera_number'),
                    'configuration': r.get('configuration'),
                    'budget_min': r.get('budget_min'),
                    'budget_max': r.get('budget_max'),
                    'possession_year': r.get('possession_year'),
                    'description': r.get('description'),
                    'amenities': r.get('amenities')
                }
            return None
        except Exception as e:
            logger.error(f"Error getting project {project_id}: {e}")
            return None
    
    async def search_documents(
        self,
        query: str,
        project_id: Optional[str] = None,
        similarity_threshold: float = 0.5,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Search documents using vector similarity."""
        try:
            results = search_similar(query, project_filter=project_id, top_k=top_k)
            
            # Filter by threshold and format
            chunks = []
            for r in results:
                sim = r.get('similarity', 0)
                if sim >= similarity_threshold:
                    chunks.append({
                        'content': r['text'],
                        'section': f"Page {r.get('page', 'N/A')}",
                        'document_title': r.get('project_name', 'Unknown'),
                        'project_name': r.get('project_name', 'Unknown'),
                        'similarity': sim,
                        'metadata': {
                            'page': r.get('page'),
                            'source': 'pixeltable'
                        }
                    })
            
            return chunks
        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []
    
    async def get_projects_by_filters(
        self,
        configuration: str = None,
        location: str = None,
        budget_min: int = None,
        budget_max: int = None,
        possession_year: int = None,
        status: str = None
    ) -> List[Dict[str, Any]]:
        """Get projects matching filter criteria."""
        try:
            projects = get_projects_table()
            query = projects.select()
            
            # Apply filters
            if configuration:
                query = query.where(projects.configuration.contains(configuration))
            if location:
                query = query.where(projects.location.contains(location))
            if budget_min:
                query = query.where(projects.budget_max >= budget_min)
            if budget_max:
                query = query.where(projects.budget_min <= budget_max)
            if possession_year:
                query = query.where(projects.possession_year == possession_year)
            if status:
                query = query.where(projects.status == status)
            
            results = query.collect()
            
            return [
                {
                    'project_id': r['project_id'],
                    'name': r['name'],
                    'location': r['location'],
                    'configuration': r['configuration'],
                    'budget_min': r['budget_min'],
                    'budget_max': r['budget_max'],
                    'possession_year': r['possession_year'],
                    'status': r['status'],
                    'description': r.get('description'),
                    'amenities': r.get('amenities')
                }
                for r in results
            ]
        except Exception as e:
            logger.error(f"Error filtering projects: {e}")
            return []
    
    def get_analytics(self, days: int = 7) -> Dict[str, Any]:
        """Get query analytics data."""
        return get_analytics_data(days)


# Global instance - replaces supabase_client
pixeltable_client = PixeltableClient()
