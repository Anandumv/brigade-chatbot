"""
Comprehensive Context Understanding Service
Builds rich context from session, conversation history, and query for ALL query types.
"""

import logging
from typing import Dict, List, Any, Optional
from services.session_manager import ConversationSession

logger = logging.getLogger(__name__)


class ContextUnderstandingService:
    """
    Service to build comprehensive context for understanding ANY query.
    Extracts all relevant information from session, conversation history, and query.
    """
    
    def __init__(self):
        pass
    
    def build_comprehensive_context(
        self,
        query: str,
        session: Optional[ConversationSession],
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Build comprehensive context for understanding ANY query.
        
        Returns:
            Dict with all context information needed for intent classification and response generation
        """
        context = {
            "query": query,
            "query_lower": query.lower(),
            "session": {},
            "conversation": {},
            "projects": {},
            "requirements": {},
            "inferred_intent_hints": []
        }
        
        if not session:
            return context
        
        # 1. SESSION CONTEXT
        context["session"] = {
            "session_id": session.session_id if hasattr(session, 'session_id') else None,
            "last_intent": session.last_intent if hasattr(session, 'last_intent') else None,
            "last_topic": session.last_topic if hasattr(session, 'last_topic') else None,
            "conversation_phase": session.conversation_phase if hasattr(session, 'conversation_phase') else None,
            "message_count": len(session.messages) if hasattr(session, 'messages') and session.messages else 0
        }
        
        # 2. PROJECT CONTEXT
        context["projects"] = {
            "last_shown": [],
            "interested": [],
            "selected": None,
            "mentioned_in_query": self._extract_project_mentions(query)
        }
        
        if hasattr(session, 'last_shown_projects') and session.last_shown_projects:
            context["projects"]["last_shown"] = [
                {
                    "name": p.get('name') if isinstance(p, dict) else str(p),
                    "location": p.get('location') if isinstance(p, dict) else None,
                    "price": p.get('budget_min') if isinstance(p, dict) else None,
                    "config": p.get('configuration') if isinstance(p, dict) else None
                }
                for p in session.last_shown_projects[:5]  # Last 5 shown
            ]
        
        if hasattr(session, 'interested_projects') and session.interested_projects:
            context["projects"]["interested"] = session.interested_projects[-3:]  # Last 3 interested
            context["projects"]["selected"] = session.interested_projects[-1] if session.interested_projects else None
        
        # 3. REQUIREMENTS CONTEXT
        context["requirements"] = {}
        if hasattr(session, 'current_filters') and session.current_filters:
            filters = session.current_filters
            context["requirements"] = {
                "budget_max": filters.get('budget_max') or filters.get('max_price_inr'),
                "budget_min": filters.get('budget_min') or filters.get('min_price_inr'),
                "location": filters.get('location') or filters.get('locality') or filters.get('area'),
                "configuration": filters.get('configuration') or filters.get('bedrooms'),
                "possession": filters.get('possession_year')
            }
        
        # 4. CONVERSATION HISTORY CONTEXT
        context["conversation"] = {
            "recent_messages": [],
            "mentioned_locations": [],
            "mentioned_budgets": [],
            "mentioned_configs": [],
            "topics_discussed": []
        }
        
        if conversation_history:
            # Extract from last 10 messages
            recent = conversation_history[-10:]
            context["conversation"]["recent_messages"] = [
                {"role": msg.get("role"), "content": msg.get("content", "")[:200]}  # Truncate for context
                for msg in recent
            ]
            
            # Extract entities from conversation
            for msg in recent:
                content = msg.get("content", "").lower()
                
                # Extract locations
                locations = self._extract_locations_from_text(content)
                context["conversation"]["mentioned_locations"].extend(locations)
                
                # Extract budgets
                budgets = self._extract_budgets_from_text(content)
                context["conversation"]["mentioned_budgets"].extend(budgets)
                
                # Extract configs
                configs = self._extract_configs_from_text(content)
                context["conversation"]["mentioned_configs"].extend(configs)
        
        # Remove duplicates
        context["conversation"]["mentioned_locations"] = list(set(context["conversation"]["mentioned_locations"]))
        context["conversation"]["mentioned_budgets"] = list(set(context["conversation"]["mentioned_budgets"]))
        context["conversation"]["mentioned_configs"] = list(set(context["conversation"]["mentioned_configs"]))
        
        # 5. INFERRED INTENT HINTS
        context["inferred_intent_hints"] = self._infer_intent_hints(query, context)
        
        return context
    
    def _extract_project_mentions(self, query: str) -> List[str]:
        """Extract potential project name mentions from query."""
        # This is a simple extraction - GPT will do better matching
        # But we can extract obvious patterns
        mentions = []
        query_lower = query.lower()
        
        # Common project name patterns
        project_keywords = ["citrine", "avalon", "green vista", "minara", "glenbrook", "brigade", "prestige"]
        for keyword in project_keywords:
            if keyword in query_lower:
                mentions.append(keyword)
        
        return mentions
    
    def _extract_locations_from_text(self, text: str) -> List[str]:
        """Extract location mentions from text."""
        locations = []
        text_lower = text.lower()
        
        bangalore_locations = [
            "whitefield", "sarjapur", "electronic city", "hebbal", "yeshwantpur",
            "koramangala", "indiranagar", "jayanagar", "hsr", "btm", "marathahalli",
            "bellandur", "outer ring road", "orr", "bannerghatta", "hennur", "yelahanka",
            "devanahalli", "kengeri", "jp nagar", "mg road", "brigade road",
            "rajajinagar", "malleshwaram", "basavanagudi", "kr puram", "varthur",
            "chandapura", "hosur road", "old madras road", "tumkur road", "mysore road",
            "kanakpura road", "north bangalore", "south bangalore", "east bangalore",
            "west bangalore", "central bangalore", "bagalur", "thanisandra"
        ]
        
        for loc in bangalore_locations:
            if loc in text_lower:
                locations.append(loc.title())
        
        return locations
    
    def _extract_budgets_from_text(self, text: str) -> List[str]:
        """Extract budget mentions from text."""
        import re
        budgets = []
        
        # Patterns: "1.5 cr", "2 crore", "150 lakhs", "under 2 cr"
        patterns = [
            r'(\d+\.?\d*)\s*(?:cr|crore|crores)',
            r'(\d+\.?\d*)\s*(?:lakh|lakhs)',
            r'under\s+(\d+\.?\d*)',
            r'around\s+(\d+\.?\d*)',
            r'upto\s+(\d+\.?\d*)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text.lower())
            budgets.extend(matches)
        
        return budgets
    
    def _extract_configs_from_text(self, text: str) -> List[str]:
        """Extract configuration mentions from text."""
        import re
        configs = []
        
        # Patterns: "2 bhk", "3bhk", "2.5 BHK"
        pattern = r'(\d+\.?\d*)\s*bhk'
        matches = re.findall(pattern, text.lower())
        configs.extend([f"{m}BHK" for m in matches])
        
        return configs
    
    def _infer_intent_hints(self, query: str, context: Dict[str, Any]) -> List[str]:
        """Infer intent hints from query and context."""
        hints = []
        query_lower = query.lower()
        
        # Check for vague queries that need context
        vague_patterns = ["more", "tell me more", "details", "about it", "what about", "how about"]
        if any(pattern in query_lower for pattern in vague_patterns):
            if context["projects"]["last_shown"]:
                hints.append("likely_about_last_shown_project")
            if context["projects"]["selected"]:
                hints.append("likely_about_selected_project")
        
        # Check for follow-up questions
        followup_patterns = ["also", "and", "what else", "anything else", "other", "another"]
        if any(pattern in query_lower for pattern in followup_patterns):
            hints.append("follow_up_query")
        
        # Check for comparison
        comparison_patterns = ["compare", "vs", "versus", "difference", "better", "which"]
        if any(pattern in query_lower for pattern in comparison_patterns):
            hints.append("comparison_query")
        
        # Check for search
        search_patterns = ["show", "find", "search", "looking for", "need", "want"]
        if any(pattern in query_lower for pattern in search_patterns):
            hints.append("search_query")
        
        # Check for price/budget questions
        price_patterns = ["price", "cost", "budget", "expensive", "affordable", "minimum", "maximum"]
        if any(pattern in query_lower for pattern in price_patterns):
            hints.append("price_query")
        
        # Check for location questions
        location_patterns = ["location", "where", "near", "nearby", "distance", "far"]
        if any(pattern in query_lower for pattern in location_patterns):
            hints.append("location_query")
        
        return hints
    
    def enrich_query_with_context(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> str:
        """
        Enrich query with context information for better understanding.
        Auto-completes incomplete queries.
        """
        enriched = query
        query_lower = query.lower()
        
        # If query is very vague, add context
        vague_patterns = ["more", "details", "about it", "tell me", "what about"]
        if any(pattern in query_lower for pattern in vague_patterns):
            # Add project context if available
            if context.get("projects", {}).get("selected"):
                selected = context["projects"]["selected"]
                if isinstance(selected, dict):
                    enriched = f"{query} about {selected.get('name', selected)}"
                else:
                    enriched = f"{query} about {selected}"
            elif context.get("projects", {}).get("last_shown"):
                last_project = context["projects"]["last_shown"][0]
                enriched = f"{query} about {last_project.get('name') if isinstance(last_project, dict) else last_project}"
            # Add topic context if available
            elif context.get("session", {}).get("last_topic"):
                enriched = f"{query} regarding {context['session']['last_topic']}"
        
        # If query mentions "these" or "those", add location/project context
        if "these" in query_lower or "those" in query_lower:
            if context["conversation"]["mentioned_locations"]:
                locations = ", ".join(context["conversation"]["mentioned_locations"][:2])
                enriched = f"{query} in {locations}"
        
        # If query asks for "nearby" or "more nearby", add location context
        if "nearby" in query_lower or "near" in query_lower:
            if context["conversation"]["mentioned_locations"]:
                location = context["conversation"]["mentioned_locations"][-1]
                enriched = f"{query} near {location}"
            elif context["requirements"].get("location"):
                enriched = f"{query} near {context['requirements']['location']}"
        
        return enriched


# Global instance
context_understanding = ContextUnderstandingService()
