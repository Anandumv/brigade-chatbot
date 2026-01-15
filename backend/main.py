"""
Main FastAPI application for Real Estate Sales Intelligence Chatbot.
Powered by Pixeltable - No Supabase Required!
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import logging
from contextlib import asynccontextmanager
import sys
import os
# Add the vendor directory to sys.path to allow importing local packages (e.g. patched pixeltable)
# We add it at the BEGINNING of sys.path to ensure local versions take precedence
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'vendor')))

import nest_asyncio


# Apply nest_asyncio to allow re-entrant event loops
# Wrap in try-except because it fails with 'uvloop' (default on Render)
try:
    nest_asyncio.apply()
except ValueError:
    print("WARNING: Could not patch event loop (likely uvloop). Pixeltable sync might flak.")
except Exception as e:
    print(f"WARNING: nest_asyncio failed: {e}")

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
from services.sales_conversation import sales_conversation, get_filter_options, SalesIntent
from services.intelligent_sales import intelligent_sales, ConversationContext, SalesIntent as AISalesIntent
from services.sales_intelligence import sales_intelligence

# Pixeltable-only mode - replacing Supabase
from database.pixeltable_client import pixeltable_client

# Force reload triggers
# Last updated: Migrated to Pixeltable-only architecture

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
    
    # Auto-seed projects if table is empty
    try:
        from database.pixeltable_setup import get_projects_table, initialize_pixeltable
        import json
        import os
        import pixeltable as pxt
        
        # Ensure tables exist
        initialize_pixeltable()
        
        projects_table = get_projects_table()
        count = projects_table.count()
        logger.info(f"Projects table has {count} rows.")
        
        if count == 0:
            seed_file = os.path.join(os.path.dirname(__file__), 'data', 'seed_projects.json')
            if os.path.exists(seed_file):
                with open(seed_file, 'r') as f:
                    seed_data = json.load(f)
                projects_table.insert(seed_data)
                logger.info(f"Seeded {len(seed_data)} projects from seed_projects.json")
            else:
                logger.warning(f"Seed file not found: {seed_file}")
    except Exception as e:
        logger.error(f"Auto-seed failed: {e}")
    
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
    session_id: Optional[str] = None  # For multi-turn conversations
    persona: Optional[str] = None  # Phase 2: persona-based pitches
    filters: Optional[Dict[str, Any]] = None  # UI-selected filters


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
    project_info: Optional[Dict[str, Any]] = None
    suggested_actions: Optional[List[str]] = None  # Dynamic quick reply chips


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


@app.post("/admin/refresh-projects")
async def admin_refresh_projects(x_admin_key: str = Header(None)):
    """
    Admin endpoint to force re-seed/update project data from seed_projects.json.
    """
    import json
    import os
    import pixeltable as pxt
    
    # Simple security: First 8 chars of OpenAI key or 'secret'
    expected_key = settings.openai_api_key[:8] if settings.openai_api_key else "secret"
    
    if x_admin_key != expected_key:
         raise HTTPException(status_code=403, detail="Invalid Admin Key")

    try:
        # Drop existing and recreate with fresh data
        try:
            pxt.drop_table('brigade.projects', force=True)
            logger.info("Dropped existing projects table")
        except Exception as e:
            logger.warning(f"Could not drop table: {e}")
        
        # Create fresh table with schema
        schema = {
            'project_id': pxt.String,
            'name': pxt.String,
            'developer': pxt.String,
            'location': pxt.String,
            'zone': pxt.String,
            'configuration': pxt.String,
            'budget_min': pxt.Int,
            'budget_max': pxt.Int,
            'possession_year': pxt.Int,
            'possession_quarter': pxt.String,
            'status': pxt.String,
            'rera_number': pxt.String,
            'description': pxt.String,
            'amenities': pxt.String,
            'usp': pxt.String,
        }
        
        projects = pxt.create_table('brigade.projects', schema)
        logger.info("Created fresh projects table")
        
        # Load from JSON
        seed_file = os.path.join(os.path.dirname(__file__), 'data', 'seed_projects.json')
        if os.path.exists(seed_file):
            with open(seed_file, 'r') as f:
                seed_data = json.load(f)
            projects.insert(seed_data)
            return {"status": "success", "message": f"Loaded {len(seed_data)} projects"}
        else:
            return {"status": "error", "message": f"Seed file not found: {seed_file}"}
            
    except Exception as e:
        logger.error(f"Admin refresh failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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

        # Extract and merge filters early (needed for context and search)
        filters = filter_extractor.extract_filters(request.query)
        if request.filters:
            logger.info(f"Merging explicit UI filters: {request.filters}")
            filters = filter_extractor.merge_filters(filters, request.filters)
        
        # Create conversation context
        context = ConversationContext(
            session_id=request.session_id or "",
            current_filters=request.filters or {},
            last_intent=intent.value if hasattr(intent, 'value') else str(intent)
        )

        # Step 1.5: Handle greetings immediately without RAG
        if intent == "greeting":
            response_time_ms = int((time.time() - start_time) * 1000)
            greeting_response = """👋 **Hello!** Welcome to Pinclick Genie!

