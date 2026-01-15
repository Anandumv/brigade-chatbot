"""
Sales Conversation Handler Service
Implements the complete sales conversation logic including:
- FAQ responses for common sales questions
- Objection handling decision trees
- Face-to-face meeting promotion
- Conversation state tracking
"""

from typing import Dict, Any, Optional, List, Tuple
from enum import Enum
from pydantic import BaseModel
import logging
import re

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
    REQUEST_CALLBACK = "request_callback"
    
    AGREEMENT = "agreement"
    DISAGREEMENT = "disagreement"
    
    UNKNOWN = "unknown"


class ConversationState(BaseModel):
    """Track conversation context for multi-turn conversations"""
    session_id: str = ""
    current_filters: Dict[str, Any] = {}
    last_intent: Optional[str] = None
    objections_raised: List[str] = []
    interested_projects: List[str] = []
    meeting_suggested: bool = False
    site_visit_suggested: bool = False
    awaiting_response: Optional[str] = None  # What we're waiting for user to respond to


# ============================================================================
# FAQ RESPONSE TEMPLATES
# ============================================================================

FAQ_RESPONSES = {
    SalesIntent.FAQ_BUDGET_STRETCH: """
**💰 Stretching Your Budget - Smart Investment Tips** 🏠

Investing a bit more often gives you:

📈 **Better location** with higher appreciation potential
🏠 **Larger carpet area** for comfortable living
✨ **Premium amenities** that add to quality of life
🏆 **Reputed developer** with proven track record

**Pro tip**: A 10-15% stretch in budget can result in 25-30% better value!

💡 *Many of our customers initially had a strict budget but found that a small stretch opened doors to significantly better options.*

👉 **Would you like me to show you options slightly above your budget that offer exceptional value?**
""",

    SalesIntent.FAQ_OTHER_LOCATION: """
**📍 Exploring New Locations - Hidden Gems** ✨

The recommended location is rapidly developing due to:

🚇 **Infrastructure boost**: Metro connectivity, flyovers, IT parks nearby
💰 **Price advantage**: 15-20% lower than established areas
📈 **Growth potential**: Expected 40-50% appreciation in 3-5 years
🏠 **Better specifications** at the same budget

🎯 *Many of our satisfied customers initially wanted a different location but are now thrilled with their decision!*

**Real Example**: A customer looking at Koramangala (₹1.5 Cr budget) found a much bigger 3BHK in Sarjapur Road at ₹1.2 Cr with better amenities.

👉 **Shall I share some success stories and show you what's available in emerging locations?**
""",

    SalesIntent.FAQ_UNDER_CONSTRUCTION: """
**🏗️ Why Under-Construction Can Be Smarter** 💡

Benefits of under-construction properties:

💰 **Price advantage**: 15-25% lower than ready properties
📅 **Payment flexibility**: Pay in installments as per construction stages
✨ **Fresh property**: Move into a brand new home, not a resale
🎨 **Customization**: Often possible to make small modifications
📈 **Appreciation**: Property value increases by possession time

🔒 **RERA Protection**: Your investment is completely secure with registered projects!

**Investment Math**:
- Ready property today: ₹1.5 Cr
- Under-construction (2027 possession): ₹1.2 Cr → Worth ₹1.6-1.8 Cr by possession

👉 **Would you like to see some excellent under-construction options with great appreciation potential?**
""",

    SalesIntent.FAQ_FACE_TO_FACE_MEETING: """
**🤝 Let's Meet & Explore Your Dream Home** 🏡

A face-to-face meeting helps us:

👤 **Understand your needs** deeply and personally
🔒 **Show exclusive inventory** not available online
💳 **Explain payment plans** and negotiate best deals
📋 **Answer all questions** in detail with documentation
🤝 **Build trust** through personal interaction

**What to expect**:
✅ Detailed project presentations
✅ Virtual/actual site tour options
✅ Personalized cost sheet
✅ Home loan assistance discussion
✅ No obligation - just exploration!

Our property experts are available at your convenience.

👉 **When would you like to schedule a meeting?** I can arrange it at our office, the project site, or even a video call!
""",

    SalesIntent.FAQ_SITE_VISIT: """
**🚗 Schedule Your Site Visit** 🏠

Experience the property firsthand:

🏗️ **See the actual construction** quality and progress
🌳 **Explore the neighborhood** and connectivity
👥 **Meet our sales team** for personalized assistance
🎁 **Get exclusive site visit offers** and priority booking

**We offer**:
✅ Free pick-up and drop from your location
✅ Complimentary refreshments
✅ On-spot booking benefits (up to ₹2-5 Lac off!)
✅ No obligation to buy

**Weekend slots fill up fast** - I recommend booking early!

👉 **When would you like to visit?** Share your preferred date/time and pickup location, and I'll arrange everything!
""",

    SalesIntent.FAQ_PINCLICK_VALUE: """
**🌟 Why Pinclick? Your Trusted Property Partner**

Pinclick adds value at every step of your home-buying journey:

🔍 **Verified listings** - All properties are personally verified
📊 **Market insights** - Data-driven price analysis & negotiation
💼 **Expert guidance** - Experienced property consultants
📋 **Documentation support** - Hassle-free paperwork
💰 **Best deals** - Exclusive discounts & offers
🤝 **Post-sale support** - We're with you till possession & beyond

**Our Track Record**:
- ✅ **500+ happy customers** this year
- ✅ **₹50 Cr+** worth of properties sold
- ✅ **4.8/5** customer satisfaction rating
- ✅ **Zero complaints** on RERA platform

💬 *"Pinclick made our home-buying journey stress-free. Their team was always available and got us a great deal!"* - Recent Customer

👉 **Would you like to speak with some of our recent customers about their experience?**
"""
}


