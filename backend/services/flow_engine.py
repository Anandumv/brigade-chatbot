import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import openai
from config import settings
from database.pixeltable_setup import get_projects_table
import pixeltable as pxt
import difflib
import re
from services.web_search import web_search_service
from services.web_search import web_search_service
from services.sales_agent_prompt import SALES_AGENT_SYSTEM_PROMPT
from services.web_search import web_search_service
from services.sales_agent_prompt import SALES_AGENT_SYSTEM_PROMPT, LIGHT_INTENT_SYSTEM_PROMPT
from services.sales_formatter import sales_formatter
from services.sales_conversation import sales_conversation
from utils.geolocation_utils import get_coordinates, calculate_distance

logger = logging.getLogger(__name__)

def clean_configuration_string(config_raw: str) -> str:
    """Parses messy configuration strings to extract clean BHK types."""
    if not config_raw: return "Details on Request"
    
    # Regex to find 2BHK, 3 BHK, 2.5BHK etc
    # Matches: number + optional decimal + optional space + BHK
    matches = re.findall(r"(\d+(?:\.\d+)?)\s*BHK", str(config_raw), re.IGNORECASE)
    
    if not matches:
        return str(config_raw)
        
    # Deduplicate and sort numerically
    try:
        unique_bhk = sorted(list(set(float(m) for m in matches)))
        # Format: 2.0 -> 2, 2.5 -> 2.5
        formatted = [f"{g:g} BHK" for g in unique_bhk]
        return ", ".join(formatted)
    except Exception:
        return str(config_raw)

def format_configuration_table(config_raw: str) -> str:
    """Parses config string into a markdown table."""
    if not config_raw: return ""
    
    # Extract groups like {2BHK, 1200, 1.2Cr}
    groups = re.findall(r"\{([^}]+)\}", str(config_raw))
    
    if not groups:
        # Fallback to existing clean string if no groups found
        cleaned = clean_configuration_string(config_raw)
        return f"**Config:** {cleaned}"
        
    # Build table
    # Build clean list instead of table (User preference & mobile friendly)
    list_lines = []
    
    for group in groups:
        parts = [p.strip() for p in group.split(',')]
        if len(parts) >= 3:
            config, size, price = parts[0], parts[1], parts[2]
            # Format: "  - **2 BHK**: 1127 - 1461 sq.ft • ₹2.20 Cr*"
            list_lines.append(f"  \n- **{config}**: {size} sq.ft • {price}")
        elif len(parts) >= 1:
            list_lines.append(f"  \n- {parts[0]}")
             
    return "\n" + "".join(list_lines) + "\n\n"

# --- SYSTEM PROMPT ---
STRICT_SYSTEM_PROMPT = """
ROLE
You are an AI Sales Agent for Pinclick.
You speak directly to the customer.
You enforce a deterministic flowchart to guide the customer to a site visit.

AUTHORITY HIERARCHY (STRICT)
1. Flowchart logic — absolute authority
2. Pixeltable RAG — single source of factual truth
3. LLM generation — language only, never facts

DATA SOURCE
- All project data, pricing, possession, locations, and inventory must come from Pixeltable RAG.
- If Pixeltable returns zero rows, you must not invent, infer, or approximate. Same applies if budget is too low.

OUTPUT FORMAT (MANDATORY)
Always respond in four fixed sections:
1. Extracted Requirements: (JSON format with Configuration, Location, Budget, Possession)
2. Current Flowchart Node: (e.g., NODE 2)
3. System Action: (Instructions for the agent)
4. Next Redirection: (e.g., NODE 3)
"""

# --- MODELS ---
class FlowRequirements(BaseModel):
    configuration: Optional[str] = None
    location: Optional[str] = None
    area: Optional[str] = None # Zone: "North Bangalore", "East Bangalore", etc.
    budget_max: Optional[float] = None
    possession_year: Optional[int] = None
    possession_type: Optional[str] = None # "RTMI" or "Under Construction"
    project_name: Optional[str] = None # Explicit project name (e.g. "Birla Evara")
    feature_requested: Optional[str] = None # Feature being asked about (e.g. "carpet area", "RM contact", "price")

class FlowState(BaseModel):
    # Core Context (Persistent)
    requirements: FlowRequirements = Field(default_factory=FlowRequirements)
    
    # Session Context
    last_search_results: List[Dict[str, Any]] = Field(default_factory=list)
    last_shown_projects: List[Dict[str, Any]] = Field(default_factory=list)
    selected_project_id: Optional[str] = None
    selected_project_name: Optional[str] = None
    
    # Conversation History
    last_intent: Optional[str] = None
    current_node: str = "ROUTER"
    pagination_offset: int = 0

class FlowResponse(BaseModel):
    extracted_requirements: Dict[str, Any]
    current_node: str
    system_action: str # Markdown string for general use
    next_redirection: str
    
    # New: Structured fields for CopilotResponse compatibility
    answer_bullets: List[str] = Field(default_factory=list)
    projects: List[Dict[str, Any]] = Field(default_factory=list)
    pitch_help: Optional[str] = None
    next_suggestion: Optional[str] = None
    coaching_point: Optional[str] = None

