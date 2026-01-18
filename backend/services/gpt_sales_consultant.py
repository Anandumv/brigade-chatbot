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
from services.sales_agent_prompt import SALES_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    timeout=30.0  # 30 second timeout for API calls
)


async def generate_consultant_response(
    query: str,
    session: ConversationSession,
    intent: str = None,
    sentiment_analysis: dict = None,
    extraction: dict = None
) -> str:
    """
    Unified GPT sales consultant for continuous conversation.

    Args:
        query: User's query
        session: Full session state with history, context, projects
        intent: Optional intent hint (faq, objection, etc.)
        sentiment_analysis: Optional sentiment analysis results
        extraction: Optional extraction data from intent classifier (project_name, topic, etc.)

    Returns:
        Natural conversational response
    """

    # Build comprehensive context
    context = build_consultant_context(session)
    
    # 🆕 Inject project_name from extraction if available (for distance/connectivity questions)
    if extraction and extraction.get("project_name"):
        project_name = extraction.get("project_name")
        # Add to context so GPT knows which project to answer about
        if "last_shown_projects" not in context or not context["last_shown_projects"]:
            context["last_shown_projects"] = []
        # Check if project already in context
        project_in_context = any(
            p.get("name", "").lower() == project_name.lower() 
            for p in context["last_shown_projects"]
        )
        if not project_in_context:
            # Add project to context for GPT reference
            context["last_shown_projects"].insert(0, {
                "name": project_name,
                "location": extraction.get("location", "N/A"),
                "price": "N/A",
                "config": "N/A"
            })

    # Determine conversation goal
    goal = determine_conversation_goal(intent, query, session, extraction)
    
    # 🆕 Enhance goal with sentiment awareness
    if sentiment_analysis:
        sentiment = sentiment_analysis.get("sentiment", "neutral")
        frustration_level = sentiment_analysis.get("frustration_level", 0)
        
        # Add sentiment-specific goal guidance
        if sentiment == "frustrated" or frustration_level >= 7:
            goal += "\n\n🚨 CUSTOMER IS FRUSTRATED - Priority: Address concern immediately with empathy and concrete solutions."
        elif sentiment == "excited":
            goal += "\n\n✨ CUSTOMER IS EXCITED - Capitalize on enthusiasm, suggest immediate action (site visit/booking)."
        elif sentiment == "negative":
            goal += "\n\n⚠️ CUSTOMER HAS CONCERNS - Build trust through transparency and detailed explanations."

    # Get conversation history
    conversation_history = []
    if session and hasattr(session, 'messages'):
        conversation_history = session.messages[-10:]

    # Generate response with GPT
    response = await call_gpt_consultant(
        query=query,
        conversation_history=conversation_history,
        context=context,
        goal=goal,
        sentiment_analysis=sentiment_analysis
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


def determine_conversation_goal(intent: str, query: str, session: ConversationSession, extraction: dict = None) -> str:
    """
    Determine what the user wants to achieve in this conversation turn.

    Returns goal prompt for GPT.
    """

    # 🆕 Check for distance/connectivity questions first (even if intent is sales_conversation)
    query_lower = query.lower()
    is_distance_query = any(word in query_lower for word in ["distance", "far", "near", "airport", "metro", "office", "school", "hospital", "how far"])
    
    if is_distance_query and extraction and extraction.get("project_name"):
        project_name = extraction.get("project_name")
        return f"Answer the distance/connectivity question about {project_name}. Provide specific distance information (in km or minutes) from the mentioned location (airport, metro, etc.) to {project_name}. Use bullet points, be concise, and include actionable information."

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
        elif extraction and extraction.get("project_name"):
            return f"Provide more insights about {extraction.get('project_name')} - selling points, advantages, investment potential"
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

    elif intent == "sales_conversation":
        # Generic sales conversation - check if it's about a specific project
        if extraction and extraction.get("project_name"):
            project_name = extraction.get("project_name")
            topic = extraction.get("topic", "general")
            return f"Answer the user's question about {project_name} regarding {topic}. Be specific, concise, and sales-oriented."
        else:
            # Detect generic sales questions that need comprehensive responses
            query_lower = query.lower()
            is_generic_sales_question = any(phrase in query_lower for phrase in [
                "why buy", "why choose", "why invest", "why this", "why that",
                "advantages of", "benefits of", "pros of", "why is", "why are",
                "what are the", "tell me about", "explain", "help me understand"
            ])
            
            if is_generic_sales_question:
                # Extract topic from query for comprehensive response
                topic = detect_sales_topic(query)
                return f"""Provide a COMPREHENSIVE, CALL-READY response about {topic}. 

CRITICAL REQUIREMENTS FOR LIVE CALLS:
• Provide 6-10 detailed bullet points (not just 2-3)
• Each bullet must be speakable during a live call (concise but complete)
• Include specific benefits, advantages, and selling points
• Make it actionable and persuasive for sales conversations
• Use real estate terminology and market insights
• Structure as: Main point → Supporting detail → Call-to-action where relevant

**FORMATTING REQUIREMENTS (MANDATORY):**
• **ALWAYS use bold (**text**) for key points, main benefits, and important terms**
• Format each bullet as: • **Main Point**: Supporting detail
• Bold the most important words in each bullet (e.g., **unique features**, **long-term value**, **ROI**, **resale value**)
• Use **bold** for numbers, percentages, and key selling points
• Make bullets scannable - bold helps sales people quickly identify key talking points

EXAMPLE FORMAT:
• **Highlight unique features** not available in lower-priced properties - positions as premium investment
• **Emphasize long-term value gains** and **ROI** - shows financial wisdom of stretching budget
• **Discuss potential for higher resale value** - addresses future returns concern
• **Mention financing options** that can ease initial budget constraints - removes immediate barrier
• **Showcase premium amenities** and **exclusive community benefits** - justifies premium pricing

Generate a comprehensive response that helps during live sales calls. EVERY bullet point MUST have bold text for key terms."""
            else:
                return "Continue the property search conversation naturally"

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


def detect_sales_topic(query: str) -> str:
    """Detect the sales topic from a generic sales question."""
    
    query_lower = query.lower()
    
    # Under Construction / Ready to Move
    if any(phrase in query_lower for phrase in ["under construction", "construction", "not ready", "still building"]):
        return "under construction properties"
    elif any(phrase in query_lower for phrase in ["ready to move", "rtm", "ready possession", "immediate possession"]):
        return "ready to move properties"
    
    # Location-based questions
    locations = ["whitefield", "sarjapur", "electronic city", "koramangala", "indiranagar", 
                 "marathahalli", "hebbal", "yelahanka", "bellandur", "varthur", "panathur", "oracle"]
    for loc in locations:
        if loc in query_lower:
            return f"investing in {loc.title()}"
    
    # Investment-related
    if any(phrase in query_lower for phrase in ["investment", "roi", "appreciation", "returns", "resale"]):
        return "real estate investment"
    
    # Budget/Financing
    if any(phrase in query_lower for phrase in ["budget", "emi", "loan", "financing", "payment"]):
        return "budget and financing options"
    
    # Amenities
    if any(phrase in query_lower for phrase in ["amenities", "facilities", "features"]):
        return "property amenities and facilities"
    
    # Location advantages
    if any(phrase in query_lower for phrase in ["location", "connectivity", "nearby", "proximity"]):
        return "location advantages and connectivity"
    
    # Generic fallback
    return "real estate investment in Bangalore"


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

    # Current topic (prominent display)
    if context.get("last_topic"):
        lines.append(f"**CURRENT DISCUSSION TOPIC:** {context['last_topic']}")
        lines.append("")

    # Conversation phase
    if context.get("conversation_phase"):
        lines.append(f"**CONVERSATION PHASE:** {context['conversation_phase']}")
        lines.append("")

    # Recent conversation summary (last 2-3 messages)
    recent_messages = context.get("recent_messages", [])
    if recent_messages:
        lines.append("**RECENT CONVERSATION (for context inference):**")
        # Show last 3 messages for context
        for msg in recent_messages[-3:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")[:200]  # Truncate to avoid token overflow
            if content:
                lines.append(f"- {role.upper()}: {content}")
        lines.append("")
        
        # Extract and list locations mentioned in recent messages
        import re
        locations_mentioned = set()
        common_locations = ["whitefield", "sarjapur", "electronic city", "koramangala", "indiranagar", "marathahalli", "hebbal", "yelahanka", "bellandur", "varthur"]
        for msg in recent_messages:
            content = msg.get("content", "").lower()
            for loc in common_locations:
                if loc in content:
                    locations_mentioned.add(loc.title())
        if locations_mentioned:
            lines.append(f"**LOCATIONS MENTIONED IN CONVERSATION:** {', '.join(sorted(locations_mentioned))}")
            lines.append("")
        
        # Extract project names mentioned
        projects_mentioned = set()
        if context.get("last_shown_projects"):
            for proj in context["last_shown_projects"]:
                projects_mentioned.add(proj.get("name", ""))
        if context.get("interested_projects"):
            projects_mentioned.update(context["interested_projects"])
        if projects_mentioned:
            lines.append(f"**PROJECTS MENTIONED IN CONVERSATION:** {', '.join(sorted(projects_mentioned))}")
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
    goal: str,
    sentiment_analysis: dict = None
) -> str:
    """
    Call GPT with unified consultant prompt and sentiment-adaptive tone.
    """

    # Build context section
    context_section = format_context_for_prompt(context)
    
    # 🆕 Build sentiment-adaptive tone instructions
    tone_instructions = ""
    empathy_statement = ""
    
    if sentiment_analysis:
        from services.sentiment_analyzer import get_sentiment_analyzer
        
        analyzer = get_sentiment_analyzer()
        sentiment = sentiment_analysis.get("sentiment", "neutral")
        frustration_level = sentiment_analysis.get("frustration_level", 0)
        detected_emotions = sentiment_analysis.get("detected_emotions", [])
        
        # Get tone adjustment
        tone_adjustment = analyzer.get_tone_adjustment(sentiment, frustration_level)
        
        # Generate empathy statement
        empathy_statement = analyzer.generate_empathy_statement(
            sentiment,
            detected_emotions,
            specific_concern=context.get("last_objection_type")
        )
        
        # Build tone instructions
        tone_instructions = f"""
        
🎭 TONE ADAPTATION (Critical):
- Customer Sentiment: {sentiment.upper()}
- Frustration Level: {frustration_level}/10
- Detected Emotions: {', '.join(detected_emotions) if detected_emotions else 'none'}
- Empathy Level: {tone_adjustment['empathy_level']}
- Response Style: {tone_adjustment['response_style']}

📋 REQUIRED ACTIONS:
{chr(10).join('- ' + action for action in tone_adjustment['suggested_actions'])}

🚫 AVOID:
{chr(10).join('- ' + avoid for avoid in tone_adjustment['avoid'])}

💡 TONE GUIDANCE:
{chr(10).join('- ' + prompt for prompt in tone_adjustment['prompt_additions'])}

⚡ START YOUR RESPONSE WITH: "{empathy_statement}"
"""

    # Build system prompt using production Sales Agent GPT prompt
    # Add context and goal as additional instructions
    system_prompt = f"""{SALES_AGENT_SYSTEM_PROMPT}

⸻

CURRENT CONVERSATION CONTEXT:
{context_section}

YOUR GOAL FOR THIS TURN:
{goal}{tone_instructions}

⸻

ADDITIONAL CONTEXT-SPECIFIC RULES:

1. **PROJECTS SHOWN**: Reference projects from context above when relevant
2. **USER REQUIREMENTS**: Use budget, location, configuration from context
3. **CONVERSATION HISTORY**: All previous messages are in the conversation history below
4. **SENTIMENT AWARENESS**: {tone_instructions if tone_instructions else "Customer sentiment: Neutral - respond professionally"}
5. **INFERENCE FROM CONTEXT**: If user says vague phrases ("more", "nearby", "these areas"), check context above and conversation history below

**CRITICAL FORMATTING REQUIREMENT:**
• **ALWAYS use bold (**text**) for key points, main benefits, numbers, and important terms in EVERY response**
• Format bullets as: • **Main Point**: supporting detail
• Bold the most important words: **unique features**, **ROI**, **value**, **premium**, **exclusive**, **investment potential**, etc.
• Bold all numbers and percentages: **₹1.25 Cr**, **10 mins**, **15-20%**, etc.
• Bold project names, locations, and key selling points
• This makes responses scannable and helps sales people quickly identify talking points during calls

REMEMBER: You are a silent sales brain running during a live call. Every token must earn its place.
"""

    # Build messages
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    if conversation_history:
        messages.extend(conversation_history[-10:])

    # Add current query
    messages.append({"role": "user", "content": query})

    try:
        # Determine if this is a generic sales question that needs comprehensive response
        query_lower = query.lower()
        is_comprehensive_question = any(phrase in query_lower for phrase in [
            "why buy", "why choose", "why invest", "advantages of", "benefits of", 
            "what are the", "tell me about", "explain", "help me understand"
        ])
        
        # Use higher max_tokens for comprehensive sales questions (6-10 bullet points)
        max_tokens = 1000 if is_comprehensive_question else 600
        
        # Call GPT
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=messages,
            temperature=0.7,
            max_tokens=max_tokens
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.error(f"GPT consultant call failed: {e}")

        # Fallback response
        if context.get("last_shown_projects"):
            project_name = context["last_shown_projects"][0]["name"]
            return f"""• I'd be happy to discuss **{project_name}** in more detail.
• **Great value** on location, amenities, and pricing for your requirements.
• I can share more on **location advantages**, **investment potential**, or **amenities**.
• Or we can **schedule a site visit**—just say when works for you."""
        else:
            return """• I'm here to help you find the perfect property in **Bangalore**!

I can assist with:
- **Property search** (budget, config, location)
- **Project details** and comparisons
- **Location insights** and connectivity
- **Investment advice** and ROI potential
- **Site visit** scheduling

What would you like to explore?"""
