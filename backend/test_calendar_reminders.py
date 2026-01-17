"""
Test Calendar & Reminder Services
Tests calendar availability, event creation, and automated reminders
"""

import logging
from datetime import datetime, date, timedelta, time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.calendar_service import get_calendar_service
from services.reminder_service import get_reminder_service, ReminderType
from services.scheduling_service import (
    get_scheduling_service,
    SiteVisitRequest,
    TimeSlot
)


def test_calendar_and_reminders():
    """Test calendar integration and reminder system"""
    print("\n" + "="*80)
    print("CALENDAR & REMINDER SERVICES - TEST SUITE")
    print("="*80)
    
    calendar_service = get_calendar_service()
    reminder_service = get_reminder_service()
    scheduling_service = get_scheduling_service()
    
    # Test 1: Check Availability (Available Slot)
    print("\n" + "="*80)
    print("TEST 1: Check Calendar Availability (Available)")
    print("="*80)
    
    # Get next weekday (skip weekends)
    tomorrow = date.today() + timedelta(days=1)
    while tomorrow.weekday() >= 5:  # Skip Saturday (5) and Sunday (6)
        tomorrow += timedelta(days=1)
    
    availability = calendar_service.check_availability(
        "Rajesh Kumar",
        tomorrow,
        "morning"
    )
    
    assert availability['available'] == True
    assert 'time_range' in availability
    
    print("✅ Availability check successful (available)")
    print(f"   RM: Rajesh Kumar")
    print(f"   Date: {tomorrow} ({tomorrow.strftime('%A')})")
    print(f"   Slot: morning ({availability['time_range']})")
    
    # Test 2: Create Calendar Event
    print("\n" + "="*80)
    print("TEST 2: Create Calendar Event")
    print("="*80)
    
    event_result = calendar_service.create_event(
        rm_name="Rajesh Kumar",
        user_name="John Doe",
        user_email="john@example.com",
        project_name="Brigade Citrine",
        visit_date=tomorrow,
        time_slot="morning",
        notes="Interested in 3BHK units"
    )
    
    assert event_result['success'] == True
    assert 'event_id' in event_result
    assert event_result['calendar_invite_sent'] == True
    
    event_id = event_result['event_id']
    
    print("✅ Calendar event created successfully")
    print(f"   Event ID: {event_id}")
    print(f"   Title: {event_result['title']}")
    print(f"   Date: {event_result['date']}")
    print(f"   Time: {event_result['time']}")
    
    # Test 3: Check Availability (Busy Slot - should be blocked now)
    print("\n" + "="*80)
    print("TEST 3: Check Availability (Busy Slot)")
    print("="*80)
    
    availability_busy = calendar_service.check_availability(
        "Rajesh Kumar",
        tomorrow,
        "morning"
    )
    
    assert availability_busy['available'] == False
    assert availability_busy['reason'] == "Time slot already booked"
    assert 'alternative_slots' in availability_busy
    
    print("✅ Busy slot detected correctly")
    print(f"   Reason: {availability_busy['reason']}")
    print(f"   Alternative slots: {len(availability_busy['alternative_slots'])}")
    
    # Test 4: Schedule Visit Reminders
    print("\n" + "="*80)
    print("TEST 4: Schedule Visit Reminders")
    print("="*80)
    
    # Schedule reminders for day after tomorrow (so 24h reminder is in future)
    visit_date = date.today() + timedelta(days=2)
    
    reminder_ids = reminder_service.schedule_visit_reminders(
        visit_id="visit_test_001",
        user_id="test_user_001",
        user_name="John Doe",
        user_email="john@example.com",
        user_phone="+91 98765 43210",
        project_name="Brigade Citrine",
        visit_date=visit_date,
        visit_time="9:00 AM - 12:00 PM",
        rm_name="Rajesh Kumar",
        rm_phone="+91 98765 43211"
    )
    
    assert len(reminder_ids) > 0
    
    print("✅ Visit reminders scheduled successfully")
    print(f"   Reminders scheduled: {len(reminder_ids)}")
    
    for reminder_id in reminder_ids:
        status = reminder_service.get_reminder_status(reminder_id)
        print(f"   - {status['type']}: {status['channel']} at {status['scheduled_time']}")
    
    # Test 5: Get Pending Reminders
    print("\n" + "="*80)
    print("TEST 5: Get Pending Reminders")
    print("="*80)
    
    pending = reminder_service.get_pending_reminders()
    
    assert len(pending) >= len(reminder_ids)
    
    print("✅ Pending reminders retrieved")
    print(f"   Total pending: {len(pending)}")
    
    # Test 6: Cancel Reminder
    print("\n" + "="*80)
    print("TEST 6: Cancel Reminder")
    print("="*80)
    
    if reminder_ids:
        first_reminder_id = reminder_ids[0]
        cancelled = reminder_service.cancel_reminder(first_reminder_id)
        
        assert cancelled == True
        
        status_after = reminder_service.get_reminder_status(first_reminder_id)
        assert status_after['status'] == "cancelled"
        
        print("✅ Reminder cancelled successfully")
        print(f"   Reminder ID: {first_reminder_id}")
        print(f"   New status: {status_after['status']}")
    
    # Test 7: Integrated Schedule (with Calendar + Reminders)
    print("\n" + "="*80)
    print("TEST 7: Integrated Scheduling (Calendar + Reminders)")
    print("="*80)
    
    # Use scheduling service which now integrates calendar + reminders
    visit_request = SiteVisitRequest(
        user_id="test_user_002",
        project_id="proj_002",
        project_name="Prestige Falcon City",
        contact_name="Jane Smith",
        contact_phone="+91 98765 55555",
        contact_email="jane@example.com",
        requested_date=date.today() + timedelta(days=3),
        requested_time_slot=TimeSlot.AFTERNOON,
        source="test"
    )
    
    result = scheduling_service.schedule_site_visit(visit_request)
    
    assert result['success'] == True
    assert 'calendar_invite_sent' in result['details']
    assert result['details']['reminders_scheduled'] > 0
    
    print("✅ Integrated scheduling successful")
    print(f"   Visit ID: {result['visit_id']}")
    print(f"   Calendar invite sent: {result['details']['calendar_invite_sent']}")
    print(f"   Reminders scheduled: {result['details']['reminders_scheduled']}")
    
    # Test 8: Reschedule Event
    print("\n" + "="*80)
    print("TEST 8: Reschedule Calendar Event")
    print("="*80)
    
    new_date = tomorrow + timedelta(days=1)
    
    rescheduled = calendar_service.update_event(
        event_id,
        new_date=new_date,
        new_time_slot="afternoon"
    )
    
    assert rescheduled == True
    
    print("✅ Event rescheduled successfully")
    print(f"   Event ID: {event_id}")
    print(f"   New date: {new_date}")
    print(f"   New slot: afternoon")
    
    # Test 9: Cancel Event (frees slot)
    print("\n" + "="*80)
    print("TEST 9: Cancel Calendar Event")
    print("="*80)
    
    cancelled_event = calendar_service.cancel_event(event_id)
    
    assert cancelled_event == True
    
    # Check that original slot is now available again
    availability_after_cancel = calendar_service.check_availability(
        "Rajesh Kumar",
        tomorrow,
        "morning"
    )
    
    assert availability_after_cancel['available'] == True
    
    print("✅ Event cancelled and slot freed")
    print(f"   Event ID: {event_id}")
    print(f"   Slot now available: {availability_after_cancel['available']}")
    
    # Test 10: Get RM Schedule
    print("\n" + "="*80)
    print("TEST 10: Get RM Schedule")
    print("="*80)
    
    schedule = calendar_service.get_rm_schedule(
        "Rajesh Kumar",
        date.today(),
        date.today() + timedelta(days=3)
    )
    
    assert len(schedule) > 0
    
    print("✅ RM schedule retrieved")
    print(f"   Total slots: {len(schedule)}")
    print(f"   Available slots: {sum(1 for s in schedule if s['available'])}")
    print(f"   Busy slots: {sum(1 for s in schedule if not s['available'])}")
    
    # Test 11: Send Due Reminders (Mock)
    print("\n" + "="*80)
    print("TEST 11: Send Due Reminders")
    print("="*80)
    
    # Create a reminder that's already due (in the past)
    past_reminder_id = reminder_service._create_reminder(
        reminder_type=ReminderType.VISIT_1H,
        channel="sms",
        user_id="test_user_due",
        user_name="Test User",
        user_contact="+91 99999 99999",
        related_type="visit",
        related_id="visit_due_test",
        scheduled_time=datetime.now() - timedelta(minutes=5),  # 5 min ago
        subject=None,
        message="Test reminder"
    )
    
    # Send due reminders
    send_result = reminder_service.send_due_reminders()
    
    assert send_result['sent'] > 0
    
    # Check reminder status
    past_reminder_status = reminder_service.get_reminder_status(past_reminder_id)
    assert past_reminder_status['status'] == "sent"
    
    print("✅ Due reminders sent successfully")
    print(f"   Sent: {send_result['sent']}")
    print(f"   Failed: {send_result['failed']}")
    print(f"   Pending: {send_result['pending']}")
    
    # Final Summary
    print("\n" + "="*80)
    print("✅ ALL CALENDAR & REMINDER TESTS PASSED")
    print("="*80)
    print("\nKey Features Tested:")
    print("  ✅ Calendar availability checking")
    print("  ✅ Calendar event creation")
    print("  ✅ Event rescheduling")
    print("  ✅ Event cancellation")
    print("  ✅ Slot blocking/freeing")
    print("  ✅ Visit reminder scheduling (24h + 1h)")
    print("  ✅ Reminder cancellation")
    print("  ✅ Integrated scheduling (calendar + reminders)")
    print("  ✅ RM schedule viewing")
    print("  ✅ Pending reminders query")
    print("  ✅ Sending due reminders")
    
    print(f"\nTotal calendar events: {len(calendar_service.events)}")
    print(f"Total reminders: {len(reminder_service.reminders)}")
    
    return True


if __name__ == "__main__":
    try:
        success = test_calendar_and_reminders()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