# --- LLM HELPERS ---
def extract_requirements_llm(user_input: str) -> FlowRequirements:
    """Extracts structured data from free text using LLM."""
    try:
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=[
                {"role": "system", "content": "Extract JSON: configuration (e.g. 2BHK), location (locality like 'Sarjapur', 'Whitefield'), area (zone like 'East Bangalore', 'North Bangalore', 'South Bangalore', 'West Bangalore' - infer from location if not explicit), budget_max (float in Cr), possession_year (int), possession_type (RTMI/Under Construction), project_name (CRITICAL: extract project names like 'Birla Evara', 'Brigade Avalon', 'Nambiar D-25', 'Godrej Woods' - recognize these even in questions), feature_requested (e.g. 'carpet area', 'RM contact', 'price', 'amenities', 'possession', 'schools', 'distance', null if none). Return null if missing. IMPORTANT: For well-known Bangalore localities, infer the area/zone: Sarjapur/Whitefield/Marathahalli -> 'East Bangalore', Devanahalli/Yelahanka/Hebbal -> 'North Bangalore'."},
                {"role": "user", "content": user_input}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return FlowRequirements(**data)
    except openai.RateLimitError:
        logger.error("OpenAI RateLimitError in extract_requirements_llm")
        raise
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        return FlowRequirements()

def generate_persuasion_text(topic: str, context: str) -> str:
    """Generates persuasive sales text (no facts, only logic)."""
    try:
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=[
                {"role": "system", "content": "You are a sales coach. Generate persuasive talking points (no fake data) for the agent."},
                {"role": "user", "content": f"Topic: {topic}\nContext: {context}"}
            ]
        )
        return response.choices[0].message.content
    except openai.RateLimitError:
        logger.error("OpenAI RateLimitError in generate_persuasion_text")
        raise
    except Exception:
        return "Could not generate persuasion text."

def classify_user_intent(user_input: str, context: str, chat_history: List[Dict[str, str]] = []) -> dict:
    """Uses LLM to classify user intent and sentiment in conversation."""
    try:
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        
        # Format history for context
        history_text = ""
        if chat_history:
            history_text = "\nRecent Conversation History:\n" + "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-5:]])

        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": LIGHT_INTENT_SYSTEM_PROMPT + """

⸻

TASK: INTENT & SENTIMENT CLASSIFICATION (INTERNAL)

⚠️ OVERRIDE: IGNORE "LIVE CALL OUTPUT RULES".
⚠️ OVERRIDE: OUTPUT JSON ONLY.

Analyze user input and return JSON:
Analyze user input and return JSON:
- intent: [
    project_discovery,      # "Show me 2BHKs in Whitefield", "Find projects"
    project_specific,       # "Details of Birla Evara", "Tell me about X"
    comparison,             # "Compare with Sarjapur", "Is this better than X?"
    contextual_query,       # "Anything nearby?", "Schools near there?", "Same price elsewhere?"
    sales_support,          # "Give me a pitch", "Convince values", "Why buy?"
    objection_budget,       # "Too expensive"
    objection_location,     # "Location is bad"
    objection_possession,   # "Need ready to move"
    schedule_visit,         # "Book a visit", "When can I see?"
    ambiguous               # "Hello", "Thanks"
]
- confidence: float 0-1
- sentiment: [positive, neutral, negative]
- explanation: brief reason

Use 'project_specific' if specific project mentioned.
Use 'contextual_query' if referring to previous context ("nearby", "there", "similar").

"""
                },
                {"role": "user", "content": f"Context: {context}\n{history_text}\nUser said: {user_input}"}
            ],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except openai.RateLimitError:
        logger.error("OpenAI RateLimitError in classify_user_intent")
        raise
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        # Fallback to keyword-based detection
        user_lower = user_input.lower()
        if any(word in user_lower for word in ["expensive", "budget", "cost", "price", "afford"]):
            return {"intent": "budget_objection", "confidence": 0.6, "sentiment": "negative", "explanation": "Keyword match"}
        elif any(word in user_lower for word in ["ready", "move", "possession", "timeline", "date"]):
            return {"intent": "possession_objection", "confidence": 0.6, "sentiment": "negative", "explanation": "Keyword match"}
        elif any(word in user_lower for word in ["yes", "good", "interested", "book", "visit", "schedule"]):
            return {"intent": "positive_interest", "confidence": 0.6, "sentiment": "positive", "explanation": "Keyword match"}
        elif any(word in user_lower for word in ["tell me", "more about", "select", "pitch", "why"]):
            return {"intent": "project_selection", "confidence": 0.6, "sentiment": "neutral", "explanation": "Keyword match for project details"}
        else:
            return {"intent": "ambiguous", "confidence": 0.5, "sentiment": "neutral", "explanation": "No clear match"}

def generate_contextual_response(user_input: str, context: str, conversation_goal: str, chat_history: List[Dict[str, str]] = []) -> str:
    """Generates a contextual, natural response using LLM for continuous conversation."""
    try:
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        
        # Format history
        history_text = ""
        if chat_history:
            history_text = "\nRecent Conversation History:\n" + "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-6:]])
            
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": f"""{SALES_AGENT_SYSTEM_PROMPT}

⸻

TASK: GENERATE SPEAKABLE RESPONSE
Current conversation context: {context}
{history_text}
Your immediate goal: {conversation_goal}

Override: Ensure output is strictly bullet points as per System Prompt. Start every bullet point with a hyphen (-) or bullet character (•)."""
                },
                {"role": "user", "content": f"Customer said: '{user_input}'. specific_instruction: Generate a response to achieve the goal."}
            ]
        )
        return response.choices[0].message.content
    except openai.RateLimitError:
        logger.error("OpenAI RateLimitError in generate_contextual_response")
        raise
    except Exception as e:
        logger.error(f"Contextual response generation failed: {e}")
        return "I'd be happy to help you with that. Could you tell me more about what you're looking for?"

def fetch_nearby_amenities(project_name: str, location: str) -> str:
    """Fetch nearby amenities using web search for location-based sales pitch."""
    try:
        query = f"What are the nearby amenities, schools, hospitals, malls, metro stations near {project_name} in {location}, Bangalore? Provide specific names and distances."

        logger.info(f"Fetching nearby amenities for {project_name} in {location}")

        web_result = web_search_service.search_and_answer(
            query=query,
            topic_hint=f"{project_name} Bangalore location advantages"
        )

        if web_result.get("answer"):
            return f"\n\n**🌍 Location Advantages & Nearby Amenities:**\n{web_result['answer']}"
        else:
            return ""
    except Exception as e:
        logger.error(f"Failed to fetch nearby amenities: {e}")
        return ""

def classify_followup_intent(user_input: str, project_name: str, project_location: str) -> dict:
    """
    Classify user's follow-up question about a selected project using LLM.

    Returns dict with:
    - intent: str (location_info, amenities_nearby, investment_pitch, project_details, site_visit, objection, unclear)
    - needs_web_search: bool (whether external data would help)
    - confidence: float (0-1)
    """
    try:
        client = openai.OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )

        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            messages=[
                {
                    "role": "system",
                    "content": f"""Analyze the sales agent's question about {project_name} in {project_location}.

