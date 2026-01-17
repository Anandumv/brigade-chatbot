"""
Context Injection Service for Continuous Conversations.

Enriches vague user queries with session context to enable natural conversation flow.
Prevents the chatbot from asking repetitive clarifying questions.
"""

import logging
import re
from typing import Optional
from services.session_manager import ConversationSession

logger = logging.getLogger(__name__)


# Generic question patterns that should NEVER get project context
GENERIC_PATTERNS = [
    # Finance terms
    "what is emi", "how to calculate emi", "emi calculator", "calculate emi",
    "what is home loan", "how to apply loan", "loan eligibility", "loan process",
    "interest rate", "down payment", "processing fee", "loan tenure",
    "home loan interest", "emi calculation", "loan amount",
    
    # Legal/Process
    "what is rera", "how to register", "stamp duty", "registration fee",
    "registration process", "legal documents", "sale deed", "agreement",
    "property registration", "title deed", "encumbrance certificate",
    
    # General real estate
    "what is carpet area", "what is built up area", "super built up",
    "difference between", "what is the difference", "how to",
    "what is the process", "what does", "how does", "why is",
    
    # Services
    "who is pinclick", "what services", "how do you help", "what do you do",
    "your commission", "fees", "charges", "how pinclick", "pinclick services",
    
    # General questions
    "what is", "how to", "why is", "when to", "who is", "where is"
]


# Bangalore location names for comparison detection
BANGALORE_LOCATIONS = [
    "whitefield", "sarjapur", "electronic city", "hebbal", "yeshwantpur",
    "koramangala", "indiranagar", "jayanagar", "hsr", "btm", "marathahalli",
    "bellandur", "outer ring road", "bannerghatta", "hennur", "yelahanka",
    "devanahalli", "kengeri", "jp nagar", "mg road", "brigade road",
    "rajajinagar", "malleshwaram", "basavanagudi", "kr puram", "varthur",
    "chandapura", "hosur road", "old madras road", "tumkur road", "mysore road",
    "kanakpura road", "north bangalore", "south bangalore", "east bangalore",
    "west bangalore", "central bangalore"
]


def is_location_comparison_query(query: str) -> bool:
    """
    Detect if query is comparing locations/areas (should be generic).
    
    Examples:
    - "why whitefield is better than Sarjapur"
    - "Whitefield vs Sarjapur"
    - "which is better whitefield or sarjapur"
    - "why should I buy in whitefield"
    - "is whitefield location good"
    - "tell me about whitefield area"
    
    Returns True for location comparison questions.
    """
    query_lower = query.lower().strip()
    
    # Check if query mentions any Bangalore locations
    has_location = any(loc in query_lower for loc in BANGALORE_LOCATIONS)
    
    if not has_location:
        return False
    
    # Pattern 1: "X vs Y", "X or Y", "better than", "compared to"
    comparison_patterns = [
        " vs ", " versus ", " or ", "better than", "compared to",
        "difference between", "compare", "comparison"
    ]
    if any(pattern in query_lower for pattern in comparison_patterns):
        return True
    
    # Pattern 2: "why should I buy in X", "is X good", "tell me about X area"
    area_info_patterns = [
        "why should i buy in", "is .* good", "is .* better",
        "tell me about .* area", "tell me about .* location",
        "why .* is good", "why .* is better"
    ]
    for pattern in area_info_patterns:
        if re.search(pattern, query_lower):
            return True
    
    # Pattern 3: "why X better/good" (without explicit property mention)
    if "why" in query_lower and has_location:
        if "better" in query_lower or "good" in query_lower or "best" in query_lower:
            # Make sure it's not about a specific project
            # "why Brigade Citrine is better" should NOT match
            # "why Whitefield is better" SHOULD match
            project_indicators = ["brigade", "sobha", "prestige", "godrej", 
                                "citrine", "avalon", "neopolis", "project"]
            if not any(proj in query_lower for proj in project_indicators):
                return True
    
    return False


def is_generic_question(query: str) -> bool:
    """
    Check if query is a generic question that shouldn't use project context.
    
    Generic questions are about general topics (EMI, RERA, loans, etc.) that
    should receive generic answers, NOT be forced into project-specific context.
    
    Examples:
    - "What is EMI?" → Generic (True)
    - "How to apply for loan?" → Generic (True)
    - "What is RERA?" → Generic (True)
    - "give more points" → Not Generic (False) - should use context
    - "tell me more" → Not Generic (False) - should use context
    """
    # CRITICAL: Check for location comparison first
    # "why whitefield is better than Sarjapur" should be generic
    if is_location_comparison_query(query):
        return True
    
    query_lower = query.lower().strip()
    
    # Check against generic patterns
    for pattern in GENERIC_PATTERNS:
        if pattern in query_lower:
            return True
    
    # Check for question words WITHOUT property context
    question_words = ["what is", "how to", "why is", "when to", "who is", "where is", 
                     "what are", "how do", "what does", "how does"]
    property_words = ["project", "property", "apartment", "flat", "home", "villa", 
                     "this", "that", "about", "citrine", "avalon", "brigade", "sobha",
                     "here", "these", "those"]
    
    has_question_word = any(qw in query_lower for qw in question_words)
    has_property_context = any(pw in query_lower for pw in property_words)
    
    # If it's a question WITHOUT property words → Generic
    # e.g., "What is EMI?" has "what is" but no property words → Generic
    if has_question_word and not has_property_context:
        return True
    
    return False


