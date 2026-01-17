"""
Conversation Director Service
Real-time sales coaching engine that guides salesmen during live customer calls
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import re

from models.coaching_rules import (
    COACHING_RULES,
    STAGE_TRANSITIONS,
    CoachingPriority,
    CoachingType,
    get_coaching_rule,
    get_all_rules_for_stage,
    get_high_priority_rules
)

logger = logging.getLogger(__name__)


class ConversationDirector:
    """
    Analyzes conversation flow and provides real-time coaching prompts to salesmen
    """

    def __init__(self):
        self.rules = COACHING_RULES
        self.stage_transitions = STAGE_TRANSITIONS

    def detect_conversation_stage(
        self,
        session: Dict[str, Any],
        current_query: str,
        search_performed: bool = False
    ) -> str:
        """
        Detect the current conversation stage based on session history

        Stages: discovery → evaluation → negotiation → closing

        Args:
            session: Conversation session with history
            current_query: Current user query
            search_performed: Whether a property search was just performed

        Returns:
            Stage name: discovery, evaluation, negotiation, or closing
        """
        messages = session.get("messages", [])
        message_count = len(messages)

        # Extract session metrics
        projects_viewed = len(session.get("last_shown_projects", []))
        interested_projects = session.get("interested_projects", [])
        objections_raised = session.get("objections_raised", [])
        current_filters = session.get("current_filters", {})

        # CLOSING stage detection
        if any(keyword in current_query.lower() for keyword in [
            "site visit", "schedule", "book", "token", "callback", "meeting",
            "when can we meet", "arrange a visit"
        ]):
            return "closing"

        # NEGOTIATION stage detection
        if objections_raised or any(keyword in current_query.lower() for keyword in [
            "expensive", "too much", "cheaper", "discount", "price high",
            "far", "too far", "concern", "worried", "risk", "compare",
            "versus", "vs", "better than"
        ]):
            return "negotiation"

        # EVALUATION stage detection
        if projects_viewed >= 2 or any(keyword in current_query.lower() for keyword in [
            "tell me more", "more about", "amenities", "schools nearby",
            "distance", "how far", "floor plan", "carpet area", "possession",
            "more details", "more points"
        ]):
            return "evaluation"

        # DISCOVERY stage (default for early conversation)
        if message_count <= 3 or search_performed or current_filters:
            return "discovery"

        # Default to evaluation if unclear
        return "evaluation"

    def calculate_engagement_score(self, session: Dict[str, Any]) -> float:
        """
        Calculate engagement score (0-10) based on conversation metrics

        Higher score = more engaged customer

        Factors:
        - Message count
        - Projects viewed
        - Interested projects marked
        - Query depth (amenities, location questions)
        - Response time (fast = engaged)
        """
        score = 0.0

        # Message count (0-3 points)
        messages = session.get("messages", [])
        message_count = len(messages)
        score += min(3.0, message_count / 3)

        # Projects viewed (0-3 points)
        projects_viewed = len(session.get("last_shown_projects", []))
        score += min(3.0, projects_viewed / 2)

        # Interested projects (0-2 points)
        interested_count = len(session.get("interested_projects", []))
        score += min(2.0, interested_count * 1.0)

        # Deep queries (amenities, location, specifics) - 0-2 points
        recent_messages = messages[-5:] if len(messages) >= 5 else messages
        deep_query_keywords = [
            "amenities", "schools", "hospital", "metro", "airport",
            "distance", "how far", "floor plan", "carpet area", "possession",
            "rera", "price", "configuration"
        ]
        deep_query_count = sum(
            1 for msg in recent_messages
            if msg.get("role") == "user" and any(
                kw in msg.get("content", "").lower() for kw in deep_query_keywords
            )
        )
        score += min(2.0, deep_query_count / 2)

        return min(10.0, score)

    def should_trigger_action(
        self,
        rule_name: str,
        session: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Check if a coaching rule's conditions are met

        Args:
            rule_name: Name of the coaching rule
            session: Conversation session
            context: Additional context (current_query, stage, etc.)

        Returns:
            True if rule should trigger, False otherwise
        """
        rule = get_coaching_rule(rule_name)
        if not rule:
            return False

        conditions = rule.get("conditions", {})

        # Check conversation stage
        if "conversation_stage" in conditions:
            current_stage = context.get("conversation_stage", "discovery")
            if current_stage not in conditions["conversation_stage"]:
                return False

        # Check minimum projects viewed
        if "min_projects_viewed" in conditions:
            projects_viewed = len(session.get("last_shown_projects", []))
            if projects_viewed < conditions["min_projects_viewed"]:
                return False

        # Check minimum messages
        if "min_messages" in conditions:
            message_count = len(session.get("messages", []))
            if message_count < conditions["min_messages"]:
                return False

        # Check objection type
        if "objection_type" in conditions:
            objections = session.get("objections_raised", [])
            if conditions["objection_type"] not in objections:
                return False

        # Check query contains keywords
        if "query_contains" in conditions:
            current_query = context.get("current_query", "").lower()
            if not any(kw in current_query for kw in conditions["query_contains"]):
                return False

        # Check if budget alternatives were shown
        if "budget_alternatives_shown" in conditions:
            if not context.get("budget_alternatives_shown", False):
                return False

        # Check silence duration
        if "silence_duration_seconds" in conditions:
            last_message_time = context.get("last_message_time")
            if last_message_time:
                silence_seconds = (datetime.now() - last_message_time).total_seconds()
                if silence_seconds < conditions["silence_duration_seconds"]:
                    return False

        # Check query type (supports string or list of allowed types)
        if "query_type" in conditions:
            qt = conditions["query_type"]
            ctx_qt = context.get("query_type")
            if isinstance(qt, list):
                if ctx_qt not in qt:
                    return False
            else:
                if ctx_qt != qt:
                    return False

        # Check if real data was used
        if "real_data_used" in conditions:
            if not context.get("real_data_used", False):
                return False

        return True

    def get_coaching_prompt(
        self,
        session: Dict[str, Any],
        current_query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a coaching prompt for the salesman based on conversation state

        Args:
            session: Conversation session
            current_query: Current user query
            context: Additional context (projects shown, market data, etc.)

        Returns:
            Coaching prompt dict or None if no coaching needed
            {
                "type": "action_suggestion",
                "priority": "high",
                "message": "...",
                "suggested_script": "..."
            }
        """
        if context is None:
            context = {}

        # Detect conversation stage
        stage = self.detect_conversation_stage(
            session,
            current_query,
            context.get("search_performed", False)
        )
        context["conversation_stage"] = stage
        context["current_query"] = current_query

        # Calculate engagement score
        engagement_score = self.calculate_engagement_score(session)
        context["engagement_score"] = engagement_score

        # Check all rules in priority order (HIGH first)
        triggered_rule = None
        highest_priority = None

        for rule_name in get_high_priority_rules():
            if self.should_trigger_action(rule_name, session, context):
                rule = get_coaching_rule(rule_name)
                if highest_priority is None or rule["priority"].value == "high":
                    triggered_rule = rule_name
                    highest_priority = rule["priority"]
                    if highest_priority.value == "critical":
                        break  # Critical rules take immediate precedence

        # If no high priority rule, check medium/low
        if not triggered_rule:
            for rule_name, rule in COACHING_RULES.items():
                if self.should_trigger_action(rule_name, session, context):
                    triggered_rule = rule_name
                    break

        if not triggered_rule:
            return None

        # Build coaching prompt
        rule = get_coaching_rule(triggered_rule)
        return self._build_prompt_from_rule(rule, session, context)

    def _build_prompt_from_rule(
        self,
        rule: Dict[str, Any],
        session: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Build a coaching prompt from a rule template

        Fills in template variables with session/context data
        """
        message_template = rule.get("message_template", "")
        script_template = rule.get("suggested_script")

        # Build template variables
        template_vars = {
            "projects_count": len(session.get("last_shown_projects", [])),
            "messages_count": len(session.get("messages", [])),
            "budget_max": session.get("current_filters", {}).get("budget_max", 0) / 10000000,  # Convert to Cr
            "engagement_score": context.get("engagement_score", 0),
            "conversation_stage": context.get("conversation_stage", "unknown")
        }

        # Project names
        project_names = [p.get("name", "") for p in session.get("last_shown_projects", [])[:3]]
        if project_names:
            template_vars["project_names"] = ", ".join(project_names)

        # Context-specific variables
        template_vars.update(context.get("template_vars", {}))

        # Fill message template
        try:
            message = message_template.format(**template_vars)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            message = message_template

        # Fill script template
        suggested_script = None
        if script_template:
            try:
                suggested_script = script_template.format(**template_vars)
            except KeyError as e:
                logger.warning(f"Missing script template variable: {e}")
                suggested_script = script_template

        return {
            "type": rule["type"].value,
            "priority": rule["priority"].value,
            "message": message,
            "suggested_script": suggested_script
        }

    def track_objection(self, session: Dict[str, Any], query: str) -> Optional[str]:
        """
        Detect and track objections from customer query

        Returns:
            Objection type if detected, else None
        """
        query_lower = query.lower()

        # Budget objection
        if any(kw in query_lower for kw in [
            "expensive", "too much", "cheaper", "discount", "price high",
            "costly", "can't afford", "over budget"
        ]):
            if "budget" not in session.get("objections_raised", []):
                session.setdefault("objections_raised", []).append("budget")
            return "budget"

        # Location objection
        if any(kw in query_lower for kw in [
            "too far", "far from", "distance is", "location not good",
            "prefer closer"
        ]):
            if "location" not in session.get("objections_raised", []):
                session.setdefault("objections_raised", []).append("location")
            return "location"

        # Construction risk objection
        if any(kw in query_lower for kw in [
            "under construction", "not ready", "construction risk",
            "delayed", "will it complete", "safe to buy"
        ]):
            if "construction_risk" not in session.get("objections_raised", []):
                session.setdefault("objections_raised", []).append("construction_risk")
            return "construction_risk"

        return None


# Singleton instance
_director_instance = None


def get_conversation_director() -> ConversationDirector:
    """Get singleton instance of ConversationDirector"""
    global _director_instance
    if _director_instance is None:
        _director_instance = ConversationDirector()
    return _director_instance
