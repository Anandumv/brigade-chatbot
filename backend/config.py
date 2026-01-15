"""
Configuration management for the Real Estate Sales Intelligence Chatbot.
Pixeltable-only mode - Supabase is optional.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI/OpenRouter Configuration
    openai_api_key: str
    openai_base_url: Optional[str] = "https://openrouter.ai/api/v1"  # OpenRouter by default

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
    gpt_model: str = "openai/gpt-4-turbo-preview"  # OpenRouter format
    llm_model: Optional[str] = None  # Alias for gpt_model from env
    max_tokens: int = 1500
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
SALES_FAQ_KEYWORDS = [
    "stretch budget", "extend budget", "increase budget",
    "other location", "different location", "alternate location",
    "why under construction", "benefits of under construction",
    "face to face", "meet in person", "schedule meeting",
    "site visit", "visit site", "see property",
    "pinclick value", "why pinclick", "about pinclick",
]

# Objection keywords for detection
SALES_OBJECTION_KEYWORDS = [
    "too expensive", "costly", "high price", "can't afford",
    "out of budget", "beyond budget", "budget is less",
    "too far", "far from", "wrong location", "different area",
    "can't wait", "need immediately", "urgent", "too late",
    "don't trust", "scared of delay", "construction risk",
]

# Property search detection keywords
PROPERTY_SEARCH_KEYWORDS = [
    "show me", "list", "available", "options", "configurations",
    "bhk", "bedroom", "units", "flats", "apartments",
    "under", "budget", "price range", "affordable",
    "ready to move", "possession", "immediate"
]

# Refusal messages
REFUSAL_MESSAGES = {
    "no_relevant_info": "This information is not available in the project documents or approved sources.",
    "future_prediction": "I cannot provide predictions about future property values, ROI, or market trends.",
    "legal_advice": "I cannot provide legal or financial advice. Please consult with appropriate professionals.",
    "conflicting_info": "I found conflicting information in the sources. Please contact our sales team for clarification.",
    "insufficient_confidence": "I cannot provide a confident answer based on the available information.",
}
