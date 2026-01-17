"""
GPT-First Intent Classification with Intelligent Data Source Routing.

This module replaces keyword-based classification with GPT-4 as the primary classifier.
GPT decides both the intent AND where to get the answer (database vs GPT generation).
"""

import json
import logging
from typing import Dict, List, Optional
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url
)


def classify_intent_gpt_first(
    query: str,
    conversation_history: Optional[List[Dict]] = None,
    session_state: Optional[Dict] = None,
    context_summary: Optional[str] = None
) -> Dict:
    """
    GPT-4 primary classifier with intelligent data source selection.

    Args:
        query: User's input query
        conversation_history: Last N conversation turns for context (optional)
        session_state: Current session state with selected_project, requirements, etc. (optional)
        context_summary: Formatted context summary from session manager (optional)

    Returns:
        {
          "intent": str,  # property_search, project_details, more_info_request, etc.
          "data_source": str,  # "database", "gpt_generation", "hybrid"
          "confidence": float,  # 0.0-1.0
          "reasoning": str,  # Why this classification
          "extraction": dict,  # Extracted entities (config, budget, location, project_name, topic, etc.)
        }
    """

    system_prompt = _build_system_prompt()

    # Build messages array
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history for context (last 10 turns now for better context)
    if conversation_history:
        messages.extend(conversation_history[-10:])

    # Build comprehensive context info
    context_info = ""
    
    # Use context summary if available (preferred)
    if context_summary:
        context_info = f"\n\n**Conversation Context:**\n{context_summary}"
    
    # Add detailed session state
    if session_state:
        if session_state.get("selected_project_name"):
            context_info += f"\n**Current Project:** {session_state['selected_project_name']}"
        
        # CRITICAL: Add last_shown_projects for context
        if session_state.get("last_shown_projects"):
            projects = session_state["last_shown_projects"]
            if projects:
                project_names = [p.get('name') if isinstance(p, dict) else str(p) for p in projects[:3]]
                context_info += f"\n**Last Shown Projects:** {', '.join(project_names)}"
                context_info += "\n**CRITICAL:** If user asks vague questions (e.g., 'price', 'location', 'amenities'), assume they're asking about the last shown project."
        
        # CRITICAL: Add interested_projects for context
        if session_state.get("interested_projects"):
            interested = session_state["interested_projects"]
            if interested:
                context_info += f"\n**Interested Projects:** {', '.join(interested[-3:])}"
                context_info += "\n**CRITICAL:** Use these projects for context when query is vague or doesn't mention a project."
        
        # CRITICAL: Add available projects list for GPT to match against
        if session_state.get("available_projects"):
            projects_list = [p.get('name') for p in session_state['available_projects'][:30]]  # First 30 for context
            context_info += f"\n**Available Projects (sample):** {', '.join(projects_list)}"
            context_info += f"\n**Total Available Projects:** {len(session_state['available_projects'])}"
            context_info += "\n**CRITICAL:** Match partial project names from query to this list. Use fuzzy matching. Examples: 'Green Vista' → 'Green Vista in Bellandur', 'citrine' → 'Brigade Citrine'."
        
        if session_state.get("requirements"):
            req = session_state["requirements"]
            req_parts = []
            if req.get('configuration'):
                req_parts.append(f"config={req['configuration']}")
            if req.get('location'):
                req_parts.append(f"location={req['location']}")
            if req.get('budget_max'):
                req_parts.append(f"budget={req['budget_max']} Cr")
            if req_parts:
                context_info += f"\n**User Requirements:** {', '.join(req_parts)}"
        
        # Add last intent and topic if available
        if session_state.get("last_intent"):
            context_info += f"\n**Last Intent:** {session_state['last_intent']}"
        if session_state.get("last_topic"):
            context_info += f"\n**Last Topic:** {session_state['last_topic']}"
        if session_state.get("conversation_phase"):
            context_info += f"\n**Phase:** {session_state['conversation_phase']}"

    # Add user query with context
    user_message = f"Classify this query: {query}"
    if context_info:
        user_message += context_info

    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(
            model=settings.effective_gpt_model,
            temperature=0.0,  # Deterministic classification
            messages=messages,
            max_tokens=300,
            response_format={"type": "json_object"}  # Force JSON output
        )

        result = json.loads(response.choices[0].message.content)

        # Validate and set defaults
        result.setdefault("intent", "unsupported")
        result.setdefault("data_source", "database")
        result.setdefault("confidence", 0.5)
        result.setdefault("reasoning", "No reasoning provided")
        result.setdefault("extraction", {})

        logger.info(f"GPT Classification: intent={result['intent']}, data_source={result['data_source']}, confidence={result['confidence']}")

        return result

    except Exception as e:
        logger.error(f"GPT classification failed: {e}")
        # Return safe default
        return {
            "intent": "unsupported",
            "data_source": "database",
            "confidence": 0.0,
            "reasoning": f"Classification error: {str(e)}",
            "extraction": {}
        }


