"""
Unified GPT Sales Consultant for Continuous Conversation.

This module provides a single handler for ALL conversational queries, replacing
the fragmented routing through flow_engine, intelligent_sales, and other handlers.

Key Features:
- Always conversational (never asks clarifying questions)
- Context-aware (references shown projects, budget, requirements)
- Goal-oriented (knows if user wants info, has objection, or is comparing)
- Memory (updates session state after each response)
"""

import logging
from typing import Dict, List, Optional
from openai import OpenAI
from config import settings
from services.session_manager import ConversationSession  # Fixed import

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url
)


async def generate_consultant_response(
    query: str,
    session: ConversationSession,
    intent: str = None
) -> str:
    """
    Unified GPT sales consultant for continuous conversation.

    Args:
        query: User's query
        session: Full session state with history, context, projects
        intent: Optional intent hint (faq, objection, etc.)

    Returns:
        Natural conversational response
    """

    # Build comprehensive context
    context = build_consultant_context(session)

    # Determine conversation goal
    goal = determine_conversation_goal(intent, query, session)

    # Get conversation history
    conversation_history = []
    if session and hasattr(session, 'messages'):
        conversation_history = session.messages[-10:]

    # Generate response with GPT
    response = await call_gpt_consultant(
        query=query,
        conversation_history=conversation_history,
        context=context,
        goal=goal
    )

    logger.info(f"Generated consultant response (intent={intent}, session={session.session_id if session else 'None'})")

    return response


def build_consultant_context(session: ConversationSession) -> dict:
    """Build rich context for GPT consultant."""

    if not session:
        return {}

    context = {
        # Shown Projects (CRITICAL)
        "last_shown_projects": [],

        # User Requirements
        "requirements": {},

        # Conversation State
        "interested_projects": [],
        "objections_raised": [],
        "last_topic": None,
        "conversation_phase": None,

        # Conversation History
        "recent_messages": [],
        "messages_count": 0
    }

    # Extract shown projects
    if hasattr(session, 'last_shown_projects') and session.last_shown_projects:
        context["last_shown_projects"] = [
            {
                "name": p.get("name", "Unknown"),
                "price": f"₹{p.get('budget_min', 0)/100:.1f} - ₹{p.get('budget_max', 0)/100:.1f} Cr",
                "config": p.get("configuration", "N/A"),
                "location": p.get("location", "N/A"),
                "highlights": p.get("usp", "")[:200]  # Truncate to avoid token overflow
            }
            for p in session.last_shown_projects[-5:]  # Last 5 projects
        ]

    # Extract user requirements
    if hasattr(session, 'current_filters') and session.current_filters:
        context["requirements"] = {
            "configuration": session.current_filters.get("configuration"),
            "budget_max": session.current_filters.get("budget_max"),
            "location": session.current_filters.get("location")
        }

    # Extract conversation state
    if hasattr(session, 'interested_projects'):
        context["interested_projects"] = session.interested_projects

    if hasattr(session, 'objections_raised'):
        context["objections_raised"] = session.objections_raised

    if hasattr(session, 'last_topic'):
        context["last_topic"] = session.last_topic

    if hasattr(session, 'conversation_phase'):
        context["conversation_phase"] = session.conversation_phase

    # Extract conversation history
    if hasattr(session, 'messages'):
        context["recent_messages"] = session.messages[-10:]
        context["messages_count"] = len(session.messages)

    return context


def determine_conversation_goal(intent: str, query: str, session: ConversationSession) -> str:
    """
    Determine what the user wants to achieve in this conversation turn.

    Returns goal prompt for GPT.
    """

    if not intent:
        # Default: Continue conversation naturally
        if session and hasattr(session, 'last_topic') and session.last_topic:
            return f"Continue discussing {session.last_topic} naturally"
        else:
            return "Continue the property search conversation naturally"

    # Intent-based goals
    if intent == "sales_faq":
        return "Answer the user's question about the home buying process, financing, or services"

    elif intent == "sales_objection":
        objection_type = detect_objection_type(query)  # budget, location, possession, trust
        return f"Handle the user's {objection_type} concern persuasively without being pushy"

    elif intent == "more_info_request":
        # Check if about specific project or general
        if session and hasattr(session, 'interested_projects') and session.interested_projects:
            project = session.interested_projects[-1]
            return f"Provide more insights about {project} - selling points, advantages, investment potential"
        else:
            return "Provide helpful information about real estate investment in general"

    elif intent == "comparison":
        if session and hasattr(session, 'interested_projects') and len(session.interested_projects) >= 2:
            return f"Compare {', '.join(session.interested_projects[-2:])} objectively"
        else:
            return "Help user compare options if multiple projects were shown"

    elif intent == "meeting_request" or intent == "site_visit":
        return "Help user schedule a site visit or meeting - explain process, benefits, and get preferred time"

    elif intent == "greeting":
        return "Greet warmly and offer to help find their ideal property"

    else:
        # Default: Continue conversation naturally
        if session and hasattr(session, 'last_topic') and session.last_topic:
            return f"Continue discussing {session.last_topic} naturally"
        else:
            return "Continue the property search conversation naturally"


