"""
Fuzzy Project Name Matcher
Matches partial, misspelled, or informal project names to actual project names in database.
"""

import logging
import difflib
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Known project name mappings (partial → full name)
# This list should be expanded based on actual projects in database
PROJECT_NAME_MAPPINGS = {
    # Brigade projects
    "avalon": "Brigade Avalon",
    "citrine": "Brigade Citrine",
    "folium": "Brigade Folium",
    "neopolis": "Brigade Neopolis",
    "lakefront": "Brigade Lakefront",
    "ozone": "Brigade Ozone",
    "cornerstone": "Brigade Cornerstone",
    "orchards": "Brigade Orchards",
    "utopia": "Brigade Utopia",
    "atmosphere": "Brigade Atmosphere",
    "palmsprings": "Brigade Palm Springs",
    "palm springs": "Brigade Palm Springs",
    "eldorado": "Brigade El Dorado",
    "el dorado": "Brigade El Dorado",
    "wisteria": "Brigade Wisteria",
    "meadows": "Brigade Meadows",
    "sanctuary": "Brigade Sanctuary",
    "caladium": "Brigade Caladium",
    "xanadu": "Brigade Xanadu",
    "panorama": "Brigade Panorama",
    "calista": "Brigade Calista",
    
    # Sobha projects
    "sobha dream": "Sobha Dream Acres",
    "dream acres": "Sobha Dream Acres",
    "sobha neopolis": "Sobha Neopolis",
    "sobha city": "Sobha City",
    "royal pavilion": "Sobha Royal Pavilion",
    
    # Prestige projects
    "prestige city": "Prestige City",
    "prestige falcon": "Prestige Falcon City",
    "prestige lakeside": "Prestige Lakeside Habitat",
    
    # Mana projects
    "mana skanda": "Mana Skanda",
    "skanda": "Mana Skanda",
    "mana tropicale": "Mana Tropicale",
    "tropicale": "Mana Tropicale",
    
    # Common misspellings
    "avlon": "Brigade Avalon",
    "citrne": "Brigade Citrine",
    "citrin": "Brigade Citrine",
    "folim": "Brigade Folium",
    "foliom": "Brigade Folium",
}


def extract_project_name_from_query(query: str, known_projects: Optional[List[str]] = None) -> Optional[str]:
    """
    Extract project name from a query using fuzzy matching.
    
    Args:
        query: User's query text
        known_projects: List of known project names from database
        
    Returns:
        Best matching project name or None
    """
    query_lower = query.lower().strip()
    
    # 1. Check direct mappings first (fastest)
    for partial, full in PROJECT_NAME_MAPPINGS.items():
        if partial in query_lower:
            logger.info(f"Fuzzy match (direct): '{partial}' -> '{full}'")
            return full
    
    # 2. If we have known projects from database, do fuzzy matching
    if known_projects:
        # Extract potential project words from query (skip common words)
        skip_words = {'need', 'details', 'of', 'about', 'tell', 'me', 'more', 'give', 'show', 
                      'the', 'please', 'want', 'info', 'information', 'on', 'for', 'project',
                      'full', 'complete', 'all', 'get', 'find', 'search'}
        
        query_words = [w for w in query_lower.split() if w not in skip_words and len(w) > 2]
        
        for word in query_words:
            # Try fuzzy match against all known project names
            for project in known_projects:
                project_lower = project.lower()
                # Check if word matches any part of project name
                project_words = project_lower.split()
                
                for proj_word in project_words:
                    # Exact substring match
                    if word in proj_word or proj_word in word:
                        logger.info(f"Fuzzy match (substring): '{word}' in '{project}'")
                        return project
                    
                    # Fuzzy match with high cutoff
                    close_matches = difflib.get_close_matches(word, [proj_word], n=1, cutoff=0.75)
                    if close_matches:
                        logger.info(f"Fuzzy match (difflib): '{word}' -> '{close_matches[0]}' in '{project}'")
                        return project
    
    return None


def get_project_from_database(project_name: str) -> Optional[Dict]:
    """
    Get project details from database by name (with fuzzy matching).
    
    Args:
        project_name: Project name (can be partial)
        
    Returns:
        Project dict or None
    """
    try:
        from database.pixeltable_setup import get_projects_table
        projects_table = get_projects_table()
        
        if not projects_table:
            # Fall back to mock data
            from services.hybrid_retrieval import hybrid_retrieval
            mock_projects = hybrid_retrieval._get_mock_data()
            
            for project in mock_projects:
                if project_name.lower() in project.get('name', '').lower():
                    return project
                # Fuzzy match
                close = difflib.get_close_matches(
                    project_name.lower(), 
                    [project.get('name', '').lower()], 
                    n=1, 
                    cutoff=0.6
                )
                if close:
                    return project
            return None
        
        # Query database
        results = list(projects_table.where(
            projects_table.name.contains(project_name)
        ).limit(1).collect())
        
        if results:
            return dict(results[0])
        
        # Try fuzzy match on all projects
        all_projects = list(projects_table.limit(100).collect())
        for project in all_projects:
            proj_name = project.get('name', '')
            if project_name.lower() in proj_name.lower():
                return dict(project)
            close = difflib.get_close_matches(
                project_name.lower(),
                [proj_name.lower()],
                n=1,
                cutoff=0.6
            )
            if close:
                return dict(project)
                
        return None
        
    except Exception as e:
        logger.error(f"Error getting project from database: {e}")
        return None


def is_project_detail_request(query: str) -> bool:
    """
    Check if the query is asking for project details.
    """
    query_lower = query.lower()
    
    detail_patterns = [
        "details of",
        "details about", 
        "about ",
        "info on",
        "info about",
        "information about",
        "tell me about",
        "more about",
        "more details",
        "more info",
        "full details",
        "complete details",
        "give me details",
        "need details",
        "want details",
        "show me ",
    ]
    
    return any(pattern in query_lower for pattern in detail_patterns)
