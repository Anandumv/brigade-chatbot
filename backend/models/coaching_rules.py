"""
Coaching Rules Configuration
Defines trigger conditions and prompt templates for real-time sales coaching
"""

from typing import Dict, List, Any
from enum import Enum


class CoachingPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CoachingType(Enum):
    ACTION_SUGGESTION = "action_suggestion"
    OBJECTION_HANDLING = "objection_handled"
    QUALIFICATION_OPPORTUNITY = "qualification_opportunity"
    UPSELL_OPPORTUNITY = "upsell_opportunity"
    INFO_PROVIDED = "info_provided"
    CONVERSION_TRIGGER = "conversion_trigger"


# Coaching rule definitions
COACHING_RULES: Dict[str, Dict[str, Any]] = {
    # CONVERSION TRIGGERS - High priority actions to close the sale
    "site_visit_trigger": {
        "conditions": {
            "min_projects_viewed": 2,
            "min_messages": 3,
            "conversation_stage": ["evaluation", "negotiation"]
        },
        "priority": CoachingPriority.HIGH,
        "type": CoachingType.CONVERSION_TRIGGER,
        "message_template": "💡 CONVERSION TRIGGER: Customer has viewed {projects_count} projects and asking detailed questions. High engagement detected ({messages_count} messages). TIME TO CLOSE - Suggest site visit NOW.",
        "suggested_script": "I can see you're really interested in {project_names}! The best way to experience these properties is in person. How about we schedule a site visit this weekend? I can arrange for all properties on the same day. Saturday or Sunday - which works better for you?"
    },

    "callback_trigger": {
        "conditions": {
            "min_messages": 4,
            "min_projects_viewed": 2,
            "conversation_stage": ["evaluation", "negotiation", "closing"]
        },
        "priority": CoachingPriority.HIGH,
        "type": CoachingType.CONVERSION_TRIGGER,
        "message_template": "💡 Customer is highly engaged ({messages_count} messages). Time to offer a callback with your relationship manager for detailed discussion.",
        "suggested_script": "I'd love to connect you with our relationship manager who can provide detailed information about financing options and answer any specific questions. Would you prefer a call back today evening or tomorrow morning?"
    },

    # OBJECTION HANDLING - React to customer concerns
    "budget_objection": {
        "conditions": {
            "objection_type": "budget",
            "conversation_stage": ["negotiation", "closing"]
        },
        "priority": CoachingPriority.HIGH,
        "type": CoachingType.OBJECTION_HANDLING,
        "message_template": "💡 Budget objection detected. {market_data_provided}. Now ask: 'Given the value and limited availability, would you like to block this unit with a token amount?'",
        "suggested_script": "I can see this is a great fit for your needs. {urgency_context} Would you like to secure this with a booking amount today? We can arrange a site visit for this weekend."
    },

    "location_objection": {
        "conditions": {
            "objection_type": "location",
            "conversation_stage": ["negotiation"]
        },
        "priority": CoachingPriority.MEDIUM,
        "type": CoachingType.OBJECTION_HANDLING,
        "message_template": "💡 Location concern raised. Emphasize connectivity, upcoming infrastructure, and appreciation potential.",
        "suggested_script": "While {location} might seem far, it's actually well-connected with {connectivity_info}. Plus, this area has shown {appreciation_rate}% appreciation over the last 5 years. Many of our clients initially had the same concern but are now happy with their decision!"
    },

    "construction_risk_objection": {
        "conditions": {
            "objection_type": "construction_risk",
            "conversation_stage": ["negotiation"]
        },
        "priority": CoachingPriority.MEDIUM,
        "type": CoachingType.OBJECTION_HANDLING,
        "message_template": "💡 Construction risk concern. Highlight RERA protection, builder track record, and price advantage.",
        "suggested_script": "That's a great question! This project is RERA registered ({rera_number}), which provides legal protection. {developer_name} has a strong delivery track record. Plus, you save {savings_percentage}% by buying during construction versus ready-to-move."
    },

    # QUALIFICATION OPPORTUNITIES - Learn more about customer
    "schools_query_qualification": {
        "conditions": {
            "query_contains": ["school", "education", "kids"],
            "conversation_stage": ["discovery", "evaluation"]
        },
        "priority": CoachingPriority.MEDIUM,
        "type": CoachingType.QUALIFICATION_OPPORTUNITY,
        "message_template": "💡 Customer asking about schools = likely has children. Ask: 'Do you have kids? What grades are they in?' to personalize the pitch.",
        "suggested_script": "I can see education is important to you! May I ask - do you have children? What grades are they in? I can share more about the schools that would be perfect for them."
    },

    "investment_query_qualification": {
        "conditions": {
            "query_contains": ["investment", "ROI", "appreciation", "returns"],
            "conversation_stage": ["discovery", "evaluation"]
        },
        "priority": CoachingPriority.MEDIUM,
        "type": CoachingType.QUALIFICATION_OPPORTUNITY,
        "message_template": "💡 Customer asking about investment/ROI = likely an investor. Ask: 'Are you looking for rental income or capital appreciation?' to tailor recommendations.",
        "suggested_script": "Great question! Are you planning to stay in this property yourself, or is this primarily an investment? Understanding this will help me suggest the best options for your goals."
    },

    # UPSELL OPPORTUNITIES - When to pitch premium options
    "budget_upsell": {
        "conditions": {
            "budget_alternatives_shown": True,
            "conversation_stage": ["evaluation", "negotiation"]
        },
        "priority": CoachingPriority.MEDIUM,
        "type": CoachingType.UPSELL_OPPORTUNITY,
        "message_template": "💡 Customer budget is ₹{budget_max} Cr. ₹{premium_price} Cr option offers excellent value - emphasize only ₹{emi_difference}/month more for significantly better lifestyle.",
        "suggested_script": "While these projects fit your budget perfectly, I'd also like to show you this option at ₹{premium_price} Cr. For just ₹{price_difference} lakhs more, you get {benefits}. The EMI difference is only ₹{emi_difference}/month. Would you like to see this as well?"
    },

    "configuration_upsell": {
        "conditions": {
            "query_contains": ["2BHK", "2 BHK"],
            "has_3bhk_options": True,
            "conversation_stage": ["evaluation"]
        },
        "priority": CoachingPriority.LOW,
        "type": CoachingType.UPSELL_OPPORTUNITY,
        "message_template": "💡 Customer searching for 2BHK. Mention 3BHK options if budget allows - extra space for home office/future needs.",
        "suggested_script": "I've shown you some great 2BHK options. We also have 3BHK units that many families find valuable for a home office or future needs. Would you like to see those as well, even if they're slightly above your current budget?"
    },

    # INFO PROVIDED - Low priority confirmations
    "distance_info_provided": {
        "conditions": {
            "query_type": ["location_distance", "project_details", "more_info_request"],
            "real_data_used": True
        },
        "priority": CoachingPriority.LOW,
        "type": CoachingType.INFO_PROVIDED,
        "message_template": "✓ Provided accurate distance data. If customer asks about commute, emphasize excellent highway connectivity.",
        "suggested_script": None  # No script needed for low priority info
    },

    "amenities_info_provided": {
        "conditions": {
            "query_type": ["amenities", "project_details", "more_info_request"],
            "real_data_used": True
        },
        "priority": CoachingPriority.LOW,
        "type": CoachingType.INFO_PROVIDED,
        "message_template": "✓ Provided real amenities data with distances. Good foundation for qualification questions.",
        "suggested_script": None
    },

    # FALLBACK - Low priority tip when nothing else triggers
    "general_conversation_tip": {
        "conditions": {
            "min_messages": 1,
            "real_data_used": True
        },
        "priority": CoachingPriority.LOW,
        "type": CoachingType.INFO_PROVIDED,
        "message_template": "✓ Use **bold** for project names and prices. Suggest **site visit** or **brochure** when relevant.",
        "suggested_script": None
    },

    # SILENCE/INACTIVITY - Re-engagement
    "silence_detected": {
        "conditions": {
            "silence_duration_seconds": 120,  # 2 minutes
            "conversation_stage": ["evaluation", "negotiation"]
        },
        "priority": CoachingPriority.MEDIUM,
        "type": CoachingType.ACTION_SUGGESTION,
        "message_template": "💡 Customer silent for 2 minutes. Ask: 'Any specific concerns?' or 'Would you like me to clarify anything?'",
        "suggested_script": "I notice I haven't heard from you in a bit. Do you have any specific concerns or questions I can help address? I'm here to help!"
    }
}


