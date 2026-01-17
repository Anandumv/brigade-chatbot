"""
Project Fact Extractor Service

Fetches REAL data from database for factual queries about projects.
NEVER invents or estimates - returns actual database facts only.
"""

import logging
import re
from typing import Dict, Optional, List
from database.pixeltable_setup import get_projects_table

logger = logging.getLogger(__name__)


def extract_carpet_area_from_config(configuration: str, bhk: str = None) -> Dict[str, any]:
    """
    Extract carpet area information from configuration string.
    
    Configuration format examples:
    - "{2BHK, 1127 - 1461, 2.20Cr}, {3BHK, 1650 - 1850, 3.50Cr}"
    - "2 BHK: 1200-1400 sqft, 3 BHK: 1600-1800 sqft"
    
    Returns dict with min_sqft, max_sqft, and configuration type
    """
    if not configuration:
        return None
    
    results = []
    
    # Pattern 1: {2BHK, 1127 - 1461, 2.20Cr}
    pattern1 = r'\{([0-9.]+\s*BHK),\s*([0-9]+)\s*-\s*([0-9]+)'
    matches1 = re.findall(pattern1, configuration, re.IGNORECASE)
    
    for match in matches1:
        config_type = match[0].strip()
        min_area = int(match[1])
        max_area = int(match[2])
        
        results.append({
            "configuration": config_type,
            "carpet_area_min": min_area,
            "carpet_area_max": max_area,
            "area_range": f"{min_area} - {max_area} sq ft"
        })
    
    # Pattern 2: 2 BHK: 1200-1400 sqft
    pattern2 = r'([0-9.]+\s*BHK)[:\s]+([0-9]+)\s*-\s*([0-9]+)'
    matches2 = re.findall(pattern2, configuration, re.IGNORECASE)
    
    for match in matches2:
        config_type = match[0].strip()
        min_area = int(match[1])
        max_area = int(match[2])
        
        results.append({
            "configuration": config_type,
            "carpet_area_min": min_area,
            "carpet_area_max": max_area,
            "area_range": f"{min_area} - {max_area} sq ft"
        })
    
    # Filter by BHK type if specified
    if bhk:
        bhk_normalized = bhk.upper().replace(" ", "")
        results = [r for r in results if bhk_normalized in r["configuration"].upper().replace(" ", "")]
    
    return results if results else None


def get_project_fact(project_name: str, fact_type: str, bhk_type: str = None) -> Optional[Dict]:
    """
    Fetch actual facts from database for a specific project.
    
    Args:
        project_name: Name of the project (e.g., "Sobha Neopolis", "Birla Evara")
        fact_type: Type of fact requested - "carpet_area", "price", "possession", "rera", "amenities", "location"
        bhk_type: Optional BHK configuration (e.g., "2BHK", "3BHK")
    
    Returns:
        Dict with actual database facts, or None if not found
    """
    try:
        projects_table = get_projects_table()
        
        # Query for the specific project
        results = list(projects_table.where(
            projects_table.name.contains(project_name)
        ).limit(1).collect())
        
        if not results:
            logger.warning(f"Project not found in database: {project_name}")
            return None
        
        project = results[0]
        
        # Extract the requested fact
        if fact_type == "carpet_area":
            config_data = extract_carpet_area_from_config(
                project.get('configuration', ''),
                bhk_type
            )
            
            if config_data:
                return {
                    "project_name": project.get('name'),
                    "fact_type": "carpet_area",
                    "bhk_type": bhk_type,
                    "configurations": config_data,
                    "source": "database"
                }
            else:
                return {
                    "project_name": project.get('name'),
                    "fact_type": "carpet_area",
                    "raw_configuration": project.get('configuration'),
                    "message": "Configuration available but carpet area not specified in standard format",
                    "source": "database"
                }
        
        elif fact_type == "price":
            budget_min = project.get('budget_min', 0) / 100  # Convert to Cr
            budget_max = project.get('budget_max', 0) / 100
            
            return {
                "project_name": project.get('name'),
                "fact_type": "price",
                "price_range": f"₹{budget_min:.2f} - ₹{budget_max:.2f} Cr",
                "price_min_cr": budget_min,
                "price_max_cr": budget_max,
                "source": "database"
            }
        
        elif fact_type == "possession":
            return {
                "project_name": project.get('name'),
                "fact_type": "possession",
                "possession_quarter": project.get('possession_quarter'),
                "possession_year": project.get('possession_year'),
                "possession": f"{project.get('possession_quarter', '')} {project.get('possession_year', '')}".strip(),
                "source": "database"
            }
        
        elif fact_type == "rera":
            return {
                "project_name": project.get('name'),
                "fact_type": "rera",
                "rera_number": project.get('rera_number'),
                "source": "database"
            }
        
        elif fact_type == "amenities":
            return {
                "project_name": project.get('name'),
                "fact_type": "amenities",
                "amenities": project.get('amenities'),
                "source": "database"
            }
        
        elif fact_type == "location":
            return {
                "project_name": project.get('name'),
                "fact_type": "location",
                "location": project.get('location'),
                "zone": project.get('zone'),
                "source": "database"
            }
        
        elif fact_type == "developer":
            return {
                "project_name": project.get('name'),
                "fact_type": "developer",
                "developer": project.get('developer'),
                "source": "database"
            }
        
        elif fact_type == "status":
            return {
                "project_name": project.get('name'),
                "fact_type": "status",
                "status": project.get('status'),
                "source": "database"
            }
        
        else:
            # Return all facts
            return {
                "project_name": project.get('name'),
                "fact_type": "all",
                "data": project,
                "source": "database"
            }
    
    except Exception as e:
        logger.error(f"Error fetching project fact: {e}")
        return None


