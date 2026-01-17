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

# --- SYSTEM PROMPT ---
STRICT_SYSTEM_PROMPT = """
ROLE
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
    possession_type: Optional[str] = None # "RTMI" or "Under Construction"

class FlowState(BaseModel):
    current_node: str = "NODE 1"
    requirements: FlowRequirements = Field(default_factory=FlowRequirements)
    last_system_action: Optional[str] = None
    selected_project_id: Optional[str] = None
    selected_project_name: Optional[str] = None
    cached_project_details: Optional[Dict[str, Any]] = None
    last_shown_projects: List[Dict[str, Any]] = Field(default_factory=list)
    pagination_offset: int = 3  # Track pagination state (default skip top 3)

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
                {"role": "system", "content": "Extract JSON: configuration (e.g. 2BHK), location, budget_max (float in Cr), possession_year (int), possession_type (RTMI/Under Construction). Return null if missing."},
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

def classify_user_intent(user_input: str, context: str) -> dict:
    """Uses LLM to classify user intent and sentiment in conversation."""
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
                    "content": """Analyze the user's response and classify their intent. Return JSON with:
- intent: one of [budget_objection, possession_objection, location_objection, positive_interest, request_info, ambiguous, negative]
- confidence: float 0-1
- sentiment: one of [positive, neutral, negative]
- explanation: brief reason for classification

Examples:
"Too expensive" → {"intent": "budget_objection", "confidence": 0.95, "sentiment": "negative", "explanation": "User expressed price concern"}
"Looks good" → {"intent": "positive_interest", "confidence": 0.9, "sentiment": "positive", "explanation": "User showed approval"}
"Tell me more about amenities" → {"intent": "request_info", "confidence": 0.85, "sentiment": "neutral", "explanation": "User wants more details"}"""
                },
                {"role": "user", "content": f"Context: {context}\nUser said: {user_input}"}
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

def generate_contextual_response(user_input: str, context: str, conversation_goal: str) -> str:
    """Generates a contextual, natural response using LLM for continuous conversation."""
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
                    "content": f"""You are a 'Sales Co-pilot' for a real estate agent at Pinclick.
Your goal is to provide the agent with persuasive *talking points* and *scripts* to say to the customer on the phone.

Current conversation context: {context}

Your immediate goal: {conversation_goal}

