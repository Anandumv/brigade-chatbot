"""
Scheduling Service
Handles site visit and callback scheduling requests

Features:
- Schedule site visits (with specific project)
- Request callbacks (general inquiries)
- Auto-assign to available RMs
- Send notifications (email/SMS placeholders)
- Track scheduling status
- Reminder system

Supports:
- Railway PostgreSQL (production) - when DATABASE_URL is set
- In-memory storage (development) - fallback when DATABASE_URL is not set
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, date, time, timedelta
from pydantic import BaseModel
from enum import Enum
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


class VisitType(str, Enum):
    """Type of visit/contact"""
    SITE_VISIT = "site_visit"
    CALLBACK = "callback"


class SchedulingStatus(str, Enum):
    """Status of scheduled visit/callback"""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    NO_ANSWER = "no_answer"
    CONTACTED = "contacted"


class TimeSlot(str, Enum):
    """Time slots for visits"""
    MORNING = "morning"      # 9 AM - 12 PM
    AFTERNOON = "afternoon"  # 12 PM - 3 PM
    EVENING = "evening"      # 3 PM - 6 PM


class UrgencyLevel(str, Enum):
    """Urgency level for callbacks"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class SiteVisitRequest(BaseModel):
    """Model for site visit request"""
    user_id: str
    session_id: Optional[str] = None
    project_id: str
    project_name: str
    contact_name: str
    contact_phone: str
    contact_email: Optional[str] = None
    requested_date: Optional[date] = None
    requested_time_slot: Optional[TimeSlot] = None
    user_notes: Optional[str] = None
    source: str = "user_request"
    lead_score: Optional[float] = None


class CallbackRequest(BaseModel):
    """Model for callback request"""
    user_id: str
    session_id: Optional[str] = None
    contact_name: str
    contact_phone: str
    contact_email: Optional[str] = None
    callback_reason: str = "general_inquiry"
    user_notes: Optional[str] = None
    urgency_level: UrgencyLevel = UrgencyLevel.MEDIUM
    preferred_date: Optional[date] = None
    preferred_time: Optional[time] = None
    source: str = "user_request"
    lead_score: Optional[float] = None


