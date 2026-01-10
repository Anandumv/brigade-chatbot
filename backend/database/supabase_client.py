"""
Supabase client initialization and helper functions.
"""

from supabase import create_client, Client
from typing import Optional, List, Dict, Any
from config import settings
import logging

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Wrapper for Supabase client with helper methods."""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_key
        )

    async def get_project_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project details by ID."""
        try:
            response = self.client.table("projects").select("*").eq("id", project_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Error fetching project {project_id}: {e}")
            return None

    async def get_user_projects(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all projects accessible by a user."""
        try:
            # Get user profile with project access
            profile_response = self.client.table("user_profiles").select("project_access, role").eq("id", user_id).execute()

            if not profile_response.data:
                return []

            profile = profile_response.data[0]

            # Admins have access to all projects
            if profile.get("role") == "admin":
                projects_response = self.client.table("projects").select("*").execute()
                return projects_response.data

            # Regular users have access to specific projects
            project_ids = profile.get("project_access", [])
            if not project_ids:
                return []

            projects_response = self.client.table("projects").select("*").in_("id", project_ids).execute()
            return projects_response.data
        except Exception as e:
            logger.error(f"Error fetching user projects for {user_id}: {e}")
            return []

    async def insert_document_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Insert a document chunk with embedding."""
        try:
            response = self.client.table("document_chunks").insert(chunk_data).execute()
            return response.data[0]["id"] if response.data else None
        except Exception as e:
            logger.error(f"Error inserting document chunk: {e}")
            return None

    async def search_similar_chunks(
        self,
        query_embedding: List[float],
        match_threshold: float = 0.75,
        match_count: int = 5,
        filter_project_id: Optional[str] = None,
        filter_source_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar document chunks using vector similarity.

        Args:
            query_embedding: The embedding vector of the query
            match_threshold: Minimum similarity score (0-1)
            match_count: Maximum number of results to return
            filter_project_id: Optional project ID filter
            filter_source_type: Optional source type filter ('internal' or 'external')

        Returns:
            List of similar chunks with metadata
        """
        try:
            # Call the Postgres function for vector similarity search
            params = {
                "query_embedding": query_embedding,
                "match_threshold": match_threshold,
                "match_count": match_count,
                "filter_project_id": filter_project_id,
                "filter_source_type": filter_source_type
            }

            response = self.client.rpc("search_similar_chunks", params).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error searching similar chunks: {e}")
            return []

    async def log_query(
        self,
        user_id: str,
        query: str,
        intent: str,
        answered: bool,
        refusal_reason: Optional[str] = None,
        response_time_ms: Optional[int] = None,
        confidence_score: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> None:
        """Log a user query for analytics and audit trail."""
        try:
            log_data = {
                "user_id": user_id,
                "query": query,
                "intent": intent,
                "answered": answered,
                "refusal_reason": refusal_reason,
                "response_time_ms": response_time_ms,
                "confidence_score": confidence_score,
                "project_id": project_id
            }
            self.client.table("query_logs").insert(log_data).execute()
        except Exception as e:
            logger.error(f"Error logging query: {e}")

    async def get_unit_types(self, project_id: str) -> List[Dict[str, Any]]:
        """Get structured unit type data for a project."""
        try:
            response = self.client.table("unit_types").select("*").eq("project_id", project_id).execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching unit types for project {project_id}: {e}")
            return []

    async def insert_document(
        self,
        project_id: str,
        title: str,
        doc_type: str,
        file_path: str,
        version: str = "1.0",
        uploaded_by: Optional[str] = None
    ) -> Optional[str]:
        """Insert a new document record."""
        try:
            document_data = {
                "project_id": project_id,
                "title": title,
                "type": doc_type,
                "file_path": file_path,
                "version": version,
                "uploaded_by": uploaded_by
            }
            response = self.client.table("documents").insert(document_data).execute()
            return response.data[0]["id"] if response.data else None
        except Exception as e:
            logger.error(f"Error inserting document: {e}")
            return None

    async def get_approved_sources(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get list of approved external sources."""
        try:
            query = self.client.table("approved_sources").select("*")
            if active_only:
                query = query.eq("is_active", True)
            response = query.execute()
            return response.data if response.data else []
        except Exception as e:
            logger.error(f"Error fetching approved sources: {e}")
            return []


# Global Supabase client instance
supabase_client = SupabaseClient()