I'm your AI-powered real estate assistant. I can help you with:

🏠 **Property Search** - "Show me 2BHK in Bangalore under 2 Cr"
🏢 **Project Details** - "Tell me about Brigade Citrine amenities"
💰 **Pricing Info** - "What's the price of 3BHK at Brigade Avalon?"
📍 **Location Info** - "Projects near Whitefield"
🤝 **Sales Support** - "Schedule a site visit" or "Arrange a meeting"

How can I assist you today?"""
            return ChatQueryResponse(
                answer=greeting_response,
                sources=[],
                confidence="High",
                intent="greeting",
                refusal_reason=None,
                response_time_ms=response_time_ms
            )

        # Step 1.6: Handle sales FAQ intents with intelligent GPT-4 handler
        if intent == "sales_faq":
            logger.info("Routing to intelligent sales FAQ handler")
            response_text, sales_intent, should_fallback, actions = await intelligent_sales.handle_query(
                query=request.query,
                context=context,
                session_id=request.session_id
            )
            
            if not should_fallback and response_text:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if request.user_id:
                    await pixeltable_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent=f"intelligent_faq_{sales_intent.value}",
                        answered=True,
                        confidence_score="High",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )
                
                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="High",
                    intent="intelligent_sales_faq",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=actions
                )

        # Step 1.7: Handle sales objection intents with intelligent handler
        if intent == "sales_objection":
            logger.info("Routing to intelligent sales objection handler")
            response_text, sales_intent, should_fallback, actions = await intelligent_sales.handle_query(
                query=request.query,
                context=context,
                session_id=request.session_id
            )
            
            if not should_fallback and response_text:
                response_time_ms = int((time.time() - start_time) * 1000)
                
                if request.user_id:
                    await pixeltable_client.log_query(
                        user_id=request.user_id,
                        query=request.query,
                        intent=f"intelligent_objection_{sales_intent.value}",
                        answered=True,
                        confidence_score="High",
                        response_time_ms=response_time_ms,
                        project_id=request.project_id
                    )
                
                return ChatQueryResponse(
                    answer=response_text,
                    sources=[],
                    confidence="High",
                    intent="intelligent_sales_objection",
                    refusal_reason=None,
                    response_time_ms=response_time_ms,
                    suggested_actions=actions
                )


        # Step 2: Route property_search to hybrid filtering (NEW FLOW)
        if intent == "property_search":
            logger.info("Routing to property search with hybrid filtering")
            logger.info(f"Using merged filters: {filters.dict(exclude_none=True)}")

            # Hybrid retrieval (SQL + vector search)
            # Use the filters we extracted/merged earlier
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
                    await pixeltable_client.log_query(
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
                await pixeltable_client.log_query(
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
                    await pixeltable_client.log_query(
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
                    await pixeltable_client.log_query(
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
                await pixeltable_client.log_query(
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
                await pixeltable_client.log_query(
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
            await pixeltable_client.log_query(
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
        projects = await pixeltable_client.get_user_projects(user_id)

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
        project = await pixeltable_client.get_project_by_id(project_id)

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


@app.get("/api/filters/options")
async def get_filter_options_endpoint():
    """
    Get all available filter options for frontend dropdowns.
    
    Returns:
        - configurations: List of BHK options (1-6)
        - locations: Grouped by area (North/East Bangalore)
        - budget_ranges: Price ranges in INR
        - possession_years: Available possession years (2024-2030 + Ready)
    """
    try:
        return get_filter_options()
    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/sales")
async def sales_chat_query(request: ChatQueryRequest):
    """
    Intelligent sales-focused chat endpoint powered by GPT-4.
    
    Provides:
    - Highly intelligent, context-aware responses
    - Natural language understanding for sales queries
    - Intelligent objection handling
    - Dynamic response generation
    - Falls back to RAG for property-specific queries
    """
    start_time = time.time()
    
    try:
        logger.info(f"Intelligent sales chat query: {request.query[:100]}...")
        
        # Use the intelligent GPT-4 powered handler
        response_text, sales_intent, should_fallback = await intelligent_sales.handle_query(
            query=request.query
        )
        
        if not should_fallback and response_text:
            response_time_ms = int((time.time() - start_time) * 1000)
            
            if request.user_id:
                await pixeltable_client.log_query(
                    user_id=request.user_id,
                    query=request.query,
                    intent=f"intelligent_sales_{sales_intent.value}",
                    answered=True,
                    confidence_score="High",
                    response_time_ms=response_time_ms,
                    project_id=request.project_id
                )
            
            logger.info(f"Intelligent sales response generated in {response_time_ms}ms")
            
            return ChatQueryResponse(
                answer=response_text,
                sources=[],
                confidence="High",
                intent=f"intelligent_sales_{sales_intent.value}",
                refusal_reason=None,
                response_time_ms=response_time_ms
            )
        
        # Fall back to regular chat endpoint for property queries
        logger.info("Falling back to regular chat processing for property/unknown query")
        return await chat_query(request)
        
    except Exception as e:
        logger.error(f"Error in intelligent sales chat: {e}", exc_info=True)
        # Fallback to regular handler on error
        try:
            return await chat_query(request)
        except:
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
            await pixeltable_client.log_query(
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
                await pixeltable_client.log_query(
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
            await pixeltable_client.log_query(
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

        # Use Pixeltable analytics
        analytics = pixeltable_client.get_analytics(days)
        
        # Format top intents
        top_intents = [
            {"intent": intent, "count": count}
            for intent, count in analytics.get('top_intents', {}).items()
        ][:5]

        return QueryAnalytics(
            total_queries=analytics.get('total_queries', 0),
            answered_queries=analytics.get('answered_queries', 0),
            refused_queries=analytics.get('refused_queries', 0),
            refusal_rate=round(analytics.get('refusal_rate', 0) * 100, 2),
            avg_response_time_ms=round(analytics.get('avg_response_time_ms', 0), 2),
            top_intents=top_intents,
            recent_refusals=analytics.get('recent_refusals', [])
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



# === Agent Flow Endpoint (STRICT MODE) ===
from services.flow_engine import execute_flow, FlowState, FlowResponse
from services.session_manager import session_manager

@app.post("/api/agent/flow", response_model=FlowResponse)
async def agent_flow_query(request: ChatQueryRequest):
    """
    Strict Flowchart-Driven Agent Logic.
    Does NOT use general RAG. Enforces the 10-node decision tree.
    """
    try:
        session_id = request.session_id or "default_agent_session"
        session = session_manager.get_or_create_session(session_id)
        
        # Load state
        current_state_data = session.flow_state
        if current_state_data:
            state = FlowState(**current_state_data)
        else:
            state = FlowState() # Start at Node 1
            
        # Execute Flow
        response = execute_flow(state, request.query)
        
        # Save state
        session.flow_state = state.dict()
        
        return response
        
    except Exception as e:
        logger.error(f"Agent flow error: {e}", exc_info=True)
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
