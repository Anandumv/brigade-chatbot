"""
Intelligent Sales Conversation Service
Uses GPT-4 for highly intelligent, context-aware sales conversations.

This service provides:
- Natural language understanding for sales queries
- Context-aware conversational responses
- Intelligent objection handling with GPT-4
- Dynamic response generation based on conversation context
"""

import os
import logging
from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from pydantic import BaseModel
import json
import httpx

logger = logging.getLogger(__name__)


class SalesIntent(str, Enum):
    """Sales-specific intent types"""
    FAQ_BUDGET_STRETCH = "faq_budget_stretch"
    FAQ_OTHER_LOCATION = "faq_other_location"
    FAQ_UNDER_CONSTRUCTION = "faq_under_construction"
    FAQ_FACE_TO_FACE_MEETING = "faq_face_to_face_meeting"
    FAQ_SITE_VISIT = "faq_site_visit"
    FAQ_PINCLICK_VALUE = "faq_pinclick_value"
    
    OBJECTION_BUDGET = "objection_budget"
    OBJECTION_LOCATION = "objection_location"
    OBJECTION_POSSESSION = "objection_possession"
    OBJECTION_UNDER_CONSTRUCTION = "objection_under_construction"
    
    REQUEST_MEETING = "request_meeting"
    REQUEST_SITE_VISIT = "request_site_visit"
    
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    
    PROPERTY_QUERY = "property_query"
    FOLLOW_UP = "follow_up"
    
    UNKNOWN = "unknown"


class ConversationContext(BaseModel):
    """Rich conversation context for multi-turn conversations"""
    session_id: str = ""
    current_filters: Dict[str, Any] = {}
    last_intent: Optional[str] = None
    conversation_history: List[Dict[str, str]] = []
    objections_raised: List[str] = []
    interested_projects: List[str] = []
    client_preferences: Dict[str, Any] = {}
    meeting_suggested: bool = False
    site_visit_suggested: bool = False
    budget_discussed: bool = False
    location_discussed: bool = False


# ============================================================================
# SYSTEM PROMPTS FOR GPT-4
# ============================================================================

SALES_SYSTEM_PROMPT = """You are an expert real estate sales consultant for Pinclick, a premium property consultancy in Bangalore, India.

**Your Personality:**
- Warm, friendly, and highly professional
- Empathetic to customer concerns
- Persuasive but never pushy
- Solution-oriented and helpful
- Knowledgeable about Bangalore real estate market

**Your Goals:**
1. Understand customer needs deeply
2. Address objections tactfully
3. Guide customers toward making informed decisions
4. Always aim for a face-to-face meeting or site visit as the ultimate goal
5. Never say "no" - always find alternatives

**Key Knowledge:**
- Bangalore real estate market trends
- Benefits of under-construction vs ready properties
- Location appreciation potential
- RERA regulations and protections
- Home loan processes
- Pinclick's unique value proposition

**Response Guidelines:**
- Use emojis sparingly for warmth (1-3 per response)
- Keep responses conversational but informative
- Always end with a clear next step or question
- Format with bullet points for clarity when listing benefits
- Be specific with numbers when discussing value propositions
- Never make up property details - focus on general guidance

**Pinclick Value Proposition:**
- 500+ happy customers
- Verified listings only
- End-to-end support (search to possession)
- Expert market knowledge
- Best deals and exclusive offers
- 4.8/5 customer rating
"""