def detect_project_fact_query(query: str) -> Optional[Dict]:
    """
    Detect if a query is asking for specific facts about a project.
    
    Returns dict with project_name, fact_type, and bhk_type if detected, else None
    """
    query_lower = query.lower()
    
    # Fact type patterns
    fact_patterns = {
        "carpet_area": ["carpet", "carpet area", "carpet size", "area", "size", "sqft", "square feet"],
        "price": ["price", "cost", "budget", "how much", "pricing"],
        "possession": ["possession", "possession date", "ready", "handover", "completion"],
        "rera": ["rera", "rera number", "registration"],
        "amenities": ["amenities", "facilities", "features"],
        "location": ["location", "where", "address", "located"],
        "developer": ["developer", "builder", "who built", "who is developing"],
        "status": ["status", "under construction", "ready to move", "rtmi"]
    }
    
    # Project name patterns (common projects)
    project_keywords = {
        "sobha neopolis": ["sobha neopolis", "neopolis", "sobha neo"],
        "birla evara": ["birla evara", "evara", "birla ev"],
        "brigade citrine": ["brigade citrine", "citrine"],
        "brigade avalon": ["brigade avalon", "avalon"],
        "godrej woods": ["godrej woods", "woods"],
        "godrej eden": ["godrej eden", "eden"],
        "prestige": ["prestige"],
        "sobha": ["sobha"],
        "brigade": ["brigade"]
    }
    
    # BHK type patterns
    bhk_pattern = r'([0-9.]+)\s*BHK'
    bhk_match = re.search(bhk_pattern, query, re.IGNORECASE)
    bhk_type = bhk_match.group(0) if bhk_match else None
    
    # Detect project name
    detected_project = None
    for project_name, keywords in project_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            detected_project = project_name.title()
            break
    
    # Detect fact type
    detected_fact = None
    for fact_type, keywords in fact_patterns.items():
        if any(keyword in query_lower for keyword in keywords):
            detected_fact = fact_type
            break
    
    # Only return if we detected both project and fact type
    if detected_project and detected_fact:
        return {
            "project_name": detected_project,
            "fact_type": detected_fact,
            "bhk_type": bhk_type,
            "is_factual_query": True
        }
    
    return None


def format_fact_response(fact_data: Dict, query: str) -> str:
    """
    Format database facts into a natural response.
    Uses ONLY database data, never invents information.
    """
    if not fact_data or fact_data.get("source") != "database":
        return None
    
    project_name = fact_data.get("project_name")
    fact_type = fact_data.get("fact_type")
    
    if fact_type == "carpet_area":
        if "configurations" in fact_data and fact_data["configurations"]:
            configs = fact_data["configurations"]
            response_parts = [f"Based on **actual data** from our database for **{project_name}**:\n"]
            
            for config in configs:
                response_parts.append(
                    f"\n• **{config['configuration']}**: {config['area_range']} (carpet area)"
                )
            
            response_parts.append(f"\n\n_Note: These are actual sizes from the developer's specifications, not estimates._")
            response_parts.append(f"\n\nWould you like to know more about pricing, amenities, or schedule a site visit?")
            
            return "".join(response_parts)
        else:
            return f"I found **{project_name}** in our database, but the exact carpet area details are not specified in a standard format.\n\nI recommend connecting with the developer directly for precise measurements, or I can schedule a site visit for you to see the actual units."
    
    elif fact_type == "price":
        return f"**{project_name}** - Price Range (from database):\n\n💰 **{fact_data['price_range']}**\n\n_This is the actual price range from our verified listings._\n\nWould you like to know about EMI options or schedule a site visit?"
    
    elif fact_type == "possession":
        return f"**{project_name}** - Possession Details (from database):\n\n📅 **{fact_data['possession']}**\n\nWould you like more details about the project status or payment plans?"
    
    elif fact_type == "rera":
        return f"**{project_name}** - RERA Registration (from database):\n\n🛡️ **{fact_data['rera_number']}**\n\n_RERA registration ensures legal compliance and buyer protection._"
    
    elif fact_type == "location":
        return f"**{project_name}** - Location (from database):\n\n📍 **{fact_data['location']}**\n\nWould you like to know about connectivity, nearby amenities, or schedule a site visit?"
    
    else:
        return None
