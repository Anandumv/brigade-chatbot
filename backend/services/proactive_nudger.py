"""
Proactive Nudger Service
Detects patterns in user behavior and generates smart nudges at optimal moments

Pattern Types:
- Repeat views (same project viewed 3+ times)
- Location focus (keeps searching same location)
- Budget concerns (multiple budget objections)
- Long session (engaged for 15+ minutes)
- Abandoned interest (viewed but didn't schedule)
- Price sensitivity (always asks about cheaper options)
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class ProactiveNudger:
    """
    Detect user behavior patterns and generate proactive nudges
    
    Features:
    - Pattern detection (repeat views, location focus, etc.)
    - Smart timing (don't overwhelm user)
    - Contextual nudges (relevant to current behavior)
    - Nudge history tracking (avoid repetition)
    """
    
    def __init__(self):
        self.nudge_cooldown_minutes = 10  # Don't nudge more than once per 10 min
    
    def detect_patterns_and_nudge(
        self,
        user_profile: Optional[Any],
        session: Any,
        current_query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze user behavior and generate proactive nudge if appropriate
        
        Args:
            user_profile: UserProfile object (or None if no profile)
            session: ConversationSession object
            current_query: Current user query
        
        Returns:
            Dict with nudge details or None if no nudge needed
            {
                "type": "repeat_views" | "location_focus" | "budget_concern" | ...,
                "message": "Nudge message to show",
                "action": "schedule_visit" | "show_alternatives" | "take_break" | ...,
                "priority": "high" | "medium" | "low"
            }
        """
        # Check if we should nudge (cooldown)
        if not self._should_nudge_now(session):
            return None
        
        # Try different pattern detections in priority order
        nudge = None
        
        # HIGH PRIORITY: Repeat views (strong buying signal)
        if not nudge and user_profile:
            nudge = self._detect_repeat_views(user_profile, session)
        
        # HIGH PRIORITY: Ready to decide (viewed 5+ properties)
        if not nudge and user_profile:
            nudge = self._detect_decision_readiness(user_profile, session)
        
        # MEDIUM PRIORITY: Location focus (optimization opportunity)
        if not nudge and session:
            nudge = self._detect_location_focus(session)
        
        # MEDIUM PRIORITY: Budget concerns (need alternatives)
        if not nudge and session:
            nudge = self._detect_budget_concerns(session)
        
        # LOW PRIORITY: Long session (offer break)
        if not nudge and session:
            nudge = self._detect_long_session(session)
        
        # LOW PRIORITY: Abandoned interest (follow up)
        if not nudge and user_profile:
            nudge = self._detect_abandoned_interest(user_profile, session)
        
        if nudge:
            self._track_nudge_shown(session, nudge["type"])
            logger.info(f"🎯 PROACTIVE NUDGE: {nudge['type']} (priority: {nudge['priority']})")
        
        return nudge
    
    def _should_nudge_now(self, session: Any) -> bool:
        """
        Check if enough time has passed since last nudge
        
        Args:
            session: ConversationSession object
        
        Returns:
            True if we can nudge, False if in cooldown
        """
        if not hasattr(session, 'last_nudge_time'):
            return True
        
        if not session.last_nudge_time:
            return True
        
        # Check cooldown
        time_since_last = datetime.now() - session.last_nudge_time
        return time_since_last.total_seconds() > (self.nudge_cooldown_minutes * 60)
    
    def _track_nudge_shown(self, session: Any, nudge_type: str) -> None:
        """Track that a nudge was shown"""
        if not hasattr(session, 'last_nudge_time'):
            session.last_nudge_time = None
        if not hasattr(session, 'nudges_shown'):
            session.nudges_shown = []
        
        session.last_nudge_time = datetime.now()
        session.nudges_shown.append({
            "type": nudge_type,
            "timestamp": datetime.now().isoformat()
        })
    
    # ========================================
    # PATTERN DETECTION METHODS
    # ========================================
    
    def _detect_repeat_views(
        self,
        user_profile: Any,
        session: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user keeps viewing the same project (3+ times)
        
        Strong buying signal - suggest site visit
        """
        if not hasattr(user_profile, 'properties_viewed'):
            return None
        
        # Find most viewed property
        max_views = 0
        most_viewed = None
        
        for prop in user_profile.properties_viewed:
            view_count = prop.get("view_count", 0)
            if view_count > max_views:
                max_views = view_count
                most_viewed = prop
        
        # Threshold: 3+ views
        if max_views >= 3:
            project_name = most_viewed.get("name", "this property")
            
            return {
                "type": "repeat_views",
                "message": f"🎯 **I notice you keep coming back to {project_name}** - "
                          f"you've viewed it {max_views} times! It's clearly on your mind. "
                          f"Would you like to **schedule a site visit this weekend** to see it in person? "
                          f"I can connect you with our Relationship Manager right away!",
                "action": "schedule_visit",
                "priority": "high",
                "project_name": project_name,
                "view_count": max_views
            }
        
        return None
    
    def _detect_decision_readiness(
        self,
        user_profile: Any,
        session: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user has viewed enough properties to make a decision (5+)
        
        Suggest narrowing down or scheduling visits
        """
        if not hasattr(user_profile, 'properties_viewed'):
            return None
        
        viewed_count = len(user_profile.properties_viewed)
        
        # Threshold: 5+ properties viewed
        if viewed_count >= 5:
            # Check if any are marked as interested
            interested_count = len(user_profile.interested_projects) if hasattr(user_profile, 'interested_projects') else 0
            
            if interested_count >= 2:
                # Multiple interests - suggest comparison
                return {
                    "type": "decision_readiness",
                    "message": f"💡 **You've explored {viewed_count} properties and seem interested in {interested_count} of them!** "
                              f"Would you like me to create a detailed comparison to help you decide? "
                              f"I can highlight the pros and cons of each based on your priorities.",
                    "action": "compare_properties",
                    "priority": "high"
                }
            else:
                # Many views, no clear favorite - help narrow down
                return {
                    "type": "decision_readiness",
                    "message": f"🤔 **You've viewed {viewed_count} properties** - that's great research! "
                              f"Would you like me to help you narrow it down? I can focus on your top priorities "
                              f"(budget, location, amenities) to find the perfect match.",
                    "action": "narrow_down",
                    "priority": "medium"
                }
        
        return None
    
    def _detect_location_focus(self, session: Any) -> Optional[Dict[str, Any]]:
        """
        Detect if user keeps asking about the same location
        
        Suggest exploring nearby areas for better value
        """
        if not hasattr(session, 'current_filters'):
            return None
        
        # Check how many times same location was queried
        location_mentions = 0
        focused_location = None
        
        if session.current_filters.get('location'):
            focused_location = session.current_filters['location']
            
            # Count mentions in message history
            if hasattr(session, 'messages'):
                for msg in session.messages[-10:]:  # Last 10 messages
                    content = msg.get('content', '').lower()
                    if focused_location.lower() in content:
                        location_mentions += 1
        
        # Threshold: 3+ mentions of same location
        if location_mentions >= 3 and focused_location:
            return {
                "type": "location_focus",
                "message": f"🗺️ **I notice you're really focused on {focused_location}!** "
                          f"That's a great area. Would you also like to explore nearby localities? "
                          f"Sometimes areas 3-5km away offer similar amenities at 15-20% lower prices "
                          f"with higher appreciation potential. Want to see some options?",
                "action": "show_nearby_areas",
                "priority": "medium",
                "location": focused_location
            }
        
        return None
    
    def _detect_budget_concerns(self, session: Any) -> Optional[Dict[str, Any]]:
        """
        Detect if user has raised budget objections multiple times
        
        Suggest financing options or cheaper alternatives
        """
        if not hasattr(session, 'objection_count'):
            return None
        
        objection_count = session.objection_count
        
        # Threshold: 2+ objections in session
        if objection_count >= 2:
            return {
                "type": "budget_concern",
                "message": f"💰 **I understand budget is a key concern for you.** "
                          f"Would it help if I showed you:\n"
                          f"1. **Flexible payment plans** (construction-linked, subvention schemes)\n"
                          f"2. **Upcoming projects** in emerging areas (better prices, high growth)\n"
                          f"3. **Slightly smaller units** that fit your budget perfectly\n\n"
                          f"Which would you prefer?",
                "action": "show_budget_options",
                "priority": "medium"
            }
        
        return None
    
    def _detect_long_session(self, session: Any) -> Optional[Dict[str, Any]]:
        """
        Detect if user has been in session for 15+ minutes
        
        Suggest taking a break or emailing details
        """
        if not hasattr(session, 'messages') or len(session.messages) < 10:
            return None
        
        # Check session duration (first message to now)
        if session.messages:
            first_msg = session.messages[0]
            if 'timestamp' in first_msg:
                first_time = datetime.fromisoformat(first_msg['timestamp'])
                duration_minutes = (datetime.now() - first_time).total_seconds() / 60
                
                # Threshold: 15+ minutes
                if duration_minutes >= 15:
                    return {
                        "type": "long_session",
                        "message": f"⏰ **You've been exploring for {int(duration_minutes)} minutes** - "
                                  f"that's great engagement! Would you like me to:\n"
                                  f"1. **Email you a summary** of all properties we discussed\n"
                                  f"2. **Schedule a callback** with our expert for a detailed discussion\n"
                                  f"3. **Continue exploring** - I'm here as long as you need!\n\n"
                                  f"What works best for you?",
                        "action": "offer_break",
                        "priority": "low"
                    }
        
        return None
    
    def _detect_abandoned_interest(
        self,
        user_profile: Any,
        session: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if user showed interest but didn't schedule visit
        
        Suggest following up (only for users with multiple sessions)
        """
        if not hasattr(user_profile, 'interested_projects'):
            return None
        
        if not hasattr(user_profile, 'site_visits_scheduled'):
            return None
        
        # Only trigger for returning users (2+ sessions)
        total_sessions = getattr(user_profile, 'total_sessions', 0)
        if total_sessions < 2:
            return None
        
        # Check if interested but no site visits
        interested_count = len(user_profile.interested_projects)
        site_visits = user_profile.site_visits_scheduled
        
        if interested_count >= 1 and site_visits == 0:
            project_name = user_profile.interested_projects[0].get('name', 'these properties')
            
            return {
                "type": "abandoned_interest",
                "message": f"👋 **Welcome back!** I see you were interested in {project_name} last time. "
                          f"Have you had a chance to think about it? "
                          f"Would you like to schedule a site visit or learn more about the project?",
                "action": "follow_up",
                "priority": "low",
                "project_name": project_name
            }
        
        return None


# Singleton instance
_nudger_instance = None


def get_proactive_nudger() -> ProactiveNudger:
    """Get singleton instance of ProactiveNudger"""
    global _nudger_instance
    if _nudger_instance is None:
        _nudger_instance = ProactiveNudger()
    return _nudger_instance
