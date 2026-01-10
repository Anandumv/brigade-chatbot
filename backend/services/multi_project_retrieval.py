"""
Multi-project retrieval service for comparison queries.
Phase 2 feature.
"""

from typing import List, Dict, Any, Optional
from services.retrieval import retrieval_service
import logging

logger = logging.getLogger(__name__)


class MultiProjectRetrieval:
    """Handle retrieval across multiple projects for comparison queries."""

    async def retrieve_for_comparison(
        self,
        query: str,
        project_ids: List[str],
        top_k_per_project: int = 3
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve chunks from multiple projects for comparison.

        Args:
            query: User's comparison question
            project_ids: List of project IDs to compare
            top_k_per_project: Number of chunks to retrieve per project

        Returns:
            Dictionary mapping project_id to list of chunks
        """
        results = {}

        for project_id in project_ids:
            try:
                chunks = await retrieval_service.retrieve_similar_chunks(
                    query=query,
                    project_id=project_id,
                    top_k=top_k_per_project
                )
                results[project_id] = chunks
                logger.info(f"Retrieved {len(chunks)} chunks for project {project_id}")
            except Exception as e:
                logger.error(f"Error retrieving for project {project_id}: {e}")
                results[project_id] = []

        return results

    async def retrieve_all_projects(
        self,
        query: str,
        top_k: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve chunks from all projects and group by project.

        Args:
            query: User's query
            top_k: Total number of chunks to retrieve

        Returns:
            Dictionary mapping project names to chunks
        """
        # Retrieve without project filter
        all_chunks = await retrieval_service.retrieve_similar_chunks(
            query=query,
            project_id=None,
            top_k=top_k
        )

        # Group by project
        grouped = {}
        for chunk in all_chunks:
            project_name = chunk.get("project_name", "Unknown")
            if project_name not in grouped:
                grouped[project_name] = []
            grouped[project_name].append(chunk)

        logger.info(f"Retrieved chunks from {len(grouped)} projects")
        return grouped

    def validate_comparison_coverage(
        self,
        grouped_chunks: Dict[str, List[Dict[str, Any]]],
        min_projects: int = 2
    ) -> bool:
        """
        Validate that we have sufficient coverage for comparison.

        Args:
            grouped_chunks: Chunks grouped by project
            min_projects: Minimum number of projects needed

        Returns:
            True if sufficient coverage
        """
        projects_with_chunks = sum(1 for chunks in grouped_chunks.values() if len(chunks) > 0)
        return projects_with_chunks >= min_projects


# Global multi-project retrieval instance
multi_project_retrieval = MultiProjectRetrieval()