FAQ_CONTEXT = {
    SalesIntent.FAQ_BUDGET_STRETCH: """
The customer is asking about stretching their budget. Key points to cover:
- 10-15% stretch can give 25-30% better value
- Better location = higher appreciation
- Larger carpet area for comfortable living
- Premium amenities
- Reputed developer with proven track record
- EMI difference is often minimal (₹3-5K more per month)
End by offering to show options slightly above budget.
""",

    SalesIntent.FAQ_OTHER_LOCATION: """
The customer is hesitant about a suggested location. Key points:
- Infrastructure developments (Metro, flyovers, IT parks)
- 15-20% price advantage vs established areas
- 40-50% appreciation potential in 3-5 years
- Better specifications at same budget
- Share success stories of customers who were initially hesitant
End by offering to show options in both locations for comparison.
""",

    SalesIntent.FAQ_UNDER_CONSTRUCTION: """
The customer prefers ready-to-move but we're suggesting under-construction. Key points:
- 15-25% lower price
- Payment flexibility (pay in stages)
- Brand new property
- Customization options possible
- RERA protection (legally secured)
- Property appreciates by possession time
- Investment math: Buy at 1.2Cr, worth 1.6-1.8Cr by possession
End by offering to show both ready and under-construction options.
""",

    SalesIntent.FAQ_FACE_TO_FACE_MEETING: """
The customer is asking about meeting or needs to understand why meeting is important. Key points:
- Understand needs deeply and personally
- Show exclusive inventory not available online
- Explain payment plans in detail
- Answer all questions with documentation
- Build trust through personal interaction
- Virtual/site/office meeting options available
- No obligation - just exploration
End by asking for preferred date/time and meeting format.
""",

    SalesIntent.FAQ_SITE_VISIT: """
The customer is asking about site visits. Key points:
- See actual construction quality and progress
- Explore the neighborhood and connectivity
- Meet sales team for personalized assistance
- Get exclusive site visit offers
- Free pick-up and drop available
- Complimentary refreshments
- On-spot booking benefits (₹2-5 Lac off!)
- No obligation to buy
End by asking for preferred date/time and pickup location.
""",

    SalesIntent.FAQ_PINCLICK_VALUE: """
The customer wants to know about Pinclick's value. Key points:
- All properties personally verified
- Data-driven price analysis and negotiation
- Experienced property consultants
- Hassle-free documentation support
- Exclusive discounts and offers
- Post-sale support till possession and beyond
- 500+ happy customers this year
- ₹50 Cr+ worth of properties sold
- 4.8/5 customer satisfaction rating
- Zero complaints on RERA platform
End by offering to connect with recent customers for testimonials.
"""
}

OBJECTION_CONTEXT = {
    SalesIntent.OBJECTION_BUDGET: """
The customer has a budget objection (too expensive). Handle with empathy:
Options to present:
1. Similar projects in emerging areas (10-20% lower)
2. Slightly smaller configuration (well-designed 2BHK can match 3BHK space)
3. Under-construction options (lower price + appreciation)
4. If possible, encourage slight stretch (better long-term investment)
Ask which approach they'd prefer or offer to schedule a call to discuss specifics.
""",

    SalesIntent.OBJECTION_LOCATION: """
The customer has a location objection. Handle with understanding:
Explain why the alternate location was suggested:
- Same/better connectivity
- 15-20% lower price for same specs
- Higher appreciation potential
- New IT hubs coming up
If they still prefer original location:
1. Show options in higher budget
2. Find smaller configurations
3. Check resale options
Offer to show options in both locations for comparison. Suggest a site visit to experience both.
""",

    SalesIntent.OBJECTION_POSSESSION: """
The customer needs immediate possession. Understand their situation:
Ask why they need early possession:
1. Moving out of current home?
2. Paying rent and want to save?
3. Worried about construction delays?

Ready-to-move benefits: Immediate move-in, WYSIWYG, no risk
Under-construction benefits: 15-25% lower, flexible payment, brand new, RERA protected

Offer projects with 6-12 month possession as middle ground.
""",

    SalesIntent.OBJECTION_UNDER_CONSTRUCTION: """
The customer doesn't trust under-construction projects. Address concerns directly:
- Delays: RERA registered with penalty clauses, we recommend 95%+ on-time developers
- Quality: Site visits during construction, sample flats available, third-party audits
- Payments: Only 10-20% initially, rest linked to construction progress

If they still prefer ready-to-move:
- We have excellent ready options at slightly higher price
- Offer to show both for comparison
"""
}