# ============================================================================
# OBJECTION HANDLING TEMPLATES
# ============================================================================

OBJECTION_RESPONSES = {
    SalesIntent.OBJECTION_BUDGET: """
**💡 I Understand Your Budget Concerns**

However, stretching your budget slightly can offer significant long-term benefits:

1.  **Better Location**: Higher appreciation potential and better connectivity.
2.  **Quality of Life**: Access to premium amenities and larger spaces.
3.  **Future Value**: A 10% stretch today could mean 30% higher resale value later.

**Alternative**: We can also look at emerging locations where your budget gets you more space and similar amenities to your preferred area.

👉 **I strongly recommend a Face-to-Face meeting to explore these options and see the value firsthand. When works best for you?**
""",

    SalesIntent.OBJECTION_LOCATION: """
**📍 I Hear Your Location Preference**

Let me explain why we suggested the alternate location:

**Why consider it?**
- 🚇 Same metro connectivity as your preferred area
- 💰 15-20% lower price for same specifications  
- 📈 Higher appreciation potential (emerging area)
- 🏢 New IT parks/employment hubs coming up

**If you still prefer your original location, I can:**
1. Show options in a slightly higher budget
2. Find smaller configurations in same budget
3. Check resale options (may have compromises)

💡 *Many customers who initially said no to alternate locations are now our biggest advocates!*

👉 **Would you like to at least see what's available in both locations for comparison?** A site visit really helps in making this decision.
""",

    SalesIntent.OBJECTION_POSSESSION: """
**🗓️ I Understand You Want Early Possession**

However, investing in an **Under-Construction** project has distinct advantages:

1.  **Price Advantage**: You save 15-25% compared to ready-to-move properties.
2.  **Payment Flexibility**: You don't need to pay the full amount upfront.
3.  **Appreciation**: The property value grows significantly by the time you move in.

If your need is immediate, we can certainly look at ready options, but they might come at a premium or in a different location.

👉 **Let's meet to discuss your timeline and budget constraints. I can show you the best projects that fit your specific needs.**
""",

    SalesIntent.OBJECTION_UNDER_CONSTRUCTION: """
**🏗️ I Understand Your Concern About Under-Construction**

Your concerns about delays are valid, but here is how we mitigate them:

1.  **RERA Protection**: All our projects are strictly RERA registered with penalty clauses for delays.
2.  **Reputed Developers**: We only recommend builders with a 95%+ on-time delivery track record.
3.  **Construction Quality**: You can visit the site and see the progress yourself.

Investing now locks in a lower price before the inevitable appreciation at completion.

👉 **Shall we schedule a meeting to review the track record and current status of these projects?**
"""
}


