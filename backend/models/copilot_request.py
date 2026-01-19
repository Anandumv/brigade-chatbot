"""
Copilot Request Models (Spec-Compliant)
Defines the /assist endpoint request structure with Quick Filters.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class QuickFilters(BaseModel):
    """
    Quick Filters for property search (spec-compliant).
    Persists across conversation turns in Redis context.
    """
    price_range: Optional[List[int]] = Field(
        None,
        description="[min_price, max_price] in INR. Example: [7000000, 13000000]"
    )

    bhk: Optional[List[str]] = Field(
        None,
        description="List of BHK types. Example: ['2BHK', '3BHK']"
    )

    status: Optional[List[str]] = Field(
        None,
        description="Project status. Options: ['Ready-to-move', 'Under Construction']"
    )

    amenities: Optional[List[str]] = Field(
        None,
        description="Required amenities. Example: ['Pool', 'Clubhouse', 'Gym']"
    )

    radius_km: Optional[int] = Field(
        None,
        description="Search radius from location in kilometers. Example: 5"
    )

    possession_window: Optional[int] = Field(
        None,
        description="Possession year. Example: 2027"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "price_range": [7000000, 13000000],
                "bhk": ["2BHK"],
                "status": ["Ready-to-move"],
                "amenities": ["Pool", "Clubhouse"],
                "radius_km": 5
            }
        }


class AssistRequest(BaseModel):
    """
    Request model for /api/assist endpoint (spec-compliant).

    Fields:
    - call_id: Unique identifier for conversation (persists in Redis)
    - query: User's natural language query
    - filters: Optional quick filters (override context filters)
    """
    call_id: str = Field(
        ...,
        description="Unique conversation identifier (UUID). Used for Redis context persistence."
    )

    query: str = Field(
        ...,
        min_length=1,
        description="User's natural language query"
    )

    filters: Optional[QuickFilters] = Field(
        None,
        description="Quick filters (optional). Overrides context filters if provided."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "call_id": "550e8400-e29b-41d4-a716-446655440000",
                "query": "Show me 2BHK ready-to-move options under 1.3Cr in Sarjapur",
                "filters": {
                    "price_range": [7000000, 13000000],
                    "bhk": ["2BHK"],
                    "status": ["Ready-to-move"],
                    "radius_km": 5
                }
            }
        }
