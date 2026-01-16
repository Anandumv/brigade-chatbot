import sys
import os
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from services.intent_classifier import IntentClassifier

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_queries():
    classifier = IntentClassifier()
    
    queries = [
        "Brigade avlon",
        "help me pitch Brigade avalon",
        "pitch me SBR Minara",
        "tell me about sobha neopolis"
    ]
    
    print("\n--- Testing Intent Classification ---")
    for q in queries:
        intent = classifier.classify_intent(q)
        print(f"Query: '{q}' -> Intent: '{intent}'")

if __name__ == "__main__":
    test_queries()