def detect_objection_type(query: str) -> str:
    """Detect the type of objection from the query."""

    query_lower = query.lower()

    if any(word in query_lower for word in ["expensive", "costly", "budget", "price", "afford", "cheap"]):
        return "budget"
    elif any(word in query_lower for word in ["location", "far", "distance", "commute", "traffic"]):
        return "location"
    elif any(word in query_lower for word in ["possession", "delivery", "delay", "when", "timeline", "construction"]):
        return "possession"
    elif any(word in query_lower for word in ["trust", "fraud", "scam", "legitimate", "reliable", "rera"]):
        return "trust"
    else:
        return "general"


def format_context_for_prompt(context: dict) -> str:
    """Format context dictionary into readable prompt section."""

    lines = []

    # Shown projects
    if context.get("last_shown_projects"):
        lines.append("**PROJECTS SHOWN TO USER:**")
        for i, proj in enumerate(context["last_shown_projects"], 1):
            lines.append(f"{i}. {proj['name']}")
            lines.append(f"   - Price: {proj['price']}")
            lines.append(f"   - Config: {proj['config']}")
            lines.append(f"   - Location: {proj['location']}")
            if proj.get("highlights"):
                lines.append(f"   - Highlights: {proj['highlights']}")
        lines.append("")

    # User requirements
    req = context.get("requirements", {})
    if any(req.values()):
        lines.append("**USER REQUIREMENTS:**")
        if req.get("configuration"):
            lines.append(f"- Configuration: {req['configuration']}")
        if req.get("budget_max"):
            lines.append(f"- Budget: Up to ₹{req['budget_max']} Cr")
        if req.get("location"):
            lines.append(f"- Location: {req['location']}")
        lines.append("")

    # Interested projects
    if context.get("interested_projects"):
        lines.append(f"**INTERESTED IN:** {', '.join(context['interested_projects'])}")
        lines.append("")

    # Objections raised
    if context.get("objections_raised"):
        lines.append(f"**OBJECTIONS RAISED:** {', '.join(context['objections_raised'])}")
        lines.append("")

    # Current topic
    if context.get("last_topic"):
        lines.append(f"**CURRENT TOPIC:** {context['last_topic']}")
        lines.append("")

    # Conversation phase
    if context.get("conversation_phase"):
        lines.append(f"**CONVERSATION PHASE:** {context['conversation_phase']}")
        lines.append("")

    # Messages count
    if context.get("messages_count"):
        lines.append(f"**CONVERSATION TURNS:** {context['messages_count']}")
        lines.append("")

    if not lines:
        return "New conversation - no prior context"

    return "\n".join(lines)


async def call_gpt_consultant(
    query: str,
    conversation_history: List[Dict],
    context: dict,
    goal: str
) -> str:
    """
    Call GPT with unified consultant prompt.
    """

    # Build context section
    context_section = format_context_for_prompt(context)

    system_prompt = f"""You are a senior real estate sales consultant at Pinclick, having a live conversation with a potential homebuyer in Bangalore.

CONVERSATION CONTEXT:
{context_section}

YOUR GOAL FOR THIS TURN:
{goal}

CRITICAL RULES:
1. **CONTINUOUS CONVERSATION**: Never ask "What would you like to know?" or clarifying questions
2. **CONTEXT-AWARE**: Reference projects you've shown them, their budget, their requirements
3. **SPECIFIC, NOT GENERIC**: Use actual project names, prices, and features from context
4. **NATURAL FLOW**: Build on previous messages, don't restart the conversation
5. **SALES-FOCUSED**: Guide toward decision, site visit, or next step
6. **HONEST**: Don't invent facts not in context - acknowledge if you don't have specific info

CONVERSATION STYLE:
- Consultative, not salesy
- Specific numbers and comparisons
- Address their actual situation
- End with relevant next step

WHAT YOU HAVE ACCESS TO:
- Projects shown to them (in context above)
- Their requirements and budget
- Previous conversation
- General real estate knowledge

WHAT YOU DON'T DO:
- Ask what they're looking for (you already know)
- Repeat project lists (they've seen them)
- Generic advice without project specifics
- Break conversation flow

RESPOND NATURALLY:
"""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    if conversation_history:
        messages.extend(conversation_history[-10:])

    # Add current query
    messages.append({"role": "user", "content": query})

    try:
        # Call GPT
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=messages,
            temperature=0.7,
            max_tokens=600
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"GPT consultant call failed: {e}")

        # Fallback response
        if context.get("last_shown_projects"):
            project_name = context["last_shown_projects"][0]["name"]
            return f"""I'd be happy to discuss {project_name} in more detail.

This is an excellent property that matches your requirements. Based on what you've shared, I think it offers great value in terms of location, amenities, and pricing.

Would you like to know more about specific aspects like the location advantages, investment potential, or amenities? Or shall we schedule a site visit?"""
        else:
            return """I'm here to help you find the perfect property in Bangalore!

I can assist with:
- Property search based on your budget and preferences
- Project details and comparisons
- Location insights and connectivity
- Investment advice and ROI potential
- Site visit scheduling

What would you like to explore?"""
