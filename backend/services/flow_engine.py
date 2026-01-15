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
            model=settings.llm_model,
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
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": "You are a sales coach. Generate persuasive talking points (no fake data) for the agent."},
                {"role": "user", "content": f"Topic: {topic}\nContext: {context}"}
            ]
        )
        return response.choices[0].message.content
    except Exception:
        return "Could not generate persuasion text."

# --- NODE LOGIC ---
def execute_flow(state: FlowState, user_input: str) -> FlowResponse:
    # 1. Update Requirements (Merge new input with existing state)
    new_reqs = extract_requirements_llm(user_input)
    # Simple merge logic (new overrides old if present)
    merged_reqs = state.requirements.copy(update={k: v for k, v in new_reqs.dict().items() if v is not None})
    state.requirements = merged_reqs

    # 2. Determine Node Logic
    node = state.current_node
    action = ""
    next_node = node

    projects_table = get_projects_table()
    
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
        # Query Pixeltable
        t = projects_table

        # Build Query logic (same as before)
        budget_limit = (merged_reqs.budget_max or 100) * 100

        matches = []
        match_details = []
        upsell_matches = []

        all_projects = t.select(
            t.project_id, t.name, t.location, t.budget_min, t.budget_max,
            t.configuration, t.status, t.possession_year, t.possession_quarter,
            t.rera_number, t.amenities, t.usp, t.description
        ).collect()

        loc_term = (merged_reqs.location or "").lower()
        conf_term = (merged_reqs.configuration or "").lower()

        for p in all_projects:
            # Filter Location
            p_loc = p['location'].lower()
            if loc_term and loc_term not in p_loc: continue
            # Filter Config
            p_conf = p['configuration'].lower()
            if conf_term and conf_term not in p_conf: continue
            # Filter Poss Type
            if merged_reqs.possession_type == "RTMI" and "ready" not in p['status'].lower(): continue

            if p['budget_min'] <= budget_limit:
                matches.append(f"{p['name']} ({p['status']})")
                match_details.append(p)
            elif p['budget_min'] <= budget_limit * 1.2:
                upsell_matches.append(f"{p['name']} ({p['budget_min']/100} Cr)")

        if matches:
            # Build detailed response with property information
            response_parts = ["I found these excellent matches:\n"]

            for i, proj in enumerate(match_details[:3], 1):  # Show top 3 in detail
                response_parts.append(f"\n{i}. **{proj['name']}** ({proj['status']})")
                response_parts.append(f"   📍 Location: {proj['location']}")
                response_parts.append(f"   💰 Price Range: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                response_parts.append(f"   🏠 Configuration: {proj['configuration']}")
                response_parts.append(f"   📅 Possession: {proj['possession_quarter']} {proj['possession_year']}")

                if proj.get('usp'):
                    response_parts.append(f"   ✨ USP: {proj['usp']}")

                # Parse and show key amenities (first 3-4)
                if proj.get('amenities'):
                    amenities = proj['amenities'].replace("['", "").replace("']", "").replace("'", "")
                    amenities_list = amenities.split(", ")[:4]
                    response_parts.append(f"   🎯 Amenities: {', '.join(amenities_list)}")

                if proj.get('rera_number'):
                    response_parts.append(f"   📋 RERA: {proj['rera_number']}")

            # If more than 3 matches, mention them
            if len(matches) > 3:
                response_parts.append(f"\n\nPlus {len(matches) - 3} more options available!")

            response_parts.append("\n\nWould you like to schedule a site visit to see these properties? 🏡")

            action = "\n".join(response_parts)
            state.last_system_action = f"shown_matches:{len(matches)}"
            next_node = "NODE 2A"
        else:
            action = "No exact matches found."
            if upsell_matches:
                 action += f" Upsell candidates exist: {', '.join(upsell_matches[:3])}."
            next_node = "NODE 3"

    # --- NODE 2A: Exact Match Output / Objection Handler ---
    elif node == "NODE 2A":
        # Analyze User Input for Objections
        prompt = f"Analyze response to project options: '{user_input}'. Return: 'budget_objection', 'possession_objection', 'acceptance', or 'other'."
        # Simplified keyword check for prototype speed (LLM would be better)
        l_input = user_input.lower()
        
        if "expensive" in l_input or "budget" in l_input or "cost" in l_input or "high" in l_input:
            action = "Budget objection detected. Proceeding to Budget Check."
            next_node = "NODE 3"
        elif "date" in l_input or "time" in l_input or "ready" in l_input or "move" in l_input or "late" in l_input:
            action = "Possession objection detected. Proceeding to Classification."
            next_node = "NODE 8"
        elif "book" in l_input or "visit" in l_input or "good" in l_input or "interest" in l_input:
             action = "Interest detected. Pushing for Face-to-Face meeting."
             next_node = "Face-to-Face Push"
        else:
             # Default assumption: If ambiguous, maybe ask again or assume Budget? 
             # Flowchart says "If objection raised". If no objection, maybe they are thinking.
             action = "No clear objection. Ask: 'Shall we schedule a site visit to see these?'"
             next_node = "Face-to-Face Push" # Aggressive push as per "End every successful path in F2F"

    # --- NODE 3: Budget Flexibility ---
    elif node == "NODE 3":
        action = "Would you be comfortable stretching your budget by 10-20%? It could open up significantly better options with higher appreciation potential."
        # Logic to detect Yes/No from user_input would happen in next turn
        if "yes" in user_input.lower() or "ok" in user_input.lower():
            next_node = "NODE 4"
        elif "no" in user_input.lower():
            next_node = "NODE 5"
        else:
            next_node = "NODE 3"

    # --- NODE 4: Above Budget Inventory ---
    elif node == "NODE 4":
        # Fetch the upsell items we found earlier or re-query
        # For simplicity, re-run query with higher budget
        t = projects_table
        budget_limit = (merged_reqs.budget_max or 100) * 100 * 1.25 # 25% stretch

        # Similar logic as Node 2 but strict on location/config
        all_projects = t.select(
            t.name, t.budget_min, t.budget_max, t.location, t.configuration,
            t.status, t.possession_year, t.possession_quarter, t.amenities, t.usp
        ).collect()
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

            action = "\n".join(response_parts)
            state.current_node = "END"
            next_node = "Face-to-Face Push"
        else:
            action = "Even with stretch, no options found."
            next_node = "NODE 5" # Try convincing or move to location pivot

    # --- NODE 5: Budget Justification ---
    elif node == "NODE 5":
        persuasion = generate_persuasion_text("Budget Stretch", f"Client wants {merged_reqs.location} under {merged_reqs.budget_max}Cr. Market price is usually higher per sqft in this premium area.")
        action = f"{persuasion}\n\nDoes that sound reasonable to you?"
        if "agree" in user_input.lower() or "ok" in user_input.lower():
            next_node = "NODE 4"
        elif "no" in user_input.lower():
            next_node = "NODE 6"
        else: 
            next_node = "NODE 5"

    # --- NODE 6: Location Flexibility ---
    elif node == "NODE 6":
        action = "Would you be open to exploring similar premium projects in nearby locations (within a 10km radius)?"
        if "yes" in user_input.lower():
            next_node = "NODE 7"
        elif "no" in user_input.lower():
            action = "End Process: No Viable Options."
            next_node = "No Viable Options"
        else:
            next_node = "NODE 6"

    # --- NODE 7: Alternate Location ---
    elif node == "NODE 7":
        t = projects_table
        budget_limit = (merged_reqs.budget_max or 100) * 100
        matches = []
        match_details = []

        loc_term = (merged_reqs.location or "").lower()
        conf_term = (merged_reqs.configuration or "").lower()

        # Get all projects to find zone context (small dataset)
        all_projects = t.select(
            t.name, t.location, t.zone, t.budget_min, t.budget_max,
            t.configuration, t.status, t.possession_year, t.possession_quarter,
            t.amenities, t.usp
        ).collect()

        target_zone = None
        for p in all_projects:
            if loc_term in p['location'].lower():
                target_zone = p['zone']
                break

        if not target_zone:
             # Fallback: Assume the input IS the zone (e.g. "East Bangalore") or just search all
             target_zone = "" # Search all

        # Search for projects in the target zone (or all) that meet budget
        for p in all_projects:
             if p['budget_min'] <= budget_limit:
                 # If we have a target zone, enforce it.
                 if target_zone and (target_zone.lower() not in (p['zone'] or "").lower()):
                     continue

                 # Check configuration if specified
                 if conf_term and conf_term not in p['configuration'].lower():
                     continue

                 # Don't show the same location user rejected (if they did)?
                 # Flowchart says "Alternate micro-locations".
                 # If original query was "Whitefield", and p['location'] is "Whitefield", maybe skip?
                 # For now, just show best options in zone.
                 matches.append(f"{p['name']} ({p['location']})")
                 match_details.append(p)

        # Remove duplicates and limit
        unique_matches = []
        unique_details = []
        seen = set()
        for i, m in enumerate(matches):
            if m not in seen:
                seen.add(m)
                unique_matches.append(m)
                unique_details.append(match_details[i])

        unique_matches = unique_matches[:3]
        unique_details = unique_details[:3]

        if unique_matches:
            response_parts = [f"I found excellent alternate options in {target_zone or 'nearby areas'}:\n"]

            for i, proj in enumerate(unique_details, 1):
                response_parts.append(f"\n{i}. **{proj['name']}** ({proj['status']})")
                response_parts.append(f"   📍 Location: {proj['location']}")
                response_parts.append(f"   💰 Price Range: ₹{proj['budget_min']/100:.2f} - ₹{proj['budget_max']/100:.2f} Cr")
                response_parts.append(f"   🏠 Configuration: {proj['configuration']}")
                response_parts.append(f"   📅 Possession: {proj['possession_quarter']} {proj['possession_year']}")

                if proj.get('usp'):
                    response_parts.append(f"   ✨ USP: {proj['usp']}")

            response_parts.append("\n\nThese locations offer similar connectivity and amenities. Does the possession timeline work for you?")

            action = "\n".join(response_parts)
            next_node = "NODE 8"
        else:
            action = "No alternate options found even in wider zone."
            next_node = "No Viable Options"

    # --- NODE 8: Possession Check ---
    elif node == "NODE 8":
        action = "Does the possession timeline work for you?"
        if "yes" in user_input.lower():
            # Classify objection: Needs earlier or later?
            action = "Is client asking for Earlier (Ready to move) or Later?"
            # Heuristic: If user says "want ready to move", go to Node 9/10
            if "ready" in user_input.lower() or "earlier" in user_input.lower():
                next_node = "NODE 9" # Explain Under Construction benefits
            else:
                next_node = "NODE 10" # Default/Other
        elif "no" in user_input.lower():
             next_node = "Face-to-Face Push"
        else:
             next_node = "NODE 8"

    # --- NODE 9: Under Construction Pitch ---
    elif node == "NODE 9":
        pitch = generate_persuasion_text("Invest in Under Construction", "Client wants Ready to Move, but we only have Under Construction. Explain Lower Entry Price, High Appreciation, Linked Payment Plan.")
        action = f"{pitch}\n\nGiven these benefits, shall we schedule a meeting to discuss the payment plan?"
        next_node = "Face-to-Face Push"

    # ... Defaults ...


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
