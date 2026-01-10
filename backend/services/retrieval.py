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

        # Sales query expansion mappings
        self.sales_expansions = {
            "1bhk": "1 bedroom 1bhk apartment flat studio",
            "2bhk": "2 bedroom 2bhk apartment flat",
            "3bhk": "3 bedroom 3bhk apartment flat",
            "4bhk": "4 bedroom 4bhk apartment flat",
            "5bhk": "5 bedroom 5bhk apartment flat penthouse",
            "sqft": "square feet area size carpet built-up super",
            "amenities": "amenities facilities features clubhouse gym pool",
            "price": "price cost pricing rate per sqft total",
            "location": "location connectivity address near distance",
            "ready": "ready possession move-in completion delivery",
            "under construction": "under construction ongoing project timeline",
            "rera": "rera registration approval license",
        }

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

    def expand_sales_query(self, query: str) -> str:
        """
        Expand common sales abbreviations and terms for better matching.

        Args:
            query: Original user query

        Returns:
            Expanded query with additional keywords
        """
        expanded_query = query
        query_lower = query.lower()

        # Check for each expansion term and add synonyms
        for term, expansion in self.sales_expansions.items():
            if term in query_lower:
                # Add expansion to query without replacing original term
                expanded_query = f"{expanded_query} {expansion}"
                logger.debug(f"Expanded '{term}' with: {expansion}")

        return expanded_query

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
        # Expand query for better matching
        expanded_query = self.expand_sales_query(query)
        logger.info(f"Original query: {query}")
        if expanded_query != query:
            logger.info(f"Expanded query: {expanded_query}")

        # Generate query embedding from expanded query
        query_embedding = self.generate_query_embedding(expanded_query)

        # Use provided or default parameters
        threshold = similarity_threshold or self.similarity_threshold
        limit = top_k or self.top_k

        # Try vector similarity search first
        chunks = await supabase_client.search_similar_chunks(
            query_embedding=query_embedding,
            match_threshold=threshold,
            match_count=limit,
            filter_project_id=project_id,
            filter_source_type=source_type
        )

        # Fallback to text search if vector search returns no results
        if not chunks:
            logger.warning("Vector search returned no results, falling back to text search")
            chunks = await supabase_client.search_chunks_by_text(
                query=query,
                limit=limit,
                filter_project_id=project_id
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
