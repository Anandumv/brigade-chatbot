"""
Confidence scoring service to determine answer reliability.
"""

from typing import List, Dict, Any, Literal
from config import CONFIDENCE_THRESHOLDS
import logging

logger = logging.getLogger(__name__)

ConfidenceLevel = Literal["High", "Medium", "Not Available"]


class ConfidenceScorer:
    """Calculate confidence scores for retrieved information."""

    def __init__(self):
        self.high_threshold = CONFIDENCE_THRESHOLDS["high"]
        self.medium_threshold = CONFIDENCE_THRESHOLDS["medium"]

    def score_confidence(
        self,
        chunks: List[Dict[str, Any]]
    ) -> ConfidenceLevel:
        """
        Calculate confidence level based on retrieved chunks.

        Args:
            chunks: Retrieved document chunks with similarity scores

        Returns:
            Confidence level: 'High', 'Medium', or 'Not Available'
        """
        if not chunks:
            return "Not Available"

        top_similarity = chunks[0].get("similarity", 0)

        # High confidence: Top chunk has very high similarity AND multiple chunks agree
        if top_similarity >= self.high_threshold:
            if len(chunks) >= 2:
                # Check if second chunk also has high similarity (agreement)
                second_similarity = chunks[1].get("similarity", 0)
                if second_similarity >= self.medium_threshold:
                    logger.info(f"High confidence: top_sim={top_similarity:.3f}, second_sim={second_similarity:.3f}")
                    return "High"

            # High similarity but only one chunk - still high confidence
            logger.info(f"High confidence: top_sim={top_similarity:.3f}, single source")
            return "High"

        # Medium confidence: Decent similarity OR synthesis from multiple chunks
        elif top_similarity >= self.medium_threshold:
            logger.info(f"Medium confidence: top_sim={top_similarity:.3f}")
            return "Medium"

        # Low confidence - treat as "Not Available"
        else:
            logger.info(f"Low confidence: top_sim={top_similarity:.3f} - treating as Not Available")
            return "Not Available"

    def requires_multiple_sources(self, intent: str) -> bool:
        """
        Check if the query intent requires multiple sources for high confidence.

        Args:
            intent: Query intent type

        Returns:
            True if multiple sources required
        """
        # Comparison queries should have sources from both projects
        if intent == "comparison":
            return True

        # Sales pitches might benefit from multiple perspectives
        if intent == "sales_pitch":
            return True

        return False

    def validate_sources_for_intent(
        self,
        chunks: List[Dict[str, Any]],
        intent: str
    ) -> bool:
        """
        Validate that retrieved chunks match the query intent.

        Args:
            chunks: Retrieved chunks
            intent: Query intent

        Returns:
            True if chunks are appropriate for intent
        """
        if not chunks:
            return False

        # For comparison queries, ensure we have chunks from multiple projects
        if intent == "comparison":
            projects = set(chunk.get("project_name") for chunk in chunks)
            if len(projects) < 2:
                logger.warning("Comparison query but chunks from only one project")
                return False

        return True

    def get_confidence_explanation(
        self,
        confidence: ConfidenceLevel,
        chunks: List[Dict[str, Any]]
    ) -> str:
        """
        Get human-readable explanation for confidence score.

        Args:
            confidence: Confidence level
            chunks: Retrieved chunks

        Returns:
            Explanation string
        """
        if confidence == "High":
            if len(chunks) > 1:
                return "High confidence - multiple sources confirm this information"
            else:
                return "High confidence - found exact match in documentation"

        elif confidence == "Medium":
            return "Medium confidence - information synthesized from available sources"

        else:
            return "Information not available in current documentation"


# Global confidence scorer instance
confidence_scorer = ConfidenceScorer()
