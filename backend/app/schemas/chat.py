"""Pydantic schemas for the chat API."""
from typing import Any, Optional
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str

    model_config = {"json_schema_extra": {"example": {"message": "Why was Leclerc faster than Norris in qualifying?"}}}


class ChatResponse(BaseModel):
    answer: str
    intent: str
    sources: list[str]
    graph_context: dict[str, Any]
    analytics: dict[str, Any]
    documents: list[dict[str, Any]]
    error: Optional[str] = None