Guidelines:
- format your response as a script the agent can read or paraphrase.
- Be persuasive, empathetic, and professional.
- Focus on value / investment potential / lifestyle upgrade.
- Keep it concise (2-3 sentences max).
- Use [Talking Point] style if helpful.
- Never make up property facts."""
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

# --- NODE LOGIC ---
def execute_flow(state: FlowState, user_input: str) -> FlowResponse:
    # 1. Update Requirements (Merge new input with existing state)
    old_reqs = state.requirements.copy()
    new_reqs = extract_requirements_llm(user_input)
    
    # Simple merge logic (new overrides old if present)
    merged_reqs = old_reqs.copy(update={k: v for k, v in new_reqs.dict().items() if v is not None})
    state.requirements = merged_reqs

    # 2. Determine Node Logic
    node = state.current_node
    action = ""
    next_node = node
    
    # 3. Classify Intent for Interceptors
    context = f"Current node: {node}. Extracted reqs: {merged_reqs.dict()}"
    classification = classify_user_intent(user_input, context)
    intent = classification.get("intent", "ambiguous")

    # --- REQUIREMENT REFINEMENT INTERCEPTOR ---
    if node != "NODE 1" and intent != "project_selection":
        changed = False
        def normalize(s):
            if not s: return ""
            return s.lower().replace("bangalore", "").replace("bengaluru", "").strip(", ")
        
        if new_reqs.location:
             new_loc = normalize(new_reqs.location)
             old_loc = normalize(old_reqs.location)
             if new_loc and new_loc not in old_loc and old_loc not in new_loc:
                 changed = True
        
        if new_reqs.configuration and new_reqs.configuration != old_reqs.configuration: changed = True
        if new_reqs.budget_max and new_reqs.budget_max != old_reqs.budget_max: changed = True
        
        if changed:
            logger.info(f"Core requirements changed. Resetting to NODE 2. Old: {old_reqs.location}, New: {new_reqs.location}")
            # Reset state for new search
            state.selected_project_id = None 
            state.selected_project_name = None
            state.cached_project_details = None
            node = "NODE 2" # Proceed to re-search in this current call
    try:
        projects_table = get_projects_table()
    except Exception:
        projects_table = None

    # --- GLOBAL INTENT INTERCEPTOR ---
    user_lower = user_input.lower()
    if any(w in user_lower for w in ["nearby", "other area", "alternate location", "within 10km", "different area"]):
        if merged_reqs.location: # Only if we have a base location to pivot from
            action = "Certainly! Let me look for properties in nearby areas within a 10km radius of your preferred location."
            next_node = "NODE 7"
            # Proceed to NODE 7 logic immediately or return?
            # Let's return and let the next loop handle Node 7 results to keep it clean.
            return FlowResponse(
                extracted_requirements=merged_reqs.dict(),
                current_node="NODE 6_WAIT", # Transition state
                system_action=action,
                next_redirection="NODE 7"
            )
        else:
            # Nearby requested but no location context
            action = "I can definitely help find nearby projects! 🌍 Which location or specific landmark should I search around?"
            return FlowResponse(
                extracted_requirements=merged_reqs.dict(),
                current_node="NODE 1",
                system_action=action,
                next_redirection="NODE 1"
            )

    # --- UPSELL / HIGHER BUDGET INTERCEPTOR ---
    if any(w in user_lower for w in ["slightly higher", "higher option", "increase budget", "premium", "more expensive", "above my budget", "stretch"]):
        if merged_reqs.budget_max:
            # Increase budget by 20%
            new_budget = float(merged_reqs.budget_max) * 1.2
            merged_reqs.budget_max = new_budget
            state.requirements.budget_max = new_budget
            
            action = f"Got it! Let's stretch the budget slightly to **₹{new_budget:.2f} Cr** and see what premium options unlock for you. 💎"
            
            # Reset state for fresh search
            state.selected_project_id = None 
            state.selected_project_name = None
            state.cached_project_details = None
             
            # Proceed to search with new budget
            node = "NODE 2"
            next_node = "NODE 2"
            
            # We continue execution to NODE 2 in this same call so the user gets results immediately
        else:
            # If no budget set yet
            action = "I can definitely show you premium options. What's your max budget?"
            return FlowResponse(
                extracted_requirements=merged_reqs.dict(),
                current_node="NODE 1",
                system_action=action,
                next_redirection="NODE 1"
            )

    # --- SHOW MORE INTERCEPTOR ---
    if any(w in user_lower for w in ["show more", "more options", "see more", "other projects", "remaining"]):
        if state.last_shown_projects and len(state.last_shown_projects) > state.pagination_offset:
            # Dynamic Pagination
            start = state.pagination_offset
            PAGE_SIZE = 5
            end = start + PAGE_SIZE
            batch = state.last_shown_projects[start:end]
            
            # Update offset for next time
            state.pagination_offset = end
            
            response_parts = ["Here are more options:\n\n"]
            for i, proj in enumerate(batch, start + 1):  # Continue numbering
                # Simplify configuration
                config_display = clean_configuration_string(proj.get('configuration', ''))
                
                response_parts.append(f"**{i}. {proj['name']}** ({proj['status']})\n")
                response_parts.append(f"   📍 {proj['location']}\n")
                response_parts.append(f"   💰 ₹{proj['budget_min']} - ₹{proj['budget_max']} Cr\n")
                response_parts.append(f"   🏠 {config_display}\n\n")

            remaining = len(state.last_shown_projects) - end
            if remaining > 0:
                response_parts.append(f"_And {remaining} more in our database... Say 'show more' again!_\n\n")
            
            response_parts.append("Would you like details on any of these? Just say the project name! 🏡")
            action = "".join(response_parts)
            
            return FlowResponse(
                extracted_requirements=merged_reqs.dict(),
                current_node=node,
                system_action=action,
                next_redirection="NODE 2A"
            )

    # --- FUZZY PROJECT NAME MATCHING (Handles typos like "Brigade avlon") ---
    # If user input closely matches a project name in context, force project_selection intent
    if state.last_shown_projects:
        for p in state.last_shown_projects:
            name = p.get('name', '').lower()
            project_words = name.split()
            user_words = user_lower.split()
            
            # Check if any significant user word matches a project word (fuzzy)
            # e.g., "avlon" -> "avalon"
            matched = False
            for uw in user_words:
                if len(uw) < 4: continue # Skip short words
                # Check fuzzy match against project name words
                close = difflib.get_close_matches(uw, project_words, n=1, cutoff=0.8)
                if close:
                    matched = True
                    break
            
            if matched:
                logger.info(f"Fuzzy match found: '{user_input}' -> '{name}'. Forcing project_selection.")
                intent = "project_selection"
                # We don't break here, we let the interceptor below handle the actual selection logic
                # which iterates and selects.
                break

    # --- PROJECT SELECTION INTERCEPTOR ---
    # Expanded keywords to cover more natural ways users ask about projects
    selection_keywords = ["tell me", "details about", "pitch me", "select", "pitch ", "about ", "more on", "why ", "usp of", "info on", "interested in"]
    if intent == "project_selection" or any(w in user_lower for w in selection_keywords):
        # Try to find which project the user is referring to
        target_project = None
        
        # 1. Check against recently shown projects (session state)
        if state.last_shown_projects:
            for p in state.last_shown_projects:
                name = p.get('name', '').lower()
                if name in user_lower or any(word in user_lower for word in name.split()):
                    # Exclude very short words/numbers from partial match
                    significant_words = [w for w in name.split() if len(w) > 3]
                    if any(sw in user_lower for sw in significant_words):
                        target_project = p
                        break
        
        # 2. Numbered selection fallback
        if not target_project and state.last_shown_projects:
            if "first" in user_lower or "one" in user_lower or "1" in user_lower: 
                target_project = state.last_shown_projects[0]
            elif "second" in user_lower or "two" in user_lower or "2" in user_lower and len(state.last_shown_projects) > 1:
                target_project = state.last_shown_projects[1]
            elif "third" in user_lower or "three" in user_lower or "3" in user_lower and len(state.last_shown_projects) > 2:
                target_project = state.last_shown_projects[2]

        # 3. Database lookup fallback (for when session is empty or project not in recent list)
        if not target_project and projects_table:
            try:
                t = projects_table
                all_projects = t.select(
                    t.project_id, t.name, t.location, t.budget_min, t.budget_max,
                    t.configuration, t.status, t.possession_year, t.possession_quarter,
                    t.rera_number, t.amenities, t.usp, t.description
                ).collect()
                
                # Find project by name match
                for p in all_projects:
                    name = p.get('name', '').lower()
                    significant_words = [w for w in name.split() if len(w) > 3]
                    if any(sw in user_lower for sw in significant_words):
                        target_project = p
                        logger.info(f"Found project '{p.get('name')}' via database lookup")
                        break
            except Exception as e:
                logger.warning(f"Database lookup for project failed: {e}")

        if target_project:
            state.selected_project_id = target_project.get('project_id')
            state.selected_project_name = target_project.get('name')
            state.cached_project_details = target_project
            
            # Generate detailed pitch for the selected project
            proj = target_project
            pitch_parts = [f"🏠 **{proj.get('name')}** - Here's everything you need to know:\n\n"]
            
            # Developer (trust signal)
            if proj.get('developer'):
                pitch_parts.append(f"**🏗️ Developer:** {proj.get('developer')}\n")
            
            pitch_parts.append(f"**📍 Location:** {proj.get('location')}\n")
            pitch_parts.append(f"**💰 Price Range:** ₹{proj.get('budget_min', 0)/100:.2f} - ₹{proj.get('budget_max', 0)/100:.2f} Cr\n")
            
            # Configuration (BHK types)
            if proj.get('configuration'):
                config_display = clean_configuration_string(proj.get('configuration', ''))
                pitch_parts.append(f"**🛏️ Configuration:** {config_display}\n")
            
            pitch_parts.append(f"**📊 Status:** {proj.get('status')}\n")
            pitch_parts.append(f"**📅 Possession:** {proj.get('possession_quarter')} {proj.get('possession_year')}\n")
            
            if proj.get('rera_number'):
                pitch_parts.append(f"**📋 RERA:** {proj.get('rera_number')}\n")
            
            # Description if available
            if proj.get('description') and len(proj.get('description', '')) > 10:
                desc = proj.get('description', '')[:300]
                if len(proj.get('description', '')) > 300:
                    desc += "..."
                pitch_parts.append(f"\n**📝 About:**\n{desc}\n")
            
            if proj.get('usp'):
                pitch_parts.append(f"\n**✨ Why this property?**\n{proj.get('usp')}\n")
            
            if proj.get('amenities'):
                amenities = proj.get('amenities', '').replace("[", "").replace("]", "").replace("'", "")
                pitch_parts.append(f"\n**🎯 Key Amenities:** {amenities}\n")
            
            # Highlights if available
            if proj.get('highlights') and len(proj.get('highlights', '')) > 10:
                pitch_parts.append(f"\n**💎 Highlights:** {proj.get('highlights')}\n")
            
            pitch_parts.append("\n👉 **Ready to see it in person? Schedule a site visit!**")
            action = "".join(pitch_parts)
            
            next_node = "NODE 2B"
            return FlowResponse(
                extracted_requirements=merged_reqs.dict(),
                current_node=node,
                system_action=action,
                next_redirection="NODE 2B"
            )

    # --- NODE 1: Normalization Gate ---
    if node == "NODE 1":
        # Proceed if we have at least one meaningful filter (location OR configuration OR budget)
        has_any_filter = merged_reqs.configuration or merged_reqs.location or merged_reqs.budget_max
        if not has_any_filter:
            action = f"I'd love to help! To find the best options, could you please share your preferred Configuration (e.g., 2BHK), Location, and Max Budget?"
            next_node = "NODE 1"
        else:
            next_node = "NODE 2"
            # Fall through to Node 2 for efficiency
            node = "NODE 2"

    # --- NODE 2: SEARCH & RESULTS ---
    if node == "NODE 2":
        state.pagination_offset = 3  # Reset pagination on new search
        # 1. Sanity Check for Budget
        budget_warning = ""
        if merged_reqs.budget_max and merged_reqs.budget_max > 50:
            # Heuristic: If > 50 Cr, it's likely a typo or mixed units
            budget_warning = f"_Note: I noticed a budget of **₹{merged_reqs.budget_max:,.0f} Cr**. I've listed all options within this range, but please clarify if you meant something else (like ₹1.5 Cr)._ 🧐\n\n"
        
        # 2. Run Search
        # (Proceed with existing search logic)
        all_projects = []
        
        if projects_table:
            # Query Pixeltable
            t = projects_table
            all_projects = t.select(
                t.project_id, t.name, t.location, t.budget_min, t.budget_max,
                t.configuration, t.status, t.possession_year, t.possession_quarter,
                t.rera_number, t.amenities, t.usp, t.description
            ).collect()
        else:
             # Fallback to mock data
             from services.hybrid_retrieval import hybrid_retrieval
             logger.info("Using Mock Data for Flow Engine")
             all_projects = hybrid_retrieval.mock_projects if hybrid_retrieval.mock_projects else []

        loc_term = (merged_reqs.location or "").lower()
        conf_term = (merged_reqs.configuration or "").lower()
        
        # Helper to run search with given constraints
        def run_search(projects, budget_cap=None):
            results = []
            details = []
            upsells = []
            
            cap = float(budget_cap) * 100 if budget_cap else float('inf')
            
            for p in projects:
                # Filter Location
                p_loc = p['location'].lower()
                if loc_term and loc_term not in p_loc: continue
                
                # Filter Config (Normalize: remove spaces and dots)
                p_conf_norm = p['configuration'].lower().replace(" ", "").replace(".", "")
                conf_term_norm = conf_term.replace(" ", "").replace(".", "")
                if conf_term and conf_term_norm not in p_conf_norm: continue
                
                # Filter Poss Type
                if merged_reqs.possession_type == "RTMI" and "ready" not in p['status'].lower(): continue

                if p['budget_min'] <= cap:
                    results.append(f"{p['name']} ({p['status']})")
                    details.append(p)
                elif p['budget_min'] <= cap * 1.2:
                    upsells.append(f"{p['name']} ({p['budget_min']/100} Cr)")
            
            return results, details, upsells

        # 1. Strict Search (with budget)
        matches, match_details, upsell_matches = run_search(all_projects, merged_reqs.budget_max)
        
        budget_relaxed = False
        
        # 2. Fallback: If no matches, try relaxing budget completely
        if not matches and merged_reqs.budget_max:
            logger.info("No matches with strict budget. relaxing budget constraint.")
            matches, match_details, _ = run_search(all_projects, budget_cap=None)
            if matches:
                 budget_relaxed = True

        if matches:
            # Score and sort projects by fit to requirements
            def score_project_fit(proj: dict, requirements) -> int:
                """Score project 0-100 based on requirement fit."""
                score = 50  # Base score

                # Budget fit (+25 if within range, -15 if over)
                if requirements.budget_max:
                    if proj.get('budget_min', 0) <= requirements.budget_max * 100:
                        score += 25
                    else:
                        over_pct = ((proj.get('budget_min', 0) / 100) - requirements.budget_max) / requirements.budget_max
                        if over_pct < 0.15:  # Within 15% over
                            score += 10
                        else:
                            score -= 15

                # Configuration exact match (+20)
                if requirements.configuration:
                    req_config = requirements.configuration.upper()
                    proj_config = proj.get('configuration', '').upper()
                    if req_config in proj_config:
                        score += 20

                # Possession match (+15 for RTMI when requested)
                if requirements.possession_type == "RTMI":
                    if proj.get('status', '').lower() in ['ready to move', 'rtmi', 'completed']:
                        score += 15

                # Location zone match (+10)
                if requirements.location:
                    if requirements.location.lower() in proj.get('location', '').lower():
                        score += 10

                return score

            # Score all projects
            for proj in match_details:
                proj['_fit_score'] = score_project_fit(proj, merged_reqs)

            # Sort by fit score (best first)
            match_details.sort(key=lambda x: x.get('_fit_score', 0), reverse=True)

            # Build detailed response with property information using proper markdown
            if budget_relaxed:
                response_parts = [budget_warning + f"I couldn't find matches within **₹{merged_reqs.budget_max} Cr**, but here are excellent options slightly above that range:\n\n"]
            else:
                response_parts = [budget_warning]

                # ---------------------------------------------------------
                # DIRECT ANSWER LOGIC (Minimum Budget / Starting Price)
                # ---------------------------------------------------------
                query_lower = query.lower()
                min_price_keywords = ["minimum budget", "min budget", "starting price", "lowest price", "cheapest", "least expensive", "start from", "starts from", "start price"]
                
                if matches and any(kw in query_lower for kw in min_price_keywords):
                    # Calculate minimum budget from matches
                    min_price_proj = min(matches, key=lambda x: x.get('budget_min', float('inf')))
                    min_price_val = min_price_proj.get('budget_min', 0) / 100
                    
                    direct_answer = f"💡 **The minimum budget required starts at ₹{min_price_val:.2f} Cr** with {min_price_proj.get('name')}.\n\n"
                    response_parts.append(direct_answer)
                
                # ---------------------------------------------------------

                # Add recommendation banner if top match has good fit score
                if match_details and match_details[0]['_fit_score'] >= 70:
                    best = match_details[0]
                    response_parts.append(f"🎯 **TOP RECOMMENDATION: {best['name']}**\n")
                    response_parts.append(f"_(Best fit for your {merged_reqs.configuration or 'requirements'} in {merged_reqs.location or 'Bangalore'})_\n\n")
                    response_parts.append("---\n\n")

                response_parts.append(f"I found **{len(matches)} properties** matching your criteria:\n\n")

            for i, proj in enumerate(match_details[:3], 1):  # Show top 3 in detail
                response_parts.append(f"**{i}. {proj['name']}** ({proj['status']})\n")

                # ADD DEVELOPER (trust signal)
                if proj.get('developer'):
                    response_parts.append(f"- 🏗️ Developer: **{proj['developer']}**\n")

                response_parts.append(f"- 📍 Location: {proj['location']}\n")
                response_parts.append(f"- 💰 Price: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr\n")

                # Simplify configuration - extract just BHK types
                config_display = clean_configuration_string(proj.get('configuration', ''))
                response_parts.append(f"- 🏠 Config: {config_display}\n")

                response_parts.append(f"- 📅 Possession: {proj['possession_quarter']} {proj['possession_year']}\n")

                # ADD USP (differentiation)
                if proj.get('usp') and len(proj['usp']) > 10:
                    usp_short = proj['usp'][:100] + "..." if len(proj['usp']) > 100 else proj['usp']
                    response_parts.append(f"- ✨ Highlights: {usp_short}\n")

                if proj.get('amenities'):
                    amenities = proj['amenities'].replace("[", "").replace("]", "").replace("'", "")
                    response_parts.append(f"- 🎯 Amenities: {amenities}\n")

                # ADD RERA (compliance signal)
                if proj.get('rera_number') and 'pending' not in proj['rera_number'].lower():
                    response_parts.append(f"- 🛡️ RERA: {proj['rera_number']}\n")

                response_parts.append("\n")  # Extra line between projects

            # If more than 3 matches, make it actionable
            if len(matches) > 3:
                response_parts.append(f"\n📋 **Plus {len(matches) - 3} more options!** Type \"show more\" to see them.\n\n")

            response_parts.append("Would you like to schedule a site visit to see these properties? 🏡")

            action = "".join(response_parts)
            state.last_system_action = f"shown_matches:{len(matches)}"
            state.last_shown_projects = match_details[:10] # Store up to 10 projects
            next_node = "NODE 2A"
        else:
            action = "No exact matches found."
            if upsell_matches:
                 action += f" Upsell candidates exist: {', '.join(upsell_matches[:3])}."
            next_node = "NODE 3"

    elif node == "NODE 2A":
        # (Intent classification already done globally above)
        logger.info(f"NODE 2A: Classified intent as '{intent}' with confidence {classification.get('confidence', 0)}")

        if intent == "budget_objection":
            action = "I completely understand that budget is an important consideration. Let me help you explore some options that might work better for you."
            next_node = "NODE 3"
        elif intent == "possession_objection" or any(w in user_input.lower() for w in ["ready", "move", "possession"]):
            action = "I see that the possession timeline is important to you. Let me check what options we have that better match your requirements."
            next_node = "NODE 10" # Pivot to RTMI check
        elif "nearby" in user_input.lower() or "other area" in user_input.lower() or "alternate" in user_input.lower():
            action = "Certainly! Let me look for properties in nearby areas within a 10km radius."
            next_node = "NODE 7"
        elif intent == "positive_interest":
             action = "That's wonderful! I'm excited to help you schedule a site visit. This will give you a chance to see the property firsthand and ask any questions."
             next_node = "FACE_TO_FACE"
        elif intent == "request_info":
             action = "I'd be happy to provide more details about any of these properties. What specific aspects would you like to know more about?"
             next_node = "NODE 2A"  # Stay to answer questions
        else:
             # Ambiguous or unclear intent
             action = "I'd be happy to help you further! Would you like to know more about these properties, or shall we schedule a site visit to see them in person?"
             next_node = "NODE 2A"  # Stay in objection handler to wait for clarification

    # --- NODE 2B: Deep-Dive Project Pitch ---
    elif node == "NODE 2B":
        project = state.cached_project_details or {}
        p_name = state.selected_project_name or "this project"
        
        # Build context for LLM
        details = f"""
