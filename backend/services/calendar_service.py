"""
Calendar Integration Service
Manages calendar availability and event creation

Features:
- Check RM availability
- Create calendar events
- Send calendar invites
- Update/cancel events
- Sync with Google Calendar (or other providers)
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, date, time, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class CalendarProvider(str, Enum):
    """Supported calendar providers"""
    GOOGLE = "google"
    OUTLOOK = "outlook"
    APPLE = "apple"


class AvailabilityStatus(str, Enum):
    """Availability status"""
    AVAILABLE = "available"
    BUSY = "busy"
    TENTATIVE = "tentative"
    OUT_OF_OFFICE = "out_of_office"


class CalendarService:
    """
    Manage calendar integration
    
    Features:
    - Check availability
    - Create events
    - Send invites
    - Sync with external calendars (Google, Outlook, etc.)
    
    Note: This is a mock implementation. In production, integrate with:
    - Google Calendar API (google-api-python-client)
    - Microsoft Graph API (for Outlook)
    - Apple Calendar (CalDAV)
    """
    
    def __init__(self):
        # Mock RM schedules (in production, fetch from actual calendars)
        self.rm_schedules = {
            "Rajesh Kumar": self._generate_mock_schedule(),
            "Priya Sharma": self._generate_mock_schedule(),
            "Amit Patel": self._generate_mock_schedule()
        }
        
        # Calendar events created (in-memory, in production use database)
        self.events: Dict[str, Dict[str, Any]] = {}
        self.event_counter = 0
    
    def check_availability(
        self,
        rm_name: str,
        requested_date: date,
        time_slot: str  # 'morning', 'afternoon', 'evening'
    ) -> Dict[str, Any]:
        """
        Check if RM is available at requested date/time
        
        Args:
            rm_name: Name of the RM
            requested_date: Date of visit
            time_slot: Time slot (morning/afternoon/evening)
        
        Returns:
            Dict with availability status and details
        """
        # Get RM schedule
        schedule = self.rm_schedules.get(rm_name, {})
        
        # Check if date is in the past
        if requested_date < date.today():
            return {
                "available": False,
                "reason": "Date is in the past",
                "alternative_dates": self._get_next_available_dates(rm_name, 3)
            }
        
        # Check if it's a weekend (Saturday = 5, Sunday = 6)
        if requested_date.weekday() >= 5:
            return {
                "available": False,
                "reason": "Weekends not available",
                "alternative_dates": self._get_next_available_dates(rm_name, 3, skip_weekends=True)
            }
        
        # Check RM schedule for that day
        date_str = requested_date.isoformat()
        day_schedule = schedule.get(date_str, {})
        
        # Check specific time slot
        slot_available = day_schedule.get(time_slot, {}).get("available", True)
        
        if slot_available:
            return {
                "available": True,
                "rm_name": rm_name,
                "date": date_str,
                "time_slot": time_slot,
                "time_range": self._get_time_range(time_slot)
            }
        else:
            # Suggest alternative slots on same day or next available
            return {
                "available": False,
                "reason": "Time slot already booked",
                "alternative_slots": self._get_alternative_slots(rm_name, requested_date),
                "alternative_dates": self._get_next_available_dates(rm_name, 3)
            }
    
    def create_event(
        self,
        rm_name: str,
        user_name: str,
        user_email: Optional[str],
        project_name: str,
        visit_date: date,
        time_slot: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a calendar event
        
        Args:
            rm_name: RM name
            user_name: User/customer name
            user_email: User email for invite
            project_name: Property name
            visit_date: Date of visit
            time_slot: Time slot
            notes: Additional notes
        
        Returns:
            Dict with event details
        """
        # Generate event ID
        self.event_counter += 1
        event_id = f"cal_event_{self.event_counter:06d}"
        
        # Get time range for slot
        time_range = self._get_time_range(time_slot)
        start_time, end_time = time_range.split(" - ")
        
        # Create event
        event = {
            "id": event_id,
            "rm_name": rm_name,
            "user_name": user_name,
            "user_email": user_email,
            "project_name": project_name,
            "title": f"Site Visit: {project_name} - {user_name}",
            "date": visit_date,
            "time_slot": time_slot,
            "start_time": start_time,
            "end_time": end_time,
            "notes": notes,
            "status": "scheduled",
            "created_at": datetime.now(),
            "reminders": {
                "24h_before": False,
                "1h_before": False
            }
        }
        
        # Store event
        self.events[event_id] = event
        
        # Block the slot in RM schedule
        self._block_slot(rm_name, visit_date, time_slot)
        
        logger.info(f"📅 CALENDAR EVENT CREATED: {event_id} - {project_name} on {visit_date}")
        
        # In production: Create actual calendar event using API
        # google_calendar_api.create_event(...)
        # send_calendar_invite(user_email, event)
        
        return {
            "success": True,
            "event_id": event_id,
            "title": event["title"],
            "date": visit_date.strftime("%A, %B %d, %Y"),
            "time": time_range,
            "calendar_invite_sent": user_email is not None,
            "message": "Calendar event created and invite sent"
        }
    
    def update_event(
        self,
        event_id: str,
        new_date: Optional[date] = None,
        new_time_slot: Optional[str] = None,
        status: Optional[str] = None
    ) -> bool:
        """Update an existing calendar event"""
        if event_id not in self.events:
            return False
        
        event = self.events[event_id]
        
        # If rescheduling, free up old slot and block new one
        if new_date or new_time_slot:
            old_date = event["date"]
            old_slot = event["time_slot"]
            rm_name = event["rm_name"]
            
            # Free old slot
            self._unblock_slot(rm_name, old_date, old_slot)
            
            # Update event
            if new_date:
                event["date"] = new_date
            if new_time_slot:
                event["time_slot"] = new_time_slot
                time_range = self._get_time_range(new_time_slot)
                start_time, end_time = time_range.split(" - ")
                event["start_time"] = start_time
                event["end_time"] = end_time
            
            # Block new slot
            self._block_slot(rm_name, event["date"], event["time_slot"])
            
            logger.info(f"📅 EVENT RESCHEDULED: {event_id} to {event['date']} {event['time_slot']}")
        
        # Update status
        if status:
            event["status"] = status
            logger.info(f"📅 EVENT STATUS UPDATED: {event_id} → {status}")
        
        return True
    
    def cancel_event(self, event_id: str) -> bool:
        """Cancel a calendar event and free up the slot"""
        if event_id not in self.events:
            return False
        
        event = self.events[event_id]
        
        # Free up the slot
        self._unblock_slot(event["rm_name"], event["date"], event["time_slot"])
        
        # Mark as cancelled
        event["status"] = "cancelled"
        event["cancelled_at"] = datetime.now()
        
        logger.info(f"📅 EVENT CANCELLED: {event_id}")
        
        return True
    
    def get_rm_schedule(
        self,
        rm_name: str,
        date_from: date,
        date_to: date
    ) -> List[Dict[str, Any]]:
        """
        Get RM's schedule for a date range
        
        Returns list of busy/available slots
        """
        schedule = []
        current_date = date_from
        
        while current_date <= date_to:
            date_str = current_date.isoformat()
            day_schedule = self.rm_schedules.get(rm_name, {}).get(date_str, {})
            
            for time_slot in ["morning", "afternoon", "evening"]:
                slot_info = day_schedule.get(time_slot, {"available": True})
                
                schedule.append({
                    "date": current_date,
                    "time_slot": time_slot,
                    "time_range": self._get_time_range(time_slot),
                    "available": slot_info.get("available", True),
                    "booked_by": slot_info.get("booked_by")
                })
            
            current_date += timedelta(days=1)
        
        return schedule
    
    # ========================================
    # HELPER METHODS
    # ========================================
    
    def _generate_mock_schedule(self) -> Dict[str, Dict[str, Any]]:
        """Generate mock schedule for next 30 days"""
        schedule = {}
        current_date = date.today()
        
        for i in range(30):
            check_date = current_date + timedelta(days=i)
            date_str = check_date.isoformat()
            
            # All slots available by default
            schedule[date_str] = {
                "morning": {"available": True},
                "afternoon": {"available": True},
                "evening": {"available": True}
            }
        
        return schedule
    
    def _get_time_range(self, time_slot: str) -> str:
        """Get time range for a time slot"""
        ranges = {
            "morning": "9:00 AM - 12:00 PM",
            "afternoon": "12:00 PM - 3:00 PM",
            "evening": "3:00 PM - 6:00 PM"
        }
        return ranges.get(time_slot, "TBD")
    
    def _block_slot(self, rm_name: str, visit_date: date, time_slot: str) -> None:
        """Block a time slot in RM's schedule"""
        date_str = visit_date.isoformat()
        
        if rm_name in self.rm_schedules:
            if date_str not in self.rm_schedules[rm_name]:
                self.rm_schedules[rm_name][date_str] = {
                    "morning": {"available": True},
                    "afternoon": {"available": True},
                    "evening": {"available": True}
                }
            
            self.rm_schedules[rm_name][date_str][time_slot] = {
                "available": False,
                "booked_by": "site_visit",
                "booked_at": datetime.now().isoformat()
            }
    
    def _unblock_slot(self, rm_name: str, visit_date: date, time_slot: str) -> None:
        """Free up a time slot in RM's schedule"""
        date_str = visit_date.isoformat()
        
        if rm_name in self.rm_schedules and date_str in self.rm_schedules[rm_name]:
            self.rm_schedules[rm_name][date_str][time_slot] = {"available": True}
    
    def _get_alternative_slots(
        self,
        rm_name: str,
        requested_date: date
    ) -> List[Dict[str, str]]:
        """Get alternative time slots on the same day"""
        alternatives = []
        date_str = requested_date.isoformat()
        day_schedule = self.rm_schedules.get(rm_name, {}).get(date_str, {})
        
        for time_slot in ["morning", "afternoon", "evening"]:
            if day_schedule.get(time_slot, {}).get("available", True):
                alternatives.append({
                    "time_slot": time_slot,
                    "time_range": self._get_time_range(time_slot)
                })
        
        return alternatives
    
    def _get_next_available_dates(
        self,
        rm_name: str,
        count: int = 3,
        skip_weekends: bool = False
    ) -> List[Dict[str, Any]]:
        """Get next N available dates"""
        alternatives = []
        current_date = date.today() + timedelta(days=1)
        checked = 0
        max_check = 30  # Check up to 30 days ahead
        
        while len(alternatives) < count and checked < max_check:
            # Skip weekends if requested
            if skip_weekends and current_date.weekday() >= 5:
                current_date += timedelta(days=1)
                checked += 1
                continue
            
            date_str = current_date.isoformat()
            day_schedule = self.rm_schedules.get(rm_name, {}).get(date_str, {})
            
            # Check if any slot is available
            available_slots = []
            for time_slot in ["morning", "afternoon", "evening"]:
                if day_schedule.get(time_slot, {}).get("available", True):
                    available_slots.append({
                        "time_slot": time_slot,
                        "time_range": self._get_time_range(time_slot)
                    })
            
            if available_slots:
                alternatives.append({
                    "date": current_date,
                    "date_formatted": current_date.strftime("%A, %B %d, %Y"),
                    "available_slots": available_slots
                })
            
            current_date += timedelta(days=1)
            checked += 1
        
        return alternatives


# Singleton instance
_calendar_service_instance = None


def get_calendar_service() -> CalendarService:
    """Get singleton instance of CalendarService"""
    global _calendar_service_instance
    if _calendar_service_instance is None:
        _calendar_service_instance = CalendarService()
    return _calendar_service_instance