class SchedulingService:
    """
    Manage site visit and callback scheduling
    
    Features:
    - Schedule site visits
    - Request callbacks
    - Auto-assignment to RMs
    - Status tracking
    - Notifications
    - Reminders
    """
    
    def __init__(self):
        # Check if database is available
        self.use_database = DB_AVAILABLE and has_database()
        
        if self.use_database:
            logger.info("✓ Using Railway PostgreSQL for scheduling")
            self.visit_counter = self._get_max_visit_id()
            self.callback_counter = self._get_max_callback_id()
        else:
            logger.warning("⚠ No DATABASE_URL - using in-memory storage for scheduling")
            # In-memory storage fallback
            self.scheduled_visits: Dict[str, Dict[str, Any]] = {}
            self.callbacks: Dict[str, Dict[str, Any]] = {}
            self.visit_counter = 0
            self.callback_counter = 0
        
        # RM availability (mock data - in production, fetch from calendar)
        self.available_rms = [
            {"id": "rm_001", "name": "Rajesh Kumar", "phone": "+91 98765 43210", "max_daily": 5},
            {"id": "rm_002", "name": "Priya Sharma", "phone": "+91 98765 43211", "max_daily": 5},
            {"id": "rm_003", "name": "Amit Patel", "phone": "+91 98765 43212", "max_daily": 5},
        ]
    
    def _get_max_visit_id(self) -> int:
        """Get the maximum visit ID from database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(CAST(SUBSTRING(id FROM 7) AS INTEGER)) FROM scheduled_visits WHERE id LIKE 'visit_%'")
                result = cursor.fetchone()
                return result[0] if result and result[0] else 0
        except Exception as e:
            logger.error(f"Error getting max visit ID: {e}")
            return 0
    
    def _get_max_callback_id(self) -> int:
        """Get the maximum callback ID from database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(CAST(SUBSTRING(id FROM 10) AS INTEGER)) FROM requested_callbacks WHERE id LIKE 'callback_%'")
                result = cursor.fetchone()
                return result[0] if result and result[0] else 0
        except Exception as e:
            logger.error(f"Error getting max callback ID: {e}")
            return 0
    
    def schedule_site_visit(
        self,
        request: SiteVisitRequest
    ) -> Dict[str, Any]:
        """
        Schedule a site visit
        
        Args:
            request: SiteVisitRequest object
        
        Returns:
            Dict with visit details and confirmation
        """
        # Determine requested date (default to tomorrow if not specified)
        if not request.requested_date:
            request.requested_date = date.today() + timedelta(days=1)
        
        # Determine time slot (default to morning)
        if not request.requested_time_slot:
            request.requested_time_slot = TimeSlot.MORNING
        
        # 🆕 Check calendar availability
        from services.calendar_service import get_calendar_service
        
        calendar_service = get_calendar_service()
        
        # Auto-assign RM (in production, check actual availability)
        assigned_rm = self._assign_rm(request.requested_date)
        
        # Check if slot is available
        availability = calendar_service.check_availability(
            assigned_rm["name"],
            request.requested_date,
            request.requested_time_slot.value
        )
        
        if not availability.get("available"):
            # Slot not available, suggest alternatives
            return {
                "success": False,
                "message": "Selected slot not available",
                "reason": availability.get("reason"),
                "alternative_slots": availability.get("alternative_slots", []),
                "alternative_dates": availability.get("alternative_dates", [])
            }
        
        # Generate visit ID
        self.visit_counter += 1
        visit_id = f"visit_{self.visit_counter:06d}"
        
        # Create visit record
        visit = {
            "id": visit_id,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "visit_type": VisitType.SITE_VISIT,
            "project_id": request.project_id,
            "project_name": request.project_name,
            "contact_name": request.contact_name,
            "contact_phone": request.contact_phone,
            "contact_email": request.contact_email,
            "requested_date": request.requested_date,
            "requested_time_slot": request.requested_time_slot,
            "status": SchedulingStatus.PENDING,
            "assigned_rm": assigned_rm["name"],
            "assigned_rm_phone": assigned_rm["phone"],
            "user_notes": request.user_notes,
            "source": request.source,
            "lead_score_at_request": request.lead_score,
            "created_at": datetime.now(),
            "reminder_sent": False
        }
        
        # Store visit (database or in-memory)
        if self.use_database:
            self._save_visit_to_db(visit)
        else:
            self.scheduled_visits[visit_id] = visit
        
        # 🆕 Create calendar event
        calendar_result = calendar_service.create_event(
            rm_name=assigned_rm["name"],
            user_name=request.contact_name,
            user_email=request.contact_email,
            project_name=request.project_name,
            visit_date=request.requested_date,
            time_slot=request.requested_time_slot.value,
            notes=request.user_notes
        )
        
        visit["calendar_event_id"] = calendar_result.get("event_id")
        
        # 🆕 Schedule reminders
        from services.reminder_service import get_reminder_service
        
        reminder_service = get_reminder_service()
        reminder_ids = reminder_service.schedule_visit_reminders(
            visit_id=visit_id,
            user_id=request.user_id,
            user_name=request.contact_name,
            user_email=request.contact_email,
            user_phone=request.contact_phone,
            project_name=request.project_name,
            visit_date=request.requested_date,
            visit_time=self._format_time_slot(request.requested_time_slot),
            rm_name=assigned_rm["name"],
            rm_phone=assigned_rm["phone"]
        )
        
        visit["reminder_ids"] = reminder_ids
        
        logger.info(f"📅 SITE VISIT SCHEDULED: {visit_id} for {request.project_name} on {request.requested_date}")
        logger.info(f"📅 Calendar event: {visit['calendar_event_id']}")
        logger.info(f"⏰ Reminders scheduled: {len(reminder_ids)}")
        
        # Send notifications (placeholder)
        self._send_visit_confirmation(visit)
        self._notify_rm(visit)
        
        return {
            "success": True,
            "visit_id": visit_id,
            "status": "pending",
            "message": f"Site visit scheduled for {request.project_name}",
            "details": {
                "date": request.requested_date.strftime("%A, %B %d, %Y"),
                "time_slot": self._format_time_slot(request.requested_time_slot),
                "rm_name": assigned_rm["name"],
                "rm_phone": assigned_rm["phone"],
                "confirmation_sent": True,
                "calendar_invite_sent": request.contact_email is not None,
                "reminders_scheduled": len(reminder_ids)
            }
        }
    
    def request_callback(
        self,
        request: CallbackRequest
    ) -> Dict[str, Any]:
        """
        Request a callback from sales team
        
        Args:
            request: CallbackRequest object
        
        Returns:
            Dict with callback details and confirmation
        """
        # Generate callback ID
        self.callback_counter += 1
        callback_id = f"callback_{self.callback_counter:06d}"
        
        # Auto-assign agent based on urgency
        assigned_agent = self._assign_agent(request.urgency_level)
        
        # Create callback record
        callback = {
            "id": callback_id,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "contact_name": request.contact_name,
            "contact_phone": request.contact_phone,
            "contact_email": request.contact_email,
            "callback_reason": request.callback_reason,
            "user_notes": request.user_notes,
            "urgency_level": request.urgency_level,
            "preferred_date": request.preferred_date,
            "preferred_time": request.preferred_time,
            "status": SchedulingStatus.PENDING,
            "assigned_agent": assigned_agent["name"],
            "assigned_agent_phone": assigned_agent["phone"],
            "source": request.source,
            "lead_score_at_request": request.lead_score,
            "created_at": datetime.now(),
            "call_attempts": 0
        }
        
        # Store callback (database or in-memory)
        if self.use_database:
            self._save_callback_to_db(callback)
        else:
            self.callbacks[callback_id] = callback
        
        logger.info(f"📞 CALLBACK REQUESTED: {callback_id} ({request.urgency_level}) - {request.callback_reason}")
        
        # Send notifications
        self._send_callback_confirmation(callback)
        self._notify_agent(callback)
        
        # Calculate expected callback time
        expected_time = self._calculate_callback_time(request.urgency_level)
        
        return {
            "success": True,
            "callback_id": callback_id,
            "status": "pending",
            "message": "Callback request received",
            "details": {
                "agent_name": assigned_agent["name"],
                "expected_callback": expected_time,
                "urgency": request.urgency_level,
                "confirmation_sent": True
            }
        }
    
    def get_visit_details(self, visit_id: str) -> Optional[Dict[str, Any]]:
        """Get details of scheduled visit"""
        if not self.use_database:
            return self.scheduled_visits.get(visit_id)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM scheduled_visits WHERE id = %s", (visit_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting visit details: {e}")
            return None
    
    def get_callback_details(self, callback_id: str) -> Optional[Dict[str, Any]]:
        """Get details of callback request"""
        if not self.use_database:
            return self.callbacks.get(callback_id)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM requested_callbacks WHERE id = %s", (callback_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting callback details: {e}")
            return None
    
    def get_user_visits(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all visits for a user"""
        if not self.use_database:
            return [
                visit for visit in self.scheduled_visits.values()
                if visit["user_id"] == user_id
            ]
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM scheduled_visits 
                    WHERE user_id = %s 
                    ORDER BY requested_date DESC, created_at DESC
                """, (user_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting user visits: {e}")
            return []
    
    def get_user_callbacks(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all callbacks for a user"""
        if not self.use_database:
            return [
                callback for callback in self.callbacks.values()
                if callback["user_id"] == user_id
            ]
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM requested_callbacks 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                """, (user_id,))
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting user callbacks: {e}")
            return []
    
    def update_visit_status(
        self,
        visit_id: str,
        status: SchedulingStatus,
        notes: Optional[str] = None
    ) -> bool:
        """Update status of scheduled visit"""
        # Get visit details first
        visit = self.get_visit_details(visit_id)
        if not visit:
            return False
        
        # Update fields based on status
        if status == SchedulingStatus.CONFIRMED:
            confirmed_at = datetime.now()
        elif status == SchedulingStatus.COMPLETED:
            completed_at = datetime.now()
        elif status == SchedulingStatus.CANCELLED:
            cancelled_at = datetime.now()
            
            # 🆕 Cancel reminders
            if "reminder_ids" in visit:
                from services.reminder_service import get_reminder_service
                reminder_service = get_reminder_service()
                cancelled_count = reminder_service.cancel_visit_reminders(visit_id)
                logger.info(f"⏰ Cancelled {cancelled_count} reminders for {visit_id}")
            
            # 🆕 Cancel calendar event
            if "calendar_event_id" in visit:
                from services.calendar_service import get_calendar_service
                calendar_service = get_calendar_service()
                calendar_service.cancel_event(visit["calendar_event_id"])
                logger.info(f"📅 Cancelled calendar event for {visit_id}")
        
        # Update database or in-memory
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Build dynamic UPDATE query based on status
                    updates = ["status = %s"]
                    params = [status.value]
                    
                    if status == SchedulingStatus.CONFIRMED:
                        updates.append("confirmed_at = %s")
                        params.append(datetime.now())
                    elif status == SchedulingStatus.COMPLETED:
                        updates.append("completed_at = %s")
                        params.append(datetime.now())
                    elif status == SchedulingStatus.CANCELLED:
                        updates.append("cancelled_at = %s")
                        params.append(datetime.now())
                    
                    if notes:
                        updates.append("rm_notes = %s")
                        params.append(notes)
                    
                    params.append(visit_id)
                    
                    cursor.execute(f"""
                        UPDATE scheduled_visits 
                        SET {', '.join(updates)}
                        WHERE id = %s
                    """, params)
                    
            except Exception as e:
                logger.error(f"Error updating visit status: {e}")
                return False
        else:
            # In-memory update
            if visit_id not in self.scheduled_visits:
                return False
            
            visit = self.scheduled_visits[visit_id]
            visit["status"] = status
            
            if status == SchedulingStatus.CONFIRMED:
                visit["confirmed_at"] = datetime.now()
            elif status == SchedulingStatus.COMPLETED:
                visit["completed_at"] = datetime.now()
            elif status == SchedulingStatus.CANCELLED:
                visit["cancelled_at"] = datetime.now()
            
            if notes:
                visit["rm_notes"] = notes
        
        logger.info(f"📅 VISIT STATUS UPDATED: {visit_id} → {status}")
        
        return True
    
    def update_callback_status(
        self,
        callback_id: str,
        status: SchedulingStatus,
        notes: Optional[str] = None,
        call_duration: Optional[int] = None
    ) -> bool:
        """Update status of callback"""
        # Get callback details first
        callback = self.get_callback_details(callback_id)
        if not callback:
            return False
        
        # Update database or in-memory
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Build dynamic UPDATE query
                    updates = ["status = %s", "call_attempts = call_attempts + 1", "last_call_attempt = %s"]
                    params = [status.value, datetime.now()]
                    
                    if status == SchedulingStatus.CONTACTED:
                        updates.append("contacted_at = %s")
                        params.append(datetime.now())
                    elif status == SchedulingStatus.COMPLETED:
                        updates.append("completed_at = %s")
                        params.append(datetime.now())
                    
                    if call_duration:
                        updates.append("call_duration_seconds = %s")
                        params.append(call_duration)
                    
                    if notes:
                        updates.append("agent_notes = %s")
                        params.append(notes)
                    
                    params.append(callback_id)
                    
                    cursor.execute(f"""
                        UPDATE requested_callbacks 
                        SET {', '.join(updates)}
                        WHERE id = %s
                    """, params)
                    
            except Exception as e:
                logger.error(f"Error updating callback status: {e}")
                return False
        else:
            # In-memory update
            if callback_id not in self.callbacks:
                return False
            
            callback = self.callbacks[callback_id]
            callback["status"] = status
            callback["call_attempts"] += 1
            callback["last_call_attempt"] = datetime.now()
            
            if status == SchedulingStatus.CONTACTED:
                callback["contacted_at"] = datetime.now()
            elif status == SchedulingStatus.COMPLETED:
                callback["completed_at"] = datetime.now()
            
            if call_duration:
                callback["call_duration_seconds"] = call_duration
            
            if notes:
                callback["agent_notes"] = notes
        
        logger.info(f"📞 CALLBACK STATUS UPDATED: {callback_id} → {status}")
        
        return True
    
    # ========================================
    # INTERNAL HELPER METHODS
    # ========================================
    
    def _assign_rm(self, requested_date: Optional[date] = None) -> Dict[str, str]:
        """
        Assign RM based on availability
        
        In production: Check actual calendar availability
        For now: Round-robin assignment
        """
        # Simple round-robin (in production, check actual availability)
        rm_index = self.visit_counter % len(self.available_rms)
        return self.available_rms[rm_index]
    
    def _assign_agent(self, urgency: UrgencyLevel) -> Dict[str, str]:
        """Assign agent based on urgency"""
        # For urgent, assign senior agent (first in list)
        # For others, round-robin
        if urgency == UrgencyLevel.URGENT:
            return self.available_rms[0]
        
        agent_index = self.callback_counter % len(self.available_rms)
        return self.available_rms[agent_index]
    
    def _format_time_slot(self, slot: TimeSlot) -> str:
        """Format time slot for display"""
        slots = {
            TimeSlot.MORNING: "9:00 AM - 12:00 PM",
            TimeSlot.AFTERNOON: "12:00 PM - 3:00 PM",
            TimeSlot.EVENING: "3:00 PM - 6:00 PM"
        }
        return slots.get(slot, "To be confirmed")
    
    def _calculate_callback_time(self, urgency: UrgencyLevel) -> str:
        """Calculate expected callback time based on urgency"""
        if urgency == UrgencyLevel.URGENT:
            return "Within 30 minutes"
        elif urgency == UrgencyLevel.HIGH:
            return "Within 1-2 hours"
        elif urgency == UrgencyLevel.MEDIUM:
            return "Within 4 hours"
        else:
            return "Within 24 hours"
    
    # ========================================
    # DATABASE HELPER METHODS
    # ========================================
    
    def _save_visit_to_db(self, visit: Dict[str, Any]) -> None:
        """Save visit to PostgreSQL database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO scheduled_visits (
                        id, user_id, session_id, project_id, project_name,
                        contact_name, contact_phone, contact_email,
                        requested_date, requested_time_slot,
                        status, assigned_rm, assigned_rm_phone,
                        user_notes, source, lead_score_at_request,
                        calendar_event_id, reminder_ids,
                        created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s
                    )
                """, (
                    visit["id"], visit["user_id"], visit["session_id"],
                    visit["project_id"], visit["project_name"],
                    visit["contact_name"], visit["contact_phone"], visit["contact_email"],
                    visit["requested_date"], visit["requested_time_slot"].value,
                    visit["status"].value, visit["assigned_rm"], visit["assigned_rm_phone"],
                    visit["user_notes"], visit["source"], visit["lead_score_at_request"],
                    visit.get("calendar_event_id"), json.dumps(visit.get("reminder_ids", [])),
                    visit["created_at"]
                ))
                
        except Exception as e:
            logger.error(f"Error saving visit to database: {e}")
            raise
    
    def _save_callback_to_db(self, callback: Dict[str, Any]) -> None:
        """Save callback to PostgreSQL database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT INTO requested_callbacks (
                        id, user_id, session_id,
                        contact_name, contact_phone, contact_email,
                        callback_reason, user_notes, urgency_level,
                        preferred_date, preferred_time,
                        status, assigned_agent, assigned_agent_phone,
                        source, lead_score_at_request,
                        call_attempts, created_at
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        %s, %s
                    )
                """, (
                    callback["id"], callback["user_id"], callback["session_id"],
                    callback["contact_name"], callback["contact_phone"], callback["contact_email"],
                    callback["callback_reason"], callback["user_notes"], callback["urgency_level"].value,
                    callback["preferred_date"], callback["preferred_time"],
                    callback["status"].value, callback["assigned_agent"], callback["assigned_agent_phone"],
                    callback["source"], callback["lead_score_at_request"],
                    callback["call_attempts"], callback["created_at"]
                ))
                
        except Exception as e:
            logger.error(f"Error saving callback to database: {e}")
            raise
    
    # ========================================
    # NOTIFICATION METHODS (Placeholders)
    # ========================================
    
    def _send_visit_confirmation(self, visit: Dict[str, Any]) -> None:
        """
        Send visit confirmation to user
        
        In production: Integrate with email/SMS service
        """
        message = f"""
        🎉 Site Visit Confirmed!
        
        Property: {visit['project_name']}
        Date: {visit['requested_date'].strftime('%A, %B %d, %Y')}
        Time: {self._format_time_slot(visit['requested_time_slot'])}
        
        Your Relationship Manager:
        {visit['assigned_rm']}
        {visit['assigned_rm_phone']}
        
        We'll send you a reminder 1 day before your visit!
        """
        
        logger.info(f"📧 CONFIRMATION EMAIL: {visit['contact_email']} (placeholder)")
        logger.info(f"📱 CONFIRMATION SMS: {visit['contact_phone']} (placeholder)")
        # In production: send_email(visit['contact_email'], message)
        # In production: send_sms(visit['contact_phone'], message)
    
    def _notify_rm(self, visit: Dict[str, Any]) -> None:
        """Notify RM about new visit assignment"""
        logger.info(f"🔔 RM NOTIFIED: {visit['assigned_rm']} about {visit['project_name']} visit")
        # In production: Send notification to RM's dashboard/email/SMS
    
    def _send_callback_confirmation(self, callback: Dict[str, Any]) -> None:
        """Send callback confirmation to user"""
        expected_time = self._calculate_callback_time(callback['urgency_level'])
        
        message = f"""
        📞 Callback Request Received!
        
        Your request has been assigned to {callback['assigned_agent']}.
        Expected callback: {expected_time}
        
        We'll reach you at: {callback['contact_phone']}
        """
        
        logger.info(f"📧 CALLBACK CONFIRMATION: {callback['contact_email']} (placeholder)")
        # In production: send_email/SMS
    
    def _notify_agent(self, callback: Dict[str, Any]) -> None:
        """Notify agent about new callback request"""
        logger.info(f"🔔 AGENT NOTIFIED: {callback['assigned_agent']} - {callback['urgency_level']} priority")
        # In production: Send to agent's dashboard/mobile app


# Singleton instance
_scheduling_service_instance = None


def get_scheduling_service() -> SchedulingService:
    """Get singleton instance of SchedulingService"""
    global _scheduling_service_instance
    if _scheduling_service_instance is None:
        _scheduling_service_instance = SchedulingService()
    return _scheduling_service_instance
