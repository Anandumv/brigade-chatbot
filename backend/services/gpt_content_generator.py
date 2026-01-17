"""
GPT Content Generator for Real Estate Insights.

Generates persuasive, fact-grounded content about projects beyond basic database fields.
Used for investment pitches, sustainability elaboration, location advantages, etc.
"""

import logging
from typing import Dict, Optional
from openai import OpenAI
from config import settings

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
    Generate persuasive insights about a project beyond basic facts.

    Topics handled:
    - "sustainability": Elaborate on green certifications, eco-friendly features
    - "investment": ROI potential, appreciation, market trends (with disclaimers)
    - "location_advantages": Connectivity, upcoming infrastructure, neighborhood quality
    - "amenities_benefits": How amenities improve lifestyle
    - "general_selling_points": Overall persuasive pitch
    - "general": Auto-detect what user wants to know more about

    Args:
        project_facts: Database record with name, developer, location, price, RERA, amenities, USP
        topic: What aspect to elaborate on
        query: Original user query for context
        user_requirements: User's search criteria (config, budget, location preferences)

    Returns:
        Persuasive content string (200-500 words)
    """

    system_prompt = _build_content_generation_prompt(project_facts, topic, user_requirements)

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
- Keep it conversational and engaging (200-400 words)
- Use bullet points and formatting for readability
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