def is_vague_query(query: str) -> bool:
    """
    Determine if a query is too vague and needs context enrichment.
    
    Vague queries include:
    - Very short (< 5 words)
    - Follow-up questions without subjects
    - Requests for "more info" without specifying what
    
    NOTE: Generic questions are NOT vague - they're specific about general topics.
    """
    # FIRST: Check if it's a generic question
    if is_generic_question(query):
        return False  # NOT vague, it's specific about a general topic
    
    query_lower = query.lower().strip()
    word_count = len(query.split())
    
    # Short queries that might be vague
    if word_count < 5:
        # Check for vague patterns (property-related follow-ups)
        vague_patterns = [
            "give more points",
            "more points",
            "tell me more",
            "more details",
            "more info",
            "elaborate",
            "continue",
            "go on",
            "what else",
            "anything else",
            "more about",
            "more on",
            "tell more",
            "give more",
            "show more",
            "show similar",
            "similar properties",
            "more",
            "how about",
            "what about",
            "and"
        ]
        
        for pattern in vague_patterns:
            if pattern in query_lower:
                return True
    
    # Single word queries (except greetings)
    if word_count == 1 and query_lower not in ["hi", "hello", "hey", "yes", "no", "ok", "thanks"]:
        return True
    
    return False


def has_explicit_project_mention(query: str, known_projects: list) -> bool:
    """Check if query explicitly mentions a project name."""
    query_lower = query.lower()
    
    # Common project keywords
    project_keywords = [
        "avalon", "citrine", "neopolis", "brigade", "sobha", "prestige", 
        "godrej", "birla", "evara", "folium", "eden", "serene", "woods",
        "panache", "7 gardens", "ojasvi", "calista", "sumadhura"
    ]
    
    for keyword in project_keywords:
        if keyword in query_lower:
            return True
    
    # Check against known projects from session
    for project in known_projects:
        if project and project.lower() in query_lower:
            return True
    
    return False


def enrich_query_with_context(
    query: str,
    session: Optional[ConversationSession]
) -> tuple[str, bool]:
    """
    Enrich a vague query with session context.
    
    Args:
        query: Original user query
        session: Current conversation session with context
    
    Returns:
        Tuple of (enriched_query, was_enriched)
    """
    if not session:
        return query, False
    
    # CRITICAL: Don't enrich generic questions
    # Generic questions like "What is EMI?" should remain generic
    if is_generic_question(query):
        logger.info(f"Skipping context injection for generic question: '{query}'")
        return query, False
    
    # Don't enrich if query already has explicit project mention
    if has_explicit_project_mention(query, session.interested_projects):
        return query, False
    
    # Don't enrich if not vague
    if not is_vague_query(query):
        return query, False
    
    enriched = query
    was_enriched = False
    
    # Strategy 1: Add last discussed project
    if session.interested_projects:
        last_project = session.interested_projects[-1]
        enriched = f"{query} about {last_project}"
        was_enriched = True
        logger.info(f"Context Injection: Added project context - '{query}' → '{enriched}'")
    
    # Strategy 2: Add topic context if available
    elif session.last_topic and not session.interested_projects:
        # If we have a topic but no project, add topic context
        enriched = f"{query} regarding {session.last_topic}"
        was_enriched = True
        logger.info(f"Context Injection: Added topic context - '{query}' → '{enriched}'")
    
    # Strategy 3: Add filter context if available
    elif session.current_filters and not session.interested_projects:
        # Build filter context string
        filter_parts = []
        if session.current_filters.get('configuration'):
            filter_parts.append(session.current_filters['configuration'])
        if session.current_filters.get('location'):
            filter_parts.append(f"in {session.current_filters['location']}")
        
        if filter_parts:
            filter_context = " ".join(filter_parts)
            enriched = f"{query} for {filter_context} properties"
            was_enriched = True
            logger.info(f"Context Injection: Added filter context - '{query}' → '{enriched}'")
    
    return enriched, was_enriched


def inject_context_metadata(
    query: str,
    session: Optional[ConversationSession]
) -> dict:
    """
    Create metadata dict with context for handlers.
    
    Returns context that handlers can use even if query isn't enriched.
    This allows handlers to make intelligent decisions based on conversation state.
    """
    if not session:
        return {
            "has_context": False,
            "enriched_query": query,
            "was_enriched": False
        }
    
    enriched_query, was_enriched = enrich_query_with_context(query, session)
    
    return {
        "has_context": True,
        "enriched_query": enriched_query,
        "was_enriched": was_enriched,
        "original_query": query,
        
        # Context for handlers
        "last_project": session.interested_projects[-1] if session.interested_projects else None,
        "last_topic": session.last_topic,
        "last_intent": session.last_intent,
        "current_filters": session.current_filters,
        "conversation_phase": session.conversation_phase,
        "message_count": len(session.messages),
        
        # Rich context
        "interested_projects": session.interested_projects,
        "objections_raised": session.objections_raised
    }


def should_use_gpt_fallback(
    query: str,
    session: Optional[ConversationSession],
    intent_confidence: float
) -> bool:
    """
    Determine if we should skip specific handlers and go directly to GPT fallback.
    
    Use GPT fallback when:
    1. Query is vague AND session has context AND confidence is low
    2. This prevents asking clarifying questions when context exists
    
    NOTE: Generic questions should NOT use GPT fallback with project context.
    """
    if not session:
        return False
    
    # Generic questions should be handled normally, not with project context fallback
    if is_generic_question(query):
        return False
    
    # If confidence is high, trust the handler
    if intent_confidence >= 0.8:
        return False
    
    # If query is vague and we have context, use GPT to continue naturally
    if is_vague_query(query) and (session.interested_projects or session.last_topic):
        logger.info(f"Routing vague query to GPT fallback (has context, confidence={intent_confidence})")
        return True
    
    # If confidence is low but we have conversation context
    if intent_confidence < 0.6 and len(session.messages) >= 2:
        logger.info(f"Routing low-confidence query to GPT fallback (confidence={intent_confidence}, context exists)")
        return True
    
    return False