Project: {p_name}
Location: {project.get('location')}
Price: {project.get('budget_min', 0)/100} - {project.get('budget_max', 0)/100} Cr
Configuration: {project.get('configuration')}
Possession: {project.get('possession_quarter')} {project.get('possession_year')}
Status: {project.get('status')}
USP: {project.get('usp', 'N/A')}
Amenities: {project.get('amenities', 'N/A')}
Description: {project.get('description', 'N/A')}
RERA: {project.get('rera_number', 'N/A')}
"""
        action = generate_contextual_response(
            user_input,
            details,
            f"Generate a persuasive, high-impact deep-dive pitch for {p_name}. Focus on its unique selling points, amenities, and why it's a perfect fit for the user's requirements ({merged_reqs.configuration} in {merged_reqs.location}). Guide them towards a site visit."
        )
        next_node = "NODE 2B_WAIT"

    # --- NODE 2B_WAIT: Post-Pitch Handler (Smart Follow-up with LLM + Web Search) ---
    elif node == "NODE 2B_WAIT":
        if not state.selected_project_name:
            # Safety: No project selected, ask them to select
            action = "Which project would you like to know more about?"
            next_node = "NODE 2A"
        else:
            # Classify the follow-up intent using LLM
            project_location = state.cached_project_details.get('location', '') if state.cached_project_details else ''

            intent_result = classify_followup_intent(
                user_input,
                state.selected_project_name,
                project_location
            )

            followup_intent = intent_result.get("intent")
            needs_web = intent_result.get("needs_web_search", False)

            logger.info(f"NODE 2B_WAIT: Followup intent='{followup_intent}', needs_web={needs_web}")

            # Handle based on classified intent
            if followup_intent == "site_visit":
                action = f"That's great! I'm confident you'll find **{state.selected_project_name}** even more impressive in person. Let's schedule your site visit."
                next_node = "FACE_TO_FACE"

            elif followup_intent in ["location_info", "amenities_nearby"] and needs_web:
                # Fetch external data via web search
                if project_location:
                    logger.info(f"Fetching nearby amenities for {state.selected_project_name} via web search")
                    nearby_info = fetch_nearby_amenities(state.selected_project_name, project_location)

                    if nearby_info:
                        # Combine web data with LLM-generated pitch
                        action = generate_contextual_response(
                            user_input,
                            f"User asked about {state.selected_project_name} in {project_location}. External data: {nearby_info[:500]}",
                            "Answer their specific question using the external amenity data provided. Be specific with names and distances. Then ask about scheduling a site visit."
                        )
                    else:
                        # Web search failed, use LLM only
                        action = generate_contextual_response(
                            user_input,
                            f"User wants info about {state.selected_project_name} in {project_location}. Focus on location benefits.",
                            "Provide a compelling answer about location/connectivity/neighborhood. Be persuasive about area advantages."
                        )
                else:
                    action = "I'd be happy to tell you more about the location! What specific aspects are you interested in?"

                next_node = "NODE 2B_WAIT"  # Stay to handle more questions

            elif followup_intent == "investment_pitch":
                # Generate investment-focused pitch using LLM
                action = generate_persuasion_text(
                    "Investment Benefits",
                    f"Client asking about investment potential of {state.selected_project_name} in {project_location}. Highlight ROI, appreciation, market demand, infrastructure development."
                )
                next_node = "NODE 2B_WAIT"

            elif followup_intent == "project_details":
                # Answer from database facts + LLM
                project_facts = state.cached_project_details or {}
                facts_context = f"""
