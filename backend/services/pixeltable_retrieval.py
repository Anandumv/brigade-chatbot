"""
Pixeltable Retrieval Service
Drop-in replacement for retrieval.py that uses Pixeltable for vector search.
Maintains API compatibility with existing codebase.
"""

from typing import List, Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

# Check if Pixeltable is available
PIXELTABLE_AVAILABLE = False
try:
    import pixeltable as pxt
    PIXELTABLE_AVAILABLE = True
except ImportError:
    logger.warning("Pixeltable not installed. Using fallback retrieval.")


class PixeltableRetrievalService:
    """
    Retrieval service using Pixeltable for vector similarity search.
    API-compatible with existing RetrievalService for seamless switching.
    """

    def __init__(self):
        self.initialized = False
        self.chunks_view = None
        self.faq_table = None
        
        # Sales query expansion (same as original)
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
        
        if PIXELTABLE_AVAILABLE:
            self._initialize_tables()

    def _initialize_tables(self):
        """Initialize Pixeltable table connections."""
        try:
            # Check for doc_chunks
            try:
                self.chunks_view = pxt.get_table('brigade.doc_chunks')
                logger.info("Connected to brigade.doc_chunks view")
            except Exception:
                logger.warning("Table brigade.doc_chunks not found")
            
            # Check for faq
            try:
                self.faq_table = pxt.get_table('brigade.faq')
                logger.info("Connected to brigade.faq table")
            except Exception:
                logger.warning("Table brigade.faq not found")
            
            self.initialized = self.chunks_view is not None
            
        except Exception as e:
            logger.error(f"Failed to initialize Pixeltable tables: {e}")
            self.initialized = False

    def is_available(self) -> bool:
        """Check if Pixeltable retrieval is available."""
        return PIXELTABLE_AVAILABLE and self.initialized

    def expand_sales_query(self, query: str) -> str:
        """Expand common sales abbreviations for better matching."""
        expanded_query = query
        query_lower = query.lower()

        for term, expansion in self.sales_expansions.items():
            if term in query_lower:
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
        Retrieve document chunks similar to the query using Pixeltable.

        API-compatible with original RetrievalService.
        """
        if not self.is_available():
            logger.warning("Pixeltable not available, returning empty results")
            return []

        # Expand query for better matching
        expanded_query = self.expand_sales_query(query)
        logger.info(f"Original query: {query}")
        if expanded_query != query:
            logger.info(f"Expanded query: {expanded_query}")

        # Default parameters
        threshold = similarity_threshold or 0.5
        limit = top_k or 5

        try:
            # Build similarity query
            sim = self.chunks_view.text.similarity(expanded_query)
            
            # Build result query
            results_query = self.chunks_view.select(
                self.chunks_view.text,
                self.chunks_view.page,
                self.chunks_view.project_name,
                similarity=sim
            ).where(sim >= threshold).order_by(sim, asc=False)
            
            # Apply project filter if provided
            if project_id:
                results_query = results_query.where(
                    self.chunks_view.project_name == project_id
                )
            
            # Execute query
            results = results_query.limit(limit).collect()
            
            # Convert to expected format
            chunks = []
            for row in results:
                chunk = {
                    "content": row['text'],
                    "section": f"Page {row.get('page', 'Unknown')}",
                    "document_title": row.get('project_name', 'Unknown'),
                    "project_name": row.get('project_name', 'Unknown'),
                    "similarity": row.get('similarity', 0),
                    "metadata": {
                        "page": row.get('page'),
                        "source": "pixeltable"
                    }
                }
                chunks.append(chunk)

            logger.info(f"Retrieved {len(chunks)} chunks with similarity >= {threshold}")
            return chunks

        except Exception as e:
            logger.error(f"Error retrieving chunks from Pixeltable: {e}")
            return []

    def get_faq_response(self, faq_type: str) -> Optional[str]:
        """Get pre-computed FAQ response by type."""
        if not self.faq_table:
            return None

        try:
            result = self.faq_table.where(
                self.faq_table.faq_type == faq_type
            ).select(
                self.faq_table.response
            ).limit(1).collect()

            if result:
                return result[0]['response']
            return None

        except Exception as e:
            logger.error(f"Error getting FAQ response: {e}")
            return None

    def get_all_faq_responses(self) -> Dict[str, str]:
        """Get all pre-computed FAQ responses."""
        if not self.faq_table:
            return {}

        try:
            results = self.faq_table.select(
                self.faq_table.faq_type,
                self.faq_table.response
            ).collect()

            return {row['faq_type']: row['response'] for row in results}

        except Exception as e:
            logger.error(f"Error getting all FAQ responses: {e}")
            return {}

    def filter_by_confidence(
        self,
        chunks: List[Dict[str, Any]],
        min_confidence: float = 0.75
    ) -> List[Dict[str, Any]]:
        """Filter chunks by minimum confidence score."""
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
        """Check if we have sufficient context to answer the query."""
        return len(chunks) >= min_chunks

    def get_top_chunk(
        self,
        chunks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Get the most relevant chunk."""
        return chunks[0] if chunks else None


# Hybrid service that tries Pixeltable first, falls back to Supabase
class HybridRetrievalService:
    """
    Hybrid retrieval service that uses Pixeltable when available,
    falls back to original Supabase-based retrieval otherwise.
    """

    def __init__(self):
        self.pixeltable_service = PixeltableRetrievalService()
        self._supabase_service = None  # Lazy load

    @property
    def supabase_service(self):
        """Lazy load Supabase retrieval service."""
        if self._supabase_service is None:
            from services.retrieval import retrieval_service
            self._supabase_service = retrieval_service
        return self._supabase_service

    def use_pixeltable(self) -> bool:
        """Determine whether to use Pixeltable."""
        # Use env var to control, default to Pixeltable if available
        use_pt = os.getenv("USE_PIXELTABLE", "auto").lower()
        
        if use_pt == "true":
            return self.pixeltable_service.is_available()
        elif use_pt == "false":
            return False
        else:  # auto
            return self.pixeltable_service.is_available()

    async def retrieve_similar_chunks(
        self,
        query: str,
        project_id: Optional[str] = None,
        source_type: Optional[str] = None,
        similarity_threshold: Optional[float] = None,
        top_k: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve chunks using best available service.
        """
        if self.use_pixeltable():
            logger.info("Using Pixeltable for retrieval")
            return await self.pixeltable_service.retrieve_similar_chunks(
                query=query,
                project_id=project_id,
                source_type=source_type,
                similarity_threshold=similarity_threshold,
                top_k=top_k
            )
        else:
            logger.info("Using Supabase for retrieval")
            return await self.supabase_service.retrieve_similar_chunks(
                query=query,
                project_id=project_id,
                source_type=source_type,
                similarity_threshold=similarity_threshold,
                top_k=top_k
            )

    def get_faq_response(self, faq_type: str) -> Optional[str]:
        """Get FAQ response from Pixeltable if available."""
        if self.pixeltable_service.is_available():
            return self.pixeltable_service.get_faq_response(faq_type)
        return None


# Global instances
pixeltable_retrieval = PixeltableRetrievalService()
hybrid_retrieval_service = HybridRetrievalService()
