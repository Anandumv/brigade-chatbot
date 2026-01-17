"""
Session Manager for Conversation State Persistence
Tracks conversation history, objections, and interested projects per session.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)


class ConversationSession(BaseModel):
    """Model for tracking conversation state."""
    session_id: str
    created_at: datetime = datetime.now()
    last_activity: datetime = datetime.now()
    
    # Conversation tracking
    messages: List[Dict[str, str]] = []
    current_filters: Dict[str, Any] = {}
    
    # Sales flow tracking
    objections_raised: List[str] = []
    interested_projects: List[str] = []
    
    # CTA tracking
    meeting_suggested: bool = False
    site_visit_suggested: bool = False
    callback_suggested: bool = False
    
    # Discussion tracking
    budget_discussed: bool = False
    location_discussed: bool = False
    possession_discussed: bool = False
    
    # Lead scoring
    engagement_score: int = 0  # Increases with each meaningful interaction

    # Flow Engine State (Strict Agent Mode)
    flow_state: Optional[Dict[str, Any]] = None

    # Context Tracking - Enhanced for continuous conversation
    last_intent: Optional[str] = None  # To contextually handle "show more" etc.
    last_topic: Optional[str] = None  # Last discussed topic (sustainability, investment, etc.)
    last_shown_projects: List[Dict[str, Any]] = []  # Recently shown projects with details
    conversation_phase: str = "discovery"  # discovery, evaluation, negotiation, closing

    # ENHANCED: Conversation coaching metrics
    objection_count: int = 0  # Number of objections raised
    coaching_prompts_shown: List[str] = []  # History of coaching prompts shown
    last_message_time: Optional[datetime] = None  # For silence detection
    projects_viewed_count: int = 0  # Cumulative count of unique projects viewed
    
    # 🆕 SENTIMENT TRACKING
    last_sentiment: str = "neutral"  # Last detected sentiment
    last_frustration_level: int = 0  # Last frustration score (0-10)
    escalation_recommended: bool = False  # Whether human escalation was recommended
    escalation_reason: Optional[str] = None  # Reason for escalation recommendation
    sentiment_history: List[Dict[str, Any]] = []  # Track sentiment over time
    frustration_score: float = 0.0  # Rolling average frustration (0-10)
    
    # 🆕 PROACTIVE NUDGING TRACKING
    last_nudge_time: Optional[datetime] = None  # When last nudge was shown
    nudges_shown: List[Dict[str, Any]] = []  # History of nudges shown


class SessionManager:
    """Manage conversation sessions with in-memory storage."""
    
    def __init__(self, session_timeout_minutes: int = 240):  # 4 hours (240 minutes)
        self.sessions: Dict[str, ConversationSession] = {}
        self.session_timeout = timedelta(minutes=session_timeout_minutes)
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> ConversationSession:
        """Get existing session or create new one."""
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            # Check if session expired
            if datetime.now() - session.last_activity > self.session_timeout:
                logger.info(f"Session {session_id} expired, creating new one")
                return self._create_session(session_id)
            session.last_activity = datetime.now()
            return session
        
        # Create new session
        new_id = session_id or str(uuid.uuid4())[:8]
        return self._create_session(new_id)
    
    def _create_session(self, session_id: str) -> ConversationSession:
        """Create a new session."""
        session = ConversationSession(session_id=session_id)
        self.sessions[session_id] = session
        logger.info(f"Created new session: {session_id}")
        return session
    
    def add_message(self, session_id: str, role: str, content: str):
        """Add a message to session history."""
        if session_id in self.sessions:
            current_time = datetime.now()
            self.sessions[session_id].messages.append({
                "role": role,
                "content": content,
                "timestamp": current_time.isoformat()
            })
            # Update last message time for silence detection
            self.sessions[session_id].last_message_time = current_time
            # Keep only last 10 messages
            self.sessions[session_id].messages = self.sessions[session_id].messages[-10:]
            self.sessions[session_id].engagement_score += 1
    
    def record_objection(self, session_id: str, objection_type: str):
        """Record an objection raised by the customer."""
        if session_id in self.sessions:
            if objection_type not in self.sessions[session_id].objections_raised:
                self.sessions[session_id].objections_raised.append(objection_type)
                self.sessions[session_id].objection_count += 1  # Track total objections
                logger.info(f"Session {session_id}: Recorded objection '{objection_type}'")
    
    def record_interest(self, session_id: str, project_name: str):
        """Record a project the customer showed interest in."""
        if session_id in self.sessions:
            if project_name not in self.sessions[session_id].interested_projects:
                self.sessions[session_id].interested_projects.append(project_name)
                logger.info(f"Session {session_id}: Recorded interest in '{project_name}'")
    
    def update_filters(self, session_id: str, filters: Dict[str, Any]):
        """Update the current search filters for the session."""
        if session_id in self.sessions:
            self.sessions[session_id].current_filters.update(filters)
    
    def mark_cta_suggested(self, session_id: str, cta_type: str):
        """Mark that a specific CTA has been suggested."""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if cta_type == "meeting":
                session.meeting_suggested = True
            elif cta_type == "site_visit":
                session.site_visit_suggested = True
            elif cta_type == "callback":
                session.callback_suggested = True
    
    def get_next_cta(self, session_id: str) -> Optional[str]:
        """Determine the next best CTA based on conversation state."""
        if session_id not in self.sessions:
            return "meeting"
        
        session = self.sessions[session_id]
        
        # Priority: Meeting -> Site Visit -> Callback
        if not session.meeting_suggested:
            return "meeting"
        elif not session.site_visit_suggested:
            return "site_visit"
        elif not session.callback_suggested:
            return "callback"
        
        # All CTAs suggested, cycle back to meeting
        return "meeting"
    
    def get_conversation_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of the conversation for context."""
        if session_id not in self.sessions:
            return {}
        
        session = self.sessions[session_id]
        return {
            "message_count": len(session.messages),
            "objections": session.objections_raised,
            "interested_projects": session.interested_projects,
            "current_filters": session.current_filters,
            "engagement_score": session.engagement_score,
            "ctas_suggested": {
                "meeting": session.meeting_suggested,
                "site_visit": session.site_visit_suggested,
                "callback": session.callback_suggested
            }
        }
    
    def get_recent_messages(self, session_id: str, count: int = 5) -> List[Dict[str, str]]:
        """Get recent messages for LLM context."""
        if session_id not in self.sessions:
            return []
        return self.sessions[session_id].messages[-count:]
    
    def save_session(self, session: ConversationSession) -> None:
        """Persist session state after updates. CRITICAL: Never lose context."""
        # Ensure context is preserved
        if not hasattr(session, 'last_shown_projects'):
            session.last_shown_projects = []
        if not hasattr(session, 'current_filters'):
            session.current_filters = {}
        
        # Save session
        if session.session_id in self.sessions:
            self.sessions[session.session_id] = session
        else:
            self.sessions[session.session_id] = session
        session.last_activity = datetime.now()
        logger.info(f"✅ Session saved: Context preserved (projects: {len(session.last_shown_projects)}, filters: {bool(session.current_filters)})")
    
    def get_context_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get enriched context summary for GPT fallback.
        Returns comprehensive conversation context for intelligent responses.
        """
        if session_id not in self.sessions:
            return {
                "has_context": False,
                "summary": "New conversation"
            }
        
        session = self.sessions[session_id]
        
        # Build context summary
        context = {
            "has_context": True,
            "session_id": session_id,
            "message_count": len(session.messages),
            "engagement_score": session.engagement_score,
            "conversation_phase": session.conversation_phase,
            
            # Current state
            "current_filters": session.current_filters,
            "last_intent": session.last_intent,
            "last_topic": session.last_topic,
            
            # Projects
            "interested_projects": session.interested_projects,
            "last_project": session.interested_projects[-1] if session.interested_projects else None,
            "last_shown_projects": session.last_shown_projects[-5:] if session.last_shown_projects else [],
            
            # Sales tracking
            "objections_raised": session.objections_raised,
            "ctas_suggested": {
                "meeting": session.meeting_suggested,
                "site_visit": session.site_visit_suggested,
                "callback": session.callback_suggested
            },
            
            # Recent conversation
            "recent_messages": session.messages[-10:] if session.messages else [],
            
            # Formatted summary for GPT
            "summary": self._format_context_for_gpt(session)
        }
        
        return context
    
    def record_objection(self, session_id: str, objection_type: str) -> None:
        """
        Record an objection raised by the user.

        Args:
            session_id: Session identifier
            objection_type: Type of objection (budget, location, possession, trust)
        """
        session = self.get_or_create_session(session_id)

        if not hasattr(session, 'objections_raised'):
            session.objections_raised = []

        if objection_type not in session.objections_raised:
            session.objections_raised.append(objection_type)
            self.save_session(session)
            logger.info(f"Recorded objection '{objection_type}' for session {session_id}")

    def track_coaching_prompt(self, session_id: str, prompt_type: str) -> None:
        """
        Track that a coaching prompt was shown to avoid repetition.
        
        Args:
            session_id: Session identifier
            prompt_type: Type of coaching prompt (e.g., "site_visit_trigger")
        """
        session = self.get_or_create_session(session_id)
        
        if not hasattr(session, 'coaching_prompts_shown'):
            session.coaching_prompts_shown = []
        
        session.coaching_prompts_shown.append({
            "type": prompt_type,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 20 prompts
        session.coaching_prompts_shown = session.coaching_prompts_shown[-20:]
        self.save_session(session)
        logger.info(f"Tracked coaching prompt '{prompt_type}' for session {session_id}")
    
    def was_coaching_prompt_shown(self, session_id: str, prompt_type: str, within_minutes: int = 30) -> bool:
        """
        Check if a coaching prompt was recently shown to avoid repetition.
        
        Args:
            session_id: Session identifier
            prompt_type: Type of coaching prompt
            within_minutes: Time window to check (default: 30 minutes)
        
        Returns:
            True if prompt was shown within time window, False otherwise
        """
        session = self.get_or_create_session(session_id)
        
        if not hasattr(session, 'coaching_prompts_shown') or not session.coaching_prompts_shown:
            return False
        
        cutoff_time = datetime.now() - timedelta(minutes=within_minutes)
        
        for prompt in session.coaching_prompts_shown:
            if prompt["type"] == prompt_type:
                prompt_time = datetime.fromisoformat(prompt["timestamp"])
                if prompt_time > cutoff_time:
                    return True
        
        return False
    
    def update_projects_viewed(self, session_id: str, projects: List[Dict[str, Any]]) -> None:
        """
        Update the count of unique projects viewed.
        
        Args:
            session_id: Session identifier
            projects: List of projects shown
        """
        session = self.get_or_create_session(session_id)
        
        # Track unique project names
        existing_projects = set(p.get("name") for p in session.last_shown_projects if p.get("name"))
        new_projects = set(p.get("name") for p in projects if p.get("name"))
        
        # Count new unique projects
        newly_viewed = len(new_projects - existing_projects)
        session.projects_viewed_count += newly_viewed
        
        # Update last shown projects
        session.last_shown_projects = projects
        
        self.save_session(session)
        logger.info(f"Session {session_id}: Viewed {newly_viewed} new projects (total: {session.projects_viewed_count})")
    
    def get_engagement_metrics(self, session_id: str) -> Dict[str, Any]:
        """
        Get detailed engagement metrics for conversation coaching.
        
        Returns:
            Dict with engagement metrics
        """
        session = self.get_or_create_session(session_id)
        
        return {
            "message_count": len(session.messages),
            "projects_viewed": session.projects_viewed_count,
            "interested_projects_count": len(session.interested_projects),
            "objection_count": session.objection_count,
            "engagement_score": session.engagement_score,
            "conversation_phase": session.conversation_phase,
            "last_message_time": session.last_message_time,
            "session_duration_minutes": (datetime.now() - session.created_at).total_seconds() / 60,
            "ctas_suggested": {
                "meeting": session.meeting_suggested,
                "site_visit": session.site_visit_suggested,
                "callback": session.callback_suggested
            }
        }

    def _format_context_for_gpt(self, session: ConversationSession) -> str:
        """Format session context as natural language for GPT."""
        parts = []

        if session.interested_projects:
            parts.append(f"Currently discussing: {session.interested_projects[-1]}")

        if session.last_topic:
            parts.append(f"Last topic: {session.last_topic}")

        if session.current_filters:
            filter_str = ", ".join([f"{k}={v}" for k, v in session.current_filters.items() if v])
            if filter_str:
                parts.append(f"User requirements: {filter_str}")

        if session.objections_raised:
            parts.append(f"Objections raised: {', '.join(session.objections_raised)}")

        parts.append(f"Conversation phase: {session.conversation_phase}")
        parts.append(f"Messages exchanged: {len(session.messages)}")

        return " | ".join(parts) if parts else "New conversation"
    
    def record_coaching_prompt(self, session_id: str, prompt_type: str) -> None:
        """
        Record that a coaching prompt was shown to avoid repetition.

        Args:
            session_id: Session identifier
            prompt_type: Type of coaching prompt shown
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            if not hasattr(session, 'coaching_prompts_shown'):
                session.coaching_prompts_shown = []
            session.coaching_prompts_shown.append(prompt_type)
            # Keep only last 20 prompts
            session.coaching_prompts_shown = session.coaching_prompts_shown[-20:]
            self.save_session(session)
            logger.debug(f"Recorded coaching prompt '{prompt_type}' for session {session_id}")

    def update_projects_viewed(self, session_id: str, projects: List[Dict[str, Any]]) -> None:
        """
        Update the count of unique projects viewed.

        Args:
            session_id: Session identifier
            projects: List of project dicts shown to user
        """
        if session_id in self.sessions:
            session = self.sessions[session_id]
            # Track unique project names
            existing_names = {p.get("name") for p in session.last_shown_projects}
            new_projects = [p for p in projects if p.get("name") not in existing_names]
            session.projects_viewed_count += len(new_projects)
            self.save_session(session)

    def cleanup_expired_sessions(self):
        """Remove expired sessions to free memory."""
        now = datetime.now()
        expired = [
            sid for sid, session in self.sessions.items()
            if now - session.last_activity > self.session_timeout
        ]
        for sid in expired:
            del self.sessions[sid]
            logger.info(f"Cleaned up expired session: {sid}")

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")


