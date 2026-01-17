import math
from typing import Dict, Tuple, Optional

# Representative coordinates for Bangalore micro-locations
BANGALORE_COORDINATES: Dict[str, Tuple[float, float]] = {
    "whitefield": (12.9698, 77.7500),
    "sarjapur road": (12.9100, 77.6800),
    "sarjapur": (12.8600, 77.7800),
    "panathur": (12.9240, 77.7118),
    "marathahalli": (12.9591, 77.6974),
    "koramangala": (12.9352, 77.6245),
    "bellandur": (12.9304, 77.6784),
    "hebbal": (13.0354, 77.5988),
    "devanahalli": (13.2484, 77.7137),
    "yelahanka": (13.1007, 77.5963),
    "bagalur": (13.1332, 77.6685),
    "thanisandra": (13.0582, 77.6333),
    "hennur": (13.0258, 77.6305),
    "budigere cross": (13.0560, 77.7470),
    "marathahalli bridge": (12.9562, 77.7011),
    "jayanagar": (12.9290, 77.5829),
    "hsr layout": (12.9121, 77.6446),
    "electronic city": (12.8452, 77.6632),
    "bannerghatta road": (12.8900, 77.5900),
    "kalyan nagar": (13.0221, 77.6403),
    "kammanahalli": (13.0150, 77.6370),
    "brookefield": (12.9650, 77.7180),
    "hopefarm": (12.9840, 77.7510),
    "kadugodi": (12.9980, 77.7610),
    "varthur": (12.9400, 77.7460),
    "gunjur": (12.9150, 77.7350),
    "domlur": (12.9609, 77.6387),
    "indiranagar": (12.9784, 77.6408),
    "frazer town": (13.0000, 77.6100),
    "rt nagar": (13.0180, 77.5930),
    "sahakar nagar": (13.0600, 77.5850),
    # Broad zones (central point approximations)
    "north bangalore": (13.0500, 77.6000),  # Near Hebbal/Yelahanka
    "south bangalore": (12.8800, 77.6000),  # Near Bannerghatta
    "east bangalore": (12.9600, 77.7200),   # Near Whitefield/Marathahalli
    "west bangalore": (12.9800, 77.5200),   # Near Rajajinagar
    "central bangalore": (12.9716, 77.5946), # City center (MG Road area)
    "bangalore": (12.9716, 77.5946),        # Default Bangalore center
}

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees) using Haversine formula.
    Result is in kilometers.
    """
    # Convert decimal degrees to radians 
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula 
    dlat = lat2 - lat1 
    dlon = lon2 - lon1 
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a)) 
    r = 6371 # Radius of earth in kilometers. Use 3956 for miles
    return c * r

def get_coordinates(location_name: str) -> Optional[Tuple[float, float]]:
    """
    Returns (lat, lon) for a given location name.
    Does a simple fuzzy/keyword check.
    """
    location_name = location_name.lower()
    
    # Direct match first
    if location_name in BANGALORE_COORDINATES:
        return BANGALORE_COORDINATES[location_name]
    
    # Keyword containing match
    for key, coords in BANGALORE_COORDINATES.items():
        if key in location_name or location_name in key:
            return coords
            
    return None

def find_locations_within_radius(center_lat: float, center_lon: float, radius_km: float = 10.0) -> Dict[str, float]:
    """
    Finds all known locations within a certain radius.
    """
    results = {}
    for loc, coords in BANGALORE_COORDINATES.items():
        dist = calculate_distance(center_lat, center_lon, coords[0], coords[1])
        if dist <= radius_km:
            results[loc] = dist
    return results
