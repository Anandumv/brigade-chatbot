"""
Sentiment Analyzer Service
Analyzes customer sentiment and provides tone adaptation recommendations
"""

import logging
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI
from config import settings

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(
    api_key=settings.openai_api_key,
    base_url=settings.openai_base_url,
    timeout=30.0  # 30 second timeout for API calls
)


class SentimentAnalyzer:
    """
    Analyze customer sentiment and adapt AI tone accordingly
    
    Sentiment Categories:
    - excited: Very positive, high engagement
    - positive: Satisfied, interested
    - neutral: Informational, matter-of-fact
    - negative: Concerned, uncertain
    - frustrated: Upset, impatient
    """
    
    def __init__(self):
        self.sentiment_cache = {}  # Cache recent analyses
    
    def analyze_sentiment_quick(self, message: str) -> Dict[str, Any]:
        """
        Quick sentiment analysis using keyword detection (fast, offline)
        
        Args:
            message: User message to analyze
        
        Returns:
            Dict with sentiment, polarity, confidence
        """
        message_lower = message.lower()
        
        # Frustrated indicators
        frustrated_keywords = [
            "frustrated", "annoyed", "waste", "ridiculous", "terrible",
            "worst", "horrible", "useless", "stupid", "hate",
            "never", "always wrong", "not working", "broken"
        ]
        
        # Negative indicators
        negative_keywords = [
            "concerned", "worried", "unsure", "doubt", "problem",
            "issue", "confusing", "unclear", "not sure", "hesitant",
            "expensive", "too much", "overpriced"
        ]
        
        # Positive indicators
        positive_keywords = [
            "good", "nice", "great", "thanks", "helpful",
            "appreciate", "perfect", "excellent", "wonderful",
            "interested", "sounds good", "like it"
        ]
        
        # Excited indicators
        excited_keywords = [
            "amazing", "awesome", "love", "fantastic", "brilliant",
            "exactly", "perfect!", "yes!", "definitely", "absolutely",
            "can't wait", "excited", "wonderful"
        ]
        
        # Calculate scores
        frustrated_score = sum(1 for kw in frustrated_keywords if kw in message_lower)
        negative_score = sum(1 for kw in negative_keywords if kw in message_lower)
        positive_score = sum(1 for kw in positive_keywords if kw in message_lower)
        excited_score = sum(1 for kw in excited_keywords if kw in message_lower)
        
        # Determine sentiment
        if frustrated_score >= 2 or any(kw in message_lower for kw in ["terrible", "worst", "hate"]):
            sentiment = "frustrated"
            polarity = -0.8
            confidence = 0.85
        elif frustrated_score >= 1:
            sentiment = "negative"
            polarity = -0.5
            confidence = 0.7
        elif excited_score >= 2:
            sentiment = "excited"
            polarity = 0.8
            confidence = 0.85
        elif positive_score >= 2:
            sentiment = "positive"
            polarity = 0.5
            confidence = 0.7
        elif negative_score >= 2:
            sentiment = "negative"
            polarity = -0.4
            confidence = 0.7
        else:
            sentiment = "neutral"
            polarity = 0.0
            confidence = 0.6
        
        # Detect specific emotions
        detected_emotions = []
        if any(kw in message_lower for kw in ["uncertain", "not sure", "maybe", "hesitant"]):
            detected_emotions.append("uncertain")
        if any(kw in message_lower for kw in ["worried", "concerned", "anxious"]):
            detected_emotions.append("concerned")
        if any(kw in message_lower for kw in ["excited", "can't wait", "looking forward"]):
            detected_emotions.append("excited")
        if any(kw in message_lower for kw in ["confused", "don't understand", "unclear"]):
            detected_emotions.append("confused")
        
        return {
            "sentiment": sentiment,
            "polarity": polarity,
            "confidence": confidence,
            "detected_emotions": detected_emotions,
            "method": "keyword_analysis",
            "frustration_level": min(frustrated_score * 3, 10),
            "engagement_level": max(positive_score + excited_score, min(5, len(message.split()) / 3))
        }
    
    async def analyze_sentiment_gpt(
        self,
        message: str,
        conversation_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Deep sentiment analysis using GPT-4 (accurate, requires API call)
        
        Args:
            message: User message to analyze
            conversation_context: Previous conversation context
        
        Returns:
            Detailed sentiment analysis
        """
        # Check cache first
        cache_key = f"{message}_{conversation_context[:50] if conversation_context else ''}"
        if cache_key in self.sentiment_cache:
            logger.debug("Using cached sentiment analysis")
            return self.sentiment_cache[cache_key]
        
        context_info = f"\nContext: {conversation_context}" if conversation_context else ""
        
        prompt = f"""Analyze the sentiment and emotions in this customer message from a real estate conversation:

Message: "{message}"{context_info}

Provide a detailed sentiment analysis in JSON format:
{{
    "sentiment": "excited|positive|neutral|negative|frustrated",
    "detected_emotions": ["happy", "uncertain", "concerned", "confused", "interested"],
    "frustration_level": 0-10,
    "urgency_level": 0-10,
    "engagement_level": 0-10,
    "polarity": -1.0 to 1.0,
    "confidence": 0.0-1.0,
    "reasoning": "brief explanation of sentiment analysis",
    "key_indicators": ["specific words/phrases that indicate sentiment"]
}}

Important:
- frustration_level > 7 means immediate attention needed
- urgency_level > 7 means ready to take action
- engagement_level reflects how invested they are in the conversation"""

        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing customer sentiment in sales conversations. Provide accurate, actionable sentiment analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=400
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Add method indicator
            result["method"] = "gpt_analysis"
            
            # Cache result
            self.sentiment_cache[cache_key] = result
            
            # Limit cache size
            if len(self.sentiment_cache) > 100:
                # Remove oldest entry
                self.sentiment_cache.pop(next(iter(self.sentiment_cache)))
            
            logger.info(f"GPT sentiment analysis: {result['sentiment']} (confidence: {result['confidence']})")
            
            return result
            
        except Exception as e:
            logger.error(f"GPT sentiment analysis failed: {e}, falling back to quick analysis")
            return self.analyze_sentiment_quick(message)
    
    def get_tone_adjustment(self, sentiment: str, frustration_level: int = 0) -> Dict[str, Any]:
        """
        Get tone adjustments based on sentiment
        
        Args:
            sentiment: Detected sentiment category
            frustration_level: Frustration score (0-10)
        
        Returns:
            Tone adjustment recommendations
        """
        tone_map = {
            "frustrated": {
                "empathy_level": "very_high",
                "formality": "respectful_professional",
                "urgency_response": "immediate_help_offer",
                "response_style": "apologetic_solution_focused",
                "suggested_actions": [
                    "offer_human_escalation",
                    "acknowledge_specific_concern",
                    "provide_immediate_solution",
                    "avoid_generic_responses"
                ],
                "avoid": [
                    "lengthy_explanations",
                    "technical_jargon",
                    "additional_questions"
                ],
                "prompt_additions": [
                    "Show deep empathy and understanding",
                    "Acknowledge their frustration explicitly",
                    "Offer immediate, concrete solutions",
                    "Suggest speaking with a senior consultant if needed"
                ]
            },
            "negative": {
                "empathy_level": "high",
                "formality": "professional_warm",
                "urgency_response": "address_concern_thoroughly",
                "response_style": "reassuring_informative",
                "suggested_actions": [
                    "ask_clarifying_questions",
                    "provide_detailed_explanations",
                    "offer_alternatives",
                    "build_confidence"
                ],
                "avoid": [
                    "dismissing_concerns",
                    "over_optimism",
                    "rushing_to_close"
                ],
                "prompt_additions": [
                    "Address their concerns with empathy",
                    "Provide thorough, honest information",
                    "Build trust through transparency",
                    "Offer reassurance with facts"
                ]
            },
            "neutral": {
                "empathy_level": "moderate",
                "formality": "friendly_professional",
                "urgency_response": "normal_informative",
                "response_style": "balanced_helpful",
                "suggested_actions": [
                    "continue_conversation_naturally",
                    "provide_relevant_information",
                    "gauge_interest_level"
                ],
                "avoid": [
                    "being_too_casual",
                    "over_selling",
                    "lengthy_monologues"
                ],
                "prompt_additions": [
                    "Maintain professional yet friendly tone",
                    "Provide clear, concise information",
                    "Ask appropriate follow-up questions"
                ]
            },
            "positive": {
                "empathy_level": "moderate",
                "formality": "enthusiastic_professional",
                "urgency_response": "capitalize_on_interest",
                "response_style": "confident_engaging",
                "suggested_actions": [
                    "build_on_enthusiasm",
                    "show_additional_value",
                    "suggest_next_steps",
                    "create_momentum"
                ],
                "avoid": [
                    "being_pushy",
                    "over_promising",
                    "losing_momentum"
                ],
                "prompt_additions": [
                    "Match their enthusiasm",
                    "Highlight additional benefits",
                    "Suggest concrete next steps (site visit)",
                    "Create sense of excitement"
                ]
            },
            "excited": {
                "empathy_level": "high",
                "formality": "enthusiastic_warm",
                "urgency_response": "close_deal_naturally",
                "response_style": "energetic_action_oriented",
                "suggested_actions": [
                    "immediate_site_visit_offer",
                    "booking_opportunity",
                    "create_urgency_naturally",
                    "make_decision_easy"
                ],
                "avoid": [
                    "over_complicating",
                    "introducing_doubts",
                    "delaying_action"
                ],
                "prompt_additions": [
                    "Share their excitement genuinely",
                    "Move quickly to concrete actions",
                    "Make booking/scheduling very easy",
                    "Highlight perfect timing and fit"
                ]
            }
        }
        
        adjustment = tone_map.get(sentiment, tone_map["neutral"])
        
        # Add escalation flag if frustration is high
        if frustration_level >= 7:
            adjustment["escalation_recommended"] = True
            adjustment["escalation_message"] = (
                "I sense you have some concerns that deserve immediate attention. "
                "Would you like to speak with our senior consultant right now? "
                "They can provide personalized assistance."
            )
        
        return adjustment
    
    def should_escalate_to_human(
        self,
        sentiment: str,
        frustration_level: int,
        conversation_length: int
    ) -> tuple[bool, str]:
        """
        Determine if conversation should be escalated to human
        
        Args:
            sentiment: Current sentiment
            frustration_level: Frustration score (0-10)
            conversation_length: Number of messages in conversation
        
        Returns:
            (should_escalate: bool, reason: str)
        """
        # Critical: High frustration
        if frustration_level >= 8:
            return True, "high_frustration"
        
        # High: Frustrated and long conversation
        if sentiment == "frustrated" and conversation_length >= 5:
            return True, "persistent_frustration"
        
        # Medium: Negative sentiment and long conversation
        if sentiment == "negative" and conversation_length >= 10:
            return True, "prolonged_negative_experience"
        
        # Medium: Multiple escalation requests
        # (This would be checked at a higher level)
        
        return False, ""
    
    def generate_empathy_statement(
        self,
        sentiment: str,
        detected_emotions: List[str],
        specific_concern: Optional[str] = None
    ) -> str:
        """
        Generate appropriate empathy statement based on sentiment
        
        Args:
            sentiment: Detected sentiment
            detected_emotions: List of detected emotions
            specific_concern: Specific concern mentioned (e.g., "budget", "location")
        
        Returns:
            Empathy statement to prepend to response
        """
        empathy_map = {
            "frustrated": [
                "I completely understand your frustration, and I sincerely apologize.",
                "I hear you, and your concern is absolutely valid. Let me help fix this right away.",
                "I'm truly sorry you're experiencing this. Your time is valuable."
            ],
            "negative": [
                "I understand your concern, and I appreciate you sharing this with me.",
                "That's a very valid point, and I want to address it thoroughly.",
                "I hear what you're saying, and let's work through this together."
            ],
            "uncertain": [
                "I can see you have some questions, and that's completely natural.",
                "It's great that you're thinking this through carefully.",
                "I'm here to help clarify anything that's unclear."
            ],
            "positive": [
                "I'm glad you're finding this helpful!",
                "That's great to hear!",
                "I'm excited to help you with this!"
            ],
            "excited": [
                "I love your enthusiasm!",
                "This is exciting! Let's make this happen.",
                "Your excitement is contagious!"
            ]
        }
        
        # Select appropriate statement
        if "uncertain" in detected_emotions or "confused" in detected_emotions:
            base_statement = empathy_map.get("uncertain", ["I understand."])[0]
        else:
            statements = empathy_map.get(sentiment, ["I understand."])
            import random
            base_statement = random.choice(statements)
        
        # Add specific concern acknowledgment
        if specific_concern:
            concern_map = {
                "budget": "Budget is one of the most important factors in this decision.",
                "location": "Location is absolutely critical, and I understand your concern.",
                "timing": "Timing is everything, and I appreciate you being thoughtful about this.",
                "quality": "Quality concerns are completely valid, especially for such an important investment."
            }
            if specific_concern in concern_map:
                base_statement += " " + concern_map[specific_concern]
        
        return base_statement


# Singleton instance
_sentiment_analyzer_instance = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get singleton instance of SentimentAnalyzer"""
    global _sentiment_analyzer_instance
    if _sentiment_analyzer_instance is None:
        _sentiment_analyzer_instance = SentimentAnalyzer()
    return _sentiment_analyzer_instance
