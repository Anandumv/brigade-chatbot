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
from services.sales_agent_prompt import SALES_AGENT_SYSTEM_PROMPT
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
    budget_max: Optional[float] = None
    possession_year: Optional[int] = None
    possession_year: Optional[int] = None
    possession_type: Optional[str] = None # "RTMI" or "Under Construction"
    project_name: Optional[str] = None # Explicit project name (e.g. "Birla Evara")

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
    system_action: str
    next_redirection: str

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
                {"role": "system", "content": "Extract JSON: configuration (e.g. 2BHK), location, budget_max (float in Cr), possession_year (int), possession_type (RTMI/Under Construction), project_name (e.g. 'Birla Evara', null if generic). Return null if missing."},
                {"role": "user", "content": user_input}
            ],
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return FlowRequirements(**data)
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
                    "content": SALES_AGENT_SYSTEM_PROMPT + """

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
    if new_reqs.budget_max:
        current_reqs.budget_max = new_reqs.budget_max
    if new_reqs.configuration:
        current_reqs.configuration = new_reqs.configuration
    
    # 2. Classify Intent
    # ------------------
    context_str = f"Last Intent: {state.last_intent}. Last Project: {state.selected_project_name}. Loc: {current_reqs.location}"
    intent_data = classify_user_intent(user_input, context_str, chat_history)
    intent = intent_data.get("intent", "ambiguous")
    state.last_intent = intent
    
    logger.info(f"Router Intent: {intent} | Project: {state.selected_project_name}")

    # 3. Route Execution
    # ------------------
    action_response = ""
    next_node = "ROUTER" # Placeholder
    
    projects_table = get_projects_table()
    
    # --- A. PROJECT SPECIFIC (Details, Brochure, RM) ---
    if intent == "project_specific" or (state.selected_project_name and intent in ["request_info", "schedule_visit"]):
        # Identify Project
        target_name = new_reqs.project_name or state.selected_project_name
        if target_name:
            # DB Lookup (Exact/Fuzzy)
            project = _find_project_by_name(projects_table, target_name)
            
            if project:
                state.selected_project_id = project['project_id']
                state.selected_project_name = project['name']
                
                # If specifically asking for brochure/RM
                if "brochure" in user_input.lower():
                    url = project.get('brochure_url')
                    action_response = f"📄 **Brochure for {project['name']}**\n{url or 'Available on request via RM.'}"
                elif "rm" in user_input.lower() or "number" in user_input.lower():
                    rm = project.get('rm_details') or "+91-9988776655 (Support)"
                    action_response = f"📞 **Relationship Manager for {project['name']}**\n{rm}"
                else:
                    # Full Pitch
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
                            projects_table.project_id, projects_table.name, projects_table.location, 
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
             results = _search_projects(projects_table, current_reqs, user_input)

        state.last_search_results = results
        state.last_shown_projects = results[:5]
        
        if results:
            context_msg = ""
            if is_nearby_query:
                context_msg = f"Found {len(results)} projects within 10km of **{current_reqs.location}**:"
            elif current_reqs.budget_max:
                context_msg = f"Found {len(results)} projects generally within **{current_reqs.budget_max} Cr**:"
            
            action_response = sales_formatter.format_list_response(results[:5], context_msg)
        else:
            action_response = "I couldn't find matches for those exact criteria. Try broadening your location or budget?"

    # --- C. COMPARISON ---
    if intent == "comparison":
        # Get last project vs new project? or generic comparison?
        # For now, generic advice + data
        action_response = generate_persuasion_text("Project Comparison", f"Compare {state.selected_project_name} vs others in {current_reqs.location}")

    # --- D. SALES SUPPORT / OBJECTIONS ---
    if intent in ["sales_support", "objection_budget", "objection_location", "objection_possession"]:
        # Call Sales Conversation Logic
        resp, _, _, _ = sales_conversation.handle_sales_query(user_input)
        if resp:
            action_response = resp
        else:
            # Fallback to GPT
            action_response = generate_persuasion_text(intent, user_input)

    # --- E. SCHEDULE VISIT ---
    if intent == "schedule_visit":
        action_response = sales_formatter.format_project_card({"name": state.selected_project_name or "Project"}, detailed=False)
        action_response += "\n\n📅 **Let's book it!**\nPlease share your preferred date and time."

    if not action_response:
        action_response = "Could you tell me a bit more about what you're looking for? (Location, Budget, or specific Project)"

    return FlowResponse(
        extracted_requirements=current_reqs.model_dump(),
        current_node="ROUTER",
        system_action=action_response,
        next_redirection="ROUTER"
    )

def _get_mock_projects():
    from services.hybrid_retrieval import hybrid_retrieval
    if not hybrid_retrieval.mock_projects:
        hybrid_retrieval._load_mock_data()
    return hybrid_retrieval.mock_projects

def _find_project_by_name(table, name_query):
    """Helper to find project name."""
    if not name_query: return None
    
    # DB Search
    if table:
        try:
            # 1. Exact
            res = table.select(
                table.project_id, table.name, table.location, table.budget_min, table.budget_max,
                table.configuration, table.status, table.possession_year, table.possession_quarter,
                table.amenities, table.usp, table.brochure_url, table.rm_details
            ).where(table.name == name_query).collect()
            if res: return res[0]
            
            # 2. Fuzzy/Regex
            all_projs = table.select(
                table.project_id, table.name, table.location, table.budget_min, table.budget_max,
                table.configuration, table.status, table.possession_year, table.possession_quarter,
                table.amenities, table.usp, table.brochure_url, table.rm_details
            ).collect()
        except Exception as e:
            logger.error(f"DB Error finding project: {e}")
            all_projs = _get_mock_projects()
    else:
        all_projs = _get_mock_projects()

    # Search in all_projs (DB or Mock)
    import difflib
    names = [p['name'] for p in all_projs]
    matches = difflib.get_close_matches(name_query, names, n=1, cutoff=0.6)
    if matches:
        target = matches[0]
        for p in all_projs:
            if p['name'] == target: return p
    return None

def _search_projects(table, reqs, query_text):
    """Helper for search logic (simplified from original)."""
    
    all_rows = []
    if table:
        try:
            # Fetch all (optimization: filter in DB if possible, but python filter is safer for complex logic)
            all_rows = table.select(
                table.project_id, table.name, table.location, table.budget_min, table.budget_max,
                table.configuration, table.status, table.possession_year
            ).collect()
        except Exception as e:
            logger.error(f"DB Search error: {e}")
            all_rows = []
            
    if not all_rows:
        all_rows = _get_mock_projects()
        
    matches = []
    for p in all_rows:
        # Filter Location
        if reqs.location and reqs.location.lower() not in str(p.get('location', '')).lower():
            continue
        # Filter Budget
        if reqs.budget_max and p.get('budget_min'):
            if (p['budget_min']/100) > (reqs.budget_max * 1.1): # 10% tolerance
                continue
        # Filter Config
        if reqs.configuration:
            # Naive
            if reqs.configuration.lower()[:3] not in str(p.get('configuration', '')).lower(): 
                continue
        
        matches.append(p)
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
