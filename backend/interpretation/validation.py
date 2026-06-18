from __future__ import annotations

from datetime import UTC, datetime

from backend.assistant import AssistantGatewayResponse

from .models import (
    COCKPIT_INTERPRETATION_PROMPT_VERSION,
    COCKPIT_INTERPRETATION_SCHEMA_VERSION,
    CockpitInterpretationContext,
    CockpitInterpretationResult,
    InterpretationBullet,
)

_MAX_READING_CHARS = 900
_MAX_BULLET_CHARS = 320
_FORBIDDEN_PATTERNS = (
    "買うべき",
    "売るべき",
    "保有推奨",
    "買い推奨",
    "売り推奨",
    "必ず上がる",
    "必ず下がる",
    "購入してください",
    "売却してください",
    "strong buy",
    "strong sell",
)
_SCORE_CHANGE_PATTERNS = (
    "scoreを変更",
    "スコアを変更",
    "予測値を変更",
    "ランキングを変更",
    "再計算しました",
)


class CockpitInterpretationValidationError(ValueError):
    def __init__(self, reason: str, message: str | None = None) -> None:
        super().__init__(message or reason)
        self.reason = reason


def cockpit_interpretation_from_gateway_response(
    response: AssistantGatewayResponse,
    *,
    context: CockpitInterpretationContext,
    generated_at: datetime | None = None,
) -> CockpitInterpretationResult:
    if response.gateway_status != "ok":
        raise CockpitInterpretationValidationError(response.fallback_reason or "validation_error")
    values = [
        response.answer,
        *response.materials,
        *response.cautions,
        *response.next_checkpoints,
    ]
    if _has_forbidden_policy_text(values):
        raise CockpitInterpretationValidationError("policy_violation")
    if _has_score_change_text(values):
        raise CockpitInterpretationValidationError("policy_violation")
    referenced_ids = {item.section_id for item in response.referenced_sections}
    unknown_ids = referenced_ids - set(context.allowed_evidence_ids)
    if unknown_ids:
        raise CockpitInterpretationValidationError("unknown_evidence")

    warnings = [*context.warnings]
    if len(response.answer) > _MAX_READING_CHARS or any(
        len(item) > _MAX_BULLET_CHARS
        for item in [*response.materials, *response.cautions, *response.next_checkpoints]
    ):
        warnings.append("AI応答が長いため、画面表示用に一部を短くしました。")
    if not response.provider or not response.model or not response.profile:
        warnings.append("LLM接続メタ情報の一部が不足しています。")

    return CockpitInterpretationResult(
        symbol=context.symbol,
        company_name=context.company_name,
        status="live",
        overall_reading=_trim(response.answer, _MAX_READING_CHARS),
        positive_points=_bullets(
            response.materials,
            evidence_ids=sorted(referenced_ids),
            confidence=_confidence_value(response.confidence),
        ),
        caution_points=_bullets(
            response.cautions,
            evidence_ids=sorted(referenced_ids),
            confidence=_confidence_value(response.confidence),
        ),
        contradictions=_contradiction_bullets(response.cautions),
        uncertainties=_uncertainty_bullets(response.cautions),
        next_checks=_bullets(
            response.next_checkpoints,
            evidence_ids=sorted(referenced_ids),
            confidence=0.55,
        ),
        missing_fields=context.missing_fields,
        warnings=_dedupe(warnings),
        provider=response.provider,
        model=response.model,
        gateway_profile=response.profile,
        generated_at=_ensure_utc(generated_at or datetime.now(UTC)),
        prompt_version=COCKPIT_INTERPRETATION_PROMPT_VERSION,
        schema_version=COCKPIT_INTERPRETATION_SCHEMA_VERSION,
        context_hash=context.context_hash,
        fallback_reason=None,
        is_fallback=False,
    )


def _bullets(
    values: list[str],
    *,
    evidence_ids: list[str],
    confidence: float,
) -> list[InterpretationBullet]:
    result: list[InterpretationBullet] = []
    for value in values[:4]:
        normalized = _trim(value, _MAX_BULLET_CHARS)
        if not normalized:
            continue
        result.append(
            InterpretationBullet(
                title=_bullet_title(normalized),
                summary=normalized,
                evidence_ids=evidence_ids[:4],
                confidence=confidence,
            )
        )
    return result


def _contradiction_bullets(values: list[str]) -> list[InterpretationBullet]:
    selected = [
        value for value in values if any(word in value for word in ("矛盾", "一方", "反面"))
    ]
    return _bullets(selected[:3], evidence_ids=[], confidence=0.45)


def _uncertainty_bullets(values: list[str]) -> list[InterpretationBullet]:
    selected = [
        value
        for value in values
        if any(word in value for word in ("不確実", "不足", "未確認", "注意", "確認"))
    ]
    return _bullets(selected[:3], evidence_ids=[], confidence=0.45)


def _bullet_title(value: str) -> str:
    if "。" in value:
        return _trim(value.split("。", 1)[0], 48)
    if "、" in value:
        return _trim(value.split("、", 1)[0], 48)
    return _trim(value, 48)


def _has_forbidden_policy_text(values: list[str]) -> bool:
    joined = "\n".join(values).lower()
    return any(pattern.lower() in joined for pattern in _FORBIDDEN_PATTERNS)


def _has_score_change_text(values: list[str]) -> bool:
    joined = "\n".join(values).lower()
    return any(pattern.lower() in joined for pattern in _SCORE_CHANGE_PATTERNS)


def _confidence_value(value: str) -> float:
    return {"low": 0.35, "medium": 0.55, "high": 0.72}.get(value, 0.45)


def _trim(value: object, max_chars: int) -> str:
    text = str(value).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
