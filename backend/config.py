"""
Configuration management for the Real Estate Sales Intelligence Chatbot.
Pixeltable-only mode - Supabase is optional.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI Configuration
    openai_api_key: str
    openai_base_url: Optional[str] = "https://api.openai.com/v1"  # OpenAI direct API

    # Tavily Configuration (for web search)
    tavily_api_key: Optional[str] = "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"

    # Supabase Configuration (OPTIONAL - only for hybrid mode)
    supabase_url: Optional[str] = None
    supabase_key: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # Application Configuration
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Vector Search Configuration
    similarity_threshold: float = 0.5
    top_k_results: int = 5
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536

    # LLM Configuration
    gpt_model: str = "gpt-4-turbo-preview"  # OpenAI model name
    llm_model: Optional[str] = None  # Alias for gpt_model from env
    max_tokens: int = 1500

    @property
    def effective_gpt_model(self) -> str:
        """Returns llm_model (cleaned) or fallback to gpt_model."""
        model = self.llm_model or self.gpt_model
        if model and "/" in model:
            # Strip prefixes like 'openai/' which are common in proxy configs but invalid for direct OpenAI API
            return model.split("/")[-1]
        return model
    temperature: float = 0.1  # Low temperature for factual responses

    # Response Time Configuration
    target_response_time: int = 3000  # milliseconds

    # Pixeltable Configuration (PRIMARY DATABASE)
    use_pixeltable: str = "true"  # Default to Pixeltable-only mode
    pixeltable_data_dir: Optional[str] = None  # Custom data directory
    pixeltable_mode: str = "exclusive"  # "exclusive" or "hybrid"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra env vars


# Global settings instance
settings = Settings()


# Confidence thresholds
CONFIDENCE_THRESHOLDS = {
    "high": 0.65,      # Top chunk similarity >= 0.65 AND multiple chunks agree
    "medium": 0.50,    # Similarity 0.50-0.64 OR synthesis from 2+ chunks
    "low": 0.35        # Below 0.50 = refusal
}

# Intent classification examples for few-shot learning
INTENT_EXAMPLES = {
    "property_search": [
        "show me 2bhk options",
        "2bhk under 3cr in Bangalore",
        "3bhk ready to move",
        "affordable flats possession 2027",
        "what are the available configurations",
        "list all 2bhk units",
        "properties in whitefield under 5cr",
        "budget 2bhk in East Bangalore",
    ],
    "project_fact": [
        "What is the RERA number for Brigade Citrine?",
        "How many units are in the project?",
        "What is the location of the project?",
        "What amenities does Brigade Citrine have?",
        "Is Brigade Citrine IGBC certified?",
        "What is the possession date?",
    ],
    "sales_pitch": [
        "Why should I buy here?",
        "What makes this project unique?",
        "Tell me about the sustainability features",
        "What are the advantages of this location?",
        "Why invest in Brigade Citrine?",
    ],
    "comparison": [
        "Compare Brigade Citrine and Avalon",
        "Which project has better amenities?",
        "Difference between the two projects",
    ],
    "unsupported": [
        "What will be the property value in 5 years?",
        "Is this a good investment?",
        "Will prices go up?",
        "What ROI can I expect?",
        "Give me legal advice",
        "Should I take a loan?",
    ],
    # New sales FAQ intents
    "sales_faq": [
        "how to stretch my budget",
        "how to convince for other location",
        "why under construction",
        "ready to move vs under construction",
        "why face to face meeting",
        "what does pinclick do",
        "why pinclick",
        "schedule site visit",
        "arrange meeting",
    ],
    # Objection handling intents
    "sales_objection": [
        "too expensive",
        "can't afford this",
        "out of my budget",
        "don't like this location",
        "area is too far",
        "possession is too late",
        "don't want under construction",
        "want ready to move only",
    ],
}

# Sales FAQ keywords for quick detection
# Note: Removed "under construction", "ready to move", "possession" to prevent overlap with objections
SALES_OBJECTION_KEYWORDS = [
    "too expensive", "costly", "high price", "can't afford",
    "out of budget", "beyond budget", "budget is less",
    "too far", "far from", "wrong location", "different area",
    "can't wait", "need immediately", "urgent", "too late",
    "don't trust", "scared of delay", "construction risk",
]

# Export keywords for fast classification
PROPERTY_SEARCH_KEYWORDS = [
    "bhk", "bedroom", "apartment", "flat", "villa", "plot", "residence",
    "property", "home", "house", "project", "unit", "floor", "facing",
    "sqft", "square feet", "budget", "price", "cost", "lakh", "crore",
    "possession", "ready to move", "under construction", "move in",
    "location", "area", "locality", "neighborhood", "zone", "whitefield",
    "bangalore", "sarjapur", "north", "east", "south", "west"
]

SALES_FAQ_KEYWORDS = INTENT_EXAMPLES["sales_faq"] + [
    "stretch", "budget", "location", "area", "meeting", "visit", "site",
    "pinclick", "brokerage", "commission", "appointment", "schedule",
    "nearby", "near me", "closest", "distance", "around here", "radius",
    # Natural language follow-up queries (route to flow engine for LLM understanding)
    "more pointers", "pointers", "tell me more", "more details", "more information",
    "what else", "anything else", "elaborate", "explain more", "more about"
]

# Refusal messages
REFUSAL_MESSAGES = {
    "no_relevant_info": "This information is not available in the project documents or approved sources.",
    "future_prediction": "I cannot provide predictions about future property values, ROI, or market trends.",
    "legal_advice": "I cannot provide legal or financial advice. Please consult with appropriate professionals.",
    "conflicting_info": "I found conflicting information in the sources. Please contact our sales team for clarification.",
    "insufficient_confidence": "I cannot provide a confident answer based on the available information.",
}
