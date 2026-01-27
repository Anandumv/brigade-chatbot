"""
Copilot Response Models (Spec-Compliant)
Strict JSON-only response format with bullets for reasoning.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class LiveCallStructure(BaseModel):
    """
    6-part structure for live call scenarios with consultant-grade responses.
    Used when live_call_mode=True in the request.
    """
    situation_reframe: str = Field(
        ...,
        description="One paragraph restating client situation (spoken on call)"
    )
    consultant_questions: List[str] = Field(
        ...,
        description="2-4 high-leverage questions to ask on call"
    )
    recommended_next_step: Optional[str] = Field(
        None,
        description="Clear next action if client asks what to do"
    )
    pushback_handling: Optional[Dict[str, str]] = Field(
        None,
        description="Common objections with responses (e.g., {'We need to think': 'That's reasonable. What specifically do you want to think through?'})"
    )
    closing_summary: str = Field(
        ...,
        description="One paragraph alignment summary (spoken)"
    )
    post_call_message: str = Field(
        ...,
        description="Plain text for WhatsApp/email (no formatting, no emojis)"
    )


class ProjectInfo(BaseModel):
    """
    Project information returned in copilot response.
    All fields come from DATABASE ONLY (no GPT hallucination).
    """
    name: str = Field(..., description="Project name from database")
    location: str = Field(..., description="Full location address from database")
    price_range: str = Field(..., description="Price range formatted as '70L - 1.3Cr'")
    bhk: str = Field(..., description="BHK types as comma-separated string: '2BHK, 3BHK'")
    amenities: List[str] = Field(default_factory=list, description="List of amenities from database")
    status: str = Field(..., description="'Ready-to-move' or 'Under Construction'")

    # NEW: Critical missing fields from database
    brochure_url: Optional[str] = Field(None, description="PDF brochure download link")
    rm_details: Optional[Dict[str, str]] = Field(None, description="Relationship manager: {name, contact}")
    registration_process: Optional[str] = Field(None, description="Registration steps (markdown formatted)")
    zone: Optional[str] = Field(None, description="Zone: 'East Bangalore', 'North Bangalore', etc.")
    rera_number: Optional[str] = Field(None, description="RERA registration number")
    developer: Optional[str] = Field(None, description="Developer/builder name")
    possession_year: Optional[int] = Field(None, description="Expected possession year")
    possession_quarter: Optional[str] = Field(None, description="Possession quarter: 'Q1', 'Q2', 'Q3', 'Q4'")

    # Optional: Configuration-level details (for budget filtering transparency)
    matching_units: Optional[List[Dict[str, Any]]] = Field(None, description="Which configurations match the search criteria")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Brigade Citrine",
                "location": "Budigere Cross, East Bangalore",
                "price_range": "70L - 1.3Cr",
                "bhk": "2BHK, 3BHK",
                "amenities": ["Swimming Pool", "Clubhouse", "Gym", "Children's Play Area"],
                "status": "Under Construction"
            }
        }


class CopilotResponse(BaseModel):
    """
    Main copilot response format (spec-compliant).

    RULES:
    1. Generic, location, comparison, coaching answers are BULLETS ONLY (3-5)
    2. Project referenced (explicit or via context) → include DB facts in projects[]
    3. Budget logic is deterministic code. GPT only explains it.
    4. Location reasoning is approximate: use "around / typically / depends on traffic"
    5. Always include pitch_help and next_suggestion
    """
    projects: List[ProjectInfo] = Field(
        default_factory=list,
        description="Projects from database (empty if no project context)"
    )

    answer: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,  # Increased from 15 to support comprehensive responses
        description="Bullet points (reasoning, NOT facts). Facts go in projects[]"
    )

    pitch_help: str = Field(
        ...,
        description="Single call-ready sentence for sales rep to use on phone"
    )

    next_suggestion: str = Field(
        ...,
        description="One-line action suggestion (e.g., 'Ask about possession timeline')"
    )

    coaching_point: str = Field(
        ...,
        description="Real-time coaching for sales rep (1-2 sentences, actionable guidance)"
    )

    # NEW: Live call support
    live_call_structure: Optional['LiveCallStructure'] = Field(
        None,
        description="6-part structure for live call scenarios (only populated when live_call_mode=True)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "projects": [
                    {
                        "name": "Brigade Citrine",
                        "location": "Budigere Cross, East Bangalore",
                        "price_range": "70L - 1.3Cr",
                        "bhk": "2BHK, 3BHK",
                        "amenities": ["Swimming Pool", "Clubhouse", "Gym"],
                        "status": "Under Construction"
                    }
                ],
                "answer": [
                    "Sarjapur is typically around 30-40 km from the airport, depending on traffic",
                    "The commute can take 1-1.5 hours during peak hours via Outer Ring Road",
                    "This location is popular for IT professionals working in nearby tech parks"
                ],
                "pitch_help": "Sarjapur offers excellent connectivity to major IT hubs with ongoing metro expansion plans",
                "next_suggestion": "Ask if proximity to tech parks or schools is more important",
                "coaching_point": "Acknowledge the commute concern, then pivot to connectivity improvements and lifestyle benefits nearby"
            }
        }


class BudgetRelaxationResponse(CopilotResponse):
    """
    Extended response when budget relaxation was applied.
    Includes explanation of relaxation step.
    """
    relaxation_applied: bool = Field(
        default=False,
        description="Whether budget was relaxed (1.1x, 1.2x, or 1.3x)"
    )

    relaxation_step: Optional[float] = Field(
        None,
        description="Multiplier applied (1.0, 1.1, 1.2, or 1.3)"
    )

    original_budget: Optional[int] = Field(
        None,
        description="Original budget in INR (before relaxation)"
    )

    relaxed_budget: Optional[int] = Field(
        None,
        description="Relaxed budget in INR (after multiplier)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "projects": [
                    {
                        "name": "Brigade Citrine",
                        "location": "Budigere Cross, East Bangalore",
                        "price_range": "88L - 1.4Cr",
                        "bhk": "2BHK, 3BHK",
                        "amenities": ["Swimming Pool", "Clubhouse"],
                        "status": "Under Construction"
                    }
                ],
                "answer": [
                    "No exact matches found for 80L budget in Whitefield",
                    "Relaxed budget to 88L (1.1x) to show nearby options",
                    "These projects offer similar configurations with slight premium for location advantages"
                ],
                "pitch_help": "This project is slightly above budget but offers premium amenities and better appreciation potential",
                "next_suggestion": "Ask if they can stretch budget by 10% for better location",
                "relaxation_applied": True,
                "relaxation_step": 1.1,
                "original_budget": 8000000,
                "relaxed_budget": 8800000
            }
        }
