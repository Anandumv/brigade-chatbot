"""
Natural Language Filter Extraction Service
Parses queries like "2bhk under 3cr in Bangalore" into structured SQL filters
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from openai import OpenAI
from config import settings
import logging
import re
import json

logger = logging.getLogger(__name__)


class PropertyFilters(BaseModel):
    """Structured filters extracted from natural language query"""

    # Unit configuration
    bedrooms: Optional[List[int]] = Field(None, description="Number of bedrooms [2] from '2bhk'")
    min_bedrooms: Optional[int] = Field(None, description="Minimum bedrooms from 'at least 2bhk'")
    max_bedrooms: Optional[int] = Field(None, description="Maximum bedrooms from 'up to 3bhk'")

    # Pricing
    min_price_inr: Optional[int] = Field(None, description="Minimum price in INR")
    max_price_inr: Optional[int] = Field(None, description="Maximum price in INR from 'under 3cr'")
    budget_inr: Optional[int] = Field(None, description="Exact budget from 'around 2.5cr'")

    # Location
    city: Optional[str] = Field(None, description="City name: 'Bangalore'")
    locality: Optional[str] = Field(None, description="Locality: 'Whitefield', 'Koramangala'")
    area: Optional[str] = Field(None, description="Area: 'North Bangalore', 'East Bangalore'")

    # Possession
    possession_year: Optional[int] = Field(None, description="Possession year: 2027")
    possession_quarter: Optional[str] = Field(None, description="Q1, Q2, Q3, Q4")

    # Area/size
    min_area_sqft: Optional[int] = Field(None, description="Minimum carpet area in sqft")
    max_area_sqft: Optional[int] = Field(None, description="Maximum carpet area in sqft")

    # Project status
    status: Optional[List[str]] = Field(None, description="['ongoing', 'completed', 'upcoming']")

    # Developer
    developer_name: Optional[str] = Field(None, description="Developer/company name")
    
    # Property Type (From flowchart)
    property_type: Optional[List[str]] = Field(None, description="['apartment', 'villa', 'plot', 'row house']")

    # Amenities (for future use)
    required_amenities: Optional[List[str]] = Field(None, description="Required amenities")

    def has_filters(self) -> bool:
        """Check if any filters were extracted"""
        return any([
            self.bedrooms,
            self.min_bedrooms,
            self.max_bedrooms,
            self.min_price_inr,
            self.max_price_inr,
            self.budget_inr,
            self.city,
            self.locality,
            self.possession_year,
            self.min_area_sqft,
            self.max_area_sqft,
            self.status,
            self.developer_name,
            self.property_type
        ])

    def to_sql_conditions(self) -> tuple[List[str], Dict[str, Any]]:
        """
        Convert filters to SQL WHERE conditions and parameters.
        """
        conditions = []
        params = {}

        # Bedroom filters
        if self.bedrooms:
            conditions.append("bedrooms = ANY(:bedrooms)")
            params["bedrooms"] = self.bedrooms
        elif self.min_bedrooms and self.max_bedrooms:
            conditions.append("bedrooms BETWEEN :min_bedrooms AND :max_bedrooms")
            params["min_bedrooms"] = self.min_bedrooms
            params["max_bedrooms"] = self.max_bedrooms
        elif self.min_bedrooms:
            conditions.append("bedrooms >= :min_bedrooms")
            params["min_bedrooms"] = self.min_bedrooms
        elif self.max_bedrooms:
            conditions.append("bedrooms <= :max_bedrooms")
            params["max_bedrooms"] = self.max_bedrooms

        # Price filters
        if self.budget_inr:
            # "around 2.5cr" → +/- 10% range
            margin = int(self.budget_inr * 0.1)
            conditions.append("base_price_inr BETWEEN :budget_min AND :budget_max")
            params["budget_min"] = self.budget_inr - margin
            params["budget_max"] = self.budget_inr + margin
        else:
            if self.max_price_inr:
                conditions.append("base_price_inr <= :max_price")
                params["max_price"] = self.max_price_inr
            if self.min_price_inr:
                conditions.append("base_price_inr >= :min_price")
                params["min_price"] = self.min_price_inr

        # Location filters
        if self.city:
            conditions.append("LOWER(city) = LOWER(:city)")
            params["city"] = self.city
        if self.locality:
            conditions.append("LOWER(locality) = LOWER(:locality)")
            params["locality"] = self.locality

        # Possession filters
        if self.possession_year:
            conditions.append("possession_year = :possession_year")
            params["possession_year"] = self.possession_year
        if self.possession_quarter:
            conditions.append("possession_quarter = :possession_quarter")
            params["possession_quarter"] = self.possession_quarter

        # Area filters
        if self.min_area_sqft:
            conditions.append("carpet_area_sqft >= :min_area")
            params["min_area"] = self.min_area_sqft
        if self.max_area_sqft:
            conditions.append("carpet_area_sqft <= :max_area")
            params["max_area"] = self.max_area_sqft

        # Status filters
        if self.status:
            conditions.append("project_status = ANY(:status)")
            params["status"] = self.status

        # Developer filter
        if self.developer_name:
            conditions.append("LOWER(developer_name) LIKE LOWER(:developer)")
            params["developer"] = f"%{self.developer_name}%"
            
        # Property Type filter (New)
        if self.property_type:
            # Check config_summary for type keywords
            type_conditions = []
            for i, p_type in enumerate(self.property_type):
                param_name = f"ptype_{i}"
                type_conditions.append(f"LOWER(config_summary) LIKE :{param_name}")
                params[param_name] = f"%{p_type}%"
            
            if type_conditions:
                conditions.append(f"({' OR '.join(type_conditions)})")

        return conditions, params


class FilterExtractor:
    """Extract structured filters from natural language queries"""

    def __init__(self):
        self.openai_client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url
        )
        self.model = "gpt-4-turbo-preview"

        # Price conversion patterns (Indian numbering)
        self.price_patterns = {
            r'(\d+\.?\d*)\s*cr(?:ore)?s?': lambda x: int(float(x) * 10000000),  # 3cr → 30000000
            r'(\d+\.?\d*)\s*lac?(?:kh)?s?': lambda x: int(float(x) * 100000),   # 50lac → 5000000
            r'(\d+\.?\d*)\s*k': lambda x: int(float(x) * 1000),                  # 500k → 500000
        }

        # City aliases (normalize to standard names)
        self.city_aliases = {
            'bangalore': 'Bangalore',
            'bengaluru': 'Bangalore',
            'blr': 'Bangalore',
            'mumbai': 'Mumbai',
            'bombay': 'Mumbai',
            'delhi': 'Delhi',
            'ncr': 'Delhi NCR',
            'chennai': 'Chennai',
            'madras': 'Chennai',
            'hyderabad': 'Hyderabad',
            'pune': 'Pune',
            'kolkata': 'Kolkata',
            'calcutta': 'Kolkata'
        }

        # Known localities (exact match from flowchart)
        self.localities = {
            # East Bangalore (From flowchart)
            'whitefield', 'budigere cross', 'varthur', 'gunjur', 
            'sarjapur road', 'panathur road', 'kadugodi',
            
            # North Bangalore (From flowchart)
            'thanisandra', 'jakkur', 'baglur', 'yelahanka', 'devanahalli',
            'airport', 'kempegowda international airport', 'bial',
            
            # Other common areas
            'koramangala', 'indiranagar', 'hsr layout', 'electronic city',
            'marathahalli', 'jp nagar', 'btm layout', 'jayanagar', 
            'rajajinagar', 'yeshwanthpur', 'hebbal', 'old madras road',
            'bannerghatta road', 'kr puram', 'mahadevpura', 'bellandur',
            'hennur', 'kundanhalli', 'brookefield',
        }

        # Status keywords
        self.status_keywords = {
            'ready': ['completed'],
            'ready to move': ['completed'],
            'rtmi': ['completed'],  # Added from flowchart
            'immediate possession': ['completed'],
            'under construction': ['ongoing'],
            'ongoing': ['ongoing'],
            'upcoming': ['upcoming'],
            'new launch': ['upcoming'],
            'pre-launch': ['upcoming']
        }

        # Developer aliases
        self.developer_aliases = {
            'brigade': 'Brigade Group',
            'prestige': 'Prestige Group',
            'sobha': 'Sobha Limited',
            'godrej': 'Godrej Properties',
            'mahindra': 'Mahindra Lifespaces'
        }

    def extract_filters(self, query: str) -> PropertyFilters:
        """
        Extract structured filters from natural language query using regex patterns.
        """
        query_lower = query.lower()
        filters = PropertyFilters()

        logger.info(f"Extracting filters from query: {query}")

        # Extract bedrooms
        filters.bedrooms = self._extract_bedrooms(query_lower)

        # Extract price range
        filters.min_price_inr, filters.max_price_inr, filters.budget_inr = self._extract_price(query_lower)

        # Extract city
        filters.city = self._extract_city(query_lower)

        # Extract locality
        filters.locality = self._extract_locality(query_lower)

        # Extract possession year
        filters.possession_year = self._extract_possession_year(query_lower)

        # Extract area/size (sqft)
        filters.min_area_sqft, filters.max_area_sqft = self._extract_size(query_lower)

        # Extract zone (North/South/East/West Bangalore)
        filters.area = self._extract_zone(query_lower)

        # Extract status
        filters.status = self._extract_status(query_lower)

        # Extract developer
        filters.developer_name = self._extract_developer(query_lower)
        
        # Extract property type
        filters.property_type = self._extract_property_type(query_lower)

        logger.info(f"Extracted filters: {filters.dict(exclude_none=True)}")

        return filters

    def _extract_bedrooms(self, query: str) -> Optional[List[int]]:
        """Extract bedroom count: '2bhk' → [2], '2bhk or 3bhk' → [2, 3]"""
        patterns = [
            r'(\d+)\s*bhk',           # "2bhk", "3 bhk"
            r'(\d+)\s*bed',           # "2 bed", "3bed"
            r'(\d+)\s*bedroom',       # "2 bedroom"
        ]

        bedrooms = set()
        for pattern in patterns:
            matches = re.findall(pattern, query)
            for match in matches:
                bedroom_count = int(match)
                if 0 <= bedroom_count <= 10:  # Sanity check
                    bedrooms.add(bedroom_count)

        return sorted(list(bedrooms)) if bedrooms else None
        
    def _extract_property_type(self, query: str) -> Optional[List[str]]:
        """Extract property type: 'villa', 'plot', 'row house'"""
        types = set()
        
        if 'villa' in query:
            types.add('villa')
        if 'plot' in query or 'land' in query:
            types.add('plot')
        if 'row house' in query or 'rowhouse' in query:
            types.add('row house')
        if 'apartment' in query or 'flat' in query:
            types.add('apartment')
            
        return list(types) if types else None

    def _extract_price(self, query: str) -> tuple[Optional[int], Optional[int], Optional[int]]:
        """
        Extract price range from query.

        Returns: (min_price, max_price, budget)
        """
        min_price = None
        max_price = None
        budget = None

        # Check for "under", "below", "less than"
        if re.search(r'under|below|less than|upto|up to|within', query):
            for pattern, converter in self.price_patterns.items():
                match = re.search(pattern, query)
                if match:
                    max_price = converter(match.group(1))
                    break

        # Check for "above", "over", "more than"
        elif re.search(r'above|over|more than|minimum', query):
            for pattern, converter in self.price_patterns.items():
                match = re.search(pattern, query)
                if match:
                    min_price = converter(match.group(1))
                    break

        # Check for "between X and Y"
        elif 'between' in query and 'and' in query:
            amounts = []
            for pattern, converter in self.price_patterns.items():
                matches = re.findall(pattern, query)
                for match in matches:
                    amounts.append(converter(match))
            if len(amounts) >= 2:
                min_price = min(amounts)
                max_price = max(amounts)

        # Check for "around", "approximately"
        elif re.search(r'around|approximately|approx|budget', query):
            for pattern, converter in self.price_patterns.items():
                match = re.search(pattern, query)
                if match:
                    budget = converter(match.group(1))
                    break

        return min_price, max_price, budget

    def _extract_city(self, query: str) -> Optional[str]:
        """Extract city name: 'in bangalore' → 'Bangalore'"""
        for alias, city in self.city_aliases.items():
            if re.search(r'\b' + re.escape(alias) + r'\b', query):
                return city
        return None

    def _extract_locality(self, query: str) -> Optional[str]:
        """Extract locality: 'whitefield' → 'Whitefield'"""
        for locality in self.localities:
            if locality in query:
                return locality.title()  # Capitalize: 'whitefield' → 'Whitefield'
        return None

    def _extract_possession_year(self, query: str) -> Optional[int]:
        """Extract possession year: 'possession 2027' → 2027"""
        patterns = [
            r'possession\s+(\d{4})',         # "possession 2027"
            r'(\d{4})\s+possession',         # "2027 possession"
            r'ready by\s+(\d{4})',           # "ready by 2027"
            r'delivery in\s+(\d{4})',        # "delivery in 2027"
        ]

        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                year = int(match.group(1))
                if 2020 <= year <= 2050:  # Sanity check
                    return year

        return None

    def _extract_zone(self, query: str) -> Optional[str]:
        """Extract zone: 'North Bangalore', 'South Bangalore'"""
        zones = {
            'north bangalore': 'North Bangalore',
            'north bmr': 'North Bangalore',
            'north': 'North Bangalore',
            'south bangalore': 'South Bangalore',
            'south': 'South Bangalore',
            'east bangalore': 'East Bangalore',
            'east': 'East Bangalore',
            'west bangalore': 'West Bangalore',
            'west': 'West Bangalore',
            'central bangalore': 'Central Bangalore',
            'central': 'Central Bangalore'
        }
        
        # Check for explicit zone mentions
        # We need to be careful not to match 'North' in 'Northern Lights' project name if possible, 
        # but for now, simple keyword match if followed by Bangalore or just pure direction in context works.
        # Flowchart specific zones are key.
        
        for key, value in zones.items():
            # word boundary check
            if re.search(r'\b' + re.escape(key) + r'\b', query):
                return value
        return None

    def _extract_size(self, query: str) -> tuple[Optional[int], Optional[int]]:
        """Extract area range: 'above 1000 sqft' → (1000, None)"""
        min_area = None
        max_area = None

        # Pattern: "1000 sqft", "2000 sq ft", "1500 sft"
        area_pattern = r'(\d+)\s*(?:sq\s*ft|sqft|sft|square\s*feet)'

        if re.search(r'above|over|more than|minimum', query):
            match = re.search(area_pattern, query)
            if match:
                min_area = int(match.group(1))
        elif re.search(r'under|below|less than|upto|maximum', query):
            match = re.search(area_pattern, query)
            if match:
                max_area = int(match.group(1))

        return min_area, max_area

    def _extract_status(self, query: str) -> Optional[List[str]]:
        """Extract project status: 'ready to move' → ['completed']"""
        for keyword, statuses in self.status_keywords.items():
            if keyword in query:
                return statuses
        return None

    def _extract_developer(self, query: str) -> Optional[str]:
        """Extract developer name: 'brigade projects' → 'Brigade Group'"""
        for alias, developer in self.developer_aliases.items():
            if re.search(r'\b' + re.escape(alias) + r'\b', query):
                return developer
        return None

    def extract_with_llm_fallback(self, query: str) -> PropertyFilters:
        """
        Use GPT-4 to extract complex filters when regex patterns are insufficient.

        Use cases:
        - Complex locality names not in our list
        - Ambiguous queries: "spacious 2bhk" (what's spacious?)
        - Regional terms: "luxury", "affordable", "premium"
        """
        try:
            system_prompt = """You are a filter extraction assistant for real estate queries.

Extract structured filters from the user's query and return as JSON.

Available fields:
- bedrooms: list of integers [2, 3]
- min_price_inr: integer (in INR)
- max_price_inr: integer (in INR)
- budget_inr: integer (approximate budget in INR)
- city: string (Bangalore, Mumbai, Delhi, etc.)
- locality: string (Whitefield, Koramangala, etc.)
- possession_year: integer (2027, 2028, etc.)
- status: list of strings ["completed", "ongoing", "upcoming"]
- developer_name: string (Brigade Group, Prestige Group, etc.)
- property_type: list of strings ["apartment", "villa", "plot"]

Price conversion:
- 1 crore (cr) = 10,000,000 INR
- 1 lakh (lac) = 100,000 INR

Examples:
Input: "2bhk under 3cr in Bangalore"
Output: {"bedrooms": [2], "max_price_inr": 30000000, "city": "Bangalore"}

Input: "3bhk whitefield ready to move under 5cr"
Output: {"bedrooms": [3], "locality": "Whitefield", "status": ["completed"], "max_price_inr": 50000000}

Input: "affordable brigade 2bhk possession 2027"
Output: {"bedrooms": [2], "developer_name": "Brigade Group", "possession_year": 2027}

Return ONLY valid JSON with extracted filters. If a field cannot be determined, omit it."""

            response = self.openai_client.chat.completions.create(
                model=self.model,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract filters from: {query}"}
                ],
                response_format={"type": "json_object"}
            )

            extracted_json = response.choices[0].message.content
            extracted_data = json.loads(extracted_json)

            logger.info(f"LLM extracted filters: {extracted_data}")

            return PropertyFilters(**extracted_data)

        except Exception as e:
            logger.error(f"LLM filter extraction failed: {e}", exc_info=True)
            # Fall back to regex extraction
            return self.extract_filters(query)

    def merge_filters(self, nlp_filters: PropertyFilters, ui_filters: Dict[str, Any]) -> PropertyFilters:
        """
        Merge explicit UI filters into NLP-extracted filters.
        UI filters take precedence.
        """
        if not ui_filters:
            return nlp_filters
            
        merged = nlp_filters.copy()
        
        # Merge logic
        # 1. Configuration (BHK)
        if ui_filters.get('configuration'):
            try:
                # "2" -> [2], "2.5" -> [2, 3] logic or strictly follows UI?
                # Converting UI string to bedroom list
                conf = ui_filters['configuration']
                if conf == 'plots':
                    merged.property_type = ['plot']
                    merged.bedrooms = None
                elif conf == 'villa':
                    merged.property_type = ['villa']
                else:
                    # '2', '2.5', '3'
                    val = float(conf)
                    if val.is_integer():
                        merged.bedrooms = [int(val)]
                    else:
                        # Handle .5 (e.g. 2.5 BHK) -> maybe map to closest or explicit field?
                        # For now mapping 2.5 -> [2, 3] or just keep as is if downstream handler supports it
                        # Since PropertyFilters uses List[int], we might need to broaden it or round
                        merged.bedrooms = [int(val), int(val)+1] # 2.5 -> [2, 3]
            except ValueError:
                pass
                
        # 2. Location
        if ui_filters.get('location'):
            # UI sends "whitefield", "north_bangalore", etc.
            loc = ui_filters['location']
            # Check if it's an area or locality
            if 'bangalore' in loc: 
                merged.area = loc.replace('_', ' ').title() # north_bangalore -> North Bangalore
            else:
                merged.locality = loc.replace('_', ' ').title() # whitefield -> Whitefield
                
        # 3. Budget (Range sent as min/max usually, but check API)
        # Frontend sends budgetMin / budgetMax in payload usually?
        # Checking api.ts: it sends the whole 'SelectedFilters' object which has budgetMin/Max
        
        if ui_filters.get('budgetMin'):
            merged.min_price_inr = int(ui_filters['budgetMin'])
            merged.budget_inr = None # Clear vague budget if explicit range set
            
        if ui_filters.get('budgetMax'):
            merged.max_price_inr = int(ui_filters['budgetMax'])
            if not ui_filters.get('budgetMin'):
                 merged.budget_inr = None

        # 4. Possession
        if ui_filters.get('possessionYear'):
            val = ui_filters['possessionYear']
            if val == 'READY':
                merged.status = ['completed']
                merged.possession_year = None
            else:
                try:
                    merged.possession_year = int(val)
                except:
                    pass
                    
        return merged


# Global instance
filter_extractor = FilterExtractor()

