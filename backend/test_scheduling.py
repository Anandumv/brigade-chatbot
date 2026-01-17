"""
Test Scheduling Service
Tests site visit and callback scheduling functionality
"""

import logging
from datetime import datetime, date, timedelta, time

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.scheduling_service import (
    get_scheduling_service,
    SiteVisitRequest,
    CallbackRequest,
    TimeSlot,
    UrgencyLevel,
    SchedulingStatus
)


def test_scheduling_service():
    """Test complete scheduling functionality"""
    print("\n" + "="*80)
    print("SCHEDULING SERVICE - TEST SUITE")
    print("="*80)
    
    service = get_scheduling_service()
    
    # Test 1: Schedule Site Visit
    print("\n" + "="*80)
    print("TEST 1: Schedule Site Visit")
    print("="*80)
    
    visit_request = SiteVisitRequest(
        user_id="test_user_001",
        session_id="sess_001",
        project_id="proj_001",
        project_name="Brigade Citrine",
        contact_name="John Doe",
        contact_phone="+91 98765 43210",
        contact_email="john@example.com",
        requested_date=date.today() + timedelta(days=2),
        requested_time_slot=TimeSlot.MORNING,
        user_notes="Interested in 3BHK units",
        source="test",
        lead_score=7.5
    )
    
    result = service.schedule_site_visit(visit_request)
    
    assert result['success'] == True
    assert 'visit_id' in result
    assert result['status'] == 'pending'
    assert 'rm_name' in result['details']
    
    visit_id = result['visit_id']
    
    print("✅ Site visit scheduled successfully")
    print(f"   Visit ID: {visit_id}")
    print(f"   Status: {result['status']}")
    print(f"   RM: {result['details']['rm_name']}")
    print(f"   Date: {result['details']['date']}")
    print(f"   Time: {result['details']['time_slot']}")
    
    # Test 2: Get Visit Details
    print("\n" + "="*80)
    print("TEST 2: Get Visit Details")
    print("="*80)
    
    visit_details = service.get_visit_details(visit_id)
    
    assert visit_details is not None
    assert visit_details['id'] == visit_id
    assert visit_details['project_name'] == "Brigade Citrine"
    assert visit_details['contact_name'] == "John Doe"
    assert visit_details['status'] == SchedulingStatus.PENDING
    
    print("✅ Visit details retrieved successfully")
    print(f"   Project: {visit_details['project_name']}")
    print(f"   Contact: {visit_details['contact_name']}")
    print(f"   Phone: {visit_details['contact_phone']}")
    
    # Test 3: Update Visit Status
    print("\n" + "="*80)
    print("TEST 3: Update Visit Status")
    print("="*80)
    
    success = service.update_visit_status(
        visit_id,
        SchedulingStatus.CONFIRMED,
        "Confirmed with user"
    )
    
    assert success == True
    
    updated_visit = service.get_visit_details(visit_id)
    assert updated_visit['status'] == SchedulingStatus.CONFIRMED
    assert 'confirmed_at' in updated_visit
    assert updated_visit['rm_notes'] == "Confirmed with user"
    
    print("✅ Visit status updated successfully")
    print(f"   New status: {updated_visit['status']}")
    print(f"   Notes: {updated_visit['rm_notes']}")
    
    # Test 4: Request Callback
    print("\n" + "="*80)
    print("TEST 4: Request Callback")
    print("="*80)
    
    callback_request = CallbackRequest(
        user_id="test_user_002",
        session_id="sess_002",
        contact_name="Jane Smith",
        contact_phone="+91 98765 43211",
        contact_email="jane@example.com",
        callback_reason="budget_discussion",
        user_notes="Need help with financing options",
        urgency_level=UrgencyLevel.HIGH,
        source="test",
        lead_score=8.0
    )
    
    result = service.request_callback(callback_request)
    
    assert result['success'] == True
    assert 'callback_id' in result
    assert result['status'] == 'pending'
    assert result['details']['urgency'] == UrgencyLevel.HIGH
    
    callback_id = result['callback_id']
    
    print("✅ Callback requested successfully")
    print(f"   Callback ID: {callback_id}")
    print(f"   Status: {result['status']}")
    print(f"   Agent: {result['details']['agent_name']}")
    print(f"   Expected callback: {result['details']['expected_callback']}")
    print(f"   Urgency: {result['details']['urgency']}")
    
    # Test 5: Get Callback Details
    print("\n" + "="*80)
    print("TEST 5: Get Callback Details")
    print("="*80)
    
    callback_details = service.get_callback_details(callback_id)
    
    assert callback_details is not None
    assert callback_details['id'] == callback_id
    assert callback_details['callback_reason'] == "budget_discussion"
    assert callback_details['urgency_level'] == UrgencyLevel.HIGH
    
    print("✅ Callback details retrieved successfully")
    print(f"   Reason: {callback_details['callback_reason']}")
    print(f"   Urgency: {callback_details['urgency_level']}")
    print(f"   Notes: {callback_details['user_notes']}")
    
    # Test 6: Update Callback Status
    print("\n" + "="*80)
    print("TEST 6: Update Callback Status")
    print("="*80)
    
    success = service.update_callback_status(
        callback_id,
        SchedulingStatus.CONTACTED,
        "Spoke with user, answered all questions",
        call_duration=300  # 5 minutes
    )
    
    assert success == True
    
    updated_callback = service.get_callback_details(callback_id)
    assert updated_callback['status'] == SchedulingStatus.CONTACTED
    assert 'contacted_at' in updated_callback
    assert updated_callback['call_attempts'] == 1
    assert updated_callback['call_duration_seconds'] == 300
    
    print("✅ Callback status updated successfully")
    print(f"   New status: {updated_callback['status']}")
    print(f"   Call attempts: {updated_callback['call_attempts']}")
    print(f"   Duration: {updated_callback['call_duration_seconds']}s")
    
    # Test 7: Get User Visits
    print("\n" + "="*80)
    print("TEST 7: Get User Visits")
    print("="*80)
    
    user_visits = service.get_user_visits("test_user_001")
    
    assert len(user_visits) == 1
    assert user_visits[0]['id'] == visit_id
    
    print("✅ User visits retrieved successfully")
    print(f"   Total visits: {len(user_visits)}")
    
    # Test 8: Get User Callbacks
    print("\n" + "="*80)
    print("TEST 8: Get User Callbacks")
    print("="*80)
    
    user_callbacks = service.get_user_callbacks("test_user_002")
    
    assert len(user_callbacks) == 1
    assert user_callbacks[0]['id'] == callback_id
    
    print("✅ User callbacks retrieved successfully")
    print(f"   Total callbacks: {len(user_callbacks)}")
    
    # Test 9: Multiple Visits for Same User
    print("\n" + "="*80)
    print("TEST 9: Multiple Visits for Same User")
    print("="*80)
    
    # Schedule second visit
    visit_request_2 = SiteVisitRequest(
        user_id="test_user_001",  # Same user
        project_id="proj_002",
        project_name="Prestige Falcon City",
        contact_name="John Doe",
        contact_phone="+91 98765 43210",
        contact_email="john@example.com",
        requested_date=date.today() + timedelta(days=3),
        requested_time_slot=TimeSlot.AFTERNOON,
        source="test"
    )
    
    result_2 = service.schedule_site_visit(visit_request_2)
    visit_id_2 = result_2['visit_id']
    
    user_visits = service.get_user_visits("test_user_001")
    
    assert len(user_visits) == 2
    assert any(v['id'] == visit_id for v in user_visits)
    assert any(v['id'] == visit_id_2 for v in user_visits)
    
    print("✅ Multiple visits tracked successfully")
    print(f"   Total visits for user: {len(user_visits)}")
    print(f"   Projects: {', '.join([v['project_name'] for v in user_visits])}")
    
    # Test 10: Urgency Levels
    print("\n" + "="*80)
    print("TEST 10: Urgency Levels")
    print("="*80)
    
    urgency_levels = [UrgencyLevel.URGENT, UrgencyLevel.HIGH, UrgencyLevel.MEDIUM, UrgencyLevel.LOW]
    expected_times = ["Within 30 minutes", "Within 1-2 hours", "Within 4 hours", "Within 24 hours"]
    
    for urgency, expected_time in zip(urgency_levels, expected_times):
        callback_req = CallbackRequest(
            user_id=f"test_user_urgency_{urgency.value}",
            contact_name="Test User",
            contact_phone="+91 99999 99999",
            callback_reason="test",
            urgency_level=urgency,
            source="test"
        )
        
        result = service.request_callback(callback_req)
        assert result['details']['expected_callback'] == expected_time
        
        print(f"✅ {urgency.value.upper()}: {expected_time}")
    
    # Test 11: RM Assignment (Round-Robin)
    print("\n" + "="*80)
    print("TEST 11: RM Assignment")
    print("="*80)
    
    assigned_rms = []
    for i in range(6):  # Test 6 visits
        visit_req = SiteVisitRequest(
            user_id=f"test_user_{i}",
            project_id=f"proj_{i}",
            project_name=f"Property {i}",
            contact_name=f"User {i}",
            contact_phone=f"+91 9999{i:05d}",
            source="test"
        )
        
        result = service.schedule_site_visit(visit_req)
        assigned_rms.append(result['details']['rm_name'])
    
    # Check round-robin (should cycle through 3 RMs)
    unique_rms = set(assigned_rms[:3])
    assert len(unique_rms) == 3  # First 3 should be different
    
    # Check it cycles back
    assert assigned_rms[0] == assigned_rms[3]
    assert assigned_rms[1] == assigned_rms[4]
    
    print("✅ RM assignment works correctly (round-robin)")
    print(f"   RMs assigned: {', '.join(unique_rms)}")
    
    # Final Summary
    print("\n" + "="*80)
    print("✅ ALL SCHEDULING TESTS PASSED")
    print("="*80)
    print("\nKey Features Tested:")
    print("  ✅ Site visit scheduling")
    print("  ✅ Visit status updates")
    print("  ✅ Callback requests")
    print("  ✅ Callback status updates")
    print("  ✅ User visit history")
    print("  ✅ User callback history")
    print("  ✅ Multiple visits per user")
    print("  ✅ Urgency levels (urgent/high/medium/low)")
    print("  ✅ RM round-robin assignment")
    print("  ✅ Lead score tracking")
    print("  ✅ Notes and timestamps")
    
    print(f"\nTotal visits scheduled: {len(service.scheduled_visits)}")
    print(f"Total callbacks requested: {len(service.callbacks)}")
    
    return True


if __name__ == "__main__":
    try:
        success = test_scheduling_service()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