# Conversation stage transition rules
STAGE_TRANSITIONS: Dict[str, List[str]] = {
    "discovery": {
        "next_stages": ["evaluation"],
        "triggers": [
            "Requirements captured (BHK, budget, location)",
            "First project search performed"
        ]
    },
    "evaluation": {
        "next_stages": ["negotiation", "closing"],
        "triggers": [
            "3+ projects viewed",
            "Detailed questions about specific projects",
            "Amenities/location queries"
        ]
    },
    "negotiation": {
        "next_stages": ["closing", "evaluation"],
        "triggers": [
            "Objections raised (budget, location, construction risk)",
            "Comparison between projects",
            "Payment/financing questions"
        ]
    },
    "closing": {
        "next_stages": ["won", "lost"],
        "triggers": [
            "Site visit scheduled",
            "Callback requested",
            "Token payment discussed"
        ]
    }
}


def get_coaching_rule(rule_name: str) -> Dict[str, Any]:
    """Get a specific coaching rule by name"""
    return COACHING_RULES.get(rule_name, {})


def get_all_rules_for_stage(stage: str) -> List[Dict[str, Any]]:
    """Get all applicable coaching rules for a conversation stage"""
    applicable_rules = []
    for rule_name, rule in COACHING_RULES.items():
        conditions = rule.get("conditions", {})
        if "conversation_stage" in conditions:
            if stage in conditions["conversation_stage"]:
                applicable_rules.append({
                    "name": rule_name,
                    **rule
                })
    return applicable_rules


def get_high_priority_rules() -> List[str]:
    """Get names of all high/critical priority rules"""
    return [
        name for name, rule in COACHING_RULES.items()
        if rule["priority"] in [CoachingPriority.HIGH, CoachingPriority.CRITICAL]
    ]
