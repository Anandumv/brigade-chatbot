"""
User Profile Manager
Manages persistent user profiles across sessions for personalization and memory

Supports:
- Railway PostgreSQL (production) - when DATABASE_URL is set
- In-memory storage (development) - fallback when DATABASE_URL is not set
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import json

# Import database utilities
try:
    from database.connection import get_db_connection, has_database
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Database connection not available - using in-memory storage only")

logger = logging.getLogger(__name__)


class UserProfile(BaseModel):
    """User profile model"""
    # Identity
    user_id: str
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    
    # Preferences
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    preferred_configurations: List[str] = []
    preferred_locations: List[str] = []
    must_have_amenities: List[str] = []
    avoided_amenities: List[str] = []
    
    # Interaction History
    total_sessions: int = 0
    properties_viewed: List[Dict[str, Any]] = []
    properties_rejected: List[Dict[str, Any]] = []
    interested_projects: List[Dict[str, Any]] = []
    objections_history: List[Dict[str, Any]] = []
    
    # Lead Scoring
    engagement_score: float = 0.0
    intent_to_buy_score: float = 0.0
    lead_temperature: str = "cold"  # hot, warm, cold
    
    # Sales Stage
    current_stage: str = "awareness"  # awareness, consideration, decision, negotiation
    stage_history: List[Dict[str, Any]] = []
    
    # Timestamps
    created_at: datetime = datetime.now()
    last_active: datetime = datetime.now()
    last_session_id: Optional[str] = None
    
    # Analytics
    site_visits_scheduled: int = 0
    site_visits_completed: int = 0
    callbacks_requested: int = 0
    callbacks_completed: int = 0
    brochures_downloaded: int = 0
    
    # Sentiment Tracking
    sentiment_history: List[Dict[str, Any]] = []
    avg_sentiment_score: float = 0.0
    
    # Notes
    notes: Optional[str] = None
    tags: List[str] = []


class UserProfileManager:
    """
    Manage persistent user profiles across sessions
    
    Provides:
    - Cross-session memory
    - Preference tracking
    - Lead scoring
    - Welcome back messages
    - View history
    
    Storage:
    - Uses Railway PostgreSQL if DATABASE_URL is set
    - Falls back to in-memory storage for development
    """
    
    def __init__(self):
        # Check if database is available
        self.use_database = DB_AVAILABLE and has_database()
        
        if self.use_database:
            logger.info("✓ Using Railway PostgreSQL for user profiles")
        else:
            logger.warning("⚠ No DATABASE_URL - using in-memory storage for user profiles")
            # In-memory storage fallback
            self.profiles: Dict[str, UserProfile] = {}
    
    def get_or_create_profile(self, user_id: str) -> UserProfile:
        """
        Get existing profile or create new one
        
        Args:
            user_id: Unique user identifier
        
        Returns:
            UserProfile object
        """
        # In-memory fallback
        if not self.use_database:
            if user_id in self.profiles:
                profile = self.profiles[user_id]
                profile.last_active = datetime.now()
                logger.info(f"Loaded existing profile for user {user_id} (sessions: {profile.total_sessions})")
                return profile
            
            # Create new profile
            profile = UserProfile(user_id=user_id)
            self.profiles[user_id] = profile
            logger.info(f"Created new profile for user {user_id}")
            return profile
        
        # Database mode
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Try to get existing profile
                cursor.execute("""
                    SELECT * FROM user_profiles WHERE user_id = %s
                """, (user_id,))
                
                row = cursor.fetchone()
                
                if row:
                    # Parse JSONB fields
                    profile_data = dict(row)
                    profile_data['created_at'] = row['created_at']
                    profile_data['last_active'] = datetime.now()
                    
                    profile = UserProfile(**profile_data)
                    
                    # Update last_active timestamp
                    cursor.execute("""
                        UPDATE user_profiles 
                        SET last_active = %s 
                        WHERE user_id = %s
                    """, (profile.last_active, user_id))
                    
                    logger.info(f"Loaded existing profile from DB for user {user_id} (sessions: {profile.total_sessions})")
                    return profile
                else:
                    # Create new profile
                    profile = UserProfile(user_id=user_id)
                    
                    cursor.execute("""
                        INSERT INTO user_profiles (
                            user_id, name, phone, email,
                            budget_min, budget_max,
                            preferred_configurations, preferred_locations,
                            must_have_amenities, avoided_amenities,
                            total_sessions, properties_viewed, properties_rejected,
                            interested_projects, objections_history,
                            engagement_score, intent_to_buy_score, lead_temperature,
                            current_stage, stage_history,
                            created_at, last_active, last_session_id,
                            site_visits_scheduled, site_visits_completed,
                            callbacks_requested, callbacks_completed, brochures_downloaded,
                            sentiment_history, avg_sentiment_score,
                            notes, tags
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s
                        )
                    """, (
                        profile.user_id, profile.name, profile.phone, profile.email,
                        profile.budget_min, profile.budget_max,
                        json.dumps(profile.preferred_configurations), json.dumps(profile.preferred_locations),
                        json.dumps(profile.must_have_amenities), json.dumps(profile.avoided_amenities),
                        profile.total_sessions, json.dumps(profile.properties_viewed), json.dumps(profile.properties_rejected),
                        json.dumps(profile.interested_projects), json.dumps(profile.objections_history),
                        profile.engagement_score, profile.intent_to_buy_score, profile.lead_temperature,
                        profile.current_stage, json.dumps(profile.stage_history),
                        profile.created_at, profile.last_active, profile.last_session_id,
                        profile.site_visits_scheduled, profile.site_visits_completed,
                        profile.callbacks_requested, profile.callbacks_completed, profile.brochures_downloaded,
                        json.dumps(profile.sentiment_history), profile.avg_sentiment_score,
                        profile.notes, json.dumps(profile.tags)
                    ))
                    
                    logger.info(f"Created new profile in DB for user {user_id}")
                    return profile
                    
        except Exception as e:
            logger.error(f"Database error in get_or_create_profile: {e}")
            # Fall back to in-memory
            if user_id not in self.profiles:
                self.profiles[user_id] = UserProfile(user_id=user_id)
            return self.profiles[user_id]
    
    def update_preferences(
        self,
        user_id: str,
        budget_min: Optional[int] = None,
        budget_max: Optional[int] = None,
        configurations: Optional[List[str]] = None,
        locations: Optional[List[str]] = None,
        amenities: Optional[List[str]] = None
    ) -> None:
        """
        Update user preferences
        
        Args:
            user_id: User identifier
            budget_min: Minimum budget in lakhs
            budget_max: Maximum budget in lakhs
            configurations: Preferred configurations (e.g., ["2BHK", "3BHK"])
            locations: Preferred locations
            amenities: Must-have amenities
        """
        profile = self.get_or_create_profile(user_id)
        
        if budget_min is not None:
            profile.budget_min = budget_min
        if budget_max is not None:
            profile.budget_max = budget_max
        if configurations:
            # Merge with existing, avoid duplicates
            profile.preferred_configurations = list(set(profile.preferred_configurations + configurations))
        if locations:
            profile.preferred_locations = list(set(profile.preferred_locations + locations))
        if amenities:
            profile.must_have_amenities = list(set(profile.must_have_amenities + amenities))
        
        self.save_profile(profile)
        logger.info(f"Updated preferences for user {user_id}")
    
    def track_property_viewed(
        self,
        user_id: str,
        project_id: str,
        project_name: str,
        project_details: Optional[Dict] = None
    ) -> None:
        """
        Track that user viewed a property
        
        Args:
            user_id: User identifier
            project_id: Project ID
            project_name: Project name
            project_details: Additional project details
        """
        profile = self.get_or_create_profile(user_id)
        
        # Check if already viewed
        existing = next(
            (p for p in profile.properties_viewed if p.get("id") == project_id),
            None
        )
        
        if existing:
            # Increment view count
            existing["view_count"] = existing.get("view_count", 1) + 1
            existing["last_viewed_at"] = datetime.now().isoformat()
        else:
            # Add new view
            profile.properties_viewed.append({
                "id": project_id,
                "name": project_name,
                "viewed_at": datetime.now().isoformat(),
                "view_count": 1,
                "details": project_details or {}
            })
        
        # Keep only last 50 properties
        profile.properties_viewed = profile.properties_viewed[-50:]
        
        self.save_profile(profile)
        logger.info(f"Tracked property view for user {user_id}: {project_name}")
    
    def track_property_rejected(
        self,
        user_id: str,
        project_id: str,
        project_name: str,
        reason: str
    ) -> None:
        """
        Track that user rejected a property with reason
        
        Args:
            user_id: User identifier
            project_id: Project ID
            project_name: Project name
            reason: Reason for rejection
        """
        profile = self.get_or_create_profile(user_id)
        
        profile.properties_rejected.append({
            "id": project_id,
            "name": project_name,
            "reason": reason,
            "rejected_at": datetime.now().isoformat()
        })
        
        # Keep only last 20 rejections
        profile.properties_rejected = profile.properties_rejected[-20:]
        
        self.save_profile(profile)
        logger.info(f"Tracked property rejection for user {user_id}: {project_name} ({reason})")
    
    def mark_interested(
        self,
        user_id: str,
        project_id: str,
        project_name: str,
        interest_level: str = "medium"
    ) -> None:
        """
        Mark user as interested in a project
        
        Args:
            user_id: User identifier
            project_id: Project ID
            project_name: Project name
            interest_level: Level of interest (low, medium, high)
        """
        profile = self.get_or_create_profile(user_id)
        
        # Check if already interested
        existing = next(
            (p for p in profile.interested_projects if p.get("id") == project_id),
            None
        )
        
        if existing:
            # Update interest level
            existing["interest_level"] = interest_level
            existing["updated_at"] = datetime.now().isoformat()
        else:
            # Add new interest
            profile.interested_projects.append({
                "id": project_id,
                "name": project_name,
                "interest_level": interest_level,
                "marked_at": datetime.now().isoformat()
            })
        
        self.save_profile(profile)
        logger.info(f"Marked interest for user {user_id}: {project_name} ({interest_level})")
    
    def track_objection(
        self,
        user_id: str,
        objection_type: str
    ) -> None:
        """
        Track objection raised by user
        
        Args:
            user_id: User identifier
            objection_type: Type of objection (budget, location, timing, etc.)
        """
        profile = self.get_or_create_profile(user_id)
        
        # Check if this objection type exists
        existing = next(
            (o for o in profile.objections_history if o.get("type") == objection_type),
            None
        )
        
        if existing:
            # Increment count
            existing["count"] = existing.get("count", 1) + 1
            existing["last_raised_at"] = datetime.now().isoformat()
        else:
            # Add new objection
            profile.objections_history.append({
                "type": objection_type,
                "count": 1,
                "first_raised_at": datetime.now().isoformat(),
                "last_raised_at": datetime.now().isoformat()
            })
        
        self.save_profile(profile)
    
    def track_sentiment(
        self,
        user_id: str,
        sentiment: str,
        frustration_level: int
    ) -> None:
        """
        Track user sentiment
        
        Args:
            user_id: User identifier
            sentiment: Sentiment category
            frustration_level: Frustration score (0-10)
        """
        profile = self.get_or_create_profile(user_id)
        
        # Map sentiment to score
        sentiment_scores = {
            "excited": 1.0,
            "positive": 0.5,
            "neutral": 0.0,
            "negative": -0.5,
            "frustrated": -1.0
        }
        
        score = sentiment_scores.get(sentiment, 0.0)
        
        profile.sentiment_history.append({
            "sentiment": sentiment,
            "frustration_level": frustration_level,
            "score": score,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 20 sentiment entries
        profile.sentiment_history = profile.sentiment_history[-20:]
        
        # Calculate average sentiment
        if profile.sentiment_history:
            profile.avg_sentiment_score = sum(
                s.get("score", 0) for s in profile.sentiment_history
            ) / len(profile.sentiment_history)
        
        self.save_profile(profile)
    
    def increment_session_count(self, user_id: str, session_id: str) -> None:
        """Increment session count for returning users"""
        profile = self.get_or_create_profile(user_id)
        profile.total_sessions += 1
        profile.last_session_id = session_id
        self.save_profile(profile)
    
    def track_site_visit_scheduled(self, user_id: str) -> None:
        """Track that user scheduled a site visit"""
        profile = self.get_or_create_profile(user_id)
        profile.site_visits_scheduled += 1
        self.save_profile(profile)
        logger.info(f"📅 Site visit scheduled for user {user_id} (total: {profile.site_visits_scheduled})")
    
    def track_callback_requested(self, user_id: str) -> None:
        """Track that user requested a callback"""
        profile = self.get_or_create_profile(user_id)
        profile.callbacks_requested += 1
        self.save_profile(profile)
        logger.info(f"📞 Callback requested by user {user_id} (total: {profile.callbacks_requested})")
    
    def calculate_lead_score(self, user_id: str) -> Dict[str, Any]:
        """
        Calculate lead scoring metrics
        
        Returns:
            Dict with engagement and intent scores
        """
        profile = self.get_or_create_profile(user_id)
        
        # Engagement Score (0-10)
        engagement = 0.0
        engagement += min(3.0, profile.total_sessions / 2)  # 0-3 pts
        engagement += min(3.0, len(profile.properties_viewed) / 5)  # 0-3 pts
        engagement += min(2.0, len(profile.interested_projects))  # 0-2 pts
        engagement += min(2.0, profile.avg_sentiment_score + 1.0)  # 0-2 pts
        
        # Intent to Buy Score (0-10)
        intent = 0.0
        intent += min(3.0, len(profile.interested_projects) * 1.5)  # 0-3 pts
        intent += 3.0 if profile.site_visits_scheduled > 0 else 0  # 0-3 pts
        intent += 2.0 if profile.callbacks_requested > 0 else 0  # 0-2 pts
        intent += min(2.0, profile.total_sessions / 3)  # 0-2 pts
        
        # Update profile
        profile.engagement_score = engagement
        profile.intent_to_buy_score = intent
        
        # Determine lead temperature
        total_score = engagement + intent
        if total_score >= 15:
            profile.lead_temperature = "hot"
        elif total_score >= 10:
            profile.lead_temperature = "warm"
        else:
            profile.lead_temperature = "cold"
        
        self.save_profile(profile)
        
        return {
            "engagement_score": round(engagement, 1),
            "intent_to_buy_score": round(intent, 1),
            "total_score": round(total_score, 1),
            "lead_temperature": profile.lead_temperature
        }
    
    def get_welcome_back_message(self, user_id: str) -> Optional[str]:
        """
        Generate welcome back message for returning users
        
        Args:
            user_id: User identifier
        
        Returns:
            Welcome message or None if first visit
        """
        profile = self.get_or_create_profile(user_id)
        
        if profile.total_sessions <= 1:
            return None  # First visit, no welcome back
        
        message_parts = ["Welcome back!"]
        
        # Add context based on previous activity
        if profile.interested_projects:
            last_interest = profile.interested_projects[-1]
            message_parts.append(
                f"I see you were interested in {last_interest['name']}."
            )
        elif profile.properties_viewed:
            recent_views = profile.properties_viewed[-3:]
            if len(recent_views) == 1:
                message_parts.append(
                    f"You were looking at {recent_views[0]['name']} last time."
                )
            else:
                names = [p['name'] for p in recent_views]
                message_parts.append(
                    f"You were exploring {', '.join(names[:-1])} and {names[-1]}."
                )
        
        # Add time-based context
        time_since_last = datetime.now() - profile.last_active
        if time_since_last.days >= 7:
            message_parts.append("It's been a while!")
        
        # Add action suggestion
        if profile.interested_projects and profile.site_visits_scheduled == 0:
            message_parts.append(
                "Would you like to schedule a site visit to see it in person?"
            )
        elif profile.preferred_configurations or profile.preferred_locations:
            filters = []
            if profile.preferred_configurations:
                filters.append(profile.preferred_configurations[0])
            if profile.preferred_locations:
                filters.append(f"in {profile.preferred_locations[0]}")
            message_parts.append(
                f"Looking for more {' '.join(filters)} options?"
            )
        else:
            message_parts.append("What would you like to explore today?")
        
        return " ".join(message_parts)
    
    def get_profile_summary(self, user_id: str) -> Dict[str, Any]:
        """Get comprehensive profile summary"""
        profile = self.get_or_create_profile(user_id)
        
        return {
            "user_id": user_id,
            "total_sessions": profile.total_sessions,
            "properties_viewed_count": len(profile.properties_viewed),
            "interested_projects_count": len(profile.interested_projects),
            "objections_count": sum(o.get("count", 0) for o in profile.objections_history),
            "lead_temperature": profile.lead_temperature,
            "engagement_score": profile.engagement_score,
            "intent_to_buy_score": profile.intent_to_buy_score,
            "avg_sentiment": profile.avg_sentiment_score,
            "site_visits_scheduled": profile.site_visits_scheduled,
            "current_stage": profile.current_stage,
            "preferences": {
                "budget": f"₹{profile.budget_min/100:.1f}-{profile.budget_max/100:.1f} Cr" if profile.budget_max else None,
                "configurations": profile.preferred_configurations,
                "locations": profile.preferred_locations
            }
        }
    
    def save_profile(self, profile: UserProfile) -> None:
        """Save profile to storage (database or in-memory)"""
        # In-memory fallback
        if not self.use_database:
            self.profiles[profile.user_id] = profile
            return
        
        # Database mode
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    UPDATE user_profiles SET
                        name = %s,
                        phone = %s,
                        email = %s,
                        budget_min = %s,
                        budget_max = %s,
                        preferred_configurations = %s,
                        preferred_locations = %s,
                        must_have_amenities = %s,
                        avoided_amenities = %s,
                        total_sessions = %s,
                        properties_viewed = %s,
                        properties_rejected = %s,
                        interested_projects = %s,
                        objections_history = %s,
                        engagement_score = %s,
                        intent_to_buy_score = %s,
                        lead_temperature = %s,
                        current_stage = %s,
                        stage_history = %s,
                        last_active = %s,
                        last_session_id = %s,
                        site_visits_scheduled = %s,
                        site_visits_completed = %s,
                        callbacks_requested = %s,
                        callbacks_completed = %s,
                        brochures_downloaded = %s,
                        sentiment_history = %s,
                        avg_sentiment_score = %s,
                        notes = %s,
                        tags = %s
                    WHERE user_id = %s
                """, (
                    profile.name,
                    profile.phone,
                    profile.email,
                    profile.budget_min,
                    profile.budget_max,
                    json.dumps(profile.preferred_configurations),
                    json.dumps(profile.preferred_locations),
                    json.dumps(profile.must_have_amenities),
                    json.dumps(profile.avoided_amenities),
                    profile.total_sessions,
                    json.dumps(profile.properties_viewed),
                    json.dumps(profile.properties_rejected),
                    json.dumps(profile.interested_projects),
                    json.dumps(profile.objections_history),
                    profile.engagement_score,
                    profile.intent_to_buy_score,
                    profile.lead_temperature,
                    profile.current_stage,
                    json.dumps(profile.stage_history),
                    profile.last_active,
                    profile.last_session_id,
                    profile.site_visits_scheduled,
                    profile.site_visits_completed,
                    profile.callbacks_requested,
                    profile.callbacks_completed,
                    profile.brochures_downloaded,
                    json.dumps(profile.sentiment_history),
                    profile.avg_sentiment_score,
                    profile.notes,
                    json.dumps(profile.tags),
                    profile.user_id
                ))
                
        except Exception as e:
            logger.error(f"Database error in save_profile: {e}")
            # Fall back to in-memory
            self.profiles[profile.user_id] = profile
    
    def get_all_hot_leads(self) -> List[UserProfile]:
        """Get all hot leads for sales team"""
        # In-memory fallback
        if not self.use_database:
            return [
                p for p in self.profiles.values()
                if p.lead_temperature == "hot"
            ]
        
        # Database mode
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM user_profiles
                    WHERE lead_temperature = 'hot'
                    ORDER BY intent_to_buy_score DESC, engagement_score DESC
                """)
                
                rows = cursor.fetchall()
                return [UserProfile(**dict(row)) for row in rows]
                
        except Exception as e:
            logger.error(f"Database error in get_all_hot_leads: {e}")
            return []


# Singleton instance
_profile_manager_instance = None


def get_profile_manager() -> UserProfileManager:
    """Get singleton instance of UserProfileManager"""
    global _profile_manager_instance
    if _profile_manager_instance is None:
        _profile_manager_instance = UserProfileManager()
    return _profile_manager_instance