# ============================================================================
# MEETING & SITE VISIT RESPONSES
# ============================================================================

MEETING_RESPONSES = {
    "schedule_meeting": """
**Excellent! Let's Schedule Your Meeting** 📅

I can arrange a meeting at:
🏢 Our office (with detailed presentations)
🏗️ Project site (see actual property)
💻 Video call (convenient if you're busy)

**Please share:**
1. Your preferred date/time
2. Meeting location preference
3. Your contact number (for confirmation)

*Our property expert will personally guide you through all options and answer every question.*

👉 **Reply with your preferences and I'll confirm immediately!**
""",

    "schedule_site_visit": """
**Great Choice! Let's Arrange Your Site Visit** 🚗

**What to expect:**
- Duration: 2-3 hours
- Free pick-up & drop from your location
- Explore model flat and actual construction
- Meet project manager
- Get exclusive site visit offers!

**Available Slots:**
📅 Weekdays: 10 AM - 6 PM
📅 Weekends: 10 AM - 5 PM

**Please share:**
1. Preferred date/time
2. Pickup location
3. Number of people visiting
4. Contact number

*Weekend slots fill up quickly - I recommend booking early!*

👉 **Reply with your details and I'll confirm your slot!**
""",

    "gentle_meeting_push": """
**💡 A Quick Suggestion**

I've shared quite a bit of information here. This decision is important and deserves a proper discussion.

**A quick 30-minute call or meeting would help:**
✅ Understand your priorities better
✅ Show you the best matching options
✅ Answer questions in real-time
✅ Get you exclusive deals

*No pressure, no obligation - just an informed discussion!*

👉 **When would be a good time for a quick call?** Even 15-20 minutes would help!
"""
}
# ============================================================================
# SUGGESTED ACTIONS (Dynamic Chips)
# ============================================================================

SUGGESTED_ACTIONS = {
    SalesIntent.FAQ_BUDGET_STRETCH: ["Show slightly higher options", "Stick to my budget"],
    SalesIntent.FAQ_OTHER_LOCATION: ["Show nearby areas", "Why this location?", "Stick to my location"],
    SalesIntent.FAQ_UNDER_CONSTRUCTION: ["Show RERA details", "Show ready options", "Explain payment plan"],
    SalesIntent.FAQ_FACE_TO_FACE_MEETING: ["Schedule Meeting", "Video Call", "Not now"],
    SalesIntent.FAQ_SITE_VISIT: ["Schedule Visit", "Send Location", "Not now"],
    SalesIntent.FAQ_PINCLICK_VALUE: ["Show Customer Reviews", "Talk to an Expert"],
    
    SalesIntent.OBJECTION_BUDGET: ["Show slightly higher", "Show smaller units", "Stick to budget"],
    SalesIntent.OBJECTION_LOCATION: ["Show nearby options", "Why is this better?", "Stick to my location"],
    SalesIntent.OBJECTION_POSSESSION: ["Show ready to move", "Explain benefits", "Stick to timeline"],
    SalesIntent.OBJECTION_UNDER_CONSTRUCTION: ["Show RERA Proof", "Show Ready Options"],
    
    SalesIntent.REQUEST_MEETING: ["Book for Tomorrow", "Book for Weekend", "Call me instead"],
    SalesIntent.REQUEST_SITE_VISIT: ["Book for Tomorrow", "Book for Weekend", "Send details"],
    "meeting_push": ["Schedule 15min Call", "Chat is fine"]
}


# ============================================================================
# SALES CONVERSATION HANDLER
# ============================================================================

