"""
Main FastAPI application for Real Estate Sales Intelligence Chatbot.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import logging
from contextlib import asynccontextmanager

from config import settings
from services.intent_classifier import intent_classifier
from services.retrieval import retrieval_service
from services.confidence_scorer import confidence_scorer
from services.refusal_handler import refusal_handler
from services.answer_generator import answer_generator
from services.multi_project_retrieval import multi_project_retrieval
from services.persona_pitch import persona_pitch_generator
from services.web_search import web_search_service
from services.hybrid_retrieval import hybrid_retrieval
from services.filter_extractor import filter_extractor
from services.response_formatter import response_formatter
from services.query_preprocessor import query_preprocessor
from database.supabase_client import supabase_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown events."""
    logger.info("Starting Real Estate Sales Intelligence Chatbot API v1.1...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Similarity threshold: {settings.similarity_threshold}")
    logger.info(f"Embedding model: {settings.embedding_model}")
    logger.info("Vector fallback enabled for property search")
    yield
    logger.info("Shutting down API...")


# Initialize FastAPI app
app = FastAPI(
    title="Real Estate Sales Intelligence Chatbot",
    description="Grounded, non-hallucinatory chatbot for real estate sales teams",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Request/Response Models ===

class ChatQueryRequest(BaseModel):
    """Request model for chat query."""
    query: str
    project_id: Optional[str] = None
    user_id: Optional[str] = None  # Required for logging
    persona: Optional[str] = None  # Phase 2: persona-based pitches


class SourceInfo(BaseModel):
    """Source information for answer."""
    document: str
    section: Optional[str] = "General"
    page: Optional[int] = None
    excerpt: str
    similarity: float


class ChatQueryResponse(BaseModel):
    """Response model for chat query."""
    answer: str
    sources: List[SourceInfo]
    confidence: str  # 'High', 'Medium', or 'Not Available'
    intent: str
    refusal_reason: Optional[str] = None
    response_time_ms: int


class ProjectInfo(BaseModel):
    """Project information."""
    id: str
    name: str
    location: str
    status: str
    rera_number: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    environment: str
    version: str


# === API Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.environment,
        "version": "1.0.0"
    }


