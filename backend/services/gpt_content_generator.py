"""
GPT Content Generator for Real Estate Insights.

Uses MASTER PROMPT from master_prompt.py for consistent Sales Advisor responses.
Generates persuasive, fact-grounded content about projects beyond basic database fields.
"""

import logging
from typing import Dict, Optional
from openai import OpenAI
from config import settings
from services.master_prompt import get_content_prompt, get_objection_prompt, get_meeting_prompt, get_general_prompt

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url
)


def generate_insights(
    project_facts: Dict,
    topic: str,
    query: str,
    user_requirements: Optional[Dict] = None
) -> str:
    """
    Generate persuasive insights using MASTER SALES ADVISOR PROMPT.

    Topics handled:
    - "sustainability": Green features explained in money/health terms
    - "investment": ROI potential with market risk disclaimers
    - "location_advantages": Connectivity, infrastructure, neighborhood
    - "amenities_benefits": How amenities improve daily lifestyle
    - "general_selling_points": 2-3 strongest selling points
    - "meeting_scheduling": Meeting options and how to schedule
    - "objection_*": Handle objections (budget, location, possession, trust)

    Returns:
        Speakable, action-oriented content (no fluff, decision-focused)
    """

    # Use master prompt library
    if topic.startswith("objection_"):
        objection_type = topic.replace("objection_", "")
        system_prompt = get_objection_prompt(objection_type, query)
    elif topic == "meeting_scheduling":
        system_prompt = get_meeting_prompt(query)
    elif project_facts.get("name") in ["Pinclick Real Estate", "Meeting Request"]:
        system_prompt = get_general_prompt(query)
    else:
        system_prompt = get_content_prompt(project_facts, topic, query, user_requirements)

    try:
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            temperature=0.7,  # Slightly creative for persuasive content
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query}
            ],
            max_tokens=600
        )

        content = response.choices[0].message.content
        logger.info(f"Generated insights for project={project_facts.get('name')}, topic={topic}")

        return content

    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        # Fallback to basic facts
        return _fallback_response(project_facts, topic)


def _build_content_generation_prompt(
    project_facts: Dict,
    topic: str,
    user_requirements: Optional[Dict]
) -> str:
    """Build the system prompt for content generation."""

    # Extract key facts
    name = project_facts.get('name', 'this project')
    developer = project_facts.get('developer', 'the developer')
    location = project_facts.get('location', 'the location')
    budget_min = project_facts.get('budget_min', 0) / 100  # Convert to Cr
    budget_max = project_facts.get('budget_max', 0) / 100
    configuration = project_facts.get('configuration', 'N/A')
    amenities = project_facts.get('amenities', 'N/A')
    usp = project_facts.get('usp', '')
    rera = project_facts.get('rera_number', 'N/A')
    status = project_facts.get('status', 'N/A')
    possession = f"{project_facts.get('possession_quarter', '')} {project_facts.get('possession_year', '')}".strip()

    # Build context-aware prompt based on topic
    topic_guidance = _get_topic_guidance(topic)

    prompt = f"""You are a knowledgeable real estate consultant helping a buyer understand the value of **{name}**.

**Project Facts (from database):**
- Name: {name}
- Developer: {developer}
- Location: {location}
- Price Range: ₹{budget_min:.2f} - ₹{budget_max:.2f} Cr
- Configurations: {configuration}
- Status: {status}
- Possession: {possession}
- Amenities: {amenities}
- Highlights (USP): {usp}
- RERA: {rera}
"""

    # Add user requirements context if available
    if user_requirements:
        prompt += f"\n**User's Requirements:**\n"
        if user_requirements.get('configuration'):
            prompt += f"- Preferred config: {user_requirements['configuration']}\n"
        if user_requirements.get('budget_max'):
            prompt += f"- Budget: Up to ₹{user_requirements['budget_max']} lakhs\n"
        if user_requirements.get('location'):
            prompt += f"- Preferred location: {user_requirements['location']}\n"

    prompt += f"""
**Your Task:**
The user is asking about: **{topic}**

{topic_guidance}

**Guidelines:**
- Be persuasive and sales-focused - your goal is to help close the deal
- Reference the actual project facts above as the foundation
- ADD EXTRA VALUE: Include common premium amenities and features typical for this price range/developer that help sales (clubhouse benefits, smart home features, premium fittings, etc.)
- ADD SELLING POINTS: Mention advantages that this type of property typically offers (rental yield potential, appreciation in this area, upcoming metro/infrastructure, etc.)
- For investment/ROI: Add disclaimers about market risks ("real estate investments carry risk", "past trends don't guarantee future returns")
- For sustainability: Explain benefits of certifications, green features, monthly cost savings
- For location: Mention connectivity (metro, highways), social infrastructure (schools, hospitals, malls), upcoming developments
- For amenities: Elaborate on lifestyle benefits AND suggest additional premium features that buyers expect at this price point
- **Use BULLET POINTS only.** **Bold** main points (project name, price, key benefits). 8-12 bullets max. For sales people on calls.
- Every point as a bullet (• or -). No paragraphs.
- Focus on buyer benefits and emotional appeal
- End with a soft call-to-action (site visit, more details, etc.)

Generate a response that elaborates on the topic while staying grounded in the facts. Be specific and actionable. Include additional selling points that help close the deal.
"""

    return prompt