class SalesConversationHandler:
    """
    Handles sales-specific conversations including:
    - FAQ responses
    - Objection handling
    - Meeting/site visit scheduling
    - Conversation state management
    """
    
    def __init__(self):
        self.faq_keywords = self._build_faq_keywords()
        self.objection_keywords = self._build_objection_keywords()
        
    def _build_faq_keywords(self) -> Dict[SalesIntent, List[str]]:
        """Build keyword patterns for FAQ detection"""
        return {
            SalesIntent.FAQ_BUDGET_STRETCH: [
                "stretch budget", "stretch my budget", "increase budget",
                "how to afford", "can't afford", "out of budget",
                "budget is tight", "exceed budget", "over budget",
                "how to stretch", "extend budget"
            ],
            SalesIntent.FAQ_OTHER_LOCATION: [
                "other location", "different location", "alternate location",
                "convince for location", "change location", "why this location",
                "prefer different area", "not this area", "another area",
                "different area", "location change"
            ],
            SalesIntent.FAQ_UNDER_CONSTRUCTION: [
                "construction project", "ongoing project", "not completed",
            ],
            SalesIntent.FAQ_FACE_TO_FACE_MEETING: [
                "face to face", "meet in person", "personal meeting",
                "want to meet", "can we meet", "schedule meeting",
                "arrange meeting", "book meeting", "meeting importance",
                "why meet", "need to meet"
            ],
            SalesIntent.FAQ_SITE_VISIT: [
                "site visit", "visit site", "see property", "see the flat",
                "visit project", "see in person", "physical visit",
                "schedule visit", "arrange visit", "want to visit",
                "can I visit", "show me property"
            ],
            SalesIntent.FAQ_PINCLICK_VALUE: [
                "why pinclick", "pinclick value", "what does pinclick do",
                "pinclick benefit", "pinclick advantage", "why use pinclick",
                "how does pinclick help", "pinclick services", "about pinclick",
                "pinclick offer", "trust pinclick"
            ]
        }
    
    def _build_objection_keywords(self) -> Dict[SalesIntent, List[str]]:
        """Build keyword patterns for objection detection"""
        return {
            SalesIntent.OBJECTION_BUDGET: [
                "too expensive", "can't afford", "cannot afford", "out of my budget",
                "very costly", "high price", "beyond budget", "over my budget",
                "budget is less", "can't pay", "cannot pay", "not in budget",
                "price is high", "expensive", "costly", "unaffordable",
                "out of budget", "exceeds budget", "beyond my budget", "price too high"
            ],
            SalesIntent.OBJECTION_LOCATION: [
                "don't like this area", "prefer other area", "wrong location",
                "too far", "not convenient", "location issue", "far away",
                "want different location", "area is not good", "location is bad",
                "far from office", "far from work", "commute issue", "long commute",
                "distance is too much", "too far from"
            ],
            SalesIntent.OBJECTION_POSSESSION: [
                "need immediate", "can't wait", "cannot wait", "want now",
                "need quickly", "urgent requirement", "waiting too long",
                "2027 is too far", "2028 is too far", "possession too late", 
                "need sooner", "can't wait till", "cannot wait till", 
                "immediate need", "need immediately", "urgently need",
                "possession is too late", "too long to wait"
            ],
            SalesIntent.OBJECTION_UNDER_CONSTRUCTION: [
                "don't trust construction", "scared of delays", "fear of delay",
                "what if delayed", "construction risk", "not comfortable with construction",
                "want ready made", "ready only", "want only ready",
                "no under construction", "completed only", "only completed",
                "risks of under construction", "worry about delays", "concerned about delays"
            ]
        }
    
    def classify_sales_intent(self, query: str) -> SalesIntent:
        """
        Classify query into sales-specific intent categories.
        
        Returns:
            SalesIntent enum value
        """
        query_lower = query.lower().strip()
        
        # Check for agreement/disagreement (for multi-turn context)
        agreement_words = ["yes", "ok", "okay", "sure", "sounds good", "let's do it", 
                          "i agree", "that works", "fine", "alright", "go ahead"]
        disagreement_words = ["no", "not interested", "don't want", "can't", 
                             "not possible", "don't agree", "won't work"]
        
        if any(word in query_lower for word in agreement_words) and len(query_lower) < 50:
            return SalesIntent.AGREEMENT
            
        if any(word in query_lower for word in disagreement_words) and len(query_lower) < 50:
            return SalesIntent.DISAGREEMENT
        
        # Check for meeting/visit requests
        meeting_phrases = [
            "schedule meeting", "book meeting", "arrange meeting",
            "schedule a meeting", "book a meeting", "arrange a meeting",
            "set up meeting", "set up a meeting", "want to meet",
            "can we meet", "let's meet", "meeting with you"
        ]
        if any(phrase in query_lower for phrase in meeting_phrases):
            return SalesIntent.REQUEST_MEETING
        
        visit_phrases = [
            "schedule visit", "book visit", "arrange visit",
            "schedule a visit", "book a visit", "arrange a visit",
            "set up visit", "set up a visit", "want to visit"
        ]
        if any(phrase in query_lower for phrase in visit_phrases):
            return SalesIntent.REQUEST_SITE_VISIT
        
        # Check FAQ keywords
        for intent, keywords in self.faq_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return intent
        
        # Check objection keywords
        for intent, keywords in self.objection_keywords.items():
            if any(kw in query_lower for kw in keywords):
                return intent
        
        return SalesIntent.UNKNOWN
    
    def handle_sales_query(
        self,
        query: str,
        state: Optional[ConversationState] = None
    ) -> Tuple[str, SalesIntent, bool, List[str]]:
        """
        Process sales-specific query and return appropriate response.
        
        Args:
            query: User's query
            state: Current conversation state (optional)
            
        Returns:
            (response_text, intent, should_fallback_to_rag, suggested_actions)
        """
        intent = self.classify_sales_intent(query)
        
        logger.info(f"Sales intent classified: {intent.value} for query: {query[:50]}...")
        
        actions = SUGGESTED_ACTIONS.get(intent, [])
        
        # Handle FAQ intents
        if intent in FAQ_RESPONSES:
            return FAQ_RESPONSES[intent], intent, False, actions
        
        # Handle objection intents
        if intent in OBJECTION_RESPONSES:
            return OBJECTION_RESPONSES[intent], intent, False, actions
        
        # Handle meeting/visit requests
        if intent == SalesIntent.REQUEST_MEETING:
            return MEETING_RESPONSES["schedule_meeting"], intent, False, actions
            
        if intent == SalesIntent.REQUEST_SITE_VISIT:
            return MEETING_RESPONSES["schedule_site_visit"], intent, False, actions
        
        # Handle agreement - suggest meeting
        if intent == SalesIntent.AGREEMENT:
            if state and state.awaiting_response:
                # Context-aware response based on what we're waiting for
                if "meeting" in state.awaiting_response.lower():
                    return MEETING_RESPONSES["schedule_meeting"], intent, False, SUGGESTED_ACTIONS.get(SalesIntent.REQUEST_MEETING, [])
                elif "visit" in state.awaiting_response.lower():
                    return MEETING_RESPONSES["schedule_site_visit"], intent, False, SUGGESTED_ACTIONS.get(SalesIntent.REQUEST_SITE_VISIT, [])
            # Default agreement response - push for meeting
            return MEETING_RESPONSES["gentle_meeting_push"], intent, False, SUGGESTED_ACTIONS.get("meeting_push", [])
        
        # Unknown intent - fallback to RAG/GPT
        return "", intent, True, []
    
    def should_handle(self, query: str) -> bool:
        """
        Check if this query should be handled by sales conversation handler.
        
        Returns:
            True if sales handler should process this query
        """
        intent = self.classify_sales_intent(query)
        return intent != SalesIntent.UNKNOWN
    
    def get_meeting_cta(self, context: str = "general") -> str:
        """
        Get appropriate call-to-action for scheduling meeting.
        
        Args:
            context: Context for CTA (budget, location, possession, general)
            
        Returns:
            CTA text to append to response
        """
        cta_templates = {
            "budget": "\n\n💡 *A quick meeting would help us find the perfect option within your budget. When works for you?*",
            "location": "\n\n💡 *A site visit would help you experience the location firsthand. Shall we arrange one?*",
            "possession": "\n\n💡 *Let's discuss your timeline in detail to find the best match. Can we schedule a call?*",
            "general": "\n\n💡 *Would you like to schedule a meeting to explore these options in detail?*"
        }
        return cta_templates.get(context, cta_templates["general"])


