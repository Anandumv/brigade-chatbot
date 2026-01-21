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
from services.sales_agent_prompt import SALES_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Initialize OpenAI client with timeout
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    timeout=30.0  # 30 second timeout for API calls
)


def classify_intent_gpt_first(
    query: str,
    conversation_history: Optional[List[Dict]] = None,
    session_state: Optional[Dict] = None,
    context_summary: Optional[str] = None,
    comprehensive_context: Optional[Dict] = None
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
    
    # Use comprehensive context if available (preferred - most complete)
    if comprehensive_context:
        ctx = comprehensive_context
        context_info += "\n\n**COMPREHENSIVE CONTEXT:**\n"
        
        # Session state
        if ctx.get("session"):
            sess = ctx["session"]
            if sess.get("last_intent"):
                context_info += f"- Last Intent: {sess['last_intent']}\n"
            if sess.get("last_topic"):
                context_info += f"- Last Topic: {sess['last_topic']}\n"
            if sess.get("conversation_phase"):
                context_info += f"- Conversation Phase: {sess['conversation_phase']}\n"
        
        # Projects
        if ctx.get("projects"):
            proj = ctx["projects"]
            if proj.get("last_shown"):
                names = [p.get("name") for p in proj["last_shown"][:3]]
                context_info += f"- Last Shown Projects: {', '.join(names)}\n"
                context_info += "**CRITICAL:** Vague queries (e.g., 'price', 'location') refer to last shown project.\n"
            if proj.get("selected"):
                context_info += f"- Selected Project: {proj['selected']}\n"
                context_info += "**CRITICAL:** All queries refer to this project unless user switches.\n"
            if proj.get("interested"):
                context_info += f"- Interested Projects: {', '.join(proj['interested'])}\n"
        
        # Requirements
        if ctx.get("requirements"):
            req = ctx["requirements"]
            req_parts = []
            if req.get("location"):
                req_parts.append(f"location={req['location']}")
            if req.get("budget_max"):
                req_parts.append(f"budget<={req['budget_max']}")
            if req.get("configuration"):
                req_parts.append(f"config={req['configuration']}")
            if req_parts:
                context_info += f"- User Requirements: {', '.join(req_parts)}\n"
        
        # Conversation history insights
        if ctx.get("conversation"):
            conv = ctx["conversation"]
            if conv.get("mentioned_locations"):
                context_info += f"- Locations Discussed: {', '.join(conv['mentioned_locations'][:3])}\n"
            if conv.get("mentioned_budgets"):
                context_info += f"- Budgets Mentioned: {', '.join(conv['mentioned_budgets'][:3])}\n"
        
        # Intent hints
        if ctx.get("inferred_intent_hints"):
            hints = ctx["inferred_intent_hints"]
            context_info += f"- Intent Hints: {', '.join(hints)}\n"
    
    # Use context summary if available (fallback)
    elif context_summary:
        context_info = f"\n\n**Conversation Context:**\n{context_summary}"
    
    # Add detailed session state (fallback if comprehensive context not available)
    elif session_state:
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
            projects_list = [p.get('name') if isinstance(p, dict) else str(p) for p in session_state['available_projects'][:50]]  # First 50 for better matching
            projects_list = [p for p in projects_list if p]  # Filter out None/empty
            if projects_list:
                context_info += f"\n**Available Projects (sample):** {', '.join(projects_list[:30])}"  # Show first 30 in context
                context_info += f"\n**Total Available Projects:** {len(session_state['available_projects'])}"
                context_info += "\n**PROJECT NAME EXTRACTION RULES - READ CAREFULLY:**"
                context_info += "\n- Extract project_name ONLY if the project is EXPLICITLY mentioned by name in the query"
                context_info += "\n- DO NOT extract project_name if query only mentions a location/area that happens to match a project's location"
                context_info += "\n- Examples of CORRECT extraction:"
                context_info += "\n  * 'tell me about Brigade Citrine' → Extract 'Brigade Citrine' ✓"
                context_info += "\n  * 'avalon price' → Extract 'Brigade Avalon' (partial name match) ✓"
                context_info += "\n  * 'brigade avlon rera' → Extract 'Brigade Avalon' (typo handling) ✓"
                context_info += "\n- Examples of INCORRECT extraction (area searches, NOT project-specific):"
                context_info += "\n  * 'show me projects in Sarjapur' → NO project_name extraction ✗ (area search)"
                context_info += "\n  * 'find flats in Whitefield' → NO project_name extraction ✗ (area search)"
                context_info += "\n  * 'what are good projects in ORR' → NO project_name extraction ✗ (area search)"
                context_info += "\n- FACT TYPE TYPOS: 'prise' → 'price', 'ammenities' → 'amenities', 'rera numbr' → 'rera_number'"
                context_info += "\n- Use EXACT project name from the list above (e.g., 'Brigade Avalon', not 'avalon' or 'Avalon')"
            else:
                logger.warning("available_projects list is empty or has no names")
        
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
            max_tokens=500,  # Increased to ensure full extraction is returned
            response_format={"type": "json_object"}  # Force JSON output
        )

        result = json.loads(response.choices[0].message.content)

        # Validate and set defaults
        result.setdefault("intent", "unsupported")
        result.setdefault("data_source", "database")
        result.setdefault("confidence", 0.5)
        result.setdefault("reasoning", "No reasoning provided")
        result.setdefault("extraction", {})

        # Enhanced logging to debug extraction issues
        extraction = result.get("extraction", {})
        project_name = extraction.get("project_name")
        logger.info(f"GPT Classification: intent={result['intent']}, data_source={result['data_source']}, confidence={result['confidence']}")
        logger.info(f"GPT Extraction: {extraction}")
        if not project_name and result['intent'] == 'project_facts':
            logger.warning(f"⚠️ GPT classified as project_facts but extraction.project_name is missing! Query: '{query[:100]}'")
            logger.warning(f"   Full extraction: {extraction}")
            logger.warning(f"   Reasoning: {result.get('reasoning', 'N/A')}")

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
    """Build the system prompt for GPT intent classification using production Sales Agent GPT principles."""

    return SALES_AGENT_SYSTEM_PROMPT + """

⸻

TASK: DATA EXTRACTION & INTENT CLASSIFICATION (INTERNAL PROCESS)

⚠️ OVERRIDE: IGNORE "LIVE CALL OUTPUT RULES".
⚠️ OVERRIDE: DO NOT OUTPUT BULLET POINTS.
⚠️ OVERRIDE: OUTPUT MUST BE VALID JSON ONLY.

You are acting as the internal neural decision engine. Your job is to parse the user's natural language into structured constraints for the system.

""" + """
You are analyzing queries during live sales calls to classify intent and route to appropriate data source.

**CRITICAL: GPT-FIRST UNDERSTANDING (Like ChatGPT - Never Lose Context)**

You have access to:
1. **Available Projects List**: All projects in database (from session_state.available_projects)
2. **Session Context**: Last shown projects, interested projects, conversation history
3. **Natural Language Understanding**: You can understand incomplete questions, partial names, vague queries

**UNIVERSAL QUERY UNDERSTANDING (CRITICAL)**

You must understand ANY query format, regardless of how it's written:
- **Typos**: "distnce", "form" (instead of "from"), "avalon" (instead of "Avalon"), "brigade avalon" (missing capitalization)
- **Incomplete queries**: "price", "more", "details", "nearby", "what else"
- **Vague references**: "it", "these", "those", "that one", "the first one", "this project"
- **Single words**: "yes", "no", "more", "ok", "sure", "thanks"
- **Mixed languages (Hindi-English/Hinglish)**: "2 bhk chahiye", "avalon ka price", "citrine ki location", "kitna price hai", "kahan pe hai"
- **Slang/abbreviations**: "2bhk", "3bhk", "rtm", "rera", "emi", "orr"
- **No question marks**: "show me 2bhk", "avalon price", "tell me about citrine"
- **Multiple intents**: "show 2bhk and compare with citrine", "price and amenities"
- **Incomplete sentences**: "lets pitch", "more about", "nearby to"
- **Follow-ups without context**: "more", "what else", "anything else", "continue"

**MIXED LANGUAGE (HINGLISH) UNDERSTANDING:**
Common Hindi words in real estate queries and their English meanings:
- **chahiye** = need/want → "2 bhk chahiye" = "I need 2BHK" (property_search)
- **ka/ki/ke** = of/the → "avalon ka price" = "price of avalon" (project_facts)
- **mein/me** = in → "whitefield mein projects" = "projects in whitefield" (property_search)
- **kahan/kaha** = where → "kahan pe hai" = "where is it" (project_facts if project mentioned, else sales_conversation)
- **kitna** = how much → "kitna price hai" = "what is the price" (project_facts if project mentioned)
- **kyun/kyu** = why → "kyun invest kare" = "why should I invest" (sales_conversation)
- **dikhao/dikhaao** = show → "projects dikhao" = "show projects" (property_search)
- **batao** = tell → "price batao" = "tell the price" (project_facts)
- **kaunsa** = which → "kaunsa better hai" = "which is better" (sales_conversation)

**CRITICAL HINGLISH INTENT CLASSIFICATION:**
- "2 bhk chahiye" → intent: property_search (user wants 2BHK), extraction: {configuration: "2BHK"}
- "3 bhk chahiye budget 2 crore" → intent: property_search, extraction: {configuration: "3BHK", budget_max: 200}
- "avalon ka price" → intent: project_facts (asking about Avalon price), extraction: {project_name: "Brigade Avalon", fact_type: "price"}
- "citrine ki location kahan hai" → intent: project_facts (asking where Citrine is), extraction: {project_name: "Brigade Citrine", fact_type: "location"}
- "whitefield mein projects" → intent: property_search (searching in Whitefield), extraction: {location: "Whitefield"}
- "sarjapur mein 2bhk dikhao" → intent: property_search, extraction: {location: "Sarjapur", configuration: "2BHK"}
- "price kitna hai" (with context) → intent: project_facts (vague query about price), use session context for project_name

**DO NOT rely on keywords or patterns. Understand intent from:**
1. **Query semantics** (meaning, not words)
2. **Conversation context** (what was discussed before)
3. **Session state** (last shown projects, filters, interested projects)
4. **Natural language patterns** (how humans actually speak)

If query is ambiguous, use context to infer most likely intent. Never ask for clarification - infer from available context.

**YOUR JOB - UNDERSTAND ALL QUERIES:**
- Match ANY query to projects in database, even if:
  * Project name is partial ("Green Vista" → match to "Green Vista in Bellandur")
  * Query is vague ("price" → use last_shown_projects to find project)
  * Question is incomplete ("lets pitch" → extract project name from context)
  * Query doesn't mention project explicitly (use session context)
  * Query is a single word ("more", "nearby", "details") → infer from context
  * Query is incomplete sentence → auto-complete using conversation history
  * Query uses pronouns ("these", "those", "it") → resolve from context
  * Query is a follow-up ("what else", "anything else") → continue from last search
  * Query has typos → understand despite spelling errors
  * Query is in mixed language → understand multilingual queries

**BARE NUMBER HANDLING (CRITICAL):**
- If the query is just a bare number (e.g., "1.5", "1.7", "2.2", "0.8"), interpret it as **Budget in Crores**.
- INTENT: property_search
- EXTRACTION: { "budget_max": <number * 100> } (Convert Cr to Lakhs)
- Reasoning: "Bare number interpreted as budget in Crores"
- Example: "1.7" → intent: property_search, extraction: { "budget_max": 170 }

**PROJECT NAME MATCHING (CRITICAL - HANDLE TYPOS):**
- If query mentions ANY part of a project name (even with typos), match it to available_projects
- **TYPO HANDLING EXAMPLES:**
  * "avalon prise" → project_name: "Brigade Avalon", fact_type: "price" (handle BOTH typos)
  * "citrine ammenities" → project_name: "Brigade Citrine", fact_type: "amenities" (handle BOTH typos)
  * "brigade avlon" → project_name: "Brigade Avalon" (handle project name typo)
  * "avalon" → match to "Brigade Avalon" (partial name)
  * "citrine" → match to "Brigade Citrine" (partial name)
  * "green vista" → match to "Green Vista in Bellandur" (partial match)
- **FACT TYPE TYPO HANDLING:**
  * "prise" → fact_type: "price"
  * "ammenities" → fact_type: "amenities"
  * "rera numbr" → fact_type: "rera_number"
  * "locaton" → fact_type: "location"
- Use fuzzy matching against available_projects list: "green" could match "Green Vista", "Green Park", etc.
- If multiple matches, prefer the one in session_state.last_shown_projects or interested_projects
- **ALWAYS extract project_name when query mentions ANY project-related word, even with typos**

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

**PATH 2: GPT SALES CONSULTANT** (If NOT in database → Get directly from GPT)
- Questions about things NOT in database:
  * **Distance/Connectivity** (PRIORITY - even if project mentioned): "how far is airport from X", "distance of airport from X", "distance to office", "nearby schools", "metro distance", "how far is X from Y"
  * Advice: "investment potential", "why buy in Whitefield", "pros and cons"
- Generic questions: "How to stretch budget?", "What is EMI?", "loan eligibility"
- Follow-ups: "more", "tell me more", "continue", "give more points"
- Objections: "too expensive", "location too far"
- Greetings: "hi", "hello"
- **CRITICAL ROUTING RULE**: If query asks about distance/connectivity (understand semantic meaning, not keywords) → ALWAYS route to GPT, even if project_name is extracted. Extract project_name for context but use GPT for answer. Examples: "how far", "distance", "nearby", "metro", "airport", "school", "office" - but understand variations like "airport se kitna dur", "metro distance", "nearby places".
- data_source: "gpt_generation"

**INTENT CLASSIFICATION - HANDLE ALL QUERY TYPES:**

1. **PROPERTY_SEARCH** (→ database):
   - User wants to find/search properties
   - Has filters: BHK, location, budget
   - Includes: "show me", "find", "search", "looking for", "need", "want"
   - Includes: "minimum budget", "starting price", "cheapest" (calculate min from results)
   - Includes: "nearby", "more nearby", "what else" (continue from last search)
   - data_source: "database"

2. **PROJECT_FACTS** (→ database):
   - User asks about a SPECIFIC PROJECT by name (explicitly mentioned in query or from session context)
   - Factual questions about project data IN database: "price", "rera", "possession", "amenities", "configuration", "status"
   - Vague queries with project context: "price", "rera", "amenities", "details", "more" (when asking about DB fields)
   - **CRITICAL**: Only classify as project_facts if user explicitly names the project OR refers to a project from conversation history
   - **DO NOT classify as project_facts** if query is a general area search like "show me projects in Sarjapur"
   - Examples:
     * ✓ "Tell me about Brigade Citrine" → project_facts (explicit project mention)
     * ✓ "What's the price?" (after discussing Brigade Citrine) → project_facts (context)
     * ✗ "Show me projects in Sarjapur" → property_search (area search, NOT project_facts)
     * ✗ "Find 2BHK in Whitefield" → property_search (area search, NOT project_facts)
   - **EXCEPTION**: Distance/connectivity questions → route to GPT even if project mentioned
   - data_source: "database"

3. **NEARBY_PROPERTIES** (→ database):
   - User asks for nearby properties: "show nearby", "what else nearby", "more nearby"
   - Uses location from context (last mentioned location or last shown project location)
   - data_source: "database"

4. **SALES_CONVERSATION** (→ GPT):
   - Generic advice, objections, FAQs
   - Questions NOT about specific projects
   - **Distance/Connectivity questions** (even if project mentioned): "distance of airport from X", "how far is X from airport", "distance to office", "nearby schools", "metro distance"
   - Location comparisons: "why whitefield", "whitefield vs sarjapur"
   - Investment advice: "investment potential", "ROI", "appreciation"
   - Process questions: "how to buy", "registration process", "EMI calculation"
   - **CRITICAL**: If query asks about distance/connectivity, route to GPT but extract project_name for context
   - data_source: "gpt_generation"

**Entity Extraction (CRITICAL - HANDLE TYPOS):**
- configuration: "2BHK", "3BHK", "4BHK"
- budget_max: In lakhs (2 Cr = 200 lakhs)
- location: "Whitefield", "Sarjapur", "East Bangalore"
- **project_name: ALWAYS extract from query (even with typos) OR session context**
  * Match typos to available_projects: "avlon" → "Brigade Avalon", "citrine" → "Brigade Citrine"
  * Use fuzzy matching against available_projects list
  * If not in query, use last_shown_projects[0] or interested_projects[-1]
- **fact_type: Extract and normalize typos**
  * "prise" → "price"
  * "ammenities" → "amenities"
  * "rera numbr" → "rera_number"
  * "locaton" → "location"
  * "possesion" → "possession"
  * "config" → "configuration"
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

Query: "avalon prise" (typo in both project name and fact type)
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Query about price with typo - match 'avalon' to 'Brigade Avalon' from available_projects, 'prise' → 'price'",
  "extraction": {"project_name": "Brigade Avalon", "fact_type": "price"}
}
```

Query: "citrine ammenities" (typo in both project name and fact type)
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Query about amenities with typo - match 'citrine' to 'Brigade Citrine' from available_projects, 'ammenities' → 'amenities'",
  "extraction": {"project_name": "Brigade Citrine", "fact_type": "amenities"}
}
```

Query: "brigade avlon" (typo in project name)
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Project name with typo - match 'avlon' to 'Brigade Avalon' from available_projects",
  "extraction": {"project_name": "Brigade Avalon"}
}
```

Query: "rera numbr" (typo in fact type, no project mentioned - use context)
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.90,
  "reasoning": "RERA query with typo - use last_shown_projects context, 'numbr' → 'rera_number'",
  "extraction": {"project_name": "Brigade Avalon", "fact_type": "rera_number"}
}
```

Query: "How far is airport from Avalon?"
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.95,
  "reasoning": "Distance question - not in database, route to GPT. Project name extracted for context.",
  "extraction": {"project_name": "Brigade Avalon", "topic": "connectivity", "fact_type": "distance"}
}
```

Query: "distance of airport form brigade avalon"
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.95,
  "reasoning": "Distance question with typo - not in database, route to GPT. Project name extracted for context.",
  "extraction": {"project_name": "Brigade Avalon", "topic": "connectivity", "fact_type": "distance"}
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

Query: "2 bhk chahiye" (Hindi-English mixed)
```json
{
  "intent": "property_search",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Hindi word 'chahiye' means 'need/want' - user wants to search for 2BHK properties",
  "extraction": {"configuration": "2BHK"}
}
```

Query: "avalon ka price" (Hindi-English mixed)
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Hindi word 'ka' means 'of' - user asking for price of Avalon project",
  "extraction": {"project_name": "Brigade Avalon", "fact_type": "price"}
}
```

Query: "citrine ki location kahan hai" (Hindi-English mixed)
```json
{
  "intent": "project_facts",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Hindi words 'ki' (of), 'kahan hai' (where is) - user asking where Citrine is located",
  "extraction": {"project_name": "Brigade Citrine", "fact_type": "location"}
}
```

Query: "whitefield mein projects dikhao" (Hindi-English mixed)
```json
{
  "intent": "property_search",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Hindi words 'mein' (in), 'dikhao' (show) - user wants to search for projects in Whitefield",
  "extraction": {"location": "Whitefield"}
}
```

Query: "3 bhk budget 2 crore mein chahiye" (Hindi-English mixed)
```json
{
  "intent": "property_search",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "Mixed language search query - 'chahiye' (need), 'mein' (in) - user needs 3BHK under 2 crores",
  "extraction": {"configuration": "3BHK", "budget_max": 200}
}
```

Now classify the user's query following these rules. Use GPT understanding to match partial project names, use session context for vague queries, handle Hindi-English (Hinglish) queries naturally, and never lose context. Return ONLY valid JSON, no other text.

**CRITICAL EXTRACTION REQUIREMENT:**
If you classify as "project_facts", you MUST include "project_name" in the extraction field. This is MANDATORY, not optional.
- If query has typos (e.g., "avalon prise"), extract: {"project_name": "Brigade Avalon", "fact_type": "price"}
- If query is vague (e.g., "price"), use last_shown_projects or interested_projects from context
- If query mentions a project (even with typos), match it to available_projects list and extract the EXACT project name

**DO NOT return project_facts intent without project_name in extraction. This will cause errors.**
"""
