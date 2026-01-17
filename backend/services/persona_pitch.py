"""
Persona-based pitch generation service.
Tailors sales pitches to different buyer personas.
Phase 2 feature.
"""

from typing import List, Dict, Any
from openai import OpenAI
from config import settings
import logging

logger = logging.getLogger(__name__)


class PersonaPitchGenerator:
    """Generate persona-tailored sales pitches."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
        self.model = settings.gpt_model
        self.temperature = 0.3  # Slightly higher for creative pitches

        # Define persona profiles
        self.personas = {
            "first_time_buyer": {
                "name": "First-Time Homebuyer",
                "priorities": [
                    "Affordability and payment plans",
                    "Ready-to-move-in condition",
                    "Loan assistance",
                    "Security and safety features",
                    "Proximity to workplace/schools",
                    "Community living"
                ],
                "concerns": [
                    "Hidden costs",
                    "Legal clarity",
                    "Builder reputation",
                    "Maintenance expenses"
                ]
            },
            "investor": {
                "name": "Property Investor",
                "priorities": [
                    "Capital appreciation potential",
                    "Rental yield",
                    "Location advantages",
                    "Brand value",
                    "Infrastructure development",
                    "Resale value"
                ],
                "concerns": [
                    "Market trends",
                    "Competition in area",
                    "Possession timeline",
                    "Rental demand"
                ]
            },
            "senior_citizen": {
                "name": "Senior Citizen",
                "priorities": [
                    "Accessibility (elevators, ramps)",
                    "Healthcare facilities nearby",
                    "Peaceful environment",
                    "Security and gated community",
                    "Maintenance support",
                    "Ground floor availability",
                    "Community spaces"
                ],
                "concerns": [
                    "Safety",
                    "Medical emergencies",
                    "Mobility issues",
                    "Social isolation"
                ]
            },
            "family": {
                "name": "Family with Children",
                "priorities": [
                    "Schools and educational institutions nearby",
                    "Children's play areas",
                    "Safe environment",
                    "Spacious units (3BHK+)",
                    "Parks and open spaces",
                    "Family-friendly amenities",
                    "Community events"
                ],
                "concerns": [
                    "Child safety",
                    "Traffic and pollution",
                    "Educational options",
                    "Recreational facilities"
                ]
            }
        }

    def generate_persona_pitch(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        persona: str
    ) -> Dict[str, Any]:
        """
        Generate persona-tailored sales pitch.

        Args:
            query: User's question
            chunks: Retrieved document chunks
            persona: Persona type (first_time_buyer, investor, senior_citizen, family)

        Returns:
            Dictionary with tailored answer and sources
        """
        if persona not in self.personas:
            logger.warning(f"Unknown persona: {persona}, using generic pitch")
            persona = "first_time_buyer"

        persona_profile = self.personas[persona]

        # Build context from chunks
        context = self._build_context(chunks)

        # Build persona-specific system prompt
        system_prompt = self._build_persona_prompt(persona_profile)

        # Generate pitch
        user_prompt = f"""Context from project documents:

{context}

Question: {query}

Generate a sales pitch that addresses the specific needs and concerns of a {persona_profile['name']}.
Highlight relevant features from the project documents that match their priorities.
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            answer = response.choices[0].message.content.strip()

            return {
                "answer": answer,
                "sources": self._extract_sources(chunks),
                "confidence": "Medium",  # Persona pitches are always medium confidence
                "persona": persona_profile["name"]
            }

        except Exception as e:
            logger.error(f"Error generating persona pitch: {e}")
            return {
                "answer": "An error occurred while generating the personalized pitch.",
                "sources": [],
                "confidence": "Not Available",
                "persona": persona_profile["name"]
            }

    def _build_persona_prompt(self, persona_profile: Dict[str, Any]) -> str:
        """Build system prompt for persona-specific pitch."""
        priorities = "\n".join(f"  - {p}" for p in persona_profile["priorities"])
        concerns = "\n".join(f"  - {c}" for c in persona_profile["concerns"])

        return f"""You are a sales assistant for Brigade Group real estate projects, speaking to a {persona_profile['name']}.

AUDIENCE PROFILE:
This buyer is primarily interested in:
{priorities}

They are typically concerned about:
{concerns}

CRITICAL RULES:
1. ONLY use information from the provided context
2. Emphasize features that match their priorities
3. Address their typical concerns if information is available
4. Be empathetic and understanding of their needs
5. Maintain factual accuracy - do not exaggerate
6. Always cite sources for claims

TONE:
- Professional yet warm
- Focus on benefits relevant to this persona
- Acknowledge their specific situation
- Build trust through transparency

FORMATTING:
- Use BULLET POINTS only. No paragraphs.
- Bold main points: project name, price, key benefits.
- For sales people on calls: one point per bullet, scannable.
"""

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string from chunks."""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            source_ref = f"[Source {i}: {chunk.get('document_title', 'Unknown')}, {chunk.get('section', 'Unknown')}]"
            content = chunk.get('content', '')
            context_parts.append(f"{source_ref}\n{content}\n")

        return "\n".join(context_parts)

    def _extract_sources(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract source metadata from chunks."""
        sources = []

        for chunk in chunks:
            metadata = chunk.get('metadata', {})

            source = {
                "document": chunk.get('document_title', metadata.get('document', 'Unknown')),
                "section": chunk.get('section', metadata.get('section', 'Unknown')),
                "page": metadata.get('page', None),
                "excerpt": chunk.get('content', '')[:200] + "..." if len(chunk.get('content', '')) > 200 else chunk.get('content', ''),
                "similarity": round(chunk.get('similarity', 0), 3)
            }
            sources.append(source)

        return sources

    def get_available_personas(self) -> List[Dict[str, str]]:
        """Get list of available personas with descriptions."""
        return [
            {
                "id": persona_id,
                "name": profile["name"],
                "description": f"Focuses on: {', '.join(profile['priorities'][:3])}"
            }
            for persona_id, profile in self.personas.items()
        ]


# Global persona pitch generator instance
persona_pitch_generator = PersonaPitchGenerator()
