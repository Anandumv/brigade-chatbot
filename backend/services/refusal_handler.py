"""
Refusal handling service for queries that cannot be answered.
Implements the principle: Refusal > Hallucination
"""

from typing import Dict, Any, Optional
from config import REFUSAL_MESSAGES
import logging

logger = logging.getLogger(__name__)


class RefusalHandler:
    """Handle refusal logic for unsupported or unanswerable queries."""

    def should_refuse(
        self,
        intent: str,
        chunks: list,
        confidence: str
    ) -> tuple[bool, Optional[str]]:
        """
        Determine if query should be refused.

        Args:
            intent: Classified intent of the query
            chunks: Retrieved document chunks
            confidence: Confidence level

        Returns:
            Tuple of (should_refuse: bool, refusal_reason: str)
        """
        # Refuse if intent is unsupported
        if intent == "unsupported":
            logger.info("Refusing due to unsupported intent")
            return True, "unsupported_intent"

        # Refuse if no relevant chunks found
        if not chunks or len(chunks) == 0:
            logger.info("Refusing due to no relevant chunks")
            return True, "no_relevant_info"

        # Refuse if confidence is too low
        if confidence == "Not Available":
            logger.info("Refusing due to insufficient confidence")
            return True, "insufficient_confidence"

        # Don't refuse - proceed with answer generation
        return False, None

    def get_refusal_response(
        self,
        refusal_reason: str,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate refusal response.

        Args:
            refusal_reason: Reason for refusal
            query: Original user query (optional, for context)

        Returns:
            Refusal response dictionary
        """
        # Map refusal reasons to messages
        reason_to_message = {
            "unsupported_intent": self._get_unsupported_intent_message(query),
            "no_relevant_info": REFUSAL_MESSAGES["no_relevant_info"],
            "insufficient_confidence": REFUSAL_MESSAGES["insufficient_confidence"],
            "conflicting_info": REFUSAL_MESSAGES["conflicting_info"],
            "future_prediction": REFUSAL_MESSAGES["future_prediction"],
            "legal_advice": REFUSAL_MESSAGES["legal_advice"],
        }

        message = reason_to_message.get(
            refusal_reason,
            REFUSAL_MESSAGES["no_relevant_info"]
        )

        return {
            "answer": message,
            "sources": [],
            "confidence": "Not Available",
            "intent": "unsupported",
            "refusal_reason": refusal_reason
        }

    def _get_unsupported_intent_message(self, query: Optional[str] = None) -> str:
        """
        Get context-specific message for unsupported intents.

        Args:
            query: User's query

        Returns:
            Refusal message
        """
        if not query:
            return REFUSAL_MESSAGES["no_relevant_info"]

        query_lower = query.lower()

        # Check for specific unsupported query types
        if any(keyword in query_lower for keyword in ["roi", "return", "investment", "profit", "value in", "years"]):
            return REFUSAL_MESSAGES["future_prediction"]

        if any(keyword in query_lower for keyword in ["legal", "lawyer", "contract", "agreement", "sue"]):
            return REFUSAL_MESSAGES["legal_advice"]

        if any(keyword in query_lower for keyword in ["should i", "recommend", "advise", "suggest buying"]):
            return "I cannot provide personal recommendations. Please consult with our sales team or a real estate advisor."

        # Default refusal
        return REFUSAL_MESSAGES["no_relevant_info"]

    def detect_hallucination_risk(self, answer: str, chunks: list) -> bool:
        """
        Detect if generated answer might contain hallucinated information.

        Args:
            answer: Generated answer
            chunks: Source chunks used

        Returns:
            True if hallucination risk detected
        """
        # Simple heuristic: check if answer is much longer than source material
        if not chunks:
            return True

        total_source_length = sum(len(chunk.get("content", "")) for chunk in chunks)
        answer_length = len(answer)

        # If answer is significantly longer than source, might be hallucinating
        if answer_length > total_source_length * 1.5:
            logger.warning("Potential hallucination: answer much longer than source material")
            return True

        return False


# Global refusal handler instance
refusal_handler = RefusalHandler()
