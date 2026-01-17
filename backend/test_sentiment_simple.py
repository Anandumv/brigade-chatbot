"""
Simple Sentiment Analysis Tests (No Config Required)

Tests sentiment detection without loading full application config.
"""

import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SimpleSentimentAnalyzer:
    """Simplified sentiment analyzer for testing"""
    
    def analyze_sentiment_quick(self, message: str):
        """Quick sentiment analysis using keywords"""
        message_lower = message.lower()
        
        # Frustrated indicators
        frustrated_keywords = [
            "frustrated", "annoyed", "waste", "ridiculous", "terrible",
            "worst", "horrible", "useless", "stupid", "hate"
        ]
        
        # Negative indicators
        negative_keywords = [
            "concerned", "worried", "unsure", "doubt", "problem",
            "expensive", "too much", "overpriced"
        ]
        
        # Positive indicators
        positive_keywords = [
            "good", "nice", "great", "thanks", "helpful",
            "appreciate", "perfect", "excellent"
        ]
        
        # Excited indicators
        excited_keywords = [
            "amazing", "awesome", "love", "fantastic", "brilliant",
            "exactly", "perfect!", "yes!"
        ]
        
        # Calculate scores
        frustrated_score = sum(1 for kw in frustrated_keywords if kw in message_lower)
        negative_score = sum(1 for kw in negative_keywords if kw in message_lower)
        positive_score = sum(1 for kw in positive_keywords if kw in message_lower)
        excited_score = sum(1 for kw in excited_keywords if kw in message_lower)
        
        # Determine sentiment
        if frustrated_score >= 2:
            sentiment = "frustrated"
            frustration_level = 9
        elif frustrated_score >= 1:
            sentiment = "negative"
            frustration_level = 6
        elif excited_score >= 2:
            sentiment = "excited"
            frustration_level = 0
        elif positive_score >= 2:
            sentiment = "positive"
            frustration_level = 0
        elif negative_score >= 2:
            sentiment = "negative"
            frustration_level = 4
        else:
            sentiment = "neutral"
            frustration_level = 0
        
        return {
            "sentiment": sentiment,
            "frustration_level": frustration_level,
            "confidence": 0.8
        }


def test_all_sentiments():
    """Test all sentiment categories"""
    print("\n" + "="*80)
    print("SENTIMENT ANALYSIS - QUICK TEST")
    print("="*80)
    
    analyzer = SimpleSentimentAnalyzer()
    
    test_cases = [
        ("This is terrible! Worst experience ever!", "frustrated"),
        ("I'm frustrated and annoyed with this", "frustrated"),
        ("I'm worried about the price, it's too expensive", "negative"),
        ("I'm uncertain if this is right for me", "negative"),
        ("What is the price?", "neutral"),
        ("Show me the floor plan", "neutral"),
        ("This sounds good, thanks!", "positive"),
        ("Great, that's helpful", "positive"),
        ("This is amazing! I love it!", "excited"),
        ("Perfect! Exactly what I wanted!", "excited"),
    ]
    
    passed = 0
    failed = 0
    
    for message, expected in test_cases:
        result = analyzer.analyze_sentiment_quick(message)
        actual = result['sentiment']
        
        status = "✅" if actual == expected else "❌"
        print(f"\n{status} \"{message}\"")
        print(f"   Expected: {expected}, Got: {actual}, Frustration: {result['frustration_level']}/10")
        
        if actual == expected:
            passed += 1
        else:
            failed += 1
    
    print(f"\n{'='*80}")
    print(f"Results: {passed}/{len(test_cases)} passed ({(passed/len(test_cases)*100):.0f}%)")
    print(f"{'='*80}")
    
    if passed == len(test_cases):
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {failed} tests failed")
    
    return passed == len(test_cases)


if __name__ == "__main__":
    success = test_all_sentiments()
    exit(0 if success else 1)
