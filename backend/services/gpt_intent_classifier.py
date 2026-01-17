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

**SIMPLIFIED 2-PATH ARCHITECTURE:**

**PATH 1: DATABASE** (Facts that EXIST in database)
- property_search: "show me 2BHK", "find flats in Whitefield"
- project_facts: "price of X", "RERA of Y", "possession date of Z", "tell me about X", "details of Y", "amenities in X"
- Database contains: name, developer, location, price, RERA, configuration, possession date, status, amenities, highlights, usp

**PATH 2: GPT SALES CONSULTANT** (Everything else - DEFAULT)
- sales_conversation: Generic FAQs, objections, follow-ups, advice, chitchat
- Examples: "How to stretch budget?", "What is EMI?", "more", "tell me more", "too expensive"
- Project questions NOT in DB: "how far is airport from Y", "investment potential", "nearby schools"

**CRITICAL ROUTING RULES:**

1. **PROPERTY_SEARCH** (→ database):
   - ONLY if user explicitly wants to find/search properties
   - Keywords: "show me", "find", "search for", "looking for", "need", "want"
   - Has ANY filter: BHK OR location OR budget (not all required)
   - data_source: "database"

2. **PROJECT_FACTS** (→ database) - **EXPANDED**:
   - User asks for ANY information about a SPECIFIC project
   - Broad queries: "tell me about X", "details of Y", "information about Z", "describe X", "what is X"
   - Specific facts: price, RERA, configuration, possession, developer, location, amenities, facilities, features, highlights, usp
   - Examples:
     * "Tell me about Brigade Citrine" → database (project details)
     * "Amenities in Avalon" → database (amenities field)
     * "Details of Neopolis" → database (all project fields)
     * "Price of Citrine" → database (price field)
   - data_source: "database"

3. **SALES_CONVERSATION** (→ GPT) - **DEFAULT for everything else**:
   - Questions about things NOT in database:
     * Distance/Location: "how far is airport from X", "distance to office", "nearby schools"
     * Advice: "investment potential", "why buy in Whitefield", "pros and cons"
   - Generic questions: "How to stretch budget?", "What is EMI?", "loan eligibility"
   - Follow-ups: "more", "tell me more", "continue", "give more points"
   - Objections: "too expensive", "location too far"
   - Greetings: "hi", "hello"
   - data_source: "gpt_generation"

**CONTEXT-AWARE "MORE" HANDLING:**

When query is "more", "tell me more", "continue", "give more points":
1. Check session.last_intent from context
2. If last_intent was "property_search" or "project_facts":
   → Classify as "sales_conversation" (elaborate on shown projects)
3. If last_intent was "sales_conversation":
   → Classify as "sales_conversation" (continue topic)
4. **NEVER** classify standalone "more" as "property_search"
5. "more" is ALWAYS elaboration, NEVER a search

**KEY PRINCIPLE:**
- If answer requires inference, calculation, or advice → GPT
- If answer is a direct database field → database
- When in doubt → GPT (smarter to let GPT handle than force DB lookup)

**Entity Extraction:**
- configuration: "2BHK", "3BHK", "4BHK"
- budget_max: In lakhs (2 Cr = 200 lakhs)
- location: "Whitefield", "Sarjapur", "East Bangalore"
- project_name: Extract if mentioned (Brigade Citrine, Sobha Neopolis, etc.)
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

Query: "more" (with last_intent="sales_conversation", last_topic="budget_stretch")
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.90,
  "reasoning": "Continue previous conversation about budget stretching",
  "extraction": {"topic": "budget_stretch"}
}
```

Query: "more" (with last_intent="property_search", interested_projects=["Brigade Citrine"])
```json
{
  "intent": "sales_conversation",
  "data_source": "gpt_generation",
  "confidence": 0.88,
  "reasoning": "Elaborate on shown projects",
  "extraction": {"project_name": "Brigade Citrine", "topic": "general_selling_points"}
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

Now classify the user's query following these rules. Return ONLY valid JSON, no other text.
"""
