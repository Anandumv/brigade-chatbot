"""
Reminder Service
Manages automated reminders for scheduled visits and callbacks

Features:
- Schedule reminders (24h, 1h, custom)
- Send email/SMS reminders
- Track reminder status
- Reschedule/cancel reminders

Supports:
- Railway PostgreSQL (production) - when DATABASE_URL is set
- In-memory storage (development) - fallback when DATABASE_URL is not set
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, date, time, timedelta
from enum import Enum
from pydantic import BaseModel

# Import database utilities
try:
    from database.connection import get_db_connection, has_database
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("Database connection not available - using in-memory storage only")

logger = logging.getLogger(__name__)


class ReminderType(str, Enum):
    """Type of reminder"""
    VISIT_24H = "visit_24h_before"
    VISIT_1H = "visit_1h_before"
    CALLBACK_PENDING = "callback_pending"
    FOLLOWUP = "followup"


class ReminderChannel(str, Enum):
    """Channel for sending reminders"""
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push_notification"


class ReminderStatus(str, Enum):
    """Status of reminder"""
    SCHEDULED = "scheduled"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Reminder(BaseModel):
    """Reminder model"""
    id: str
    reminder_type: ReminderType
    channel: ReminderChannel
    
    # Target
    user_id: str
    user_name: str
    user_contact: str  # email or phone
    
    # Related entity
    related_type: str  # 'visit' or 'callback'
    related_id: str  # visit_id or callback_id
    
    # Scheduling
    scheduled_time: datetime
    sent_at: Optional[datetime] = None
    status: ReminderStatus = ReminderStatus.SCHEDULED
    
    # Content
    subject: Optional[str] = None
    message: str
    
    # Tracking
    created_at: datetime = datetime.now()
    attempts: int = 0
    last_error: Optional[str] = None


class ReminderService:
    """
    Manage automated reminders
    
    Features:
    - Schedule reminders
    - Send via email/SMS/WhatsApp
    - Track delivery status
    - Retry failed reminders
    
    Note: This is a mock implementation. In production:
    - Use background job queue (Celery, RQ, etc.)
    - Integrate with email/SMS providers
    - Store in database for persistence
    """
    
    def __init__(self):
        # Check if database is available
        self.use_database = DB_AVAILABLE and has_database()
        
        if self.use_database:
            logger.info("✓ Using Railway PostgreSQL for reminders")
            self.reminder_counter = self._get_max_reminder_id()
        else:
            logger.warning("⚠ No DATABASE_URL - using in-memory storage for reminders")
            # In-memory storage fallback
            self.reminders: Dict[str, Reminder] = {}
            self.reminder_counter = 0
    
    def _get_max_reminder_id(self) -> int:
        """Get the maximum reminder ID from database"""
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(CAST(SUBSTRING(id FROM 10) AS INTEGER)) FROM reminders WHERE id LIKE 'reminder_%'")
                result = cursor.fetchone()
                return result[0] if result and result[0] else 0
        except Exception as e:
            logger.error(f"Error getting max reminder ID: {e}")
            return 0
    
    def schedule_visit_reminders(
        self,
        visit_id: str,
        user_id: str,
        user_name: str,
        user_email: Optional[str],
        user_phone: str,
        project_name: str,
        visit_date: date,
        visit_time: str,
        rm_name: str,
        rm_phone: str
    ) -> List[str]:
        """
        Schedule reminders for a site visit
        
        Args:
            visit_id: Visit ID
            user_id: User ID
            user_name: User name
            user_email: User email
            user_phone: User phone
            project_name: Project name
            visit_date: Visit date
            visit_time: Visit time range
            rm_name: RM name
            rm_phone: RM phone
        
        Returns:
            List of reminder IDs created
        """
        reminder_ids = []
        
        # Calculate reminder times
        visit_datetime = datetime.combine(visit_date, time(9, 0))  # Assume 9 AM start
        reminder_24h = visit_datetime - timedelta(hours=24)
        reminder_1h = visit_datetime - timedelta(hours=1)
        
        # 24h before reminder (email)
        if user_email and reminder_24h > datetime.now():
            message_24h = self._generate_visit_reminder_message(
                user_name, project_name, visit_date, visit_time, rm_name, rm_phone, hours_before=24
            )
            
            reminder_id_24h = self._create_reminder(
                reminder_type=ReminderType.VISIT_24H,
                channel=ReminderChannel.EMAIL,
                user_id=user_id,
                user_name=user_name,
                user_contact=user_email,
                related_type="visit",
                related_id=visit_id,
                scheduled_time=reminder_24h,
                subject=f"Reminder: Site Visit Tomorrow - {project_name}",
                message=message_24h
            )
            reminder_ids.append(reminder_id_24h)
            logger.info(f"📧 24h reminder scheduled: {reminder_id_24h} for {visit_date}")
        
        # 1h before reminder (SMS)
        if reminder_1h > datetime.now():
            message_1h = self._generate_visit_reminder_message(
                user_name, project_name, visit_date, visit_time, rm_name, rm_phone, hours_before=1
            )
            
            reminder_id_1h = self._create_reminder(
                reminder_type=ReminderType.VISIT_1H,
                channel=ReminderChannel.SMS,
                user_id=user_id,
                user_name=user_name,
                user_contact=user_phone,
                related_type="visit",
                related_id=visit_id,
                scheduled_time=reminder_1h,
                subject=None,
                message=message_1h
            )
            reminder_ids.append(reminder_id_1h)
            logger.info(f"📱 1h reminder scheduled: {reminder_id_1h} for {visit_date}")
        
        return reminder_ids
    
    def schedule_callback_reminder(
        self,
        callback_id: str,
        user_id: str,
        user_name: str,
        user_phone: str,
        urgency: str,
        delay_hours: int = 2
    ) -> str:
        """
        Schedule reminder for pending callback
        
        If callback not completed within X hours, send reminder to agent
        """
        reminder_time = datetime.now() + timedelta(hours=delay_hours)
        
        message = f"""
