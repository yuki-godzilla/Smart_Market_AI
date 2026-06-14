from __future__ import annotations

from fastapi import FastAPI, HTTPException

from app.clients.ollama_client import OllamaClient, OllamaClientError
from app.config import get_settings
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import ErrorDetail, HealthResponse, ModelsResponse
from app.schemas.context_answer import ContextAnswerRequest, ContextAnswerResponse
from app.schemas.summarize import SummarizeRequest, SummarizeResponse
from app.services.chat_service import ChatService
from app.services.context_answer_service import ContextAnswerService
from app.services.model_router import model_profile_for_name
from app.services.summarize_service import SummarizeService

settings = get_settings()
app = FastAPI(title=settings.APP_NAME, version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.APP_NAME)


@app.get("/models", response_model=ModelsResponse)
def models() -> ModelsResponse:
    try:
        client = OllamaClient(settings)
        installed_models = client.list_models()
    except OllamaClientError as exc:
        raise provider_error_to_http_exception(exc) from exc
    default_profile = model_profile_for_name(settings.DEFAULT_LLM_PROFILE, settings=settings)
    configured_model = default_profile.model
    installed = configured_model in installed_models
    return ModelsResponse(
        provider=default_profile.provider,
        base_url=settings.OLLAMA_BASE_URL,
        default_profile=settings.DEFAULT_LLM_PROFILE,
        default_model=configured_model,
        installed_models=installed_models,
        configured_model_installed=installed,
        install_hint=None if installed else f"Please run: ollama pull {configured_model}",
    )


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