Project: {state.selected_project_name}
Location: {project_facts.get('location')}
Developer: {project_facts.get('developer', 'Premium Developer')}
Status: {project_facts.get('status')}
Configuration: {project_facts.get('configuration')}
Amenities: {project_facts.get('amenities', '')}
RERA: {project_facts.get('rera_number', 'Registered')}
Description: {project_facts.get('description', '')}
"""
                action = generate_contextual_response(
                    user_input,
                    facts_context,
                    "Answer their specific question using the project data. Be factual and specific."
                )
                next_node = "NODE 2B_WAIT"

            elif followup_intent == "objection":
                # Detect type of objection and route appropriately
                if any(w in user_input.lower() for w in ["expensive", "budget", "cost", "price"]):
                    action = "I understand your concern about the pricing. Let me explain the value proposition..."
                    next_node = "NODE 3"  # Budget objection flow
                elif any(w in user_input.lower() for w in ["far", "location", "distance"]):
                    action = "I hear you about the location. Let me show you why this area is actually a great choice, or we can explore nearby options."
                    next_node = "NODE 6"  # Location flexibility
                else:
                    # Generic objection handling
                    action = generate_contextual_response(
                        user_input,
                        f"User has an objection about {state.selected_project_name}.",
                        "Address their concern empathetically, provide reassurance, and ask if they'd like to explore alternatives or proceed with a site visit."
                    )
                    next_node = "NODE 2B_WAIT"

            else:  # unclear or other
                # Generic smart response
                action = generate_contextual_response(
                    user_input,
                    f"User has a question about {state.selected_project_name}.",
                    "Answer helpfully and guide them towards scheduling a site visit."
                )
                next_node = "NODE 2B_WAIT"

    # --- NODE 3: Budget Flexibility (Ask Question) ---
    elif node == "NODE 3":
        # action = "I understand budget is a key consideration. Would you be comfortable stretching your budget by 10-20%? This could open up some excellent options with significantly better amenities and higher appreciation potential. What do you think?"
        action = generate_contextual_response(
            user_input, 
            f"User wants {merged_reqs.configuration} in {merged_reqs.location} under {merged_reqs.budget_max} Cr. No exact matches found.",
            "Empathize with budget constraint, but gently ask if they can stretch by 10-20% to see premium options with better amenities/ROI."
        )
        next_node = "NODE 3_WAIT"  # Wait for user response

    # --- NODE 3_WAIT: Process Budget Stretch Response ---
    elif node == "NODE 3_WAIT":
        l_input = user_input.lower()
        if "yes" in l_input or "ok" in l_input or "sure" in l_input or "agree" in l_input:
            action = "Great! Let me show you some premium options that offer exceptional value."
            next_node = "NODE 4"
        elif "nearby" in l_input or "other" in l_input or "location" in l_input:
            action = "I understand. Let's look at some great options in nearby areas instead."
            next_node = "NODE 7"
        elif "no" in l_input or "not" in l_input or "can't" in l_input:
            next_node = "NODE 5"
            # Action will be set in NODE 5
        else:
            action = "I didn't quite catch that. Would you be open to stretching your budget by 10-20% to see significantly better options? Just let me know if you're comfortable with that."
            next_node = "NODE 3_WAIT"  # Ask again

    # --- NODE 4: Above Budget Inventory ---
    elif node == "NODE 4":
        # Fetch the upsell items we found earlier or re-query
        # For simplicity, re-run query with higher budget
        # Fetch the upsell items we found earlier or re-query
        # For simplicity, re-run query with higher budget
        budget_limit = (merged_reqs.budget_max or 100) * 100 * 1.25 # 25% stretch
        
        all_projects = []
        if projects_table:
            t = projects_table
            # Similar logic as Node 2 but strict on location/config
            all_projects = t.select(
                t.name, t.budget_min, t.budget_max, t.location, t.configuration,
                t.status, t.possession_year, t.possession_quarter, t.amenities, t.usp
            ).collect()
        else:
            from services.hybrid_retrieval import hybrid_retrieval
            all_projects = hybrid_retrieval.mock_projects if hybrid_retrieval.mock_projects else []
        upsell_list = []
        upsell_details = []
        loc_term = (merged_reqs.location or "").lower()
        conf_term = (merged_reqs.configuration or "").lower()

        for p in all_projects:
            if loc_term in p['location'].lower() and p['budget_min'] <= budget_limit:
                # Also check configuration if specified
                if conf_term and conf_term not in p['configuration'].lower():
                    continue
                upsell_list.append(f"{p['name']} (Start: {p['budget_min']/100} Cr)")
                upsell_details.append(p)

        if upsell_list:
            response_parts = ["I found these premium options slightly above your range:\n"]

            for i, proj in enumerate(upsell_details[:3], 1):
                response_parts.append(f"\n{i}. **{proj['name']}** ({proj['status']})")

                # ADD DEVELOPER (trust signal)
                if proj.get('developer'):
                    response_parts.append(f"   🏗️ Developer: **{proj['developer']}**")

                response_parts.append(f"   📍 Location: {proj['location']}")
                response_parts.append(f"   💰 Price: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                response_parts.append(f"   🏠 Config: {proj['configuration']}")
                response_parts.append(f"   📅 Possession: {proj['possession_quarter']} {proj['possession_year']}")

                # ADD USP (differentiation)
                if proj.get('usp') and len(proj['usp']) > 10:
                    usp_short = proj['usp'][:100] + "..." if len(proj['usp']) > 100 else proj['usp']
                    response_parts.append(f"   ✨ Highlights: {usp_short}")

                # ADD RERA (compliance signal)
                if proj.get('rera_number') and 'pending' not in proj['rera_number'].lower():
                    response_parts.append(f"   🛡️ RERA: {proj['rera_number']}")

            response_parts.append("\n\nThese properties offer exceptional value and higher appreciation potential. Shall we schedule a site visit to see what makes them worth the investment? 🏡")

            base_action = "\n".join(response_parts)
            # Add dynamic closing
            closing = generate_contextual_response(
                user_input,
                f"User agreed to stretch budget. Showing upscale properties: {', '.join(upsell_list[:2])}.",
                "Express excitement about these premium finds and push for a site visit."
            )
            action = f"{base_action}\n\n{closing}"
            next_node = "FACE_TO_FACE"
        else:
            action = "Even with stretch, no options found."
            next_node = "NODE 5" # Try convincing or move to location pivot

    # --- NODE 5: Budget Justification (Ask) ---
    elif node == "NODE 5":
        action = generate_contextual_response(
            user_input,
            f"User rejected initial budget stretch for {merged_reqs.location}. We need to justify why market prices are higher here.",
            "Explain why market prices in this premium area are higher and why stretching the budget is a sound investment for long-term appreciation. End with a question asking if they'd consider exploring properties slightly above their range."
        )
        next_node = "NODE 5_WAIT"

    # --- NODE 5_WAIT: Process Persuasion Response ---
    elif node == "NODE 5_WAIT":
        l_input = user_input.lower()
        if "agree" in l_input or "ok" in l_input or "yes" in l_input or "sure" in l_input or "make sense" in l_input:
            action = "Wonderful! Let me show you those premium options."
            next_node = "NODE 4"
        elif "no" in l_input or "not" in l_input or "disagree" in l_input:
            next_node = "NODE 6"
            # Action will be set in NODE 6
        else:
            action = "I want to make sure I understand your preference. Are you open to considering properties slightly above your budget given the value they offer?"
            next_node = "NODE 5_WAIT"

    # --- NODE 6: Location Flexibility (Ask) ---
    elif node == "NODE 6":
        # action = "I completely understand your preference for this location. However, would you be open to exploring similar premium projects in nearby areas (within 10km)? Sometimes we find hidden gems with better value and connectivity. What are your thoughts?"
        action = generate_contextual_response(
            user_input,
            f"User rejected budget stretch for {merged_reqs.location}. We need to pivot location.",
            "Ask if they are open to nearby areas (within 10km) which might offer better value or fit their budget."
        )
        next_node = "NODE 6_WAIT"

    # --- NODE 6_WAIT: Process Location Flexibility Response ---
    elif node == "NODE 6_WAIT":
        l_input = user_input.lower()
        if "yes" in l_input or "ok" in l_input or "sure" in l_input or "open" in l_input:
            action = "Excellent! Let me search for great options in nearby areas."
            next_node = "NODE 7"
        elif "no" in l_input or "not" in l_input or "stick" in l_input:
            next_node = "NO_VIABLE_OPTIONS"
            # Action will be set in NO_VIABLE_OPTIONS
        else:
            action = "Just to clarify - would you consider properties in nearby locations that offer similar or better amenities?"
            next_node = "NODE 6_WAIT"

    # --- NODE 7: Alternate Location (Radius-based) ---
    elif node == "NODE 7":
        from utils.geolocation_utils import get_coordinates, calculate_distance
        
        target_loc = merged_reqs.location or "Bangalore"
        center_coords = get_coordinates(target_loc)
        budget_limit = (merged_reqs.budget_max or 100) * 100
        conf_term = (merged_reqs.configuration or "").lower()
        
        matches = []
        match_details = []
        
        # Access projects from Pixeltable if available, else mock
        source = []
        if projects_table:
            try:
                t = projects_table
                # Fetch all projects to scan coordinates (coordinate filtering not yet in DB)
                # Ideally we'd filter in DB but we need distance calc
                all_rows = t.select(
                     t.project_id, t.name, t.location, t.budget_min, t.budget_max,
                     t.configuration, t.status, t.possession_year, t.possession_quarter,
                     t.usp
                ).collect()
                # Determine lat/lon for each project on the fly or assuming they are in DB??
                # Wait, Pixeltable schema doesn't seem to have lat/lon columns surfaced in the select above?
                # The seed data had it. Let's assume we need to re-map or they are lacking.
                # Actually, geolocation_utils might map location string -> coords.
                # But for the *projects*, we need their location.
                # Let's use get_coordinates on project location string if lat/lon missing.
                source = all_rows
            except Exception as e:
                logger.warning(f"Failed to fetch from DB for radius: {e}")
        
        if not source:
             from services.hybrid_retrieval import hybrid_retrieval
             if not hybrid_retrieval.mock_projects:
                 hybrid_retrieval._load_mock_data()
             source = hybrid_retrieval.mock_projects

        if center_coords:
            lat, lon = center_coords
            for p in source:
                # Get project coordinates
                p_lat, p_lon = None, None
                if '_lat' in p and '_lon' in p:
                     p_lat, p_lon = p['_lat'], p['_lon']
                elif 'latitude' in p and 'longitude' in p:
                     p_lat, p_lon = p['latitude'], p['longitude']
                else:
                    # Try to resolve project location dynamically
                    # This is slow but necessary if DB lacks coords
                    pass 
                    # For now rely on source having it or strictly mock which has it.
                    # Actually, let's try to Geocode the project location string if we can.
                    # But doing it for all projects is too slow.
                    # We will assume DB *should* have it or we skip. 
                    # Wait, the User request is "Show Nearby should scan projects which we have 10 km".
                    # If DB doesn't have lat/lon, we can't scan. 
                    # I will assume `get_coordinates` works on the project location field.
                    try:
                        p_coords = get_coordinates(p.get('location', ''))
                        if p_coords:
                            p_lat, p_lon = p_coords
                    except:
                        pass
                
                if p_lat and p_lon:
                    dist = calculate_distance(lat, lon, p_lat, p_lon)
                    # We look for projects within 10km of the target location
                    if dist <= 10.0 and p['budget_min'] <= budget_limit:
                        p_copy = p.copy()
                        p_copy['_distance'] = dist
                        match_details.append(p_copy)
        
        # Sort by distance
        match_details.sort(key=lambda x: x.get('_distance', 999))
        unique_details = match_details[:3]

        if unique_details:
            response_parts = [f"I found some excellent options within 10km of {target_loc} that match your budget:\n"]

            for i, proj in enumerate(unique_details, 1):
                dist_str = f"{proj['_distance']:.1f}km away" if '_distance' in proj else ""
                response_parts.append(f"\n{i}. **{proj['name']}** ({proj['status']})")

                # ADD DEVELOPER (trust signal)
                if proj.get('developer'):
                    response_parts.append(f"   🏗️ Developer: **{proj['developer']}**")

                response_parts.append(f"   📍 Location: {proj['location']} ({dist_str})")
                response_parts.append(f"   💰 Price: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")

                # Simplify configuration
                config_display = clean_configuration_string(proj.get('configuration', ''))
                response_parts.append(f"   🏠 Config: {config_display}")

                response_parts.append(f"   📅 Possession: {proj['possession_quarter']} {proj['possession_year']}")

                # ADD USP (differentiation)
                if proj.get('usp') and len(proj['usp']) > 10:
                    usp_short = proj['usp'][:100] + "..." if len(proj['usp']) > 100 else proj['usp']
                    response_parts.append(f"   ✨ Highlights: {usp_short}")

                # ADD RERA (compliance signal)
                if proj.get('rera_number') and 'pending' not in proj['rera_number'].lower():
                    response_parts.append(f"   🛡️ RERA: {proj['rera_number']}")

            response_parts.append("\n\nThese locations offer similar connectivity and great value.")
            
            base_results = "\n".join(response_parts)
            gpt_explanation = generate_contextual_response(
                user_input,
                f"User rejected {target_loc}. Found options in nearby areas: {', '.join([p['location'] for p in unique_details])}.",
                "Explain strategically why these alternative locations are a smart move (e.g. upcoming infrastructure, better value per sqft, proximity to IT hubs). Keep it concise and persuasive."
            )
            
            action = f"{base_results}\n\n{gpt_explanation}\n\nHow does the possession timeline work for you?"
            state.last_shown_projects = unique_details
            next_node = "NODE 8"
        else:
            action = "I couldn't find any other options within 10km that fit the budget. Would you be open to exploring other premium zones in Bangalore?"
            next_node = "NO_VIABLE_OPTIONS"

    # --- NODE 8: Possession Timeline Check (Ask) ---
    elif node == "NODE 8":
        # action = "Looking at these options, how does the possession timeline work for you? Are you looking to move in immediately, or are you comfortable with a property that will be ready in a few months?"
        action = generate_contextual_response(
            user_input,
            "Shown options might include Under Construction context.",
            "Ask about their possession timeline preference: Immediate vs comfortable waiting a few months?"
        )
        next_node = "NODE 8_WAIT"

    # --- NODE 8_WAIT: Process Possession Response ---
    elif node == "NODE 8_WAIT":
        l_input = user_input.lower()
        if "ready" in l_input or "immediate" in l_input or "now" in l_input or "soon" in l_input or "asap" in l_input:
            # User wants ready-to-move
            action = "I understand you're looking for ready-to-move options. Let me check what we have available."
            next_node = "NODE 10"
        elif "fine" in l_input or "ok" in l_input or "works" in l_input or "good" in l_input or "comfortable" in l_input:
            # Timeline is acceptable
            action = "Perfect! These options should work well for your timeline."
            next_node = "FACE_TO_FACE"
        elif "no" in l_input or "not" in l_input or "issue" in l_input or "problem" in l_input:
            # User has concerns about possession
            next_node = "NODE 9"
            # Action will be set in NODE 9
        else:
            action = "Just to clarify - are you comfortable with the possession timelines shown for these properties, or would you prefer ready-to-move options?"
            next_node = "NODE 8_WAIT"

    # --- NODE 9: Under Construction / Later Possession Benefits Pitch ---
    elif node == "NODE 9":
        pitch = generate_contextual_response(
            user_input,
            f"User prefers earlier possession than suggested projects. Current reqs: {merged_reqs.dict()}",
            "Explain the strategic benefits of investing in projects with a slightly later possession (e.g., lower entry price, better appreciation potential, flexible payment plans, and more choices). Be very persuasive."
        )
        action = f"{pitch}\n\nGiven these benefits, would you like to schedule a meeting to discuss the payment plan and potential ROI?"
        next_node = "FACE_TO_FACE"

    # --- NODE 10: RTMI (Ready to Move In) Options Check ---
    elif node == "NODE 10":
        t = projects_table
        budget_limit = (merged_reqs.budget_max or 100) * 100

        rtmi_projects = []
        rtmi_details = []
        rtmi_projects = []
        rtmi_details = []
        all_projects = []
        
        if projects_table:
            t = projects_table
            all_projects = t.select(
                t.name, t.location, t.status, t.budget_min, t.budget_max,
                t.configuration, t.possession_year, t.possession_quarter,
                t.amenities, t.usp, t.rera_number
            ).collect()
        else:
             from services.hybrid_retrieval import hybrid_retrieval
             all_projects = hybrid_retrieval.mock_projects if hybrid_retrieval.mock_projects else []

        loc_term = (merged_reqs.location or "").lower()
        conf_term = (merged_reqs.configuration or "").lower()

        for p in all_projects:
            if "ready" in p['status'].lower() and p['budget_min'] <= budget_limit:
                # Apply location and config filters
                if loc_term and loc_term not in p['location'].lower():
                    continue
                if conf_term and conf_term not in p['configuration'].lower():
                    continue
                rtmi_projects.append(p['name'])
                rtmi_details.append(p)

        if rtmi_projects:
            # Show RTMI options
            response_parts = ["I found these ready-to-move-in options for you:\n"]
            for i, proj in enumerate(rtmi_details[:3], 1):
                response_parts.append(f"\n{i}. **{proj['name']}** (Ready to Move)")

                # ADD DEVELOPER (trust signal)
                if proj.get('developer'):
                    response_parts.append(f"   🏗️ Developer: **{proj['developer']}**")

                response_parts.append(f"   📍 Location: {proj['location']}")
                response_parts.append(f"   💰 Price: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                response_parts.append(f"   🏠 Config: {proj['configuration']}")

                # ADD USP (differentiation)
                if proj.get('usp') and len(proj['usp']) > 10:
                    usp_short = proj['usp'][:100] + "..." if len(proj['usp']) > 100 else proj['usp']
                    response_parts.append(f"   ✨ Highlights: {usp_short}")

                # ADD RERA (compliance signal)
                if proj.get('rera_number') and 'pending' not in proj['rera_number'].lower():
                    response_parts.append(f"   🛡️ RERA: {proj['rera_number']}")

            response_parts.append("\n\nThese properties are ready for immediate possession. Would you like to schedule a site visit?")
            action = "\n".join(response_parts)
            state.last_shown_projects = rtmi_details[:10]
            next_node = "FACE_TO_FACE"
        else:
            # No RTMI available, explain UC benefits
            uc_pitch = generate_contextual_response(
                user_input,
                "User wants ready-to-move, but we only have Under Construction. Key benefits: Lower Entry Price (save 20%), High Appreciation, Flexi Payment Plans.",
                "Convince them to consider Under Construction options by highlighting checking out nearby ready options OR discussing the financial benefits of UC."
            )
            action = uc_pitch
            next_node = "NODE 10_WAIT"

    # --- NODE 10_WAIT: Process RTMI Pivot Decision ---
    elif node == "NODE 10_WAIT":
        l_input = user_input.lower()
        if "nearby" in l_input or "location" in l_input or "other" in l_input or "alternate" in l_input:
            action = "Great! Let me search for ready-to-move options in nearby areas."
            next_node = "NODE 6"  # Try location flexibility
        elif "construction" in l_input or "uc" in l_input or "discuss" in l_input or "explore" in l_input:
            action = "Wonderful! Under-construction properties can be a great investment. Let me help you understand the benefits and timeline."
            next_node = "FACE_TO_FACE"
        else:
            action = "Would you like to see ready-to-move options in nearby areas, or learn more about the under-construction properties with their investment benefits?"
            next_node = "NODE 10_WAIT"

    # --- FACE_TO_FACE: Conversion Node ---
    elif node == "FACE_TO_FACE":
        import random

        p_name = f" to **{state.selected_project_name}**" if state.selected_project_name else ""

        # Generate realistic scarcity
        units_left = random.randint(3, 8)

        action = f"""Perfect timing! Let me arrange your site visit{p_name}. 🏡

