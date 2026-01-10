"""
Intent classification service to categorize user queries before retrieval.
Uses keyword detection + GPT-4 classification for intelligent routing.
"""

from openai import OpenAI
from config import settings, INTENT_EXAMPLES, PROPERTY_SEARCH_KEYWORDS
from typing import Literal
import logging
import re

logger = logging.getLogger(__name__)

IntentType = Literal["property_search", "project_fact", "sales_pitch", "comparison", "unsupported"]


class IntentClassifier:
    """Classifies user queries into predefined intent categories."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.model = settings.gpt_model

    def classify_intent(self, query: str) -> IntentType:
        """
        Classify the intent of a user query using keyword detection + GPT-4.

        Args:
            query: User's question

        Returns:
            Intent category: 'property_search', 'project_fact', 'sales_pitch', 'comparison', or 'unsupported'
        """
        query_lower = query.lower()

        # Priority 1: Fast keyword-based detection for property searches
        if self._is_property_search(query_lower):
            logger.info(f"Detected property_search intent via keywords: {query[:50]}...")
            return "property_search"

        # Priority 2: Fall back to GPT-4 classification for other intents
        try:
            system_prompt = self._build_system_prompt()
            user_message = f"Classify this query: {query}"

            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0.0,  # Deterministic classification
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=50
            )

            intent = response.choices[0].message.content.strip().lower()

            # Validate and map to IntentType
            if "property_search" in intent or "property" in intent or "search" in intent:
                return "property_search"
            elif "project_fact" in intent or "fact" in intent:
                return "project_fact"
            elif "sales_pitch" in intent or "pitch" in intent or "sales" in intent:
                return "sales_pitch"
            elif "comparison" in intent or "compare" in intent:
                return "comparison"
            elif "unsupported" in intent or "refuse" in intent or "risk" in intent:
                return "unsupported"
            else:
                # Default to project_fact for ambiguous cases
                logger.warning(f"Ambiguous intent classification: {intent}. Defaulting to project_fact")
                return "project_fact"

        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            # Default to project_fact on error
            return "project_fact"

    def _is_property_search(self, query_lower: str) -> bool:
        """
        Fast keyword-based detection for property search queries.

        Returns True if query matches property search patterns:
        - Has 2+ property search keywords
        - Contains BHK mention with price/location/action words
        """
        # Count matching keywords
        keyword_count = sum(1 for kw in PROPERTY_SEARCH_KEYWORDS if kw in query_lower)

        if keyword_count >= 2:
            return True

        # Check for BHK mentions with price/location/action words
        if re.search(r'\d+\s*bhk', query_lower):
            # BHK + price keywords
            if any(word in query_lower for word in ["under", "budget", "price", "cr", "crore", "lac", "lakh"]):
                return True
            # BHK + action keywords
            if any(word in query_lower for word in ["show", "list", "available", "options", "give me", "find"]):
                return True
            # BHK + location keywords
            if any(word in query_lower for word in ["in ", "at ", "near ", "bangalore", "whitefield", "road"]):
                return True

        return False

    def _build_system_prompt(self) -> str:
        """Build few-shot system prompt for intent classification."""
        prompt = """You are an intent classifier for a real estate sales chatbot.

Classify user queries into exactly ONE of these categories:

1. **property_search** - Queries asking to list/show/filter properties by criteria (unit type, price range, location, possession date, etc.)

2. **project_fact** - Factual questions about specific project details (RERA number, amenities, specifications, sustainability features, etc.)

3. **sales_pitch** - Requests for persuasive information or benefits (why buy here, what makes it unique, advantages, etc.)

4. **comparison** - Comparing multiple projects

5. **unsupported** - Questions we CANNOT answer (future predictions, ROI estimates, investment advice, legal advice, pricing trends, market forecasts, personal recommendations)

CRITICAL DISTINCTIONS:
- "show me 2bhk options" = property_search (listing/filtering)
- "what amenities does Brigade Citrine have?" = project_fact (specific project question)
- "why should I invest?" = sales_pitch (persuasive)

CRITICAL: Classify as 'unsupported' if the query asks about:
- Future property values or market trends
- ROI or investment returns
- "Should I buy?" or "Is this a good investment?"
- Legal or financial advice
- Price predictions

Examples:

"""
        # Add few-shot examples
        for intent, examples in INTENT_EXAMPLES.items():
            prompt += f"\n**{intent}**:\n"
            for example in examples[:3]:  # Limit to 3 examples per category
                prompt += f"- {example}\n"

        prompt += """
Your response must be ONLY the category name: property_search, project_fact, sales_pitch, comparison, or unsupported.
"""

        return prompt


# Global classifier instance
intent_classifier = IntentClassifier()