def _get_topic_guidance(topic: str) -> str:
    """Get specific guidance based on topic."""

    guidance_map = {
        "sustainability": """
Elaborate on:
- What green certifications mean for the buyer (lower bills, health benefits, resale value)
- Specific eco-friendly features and their impact
- Long-term financial benefits (₹ savings per month/year)
- Market advantage of sustainable homes
""",
        "investment": """
Elaborate on:
- Location appreciation potential (based on infrastructure, demand)
- Developer track record and delivery history
- Configuration demand in the area
- Rental yield potential
- **Important:** Always include disclaimers about market risks
""",
        "location_advantages": """
Elaborate on:
- Connectivity (current and upcoming metro, highways, airport access)
- Social infrastructure (schools, hospitals, malls, parks nearby)
- Employment hubs proximity (IT parks, business districts)
- Upcoming developments in the area
- Safety and livability factors
""",
        "amenities_benefits": """
Elaborate on:
- How specific amenities improve daily lifestyle
- Comparison with typical projects (what's unique here)
- Family benefits (kids play areas, senior citizen spaces)
- Health and wellness facilities
- Community and social aspects
""",
        "meeting_scheduling": """
You are helping a customer understand how to schedule a meeting or site visit with Pinclick.
Explain:
- Different meeting options (office visit, site visit, video call)
- What to expect during the meeting
- Benefits of meeting in person (see actual property, exclusive offers)
- How to schedule (share preferred date/time/contact)
- Reassure them it's no obligation, just exploration
Keep it warm, friendly, and encouraging. End with asking for their preferred time.
""",
        "general_selling_points": """
Provide a well-rounded overview covering:
- 2-3 strongest selling points of this project
- How it stands out from competitors
- Who is the ideal buyer for this project
- Why now is a good time to consider (possession timeline, pricing, market conditions)
"""
    }

    return guidance_map.get(topic, guidance_map["general_selling_points"])


def _fallback_response(project_facts: Dict, topic: str) -> str:
    """Fallback response if GPT generation fails."""

    name = project_facts.get('name', 'this project')
    developer = project_facts.get('developer', 'the developer')
    usp = project_facts.get('usp', '')

    return f"""Here's what makes **{name}** by {developer} a great choice:

{usp}

I'd be happy to provide more specific details about {topic} if you'd like. Would you also like to schedule a site visit to see the project in person?"""


def enhance_with_gpt(project_facts: Dict, query: str) -> str:
    """
    Hybrid response: Database facts + GPT persuasive framing.

    Used for general "tell me about PROJECT" queries.
    Returns structured facts with AI-generated persuasive intro/conclusion.
    """

    name = project_facts.get('name', 'this project')
    developer = project_facts.get('developer', 'N/A')
    location = project_facts.get('location', 'N/A')
    budget_min = project_facts.get('budget_min', 0) / 100
    budget_max = project_facts.get('budget_max', 0) / 100
    configuration = project_facts.get('configuration', 'N/A')
    amenities = project_facts.get('amenities', 'N/A')
    usp = project_facts.get('usp', '')
    rera = project_facts.get('rera_number', 'N/A')
    status = project_facts.get('status', 'N/A')
    possession = f"{project_facts.get('possession_quarter', '')} {project_facts.get('possession_year', '')}".strip()

    # Database facts (structured)
    facts_section = f"""**{name}** by {developer}

**Key Details:**
- 🏗️ Developer: **{developer}**
- 📍 Location: {location}
- 💰 Price Range: ₹{budget_min:.2f} - ₹{budget_max:.2f} Cr
- 🏠 Configurations: {configuration}
- 📅 Possession: {possession}
- 🛡️ RERA: {rera}

**Amenities:**
{amenities}
"""

    if usp and len(usp) > 10:
        facts_section += f"\n**Highlights:**\n{usp}\n"

    # Generate persuasive intro using GPT
    try:
        prompt = f"""You are a real estate consultant. Write a brief, engaging 2-3 sentence introduction for **{name}** that highlights why it's a great choice.

Project: {name} by {developer}
Location: {location}
USP: {usp}

Write ONLY the introduction (2-3 sentences). Be persuasive but honest."""

        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150
        )

        intro = response.choices[0].message.content.strip()

        # Combine intro + facts + CTA
        return f"""{intro}

{facts_section}

Would you like to know more about the investment potential, sustainability features, or schedule a site visit?"""

    except Exception as e:
        logger.error(f"Hybrid enhancement failed: {e}")
        # Fallback: Just return facts
        return facts_section + "\n\nWould you like more details or schedule a site visit?"