⚠️ PENDING CALLBACK REMINDER

Customer: {user_name}
Phone: {user_phone}
Urgency: {urgency.upper()}
Callback requested: {delay_hours} hours ago

Please contact customer immediately.
"""
        
        reminder_id = self._create_reminder(
            reminder_type=ReminderType.CALLBACK_PENDING,
            channel=ReminderChannel.EMAIL,  # Send to agent
            user_id=user_id,
            user_name=user_name,
            user_contact=user_phone,
            related_type="callback",
            related_id=callback_id,
            scheduled_time=reminder_time,
            subject=f"Pending Callback: {user_name} ({urgency})",
            message=message
        )
        
        logger.info(f"⏰ Callback reminder scheduled: {reminder_id} ({delay_hours}h)")
        
        return reminder_id
    
    def send_due_reminders(self) -> Dict[str, Any]:
        """
        Send all due reminders
        
        This should be called by a background job (every 5-10 minutes)
        
        Returns:
            Dict with sent/failed counts
        """
        now = datetime.now()
        sent_count = 0
        failed_count = 0
        
        # Get reminders to process
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Get due reminders
                    cursor.execute("""
                        SELECT * FROM reminders
                        WHERE status = 'scheduled'
                        AND scheduled_time <= %s
                    """, (now,))
                    
                    rows = cursor.fetchall()
                    
                    for row in rows:
                        reminder = Reminder(**dict(row))
                        success = self._send_reminder(reminder)
                        
                        if success:
                            cursor.execute("""
                                UPDATE reminders
                                SET status = 'sent', sent_at = %s
                                WHERE id = %s
                            """, (datetime.now(), reminder.id))
                            sent_count += 1
                            logger.info(f"✅ REMINDER SENT: {reminder.id}")
                        else:
                            cursor.execute("""
                                UPDATE reminders
                                SET status = 'failed', attempts = attempts + 1, last_error = %s
                                WHERE id = %s
                            """, (reminder.last_error, reminder.id))
                            failed_count += 1
                            logger.error(f"❌ REMINDER FAILED: {reminder.id}")
                            
                            # Retry logic (max 3 attempts)
                            if reminder.attempts < 3:
                                new_time = datetime.now() + timedelta(minutes=10)
                                cursor.execute("""
                                    UPDATE reminders
                                    SET scheduled_time = %s, status = 'scheduled'
                                    WHERE id = %s
                                """, (new_time, reminder.id))
                                logger.info(f"🔄 REMINDER RESCHEDULED: {reminder.id} (attempt {reminder.attempts + 1}/3)")
            except Exception as e:
                logger.error(f"Error sending due reminders: {e}")
        else:
            # In-memory processing
            for reminder_id, reminder in self.reminders.items():
                # Skip if already sent or cancelled
                if reminder.status in [ReminderStatus.SENT, ReminderStatus.CANCELLED]:
                    continue
                
                # Check if due
                if reminder.scheduled_time <= now:
                    success = self._send_reminder(reminder)
                    
                    if success:
                        reminder.status = ReminderStatus.SENT
                        reminder.sent_at = datetime.now()
                        sent_count += 1
                        logger.info(f"✅ REMINDER SENT: {reminder_id}")
                    else:
                        reminder.status = ReminderStatus.FAILED
                        reminder.attempts += 1
                        failed_count += 1
                        logger.error(f"❌ REMINDER FAILED: {reminder_id}")
                        
                        # Retry logic (max 3 attempts)
                        if reminder.attempts < 3:
                            # Reschedule for 10 minutes later
                            reminder.scheduled_time = datetime.now() + timedelta(minutes=10)
                            reminder.status = ReminderStatus.SCHEDULED
                            logger.info(f"🔄 REMINDER RESCHEDULED: {reminder_id} (attempt {reminder.attempts + 1}/3)")
        
        return {
            "sent": sent_count,
            "failed": failed_count,
            "pending": self._count_pending_reminders()
        }
    
    def cancel_reminder(self, reminder_id: str) -> bool:
        """Cancel a scheduled reminder"""
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    # Check if exists and not sent
                    cursor.execute("SELECT status FROM reminders WHERE id = %s", (reminder_id,))
                    row = cursor.fetchone()
                    
                    if not row:
                        return False
                    
                    if row['status'] == 'sent':
                        return False  # Can't cancel already sent
                    
                    cursor.execute("""
                        UPDATE reminders
                        SET status = 'cancelled'
                        WHERE id = %s
                    """, (reminder_id,))
                    
                    logger.info(f"🚫 REMINDER CANCELLED: {reminder_id}")
                    return True
                    
            except Exception as e:
                logger.error(f"Error cancelling reminder: {e}")
                return False
        else:
            # In-memory cancellation
            if reminder_id not in self.reminders:
                return False
            
            reminder = self.reminders[reminder_id]
            
            if reminder.status == ReminderStatus.SENT:
                return False  # Can't cancel already sent
            
            reminder.status = ReminderStatus.CANCELLED
            logger.info(f"🚫 REMINDER CANCELLED: {reminder_id}")
            
            return True
    
    def cancel_visit_reminders(self, visit_id: str) -> int:
        """Cancel all reminders for a visit"""
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        UPDATE reminders
                        SET status = 'cancelled'
                        WHERE related_type = 'visit'
                        AND related_id = %s
                        AND status != 'sent'
                    """, (visit_id,))
                    
                    cancelled_count = cursor.rowcount
                    logger.info(f"🚫 Cancelled {cancelled_count} reminders for visit {visit_id}")
                    return cancelled_count
                    
            except Exception as e:
                logger.error(f"Error cancelling visit reminders: {e}")
                return 0
        else:
            # In-memory cancellation
            cancelled_count = 0
            
            for reminder in self.reminders.values():
                if reminder.related_type == "visit" and reminder.related_id == visit_id:
                    if self.cancel_reminder(reminder.id):
                        cancelled_count += 1
            
            return cancelled_count
    
    def get_reminder_status(self, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a reminder"""
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM reminders WHERE id = %s", (reminder_id,))
                    row = cursor.fetchone()
                    
                    if not row:
                        return None
                    
                    return {
                        "id": row['id'],
                        "type": row['reminder_type'],
                        "channel": row['channel'],
                        "status": row['status'],
                        "scheduled_time": row['scheduled_time'].isoformat(),
                        "sent_at": row['sent_at'].isoformat() if row['sent_at'] else None,
                        "attempts": row['attempts']
                    }
            except Exception as e:
                logger.error(f"Error getting reminder status: {e}")
                return None
        else:
            # In-memory retrieval
            if reminder_id not in self.reminders:
                return None
            
            reminder = self.reminders[reminder_id]
            
            return {
                "id": reminder.id,
                "type": reminder.reminder_type,
                "channel": reminder.channel,
                "status": reminder.status,
                "scheduled_time": reminder.scheduled_time.isoformat(),
                "sent_at": reminder.sent_at.isoformat() if reminder.sent_at else None,
                "attempts": reminder.attempts
            }
    
    def get_pending_reminders(self) -> List[Dict[str, Any]]:
        """Get all pending reminders"""
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT id, reminder_type, user_name, scheduled_time, related_type, related_id
                        FROM reminders
                        WHERE status = 'scheduled'
                        ORDER BY scheduled_time
                    """)
                    
                    rows = cursor.fetchall()
                    return [{
                        "id": row['id'],
                        "type": row['reminder_type'],
                        "user_name": row['user_name'],
                        "scheduled_time": row['scheduled_time'].isoformat(),
                        "related_type": row['related_type'],
                        "related_id": row['related_id']
                    } for row in rows]
            except Exception as e:
                logger.error(f"Error getting pending reminders: {e}")
                return []
        else:
            # In-memory retrieval
            pending = []
            
            for reminder in self.reminders.values():
                if reminder.status == ReminderStatus.SCHEDULED:
                    pending.append({
                        "id": reminder.id,
                        "type": reminder.reminder_type,
                        "user_name": reminder.user_name,
                        "scheduled_time": reminder.scheduled_time.isoformat(),
                        "related_type": reminder.related_type,
                        "related_id": reminder.related_id
                    })
            
            return sorted(pending, key=lambda r: r["scheduled_time"])
    
    # ========================================
    # INTERNAL METHODS
    # ========================================
    
    def _create_reminder(
        self,
        reminder_type: ReminderType,
        channel: ReminderChannel,
        user_id: str,
        user_name: str,
        user_contact: str,
        related_type: str,
        related_id: str,
        scheduled_time: datetime,
        subject: Optional[str],
        message: str
    ) -> str:
        """Create a reminder"""
        self.reminder_counter += 1
        reminder_id = f"reminder_{self.reminder_counter:06d}"
        
        reminder = Reminder(
            id=reminder_id,
            reminder_type=reminder_type,
            channel=channel,
            user_id=user_id,
            user_name=user_name,
            user_contact=user_contact,
            related_type=related_type,
            related_id=related_id,
            scheduled_time=scheduled_time,
            subject=subject,
            message=message
        )
        
        # Store reminder (database or in-memory)
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        INSERT INTO reminders (
                            id, reminder_type, channel,
                            user_id, user_name, user_contact,
                            related_type, related_id,
                            scheduled_time, status,
                            subject, message,
                            created_at, attempts
                        ) VALUES (
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s,
                            %s, %s
                        )
                    """, (
                        reminder.id, reminder.reminder_type.value, reminder.channel.value,
                        reminder.user_id, reminder.user_name, reminder.user_contact,
                        reminder.related_type, reminder.related_id,
                        reminder.scheduled_time, reminder.status.value,
                        reminder.subject, reminder.message,
                        reminder.created_at, reminder.attempts
                    ))
            except Exception as e:
                logger.error(f"Error creating reminder in database: {e}")
                # Fall back to in-memory
                self.reminders[reminder_id] = reminder
        else:
            # In-memory storage
            self.reminders[reminder_id] = reminder
        
        return reminder_id
    
    def _send_reminder(self, reminder: Reminder) -> bool:
        """
        Send a reminder via specified channel
        
        In production: Integrate with actual email/SMS providers
        """
        try:
            if reminder.channel == ReminderChannel.EMAIL:
                # In production: send_email(reminder.user_contact, reminder.subject, reminder.message)
                logger.info(f"📧 EMAIL REMINDER: {reminder.user_contact} - {reminder.subject}")
                return True
            
            elif reminder.channel == ReminderChannel.SMS:
                # In production: send_sms(reminder.user_contact, reminder.message)
                logger.info(f"📱 SMS REMINDER: {reminder.user_contact}")
                return True
            
            elif reminder.channel == ReminderChannel.WHATSAPP:
                # In production: send_whatsapp(reminder.user_contact, reminder.message)
                logger.info(f"💬 WHATSAPP REMINDER: {reminder.user_contact}")
                return True
            
            else:
                logger.warning(f"Unknown channel: {reminder.channel}")
                return False
        
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
            reminder.last_error = str(e)
            return False
    
    def _generate_visit_reminder_message(
        self,
        user_name: str,
        project_name: str,
        visit_date: date,
        visit_time: str,
        rm_name: str,
        rm_phone: str,
        hours_before: int
    ) -> str:
        """Generate reminder message"""
        if hours_before == 24:
            return f"""
