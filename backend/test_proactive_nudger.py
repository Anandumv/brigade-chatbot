"""
Test Proactive Nudger Service
Tests pattern detection and smart nudge generation
"""

import logging
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.proactive_nudger import get_proactive_nudger
from services.session_manager import ConversationSession
from services.user_profile_manager import UserProfile


def test_proactive_nudger():
    """Test complete proactive nudging functionality"""
    print("\n" + "="*80)
    print("PROACTIVE NUDGER - TEST SUITE")
    print("="*80)
    
    nudger = get_proactive_nudger()
    
    # Test 1: Repeat Views (High Priority)
    print("\n" + "="*80)
    print("TEST 1: Detect Repeat Views (3+ times)")
    print("="*80)
    
    profile = UserProfile(
        user_id="test_user_001",
        properties_viewed=[
            {"id": "proj_001", "name": "Brigade Citrine", "view_count": 4, "viewed_at": datetime.now().isoformat()},
            {"id": "proj_002", "name": "Prestige Falcon City", "view_count": 1, "viewed_at": datetime.now().isoformat()}
        ]
    )
    
    session = ConversationSession(session_id="sess_001")
    
    nudge = nudger.detect_patterns_and_nudge(profile, session, "Tell me about Brigade Citrine")
    
    assert nudge is not None, "Should detect repeat views"
    assert nudge['type'] == "repeat_views"
    assert nudge['priority'] == "high"
    assert "Brigade Citrine" in nudge['message']
    assert nudge['view_count'] == 4
    assert "schedule a site visit" in nudge['message'].lower()
    
    print("✅ Repeat views detected successfully")
    print(f"   Type: {nudge['type']}")
    print(f"   Priority: {nudge['priority']}")
    print(f"   Message: {nudge['message'][:100]}...")
    
    # Test 2: Decision Readiness (5+ properties viewed)
    print("\n" + "="*80)
    print("TEST 2: Detect Decision Readiness (5+ viewed)")
    print("="*80)
    
    profile2 = UserProfile(
        user_id="test_user_002",
        properties_viewed=[
            {"id": f"proj_{i}", "name": f"Property {i}", "view_count": 1}
            for i in range(6)  # 6 properties
        ],
        interested_projects=[
            {"id": "proj_1", "name": "Property 1", "interest_level": "high"},
            {"id": "proj_2", "name": "Property 2", "interest_level": "medium"}
        ]
    )
    
    session2 = ConversationSession(session_id="sess_002")
    
    nudge2 = nudger.detect_patterns_and_nudge(profile2, session2, "Show me more")
    
    assert nudge2 is not None, "Should detect decision readiness"
    assert nudge2['type'] == "decision_readiness"
    assert "6 properties" in nudge2['message']
    assert "comparison" in nudge2['message'].lower()
    
    print("✅ Decision readiness detected successfully")
    print(f"   Type: {nudge2['type']}")
    print(f"   Message: {nudge2['message'][:100]}...")
    
    # Test 3: Location Focus (3+ mentions)
    print("\n" + "="*80)
    print("TEST 3: Detect Location Focus")
    print("="*80)
    
    session3 = ConversationSession(
        session_id="sess_003",
        current_filters={"location": "Whitefield"},
        messages=[
            {"role": "user", "content": "Show me properties in Whitefield"},
            {"role": "assistant", "content": "Here are properties in Whitefield..."},
            {"role": "user", "content": "Any more in Whitefield?"},
            {"role": "assistant", "content": "Yes, here are more in Whitefield..."},
            {"role": "user", "content": "What about Whitefield amenities?"},
        ]
    )
    
    nudge3 = nudger.detect_patterns_and_nudge(None, session3, "Tell me about Whitefield schools")
    
    assert nudge3 is not None, "Should detect location focus"
    assert nudge3['type'] == "location_focus"
    assert "Whitefield" in nudge3['message']
    assert "nearby" in nudge3['message'].lower()
    
    print("✅ Location focus detected successfully")
    print(f"   Type: {nudge3['type']}")
    print(f"   Location: {nudge3['location']}")
    print(f"   Message: {nudge3['message'][:100]}...")
    
    # Test 4: Budget Concerns (2+ objections)
    print("\n" + "="*80)
    print("TEST 4: Detect Budget Concerns")
    print("="*80)
    
    session4 = ConversationSession(
        session_id="sess_004",
        objection_count=3  # Multiple objections
    )
    
    nudge4 = nudger.detect_patterns_and_nudge(None, session4, "That's too expensive")
    
    assert nudge4 is not None, "Should detect budget concerns"
    assert nudge4['type'] == "budget_concern"
    assert "budget" in nudge4['message'].lower()
    assert "payment plans" in nudge4['message'].lower()
    
    print("✅ Budget concerns detected successfully")
    print(f"   Type: {nudge4['type']}")
    print(f"   Message: {nudge4['message'][:100]}...")
    
    # Test 5: Long Session (15+ minutes)
    print("\n" + "="*80)
    print("TEST 5: Detect Long Session")
    print("="*80)
    
    # Create session with old first message (20 minutes ago)
    first_time = datetime.now() - timedelta(minutes=20)
    
    session5 = ConversationSession(
        session_id="sess_005",
        messages=[
            {"role": "user", "content": "Hi", "timestamp": first_time.isoformat()},
            *[{"role": "user", "content": f"Message {i}"} for i in range(12)]  # 13 total messages
        ]
    )
    
    nudge5 = nudger.detect_patterns_and_nudge(None, session5, "Show me more")
    
    assert nudge5 is not None, "Should detect long session"
    assert nudge5['type'] == "long_session"
    assert "20 minutes" in nudge5['message']
    assert "email" in nudge5['message'].lower()
    
    print("✅ Long session detected successfully")
    print(f"   Type: {nudge5['type']}")
    print(f"   Message: {nudge5['message'][:100]}...")
    
    # Test 6: Abandoned Interest (interested but no visit)
    print("\n" + "="*80)
    print("TEST 6: Detect Abandoned Interest")
    print("="*80)
    
    profile6 = UserProfile(
        user_id="test_user_006",
        total_sessions=3,  # Returning user
        interested_projects=[
            {"id": "proj_001", "name": "Brigade Citrine", "interest_level": "high"}
        ],
        site_visits_scheduled=0  # No visits yet
    )
    
    session6 = ConversationSession(session_id="sess_006")
    
    nudge6 = nudger.detect_patterns_and_nudge(profile6, session6, "Hi")
    
    assert nudge6 is not None, "Should detect abandoned interest"
    assert nudge6['type'] == "abandoned_interest"
    assert "Brigade Citrine" in nudge6['message']
    assert "site visit" in nudge6['message'].lower()
    
    print("✅ Abandoned interest detected successfully")
    print(f"   Type: {nudge6['type']}")
    print(f"   Message: {nudge6['message'][:100]}...")
    
    # Test 7: Nudge Cooldown (Don't spam)
    print("\n" + "="*80)
    print("TEST 7: Nudge Cooldown (No Spam)")
    print("="*80)
    
    # Add last_nudge_time to session (just now)
    session_cooldown = ConversationSession(session_id="sess_007")
    session_cooldown.last_nudge_time = datetime.now()
    
    profile_cooldown = UserProfile(
        user_id="test_user_007",
        properties_viewed=[
            {"id": "proj_001", "name": "Property 1", "view_count": 5}
        ]
    )
    
    nudge_cooldown = nudger.detect_patterns_and_nudge(
        profile_cooldown,
        session_cooldown,
        "Tell me more"
    )
    
    assert nudge_cooldown is None, "Should respect cooldown"
    print("✅ Nudge cooldown respected (no spam)")
    
    # Test 8: Priority Order (High Priority First)
    print("\n" + "="*80)
    print("TEST 8: Priority Order (High > Medium > Low)")
    print("="*80)
    
    # Create profile/session that matches multiple patterns
    profile_multi = UserProfile(
        user_id="test_user_008",
        total_sessions=2,
        properties_viewed=[
            {"id": "proj_001", "name": "Top Property", "view_count": 4},  # Repeat views (HIGH)
            *[{"id": f"proj_{i}", "name": f"Property {i}", "view_count": 1} for i in range(6)]  # Many views
        ],
        interested_projects=[
            {"id": "proj_001", "name": "Top Property", "interest_level": "high"}
        ],
        site_visits_scheduled=0
    )
    
    session_multi = ConversationSession(
        session_id="sess_008",
        objection_count=2  # Budget concerns (MEDIUM)
    )
    
    nudge_multi = nudger.detect_patterns_and_nudge(profile_multi, session_multi, "Show more")
    
    # Should return HIGH priority (repeat views) not MEDIUM (budget concerns)
    assert nudge_multi['type'] == "repeat_views", "Should prioritize high over medium"
    assert nudge_multi['priority'] == "high"
    
    print("✅ Priority order respected (high priority first)")
    print(f"   Selected: {nudge_multi['type']} (priority: {nudge_multi['priority']})")
    
    # Test 9: No Pattern Detected (No Nudge)
    print("\n" + "="*80)
    print("TEST 9: No Pattern Detected (Clean)")
    print("="*80)
    
    profile_clean = UserProfile(user_id="test_user_009")
    session_clean = ConversationSession(session_id="sess_009")
    
    nudge_clean = nudger.detect_patterns_and_nudge(profile_clean, session_clean, "Hi")
    
    assert nudge_clean is None, "Should return None when no pattern detected"
    print("✅ No nudge when no pattern detected (clean)")
    
    # Test 10: Nudge History Tracking
    print("\n" + "="*80)
    print("TEST 10: Nudge History Tracking")
    print("="*80)
    
    profile_track = UserProfile(
        user_id="test_user_010",
        properties_viewed=[
            {"id": "proj_001", "name": "Property 1", "view_count": 3}
        ]
    )
    
    session_track = ConversationSession(session_id="sess_010")
    
    # First nudge
    nudge_track = nudger.detect_patterns_and_nudge(profile_track, session_track, "Tell me more")
    
    assert nudge_track is not None
    assert hasattr(session_track, 'last_nudge_time')
    assert session_track.last_nudge_time is not None
    assert len(session_track.nudges_shown) == 1
    assert session_track.nudges_shown[0]['type'] == nudge_track['type']
    
    print("✅ Nudge history tracked successfully")
    print(f"   Nudges shown: {len(session_track.nudges_shown)}")
    print(f"   Last nudge time: {session_track.last_nudge_time}")
    
    # Final Summary
    print("\n" + "="*80)
    print("✅ ALL PROACTIVE NUDGER TESTS PASSED")
    print("="*80)
    print("\nKey Features Tested:")
    print("  ✅ Repeat views detection (3+ views)")
    print("  ✅ Decision readiness (5+ properties viewed)")
    print("  ✅ Location focus (3+ mentions)")
    print("  ✅ Budget concerns (2+ objections)")
    print("  ✅ Long session (15+ minutes)")
    print("  ✅ Abandoned interest (interested but no visit)")
    print("  ✅ Nudge cooldown (10-minute spacing)")
    print("  ✅ Priority order (high > medium > low)")
    print("  ✅ No false positives (clean cases)")
    print("  ✅ Nudge history tracking")
    
    return True


if __name__ == "__main__":
    try:
        success = test_proactive_nudger()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