@app.post("/api/chat/query", response_model=ChatQueryResponse)
async def chat_query(request: ChatQueryRequest):
    """
        ChatQueryResponse with answer, sources, and metadata
    """
    start_time = time.time()

    try:
        logger.info(f"Processing query: {request.query[:100]}...")

        # Step 0: Preprocess Query
        original_query = request.query
        normalized_query = query_preprocessor.preprocess(request.query)
        request.query = normalized_query
        logger.info(f"Normalized query: '{original_query}' -> '{normalized_query}'")

        # Step 1: Intent Classification
        intent = intent_classifier.classify_intent(request.query)
        logger.info(f"Classified intent: {intent}")

        # Step 1.5: Handle greetings immediately without RAG
        greeting_words = ['hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy', 'hola']
        query_lower = request.query.lower().strip().rstrip('!')
        if query_lower in greeting_words:
            response_time_ms = int((time.time() - start_time) * 1000)
            greeting_response = """👋 **Hello!** Welcome to Pinclick Genie!

I'm your AI-powered real estate assistant. I can help you with:

🏠 **Property Search** - "Show me 2BHK in Bangalore under 2 Cr"
🏢 **Project Details** - "Tell me about Brigade Citrine amenities"
💰 **Pricing Info** - "What's the price of 3BHK at Brigade Avalon?"
📍 **Location Info** - "Projects near Whitefield"

How can I assist you today?"""
            return ChatQueryResponse(
                answer=greeting_response,
                sources=[],
                confidence="High",
                intent="greeting",
                refusal_reason=None,
                response_time_ms=response_time_ms
            )

        # Step 2: Route property_search to hybrid filtering (NEW FLOW)
        if intent == "property_search":
            logger.info("Routing to property search with hybrid filtering")

            # Extract filters from query
            filters = filter_extractor.extract_filters(request.query)
            logger.info(f"Extracted filters: {filters.dict(exclude_none=True)}")

            # Hybrid retrieval (SQL + vector search)
            search_results = await hybrid_retrieval.search_with_filters(
                query=request.query,
                filters=filters
            )

            if not search_results["projects"]:
                # No matches - fall back to web search
                logger.info("No matching properties found, falling back to web search")
                web_result = web_search_service.search_and_answer(
                    query=request.query,
                    topic_hint="Real estate properties Bangalore"
                )

                response_time_ms = int((time.time() - start_time) * 1000)

                if request.user_id:
                    await supabase_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent=intent,
                        answered=True,
                        confidence_score="Low (External)",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )

                return ChatQueryResponse(
                    answer=web_result["answer"],
                    sources=[SourceInfo(**s) for s in web_result.get("sources", [])],
                    confidence=web_result.get("confidence", "Low"),
                    intent=intent,
                    refusal_reason=None,
                    response_time_ms=response_time_ms
                )

            # Format structured response
            formatted = response_formatter.format_property_search_results(
                projects=search_results["projects"],
                query=request.query,
                filters=filters.dict(exclude_none=True)
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            if request.user_id:
                await supabase_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent=intent,
                    answered=True,
                    confidence_score=formatted.confidence,
                    response_time_ms=response_time_ms,
                    project_id=request.project_id
                )

            logger.info(f"Property search completed in {response_time_ms}ms with {len(search_results['projects'])} matches")

            return ChatQueryResponse(
                answer=formatted.answer,
                sources=[],  # Property searches don't use chunk sources
                confidence=formatted.confidence,
                intent=intent,
                refusal_reason=None,
                response_time_ms=response_time_ms
            )

        # Step 3: For unsupported intents, try web search fallback instead of refusing
        if intent == "unsupported":
            logger.info("Unsupported intent, trying web search fallback")
            web_result = web_search_service.search_and_answer(
                query=request.query,
                topic_hint="Brigade Group real estate Bangalore"
            )
            
            if web_result.get("answer") and web_result.get("is_external", False):
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Log as answered with external source
                if request.user_id:
                    await supabase_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent=intent,
                        answered=True,
                        confidence_score="Low (External)",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )
                
                return ChatQueryResponse(
                    answer=web_result["answer"],
                    sources=[SourceInfo(**s) for s in web_result.get("sources", [])],
                    confidence=web_result.get("confidence", "Low"),
                    intent=intent,
                    refusal_reason=None,
                    response_time_ms=response_time_ms
                )

        # Step 3: Retrieve similar document chunks
        chunks = await retrieval_service.retrieve_similar_chunks(
            query=request.query,
            project_id=request.project_id,
            source_type="internal"  # Phase 1: internal only
        )

        logger.info(f"Retrieved {len(chunks)} chunks")

        # Step 4: Calculate confidence
        confidence = confidence_scorer.score_confidence(chunks)
        logger.info(f"Confidence: {confidence}")

        # Step 5: Refusal logic - but with web search fallback
        should_refuse, refusal_reason = refusal_handler.should_refuse(
            intent=intent,
            chunks=chunks,
            confidence=confidence
        )

        # If we should refuse due to no relevant info, try web search fallback
        if should_refuse and refusal_reason == "no_relevant_info":
            logger.info("No internal docs found, trying web search fallback")
            web_result = web_search_service.search_and_answer(
                query=request.query,
                topic_hint="Brigade Group real estate"
            )
            
            if web_result.get("answer") and web_result.get("is_external", False):
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Log as answered with external source
                if request.user_id:
                    await supabase_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent=intent,
                        answered=True,
                        confidence_score="Low (External)",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )
                
                return ChatQueryResponse(
                    answer=web_result["answer"],
                    sources=[SourceInfo(**s) for s in web_result.get("sources", [])],
                    confidence=web_result.get("confidence", "Low"),
                    intent=intent,
                    refusal_reason=None,
                    response_time_ms=response_time_ms
                )

        # Original refusal logic for other reasons
        if should_refuse:
            refusal_response = refusal_handler.get_refusal_response(
                refusal_reason=refusal_reason,
                query=request.query
            )

            # Log query
            if request.user_id:
                await supabase_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent=intent,
                    answered=False,
                    refusal_reason=refusal_reason,
                    response_time_ms=int((time.time() - start_time) * 1000),
                    project_id=request.project_id
                )

            return ChatQueryResponse(
                **refusal_response,
                response_time_ms=int((time.time() - start_time) * 1000)
            )

        # Step 6: Generate answer (with persona support)
        if request.persona:
            # Phase 2: Persona-based pitch
            result = persona_pitch_generator.generate_persona_pitch(
                query=request.query,
                chunks=chunks,
                persona=request.persona
            )
        elif intent == "comparison":
            # Multi-project comparison
            result = answer_generator.generate_comparison_answer(
                query=request.query,
                chunks=chunks
            )
        else:
            # Standard answer
            result = answer_generator.generate_answer(
                query=request.query,
                chunks=chunks,
                intent=intent,
                confidence=confidence
            )

        # Step 7: Validate answer (anti-hallucination check)
        if refusal_handler.detect_hallucination_risk(result["answer"], chunks):
            logger.warning("Hallucination risk detected - refusing")
            refusal_response = refusal_handler.get_refusal_response(
                refusal_reason="insufficient_confidence"
            )

            # Log query
            if request.user_id:
                await supabase_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent=intent,
                    answered=False,
                    refusal_reason="hallucination_risk",
                    response_time_ms=int((time.time() - start_time) * 1000),
                    project_id=request.project_id
                )

            return ChatQueryResponse(
                **refusal_response,
                response_time_ms=int((time.time() - start_time) * 1000)
            )

        # Step 8: Log successful query
        response_time_ms = int((time.time() - start_time) * 1000)

        if request.user_id:
            await supabase_client.log_query(
                user_id=request.user_id,
                query=request.query,
                intent=intent,
                answered=True,
                confidence_score=confidence,
                response_time_ms=response_time_ms,
                project_id=request.project_id
            )

        logger.info(f"Query processed successfully in {response_time_ms}ms")

        return ChatQueryResponse(
            answer=result["answer"],
            sources=[SourceInfo(**source) for source in result["sources"]],
            confidence=result["confidence"],
            intent=intent,
            refusal_reason=None,
            response_time_ms=response_time_ms
        )

    except Exception as e:
        logger.error(f"Error processing query: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.get("/api/projects", response_model=List[ProjectInfo])
async def get_projects(user_id: str):
    """
    Get list of projects accessible by user.

    Args:
        user_id: User ID from authentication

    Returns:
        List of projects the user can query
    """
    try:
        projects = await supabase_client.get_user_projects(user_id)

        return [
            ProjectInfo(
                id=p["id"],
                name=p["name"],
                location=p["location"],
                status=p["status"],
                rera_number=p.get("rera_number")
            )
            for p in projects
        ]

    except Exception as e:
        logger.error(f"Error fetching projects: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching projects: {str(e)}")


@app.get("/api/projects/{project_id}", response_model=ProjectInfo)
async def get_project(project_id: str):
    """
    Get details of a specific project.

    Args:
        project_id: Project UUID

    Returns:
        Project information
    """
    try:
        project = await supabase_client.get_project_by_id(project_id)

        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        return ProjectInfo(
            id=project["id"],
            name=project["name"],
            location=project["location"],
            status=project["status"],
            rera_number=project.get("rera_number")
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching project: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching project: {str(e)}")


# === Phase 2 Endpoints ===

@app.get("/api/personas")
async def get_personas():
    """Get list of available buyer personas."""
    try:
        return persona_pitch_generator.get_available_personas()
    except Exception as e:
        logger.error(f"Error fetching personas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/compare")
async def compare_projects(
    query: str,
    project_ids: Optional[List[str]] = None,
    user_id: Optional[str] = None
):
    """
    Compare multiple projects based on a query.

    Args:
        query: Comparison question
        project_ids: Optional list of project IDs to compare
        user_id: User ID for logging

    Returns:
        Comparison answer with sources from multiple projects
    """
    start_time = time.time()

    try:
        # Retrieve chunks from all or specified projects
        if project_ids and len(project_ids) > 1:
            grouped_chunks = await multi_project_retrieval.retrieve_for_comparison(
                query=query,
                project_ids=project_ids
            )
            # Flatten for answer generation
            chunks = [chunk for chunks_list in grouped_chunks.values() for chunk in chunks_list]
        else:
            # Retrieve from all projects
            chunks = await retrieval_service.retrieve_similar_chunks(query=query)

        # Generate comparison answer
        result = answer_generator.generate_comparison_answer(
            query=query,
            chunks=chunks
        )

        response_time_ms = int((time.time() - start_time) * 1000)

        if user_id:
            await supabase_client.log_query(
                user_id=user_id,
                query=query,
                intent="comparison",
                answered=True,
                confidence_score=result["confidence"],
                response_time_ms=response_time_ms
            )

        return {
            "answer": result["answer"],
            "sources": result["sources"],
            "confidence": result["confidence"],
            "response_time_ms": response_time_ms
        }

    except Exception as e:
        logger.error(f"Error in comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/filtered-search")
async def filtered_search(request: ChatQueryRequest):
    """
    Natural language property search across all projects with structured filtering.

    Handles queries like:
    - "2bhk under 3cr in Bangalore"
    - "3bhk ready to move whitefield under 5cr"
    - "affordable 2bhk possession 2027"
    - "show me brigade 3bhk options"

    This endpoint:
    1. Extracts structured filters from natural language
    2. Performs SQL filtering to narrow down projects
    3. Executes vector search within filtered subset
    4. Groups results by project with expandable units
    5. Falls back to web search if no matches found

    Args:
        request: Chat query request with natural language query

    Returns:
        Multiple matching projects with unit details
    """
    start_time = time.time()

    try:
        logger.info(f"Filtered search query: {request.query}")

        # Step 1: Extract filters from query
        filters = filter_extractor.extract_filters(request.query)
        logger.info(f"Extracted filters: {filters.dict(exclude_none=True)}")

        # Step 2: Hybrid retrieval (SQL + vector search)
        search_results = await hybrid_retrieval.search_with_filters(
            query=request.query,
            filters=filters
        )

        # Step 3: Check if any results found
        if not search_results["projects"]:
            # Fallback to web search
            logger.info("No matching projects found, falling back to web search")
            web_result = web_search_service.search_and_answer(
                query=request.query,
                topic_hint="Real estate properties Bangalore"
            )

            response_time_ms = int((time.time() - start_time) * 1000)

            # Log query
            if request.user_id:
                await supabase_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent="structured_search",
                    answered=True,
                    confidence_score="Low (External)",
                    response_time_ms=response_time_ms
                )

            return {
                "query": request.query,
                "filters": filters.dict(exclude_none=True),
                "matching_projects": 0,
                "projects": [],
                "web_fallback": {
                    "answer": web_result.get("answer"),
                    "sources": web_result.get("sources", [])
                },
                "search_method": "web_fallback",
                "response_time_ms": response_time_ms
            }

        # Step 4: Format projects for response
        formatted_projects = []
        for project in search_results["projects"]:
            formatted_projects.append({
                "project_id": project["project_id"],
                "project_name": project["project_name"],
                "developer_name": project.get("developer_name"),
                "location": f"{project.get('locality', '')}, {project.get('city', '')}".strip(", "),
                "full_address": project.get("location"),
                "rera_number": project.get("rera_number"),
                "status": project.get("status"),
                "matching_unit_count": project["unit_count"],
                "price_range": {
                    "min_inr": project["price_range"]["min"],
                    "max_inr": project["price_range"]["max"],
                    "min_display": project["price_range"]["min_display"],
                    "max_display": project["price_range"]["max_display"]
                },
                "sample_units": project["matching_units"][:3],  # Show first 3
                "all_units": project["matching_units"] if project["unit_count"] <= 10 else None,
                "can_expand": project.get("can_expand", False),
                "relevant_info": [
                    {
                        "content": chunk.get("content", "")[:200] + "...",
                        "section": chunk.get("section", ""),
                        "similarity": chunk.get("similarity", 0)
                    }
                    for chunk in project.get("relevant_chunks", [])[:2]
                ]
            })

        response_time_ms = int((time.time() - start_time) * 1000)

        # Log query
        if request.user_id:
            await supabase_client.log_query(
                user_id=request.user_id,
                query=request.query,
                intent="structured_search",
                answered=True,
                confidence_score="High" if search_results["search_method"] == "hybrid" else "Medium",
                response_time_ms=response_time_ms
            )

        return {
            "query": request.query,
            "filters": search_results["filters_used"],
            "matching_projects": search_results["total_matching_projects"],
            "projects": formatted_projects,
            "search_method": search_results["search_method"],
            "response_time_ms": response_time_ms
        }

    except Exception as e:
        logger.error(f"Error in filtered search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# === Admin Endpoints (Phase 2) ===

class QueryAnalytics(BaseModel):
    """Query analytics response."""
    total_queries: int
    answered_queries: int
    refused_queries: int
    refusal_rate: float
    avg_response_time_ms: float
    top_intents: List[Dict[str, Any]]
    recent_refusals: List[Dict[str, Any]]


@app.get("/api/admin/analytics", response_model=QueryAnalytics)
async def get_analytics(user_id: str, days: int = 7):
    """
    Get query analytics for the past N days.

    Args:
        user_id: Admin user ID
        days: Number of days to analyze

    Returns:
        Analytics data
    """
    try:
        # Verify admin role (simplified for now)
        # In production, check user_profiles.role == 'admin'

        # Query Supabase for analytics
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=days)

        # Get query logs
        response = supabase_client.client.table("query_logs").select("*").gte("created_at", cutoff_date.isoformat()).execute()

        logs = response.data if response.data else []

        # Calculate metrics
        total = len(logs)
        answered = sum(1 for log in logs if log.get("answered"))
        refused = total - answered
        refusal_rate = (refused / total * 100) if total > 0 else 0

        # Avg response time
        response_times = [log.get("response_time_ms", 0) for log in logs if log.get("response_time_ms")]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0

        # Top intents
        from collections import Counter
        intent_counts = Counter(log.get("intent") for log in logs if log.get("intent"))
        top_intents = [{"intent": intent, "count": count} for intent, count in intent_counts.most_common(5)]

        # Recent refusals
        recent_refusals = [
            {
                "query": log.get("query", ""),
                "refusal_reason": log.get("refusal_reason", ""),
                "created_at": log.get("created_at", "")
            }
            for log in sorted(logs, key=lambda x: x.get("created_at", ""), reverse=True)
            if not log.get("answered")
        ][:10]

        return QueryAnalytics(
            total_queries=total,
            answered_queries=answered,
            refused_queries=refused,
            refusal_rate=round(refusal_rate, 2),
            avg_response_time_ms=round(avg_response_time, 2),
            top_intents=top_intents,
            recent_refusals=recent_refusals
        )

    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# === Development Helper Endpoints ===

if settings.environment == "development":
    @app.get("/api/dev/test-retrieval")
    async def test_retrieval(query: str, project_id: Optional[str] = None):
        """Test retrieval without answer generation."""
        try:
            chunks = await retrieval_service.retrieve_similar_chunks(
                query=query,
                project_id=project_id
            )

            return {
                "query": query,
                "chunks_retrieved": len(chunks),
                "chunks": [
                    {
                        "content": chunk["content"][:200] + "...",
                        "similarity": chunk["similarity"],
                        "section": chunk["section"],
                        "project": chunk["project_name"]
                    }
                    for chunk in chunks
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/dev/test-intent")
    async def test_intent(query: str):
        """Test intent classification."""
        try:
            intent = intent_classifier.classify_intent(query)
            return {"query": query, "intent": intent}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level="info"
    )
