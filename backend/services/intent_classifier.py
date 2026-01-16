"""
Intent classification service to categorize user queries before retrieval.
Uses keyword detection + GPT-4 classification for intelligent routing.
"""

from openai import OpenAI
from config import settings, INTENT_EXAMPLES, PROPERTY_SEARCH_KEYWORDS, SALES_FAQ_KEYWORDS, SALES_OBJECTION_KEYWORDS
from typing import Literal
import logging
import re

logger = logging.getLogger(__name__)

# Extended intent types including sales-specific intents
IntentType = Literal[
    "property_search", 
    "project_fact", 
    "sales_pitch", 
    "comparison", 
    "unsupported",
    "sales_faq",
    "sales_objection",
    "greeting"
]


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
            Intent category including sales_faq and sales_objection
        """
        query_lower = query.lower().strip()

        # Priority 0: Handle greetings - return greeting intent
        greeting_words = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'hola', 'namaste']
        # Check if query starts with a greeting or is just a greeting
        cleaned_query = re.sub(r'[^\w\s]', '', query_lower)  # Remove punctuation
        if any(cleaned_query.startswith(w) for w in greeting_words) and len(cleaned_query.split()) <= 4:
            logger.info(f"Detected greeting: {query}")
            return "greeting"

        # Priority 1: Fast keyword-based detection for property searches
        if self._is_property_search(query_lower):
            logger.info(f"Detected property_search intent via keywords: {query[:50]}...")
            return "property_search"
        
        # Priority 2: Detect sales objection queries (fast keyword match)
        # CHECK THIS BEFORE FAQ to capture negations like "I don't want"
        if self._is_sales_objection(query_lower):
            logger.info(f"Detected sales_objection intent via keywords: {query[:50]}...")
            return "sales_objection"
        
        # Priority 3: Detect sales FAQ queries (fast keyword match)
        if self._is_sales_faq(query_lower):
            logger.info(f"Detected sales_faq intent via keywords: {query[:50]}...")
            return "sales_faq"

        # Priority 4: Detect sales pitch queries (fast keyword match)
        if self._is_sales_pitch(query_lower):
             logger.info(f"Detected sales_pitch intent via keywords: {query[:50]}...")
             return "sales_pitch"

        # Priority 5: Fall back to GPT-4 classification for other intents
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

        # Handle 'show more' pagination intent
        if any(w in query_lower for w in ["show more", "more options", "see more", "other projects", "remaining"]):
            return True

        # Handle explicit project names / developers (ensure they route to flow engine)
        if any(w in query_lower for w in ["brigade", "sobha", "prestige", "godrej", "purva", "sbr", "abhee", "mana", "century", "sumadhura", "vaswani", "dsr"]):
             return True

        return False

    def _is_sales_faq(self, query_lower: str) -> bool:
        """
        Detect sales FAQ queries using keyword matching.
        
        Matches queries about:
        - Budget stretching
        - Location alternatives
        - Under-construction vs ready-to-move
        - Meeting/site visit requests
        - Pinclick value proposition
        """
        # Check for sales FAQ keywords
        for keyword in SALES_FAQ_KEYWORDS:
            if keyword in query_lower:
                return True
        
        # Additional pattern checks
        if "worth" in query_lower and ("invest" in query_lower or "buying" in query_lower):
            return True
            
        faq_patterns = [
            r'why\s+(?:should|would|do)\s+.*(?:meet|visit|pinclick)',
            r'(?:schedule|arrange|book)\s+(?:a\s+)?(?:meeting|visit|call)',
            r'(?:can|want|need)\s+(?:to\s+)?(?:meet|visit|see)',
            r'(?:stretch|increase|extend)\s+(?:my\s+)?budget',
            r'(?:other|different|alternate)\s+(?:location|area)',
            r'(?:ready\s+to\s+move|under\s+construction)',
        ]
        
        for pattern in faq_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def _is_sales_objection(self, query_lower: str) -> bool:
        """
        Detect sales objection queries using keyword matching.
        
        Matches queries about:
        - Budget concerns (too expensive, can't afford)
        - Location concerns (too far, wrong area)
        - Possession concerns (too late, need immediately)
        - Trust concerns (construction risk, delays)
        """
        # Check for sales objection keywords
        for keyword in SALES_OBJECTION_KEYWORDS:
            if keyword in query_lower:
                return True
        
        # Additional objection patterns
        objection_patterns = [
            r'(?:too|very)\s+(?:\w+\s+)*(?:expensive|costly|high|far)',
            r"(?:can't|cannot|won't|don't|do not)\s+(?:afford|wait|trust)",
            r'(?:out\s+of|beyond|exceeds?|above|more\s+than)\s+(?:my\s+)?budget',
            r'\b(?:broke|cheap|poor|money|funds)\b',  # Slang triggers
            r'(?:not|don\'t)\s+(?:like|want|prefer)\s+(?:this|that)\s+(?:location|area|project)',
            r'(?:scared|worried|concerned)\s+(?:about|of)\s+(?:delay|construction)',
            r'(?:congested|traffic|crowded|pollution)',
            r"(?:do not|don't|not)\s+(?:want|like|prefer|need)\s+(?:under|uc|construction|waiting|ready)",
        ]
        
        for pattern in objection_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False


    def _is_sales_pitch(self, query_lower: str) -> bool:
        """
        Detect sales pitch queries (pitch me, tell me about, why buy).
        """
        pitch_keywords = ["pitch", "why buy", "why should i", "give me a reason", "unique selling", "usp", "investment potential", "tell me about"]
        if any(kw in query_lower for kw in pitch_keywords):
            return True
        return False

    def _build_system_prompt(self) -> str:
        """Build few-shot system prompt for intent classification."""
        prompt = """You are an intent classifier for a real estate sales chatbot.

Classify user queries into exactly ONE of these categories:

1. **property_search** - Queries asking to list/show/filter properties by criteria (unit type, price range, location, possession date, etc.)

2. **project_fact** - Factual questions about specific project details (RERA number, amenities, specifications, sustainability features, etc.)

3. **sales_faq** - Questions about budget stretching, location switching, under-construction benefits, face-to-face meetings, site visits, or Pinclick value.

4. **sales_objection** - Objections related to price ("too expensive"), location ("too far"), possession time ("need ready to move"), or trust ("construction risk").

5. **comparison** - Comparing multiple projects

6. **unsupported** - Questions we CANNOT answer (future predictions, ROI estimates, investment advice, legal advice, pricing trends, market forecasts, personal recommendations)

CRITICAL DISTINCTIONS:
- "show me 2bhk options" = property_search (listing/filtering)
- "what amenities does Brigade Citrine have?" = project_fact (specific project question)
- "how can I stretch my budget?" = sales_faq
- "this is too expensive" = sales_objection
- "why should I invest?" = sales_faq (persuasive)

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
