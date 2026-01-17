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
    session_state: Optional[Dict] = None
) -> Dict:
    """
    GPT-4 primary classifier with intelligent data source selection.

    Args:
        query: User's input query
        conversation_history: Last N conversation turns for context (optional)
        session_state: Current session state with selected_project, requirements, etc. (optional)

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

    # Add conversation history for context (last 5 turns)
    if conversation_history:
        messages.extend(conversation_history[-5:])

    # Add session context if available
    context_info = ""
    if session_state:
        if session_state.get("selected_project_name"):
            context_info += f"\nCurrent selected project: {session_state['selected_project_name']}"
        if session_state.get("requirements"):
            req = session_state["requirements"]
            context_info += f"\nUser requirements: config={req.get('configuration')}, location={req.get('location')}, budget_max={req.get('budget_max')}"

    # Add user query with context
    user_message = f"Classify this query: {query}"
    if context_info:
        user_message += f"\n\nSession context:{context_info}"

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

**1. Classify the intent into one of:**
   - property_search: User wants to find properties OR asks for more options/similar projects ("show me more", "show more options", "any other projects", "similar properties", "something else"). WARNING: Do NOT classify "location of [Project]" or "price of [Project]" as property_search.
   - project_details: User asks to see the full details card ("show me details of X", "brochure of X", "all info about X")
   - more_info_request: User asks SPECIFIC questions about a known project ("location of Birla Evara", "price of Sobha Neopolis", "possession date of X", "distance from X to Y", "is it near X"). ALSO includes elaboration requests ("tell me more", "investment potential").
   - sales_objection: User has concerns (price too high, location too far, possession too late, don't trust UC)
   - meeting_request: User strictly asks TO schedule/book ("schedule meeting", "book visit", "app meeting", "arrange call")
   - site_visit: User wants to visit a property site (often overlaps with meeting_request)
   - sales_faq: User asks about sales process, "how do I setup site visit", "what is the process", Pinclick services, general real estate FAQs
   - comparison: User wants to compare 2+ projects
   - greeting: User greeting (hi, hello, good morning, etc.)
   - unsupported: Out-of-scope queries (politics, sports, weather, future predictions, legal advice)

**2. Determine data_source:**
   - "database": ALWAYS use for property_search.
   - "gpt_generation": ALWAYS use for more_info_request (specific questions like "location of X", "price of X" need natural language answers).
   - "hybrid": For general "tell me about PROJECT" queries - show DB facts + persuasive intro

**CRITICAL DATA SOURCE RULES:**
   - property_search → ALWAYS data_source="database"
   - more_info_request (specific questions) → data_source="gpt_generation"
   - NEVER go to web for project searches

**3. Extract entities:**
   - configuration: "2BHK", "3BHK", "4BHK", "2-bedroom" → "2BHK"
   - budget_max: Number in lakhs (convert crores to lakhs: 2 Cr = 200 lakhs)
   - budget_min: Number in lakhs (if range specified)
   - location: Locality/area name (Whitefield, Sarjapur, East Bangalore, etc.)
   - project_name: CRITICAL - ALWAYS extract project name if mentioned.
     * "location of birla evara" -> project_name="Birla Evara", topic="location"
     * "price of sobha neopolis" -> project_name="Sobha Neopolis", topic="price"
     * ANY real estate project name mentioned in the query should be extracted
   - topic: For more_info_request (sustainability, investment, location_advantages, amenities_benefits, general_selling_points)
   - objection_type: For sales_objection (budget, location, possession, trust)

**4. Return JSON format:**
   - **CONFIDENCE SCORING:**
     * "location of [Project]", "price of [Project]" -> confidence: 0.95 (Extremely High)
     * "tell me about [Project]" -> confidence: 0.95 (Extremely High)
     * "2BHK in Whitefield" -> confidence: 0.95 (Extremely High)
     * "show me flats" -> confidence: 0.9 (High)

```json
{
  "intent": "property_search|project_details|more_info_request|...",
  "data_source": "database|gpt_generation|hybrid",
  "confidence": 0.95,
  "reasoning": "User asked for specific attribute (location) of a named entity (Birla Evara), which is a direct fact query.",
  "extraction": {
    "configuration": "2BHK",
    "budget_max": 200,
    "location": "Whitefield",
    "project_name": "Brigade Citrine",
    "topic": "location"
  }
}
```

**Critical Context:**
- We have 76 real estate projects in our database with: name, developer, location, config, price, RERA, amenities, USP
- We NEVER search for projects outside the database - ALL project data comes from DB ONLY
- We NEVER use GPT/web to generate project facts, prices, configs, or search results
- For vague queries like "more pointers", "tell me more" → use session context to determine project_name
- For structured facts (RERA, price, configs, developer, location) → data_source="database" ALWAYS
- For persuasive elaboration ONLY (investment pitch, sustainability benefits, amenity lifestyle) → data_source="gpt_generation"

**Examples:**

Query: "I want a 2BHK in Whitefield under 2 Cr"
```json
{
  "intent": "property_search",
  "data_source": "database",
  "confidence": 0.95,
  "reasoning": "User specifies config, location, and budget - clear property search",
  "extraction": {"configuration": "2BHK", "location": "Whitefield", "budget_max": 200}
}
```

Query: "Tell me more about Brigade Citrine sustainability"
```json
{
  "intent": "more_info_request",
  "data_source": "gpt_generation",
  "confidence": 0.88,
  "reasoning": "User wants elaboration on sustainability - requires GPT to explain IGBC benefits",
  "extraction": {"project_name": "Brigade Citrine", "topic": "sustainability"}
}
```

Query: "What is the RERA number for Sobha Neopolis?"
```json
{
  "intent": "project_details",
  "data_source": "database",
  "confidence": 0.98,
  "reasoning": "RERA number is structured fact in database",
  "extraction": {"project_name": "Sobha Neopolis", "fact_type": "rera_number"}
}
```

Query: "more pointers on avalon"
```json
{
  "intent": "more_info_request",
  "data_source": "gpt_generation",
  "confidence": 0.90,
  "reasoning": "User wants additional selling points about Brigade Avalon project",
  "extraction": {"project_name": "Brigade Avalon", "topic": "general_selling_points"}
}
```

Query: "More pointers" (with session context: selected_project="Brigade Citrine")
```json
{
  "intent": "more_info_request",
  "data_source": "gpt_generation",
  "confidence": 0.75,
  "reasoning": "Vague request for additional insights about selected project",
  "extraction": {"project_name": "Brigade Citrine", "topic": "general_selling_points"}
}
```

Query: "too expensive for me"
```json
{
  "intent": "sales_objection",
  "data_source": "gpt_generation",
  "confidence": 0.90,
  "reasoning": "Budget objection - needs persuasive response",
  "extraction": {"objection_type": "budget"}
}
```

Query: "Tell me about Brigade Citrine"
```json
{
  "intent": "more_info_request",
  "data_source": "hybrid",
  "confidence": 0.85,
  "reasoning": "General query - show DB facts + GPT persuasion",
  "extraction": {"project_name": "Brigade Citrine", "topic": "general"}
}
```

Now classify the user's query following these rules. Return ONLY valid JSON, no other text.
"""
