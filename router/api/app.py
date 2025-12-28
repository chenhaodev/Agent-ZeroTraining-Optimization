"""
FastAPI application for Smart Router API.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from loguru import logger
import sys

from router.api.schemas import (
    RouteRequest, RouteResponse, WeaknessPattern,
    PromptRequest, PromptResponse,
    HealthResponse, StatsResponse, ReloadResponse
)
from router.api.llm_schemas import (
    ChatCompletionRequest, ChatCompletionResponse,
    ChatMessage, ErrorResponse
)
from router.core.decision_engine import get_decision_engine, reload_decision_engine
from router.utils.prompt_builder import PromptBuilder
from router.services.llm_client import get_llm_client
from router.config.settings import get_router_settings
from fastapi.responses import StreamingResponse

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add("outputs/router/logs/router.log", rotation="10 MB", level="DEBUG")


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    settings = get_router_settings()

    app = FastAPI(
        title="Smart Router API",
        description="Intelligent routing for LLM queries with weakness pattern matching",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure as needed for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize components on startup
    @app.on_event("startup")
    async def startup_event():
        """Initialize router on startup"""
        logger.info("=" * 60)
        logger.info("Smart Router API Starting...")
        logger.info("=" * 60)

        # Initialize decision engine
        engine = get_decision_engine()
        stats = engine.get_stats()

        logger.info(f"✓ Loaded {stats['total_entities']} entities")
        logger.info(f"✓ Loaded {stats['weakness_patterns']} weakness patterns")
        logger.info(f"✓ Hot-reload: {'enabled' if settings.ENABLE_HOT_RELOAD else 'disabled'}")
        logger.info(f"🚀 Router API running on http://{settings.HOST}:{settings.PORT}")
        logger.info("=" * 60)

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown"""
        logger.info("Smart Router API shutting down...")

    # ===== API Endpoints =====

    @app.post("/api/v1/route", response_model=RouteResponse, tags=["Routing"])
    async def route_question(request: RouteRequest) -> RouteResponse:
        """
        Get routing decision for a question.

        This endpoint returns:
        - Whether to use pattern retrieval retrieval
        - Matched weakness patterns
        - Confidence scores and reasoning

        The router automatically checks for data updates if hot-reload is enabled.
        """
        try:
            engine = get_decision_engine()

            decision = engine.get_routing_decision(
                question=request.question,
                entity_type=request.entity_type,
                min_confidence=request.min_confidence or 0.70,
                auto_reload=settings.ENABLE_HOT_RELOAD
            )

            # Convert weakness patterns to schema
            weakness_patterns = [
                WeaknessPattern(**pattern)
                for pattern in decision['weakness_patterns']
            ]

            return RouteResponse(
                use_patterns=decision['use_patterns'],
                rag_reason=decision['rag_reason'],
                rag_confidence=decision['rag_confidence'],
                weakness_patterns=weakness_patterns,
                has_weaknesses=decision['has_weaknesses'],
                last_reload_check=decision['last_reload_check']
            )

        except Exception as e:
            logger.error(f"Routing error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/prompt", response_model=PromptResponse, tags=["Routing"])
    async def get_enhanced_prompt(request: PromptRequest) -> PromptResponse:
        """
        Get enhanced prompt with weakness patterns injected.

        This endpoint:
        1. Gets routing decision (pattern retrieval + weakness patterns)
        2. Builds enhanced prompt with patterns
        3. Returns ready-to-use prompt for LLM

        Use this endpoint to get a complete prompt for your LLM call.
        """
        try:
            engine = get_decision_engine()
            prompt_builder = PromptBuilder()

            # Get routing decision
            decision = engine.get_routing_decision(
                question=request.question,
                entity_type=request.entity_type,
                auto_reload=settings.ENABLE_HOT_RELOAD
            )

            # Build enhanced prompt
            enhanced_prompt = prompt_builder.build_prompt(
                base_prompt=request.base_prompt,
                weakness_patterns=decision['weakness_patterns']
            )

            # Convert for response
            weakness_patterns = [
                WeaknessPattern(**pattern)
                for pattern in decision['weakness_patterns']
            ]

            routing_response = RouteResponse(
                use_patterns=decision['use_patterns'],
                rag_reason=decision['rag_reason'],
                rag_confidence=decision['rag_confidence'],
                weakness_patterns=weakness_patterns,
                has_weaknesses=decision['has_weaknesses'],
                last_reload_check=decision['last_reload_check']
            )

            return PromptResponse(
                enhanced_prompt=enhanced_prompt,
                use_patterns=decision['use_patterns'],
                weakness_patterns_applied=len(decision['weakness_patterns']),
                routing_decision=routing_response
            )

        except Exception as e:
            logger.error(f"Prompt building error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["Monitoring"])
    async def health_check() -> HealthResponse:
        """
        Health check endpoint.

        Returns service status and basic statistics.
        """
        try:
            engine = get_decision_engine()
            stats = engine.get_stats()

            # Determine status
            if stats['total_entities'] == 0 or stats['weakness_patterns'] == 0:
                status = "degraded"
            else:
                status = "healthy"

            return HealthResponse(
                status=status,
                version="1.0.0",
                entities_loaded=stats['total_entities'],
                weaknesses_loaded=stats['weakness_patterns'],
                hot_reload_enabled=settings.ENABLE_HOT_RELOAD,
                last_reload_check=stats['last_reload_check']
            )

        except Exception as e:
            logger.error(f"Health check error: {e}")
            return HealthResponse(
                status="unhealthy",
                version="1.0.0",
                entities_loaded=0,
                weaknesses_loaded=0,
                hot_reload_enabled=False,
                last_reload_check=datetime.now().isoformat()
            )

    @app.get("/api/v1/stats", response_model=StatsResponse, tags=["Monitoring"])
    async def get_stats() -> StatsResponse:
        """
        Get detailed router statistics.

        Returns:
        - Entity counts by category
        - Weakness pattern statistics
        - File modification times
        - Last reload check time
        """
        try:
            engine = get_decision_engine()
            stats = engine.get_stats()

            return StatsResponse(**stats)

        except Exception as e:
            logger.error(f"Stats error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/v1/reload", response_model=ReloadResponse, tags=["Management"])
    async def force_reload() -> ReloadResponse:
        """
        Force reload of router data.

        This endpoint:
        - Checks if data files have been updated
        - Reloads if updates detected
        - Can be called manually to force reload

        Useful after running auto-evaluation that generates new weaknesses.
        """
        try:
            engine = get_decision_engine()

            # Check for updates
            reloaded = engine.check_for_updates()

            # If no updates detected, force reload anyway
            if not reloaded:
                logger.info("No updates detected, forcing reload...")
                engine = reload_decision_engine()
                reloaded = True

            stats = engine.get_stats()

            return ReloadResponse(
                reloaded=reloaded,
                message="Data reloaded successfully" if reloaded else "No updates detected",
                entities_loaded=stats['total_entities'],
                weaknesses_loaded=stats['weakness_patterns'],
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            logger.error(f"Reload error: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/v1/chat/completions", response_model=ChatCompletionResponse, tags=["LLM API"])
    async def chat_completions(request: ChatCompletionRequest):
        """
        OpenAI-compatible chat completions endpoint with smart routing.

        This is a drop-in replacement for OpenAI's /v1/chat/completions endpoint.
        It adds intelligent routing and weakness pattern enhancement.

        Features:
        - Compatible with OpenAI SDK (just change the base_url)
        - Automatic prompt enhancement based on question
        - Weakness pattern injection
        - pattern retrieval decision making
        - Streaming support

        Router-specific parameters (optional):
        - x_entity_type: Hint for better routing (e.g., "diseases")
        - x_min_confidence: Minimum pattern retrieval confidence threshold (default: 0.70)
        - x_disable_routing: Skip routing, call LLM directly (default: False)
        - x_disable_weaknesses: Skip weakness patterns (default: False)

        Example usage:
        ```python
        from openai import OpenAI

        # Just change the base_url!
        client = OpenAI(
            api_key="your-deepseek-key",
            base_url="http://localhost:8000"  # Point to router
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "user", "content": "什么是糖尿病？"}
            ]
        )
        ```
        """
        try:
            # Handle streaming separately
            if request.stream:
                return await _handle_streaming_completion(request)

            # Disable routing if requested
            if request.x_disable_routing:
                logger.info("Routing disabled, calling LLM directly")
                llm_client = get_llm_client()
                response = await llm_client.async_chat_completion(request, enhanced_messages=None)
                response.x_routing_decision = None
                response.x_enhanced_prompt_used = False
                return response

            # Step 1: Extract user question from messages
            user_messages = [m for m in request.messages if m.role == "user"]
            if not user_messages:
                raise HTTPException(status_code=400, detail="No user message found")

            question = user_messages[-1].content  # Last user message

            # Step 2: Get routing decision
            logger.info(f"Getting routing decision for: {question[:100]}...")
            engine = get_decision_engine()
            decision = engine.get_routing_decision(
                question=question,
                entity_type=request.x_entity_type,
                min_confidence=request.x_min_confidence or 0.70,
                auto_reload=settings.ENABLE_HOT_RELOAD
            )

            logger.info(f"Routing decision: use_patterns={decision['use_patterns']}, "
                       f"confidence={decision['rag_confidence']:.2f}, "
                       f"weaknesses={len(decision['weakness_patterns'])}")

            # Step 3: Build enhanced prompt
            enhanced_messages = None
            if not request.x_disable_weaknesses and decision['weakness_patterns']:
                prompt_builder = PromptBuilder()

                # Find or create system message
                system_message_idx = next(
                    (i for i, m in enumerate(request.messages) if m.role == "system"),
                    None
                )

                if system_message_idx is not None:
                    # Enhance existing system prompt
                    base_prompt = request.messages[system_message_idx].content
                else:
                    # Use default base prompt
                    base_prompt = None

                # Build enhanced prompt with weakness patterns
                enhanced_system_prompt = prompt_builder.build_prompt(
                    base_prompt=base_prompt,
                    weakness_patterns=decision['weakness_patterns']
                )

                # Reconstruct messages with enhanced system prompt
                enhanced_messages = []

                # Add enhanced system message first
                enhanced_messages.append(ChatMessage(
                    role="system",
                    content=enhanced_system_prompt
                ))

                # Add other messages (skip original system if existed)
                for i, msg in enumerate(request.messages):
                    if msg.role != "system":
                        enhanced_messages.append(msg)

                logger.info(f"Enhanced prompt with {len(decision['weakness_patterns'])} weakness patterns")

            # Step 4: Call LLM API
            llm_client = get_llm_client()
            response = await llm_client.async_chat_completion(
                request=request,
                enhanced_messages=enhanced_messages
            )

            # Step 5: Add routing metadata to response
            response.x_routing_decision = decision
            response.x_enhanced_prompt_used = enhanced_messages is not None

            return response

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Chat completion error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    async def _handle_streaming_completion(request: ChatCompletionRequest):
        """Handle streaming chat completion"""
        try:
            # Get routing decision first (same as non-streaming)
            user_messages = [m for m in request.messages if m.role == "user"]
            if not user_messages:
                raise HTTPException(status_code=400, detail="No user message found")

            question = user_messages[-1].content

            # Get routing decision
            routing_decision = None
            enhanced_messages = None

            if not request.x_disable_routing:
                engine = get_decision_engine()
                decision = engine.get_routing_decision(
                    question=question,
                    entity_type=request.x_entity_type,
                    min_confidence=request.x_min_confidence or 0.70,
                    auto_reload=settings.ENABLE_HOT_RELOAD
                )
                routing_decision = decision

                # Build enhanced prompt if needed
                if not request.x_disable_weaknesses and decision['weakness_patterns']:
                    prompt_builder = PromptBuilder()

                    system_message_idx = next(
                        (i for i, m in enumerate(request.messages) if m.role == "system"),
                        None
                    )

                    base_prompt = request.messages[system_message_idx].content if system_message_idx is not None else None
                    enhanced_system_prompt = prompt_builder.build_prompt(
                        base_prompt=base_prompt,
                        weakness_patterns=decision['weakness_patterns']
                    )

                    enhanced_messages = [ChatMessage(role="system", content=enhanced_system_prompt)]
                    for msg in request.messages:
                        if msg.role != "system":
                            enhanced_messages.append(msg)

            # Stream response
            llm_client = get_llm_client()

            return StreamingResponse(
                llm_client.async_chat_completion_stream(
                    request=request,
                    enhanced_messages=enhanced_messages,
                    routing_decision=routing_decision
                ),
                media_type="text/event-stream"
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Streaming completion error: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/", tags=["General"])
    async def root():
        """Root endpoint"""
        return {
            "service": "Smart Router API",
            "version": "1.0.0",
            "status": "running",
            "docs": "/docs"
        }

    return app


# Create app instance
app = create_app()
