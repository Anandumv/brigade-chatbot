"""
Answer generation service using GPT-4 with strict grounding constraints.
Implements the core principle: ONLY use information from provided context.
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import settings
import logging
import re

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """Generate answers using GPT-4 with hard anti-hallucination constraints."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.gpt_model
        self.temperature = settings.temperature
        self.max_tokens = settings.max_tokens

    def generate_answer(
        self,
        query: str,
        chunks: List[Dict[str, Any]],
        intent: str,
        confidence: str
    ) -> Dict[str, Any]:
        """
        Generate answer from retrieved chunks with strict grounding.

        Args:
            query: User's question
            chunks: Retrieved document chunks
            intent: Classified intent
            confidence: Confidence level

        Returns:
            Dictionary with answer, sources, and metadata
        """
        if not chunks:
            return {
                "answer": "No relevant information found in project documents.",
                "sources": [],
                "confidence": "Not Available"
            }

        # Build context from chunks
        context = self._build_context(chunks)

        # Generate prompt
        system_prompt = self._build_system_prompt(intent)
        user_prompt = self._build_user_prompt(query, context)

        try:
            # Call GPT-4
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            answer = response.choices[0].message.content.strip()

            # Validate answer has proper citations
            if not self._has_valid_citations(answer):
                logger.warning("Generated answer lacks proper citations")
                # Force add source references
                answer = self._add_source_references(answer, chunks)

            # Extract sources
            sources = self._extract_sources(chunks)

            return {
                "answer": answer,
                "sources": sources,
                "confidence": confidence,
                "intent": intent
            }

        except Exception as e:
            logger.error(f"Error generating answer: {e}")
            return {
                "answer": "An error occurred while generating the answer.",
                "sources": [],
                "confidence": "Not Available"
            }

    def _build_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build context string from chunks."""
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            source_ref = f"[Source {i}: {chunk.get('document_title', 'Unknown')}, {chunk.get('section', 'Unknown section')}]"
            content = chunk.get('content', '')
            context_parts.append(f"{source_ref}\n{content}\n")

        return "\n".join(context_parts)

    def _build_system_prompt(self, intent: str) -> str:
        """Build system prompt with anti-hallucination constraints."""
        base_prompt = """You are a sales assistant for Brigade Group real estate projects.

CRITICAL RULES - YOU MUST FOLLOW THESE EXACTLY:

1. ONLY use information explicitly stated in the provided context chunks
2. NEVER infer, assume, or generate information not present in the context
3. NEVER use your general knowledge about real estate or Brigade Group
4. If information is not in the context, say "This information is not available in the project documents"
5. ALWAYS cite the specific source for each piece of information
6. If asked about pricing, ROI, future predictions, or legal advice → REFUSE
7. Be factual and specific - avoid marketing language not in the source
8. Keep answers concise and directly relevant to the question

When answering:
- Quote or paraphrase ONLY from the provided sources
- Include source citations in your answer (e.g., "According to the E-Brochure, Page 5...")
- If multiple sources confirm the same fact, mention multiple sources
- If sources conflict, state the conflict explicitly
"""

        # Intent-specific additions
        if intent == "sales_pitch":
            base_prompt += """
For sales pitch requests:
- Highlight benefits and features ONLY mentioned in the sources
- Do not exaggerate or add superlatives not in the original text
- Structure the pitch using actual project details from sources
"""
        elif intent == "comparison":
            base_prompt += """
For comparison requests:
- Only compare aspects explicitly mentioned in sources for BOTH projects
- Clearly label which information comes from which project
- If information is available for only one project, state that
"""

        return base_prompt

    def _build_user_prompt(self, query: str, context: str) -> str:
        """Build user prompt with query and context."""
        return f"""Context from project documents:

{context}

User question: {query}

Provide a factual answer using ONLY the information above. Include source citations."""

    def _has_valid_citations(self, answer: str) -> bool:
        """Check if answer contains source citations."""
        # Look for patterns like "Page X", "E-Brochure", "according to", etc.
        citation_patterns = [
            r'Page \d+',
            r'E-Brochure',
            r'according to',
            r'Source \d+',
            r'brochure',
            r'document'
        ]

        for pattern in citation_patterns:
            if re.search(pattern, answer, re.IGNORECASE):
                return True

        return False

    def _add_source_references(self, answer: str, chunks: List[Dict[str, Any]]) -> str:
        """Add source references to answer if missing."""
        if not chunks:
            return answer

        # Get primary source
        primary_source = chunks[0]
        source_ref = f" (Source: {primary_source.get('document_title', 'Project documents')}, {primary_source.get('section', '')})"

        return answer + source_ref

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

    def generate_comparison_answer(
        self,
        query: str,
        chunks: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate comparison answer ensuring both projects are covered.

        Args:
            query: User's comparison question
            chunks: Retrieved chunks (should contain multiple projects)

        Returns:
            Comparison answer with sources from both projects
        """
        # Group chunks by project
        projects = {}
        for chunk in chunks:
            project_name = chunk.get('project_name', 'Unknown')
            if project_name not in projects:
                projects[project_name] = []
            projects[project_name].append(chunk)

        if len(projects) < 2:
            return {
                "answer": "I can only provide comparison when information is available for multiple projects.",
                "sources": self._extract_sources(chunks),
                "confidence": "Not Available"
            }

        # Build separate contexts for each project
        context_parts = []
        for project_name, project_chunks in projects.items():
            context_parts.append(f"\n=== {project_name} ===")
            for chunk in project_chunks[:3]:  # Limit chunks per project
                context_parts.append(chunk.get('content', ''))

        context = "\n\n".join(context_parts)

        system_prompt = """You are comparing real estate projects for Brigade Group.

CRITICAL RULES:
1. Only compare aspects explicitly mentioned in BOTH projects' documents
2. Clearly label which information belongs to which project
3. If information is only available for one project, state that explicitly
4. Do not infer similarities or differences not stated in the documents
5. Cite sources for each project

Structure your comparison clearly."""

        user_prompt = f"""Context:

{context}

Question: {query}

Provide a factual comparison using ONLY the information above."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )

            answer = response.choices[0].message.content.strip()

            return {
                "answer": answer,
                "sources": self._extract_sources(chunks),
                "confidence": "Medium"  # Comparisons are always medium confidence
            }

        except Exception as e:
            logger.error(f"Error generating comparison: {e}")
            return {
                "answer": "An error occurred while generating the comparison.",
                "sources": [],
                "confidence": "Not Available"
            }


# Global answer generator instance
answer_generator = AnswerGenerator()
