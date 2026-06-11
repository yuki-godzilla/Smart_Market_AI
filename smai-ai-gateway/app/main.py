from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.config import get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ErrorDetail, HealthResponse
from app.schemas.context_answer import ContextAnswerRequest, ContextAnswerResponse
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services.chat_service import ChatService
from app.services.context_answer_service import ContextAnswerService
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
        raise provider_error_to_http_exception(exc) from exc


@app.post("/api/v1/summarize", response_model=SummarizeResponse)
def summarize(request: SummarizeRequest) -> SummarizeResponse:
    try:
        service = SummarizeService(OllamaClient(settings))
        return service.summarize(request)
    except OllamaClientError as exc:
        raise provider_error_to_http_exception(exc) from exc


@app.post("/api/v1/context-answer", response_model=ContextAnswerResponse)
def context_answer(request: ContextAnswerRequest) -> ContextAnswerResponse:
    try:
        service = ContextAnswerService(OllamaClient(settings))
        return service.answer(request)
    except OllamaClientError as exc:
        raise provider_error_to_http_exception(exc) from exc


def provider_error_to_http_exception(exc: OllamaClientError) -> HTTPException:
    detail = ErrorDetail(
        error=str(exc),
        provider=exc.provider,
        code=exc.code,
        retryable=exc.retryable,
    )
    return HTTPException(status_code=exc.http_status, detail=detail.model_dump())