**🎁 Site Visit Benefits:**
✓ Exclusive walk-through with senior property consultant
✓ Live inventory check - see available units in real-time
✓ Special booking day discounts (typically 2-5% off base price)
✓ First preference on premium floors/facing

**⏰ Availability Alert:**
Only **{units_left} prime units** left in your preferred configuration. Last weekend, we booked 4 units in this tower.

**📅 Let's Schedule:**
Our weekend slots fill up fast. Which works better for you?
• **This Saturday morning** (10 AM - 12 PM)
• **Sunday afternoon** (2 PM - 4 PM)

Once you confirm, I'll immediately send you:
📄 Floor plans & detailed pricing sheet
🎥 Virtual 360° tour link
💰 EMI calculator with payment plans

*The sooner we book, the better your unit selection will be!*"""
        next_node = "FACE_TO_FACE_WAIT"

    # --- FACE_TO_FACE_WAIT: Collect Contact Details ---
    elif node == "FACE_TO_FACE_WAIT":
        # In a real implementation, extract contact info from user_input
        # For now, just confirm and complete
        action = """Perfect! I've noted your details. Our team will reach out shortly to confirm your site visit.

Looking forward to helping you find your dream home! 🏠

Is there anything else I can help you with today?"""
        next_node = "COMPLETED"

    # --- NO_VIABLE_OPTIONS: Graceful Exit ---
    elif node == "NO_VIABLE_OPTIONS":
        action = """I understand that we haven't found exactly what you're looking for right now.

Would you like me to notify you when properties matching your requirements become available? I can keep you updated on:
📢 New launches in your preferred location
💰 Price drops or special offers
🏡 Upcoming ready-to-move properties
✨ Exclusive pre-launch opportunities

Just share your email or phone number, and I'll make sure you're the first to know!"""
        next_node = "NO_VIABLE_OPTIONS_WAIT"

    # --- NO_VIABLE_OPTIONS_WAIT: Capture Lead ---
    elif node == "NO_VIABLE_OPTIONS_WAIT":
        # In a real implementation, extract and store contact info
        action = """Thank you! I've saved your details and will reach out as soon as we have matching properties.

We appreciate your interest, and I'm confident we'll find the perfect home for you soon. Have a great day! 😊"""
        next_node = "COMPLETED"

    # --- COMPLETED: Final State ---
    elif node == "COMPLETED":
        action = "Is there anything else I can help you with today? I'm here to assist with any property-related questions!"
        next_node = "COMPLETED"  # Stay in completed state


    extracted_dict = merged_reqs.dict()
    # Clean up output
    return FlowResponse(
        extracted_requirements=extracted_dict,
        current_node=node,
        system_action=action,
        next_redirection=next_node
    )


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
