import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
import openai
from config import settings
from database.pixeltable_setup import get_projects_table
import pixeltable as pxt

logger = logging.getLogger(__name__)

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

# --- NODE LOGIC ---
def execute_flow(state: FlowState, user_input: str) -> FlowResponse:
    # ... (Lines 172-309 remain unchanged, assuming minimal edits to previous nodes unless they were static)
    # Actually, I should only replace the specific blocks requested.
    # But since I'm using replace_file_content for a large chunk, I'll validly reproduce the unchanged parts or use multiple chunks.
    # The user asked for Nodes 3, 4, 7, 8, 10.
    # I will use MULTI_REPLACE to target specific nodes.
    # Wait, I cannot use multi_replace. I must use replace_file_content for single block ?? 
    # The instruction says: "Use replace_file_content tool ONLY when you are making a SINGLE CONTIGUOUS block of edits".
    # "To edit multiple, non-adjacent lines... make a single call to multi_replace_file_content".
    # I should use multi_replace_file_content.
    pass 
    # I will act as if I am writing the code for multi_replace in the tool call below.
    return None # Placeholder for thought


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

    # --- PROJECT SELECTION INTERCEPTOR ---
    if intent == "project_selection" or any(w in user_lower for w in ["tell me", "details about", "pitch me", "select"]):
        # Try to find which project the user is referring to
        target_project = None
        
        # 1. Exact or partial name match
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

        if target_project:
            state.selected_project_id = target_project.get('project_id')
            state.selected_project_name = target_project.get('name')
            state.cached_project_details = target_project
            action = f"Excellent choice! Let me give you a detailed deep-dive into **{state.selected_project_name}**."
            next_node = "NODE 2B"
            return FlowResponse(
                extracted_requirements=merged_reqs.dict(),
                current_node=node,
                system_action=action,
                next_redirection="NODE 2B"
            )

    # --- NODE 1: Normalization Gate ---
    if node == "NODE 1":
        if not (merged_reqs.configuration and merged_reqs.location and merged_reqs.budget_max):
            action = f"I'd love to help! To find the best options, could you please share your preferred Configuration (e.g., 2BHK), Location, and Max Budget?"
            next_node = "NODE 1"
        else:
            next_node = "NODE 2"
            # Auto-proceed to execution of Node 2 logic immediately if we have data? 
            # For this step, we'll return and let the next loop handle Node 2 to show distinct steps, 
            # OR we can just fall through. Let's fall through for efficiency.
            node = "NODE 2"

    # --- NODE 2: Exact Match Query ---
    if node == "NODE 2":
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
        
        matches = []
        match_details = []
        upsell_matches = []
        
        # Convert budget to integer (scale of 100 per Cr)
        budget_limit = float(merged_reqs.budget_max) * 100 if merged_reqs.budget_max else float('inf')

        for p in all_projects:
            # Filter Location
            p_loc = p['location'].lower()
            if loc_term and loc_term not in p_loc: continue
            # Filter Config (Normalize: remove spaces and dots)
            p_conf_norm = p['configuration'].lower().replace(" ", "").replace(".", "")
            conf_term_norm = conf_term.replace(" ", "").replace(".", "")
            if conf_term and conf_term_norm not in p_conf_norm: continue
            # Filter Poss Type
            if merged_reqs.possession_type == "RTMI" and "ready" not in p['status'].lower(): continue

            if p['budget_min'] <= budget_limit:
                matches.append(f"{p['name']} ({p['status']})")
                match_details.append(p)
            elif p['budget_min'] <= budget_limit * 1.2:
                upsell_matches.append(f"{p['name']} ({p['budget_min']/100} Cr)")

        if matches:
            # Build detailed response with property information using proper markdown
            response_parts = ["I found these excellent matches:\n\n"]

            for i, proj in enumerate(match_details[:3], 1):  # Show top 3 in detail
                response_parts.append(f"**{i}. {proj['name']}** ({proj['status']})\n")
                response_parts.append(f"- 📍 Location: {proj['location']}\n")
                response_parts.append(f"- 💰 Price Range: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr\n")
                response_parts.append(f"- 🏠 Configuration: {proj['configuration']}\n")
                response_parts.append(f"- 📅 Possession: {proj['possession_quarter']} {proj['possession_year']}\n")

                if proj.get('amenities'):
                    amenities = proj['amenities'].replace("[", "").replace("]", "").replace("'", "")
                    response_parts.append(f"- 🎯 Amenities: {amenities[:100]}...\n")

                if proj.get('rera_number'):
                    response_parts.append(f"- 📋 RERA: {proj['rera_number']}\n")
                
                response_parts.append("\n")  # Extra line between projects

            # If more than 3 matches, mention them
            if len(matches) > 3:
                response_parts.append(f"*Plus {len(matches) - 3} more options available!*\n\n")

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

    # --- NODE 2B_WAIT: Post-Pitch Handler ---
    elif node == "NODE 2B_WAIT":
        l_input = user_input.lower()
        if any(w in l_input for w in ["yes", "visit", "schedule", "ok", "sure", "book"]):
            action = f"That's great! I'm confident you'll find **{state.selected_project_name}** even more impressive in person. Let's schedule your site visit."
            next_node = "FACE_TO_FACE"
        else:
            action = generate_contextual_response(
                user_input,
                f"User has just seen a detailed pitch for {state.selected_project_name}.",
                "Answer any follow-up questions about the project or gently nudge again for a site visit."
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
                response_parts.append(f"   📍 Location: {proj['location']}")
                response_parts.append(f"   💰 Price Range: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                response_parts.append(f"   🏠 Configuration: {proj['configuration']}")
                response_parts.append(f"   📅 Possession: {proj['possession_quarter']} {proj['possession_year']}")

                if proj.get('usp'):
                    response_parts.append(f"   ✨ USP: {proj['usp']}")

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
        
        # Access mock_projects directly since flow_engine is sync
        from services.hybrid_retrieval import hybrid_retrieval
        if not hybrid_retrieval.mock_projects:
            hybrid_retrieval._load_mock_data()
            
        source = hybrid_retrieval.mock_projects
        
        if center_coords:
            lat, lon = center_coords
            for p in source:
                if '_lat' in p and '_lon' in p:
                    dist = calculate_distance(lat, lon, p['_lat'], p['_lon'])
                    # We look for projects within 10km of the target location
                    if dist <= 10.0 and p['budget_min'] <= budget_limit:
                        # Optional: skip if it's the exact same location user rejected? 
                        # Actually, usually they reject the budget/price, not the loc.
                        # But if they specifically wanted "Koramangala" and we show "Koramangala", 
                        # it means we found something that fits the budget now?
                        # Let's just find everything within 10km that fits.
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
                response_parts.append(f"   📍 Location: {proj['location']} ({dist_str})")
                response_parts.append(f"   💰 Price Range: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                response_parts.append(f"   🏠 Configuration: {proj['configuration']}")
                response_parts.append(f"   📅 Possession: {proj['possession_quarter']} {proj['possession_year']}")

                if proj.get('usp'):
                    response_parts.append(f"   ✨ USP: {proj['usp']}")

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
            next_node = "No Viable Options"

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
                response_parts.append(f"   📍 Location: {proj['location']}")
                response_parts.append(f"   💰 Price Range: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                response_parts.append(f"   🏠 Configuration: {proj['configuration']}")

                if proj.get('usp'):
                    response_parts.append(f"   ✨ USP: {proj['usp']}")

                if proj.get('rera_number'):
                    response_parts.append(f"   📋 RERA: {proj['rera_number']}")

            response_parts.append("\n\nThese properties are ready for immediate possession. Would you like to schedule a site visit?")
            action = "\n".join(response_parts)
            state.last_shown_projects = upsell_details[:10]
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
        p_name = f" for **{state.selected_project_name}**" if state.selected_project_name else ""
        action = f"""Wonderful! I'd love to arrange a site visit{p_name} for you. 🏡

Seeing the property in person will help you:
✓ Experience the actual space and layout
✓ Explore the amenities firsthand
✓ Meet our property consultants
✓ Get answers to all your questions
✓ Understand the neighborhood and connectivity

What date and time would work best for you? Please share:
• Your preferred date
• Your contact number
• Any specific requirements

I'll coordinate everything and confirm your visit!"""
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
