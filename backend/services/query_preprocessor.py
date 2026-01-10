import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class QueryPreprocessor:
    """
    Preprocesses and normalizes user queries to improve intent classification and retrieval.
    Handles informal language, abbreviations, and common typos.
    """
    
    def __init__(self):
        # Common real estate abbreviations
        self.abbreviations: Dict[str, str] = {
            "cr": "crore",
            "l": "lakh",
            "lac": "lakh",
            "lacs": "lakhs",
            "k": "thousand",
            "blr": "bangalore",
            "b'lore": "bangalore",
            "wfield": "whitefield",
            "pos": "possession",
            "rdy": "ready",
            "apt": "apartment",
            "config": "configuration",
            "spec": "specification",
            "ami": "amenities",
            "loc": "location",
            "prc": "price",
            "nr": "near",
            "opp": "opposite",
            "avail": "available",
            "min": "minimum",
            "max": "maximum",
            "sqft": "sq ft",
            "sft": "sq ft",
        }
        
        # Informal phrasing cleanups
        self.phrase_mappings = [
            (r"\b(u|yu)\b", "you"),
            (r"\b(r|ar)\b", "are"),
            (r"\b(d|da)\b", "the"),
            (r"\b(hw)\b", "how"),
            (r"\b(wht|wat)\b", "what"),
            (r"\b(whr)\b", "where"),
            (r"\b(plz|pls)\b", "please"),
            (r"\b(thx|tnx|tks)\b", "thanks"),
            (r"\b(info)\b", "information"),
            (r"\b(dtls|det)\b", "details"),
            (r"\b(abt)\b", "about"),
            (r"\b(chk)\b", "check"),
            (r"\b(lk)\b", "look"),
            (r"\b(gud)\b", "good"),
            (r"\b(bttr)\b", "better"),
        ]

    def preprocess(self, query: str) -> str:
        """
        Normalize query string.
        1. Lowercase
        2. Expand abbreviations
        3. Fix common informal phrasing
        4. Normalize whitespace
        """
        if not query:
            return ""
            
        processed = query.lower().strip()
        
        # 1. Expand standard abbreviations (matches whole words)
        words = processed.split()
        normalized_words = [self.abbreviations.get(w, w) for w in words]
        processed = " ".join(normalized_words)
        
        # 2. Fix informal phrases via regex
        for pattern, replacement in self.phrase_mappings:
            processed = re.sub(pattern, replacement, processed)
            
        # 3. Clean up BHK formats (e.g. "2 bhk" -> "2bhk", "3-bhk" -> "3bhk")
        processed = re.sub(r'(\d+)\s*-?\s*bhk', r'\1bhk', processed)
        
        # 4. Clean up price formats (e.g. "1.5 cr" -> "1.5 crore")
        processed = re.sub(r'(\d+(\.\d+)?)\s*cr\b', r'\1 crore', processed)
        
        # Remove extra whitespace
        processed = re.sub(r'\s+', ' ', processed).strip()
        
        if processed != query.lower().strip():
            logger.info(f"Normalized query: '{query}' -> '{processed}'")
            
        return processed

# Singleton instance
query_preprocessor = QueryPreprocessor()