Hi {user_name},

This is a reminder about your site visit tomorrow!

📍 Property: {project_name}
📅 Date: {visit_date.strftime('%A, %B %d, %Y')}
⏰ Time: {visit_time}

Your Relationship Manager:
👤 {rm_name}
📞 {rm_phone}

We're excited to show you around! If you need to reschedule, please let us know.

See you tomorrow!
Brigade Properties
"""
        else:  # 1 hour before
            return f"""
Hi {user_name}! Your site visit is in 1 hour.

Property: {project_name}
Time: {visit_time}
RM: {rm_name} ({rm_phone})

See you soon!
"""
    
    def _count_pending_reminders(self) -> int:
        """Count pending reminders"""
        if self.use_database:
            try:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) as count FROM reminders WHERE status = 'scheduled'")
                    result = cursor.fetchone()
                    return result['count'] if result else 0
            except Exception as e:
                logger.error(f"Error counting pending reminders: {e}")
                return 0
        else:
            # In-memory count
            return sum(
                1 for r in self.reminders.values()
                if r.status == ReminderStatus.SCHEDULED
            )


# Singleton instance
_reminder_service_instance = None


def get_reminder_service() -> ReminderService:
    """Get singleton instance of ReminderService"""
    global _reminder_service_instance
    if _reminder_service_instance is None:
        _reminder_service_instance = ReminderService()
    return _reminder_service_instance
