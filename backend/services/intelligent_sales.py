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

from services.sales_intelligence import sales_intelligence
from services.sales_conversation import SUGGESTED_ACTIONS
from config import settings

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
""",

    SalesIntent.FAQ_BUDGET_STRETCH: """
The customer is asking about stretching their budget. Be supportive and analytical:
- Explain that real estate is a long-term asset; 10-15% stretch now often means 30-40% better returns or asset quality.
- Focus on EMI impact: A ₹10L stretch is often just ~₹8-9k/month extra in EMI, which is manageable for most IT professionals.
- Suggest "Value Buying": Getting a larger carpet area or better location now saves upgrading costs later (stamp duty, registration again).
- Mention Developer Subvention Plans or Flexible Payment Plans if applicable.
- Ask: "Would you be open to seeing options slightly above budget if the location/ROI justifies it?"
End by offering to show high-value options just above their range.
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
    Integrates with Pixeltable for pre-computed FAQ responses and session manager for CTAs.
    """
    
    def __init__(self):
        self.api_key = settings.openai_api_key
        self.api_base = settings.openai_base_url
        self.model = settings.effective_gpt_model
        
        # Try to initialize Pixeltable for pre-computed FAQs
        self.pixeltable_available = False
        try:
            from services.pixeltable_retrieval import pixeltable_retrieval
            self.pixeltable_retrieval = pixeltable_retrieval
            self.pixeltable_available = pixeltable_retrieval.is_available()
            if self.pixeltable_available:
                logger.info("Pixeltable FAQ integration enabled")
        except ImportError:
            logger.warning("Pixeltable not available, using LLM-only responses")
            self.pixeltable_retrieval = None
        
        # Session manager for CTA tracking
        try:
            from services.session_manager import session_manager, get_cta_for_context
            self.session_manager = session_manager
            self.get_cta = get_cta_for_context
            logger.info("Session manager integration enabled")
        except ImportError:
            self.session_manager = None
            self.get_cta = None
        
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
        Intelligent intent classification using GPT.
        Falls back to keyword matching if GPT fails.
        """
        query_lower = query.lower().strip()
        
        # Try GPT-first classification
        try:
            from services.gpt_intent_classifier import classify_intent_gpt_first
            gpt_result = classify_intent_gpt_first(query)
            gpt_intent = gpt_result.get("intent", "")
            
            # Map GPT intents to SalesIntent
            intent_mapping = {
                "sales_objection": {
                    "budget": SalesIntent.OBJECTION_BUDGET,
                    "location": SalesIntent.OBJECTION_LOCATION,
                    "possession": SalesIntent.OBJECTION_POSSESSION,
                    "trust": SalesIntent.OBJECTION_UNDER_CONSTRUCTION,
                },
                # "sales_faq": SalesIntent.FAQ_PINCLICK_VALUE, # REMOVED: Do not blindly map all FAQs to Pinclick Value
                "site_visit": SalesIntent.FAQ_SITE_VISIT,
                "meeting_request": SalesIntent.REQUEST_MEETING,
                "property_search": SalesIntent.PROPERTY_QUERY,
                "project_details": SalesIntent.PROPERTY_QUERY,
            }
            
            if gpt_intent == "sales_objection":
                objection_type = gpt_result.get("extraction", {}).get("objection_type", "")
                mapped_intent = intent_mapping["sales_objection"].get(objection_type, SalesIntent.OBJECTION_BUDGET)
                logger.info(f"GPT classified sales intent: {mapped_intent.value}")
                return mapped_intent
            elif gpt_intent == "sales_faq":
                # Fall through to keyword matching for specific FAQs (Budget, Location, etc.)
                pass
            elif gpt_intent in intent_mapping:
                mapped_intent = intent_mapping[gpt_intent]
                logger.info(f"GPT classified sales intent: {mapped_intent.value}")
                return mapped_intent
            
            # Check for more_info_request -> treat as property query to fall through
            if gpt_intent == "more_info_request":
                return SalesIntent.PROPERTY_QUERY
                
        except Exception as e:
            logger.warning(f"GPT classification failed, falling back to keywords: {e}")
        
        # Fallback to keyword matching
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
            "can i visit", "show me the property", "see the flat", "see the project",
            "setup visit", "setup site visit", "set up visit", "plan visit"
        ]
        if any(p in query_lower for p in visit_patterns):
            return SalesIntent.FAQ_SITE_VISIT
        
        # FAQ patterns
        budget_patterns = ["stretch budget", "increase budget", "afford more", 
                          "budget flexibility", "how to afford", "extend budget",
                          "budget upgrade", "higher budget worth", "spend more worth",
                          "why stretch", "should i stretch", "stretching budget",
                          "worth stretching", "stretching my budget", "increase my budget",
                          "how can i stretch", "stretch my budget", "can i stretch"]
        if any(p in query_lower for p in budget_patterns):
            return SalesIntent.FAQ_BUDGET_STRETCH
        
        location_patterns = ["other location", "different location", "alternate location",
                            "why this location", "suggest other area", "another area",
                            "nearby location", "location alternative"]
        if any(p in query_lower for p in location_patterns):
            return SalesIntent.FAQ_OTHER_LOCATION
        
        construction_patterns = ["benefit of under", "why under construction", "what about access"]
        if any(p in query_lower for p in construction_patterns):
            return SalesIntent.FAQ_UNDER_CONSTRUCTION
        
        f2f_patterns = ["face to face", "meet in person", "personal meeting",
                       "why meet", "importance of meeting", "should we meet",
                       "why do i need to meet", "why meeting", "can't you send details", 
                       "send on whatsapp", "share on whatsapp"]
        if any(p in query_lower for p in f2f_patterns):
            return SalesIntent.FAQ_FACE_TO_FACE_MEETING
        
        pinclick_patterns = ["pinclick", "your company", "your service", "what do you offer",
                            "why should i use", "your value", "how you help", "why buy through"]
        if any(p in query_lower for p in pinclick_patterns):
            return SalesIntent.FAQ_PINCLICK_VALUE
        
        # Objection patterns
        budget_objection = ["too expensive", "can't afford", "beyond budget", "out of budget",
                           "very costly", "high price", "expensive", "not in my budget",
                           "price is high", "over budget", "tight budget", "budget issue",
                           "above my budget", "more than my budget", "broke", "cheap", 
                           "less price", "low budget"]
        if any(p in query_lower for p in budget_objection):
            return SalesIntent.OBJECTION_BUDGET
        
        location_objection = ["too far", "far from", "don't like location", "location is far",
                             "commute issue", "far from office", "distance problem", 
                             "prefer indiranagar", "prefer koramangala", "prefer whitefield",
                             "congested", "traffic", "pollution", "crowded"]
        if any(p in query_lower for p in location_objection):
            return SalesIntent.OBJECTION_LOCATION
        
        possession_objection = ["need now", "need immediately", "can't wait", "urgent need",
                               "immediate possession", "want quickly", "waiting too long"]
        if any(p in query_lower for p in possession_objection):
            return SalesIntent.OBJECTION_POSSESSION
        
        uc_objection = ["don't trust", "scared of delay", "construction risk", 
                       "prefer ready", "want ready only", "ready to move only",
                       "don't want under construction", "not under construction", 
                       "delay", "delays", "scared of construction", "construction delay",
                       "not want ready", "don't want ready"]
        if any(p in query_lower for p in uc_objection):
            return SalesIntent.OBJECTION_UNDER_CONSTRUCTION
        
        # Property query patterns
        property_patterns = ["show me", "find me", "looking for", "search", "bhk",
                            "bedroom", "2bhk", "3bhk", "apartments", "flats", "property",
                            "villa", "plot", "row house"]
        if any(p in query_lower for p in property_patterns):
            return SalesIntent.PROPERTY_QUERY
            
        # Agreement/Disagreement (Moved to end)
        agreement_words = ["yes", "ok", "okay", "sure", "sounds good", "let's do it", 
                          "i agree", "that works", "fine", "alright", "go ahead", "yes please"]
        disagreement_words = ["no", "not interested", "don't want", "can't", 
                             "not possible", "don't agree", "won't work", "no thanks"]
        
        if any(query_lower.startswith(word) or query_lower == word for word in agreement_words):
            return SalesIntent.AGREEMENT
            
        if any(query_lower.startswith(word) or query_lower == word for word in disagreement_words):
            return SalesIntent.DISAGREEMENT
        
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
        
        # Use Master Prompt for dynamic generation
        from services.master_prompt import SALES_ADVISOR_SYSTEM, get_objection_prompt, get_faq_prompt
        
        # Determine specific prompt based on intent
        user_prompt = query
        if "objection" in intent.value:
            user_prompt = get_objection_prompt(query, intent.value.replace("objection_", ""))
        elif "faq" in intent.value:
            user_prompt = get_faq_prompt(query, intent.value.replace("faq_", ""))
            
        # Add context from static knowledge if available, but treating it as "Reference" not "Script"
        if additional_context:
            user_prompt += f"\n\nREFERENCE KNOWLEDGE (Use as guide, not script):\n{additional_context}"

        response = await self._call_llm(
            system_prompt=SALES_ADVISOR_SYSTEM,
            user_message=user_prompt,
            context=None, # Context is now embedded in user prompt for better flow
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
            SalesIntent.FAQ_UNDER_CONSTRUCTION: """
🏗️ **Great question! Here's why Under Construction is a smart choice:**

**Key Benefits:**
- 💰 **10-15% lower price** compared to ready-to-move properties
- 📈 **Price appreciation** as construction progresses
- 🎨 **Customization options** for interiors and layout
- 💳 **Flexible payment plans** - pay in stages, not lump sum
- 🆕 **Latest construction tech** with modern amenities

**Safety nets:**
- ✅ RERA registration ensures completion timeline
- ✅ Escrow accounts protect your money
- ✅ Reputed builders have strong track records

The wait of 2-3 years often rewards you with 20-30% appreciation!

👉 **Want me to show you some under construction projects with excellent RERA ratings?**
""",
            SalesIntent.FAQ_OTHER_LOCATION: """
📍 **Open to exploring nearby locations? Smart move!**

**Why nearby areas work better:**
- 💰 **10-20% lower prices** for same quality
- 🚗 **Same connectivity** once roads improve
- 📈 **Higher appreciation potential** in emerging areas
- 🏗️ **Better inventory** - more options to choose from

Many of our clients initially wanted Whitefield but found better value in Sarjapur, Marathahalli, or Budigere!

👉 **Shall I show you top projects in areas close to your preferred location?**
""",
        }
        
        return fallbacks.get(intent, """
I'd love to help you further! 

👉 **Would you like to schedule a quick call so I can understand your needs better?**
""")

    async def handle_query(
        self,
        query: str,
        context: Optional[ConversationContext] = None,
        session_id: Optional[str] = None
    ) -> Tuple[str, SalesIntent, bool, List[str]]:
        """
        Main entry point for handling sales queries.
        Now with Pixeltable FAQ integration and session-aware CTAs.
        
        Returns:
            (response_text, intent, should_fallback_to_rag, suggested_actions)
        """
        intent = self.classify_intent(query)
        logger.info(f"Classified sales intent: {intent.value}")
        
        # For unknown intents or property queries, fallback to RAG
        if intent in [SalesIntent.UNKNOWN, SalesIntent.PROPERTY_QUERY]:
            return "", intent, True, []
        
        
        # Try sales intelligence service for sales FAQs
        response = None
        faq_type_map = {
            SalesIntent.FAQ_BUDGET_STRETCH: "stretch_budget",
            SalesIntent.FAQ_OTHER_LOCATION: "convince_location",
            SalesIntent.FAQ_UNDER_CONSTRUCTION: "under_construction",
            SalesIntent.FAQ_FACE_TO_FACE_MEETING: "face_to_face",
            SalesIntent.FAQ_SITE_VISIT: "site_visit",
            SalesIntent.FAQ_PINCLICK_VALUE: "pinclick_value",
            
            # Map objections to handlers too
            SalesIntent.OBJECTION_BUDGET: "stretch_budget",
            SalesIntent.OBJECTION_LOCATION: "convince_location",
            SalesIntent.OBJECTION_POSSESSION: "under_construction",
            SalesIntent.OBJECTION_UNDER_CONSTRUCTION: "under_construction"
        }
        
        if intent in faq_type_map and sales_intelligence:
            faq_type = faq_type_map[intent]
            logger.info(f"Using Sales Intelligence for {faq_type}")
            response = sales_intelligence.get_faq_response(faq_type)
        
        # Fallback to GPT-4 if no response
        if not response:
            response = await self.generate_intelligent_response(query, intent, context)
        
        # Track objections in session
        if session_id and self.session_manager:
            objection_types = {
                SalesIntent.OBJECTION_BUDGET: "budget",
                SalesIntent.OBJECTION_LOCATION: "location",
                SalesIntent.OBJECTION_POSSESSION: "possession",
                SalesIntent.OBJECTION_UNDER_CONSTRUCTION: "construction"
            }
            if intent in objection_types:
                self.session_manager.record_objection(session_id, objection_types[intent])
        
        # Add session-aware CTA
        if session_id and self.session_manager and self.get_cta:
            cta_type = self.session_manager.get_next_cta(session_id)
            cta_context = self._get_cta_context(intent)
            cta_text = self.get_cta(cta_type, cta_context)
            
            # Mark CTA as suggested
            self.session_manager.mark_cta_suggested(session_id, cta_type)
            
            # Add CTA to response if not already present
            if "schedule" not in response.lower() and "meeting" not in response.lower():
                response += cta_text
        
        return response, intent, False, SUGGESTED_ACTIONS.get(intent, [])
    
    def _get_cta_context(self, intent: SalesIntent) -> str:
        """Map intent to CTA context for appropriate messaging."""
        context_map = {
            SalesIntent.FAQ_BUDGET_STRETCH: "budget",
            SalesIntent.OBJECTION_BUDGET: "budget",
            SalesIntent.FAQ_OTHER_LOCATION: "location",
            SalesIntent.OBJECTION_LOCATION: "location",
            SalesIntent.FAQ_UNDER_CONSTRUCTION: "possession",
            SalesIntent.OBJECTION_POSSESSION: "possession",
            SalesIntent.OBJECTION_UNDER_CONSTRUCTION: "possession"
        }
        return context_map.get(intent, "general")
    
    def should_handle(self, query: str) -> bool:
        """Check if this handler should process the query."""
        intent = self.classify_intent(query)
        return intent not in [SalesIntent.UNKNOWN, SalesIntent.PROPERTY_QUERY]


# Global instance
intelligent_sales = IntelligentSalesHandler()

