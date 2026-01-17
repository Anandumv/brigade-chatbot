"""
Context Injection Service for Continuous Conversations.

Enriches vague user queries with session context to enable natural conversation flow.
Prevents the chatbot from asking repetitive clarifying questions.
"""

import logging
from typing import Optional
from services.session_manager import ConversationSession

logger = logging.getLogger(__name__)


def is_vague_query(query: str) -> bool:
    """
    Determine if a query is too vague and needs context enrichment.
    
    Vague queries include:
    - Very short (< 5 words)
    - Follow-up questions without subjects
    - Requests for "more info" without specifying what
    """
    query_lower = query.lower().strip()
    word_count = len(query.split())
    
    # Short queries that might be vague
    if word_count < 5:
        # Check for vague patterns
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
    """
    if not session:
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
