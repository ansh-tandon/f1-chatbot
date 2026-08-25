"""POST /api/chat endpoint."""
import logging
from fastapi import APIRouter, HTTPException
from app.schemas.chat import ChatRequest, ChatResponse
from app.agent.orchestrator import orchestrate
from app.rag.context_builder import build_context
from app.agent.llm import ask_llm

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Main chat endpoint.
    Orchestrates across Neo4j, PostgreSQL, FastF1 analytics, and Qdrant,
    then generates a grounded LLM answer.
    """
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    message = request.message.strip()

    try:
        # 1. Orchestrate: classify intent, gather structured data
        orch_result = orchestrate(message)

        # 2. Build compact context for LLM
        context = build_context(orch_result, message)

        # 3. Ask LLM with grounded context
        answer = ask_llm(message, context)

        return ChatResponse(
            answer=answer,
            intent=orch_result.intent.value,
            sources=orch_result.sources_used,
            graph_context=orch_result.graph_context,
            analytics=orch_result.analytics,
            documents=orch_result.documents,
            error=orch_result.error,
        )

    except Exception as e:
        log.error(f"Chat endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