Classify the intent into ONE of these categories:

1. **location_info** - Questions about area, connectivity, neighborhood quality, infrastructure
   Examples: "How's the area?", "What about connectivity?", "Is the location good?"

2. **amenities_nearby** - Specific requests for nearby facilities (schools, hospitals, malls, metro)
   Examples: "Any schools nearby?", "What's around?", "Shopping options?"

3. **investment_pitch** - Questions about ROI, appreciation, why buy, market potential
   Examples: "Why should they buy?", "Good investment?", "Price appreciation?"

4. **project_details** - Specific questions about the project itself (specs, features, developer)
   Examples: "Who's the developer?", "How many towers?", "What about parking?"

5. **site_visit** - Ready to schedule or discussing visit
   Examples: "Let's schedule", "When can we visit?", "Book a tour"

6. **objection** - Concerns about price, location, timeline
   Examples: "Too expensive", "Too far", "Takes too long"

7. **unclear** - Vague or unrelated
   Examples: "Hmm", "Maybe", "What else?"

Return JSON:
{{
  "intent": "<category>",
  "needs_web_search": true/false,
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation"
}}

Use needs_web_search=true for location_info and amenities_nearby (external data helps).
Use needs_web_search=false for project_details (database has this) and investment_pitch (LLM can generate)."""
                },
                {"role": "user", "content": user_input}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )

        result = json.loads(response.choices[0].message.content)
        logger.info(f"Follow-up intent classified: {result.get('intent')} (confidence: {result.get('confidence')})")
        return result

    except openai.RateLimitError:
        logger.error("OpenAI RateLimitError in classify_followup_intent")
        raise
    except Exception as e:
        logger.error(f"Follow-up intent classification failed: {e}")
        return {
            "intent": "unclear",
            "needs_web_search": False,
            "confidence": 0.5,
            "reasoning": "Classification failed"
        }

# --- INTELLIGENT SALES COPILOT ROUTER ---
def execute_sales_copilot_flow(state: FlowState, user_input: str, chat_history: List[Dict[str, str]] = []) -> FlowResponse:
    """
    New Intelligent Router replacing rigid nodes.
    Routes based on Intent + Context.
    """
    # Initialize variables that may be used in return statement
    project = None
    results = []

    # 1. Extract & Merge Context
    # --------------------------
    new_reqs = extract_requirements_llm(user_input)
    
    # Merge Logic:
    # - If new specific project named -> Set it
    # - If new location -> Update location
    # - If new budget -> Update budget
    # - If 'nearby' intent -> Keep location, expand radius (logic in search)
    
    current_reqs = state.requirements
    
    if new_reqs.project_name:
        state.selected_project_name = new_reqs.project_name
        # If specific project asked, we might clear filters to ensure we find it?
        # Or just let search handle it.
    
    if new_reqs.location:
        current_reqs.location = new_reqs.location
    if new_reqs.area:
        current_reqs.area = new_reqs.area
    if new_reqs.budget_max:
        current_reqs.budget_max = new_reqs.budget_max
    if new_reqs.configuration:
        current_reqs.configuration = new_reqs.configuration
    
    # 2. Classify Intent
    # ------------------
    # CRITICAL: Pre-check for property search patterns before LLM classification
    # This ensures queries like "3BHK in Whitefield" are always classified as property_search
    user_lower = user_input.lower()

    # CONTEXTUAL PATTERN FORCING (NEW - check for contextual queries first)
    contextual_patterns = [
        "more", "other", "options", "alternatives", "different", "another",
        "points", "details", "information", "info", "explain", "elaborate"
    ]
    has_contextual_pattern = any(pattern in user_lower for pattern in contextual_patterns)

    # Check if we have context to use
    has_context = (state.last_shown_projects and len(state.last_shown_projects) > 0) or state.selected_project_name

    # If contextual pattern + context exists, force contextual_query intent
    if has_contextual_pattern and has_context:
        logger.info(f"🔗 Detected contextual pattern with context: '{user_input}' -> forcing contextual_query intent")
        intent = "contextual_query"
        state.last_intent = intent
    # Distance query detection
    elif any(pattern in user_lower for pattern in ["distance", "how far", "km from", "kms from"]):
        logger.info(f"📏 Detected distance query: '{user_input}' -> forcing location_info intent")
        intent = "location_info"
        state.last_intent = intent
    else:
        # Project-specific query detection (BEFORE LLM classification)
        project_feature_patterns = ["rm", "contact", "details", "carpet", "price", "amenities", "possession", "location", "map", "number"]
        has_project_feature = any(pattern in user_lower for pattern in project_feature_patterns)

        # Check if common project name appears in query
        common_projects = ["birla evara", "brigade avalon", "godrej woods", "nambiar", "folium", "avalon", "evara", "prestige", "sobha"]
        potential_project_names = [proj for proj in common_projects if proj in user_lower]

        if has_project_feature and potential_project_names:
            logger.info(f"🎯 Forcing project_specific intent: '{user_input}' (found: {potential_project_names})")
            intent = "project_specific"
            state.last_intent = intent
        else:
            # FIX #4: Removed generic keywords "in " and "at " to avoid false positives
            # (e.g., "tell me about investment in Sarjapur" should NOT be property search)
            property_search_keywords = [
                "bhk", "bedroom", "apartment", "flat", "property", "project", "villa",
                "show me", "find me", "search for", "looking for", "need", "want", "options"
            ]

            # Enhanced location detection: localities + zones
            location_keywords = [
                # Zones
                "north bangalore", "south bangalore", "east bangalore", "west bangalore",
                "north bengaluru", "south bengaluru", "east bengaluru", "west bengaluru",
                # Localities
                "whitefield", "sarjapur", "sarjapura", "marathahalli", "bellandur", "panathur",
                "devanahalli", "devanahali", "yelahanka", "hebbal", "koramangala", "indiranagar",
                "electronic city", "hsr layout", "jp nagar", "jayanagar",
                # Generic
                "bangalore", "bengaluru", "location", "area", "near"
            ]

            has_property_keywords = any(kw in user_lower for kw in property_search_keywords)
            has_location = any(loc in user_lower for loc in location_keywords)
            has_budget = any(b in user_lower for b in ["under", "below", "budget", "price", "cr", "lakh", "lac"])
            has_config = bool(new_reqs.configuration) or any(c in user_lower for c in ["1bhk", "2bhk", "2.5bhk", "3bhk", "4bhk", "5bhk"])

            # Only force property_discovery if EXPLICIT property intent (BHK or property keywords + location/budget)
            if has_config or (has_property_keywords and (has_location or has_budget)):
                logger.info(f"🔍 Detected property search pattern: '{user_input}' -> forcing project_discovery intent")
                intent = "project_discovery"
                state.last_intent = intent
            else:
                # Build comprehensive context string including last_shown_projects
                context_parts = [f"Last Intent: {state.last_intent}"]
                if state.selected_project_name:
                    context_parts.append(f"Last Project: {state.selected_project_name}")
                if current_reqs.location:
                    context_parts.append(f"Location: {current_reqs.location}")
                if state.last_shown_projects:
                    project_names = [p.get('name', p.get('project_name', str(p))) for p in state.last_shown_projects[:3]]
                    context_parts.append(f"Last Shown Projects: {', '.join(project_names)}")
                    context_parts.append("CRITICAL: Vague queries (e.g., 'price', 'more', 'details') refer to last shown project.")

                context_str = ". ".join(context_parts)
                intent_data = classify_user_intent(user_input, context_str, chat_history)
                intent = intent_data.get("intent", "ambiguous")
                state.last_intent = intent
    
    logger.info(f"Router Intent: {intent} | Project: {state.selected_project_name}")

    # 2.5. Handle Non-Property Queries
    # ---------------------------------
    # Detect queries that are clearly not about property search
    non_property_patterns = [
        "how do i", "how to", "meeting", "client", "sales technique", "conversation",
        "pitch", "closing", "negotiation", "rapport", "greeting", "hello", "hi", "hey",
        "thank", "bye", "goodbye"
    ]

    # Check if this is a greeting/farewell/generic sales question without property context
    is_non_property = any(pattern in user_lower for pattern in non_property_patterns)

    # If it's a non-property query and we have no property context, provide guidance
    if is_non_property and intent == "ambiguous" and not state.last_shown_projects and not current_reqs.location:
        logger.info(f"🚫 Detected non-property query: '{user_input}'")
        bullets = [
            "I'm here to help you find the perfect property in Bangalore",
            "I can assist with property search, budget options, location details, and project information",
            "Try asking: '2BHK under 90 lakhs in Sarjapur' or 'Show me properties in North Bangalore'"
        ]
        return FlowResponse(
            extracted_requirements=current_reqs.model_dump(),
            current_node="ROUTER",
            system_action="\n".join(f"• {b}" for b in bullets),
            next_redirection="ROUTER",
            answer_bullets=bullets,
            projects=[],
            pitch_help="Guide the client to share their property preferences",
            next_suggestion="Ask about their budget, preferred location, or configuration requirements",
            coaching_point="Redirect the conversation to property search by asking open-ended questions about their needs"
        )

    # 3. Route Execution
    # ------------------
    action_response = ""
    next_node = "ROUTER" # Placeholder

    projects_table = get_projects_table()
    
    # --- A. PROJECT SPECIFIC (Details, Brochure, RM) ---
    # Handle vague queries with context: if user asks "price", "more", "details" and we have last_shown_projects, use first one
    vague_patterns = ["price", "cost", "more", "details", "tell me", "about it", "what about"]
    is_vague_query = any(pattern in user_input.lower() for pattern in vague_patterns)
    
    if intent == "project_specific" or (state.selected_project_name and intent in ["request_info", "schedule_visit"]):
        # Identify Project
        target_name = new_reqs.project_name or state.selected_project_name
        
        # If vague query and no explicit project but we have last_shown_projects, use first one
        if not target_name and is_vague_query and state.last_shown_projects:
            first_project = state.last_shown_projects[0]
            target_name = first_project.get('name') or first_project.get('project_name')
            if target_name:
                logger.info(f"Using last_shown_projects context for vague query: '{user_input}' -> '{target_name}'")
                state.selected_project_name = target_name
        
        if target_name:
            # DB Lookup (Exact/Fuzzy)
            project = _find_project_by_name(projects_table, target_name)
            
            if project:
                state.selected_project_id = project['project_id']
                state.selected_project_name = project['name']

                # NEW: Check if specific feature requested
                feature = new_reqs.feature_requested
                if feature:
                    if "rm" in feature.lower() or "contact" in feature.lower() or "relationship manager" in feature.lower() or "number" in feature.lower():
                        rm = project.get('rm_details')
                        if rm and isinstance(rm, dict):
                            rm_text = f"**{rm.get('name', 'Support')}**: {rm.get('contact', 'N/A')}"
                        else:
                            rm_text = "**Support**: +91-9988776655"
                        action_response = f"📞 **Relationship Manager for {project['name']}**\n\n{rm_text}"

                    elif "carpet" in feature.lower() or ("area" in feature.lower() and "carpet" in user_input.lower()) or "size" in feature.lower():
                        config = project.get('configuration', '')
                        action_response = f"📐 **Carpet Area for {project['name']}**\n\n{config}\n\nFor specific unit sizes and availability, I can arrange a call with the sales team."

                    elif "price" in feature.lower() or "cost" in feature.lower() or "budget" in feature.lower():
                        budget_min = project.get('budget_min', 0) / 100
                        budget_max = project.get('budget_max', 0) / 100
                        action_response = f"💰 **Pricing for {project['name']}**\n\nStarting from {budget_min:.2f} Cr to {budget_max:.2f} Cr\n\nWould you like to explore specific unit configurations?"

                    elif "amenities" in feature.lower() or "facilities" in feature.lower():
                        amenities = project.get('amenities', 'Information not available')
                        action_response = f"🏊 **Amenities at {project['name']}**\n\n{amenities}"

                    elif "possession" in feature.lower() or "ready" in feature.lower():
                        poss_year = project.get('possession_year', 'N/A')
                        poss_quarter = project.get('possession_quarter', '')
                        status = project.get('status', 'N/A')
                        action_response = f"📅 **Possession Details for {project['name']}**\n\nStatus: {status}\nPossession: {poss_year} {poss_quarter}"

                    elif "school" in feature.lower() or "hospital" in feature.lower() or "connectivity" in feature.lower():
                        project_location = project.get('location', '')
                        description = project.get('description', '')
                        action_response = f"🗺️ **Location & Connectivity for {project['name']}**\n\nLocation: {project_location}\n\n{description}"

                    elif "location" in feature.lower() or "map" in feature.lower() or "google" in feature.lower() or "address" in feature.lower():
                        project_location = project.get('location', 'N/A')
                        zone = project.get('zone', '')
                        action_response = f"📍 **Location: {project['name']}**\n\n{project_location}\n\nTo find it on Google Maps, search for \"{project['name']}, Bangalore\" or \"{project_location}\"."

                    else:
                        # Generic feature - use GPT to generate response
                        try:
                            action_response = _generate_project_details_response(project, user_input)
                        except Exception as e:
                            logger.error(f"GPT generation failed: {e}")
                            action_response = sales_formatter.format_pitch_response(project)

                # If specifically asking for brochure/RM (fallback for queries without feature extraction)
                elif "brochure" in user_input.lower():
                    url = project.get('brochure_url')
                    action_response = f"📄 **Brochure for {project['name']}**\n{url or 'Available on request via RM.'}"
                elif "rm" in user_input.lower() or "number" in user_input.lower():
                    # FIX #2: Format RM details properly
                    rm = project.get('rm_details')
                    if rm and isinstance(rm, dict):
                        rm_text = f"**{rm.get('name', 'Support')}**: {rm.get('contact', 'N/A')}"
                    else:
                        rm_text = "**Support**: +91-9988776655"
                    action_response = f"📞 **Relationship Manager for {project['name']}**\n\n{rm_text}"
                else:
                    # FIX #6: Check if asking about project details/amenities
                    asking_details = any(word in user_input.lower() for word in [
                        "amenities", "amenity", "facilities", "features", "specifications",
                        "details", "about", "tell me", "what", "how"
                    ])

                    if asking_details:
                        # Use GPT to generate conversational response about project
                        try:
                            action_response = _generate_project_details_response(project, user_input)
                        except Exception as e:
                            logger.error(f"GPT generation failed, fallback to formatted response: {e}")
                            action_response = sales_formatter.format_pitch_response(project)
                    else:
                        # General project query - use formatted card
                        action_response = sales_formatter.format_pitch_response(project)
            else:
                action_response = f"I couldn't find specific details for '{target_name}'. Let me show you similar options."
                intent = "project_discovery" # Fallback
        else:
            intent = "project_discovery" # Fallback if no name found

    # --- B. PROJECT DISCOVERY / CONTEXTUAL (Search) ---
    if intent in ["project_discovery", "contextual_query", "ambiguous"]:
        # --- RADIUS SEARCH LOGIC ---
        results = []
        radius_matches = []
        is_nearby_query = (intent == "contextual_query") or any(w in user_input.lower() for w in ["nearby", "near", "close to", "around"])
        
        if is_nearby_query and current_reqs.location:
            center_coords = get_coordinates(current_reqs.location)
            if center_coords:
                lat1, lon1 = center_coords
                
                # Fetch all projects
                all_projs = []
                if projects_table:
                    try:
                        all_projs = projects_table.select(
                            projects_table.project_id, projects_table.name, projects_table.location, projects_table.zone,
                            projects_table.budget_min, projects_table.budget_max,
                            projects_table.configuration, projects_table.status
                        ).collect()
                    except Exception as e:
                        logger.error(f"Radius search DB error: {e}")
                        all_projs = []
                
                if not all_projs:
                    all_projs = _get_mock_projects()
                
                for p in all_projs:
                    # Naively assumes project location string can be geocoded or we simply fuzzy match location in DB
                    # Real implementation needs lat/lon in DB. 
                    # Fallback: check if we have lat/lon in DB columns (assuming they exist or we map location string)
                    p_coords = get_coordinates(p['location'])
                    if p_coords:
                        dist = calculate_distance(lat1, lon1, p_coords[0], p_coords[1])
                        if dist <= 10.0: # 10km radius
                            p['_distance'] = dist
                            radius_matches.append(p)
                
                if radius_matches:
                    radius_matches.sort(key=lambda x: x.get('_distance', 999))
                    results = radius_matches # Override text search results
        
        # Standard Search if no radius results or not a radius query
        if not results:
            # NEW: For ambiguous/contextual with context, reuse last search filters
            if intent in ["ambiguous", "contextual_query"] and state.last_shown_projects and current_reqs.location is None and current_reqs.budget_max is None and current_reqs.configuration is None:
                logger.info(f"Ambiguous/contextual query with context - showing more from last search")
                # Reuse results from last search
                results = state.last_search_results[state.pagination_offset:state.pagination_offset+5] if state.last_search_results else []
                state.pagination_offset += 5

                if results:
                    action_response = "Here are more options based on your previous search. You can swipe through the cards to explore."
                else:
                    action_response = "That was all the options I found. Would you like to adjust your filters (location, budget, BHK) to see more?"
            else:
                results = _search_projects(projects_table, current_reqs, user_input)

        # AUTOMATIC BUDGET EXPANSION: If no results and budget specified, try progressively higher budgets
        budget_expanded = False
        context_msg = ""
        if not results and current_reqs.budget_max:
            logger.info(f"No results for budget {current_reqs.budget_max} Cr, attempting automatic expansion")

            # Try expanding budget in steps: 20%, 40%, 60%, 80%, 100%
            for expansion_factor in [1.2, 1.4, 1.6, 1.8, 2.0]:
                relaxed_budget = current_reqs.budget_max * expansion_factor
                logger.info(f"Trying budget expansion to {relaxed_budget:.2f} Cr ({int(expansion_factor*100)}%)")

                relaxed_reqs = current_reqs.model_copy()
                relaxed_reqs.budget_max = relaxed_budget
                results = _search_projects(projects_table, relaxed_reqs, user_input)

                if results:
                    # Found projects with expanded budget
                    original_budget_display = f"{current_reqs.budget_max:.2f} Cr" if current_reqs.budget_max >= 1 else f"{int(current_reqs.budget_max * 100)} Lacs"
                    expansion_display = f"{relaxed_budget:.2f} Cr" if relaxed_budget >= 1 else f"{int(relaxed_budget * 100)} Lacs"

                    context_msg = f"No projects found under {original_budget_display}. Here are the nearest options up to {expansion_display}"
                    budget_expanded = True
                    logger.info(f"Budget expanded from {original_budget_display} to {expansion_display}, found {len(results)} projects")
                    break

        state.last_search_results = results
        state.last_shown_projects = results[:5]

        if results:
            # Only set default context_msg if not already set by budget expansion
            if not budget_expanded:
                if is_nearby_query:
                    context_msg = f"Found {len(results)} projects within 10km of **{current_reqs.location}**"
                elif current_reqs.budget_max:
                    context_msg = f"Found {len(results)} projects generally within **{current_reqs.budget_max} Cr**"
            
            # Simplified text response for UI - cards will show details
            action_response = f"{context_msg or 'Found the following matching projects'}. You can swipe through the cards below to explore, or ask for specific details."
        else:
            # Provide specific guidance based on what was searched
            suggestions = []
            if current_reqs.budget_max:
                suggestions.append(f"increase your budget (currently {current_reqs.budget_max} Cr)")
            if current_reqs.location:
                suggestions.append(f"try nearby areas around {current_reqs.location}")
            if current_reqs.configuration:
                suggestions.append("consider different BHK configurations")

            suggestion_text = ", ".join(suggestions) if suggestions else "broaden your search criteria"
            action_response = f"I couldn't find projects matching your exact criteria. You can try to: {suggestion_text}."

    # --- C. COMPARISON ---
    if intent == "comparison":
        # Extract project names from query - look for "or" pattern
        projects_mentioned = []

        if " or " in user_input.lower():
            parts = user_input.lower().split(" or ")
            for part in parts[:2]:  # Max 2 projects
                # Try to find project by name in each part
                words = part.split()
                for i, word in enumerate(words):
                    # Check multi-word project names
                    for length in [4, 3, 2, 1]:
                        if i + length <= len(words):
                            potential_name = " ".join(words[i:i+length])
                            proj = _find_project_by_name(projects_table, potential_name)
                            if proj and proj.get('name') not in [p.get('name') for p in projects_mentioned]:
                                projects_mentioned.append(proj)
                                break
                    if len(projects_mentioned) >= 2:
                        break

        if len(projects_mentioned) >= 2:
            # Compare the two projects
            p1, p2 = projects_mentioned[0], projects_mentioned[1]
            action_response = f"**Comparing {p1['name']} vs {p2['name']}**\n\n"
            action_response += f"**{p1['name']}:**\n- Location: {p1.get('location', 'N/A')}\n- Budget: {p1.get('budget_min', 0)/100:.2f} - {p1.get('budget_max', 0)/100:.2f} Cr\n- Possession: {p1.get('possession_year', 'N/A')} {p1.get('possession_quarter', '')}\n- Status: {p1.get('status', 'N/A')}\n\n"
            action_response += f"**{p2['name']}:**\n- Location: {p2.get('location', 'N/A')}\n- Budget: {p2.get('budget_min', 0)/100:.2f} - {p2.get('budget_max', 0)/100:.2f} Cr\n- Possession: {p2.get('possession_year', 'N/A')} {p2.get('possession_quarter', '')}\n- Status: {p2.get('status', 'N/A')}\n\n"
            action_response += "Both projects offer excellent value. Would you like detailed information about either?"

            # Set both projects in response
            results = [p1, p2]
        else:
            # Fallback to generic comparison advice
            action_response = generate_persuasion_text("Project Comparison", f"Compare {state.selected_project_name} vs others in {current_reqs.location}")

    # --- D. LOCATION INFO (Distance queries) ---
    if intent == "location_info":
        # Try to extract project name from query
        potential_project = None

        # Try multi-word combinations
        words = user_input.lower().split()
        for i in range(len(words)):
            for length in [3, 2, 1]:  # Try 3-word, 2-word, 1-word combinations
                if i + length <= len(words):
                    test_name = " ".join(words[i:i+length])
                    potential_project = _find_project_by_name(projects_table, test_name)
                    if potential_project:
                        break
            if potential_project:
                break

        if potential_project:
            # Found project - provide connectivity info
            description = potential_project.get('description', '')
            location = potential_project.get('location', '')

            # Extract distance/connectivity info from description if present
            action_response = f"🗺️ **Connectivity: {potential_project['name']}**\n\nLocation: {location}\n\n"

            if description and any(keyword in description.lower() for keyword in ["km", "near", "airport", "metro", "close"]):
                action_response += f"{description}\n\n"
            else:
                action_response += "For precise distance calculations, please check Google Maps or contact the RM for detailed connectivity information.\n\n"

            results = [potential_project]
        else:
            action_response = "To provide distance information, could you specify which project you're interested in?"

    # --- E. SALES SUPPORT / OBJECTIONS ---
    # Expand to include ambiguous queries with sales patterns
    is_sales_query = intent in ["sales_support", "objection_budget", "objection_location", "objection_possession"]
    has_sales_patterns = any(p in user_lower for p in ["setup", "arrange", "schedule", "book", "meeting", "visit"])

    if is_sales_query or (intent == "ambiguous" and has_sales_patterns):
        # Call Sales Conversation Logic
        resp, _, _, _ = sales_conversation.handle_sales_query(user_input)
        if resp:
            action_response = resp
        else:
            # Fallback to GPT
            action_response = generate_persuasion_text(intent if is_sales_query else "sales_support", user_input)

    # --- E. SCHEDULE VISIT ---
    if intent == "schedule_visit":
        action_response = sales_formatter.format_project_card({"name": state.selected_project_name or "Project"}, detailed=False)
        action_response += "\n\n📅 **Let's book it!**\nPlease share your preferred date and time."

    if not action_response:
        action_response = "Could you tell me a bit more about what you're looking for? (Location, Budget, or specific Project)"

    # --- STRUCTURED DATA POPULATION (for assist.py) ---
    # Convert action_response (markdown) to bullets for frontend if empty
    bullets = [line.strip().lstrip('-•*').strip() for line in action_response.split('\n') if line.strip() and not line.startswith('#')]
    
    return FlowResponse(
        extracted_requirements=current_reqs.model_dump(),
        current_node="ROUTER",
        system_action=action_response,
        next_redirection="ROUTER",
        answer_bullets=bullets,
        projects=results[:5] if intent in ["project_discovery", "contextual_query", "ambiguous"] else ([] if not project or intent != "project_specific" else [project]),
        pitch_help="Focus on the benefits of this choice." if intent != "project_specific" else f"Highlight the USP of {state.selected_project_name}",
        next_suggestion="Ask if they would like to visit the site." if intent != "schedule_visit" else "Confirm the slot and pickup details.",
        coaching_point="Use urgency for high-interest projects." if intent == "project_specific" else "Build rapport and understand their lifestyle needs."
    )

def _generate_project_details_response(project: dict, user_query: str) -> str:
    """
    Generate conversational GPT response about project details/amenities.
    Uses project DB data as context for GPT to generate natural response.
    """
    try:
        import openai
        import os

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Prepare project context
        project_context = f"""
