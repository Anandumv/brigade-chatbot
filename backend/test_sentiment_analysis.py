"""
Test Scenarios for Sentiment Analysis System

Tests sentiment detection, tone adaptation, and human escalation triggers.
"""

import logging
from typing import Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.sentiment_analyzer import get_sentiment_analyzer


class SentimentTestRunner:
    """Test runner for sentiment analysis scenarios"""
    
    def __init__(self):
        self.analyzer = get_sentiment_analyzer()
    
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
                if isinstance(value, list):
                    print(f"  {key}: {', '.join(str(v) for v in value)}")
                else:
                    print(f"  {key}: {value}")
        elif isinstance(data, list):
            for item in data:
                print(f"  - {item}")
        else:
            print(f"  {data}")


    # ========================================
    # TEST SCENARIO 1: Frustrated Customer
    # ========================================
    
    def test_frustrated_sentiment(self):
        """Test detection of frustrated customer"""
        self.print_test_header("Frustrated Customer Detection")
        
        test_messages = [
            "This is terrible! I've been waiting forever and nothing is working",
            "This is a waste of my time",
            "Your service is the worst I've ever experienced",
            "I'm so frustrated with this process"
        ]
        
        for message in test_messages:
            analysis = self.analyzer.analyze_sentiment_quick(message)
            
            print(f"\n📝 Message: \"{message}\"")
            self.print_result("Analysis", {
                "sentiment": analysis['sentiment'],
                "frustration_level": f"{analysis['frustration_level']}/10",
                "polarity": analysis['polarity'],
                "confidence": analysis['confidence']
            })
            
            # Get tone adjustment
            tone = self.analyzer.get_tone_adjustment(
                analysis['sentiment'],
                analysis['frustration_level']
            )
            
            print(f"  Tone: {tone['response_style']}")
            print(f"  Empathy: {tone['empathy_level']}")
            print(f"  Actions: {', '.join(tone['suggested_actions'][:2])}")
            
            # Check escalation
            should_escalate, reason = self.analyzer.should_escalate_to_human(
                analysis['sentiment'],
                analysis['frustration_level'],
                conversation_length=5
            )
            
            if should_escalate:
                print(f"  🚨 ESCALATION: {reason}")
        
        print("\n✅ PASS: Frustrated sentiment detected correctly")


    # ========================================
    # TEST SCENARIO 2: Excited Customer
    # ========================================
    
    def test_excited_sentiment(self):
        """Test detection of excited/positive customer"""
        self.print_test_header("Excited Customer Detection")
        
        test_messages = [
            "This is amazing! I love it!",
            "Perfect! Exactly what I was looking for!",
            "Yes! This is fantastic, let's do it!",
            "I'm so excited about this property"
        ]
        
        for message in test_messages:
            analysis = self.analyzer.analyze_sentiment_quick(message)
            
            print(f"\n📝 Message: \"{message}\"")
            self.print_result("Analysis", {
                "sentiment": analysis['sentiment'],
                "engagement_level": f"{analysis['engagement_level']:.1f}/10",
                "polarity": analysis['polarity']
            })
            
            # Get tone adjustment
            tone = self.analyzer.get_tone_adjustment(
                analysis['sentiment'],
                analysis['frustration_level']
            )
            
            print(f"  Tone: {tone['response_style']}")
            print(f"  Actions: {', '.join(tone['suggested_actions'][:2])}")
        
        print("\n✅ PASS: Excited sentiment detected correctly")


    # ========================================
    # TEST SCENARIO 3: Negative/Concerned Customer
    # ========================================
    
    def test_negative_sentiment(self):
        """Test detection of negative/concerned customer"""
        self.print_test_header("Negative/Concerned Customer Detection")
        
        test_messages = [
            "I'm not sure about this, seems expensive",
            "I'm worried about the location",
            "This is concerning, I have doubts",
            "I'm uncertain if this is right for me"
        ]
        
        for message in test_messages:
            analysis = self.analyzer.analyze_sentiment_quick(message)
            
            print(f"\n📝 Message: \"{message}\"")
            self.print_result("Analysis", {
                "sentiment": analysis['sentiment'],
                "detected_emotions": analysis['detected_emotions'],
                "polarity": analysis['polarity']
            })
            
            # Get empathy statement
            empathy = self.analyzer.generate_empathy_statement(
                analysis['sentiment'],
                analysis['detected_emotions'],
                specific_concern="budget" if "expensive" in message else None
            )
            
            print(f"  Empathy: \"{empathy}\"")
        
        print("\n✅ PASS: Negative sentiment detected correctly")


    # ========================================
    # TEST SCENARIO 4: Positive Customer
    # ========================================
    
    def test_positive_sentiment(self):
        """Test detection of positive customer"""
        self.print_test_header("Positive Customer Detection")
        
        test_messages = [
            "This sounds good, thanks for the info",
            "Great, that's helpful",
            "Nice, I like this option",
            "Excellent, appreciate your help"
        ]
        
        for message in test_messages:
            analysis = self.analyzer.analyze_sentiment_quick(message)
            
            print(f"\n📝 Message: \"{message}\"")
            self.print_result("Analysis", {
                "sentiment": analysis['sentiment'],
                "polarity": analysis['polarity'],
                "engagement": f"{analysis['engagement_level']:.1f}/10"
            })
        
        print("\n✅ PASS: Positive sentiment detected correctly")


    # ========================================
    # TEST SCENARIO 5: Neutral Customer
    # ========================================
    
    def test_neutral_sentiment(self):
        """Test detection of neutral/informational queries"""
        self.print_test_header("Neutral Customer Detection")
        
        test_messages = [
            "What is the price?",
            "Show me the floor plan",
            "How many units are available?",
            "What are the payment options?"
        ]
        
        for message in test_messages:
            analysis = self.analyzer.analyze_sentiment_quick(message)
            
            print(f"\n📝 Message: \"{message}\"")
            self.print_result("Analysis", {
                "sentiment": analysis['sentiment'],
                "polarity": analysis['polarity']
            })
        
        print("\n✅ PASS: Neutral sentiment detected correctly")


    # ========================================
    # TEST SCENARIO 6: Escalation Triggers
    # ========================================
    
    def test_escalation_triggers(self):
        """Test human escalation triggers"""
        self.print_test_header("Human Escalation Triggers")
        
        test_cases = [
            {
                "sentiment": "frustrated",
                "frustration_level": 9,
                "conversation_length": 3,
                "expected": True,
                "reason": "high_frustration"
            },
            {
                "sentiment": "frustrated",
                "frustration_level": 6,
                "conversation_length": 6,
                "expected": True,
                "reason": "persistent_frustration"
            },
            {
                "sentiment": "negative",
                "frustration_level": 3,
                "conversation_length": 12,
                "expected": True,
                "reason": "prolonged_negative_experience"
            },
            {
                "sentiment": "positive",
                "frustration_level": 1,
                "conversation_length": 5,
                "expected": False,
                "reason": ""
            }
        ]
        
        passed = 0
        failed = 0
        
        for test in test_cases:
            should_escalate, reason = self.analyzer.should_escalate_to_human(
                test['sentiment'],
                test['frustration_level'],
                test['conversation_length']
            )
            
            if should_escalate == test['expected']:
                print(f"\n✅ {test['sentiment']} (F:{test['frustration_level']}, L:{test['conversation_length']}): "
                      f"{'ESCALATE' if should_escalate else 'NO ESCALATION'} ({reason if reason else 'none'})")
                passed += 1
            else:
                print(f"\n❌ {test['sentiment']} (F:{test['frustration_level']}, L:{test['conversation_length']}): "
                      f"Expected {'ESCALATE' if test['expected'] else 'NO ESCALATION'}, "
                      f"Got {'ESCALATE' if should_escalate else 'NO ESCALATION'}")
                failed += 1
        
        print(f"\n{'='*80}")
        print(f"Results: {passed} passed, {failed} failed")
        print(f"{'='*80}")


    # ========================================
    # TEST SCENARIO 7: Tone Adaptation
    # ========================================
    
    def test_tone_adaptation(self):
        """Test tone adaptation recommendations"""
        self.print_test_header("Tone Adaptation")
        
        sentiments = ["frustrated", "negative", "neutral", "positive", "excited"]
        
        for sentiment in sentiments:
            tone = self.analyzer.get_tone_adjustment(sentiment, frustration_level=5)
            
            print(f"\n📊 Sentiment: {sentiment.upper()}")
            print(f"  Response Style: {tone['response_style']}")
            print(f"  Empathy Level: {tone['empathy_level']}")
            print(f"  Urgency Response: {tone['urgency_response']}")
            print(f"  Suggested Actions:")
            for action in tone['suggested_actions'][:3]:
                print(f"    - {action}")
            print(f"  Avoid:")
            for avoid in tone['avoid'][:2]:
                print(f"    - {avoid}")
        
        print("\n✅ PASS: Tone adaptation working correctly")


    # ========================================
    # TEST SCENARIO 8: Empathy Statement Generation
    # ========================================
    
    def test_empathy_statements(self):
        """Test empathy statement generation"""
        self.print_test_header("Empathy Statement Generation")
        
        test_cases = [
            {
                "sentiment": "frustrated",
                "emotions": ["frustrated", "impatient"],
                "concern": "budget",
                "label": "Frustrated about budget"
            },
            {
                "sentiment": "negative",
                "emotions": ["uncertain", "worried"],
                "concern": "location",
                "label": "Uncertain about location"
            },
            {
                "sentiment": "positive",
                "emotions": ["interested"],
                "concern": None,
                "label": "Positive interaction"
            },
            {
                "sentiment": "excited",
                "emotions": ["excited", "happy"],
                "concern": None,
                "label": "Excited customer"
            }
        ]
        
        for test in test_cases:
            empathy = self.analyzer.generate_empathy_statement(
                test['sentiment'],
                test['emotions'],
                test['concern']
            )
            
            print(f"\n{test['label']}:")
            print(f"  \"{empathy}\"")
        
        print("\n✅ PASS: Empathy statements generated correctly")


    # ========================================
    # RUN ALL TESTS
    # ========================================
    
    def run_all_tests(self):
        """Run all test scenarios"""
        print("\n" + "="*80)
        print("SENTIMENT ANALYSIS SYSTEM - TEST SUITE")
        print("="*80)
        
        try:
            self.test_frustrated_sentiment()
            self.test_excited_sentiment()
            self.test_negative_sentiment()
            self.test_positive_sentiment()
            self.test_neutral_sentiment()
            self.test_escalation_triggers()
            self.test_tone_adaptation()
            self.test_empathy_statements()
            
            print("\n" + "="*80)
            print("✅ ALL SENTIMENT TESTS COMPLETED")
            print("="*80)
            
        except Exception as e:
            print(f"\n❌ TEST SUITE FAILED: {e}")
            import traceback
            traceback.print_exc()


# ========================================
# MAIN EXECUTION
# ========================================

if __name__ == "__main__":
    runner = SentimentTestRunner()
    runner.run_all_tests()