class IntelligentSalesHandler:
    """
    Highly intelligent sales conversation handler powered by GPT-4.
    """
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.api_base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        self.model = os.getenv("LLM_MODEL", "openai/gpt-4-turbo-preview")
        
    async def _call_llm(
        self, 
        system_prompt: str, 
        user_message: str,
        context: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """Call GPT-4 for intelligent response generation."""
        
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add context if provided
        if context:
            messages.append({
                "role": "system", 
                "content": f"Additional context for this query:\n{context}"
            })
        
        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-6:]:  # Last 6 messages for context
                messages.append(msg)
        
        messages.append({"role": "user", "content": user_message})
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "messages": messages,
                        "temperature": 0.7,
                        "max_tokens": 800
                    }
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    logger.error(f"LLM API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return None

    def classify_intent(self, query: str) -> SalesIntent:
        """
        Intelligent intent classification using keyword matching + patterns.
        """
        query_lower = query.lower().strip()
        
        # Quick checks for common patterns
        
        # Agreement/Disagreement
        agreement_words = ["yes", "ok", "okay", "sure", "sounds good", "let's do it", 
                          "i agree", "that works", "fine", "alright", "go ahead", "yes please"]
        disagreement_words = ["no", "not interested", "don't want", "can't", 
                             "not possible", "don't agree", "won't work", "no thanks"]
        
        if any(query_lower.startswith(word) or query_lower == word for word in agreement_words):
            return SalesIntent.AGREEMENT
            
        if any(query_lower.startswith(word) or query_lower == word for word in disagreement_words):
            return SalesIntent.DISAGREEMENT
        
        # Meeting/Visit requests
        meeting_patterns = [
            "schedule meeting", "schedule a meeting", "book meeting", "arrange meeting",
            "want to meet", "can we meet", "let's meet", "set up meeting",
            "fix a meeting", "meeting time", "meeting date"
        ]
        if any(p in query_lower for p in meeting_patterns):
            return SalesIntent.REQUEST_MEETING
        
        visit_patterns = [
            "site visit", "visit site", "see the property", "visit property",
            "schedule visit", "arrange visit", "book visit", "want to visit",
            "can i visit", "show me the property", "see the flat", "see the project"
        ]
        if any(p in query_lower for p in visit_patterns):
            return SalesIntent.FAQ_SITE_VISIT
        
        # FAQ patterns
        budget_patterns = ["stretch budget", "increase budget", "afford more", 
                          "budget flexibility", "how to afford", "extend budget",
                          "budget upgrade", "higher budget worth", "spend more worth",
                          "why stretch", "should i stretch", "stretching budget",
                          "worth stretching", "stretching my budget", "increase my budget"]
        if any(p in query_lower for p in budget_patterns):
            return SalesIntent.FAQ_BUDGET_STRETCH
        
        location_patterns = ["other location", "different location", "alternate location",
                            "why this location", "suggest other area", "another area",
                            "nearby location", "location alternative"]
        if any(p in query_lower for p in location_patterns):
            return SalesIntent.FAQ_OTHER_LOCATION
        
        construction_patterns = ["under construction", "not ready", "still building",
                                "construction project", "benefit of under", "why under construction"]
        if any(p in query_lower for p in construction_patterns):
            return SalesIntent.FAQ_UNDER_CONSTRUCTION
        
        f2f_patterns = ["face to face", "meet in person", "personal meeting",
                       "why meet", "importance of meeting", "should we meet"]
        if any(p in query_lower for p in f2f_patterns):
            return SalesIntent.FAQ_FACE_TO_FACE_MEETING
        
        pinclick_patterns = ["pinclick", "your company", "your service", "what do you offer",
                            "why should i use", "your value", "how you help"]
        if any(p in query_lower for p in pinclick_patterns):
            return SalesIntent.FAQ_PINCLICK_VALUE
        
        # Objection patterns
        budget_objection = ["too expensive", "can't afford", "beyond budget", "out of budget",
                           "very costly", "high price", "expensive", "not in my budget",
                           "price is high", "over budget"]
        if any(p in query_lower for p in budget_objection):
            return SalesIntent.OBJECTION_BUDGET
        
        location_objection = ["too far", "far from", "don't like location", "location is far",
                             "commute issue", "far from office", "distance problem"]
        if any(p in query_lower for p in location_objection):
            return SalesIntent.OBJECTION_LOCATION
        
        possession_objection = ["need now", "need immediately", "can't wait", "urgent need",
                               "immediate possession", "want quickly", "waiting too long"]
        if any(p in query_lower for p in possession_objection):
            return SalesIntent.OBJECTION_POSSESSION
        
        uc_objection = ["don't trust", "scared of delay", "construction risk", 
                       "prefer ready", "want ready only", "ready to move only"]
        if any(p in query_lower for p in uc_objection):
            return SalesIntent.OBJECTION_UNDER_CONSTRUCTION
        
        # Property query patterns
        property_patterns = ["show me", "find me", "looking for", "search", "bhk",
                            "bedroom", "2bhk", "3bhk", "apartments", "flats", "property"]
        if any(p in query_lower for p in property_patterns):
            return SalesIntent.PROPERTY_QUERY
        
        return SalesIntent.UNKNOWN

    async def generate_intelligent_response(
        self,
        query: str,
        intent: SalesIntent,
        context: Optional[ConversationContext] = None
    ) -> str:
        """
        Generate highly intelligent, context-aware response using GPT-4.
        """
        
        # Build context for the LLM
        additional_context = ""
        
        # Add FAQ/Objection specific context
        if intent in FAQ_CONTEXT:
            additional_context = FAQ_CONTEXT[intent]
        elif intent in OBJECTION_CONTEXT:
            additional_context = OBJECTION_CONTEXT[intent]
        
        # Add conversation context
        if context:
            if context.current_filters:
                additional_context += f"\nCustomer's current preferences: {json.dumps(context.current_filters)}"
            if context.objections_raised:
                additional_context += f"\nPrevious objections raised: {', '.join(context.objections_raised)}"
            if context.interested_projects:
                additional_context += f"\nProjects customer showed interest in: {', '.join(context.interested_projects)}"
        
        # Generate response
        conversation_history = context.conversation_history if context else None
        
        response = await self._call_llm(
            system_prompt=SALES_SYSTEM_PROMPT,
            user_message=query,
            context=additional_context,
            conversation_history=conversation_history
        )
        
        if response:
            return response
        
        # Fallback to template if LLM fails
        return self._get_fallback_response(intent)
    
    def _get_fallback_response(self, intent: SalesIntent) -> str:
        """Fallback template responses if LLM is unavailable."""
        
        fallbacks = {
            SalesIntent.FAQ_BUDGET_STRETCH: """
💰 **Great question about stretching your budget!**

A 10-15% increase often gives you:
- 📍 Better location with higher appreciation
- 🏠 Larger carpet area
- ✨ Premium amenities
- 🏆 Reputed developer

The EMI difference is often just ₹3-5K more per month for significantly better value!

👉 **Would you like me to show you options slightly above your budget?**
""",
            SalesIntent.FAQ_SITE_VISIT: """
🚗 **Let's arrange your site visit!**

What you'll experience:
- 🏗️ Actual construction quality
- 🌳 Neighborhood exploration
- 🎁 Exclusive site visit offers
- 🚙 Free pick-up & drop

**On-spot booking benefits:** Up to ₹2-5 Lac off!

👉 **When would you like to visit? Share your preferred date/time!**
""",
            SalesIntent.REQUEST_MEETING: """
📅 **Excellent! Let's schedule your meeting!**

I can arrange:
- 🏢 Office meeting (detailed presentations)
- 🏗️ Site visit (see actual property)
- 💻 Video call (if you're busy)

Our expert will personally guide you through all options.

👉 **Please share your preferred date, time, and format!**
""",
            SalesIntent.OBJECTION_BUDGET: """
💡 **I understand your budget concerns.**

Let me help find the best option:
1. **Emerging areas:** 10-20% lower prices
2. **Smart configuration:** Well-designed smaller units
3. **Under-construction:** Lower price + appreciation

👉 **Which approach works best for you? Or shall we discuss specifics over a call?**
""",
        }
        
        return fallbacks.get(intent, """
I'd love to help you further! 

👉 **Would you like to schedule a quick call so I can understand your needs better?**
""")

    async def handle_query(
        self,
        query: str,
        context: Optional[ConversationContext] = None
    ) -> Tuple[str, SalesIntent, bool]:
        """
        Main entry point for handling sales queries.
        
        Returns:
            (response_text, intent, should_fallback_to_rag)
        """
        intent = self.classify_intent(query)
        logger.info(f"Classified sales intent: {intent.value}")
        
        # For unknown intents or property queries, fallback to RAG
        if intent in [SalesIntent.UNKNOWN, SalesIntent.PROPERTY_QUERY]:
            return "", intent, True
        
        # Generate intelligent response
        response = await self.generate_intelligent_response(query, intent, context)
        
        return response, intent, False
    
    def should_handle(self, query: str) -> bool:
        """Check if this handler should process the query."""
        intent = self.classify_intent(query)
        return intent not in [SalesIntent.UNKNOWN, SalesIntent.PROPERTY_QUERY]


# Global instance
intelligent_sales = IntelligentSalesHandler()
