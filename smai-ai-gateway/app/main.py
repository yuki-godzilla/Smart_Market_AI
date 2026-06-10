from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.config import get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import HealthResponse
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services.chat_service import ChatService
from app.services.summarize_service import SummarizeService

settings = get_settings()
app = FastAPI(title=settings.APP_NAME, version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.APP_NAME)


@app.post("/api/v1/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        service = ChatService(OllamaClient(settings))
        return service.chat(request)
    except OllamaClientError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": str(exc), "provider": "ollama"},
        ) from exc


@app.post("/api/v1/summarize", response_model=SummarizeResponse)
def summarize(request: SummarizeRequest) -> SummarizeResponse:
    try:
        service = SummarizeService(OllamaClient(settings))
        return service.summarize(request)
    except OllamaClientError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": str(exc), "provider": "ollama"},
        ) from exc
