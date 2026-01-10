"""
Web search service for fetching external information when internal documents don't have answers.
Uses Tavily API for real web search with LLM synthesis.
"""

from typing import Dict, Any, Optional, List
from openai import OpenAI
from config import settings
import logging
import re

logger = logging.getLogger(__name__)

# Try to import Tavily, fall back to LLM-only mode if not available
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    logger.warning("Tavily not installed. Web search will use LLM knowledge only. Install with: pip install tavily-python")


class WebSearchService:
    """Service for searching the web and getting contextual information."""

    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.model = "openai/gpt-4-turbo-preview"

        # Initialize Tavily if API key available
        self.tavily_client = None
        if TAVILY_AVAILABLE and hasattr(settings, 'tavily_api_key') and settings.tavily_api_key:
            try:
                self.tavily_client = TavilyClient(api_key=settings.tavily_api_key)
                logger.info("Tavily web search initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Tavily: {e}. Falling back to LLM knowledge.")

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
            topic_hint: Hint about the topic (e.g., "Brigade Group real estate Bangalore")

        Returns:
            Dict with answer, sources, confidence, is_external
        """
        # If Tavily is available, use real web search
        if self.tavily_client:
            return self._tavily_search(query, context, topic_hint)
        else:
            # Fall back to LLM knowledge
            return self._llm_fallback(query, context, topic_hint)

    def _tavily_search(
        self,
        query: str,
        context: Optional[str] = None,
        topic_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Use Tavily API for real web search."""
        try:
            # Build search query with topic hint
            search_query = f"{query} {topic_hint}" if topic_hint else query

            logger.info(f"Tavily search: {search_query}")

            # Tavily search with optimal settings for real estate
            search_results = self.tavily_client.search(
                query=search_query,
                search_depth="advanced",  # Deep search for better results
                max_results=5,
                include_answer=True,  # Tavily generates answer
                include_raw_content=False,
                include_domains=["brigade.co.in", "rera.karnataka.gov.in", "magicbricks.com", "99acres.com", "housing.com"]
            )

            # If no results, return fallback
            if not search_results.get("results"):
                logger.warning("No Tavily results, falling back to LLM")
                return self._llm_fallback(query, context, topic_hint)

            # Use Tavily's generated answer if available, otherwise synthesize
            if search_results.get("answer"):
                answer = search_results["answer"]
                logger.info("Using Tavily generated answer")
            else:
                answer = self._synthesize_answer(query, search_results["results"])
                logger.info("Synthesized answer from Tavily results")

            # Format sources from Tavily results
            sources = []
            for idx, result in enumerate(search_results["results"][:3], 1):
                sources.append({
                    "document": f"Web Source {idx}",
                    "section": result.get("title", "External Source"),
                    "page": None,
                    "excerpt": result.get("content", "")[:200] + "..." if len(result.get("content", "")) > 200 else result.get("content", ""),
                    "similarity": result.get("score", 0.7),
                    "url": result.get("url")
                })

            # Format answer with clear external source indication
            formatted_answer = f"""ℹ️ **External Source (Web Search):**

{answer}

*This information is from web search results. Please verify with official documents or contact our sales team for specific details about Brigade projects.*"""

            return {
                "answer": formatted_answer,
                "sources": sources,
                "confidence": "Low (External)",
                "is_external": True,
                "search_query": search_query
            }

        except Exception as e:
            logger.error(f"Tavily search error: {e}", exc_info=True)
            # Fall back to LLM knowledge on error
            return self._llm_fallback(query, context, topic_hint)

    def _synthesize_answer(self, query: str, results: List[Dict]) -> str:
        """Synthesize answer from web search results using GPT-4."""
        context = "\n\n".join([
            f"**Source: {r.get('title', 'Unknown')}**\n{r.get('content', '')[:500]}"
            for r in results
        ])

        prompt = f"""Based on these web search results, answer the question concisely and accurately.

Search Results:
{context}

Question: {query}

Provide a clear, factual answer for a real estate sales context. If information is unavailable in the search results, say so. Keep the answer concise but comprehensive."""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                max_tokens=600,
                messages=[
                    {"role": "system", "content": "You are a helpful real estate assistant synthesizing web search results."},
                    {"role": "user", "content": prompt}
                ]
            )

            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"Error synthesizing answer: {e}")
            return "I found some information but couldn't synthesize it properly. Please contact our sales team."

    def _llm_fallback(
        self,
        query: str,
        context: Optional[str] = None,
        topic_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fall back to LLM general knowledge when Tavily unavailable."""
        try:
            system_prompt = """You are Pinclick Genie, a helpful real estate assistant.

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

**Note:** This is general real estate information. For specific details about properties, please contact the sales team."""

            user_message = f"""The user asked: "{query}"

Our internal documents didn't have specific information about this topic.
{f'Context: {context}' if context else ''}
{f'Topic: {topic_hint}' if topic_hint else ''}

Please provide helpful general information that would be useful for a real estate sales agent to know."""

            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.3,
                max_tokens=800
            )

            answer = response.choices[0].message.content

            formatted_answer = f"""📚 **General Knowledge:**

{answer}

*This is general real estate information. For specific details about Brigade properties, please contact our sales team.*"""

            return {
                "answer": formatted_answer,
                "source_type": "external",
                "sources": [{
                    "document": "General Real Estate Knowledge",
                    "section": "LLM Knowledge Base",
                    "page": None,
                    "excerpt": "This information is based on general real estate knowledge.",
                    "similarity": 0.5
                }],
                "confidence": "Low",
                "is_external": True
            }

        except Exception as e:
            logger.error(f"Error in LLM fallback: {e}")
            return self._fallback_response()

    def _fallback_response(self) -> Dict[str, Any]:
        """Return when all search methods fail."""
        return {
            "answer": "I couldn't find information about this online. Please contact our sales team for assistance with your specific query.",
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
