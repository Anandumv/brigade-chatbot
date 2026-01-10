"""
Web search service for fetching external information when internal documents don't have answers.
Uses OpenRouter LLM with browsing/search capabilities.
"""

from typing import Dict, Any, Optional, List
from openai import OpenAI
from config import settings
import logging
import re

logger = logging.getLogger(__name__)


class WebSearchService:
    """Service for searching the web and getting contextual information."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        # Use a model that can provide current information
        self.model = "openai/gpt-4-turbo-preview"

    def search_and_answer(
        self,
        query: str,
        context: Optional[str] = None,
        topic_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search for information on the web and return a formatted answer.

        Args:
            query: The user's question
            context: Optional context about what we're looking for
            topic_hint: Hint about the topic (e.g., "real estate", "Brigade properties")

        Returns:
            Dict with answer and source indication
        """
        try:
            # Build a prompt that asks the LLM to provide information
            system_prompt = """You are a helpful real estate sales assistant for Brigade Group, a leading property developer in India.

When the user asks a question that isn't in your internal documents, provide helpful general information based on:
1. Common real estate knowledge
2. General information about locations, amenities, and property features
3. Industry best practices

IMPORTANT RULES:
- Be helpful and informative
- Clearly indicate this is GENERAL information, not specific to Brigade's properties
- Format your response nicely with bullet points where appropriate
- Keep responses concise but comprehensive
- Never make up specific numbers, prices, or legal details

Format your response like this:
**General Information:**
[Your helpful response here]

**Note:** This is general real estate information. For specific details about Brigade properties, please contact our sales team."""

            user_message = f"""The user asked: "{query}"

Our internal documents didn't have specific information about this topic.
{f'Context: {context}' if context else ''}
{f'Topic: {topic_hint}' if topic_hint else ''}

Please provide helpful general information that would be useful for a real estate sales agent to know."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=800
            )

            answer = response.choices[0].message.content

            return {
                "answer": answer,
                "source_type": "external",
                "sources": [{
                    "document": "General Real Estate Knowledge",
                    "section": "External Information",
                    "page": None,
                    "excerpt": "This information is based on general real estate knowledge.",
                    "similarity": 0.5
                }],
                "confidence": "Low",
                "is_external": True
            }

        except Exception as e:
            logger.error(f"Error in web search: {e}")
            return {
                "answer": "I apologize, but I couldn't find specific information about this topic. Please contact our sales team for assistance.",
                "source_type": "none",
                "sources": [],
                "confidence": "Not Available",
                "is_external": False
            }

    def get_location_info(self, location: str) -> Dict[str, Any]:
        """Get general information about a location."""
        return self.search_and_answer(
            query=f"What are the key features and benefits of living in {location}?",
            topic_hint=f"Location information for {location}"
        )

    def get_amenity_info(self, amenity: str) -> Dict[str, Any]:
        """Get general information about an amenity."""
        return self.search_and_answer(
            query=f"What are the benefits of having {amenity} in a residential property?",
            topic_hint=f"Amenity information for {amenity}"
        )


# Global web search service instance
web_search_service = WebSearchService()