# CTA Templates
CTA_TEMPLATES = {
    "meeting": {
        "budget": "\n\n📞 **Let's discuss EMI options that fit your budget!** Schedule a quick 15-minute call with our expert.",
        "location": "\n\n🗺️ **Want to explore both locations?** Let's schedule a meeting to compare options side by side.",
        "possession": "\n\n🏗️ **See the construction progress firsthand!** Schedule a site visit to see the quality and timeline.",
        "general": "\n\n📅 **Ready to take the next step?** Schedule a meeting with our property expert for personalized guidance."
    },
    "site_visit": {
        "default": "\n\n🚗 **Experience it yourself!** Book a free site visit with pick-up & drop. Get exclusive on-spot booking benefits worth ₹2-5 Lac!"
    },
    "callback": {
        "default": "\n\n📱 **Want us to call you back?** Share your number and our expert will connect within 30 minutes."
    }
}


def get_cta_for_context(cta_type: str, context: str = "general") -> str:
    """Get appropriate CTA text based on type and context."""
    if cta_type == "meeting":
        return CTA_TEMPLATES["meeting"].get(context, CTA_TEMPLATES["meeting"]["general"])
    elif cta_type == "site_visit":
        return CTA_TEMPLATES["site_visit"]["default"]
    elif cta_type == "callback":
        return CTA_TEMPLATES["callback"]["default"]
    return CTA_TEMPLATES["meeting"]["general"]


# Global session manager instance
session_manager = SessionManager()