def generate_contextual_response_with_full_history(
    query: str,
    conversation_history: list,
    session_context: Dict,
    goal: str = "Continue the conversation naturally"
) -> str:
    """
    Generate intelligent contextual responses using full conversation history.
    
    This is the ULTIMATE FALLBACK - never asks clarifying questions, always continues naturally.
    
    Args:
        query: Current user query
        conversation_history: Full conversation history (last 10 turns)
        session_context: Rich session context from session_manager.get_context_summary()
        goal: Specific goal for this response (optional)
    
    Returns:
        Natural, context-aware response that continues the conversation
    """
    
    # Build comprehensive context for GPT
    context_parts = []
    
    # Add conversation summary
    if session_context.get("summary"):
        context_parts.append(f"**Conversation Summary:** {session_context['summary']}")
    
    # Add current state
    if session_context.get("last_project"):
        context_parts.append(f"**Currently Discussing:** {session_context['last_project']}")
    
    if session_context.get("last_topic"):
        context_parts.append(f"**Last Topic:** {session_context['last_topic']}")
    
    if session_context.get("current_filters"):
        filters = session_context['current_filters']
        filter_strs = []
        if filters.get('configuration'):
            filter_strs.append(f"{filters['configuration']}")
        if filters.get('location'):
            filter_strs.append(f"in {filters['location']}")
        if filters.get('budget_max'):
            filter_strs.append(f"under ₹{filters['budget_max']} Cr")
        if filter_strs:
            context_parts.append(f"**User Requirements:** {' '.join(filter_strs)}")
    
    if session_context.get("objections_raised"):
        context_parts.append(f"**Objections:** {', '.join(session_context['objections_raised'])}")
    
    context_str = "\n".join(context_parts) if context_parts else "New conversation"
    
    # Build system prompt
    system_prompt = f"""You are an AI real estate sales assistant for Pinclick in Bangalore.

{context_str}

**YOUR CRITICAL INSTRUCTIONS:**
1. NEVER ask clarifying questions like "What would you like to know?" or "Could you clarify?"
2. Use the conversation context to infer what the user wants
3. Continue the conversation naturally as if you fully understand the context
4. If the user asks vague questions like "give more points", provide relevant information about the current topic/project
5. Be helpful, informative, and sales-focused
6. If uncertain, provide general helpful information and guide toward specific topics
7. 8-12 bullets max. Scannable.

**Your Goal:** {goal}

**Response Guidelines:**
- **ALWAYS use bullet points.** **Bold** key terms (project names, prices, configs). No paragraphs. For sales people on calls.
- Be persuasive but honest
- End with a gentle call-to-action or question to keep conversation flowing
- Reference the conversation context naturally"""

    # Build messages with history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history (last 10 turns for full context)
    if conversation_history:
        messages.extend(conversation_history[-10:])
    
    # Add current query
    messages.append({"role": "user", "content": query})
    
    try:
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            temperature=0.7,
            messages=messages,
            max_tokens=500
        )
        
        content = response.choices[0].message.content.strip()
        logger.info(f"Generated contextual response with full history (query='{query[:50]}...', context_items={len(context_parts)})")
        
        return content
    
    except Exception as e:
        logger.error(f"Contextual response generation failed: {e}")
        
        # Ultimate fallback - still try to be helpful
        if session_context.get("last_project"):
            return f"""I'd be happy to share more about **{session_context['last_project']}**. 

Here are some key points:
- It's a premium project with excellent amenities and location
- Well-suited for your requirements
- Great investment potential in this area

Would you like to know more about pricing, amenities, location advantages, or schedule a site visit?"""
        else:
            return """I'm here to help you find the perfect property in Bangalore!

I can assist with:
- 🏠 Property search based on your budget and preferences
- 📊 Project details and comparisons
- 📍 Location insights and connectivity
- 💰 Investment advice and ROI potential
- 📅 Site visit scheduling

What would you like to explore?"""