# ============================================================================
# FILTER OPTIONS (For dropdown menus)
# ============================================================================

FILTER_OPTIONS = {
    "configurations": [
        {"value": "1", "label": "1 BHK"},
        {"value": "2", "label": "2 BHK"},
        {"value": "2.5", "label": "2.5 BHK"},
        {"value": "3", "label": "3 BHK"},
        {"value": "3.5", "label": "3.5 BHK"},
        {"value": "4", "label": "4 BHK"},
        {"value": "plots", "label": "Plots"},
        {"value": "villa", "label": "Villa"},
    ],
    "locations": {
        "east_bangalore": {
            "label": "East Bangalore",
            "areas": [
                {"value": "whitefield", "label": "Whitefield"},
                {"value": "budigere_cross", "label": "Budigere Cross"},
                {"value": "varthur", "label": "Varthur"},
                {"value": "gunjur", "label": "Gunjur"},
                {"value": "sarjapur_road", "label": "Sarjapur Road"},
                {"value": "panathur_road", "label": "Panathur Road"},
                {"value": "kadugodi", "label": "Kadugodi"},
            ]
        },
        "north_bangalore": {
            "label": "North Bangalore",
            "areas": [
                {"value": "thanisandra", "label": "Thanisandra"},
                {"value": "jakkur", "label": "Jakkur"},
                {"value": "baglur", "label": "Baglur"},
                {"value": "yelahanka", "label": "Yelahanka"},
                {"value": "devanahalli", "label": "Devanahalli"},
            ]
        }
    },
    "budget_ranges": [
        {"value": "50L-1.2CR", "label": "₹50 Lac - ₹1.2 Cr", "min": 5000000, "max": 12000000},
        {"value": "1.2CR-1.5CR", "label": "₹1.2 Cr - ₹1.5 Cr", "min": 12000000, "max": 15000000},
        {"value": "1.5CR-1.8CR", "label": "₹1.5 Cr - ₹1.8 Cr", "min": 15000000, "max": 18000000},
        {"value": "1.8CR-2.0CR", "label": "₹1.8 Cr - ₹2.0 Cr", "min": 18000000, "max": 20000000},
        {"value": "2.0CR-2.5CR", "label": "₹2.0 Cr - ₹2.5 Cr", "min": 20000000, "max": 25000000},
        {"value": "2.5CR-3.0CR", "label": "₹2.5 Cr - ₹3.0 Cr", "min": 25000000, "max": 30000000},
        {"value": "3.0CR-4.0CR", "label": "₹3.0 Cr - ₹4.0 Cr", "min": 30000000, "max": 40000000},
        {"value": "4.0CR-5.0CR", "label": "₹4.0 Cr - ₹5.0 Cr", "min": 40000000, "max": 50000000},
        {"value": "ABOVE-5CR", "label": "Above ₹5 Cr", "min": 50000000, "max": None},
    ],
    "possession_years": [
        {"value": "READY", "label": "RTMI Ready To Move In"},
        {"value": "2024", "label": "2024"},
        {"value": "2027", "label": "2027"},
        {"value": "2028", "label": "2028"},
        {"value": "2029", "label": "2029"},
        {"value": "2030", "label": "2030"},
    ]
}


def get_filter_options() -> Dict[str, Any]:
    """Get all filter options for frontend dropdowns"""
    return FILTER_OPTIONS


# Global instance
sales_conversation = SalesConversationHandler()
