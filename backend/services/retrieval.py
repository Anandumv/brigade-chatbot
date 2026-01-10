"""
Retrieval service for vector similarity search of document chunks.
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import settings
from database.supabase_client import supabase_client
import logging

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving relevant document chunks based on query similarity."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.embedding_model = settings.embedding_model
        self.similarity_threshold = settings.similarity_threshold
        self.top_k = settings.top_k_results

    def generate_query_embedding(self, query: str) -> List[float]:
        """
        Generate embedding for user query.

        Args:
            query: User's question

        Returns:
            Embedding vector
        """
        try:
            response = self.client.embeddings.create(
                model=self.embedding_model,
                input=query,
                encoding_format="float"
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            raise

    async def retrieve_similar_chunks(
        self,
        query: str,
        project_id: Optional[str] = None,
        source_type: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve document chunks similar to the query.

        Args:
            query: User's question
            project_id: Optional project ID filter
            source_type: Optional source type filter ('internal' or 'external')
            similarity_threshold: Override default similarity threshold
            top_k: Override default number of results

        Returns:
            List of similar chunks with metadata and similarity scores
        """
        # Generate query embedding
        query_embedding = self.generate_query_embedding(query)

        # Use provided or default parameters
        threshold = similarity_threshold or self.similarity_threshold
        limit = top_k or self.top_k

        # Retrieve similar chunks from Supabase
        chunks = await supabase_client.search_similar_chunks(
            query_embedding=query_embedding,
            match_threshold=threshold,
            match_count=limit,
            filter_project_id=project_id,
            filter_source_type=source_type
        )

        logger.info(f"Retrieved {len(chunks)} chunks with similarity >= {threshold}")

        return chunks

    def filter_by_confidence(
        self,
        chunks: List[Dict[str, Any]],
        min_confidence: float = 0.75
    ) -> List[Dict[str, Any]]:
        """
        Filter chunks by minimum confidence score.

        Args:
            chunks: List of retrieved chunks
            min_confidence: Minimum similarity score

        Returns:
            Filtered list of chunks
        """
        filtered = [
            chunk for chunk in chunks
            if chunk.get("similarity", 0) >= min_confidence
        ]

        logger.info(f"Filtered to {len(filtered)}/{len(chunks)} chunks with confidence >= {min_confidence}")
        return filtered

    def has_sufficient_context(
        self,
        chunks: List[Dict[str, Any]],
        min_chunks: int = 1
    ) -> bool:
        """
        Check if we have sufficient context to answer the query.

        Args:
            chunks: Retrieved chunks
            min_chunks: Minimum number of chunks required

        Returns:
            True if sufficient context exists
        """
        return len(chunks) >= min_chunks

    def detect_conflicting_information(
        self,
        chunks: List[Dict[str, Any]]
    ) -> bool:
        """
        Detect if top chunks contain conflicting information.

        Args:
            chunks: Retrieved chunks

        Returns:
            True if conflicts detected
        """
        if len(chunks) < 2:
            return False

        # Simple heuristic: if top 2 chunks are from different document types
        # and have significantly different similarity scores, might indicate conflict
        top_2 = chunks[:2]

        # Check if from different projects (could indicate comparison query)
        if (top_2[0].get("project_name") != top_2[1].get("project_name")):
            # This is expected for comparison queries
            return False

        # Check for significant similarity gap (might indicate uncertainty)
        similarity_gap = top_2[0].get("similarity", 0) - top_2[1].get("similarity", 0)
        if similarity_gap > 0.15:
            logger.warning(f"Large similarity gap detected: {similarity_gap}")

        return False  # For now, no automatic conflict detection

    def get_top_chunk(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Get the most relevant chunk."""
        return chunks[0] if chunks else None


# Global retrieval service instance
retrieval_service = RetrievalService()