Project: {project.get('name')}
Location: {project.get('location')}
Configuration: {project.get('configuration')}
Price Range: ₹{project.get('budget_min', 0)/100:.2f} Cr - ₹{project.get('budget_max', 0)/100:.2f} Cr
Status: {project.get('status')}
Possession: Q{project.get('possession_quarter')} {project.get('possession_year')}
Amenities: {project.get('amenities')}
USP: {project.get('usp')}
Developer: {project.get('developer')}
RERA: {project.get('rera_number')}
"""

        prompt = f"""You are a real estate sales assistant helping a customer understand a project.

Project Information:
{project_context}

Customer Question: "{user_query}"

Generate a helpful, conversational response (3-5 bullet points) that:
1. Directly answers their question using the project data above
2. Highlights key features relevant to their question
3. Uses natural, sales-friendly language (not robotic)
4. Uses bold formatting for emphasis (**text**)

Format as bullet points starting with "•" or "-"."""

        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            messages=[
                {"role": "system", "content": "You are a helpful real estate sales assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )

        return response.choices[0].message.content.strip()

    except openai.RateLimitError:
        logger.error("OpenAI RateLimitError in _generate_project_details_response")
        raise
    except Exception as e:
        logger.error(f"GPT project details generation failed: {e}")
        # Fallback to formatted response
        from services.sales_formatter import sales_formatter
        return sales_formatter.format_pitch_response(project)

def _get_mock_projects():
    from services.hybrid_retrieval import hybrid_retrieval
    if not hybrid_retrieval.mock_projects:
        hybrid_retrieval._load_mock_data()
    return hybrid_retrieval.mock_projects

def _find_project_by_name(table, name_query):
    """Helper to find project name with case-insensitive matching."""
    if not name_query: return None

    # Fetch all projects from DB
    if table:
        try:
            all_projs = table.select(
                table.project_id, table.name, table.location, table.zone, table.budget_min, table.budget_max,
                table.configuration, table.status, table.possession_year, table.possession_quarter,
                table.amenities, table.usp, table.brochure_url, table.rm_details
            ).collect()
        except Exception as e:
            logger.error(f"DB Error finding project: {e}")
            all_projs = _get_mock_projects()
    else:
        all_projs = _get_mock_projects()

    # Step 1: Case-insensitive exact match (FIRST PRIORITY)
    name_query_lower = name_query.lower()
    for p in all_projs:
        if p['name'].lower() == name_query_lower:
            return p

    # Step 2: Word-based partial match (NEW - SECOND PRIORITY)
    # Match if any word in query matches any significant word in project name
    query_words = set(name_query_lower.split())
    # Filter out common words like "the", "of", "in"
    stop_words = {"the", "of", "in", "at", "on", "and", "or"}
    query_words = query_words - stop_words

    for p in all_projs:
        project_words = set(p['name'].lower().split())
        project_words = project_words - stop_words

        # Check for intersection (any common significant word)
        if query_words & project_words:
            logger.info(f"✓ Word-based match: '{name_query}' → '{p['name']}'")
            return p

    # Step 3: Fuzzy match fallback (THIRD PRIORITY)
    import difflib
    names = [p['name'] for p in all_projs]
    matches = difflib.get_close_matches(name_query, names, n=1, cutoff=0.4)  # Lowered from 0.6
    if matches:
        target = matches[0]
        for p in all_projs:
            if p['name'] == target:
                logger.info(f"✓ Fuzzy match: '{name_query}' → '{p['name']}' (score >= 0.4)")
                return p

    return None

def _search_projects(table, reqs, query_text):
    """Helper for search logic with locality priority scoring."""

    all_rows = []
    if table:
        try:
            # Fetch all (optimization: filter in DB if possible, but python filter is safer for complex logic)
            all_rows = table.select(
                table.project_id, table.name, table.location, table.zone, table.budget_min, table.budget_max,
                table.configuration, table.status, table.possession_year
            ).collect()
        except Exception as e:
            logger.error(f"DB Search error: {e}")
            all_rows = []

    if not all_rows:
        all_rows = _get_mock_projects()

    matches = []
    for p in all_rows:
        score = 0  # Higher score = better match

        # 1. Zone Filtering (Required if specified)
        if reqs.area:
            project_zone = str(p.get('zone', '')).lower()
            project_location = str(p.get('location', '')).lower()
            area_lower = reqs.area.lower()

            if area_lower in project_zone:
                score += 10  # Zone match
            elif area_lower in project_location:
                score += 10
            else:
                continue  # Hard filter: skip if zone doesn't match

        # 2. Locality Priority (Score-based)
        if reqs.location:
            project_location = str(p.get('location', '')).lower()
            location_lower = reqs.location.lower()

            if location_lower in project_location:
                # Check if it's an exact locality match or just zone match
                location_parts = project_location.split(',')
                if location_parts and location_lower in location_parts[0].lower():
                    score += 100  # Exact locality match (e.g., "Sarjapur Road")
                else:
                    score += 50   # Locality mentioned but not primary
            else:
                # If locality specified but not found, downgrade score but don't filter
                score -= 10

        # 3. Budget Filter
        if reqs.budget_max:
            if not p.get('budget_min') or p.get('budget_min') == 0:
                continue  # Skip invalid data

            project_min_cr = p['budget_min'] / 100
            if project_min_cr > (reqs.budget_max * 1.1):
                continue  # Hard filter: over budget

            # Score projects closer to budget higher
            if project_min_cr <= reqs.budget_max:
                score += 20  # Within budget
            else:
                score += 10  # Slightly over (within tolerance)

        # 4. Configuration Filter (with higher BHK support)
        if reqs.configuration:
            user_bhk = int(reqs.configuration[0]) if reqs.configuration[0].isdigit() else None

            if user_bhk:
                config_str = str(p.get('configuration', '')).lower()
                project_has_match = False

                # Check for exact BHK match
                if f"{user_bhk}bhk" in config_str or f"{user_bhk} bhk" in config_str:
                    project_has_match = True
                    score += 30  # Exact config match

                # Check for higher BHK within budget
                elif reqs.budget_max:
                    for bhk in range(user_bhk + 1, 6):
                        if f"{bhk}bhk" in config_str or f"{bhk} bhk" in config_str:
                            if p.get('budget_max') and (p['budget_max']/100) <= reqs.budget_max:
                                project_has_match = True
                                score += 15  # Higher BHK within budget
                                logger.debug(f"Including {p.get('name')}: {bhk}BHK within budget")
                                break

                if not project_has_match:
                    continue  # Hard filter: no matching configuration

        # Add project with score
        p['_match_score'] = score
        matches.append(p)

    # Sort by match score (highest first)
    matches.sort(key=lambda x: x.get('_match_score', 0), reverse=True)

    logger.info(f"Zone: {reqs.area}, Locality: {reqs.location}, Budget: {reqs.budget_max} Cr -> Found {len(matches)} matches")
    if matches:
        logger.debug(f"Top 3 matches: {[(p.get('name'), p.get('_match_score')) for p in matches[:3]]}")

    return matches

# Bridge to expose as execute_flow for main.py compatibility
def execute_flow(state: FlowState, user_input: str, chat_history: List[Dict[str, str]] = []) -> FlowResponse:
    return execute_sales_copilot_flow(state, user_input, chat_history)


class FlowEngine:
    """Wrapper class for flowchart-driven conversation logic."""
    
    def __init__(self):
        self.sessions: Dict[str, FlowState] = {}
    
    def get_or_create_session(self, session_id: str) -> FlowState:
        """Get existing session or create new one."""
        if session_id not in self.sessions:
            self.sessions[session_id] = FlowState()
        return self.sessions[session_id]
    
    def process(self, session_id: str, user_input: str) -> FlowResponse:
        """Process user input and return flow response."""
        state = self.get_or_create_session(session_id)
        response = execute_flow(state, user_input)
        # Update session state
        state.current_node = response.next_redirection
        return response
    
    def reset_session(self, session_id: str) -> None:
        """Reset a session to initial state."""
        if session_id in self.sessions:
            del self.sessions[session_id]


# Global instance
flow_engine = FlowEngine()