def _build_system_prompt() -> str:
    """Build the system prompt for GPT intent classification."""

    return """You are an intent classifier for a real estate chatbot. Analyze the user's query and return a JSON object.

**CRITICAL: GPT-FIRST UNDERSTANDING (Like ChatGPT - Never Lose Context)**

You have access to:
1. **Available Projects List**: All projects in database (from session_state.available_projects)
2. **Session Context**: Last shown projects, interested projects, conversation history
3. **Natural Language Understanding**: You can understand incomplete questions, partial names, vague queries

**YOUR JOB:**
- Match ANY query to projects in database, even if:
  * Project name is partial ("Green Vista" → match to "Green Vista in Bellandur")
  * Query is vague ("price" → use last_shown_projects to find project)
  * Question is incomplete ("lets pitch" → extract project name from context)
  * Query doesn't mention project explicitly (use session context)

**PROJECT NAME MATCHING:**
- If query mentions ANY part of a project name, match it to available_projects
- Examples:
  * "Green Vista" → match to "Green Vista in Bellandur" or "Green Vista Phase 2"
  * "lets pitch citrine" → match to "Brigade Citrine"
  * "avalon price" → match to "Brigade Avalon"
- Use fuzzy matching: "green" could match "Green Vista", "Green Park", etc.
- If multiple matches, prefer the one in session_state.last_shown_projects or interested_projects

**SESSION CONTEXT USAGE (NEVER LOSE CONTEXT):**
- If query is vague (e.g., "price", "location", "amenities") and doesn't mention project:
  1. Check session_state.last_shown_projects[0] for last shown project
  2. Check session_state.interested_projects[-1] for last mentioned project
  3. Extract project_name from session context
- Examples:
  * Query: "price" + last_shown_projects=[{"name": "Green Vista"}]
    → Extract: {"project_name": "Green Vista", "fact_type": "price"}
  * Query: "more details" + interested_projects=["Brigade Citrine"]
    → Extract: {"project_name": "Brigade Citrine"}

**SMART DATA ROUTING:**

**PATH 1: DATABASE** (If project available in DB → Get from database)
- property_search: "show me 2BHK", "find flats in Whitefield"
- project_facts: ANY query about a project that exists in database
  * "lets pitch X", "tell me about X", "price", "location", "amenities", "details of X"
  * If project_name is extracted (from query or session), classify as project_facts
  * Database contains: name, developer, location, price, RERA, configuration, possession date, status, amenities, highlights, usp
- data_source: "database"

**PATH 2: GPT SALES CONSULTANT** (If NOT projects → Get directly from GPT)
- Questions about things NOT in database:
  * Distance/Location: "how far is airport from X", "distance to office", "nearby schools"
  * Advice: "investment potential", "why buy in Whitefield", "pros and cons"
- Generic questions: "How to stretch budget?", "What is EMI?", "loan eligibility"
- Follow-ups: "more", "tell me more", "continue", "give more points"
- Objections: "too expensive", "location too far"
- Greetings: "hi", "hello"
- data_source: "gpt_generation"

**INTENT CLASSIFICATION:**

1. **PROPERTY_SEARCH** (→ database):
   - User wants to find/search properties
   - Has filters: BHK, location, budget
   - data_source: "database"

2. **PROJECT_FACTS** (→ database):
   - User asks about a SPECIFIC PROJECT (matched from available_projects or session context)
   - ANY query about a project: "lets pitch X", "tell me about X", "price", "location", "amenities"
   - If project_name is extracted (from query or session), classify as project_facts
   - data_source: "database"

3. **SALES_CONVERSATION** (→ GPT):
   - Generic advice, objections, FAQs
   - Questions NOT about specific projects
   - data_source: "gpt_generation"

**Entity Extraction:**
- configuration: "2BHK", "3BHK", "4BHK"
- budget_max: In lakhs (2 Cr = 200 lakhs)
- location: "Whitefield", "Sarjapur", "East Bangalore"
- project_name: Extract from query OR session context (last_shown_projects, interested_projects)
- fact_type: "price", "location", "amenities", "general" (for project_facts)
- topic: For sales_conversation (budget_stretch, emi, investment, amenities, location_benefits)

**Return JSON:**
```json
{
  "intent": "property_search|project_facts|sales_conversation",
  "data_source": "database|gpt_generation",
  "confidence": 0.95,
  "reasoning": "Brief explanation of classification decision",
  "extraction": {
    "configuration": "2BHK",
    "budget_max": 200,
    "location": "Whitefield",
    "project_name": "Brigade Citrine",
    "topic": "amenities"
  }
}
```

**EXAMPLES:**

Query: "lets pitch Green Vista"
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "User wants to pitch Green Vista - match to available project",
  "extraction": {"project_name": "Green Vista in Bellandur"}
}
```

Query: "price" (with last_shown_projects=[{"name": "Green Vista"}])
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.98,
  "reasoning": "Vague query about price - use last_shown_projects context",
  "extraction": {"project_name": "Green Vista", "fact_type": "price"}
}
```

Query: "tell me more" (with interested_projects=["Brigade Citrine"])
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.90,
  "reasoning": "Follow-up query - use interested_projects context",
  "extraction": {"project_name": "Brigade Citrine"}
}
```

Query: "Show me 2BHK in Whitefield under 2 Cr"
```json
{
  "intent": "property_search",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Explicit search with filters",
  "extraction": {"configuration": "2BHK", "location": "Whitefield", "budget_max": 200}
}
```

Query: "What is the price of Brigade Citrine?"
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.98,
  "reasoning": "Price is a database fact",
  "extraction": {"project_name": "Brigade Citrine", "fact_type": "price"}
}
```

Query: "Tell me about Brigade Citrine"
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Broad project detail query - fetch from database",
  "extraction": {"project_name": "Brigade Citrine"}
}
```

Query: "Amenities in Brigade Citrine"
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.93,
  "reasoning": "Amenities field exists in database",
  "extraction": {"project_name": "Brigade Citrine", "fact_type": "amenities"}
}
```

Query: "How far is airport from Avalon?"
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.92,
  "reasoning": "Distance calculation not in database",
  "extraction": {"project_name": "Brigade Avalon", "topic": "location_benefits"}
}
```

Query: "How to stretch my budget?"
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.95,
  "reasoning": "Generic advice - not database query",
  "extraction": {"topic": "budget_stretch"}
}
```

Query: "Too expensive for me"
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.92,
  "reasoning": "Budget objection - needs GPT sales response",
  "extraction": {"topic": "budget_objection"}
}
```

Now classify the user's query following these rules. Use GPT understanding to match partial project names, use session context for vague queries, and never lose context. Return ONLY valid JSON, no other text.
"""
