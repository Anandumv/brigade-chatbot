"""
Intent classification service to categorize user queries before retrieval.
Uses few-shot GPT-4 classification to prevent off-topic questions.
"""

from openai import OpenAI
from config import settings, INTENT_EXAMPLES
from typing import Literal
import logging

logger = logging.getLogger(__name__)

IntentType = Literal["project_fact", "sales_pitch", "comparison", "unsupported"]


class IntentClassifier:
    """Classifies user queries into predefined intent categories."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.model = settings.gpt_model

    def classify_intent(self, query: str) -> IntentType:
        """
        Classify the intent of a user query.

        Args:
            query: User's question

        Returns:
            Intent category: 'project_fact', 'sales_pitch', 'comparison', or 'unsupported'
        """
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
            if "project_fact" in intent or "fact" in intent:
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

    def _build_system_prompt(self) -> str:
        """Build few-shot system prompt for intent classification."""
        prompt = """You are an intent classifier for a real estate sales chatbot.

Classify user queries into exactly ONE of these categories:

1. **project_fact** - Factual questions about project details (RERA number, location, unit sizes, amenities, specifications, sustainability features, etc.)

2. **sales_pitch** - Requests for persuasive information or benefits (why buy here, what makes it unique, advantages, etc.)

3. **comparison** - Comparing multiple projects

4. **unsupported** - Questions we CANNOT answer (future predictions, ROI estimates, investment advice, legal advice, pricing trends, market forecasts, personal recommendations)

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
Your response must be ONLY the category name: project_fact, sales_pitch, comparison, or unsupported.
"""

        return prompt


# Global classifier instance
intent_classifier = IntentClassifier()
