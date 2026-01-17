"""
Test Scenarios for Conversation Coaching System

Tests the conversation director, market intelligence, urgency engine,
and coaching integration to ensure proper sales guidance.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.conversation_director import get_conversation_director
from services.market_intelligence import get_market_intelligence
from services.urgency_engine import get_urgency_engine
from services.session_manager import SessionManager, ConversationSession


class CoachingTestRunner:
    """Test runner for conversation coaching scenarios"""
    
    def __init__(self):
        self.director = get_conversation_director()
        self.market_intel = get_market_intelligence()
        self.urgency = get_urgency_engine()
        self.session_manager = SessionManager()
    
    def create_test_session(self, session_id: str, **kwargs) -> ConversationSession:
        """Create a test session with custom attributes"""
        session = self.session_manager.get_or_create_session(session_id)
        
        # Apply custom attributes
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        self.session_manager.save_session(session)
        return session
    
    def print_test_header(self, test_name: str):
        """Print formatted test header"""
        print("\n" + "="*80)
        print(f"TEST: {test_name}")
        print("="*80)
    
    def print_result(self, label: str, data: Any):
        """Print formatted test result"""
        print(f"\n{label}:")
        if isinstance(data, dict):
            for key, value in data.items():
                print(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                print(f"  - {item}")
        else:
            print(f"  {data}")


    # ========================================
    # TEST SCENARIO 1: Site Visit Trigger
    # ========================================
    
    def test_site_visit_trigger(self):
        """
        Test that site visit coaching triggers after customer views 3+ projects
        and asks detailed questions.
        """
        self.print_test_header("Site Visit Trigger - High Engagement")
        
        # Create session with high engagement
        session = self.create_test_session(
            "test_site_visit_001",
            messages=[
                {"role": "user", "content": "Show me 2BHK in Whitefield"},
                {"role": "assistant", "content": "Here are 3 projects..."},
                {"role": "user", "content": "Tell me about Brigade Citrine"},
                {"role": "assistant", "content": "Brigade Citrine is..."},
                {"role": "user", "content": "What about schools nearby?"},
                {"role": "assistant", "content": "There are several schools..."},
                {"role": "user", "content": "How far is the metro?"},
                {"role": "assistant", "content": "Metro is 800m away..."},
            ],
            last_shown_projects=[
                {"name": "Brigade Citrine", "location": "Whitefield"},
                {"name": "Prestige Falcon City", "location": "Whitefield"},
                {"name": "Godrej Aqua", "location": "Whitefield"}
            ],
            projects_viewed_count=3
        )
        
        # Test coaching prompt
        coaching_prompt = self.director.get_coaching_prompt(
            session=session.model_dump(),
            current_query="What about the possession date?",
            context={"search_performed": False}
        )
        
        self.print_result("Session State", {
            "messages": len(session.messages),
            "projects_viewed": session.projects_viewed_count,
            "engagement_score": session.engagement_score
        })
        
        if coaching_prompt:
            self.print_result("Coaching Prompt", {
                "type": coaching_prompt["type"],
                "priority": coaching_prompt["priority"],
                "message": coaching_prompt["message"],
                "has_script": bool(coaching_prompt.get("suggested_script"))
            })
            
            if coaching_prompt.get("suggested_script"):
                print(f"\n📝 Suggested Script:\n{coaching_prompt['suggested_script']}")
            
            print("\n✅ PASS: Site visit trigger activated")
        else:
            print("\n❌ FAIL: Site visit trigger did not activate")


    # ========================================
    # TEST SCENARIO 2: Budget Objection Handling
    # ========================================
    
    def test_budget_objection_handling(self):
        """
        Test that budget objection coaching triggers and provides
        appropriate guidance.
        """
        self.print_test_header("Budget Objection Handling")
        
        # Create session with budget objection
        session = self.create_test_session(
            "test_budget_obj_001",
            messages=[
                {"role": "user", "content": "Show me 2BHK under 2 Cr"},
                {"role": "assistant", "content": "Here are projects..."},
                {"role": "user", "content": "It's too expensive for me"},
            ],
            objections_raised=["budget"],
            objection_count=1,
            last_shown_projects=[
                {"name": "Brigade Citrine", "location": "Whitefield", "budget_min": 18000, "budget_max": 25000}
            ],
            current_filters={"budget_max": 20000}  # 2 Cr in lakhs
        )
        
        # Track objection
        objection_type = self.director.track_objection(
            session=session.model_dump(),
            query="It's too expensive for me"
        )
        
        # Get coaching prompt
        coaching_prompt = self.director.get_coaching_prompt(
            session=session.model_dump(),
            current_query="It's too expensive for me",
            context={"conversation_stage": "negotiation"}
        )
        
        self.print_result("Objection Detection", {
            "detected_type": objection_type,
            "objections_raised": session.objections_raised
        })
        
        if coaching_prompt:
            self.print_result("Coaching Response", {
                "type": coaching_prompt["type"],
                "priority": coaching_prompt["priority"],
                "message": coaching_prompt["message"]
            })
            
            if coaching_prompt.get("suggested_script"):
                print(f"\n📝 Suggested Script:\n{coaching_prompt['suggested_script']}")
            
            print("\n✅ PASS: Budget objection handled")
        else:
            print("\n❌ FAIL: Budget objection not handled")


    # ========================================
    # TEST SCENARIO 3: Market Intelligence
    # ========================================
    
    def test_market_intelligence(self):
        """
        Test market intelligence service for price comparison
        and appreciation forecasts.
        """
        self.print_test_header("Market Intelligence - Whitefield Analysis")
        
        # Test project
        test_project = {
            "name": "Brigade Citrine",
            "location": "Whitefield",
            "budget_min": 18000,  # 1.8 Cr in lakhs
            "budget_max": 25000,  # 2.5 Cr in lakhs
            "configuration": "2BHK"
        }
        
        # Get price comparison
        price_comparison = self.market_intel.get_price_comparison(
            project=test_project,
            locality="Whitefield"
        )
        
        if price_comparison:
            self.print_result("Price Comparison", {
                "project_price_per_sqft": f"₹{price_comparison['project_price_per_sqft']}",
                "market_avg_per_sqft": f"₹{price_comparison['market_avg_per_sqft']}",
                "savings_percentage": f"{price_comparison['savings_percentage']}%",
                "price_position": price_comparison['price_position'],
                "value_proposition": price_comparison['value_proposition']
            })
        
        # Get appreciation forecast
        appreciation = self.market_intel.get_appreciation_forecast(
            project=test_project,
            locality="Whitefield"
        )
        
        if appreciation:
            self.print_result("Appreciation Forecast", {
                "yoy_rate": f"{appreciation['yoy_rate_percent']}%",
                "3yr_forecast": f"{appreciation['forecast_3yr_percent']}%",
                "5yr_forecast": f"{appreciation['forecast_5yr_percent']}%",
                "projected_value_5yr": f"₹{appreciation['projected_value_5yr_lakhs']} lakhs",
                "gain_5yr": f"₹{appreciation['gain_5yr_lakhs']} lakhs",
                "roi_potential": appreciation['roi_potential']
            })
        
        # Get locality insights
        locality_insights = self.market_intel.get_locality_insights("Whitefield")
        
        if locality_insights:
            self.print_result("Locality Insights", {
                "avg_price_per_sqft": f"₹{locality_insights['avg_price_per_sqft']}",
                "appreciation_rate": f"{locality_insights['appreciation_rate_yoy']}%",
                "inventory_trend": locality_insights['inventory_trend'],
                "rental_yield": f"{locality_insights['rental_yield_percent']}%",
                "investment_grade": locality_insights['investment_grade']
            })
            
            print("\n  Upcoming Infrastructure:")
            for infra in locality_insights['upcoming_infrastructure']:
                print(f"    • {infra}")
        
        if price_comparison and appreciation and locality_insights:
            print("\n✅ PASS: Market intelligence working correctly")
        else:
            print("\n❌ FAIL: Market intelligence incomplete")


    # ========================================
    # TEST SCENARIO 4: Urgency Signals
    # ========================================
    
    def test_urgency_signals(self):
        """
        Test urgency engine for generating authentic urgency signals.
        """
        self.print_test_header("Urgency Signals - Brigade Citrine")
        
        # Test project
        test_project = {
            "name": "Brigade Citrine",
            "location": "Whitefield",
            "budget_min": 18000,
            "budget_max": 25000,
            "configuration": "2BHK",
            "total_units": 100,
            "available_units": 8  # Low inventory
        }
        
        # Get locality data
        locality_data = self.market_intel.get_locality_insights("Whitefield")
        
        # Get urgency signals
        urgency_signals = self.urgency.get_urgency_signals(
            project=test_project,
            locality_data=locality_data
        )
        
        if urgency_signals:
            print(f"\n🔥 Found {len(urgency_signals)} urgency signals:")
            
            for i, signal in enumerate(urgency_signals, 1):
                print(f"\n  Signal {i}:")
                print(f"    Type: {signal['type']}")
                print(f"    Urgency Level: {signal['urgency_level']}")
                print(f"    Priority Score: {signal['priority_score']}")
                print(f"    Message: {signal['message']}")
                
                if signal.get('data'):
                    print(f"    Data: {signal['data']}")
            
            print("\n✅ PASS: Urgency signals generated")
        else:
            print("\n❌ FAIL: No urgency signals generated")


    # ========================================
    # TEST SCENARIO 5: Conversation Stage Detection
    # ========================================
    
    def test_conversation_stage_detection(self):
        """
        Test that conversation stages are correctly detected.
        """
        self.print_test_header("Conversation Stage Detection")
        
        test_cases = [
            {
                "name": "Discovery Stage",
                "session": {
                    "messages": [
                        {"role": "user", "content": "Show me 2BHK"},
                    ],
                    "last_shown_projects": [],
                    "objections_raised": [],
                    "current_filters": {"configuration": "2BHK"}
                },
                "query": "Show me 2BHK in Whitefield",
                "expected_stage": "discovery"
            },
            {
                "name": "Evaluation Stage",
                "session": {
                    "messages": [
                        {"role": "user", "content": "Show me 2BHK"},
                        {"role": "assistant", "content": "Here are projects..."},
                        {"role": "user", "content": "Tell me more about amenities"},
                    ],
                    "last_shown_projects": [
                        {"name": "Project A"},
                        {"name": "Project B"}
                    ],
                    "objections_raised": [],
                    "current_filters": {}
                },
                "query": "What amenities does it have?",
                "expected_stage": "evaluation"
            },
            {
                "name": "Negotiation Stage",
                "session": {
                    "messages": [
                        {"role": "user", "content": "It's too expensive"},
                    ],
                    "last_shown_projects": [{"name": "Project A"}],
                    "objections_raised": ["budget"],
                    "current_filters": {}
                },
                "query": "It's too expensive for me",
                "expected_stage": "negotiation"
            },
            {
                "name": "Closing Stage",
                "session": {
                    "messages": [
                        {"role": "user", "content": "Can I schedule a site visit?"},
                    ],
                    "last_shown_projects": [{"name": "Project A"}],
                    "objections_raised": [],
                    "current_filters": {}
                },
                "query": "Can I schedule a site visit?",
                "expected_stage": "closing"
            }
        ]
        
        passed = 0
        failed = 0
        
        for test_case in test_cases:
            detected_stage = self.director.detect_conversation_stage(
                session=test_case["session"],
                current_query=test_case["query"]
            )
            
            if detected_stage == test_case["expected_stage"]:
                print(f"\n✅ {test_case['name']}: {detected_stage} (correct)")
                passed += 1
            else:
                print(f"\n❌ {test_case['name']}: {detected_stage} (expected: {test_case['expected_stage']})")
                failed += 1
        
        print(f"\n{'='*80}")
        print(f"Results: {passed} passed, {failed} failed")
        print(f"{'='*80}")


    # ========================================
    # TEST SCENARIO 6: Engagement Score Calculation
    # ========================================
    
    def test_engagement_score(self):
        """
        Test engagement score calculation based on conversation metrics.
        """
        self.print_test_header("Engagement Score Calculation")
        
        test_cases = [
            {
                "name": "Low Engagement",
                "session": {
                    "messages": [
                        {"role": "user", "content": "Hi"},
                    ],
                    "last_shown_projects": [],
                    "interested_projects": [],
                    "objections_raised": []
                },
                "expected_range": (0, 3)
            },
            {
                "name": "Medium Engagement",
                "session": {
                    "messages": [
                        {"role": "user", "content": "Show me 2BHK"},
                        {"role": "assistant", "content": "Here are projects..."},
                        {"role": "user", "content": "Tell me about amenities"},
                        {"role": "assistant", "content": "Amenities include..."},
                    ],
                    "last_shown_projects": [
                        {"name": "Project A"},
                        {"name": "Project B"}
                    ],
                    "interested_projects": [],
                    "objections_raised": []
                },
                "expected_range": (4, 7)
            },
            {
                "name": "High Engagement",
                "session": {
                    "messages": [
                        {"role": "user", "content": "Show me 2BHK"},
                        {"role": "assistant", "content": "Here are projects..."},
                        {"role": "user", "content": "Tell me about schools nearby"},
                        {"role": "assistant", "content": "Schools..."},
                        {"role": "user", "content": "How far is the metro?"},
                        {"role": "assistant", "content": "Metro is..."},
                        {"role": "user", "content": "What about floor plans?"},
                    ],
                    "last_shown_projects": [
                        {"name": "Project A"},
                        {"name": "Project B"},
                        {"name": "Project C"}
                    ],
                    "interested_projects": ["Project A", "Project B"],
                    "objections_raised": []
                },
                "expected_range": (7, 10)
            }
        ]
        
        for test_case in test_cases:
            score = self.director.calculate_engagement_score(test_case["session"])
            min_score, max_score = test_case["expected_range"]
            
            if min_score <= score <= max_score:
                print(f"\n✅ {test_case['name']}: Score = {score:.1f} (expected: {min_score}-{max_score})")
            else:
                print(f"\n❌ {test_case['name']}: Score = {score:.1f} (expected: {min_score}-{max_score})")


    # ========================================
    # TEST SCENARIO 7: Locality Comparison
    # ========================================
    
    def test_locality_comparison(self):
        """
        Test locality comparison feature.
        """
        self.print_test_header("Locality Comparison - Whitefield vs Sarjapur")
        
        comparison = self.market_intel.compare_localities("Whitefield", "Sarjapur")
        
        if comparison:
            self.print_result("Whitefield", {
                "avg_price": f"₹{comparison['locality1']['avg_price']}/sqft",
                "appreciation": f"{comparison['locality1']['appreciation']}%",
                "rental_yield": f"{comparison['locality1']['rental_yield']}%",
                "trend": comparison['locality1']['trend']
            })
            
            self.print_result("Sarjapur", {
                "avg_price": f"₹{comparison['locality2']['avg_price']}/sqft",
                "appreciation": f"{comparison['locality2']['appreciation']}%",
                "rental_yield": f"{comparison['locality2']['rental_yield']}%",
                "trend": comparison['locality2']['trend']
            })
            
            self.print_result("Winners", {
                "appreciation": comparison['winner_appreciation'],
                "affordability": comparison['winner_affordability'],
                "rental_yield": comparison['winner_rental_yield'],
                "price_difference": f"{comparison['price_difference_percent']}%"
            })
            
            print("\n✅ PASS: Locality comparison working")
        else:
            print("\n❌ FAIL: Locality comparison failed")


    # ========================================
    # RUN ALL TESTS
    # ========================================
    
    def run_all_tests(self):
        """Run all test scenarios"""
        print("\n" + "="*80)
        print("CONVERSATION COACHING SYSTEM - TEST SUITE")
        print("="*80)
        
        try:
            self.test_site_visit_trigger()
            self.test_budget_objection_handling()
            self.test_market_intelligence()
            self.test_urgency_signals()
            self.test_conversation_stage_detection()
            self.test_engagement_score()
            self.test_locality_comparison()
            
            print("\n" + "="*80)
            print("✅ ALL TESTS COMPLETED")
            print("="*80)
            
        except Exception as e:
            print(f"\n❌ TEST SUITE FAILED: {e}")
            import traceback
            traceback.print_exc()


# ========================================
# MAIN EXECUTION
# ========================================

if __name__ == "__main__":
    runner = CoachingTestRunner()
    runner.run_all_tests()
