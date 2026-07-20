"""Append-only, point-in-time audit storage for live forecast predictions.

The audit is intentionally separate from runtime forecast calculation.  It freezes
the prediction that was observable at an origin and attaches an outcome only after
the requested number of later daily bars has become observable.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Iterator, Literal, Self, Sequence

from pydantic import ConfigDict, Field, model_validator

from backend.core.data_contracts import Bar, StrictBaseModel
from backend.forecast.evaluation import ForecastValidationPoint
from backend.forecast.model_policy import HORIZON_MODEL_POLICY_VERSION
from backend.forecast.service import (
    FORECAST_ROLE_CONFIDENCE_POLICY_VERSION,
    AdvancedForecastConsensus,
)

SEALED_AUDIT_SCHEMA_VERSION = "forecast-sealed-audit-v1"
SEALED_AUDIT_DATABASE_VERSION = 1
SEALED_AUDIT_INTERVAL_POLICY_VERSION = "advanced-consensus-quantile-range-v1"
DEFAULT_SEALED_AUDIT_DATABASE = Path("data/cache/forecast_sealed_audit.sqlite")
DEFAULT_SEALED_AUDIT_HORIZONS = (20, 40, 60, 80, 100, 120)

AuditCohort = Literal["new_calendar", "new_symbol", "mixed"]


class ForecastSealedAuditError(RuntimeError):
    """Base error for sealed audit persistence or integrity failures."""


class ForecastSealedAuditConflict(ForecastSealedAuditError):
    """Raised when an immutable audit row would be changed."""


class ForecastSealedAuditCorruptData(ForecastSealedAuditError):
    """Raised when persisted content fails schema or digest validation."""


class ForecastSealedAuditManifest(StrictBaseModel):
    """Predeclared cohort, policy versions, horizons, and adoption gates."""

    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())

    schema_version: str = SEALED_AUDIT_SCHEMA_VERSION
    manifest_id: str = Field(pattern=r"^fsa_[A-Za-z0-9_-]{8,96}$")
    created_at: datetime
    accept_origins_at_or_after: datetime
    cohort: AuditCohort
    symbols: list[str] = Field(min_length=1)
    horizons: list[int] = Field(min_length=1)
    source_revision: str = Field(min_length=1)
    expected_selection_policy_version: str = HORIZON_MODEL_POLICY_VERSION
    expected_confidence_policy_version: str = FORECAST_ROLE_CONFIDENCE_POLICY_VERSION
    interval_policy_version: str = SEALED_AUDIT_INTERVAL_POLICY_VERSION
    evaluation_role: Literal["new_sealed_audit"] = "new_sealed_audit"
    max_origin_age_days: int = Field(default=7, ge=0, le=14)
    min_cases_per_horizon: int = Field(default=100, ge=1)
    target_coverage: Decimal = Field(default=Decimal("0.60"), gt=0, lt=1)
    minimum_coverage: Decimal = Field(default=Decimal("0.55"), gt=0, lt=1)
    min_interval_score_improvement: Decimal = Field(
        default=Decimal("0.01"), ge=0, le=Decimal("0.25")
    )
    min_application_rate: Decimal = Field(default=Decimal("0.50"), ge=0, le=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        _require_aware(self.created_at, "created_at")
        _require_aware(self.accept_origins_at_or_after, "accept_origins_at_or_after")
        if self.accept_origins_at_or_after > self.created_at:
            raise ValueError("accept_origins_at_or_after must not follow created_at")
        if self.schema_version != SEALED_AUDIT_SCHEMA_VERSION:
            raise ValueError("unsupported sealed audit schema version")
        if self.symbols != sorted(set(self.symbols)):
            raise ValueError("symbols must be normalized, unique, and sorted")
        if any(symbol != _normalize_symbol(symbol) for symbol in self.symbols):
            raise ValueError("symbols must be uppercase and trimmed")
        if self.horizons != sorted(set(self.horizons)) or any(
            horizon < 1 for horizon in self.horizons
        ):
            raise ValueError("horizons must be positive, unique, and sorted")
        if self.minimum_coverage > self.target_coverage:
            raise ValueError("minimum_coverage must not exceed target_coverage")
        return self


class ForecastSealedPrediction(StrictBaseModel):
    """Immutable forecast output captured before the target was observable."""

    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())

    schema_version: str = SEALED_AUDIT_SCHEMA_VERSION
    prediction_id: str = Field(pattern=r"^fsp_[a-f0-9]{24}$")
    manifest_id: str = Field(pattern=r"^fsa_[A-Za-z0-9_-]{8,96}$")
    symbol: str = Field(min_length=1)
    market: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    regime: str = Field(min_length=1)
    model_name: Literal["forecast_consensus"] = "forecast_consensus"
    horizon_days: int = Field(ge=1)
    origin_at: datetime
    recorded_at: datetime
    origin_close: Decimal = Field(gt=0)
    forecast_close: Decimal = Field(ge=0)
    predicted_return: Decimal
    direction_predicted_return: Decimal
    predicted_return_lower: Decimal | None = None
    predicted_return_upper: Decimal | None = None
    confidence: str = Field(min_length=1)
    center_confidence: str = Field(min_length=1)
    direction_confidence: str = Field(min_length=1)
    selection_policy_version: str = Field(min_length=1)
    confidence_policy_version: str = Field(min_length=1)
    interval_policy_version: str = Field(min_length=1)
    horizon_band: str = Field(min_length=1)
    audit_status: str = Field(min_length=1)
    selection_mode: str = Field(min_length=1)
    selected_adapter_names: list[str] = Field(default_factory=list)
    center_adapter_names: list[str] = Field(default_factory=list)
    direction_adapter_names: list[str] = Field(default_factory=list)
    model_weights: dict[str, Decimal] = Field(default_factory=dict)
    model_disagreement: Decimal = Field(ge=0)
    source_provider: str = Field(min_length=1)
    source_bar_count: int = Field(ge=1)
    source_history_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_prediction(self) -> Self:
        _require_aware(self.origin_at, "origin_at")
        _require_aware(self.recorded_at, "recorded_at")
        if self.schema_version != SEALED_AUDIT_SCHEMA_VERSION:
            raise ValueError("unsupported sealed audit schema version")
        if self.symbol != _normalize_symbol(self.symbol):
            raise ValueError("symbol must be uppercase and trimmed")
        if self.recorded_at < self.origin_at:
            raise ValueError("recorded_at must not precede origin_at")
        interval = (self.predicted_return_lower, self.predicted_return_upper)
        if (interval[0] is None) != (interval[1] is None):
            raise ValueError("prediction interval must contain both lower and upper")
        if interval[0] is not None and interval[1] is not None:
            if interval[0] > self.predicted_return or self.predicted_return > interval[1]:
                raise ValueError("prediction interval must contain predicted_return")
        for names in (
            self.selected_adapter_names,
            self.center_adapter_names,
            self.direction_adapter_names,
        ):
            if len(names) != len(set(names)):
                raise ValueError("adapter names must be unique")
        if any(weight < 0 for weight in self.model_weights.values()):
            raise ValueError("model weights must be non-negative")
        return self


class ForecastSealedOutcome(StrictBaseModel):
    """Immutable realized return attached after a target daily bar matures."""

    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())

    schema_version: str = SEALED_AUDIT_SCHEMA_VERSION
    prediction_id: str = Field(pattern=r"^fsp_[a-f0-9]{24}$")
    target_at: datetime
    matured_at: datetime
    target_close: Decimal = Field(gt=0)
    actual_return: Decimal
    target_provider: str = Field(min_length=1)
    target_bar_offset: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        _require_aware(self.target_at, "target_at")
        _require_aware(self.matured_at, "matured_at")
        if self.schema_version != SEALED_AUDIT_SCHEMA_VERSION:
            raise ValueError("unsupported sealed audit schema version")
        if self.matured_at < self.target_at:
            raise ValueError("matured_at must not precede target_at")
        return self


class ForecastSealedAuditWriteResult(StrictBaseModel):
    inserted_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)


class ForecastSealedAuditMaturationSkip(StrictBaseModel):
    prediction_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class ForecastSealedAuditMaturationResult(StrictBaseModel):
    manifest_id: str = Field(min_length=1)
    pending_count: int = Field(ge=0)
    inserted_count: int = Field(ge=0)
    duplicate_count: int = Field(ge=0)
    skips: list[ForecastSealedAuditMaturationSkip] = Field(default_factory=list)


class ForecastSealedAuditHorizonStatus(StrictBaseModel):
    horizon_days: int = Field(ge=1)
    captured_count: int = Field(ge=0)
    matured_count: int = Field(ge=0)
    required_count: int = Field(ge=1)
    sample_ready: bool
    rmse: Decimal | None = Field(default=None, ge=0)
    direction_accuracy: Decimal | None = Field(default=None, ge=0, le=1)
    interval_sample_count: int = Field(ge=0)
    interval_coverage: Decimal | None = Field(default=None, ge=0, le=1)
    mean_interval_width: Decimal | None = Field(default=None, ge=0)
    mean_interval_score: Decimal | None = Field(default=None, ge=0)


class ForecastSealedAuditSummary(StrictBaseModel):
    manifest_id: str = Field(min_length=1)
    generated_at: datetime
    prediction_count: int = Field(ge=0)
    matured_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    horizon_rows: list[ForecastSealedAuditHorizonStatus]
    warnings: list[str] = Field(default_factory=list)


class SealedForecastAuditRepository:
    """SQLite repository with immutable rows and digest verification."""

    def __init__(self, path: Path = DEFAULT_SEALED_AUDIT_DATABASE) -> None:
        self.path = path

    def add_manifest(self, manifest: ForecastSealedAuditManifest) -> bool:
        manifest = ForecastSealedAuditManifest.model_validate(manifest.model_dump())
        payload, digest = _encoded_model(manifest)
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT payload_json, content_hash FROM audit_manifest WHERE manifest_id = ?",
                (manifest.manifest_id,),
            ).fetchone()
            if existing is not None:
                self._assert_existing(existing, payload, digest, "manifest")
                return False
            connection.execute(
                "INSERT INTO audit_manifest "
                "(manifest_id, created_at, payload_json, content_hash) VALUES (?, ?, ?, ?)",
                (manifest.manifest_id, manifest.created_at.isoformat(), payload, digest),
            )
        return True

    def get_manifest(self, manifest_id: str) -> ForecastSealedAuditManifest:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json, content_hash FROM audit_manifest WHERE manifest_id = ?",
                (manifest_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"sealed audit manifest not found: {manifest_id}")
        return self._decoded_model(row, ForecastSealedAuditManifest, "manifest")

    def add_predictions(
        self,
        predictions: list[ForecastSealedPrediction],
    ) -> ForecastSealedAuditWriteResult:
        if not predictions:
            return ForecastSealedAuditWriteResult(inserted_count=0, duplicate_count=0)
        inserted = 0
        duplicates = 0
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            manifests: dict[str, ForecastSealedAuditManifest] = {}
            try:
                for prediction in predictions:
                    prediction = ForecastSealedPrediction.model_validate(prediction.model_dump())
                    manifest = manifests.get(prediction.manifest_id)
                    if manifest is None:
                        row = connection.execute(
                            "SELECT payload_json, content_hash FROM audit_manifest "
                            "WHERE manifest_id = ?",
                            (prediction.manifest_id,),
                        ).fetchone()
                        if row is None:
                            raise KeyError(
                                f"sealed audit manifest not found: {prediction.manifest_id}"
                            )
                        manifest = self._decoded_model(row, ForecastSealedAuditManifest, "manifest")
                        manifests[prediction.manifest_id] = manifest
                    _validate_prediction_against_manifest(prediction, manifest)
                    payload, digest = _encoded_model(prediction)
                    existing = connection.execute(
                        "SELECT payload_json, content_hash FROM audit_prediction "
                        "WHERE prediction_id = ? OR "
                        "(manifest_id = ? AND symbol = ? AND horizon_days = ? AND origin_at = ?)",
                        (
                            prediction.prediction_id,
                            prediction.manifest_id,
                            prediction.symbol,
                            prediction.horizon_days,
                            prediction.origin_at.isoformat(),
                        ),
                    ).fetchone()
                    if existing is not None:
                        self._assert_existing(existing, payload, digest, "prediction")
                        duplicates += 1
                        continue
                    connection.execute(
                        "INSERT INTO audit_prediction "
                        "(prediction_id, manifest_id, symbol, horizon_days, origin_at, recorded_at, "
                        "payload_json, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            prediction.prediction_id,
                            prediction.manifest_id,
                            prediction.symbol,
                            prediction.horizon_days,
                            prediction.origin_at.isoformat(),
                            prediction.recorded_at.isoformat(),
                            payload,
                            digest,
                        ),
                    )
                    inserted += 1
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ForecastSealedAuditWriteResult(
            inserted_count=inserted,
            duplicate_count=duplicates,
        )

    def add_outcomes(
        self,
        outcomes: list[ForecastSealedOutcome],
    ) -> ForecastSealedAuditWriteResult:
        if not outcomes:
            return ForecastSealedAuditWriteResult(inserted_count=0, duplicate_count=0)
        inserted = 0
        duplicates = 0
        with self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                for outcome in outcomes:
                    outcome = ForecastSealedOutcome.model_validate(outcome.model_dump())
                    prediction_row = connection.execute(
                        "SELECT payload_json, content_hash FROM audit_prediction "
                        "WHERE prediction_id = ?",
                        (outcome.prediction_id,),
                    ).fetchone()
                    if prediction_row is None:
                        raise KeyError(f"sealed prediction not found: {outcome.prediction_id}")
                    prediction = self._decoded_model(
                        prediction_row, ForecastSealedPrediction, "prediction"
                    )
                    _validate_outcome_against_prediction(outcome, prediction)
                    payload, digest = _encoded_model(outcome)
                    existing = connection.execute(
                        "SELECT payload_json, content_hash FROM audit_outcome "
                        "WHERE prediction_id = ?",
                        (outcome.prediction_id,),
                    ).fetchone()
                    if existing is not None:
                        self._assert_existing(existing, payload, digest, "outcome")
                        duplicates += 1
                        continue
                    connection.execute(
                        "INSERT INTO audit_outcome "
                        "(prediction_id, target_at, payload_json, content_hash) "
                        "VALUES (?, ?, ?, ?)",
                        (
                            outcome.prediction_id,
                            outcome.target_at.isoformat(),
                            payload,
                            digest,
                        ),
                    )
                    inserted += 1
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return ForecastSealedAuditWriteResult(
            inserted_count=inserted,
            duplicate_count=duplicates,
        )

    def list_predictions(self, manifest_id: str) -> list[ForecastSealedPrediction]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json, content_hash FROM audit_prediction "
                "WHERE manifest_id = ? ORDER BY origin_at, symbol, horizon_days",
                (manifest_id,),
            ).fetchall()
        return [self._decoded_model(row, ForecastSealedPrediction, "prediction") for row in rows]

    def list_outcomes(self, manifest_id: str) -> list[ForecastSealedOutcome]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT o.payload_json, o.content_hash FROM audit_outcome o "
                "JOIN audit_prediction p ON p.prediction_id = o.prediction_id "
                "WHERE p.manifest_id = ? ORDER BY o.target_at, o.prediction_id",
                (manifest_id,),
            ).fetchall()
        return [self._decoded_model(row, ForecastSealedOutcome, "outcome") for row in rows]

    def list_pending_predictions(self, manifest_id: str) -> list[ForecastSealedPrediction]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT p.payload_json, p.content_hash FROM audit_prediction p "
                "LEFT JOIN audit_outcome o ON o.prediction_id = p.prediction_id "
                "WHERE p.manifest_id = ? AND o.prediction_id IS NULL "
                "ORDER BY p.origin_at, p.symbol, p.horizon_days",
                (manifest_id,),
            ).fetchall()
        return [self._decoded_model(row, ForecastSealedPrediction, "prediction") for row in rows]

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=5.0)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA busy_timeout = 5000")
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version not in {0, SEALED_AUDIT_DATABASE_VERSION}:
                raise ForecastSealedAuditCorruptData(
                    f"unsupported sealed audit database version: {version}"
                )
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS audit_manifest (
                    manifest_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_prediction (
                    prediction_id TEXT PRIMARY KEY,
                    manifest_id TEXT NOT NULL REFERENCES audit_manifest(manifest_id),
                    symbol TEXT NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    origin_at TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    UNIQUE(manifest_id, symbol, horizon_days, origin_at)
                );
                CREATE INDEX IF NOT EXISTS idx_audit_prediction_manifest
                    ON audit_prediction(manifest_id, origin_at);
                CREATE TABLE IF NOT EXISTS audit_outcome (
                    prediction_id TEXT PRIMARY KEY REFERENCES audit_prediction(prediction_id),
                    target_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    content_hash TEXT NOT NULL
                );
                """
            )
            if version == 0:
                connection.execute(f"PRAGMA user_version = {SEALED_AUDIT_DATABASE_VERSION}")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _decoded_model(row: sqlite3.Row, model_type: type[StrictBaseModel], label: str):
        payload = str(row["payload_json"])
        digest = str(row["content_hash"])
        if _sha256(payload) != digest:
            raise ForecastSealedAuditCorruptData(f"{label} digest does not match")
        try:
            model = model_type.model_validate_json(payload)
        except ValueError as exc:
            raise ForecastSealedAuditCorruptData(f"invalid {label} payload") from exc
        canonical, canonical_digest = _encoded_model(model)
        if canonical != payload or canonical_digest != digest:
            raise ForecastSealedAuditCorruptData(f"non-canonical {label} payload")
        return model

    @staticmethod
    def _assert_existing(
        row: sqlite3.Row,
        payload: str,
        digest: str,
        label: str,
    ) -> None:
        stored_payload = str(row["payload_json"])
        stored_digest = str(row["content_hash"])
        if _sha256(stored_payload) != stored_digest:
            raise ForecastSealedAuditCorruptData(f"stored {label} digest does not match")
        if stored_payload != payload or stored_digest != digest:
            raise ForecastSealedAuditConflict(f"immutable {label} already exists")


def create_forecast_sealed_audit_manifest(
    *,
    symbols: list[str],
    horizons: list[int] | tuple[int, ...] = DEFAULT_SEALED_AUDIT_HORIZONS,
    created_at: datetime,
    accept_origins_at_or_after: datetime,
    cohort: AuditCohort,
    source_revision: str,
    manifest_id: str | None = None,
    min_cases_per_horizon: int = 100,
) -> ForecastSealedAuditManifest:
    """Create a canonical predeclared manifest before predictions are captured."""

    normalized_symbols = sorted({_normalize_symbol(symbol) for symbol in symbols if symbol.strip()})
    normalized_horizons = sorted(set(horizons))
    if manifest_id is None:
        identifier_payload = "|".join(
            [
                created_at.isoformat(),
                ",".join(normalized_symbols),
                ",".join(str(value) for value in normalized_horizons),
                source_revision,
            ]
        )
        suffix = hashlib.sha256(identifier_payload.encode("utf-8")).hexdigest()[:12]
        manifest_id = f"fsa_{created_at.astimezone(UTC):%Y%m%dT%H%M%SZ}_{suffix}"
    return ForecastSealedAuditManifest(
        manifest_id=manifest_id,
        created_at=created_at,
        accept_origins_at_or_after=accept_origins_at_or_after,
        cohort=cohort,
        symbols=normalized_symbols,
        horizons=normalized_horizons,
        source_revision=source_revision.strip(),
        min_cases_per_horizon=min_cases_per_horizon,
    )


def build_forecast_sealed_prediction(
    manifest: ForecastSealedAuditManifest,
    consensus: AdvancedForecastConsensus,
    bars: list[Bar],
    *,
    recorded_at: datetime,
    market: str,
    asset_type: str,
    regime: str,
) -> ForecastSealedPrediction:
    """Freeze one current consensus with a digest of its point-in-time input bars."""

    _require_aware(recorded_at, "recorded_at")
    if any(bar.ts.tzinfo is None or bar.ts.utcoffset() is None for bar in bars):
        raise ValueError("source bar timestamps must be timezone-aware")
    sorted_bars = sorted(bars, key=lambda item: item.ts)
    if not sorted_bars:
        raise ValueError("daily bars are required")
    symbol = _normalize_symbol(consensus.symbol)
    if any(_normalize_symbol(bar.symbol.raw) != symbol for bar in sorted_bars):
        raise ValueError("all source bars must match the consensus symbol")
    if any(bar.interval != "1d" for bar in sorted_bars):
        raise ValueError("sealed forecast audit requires daily bars")
    origin = sorted_bars[-1]
    if len({bar.ts for bar in sorted_bars}) != len(sorted_bars):
        raise ValueError("source bars must have unique timestamps")
    if any(bar.provider != origin.provider for bar in sorted_bars):
        raise ValueError("source bars must use one provider")
    _require_aware(origin.ts, "origin_at")
    if origin.close <= 0:
        raise ValueError("origin close must be positive")
    identifier = _prediction_identifier(
        manifest.manifest_id,
        symbol,
        consensus.horizon_days,
        origin.ts,
    )
    prediction = ForecastSealedPrediction(
        prediction_id=identifier,
        manifest_id=manifest.manifest_id,
        symbol=symbol,
        market=market.strip() or "unknown",
        asset_type=asset_type.strip() or "unknown",
        regime=regime.strip() or "unknown",
        horizon_days=consensus.horizon_days,
        origin_at=origin.ts,
        recorded_at=recorded_at,
        origin_close=origin.close,
        forecast_close=consensus.consensus_forecast_close,
        predicted_return=consensus.consensus_predicted_return,
        direction_predicted_return=consensus.direction_predicted_return,
        predicted_return_lower=consensus.predicted_return_lower,
        predicted_return_upper=consensus.predicted_return_upper,
        confidence=consensus.confidence,
        center_confidence=consensus.center_confidence,
        direction_confidence=consensus.direction_confidence,
        selection_policy_version=consensus.selection_policy_version,
        confidence_policy_version=consensus.confidence_policy_version,
        interval_policy_version=manifest.interval_policy_version,
        horizon_band=consensus.horizon_band,
        audit_status=consensus.audit_status,
        selection_mode=consensus.selection_mode,
        selected_adapter_names=list(consensus.selected_adapter_names),
        center_adapter_names=list(consensus.center_adapter_names),
        direction_adapter_names=list(consensus.direction_adapter_names),
        model_weights=dict(consensus.model_weights),
        model_disagreement=consensus.direction_predicted_return_range,
        source_provider=origin.provider,
        source_bar_count=len(sorted_bars),
        source_history_digest=_bar_history_digest(sorted_bars),
        warnings=list(consensus.warnings),
    )
    _validate_prediction_against_manifest(prediction, manifest)
    return prediction


def mature_forecast_sealed_predictions(
    repository: SealedForecastAuditRepository,
    manifest_id: str,
    bars_by_symbol: dict[str, list[Bar]],
    *,
    observed_at: datetime,
) -> ForecastSealedAuditMaturationResult:
    """Attach outcomes only after the exact trading-bar horizon is observable."""

    _require_aware(observed_at, "observed_at")
    pending = repository.list_pending_predictions(manifest_id)
    outcomes: list[ForecastSealedOutcome] = []
    skips: list[ForecastSealedAuditMaturationSkip] = []
    for prediction in pending:
        matching_bars = [
            bar
            for bar in bars_by_symbol.get(prediction.symbol, [])
            if _normalize_symbol(bar.symbol.raw) == prediction.symbol
            and bar.interval == "1d"
            and bar.provider == prediction.source_provider
        ]
        if any(bar.ts.tzinfo is None or bar.ts.utcoffset() is None for bar in matching_bars):
            skips.append(_maturation_skip(prediction, "bar_timestamp_naive"))
            continue
        candidate_bars = sorted(matching_bars, key=lambda item: item.ts)
        timestamps = [bar.ts for bar in candidate_bars]
        if len(timestamps) != len(set(timestamps)):
            skips.append(_maturation_skip(prediction, "duplicate_bar_timestamp"))
            continue
        try:
            origin_index = timestamps.index(prediction.origin_at)
        except ValueError:
            skips.append(_maturation_skip(prediction, "origin_bar_missing"))
            continue
        origin_bar = candidate_bars[origin_index]
        if origin_bar.close != prediction.origin_close:
            skips.append(_maturation_skip(prediction, "origin_close_revised"))
            continue
        target_index = origin_index + prediction.horizon_days
        if target_index >= len(candidate_bars):
            skips.append(_maturation_skip(prediction, "target_not_yet_available"))
            continue
        target = candidate_bars[target_index]
        if target.close <= 0:
            skips.append(_maturation_skip(prediction, "target_close_non_positive"))
            continue
        if target.ts <= prediction.recorded_at:
            skips.append(_maturation_skip(prediction, "prediction_recorded_after_target"))
            continue
        if target.ts > observed_at:
            skips.append(_maturation_skip(prediction, "target_not_yet_observable"))
            continue
        actual_return = (target.close / prediction.origin_close) - Decimal("1")
        outcomes.append(
            ForecastSealedOutcome(
                prediction_id=prediction.prediction_id,
                target_at=target.ts,
                matured_at=observed_at,
                target_close=target.close,
                actual_return=actual_return,
                target_provider=target.provider,
                target_bar_offset=prediction.horizon_days,
            )
        )
    write_result = repository.add_outcomes(outcomes)
    return ForecastSealedAuditMaturationResult(
        manifest_id=manifest_id,
        pending_count=len(pending),
        inserted_count=write_result.inserted_count,
        duplicate_count=write_result.duplicate_count,
        skips=skips,
    )


def forecast_sealed_validation_points(
    repository: SealedForecastAuditRepository,
    manifest_id: str,
) -> list[ForecastValidationPoint]:
    """Convert only matured immutable rows to the existing evaluation contract."""

    predictions = {
        prediction.prediction_id: prediction
        for prediction in repository.list_predictions(manifest_id)
    }
    points: list[ForecastValidationPoint] = []
    for outcome in repository.list_outcomes(manifest_id):
        prediction = predictions.get(outcome.prediction_id)
        if prediction is None:
            raise ForecastSealedAuditCorruptData("outcome prediction is missing")
        _validate_outcome_against_prediction(outcome, prediction)
        points.append(
            ForecastValidationPoint(
                symbol=prediction.symbol,
                market=prediction.market,
                asset_type=prediction.asset_type,
                regime=prediction.regime,
                model_name=prediction.model_name,
                horizon_days=prediction.horizon_days,
                origin_at=prediction.origin_at,
                target_at=outcome.target_at,
                predicted_return=prediction.predicted_return,
                direction_predicted_return=prediction.direction_predicted_return,
                predicted_return_lower=prediction.predicted_return_lower,
                predicted_return_upper=prediction.predicted_return_upper,
                confidence=prediction.confidence,
                center_confidence=prediction.center_confidence,
                direction_confidence=prediction.direction_confidence,
                selection_policy_version=prediction.selection_policy_version,
                horizon_band=prediction.horizon_band,
                audit_status=prediction.audit_status,
                actual_return=outcome.actual_return,
                model_disagreement=prediction.model_disagreement,
            )
        )
    return sorted(points, key=lambda item: (item.origin_at, item.symbol, item.horizon_days))


def summarize_forecast_sealed_audit(
    repository: SealedForecastAuditRepository,
    manifest_id: str,
    *,
    generated_at: datetime | None = None,
) -> ForecastSealedAuditSummary:
    manifest = repository.get_manifest(manifest_id)
    predictions = repository.list_predictions(manifest_id)
    points = forecast_sealed_validation_points(repository, manifest_id)
    prediction_counts = Counter(item.horizon_days for item in predictions)
    rows: list[ForecastSealedAuditHorizonStatus] = []
    for horizon in manifest.horizons:
        selected = [point for point in points if point.horizon_days == horizon]
        squared_errors = [(point.predicted_return - point.actual_return) ** 2 for point in selected]
        direction_hits = [
            _direction(point.predicted_return) == _direction(point.actual_return)
            for point in selected
        ]
        interval_points = [
            point
            for point in selected
            if point.predicted_return_lower is not None and point.predicted_return_upper is not None
        ]
        coverages = [
            point.predicted_return_lower <= point.actual_return <= point.predicted_return_upper
            for point in interval_points
            if point.predicted_return_lower is not None and point.predicted_return_upper is not None
        ]
        widths = [
            point.predicted_return_upper - point.predicted_return_lower
            for point in interval_points
            if point.predicted_return_lower is not None and point.predicted_return_upper is not None
        ]
        scores = [
            _interval_score(
                actual=point.actual_return,
                lower=point.predicted_return_lower,
                upper=point.predicted_return_upper,
                target_coverage=manifest.target_coverage,
            )
            for point in interval_points
            if point.predicted_return_lower is not None and point.predicted_return_upper is not None
        ]
        rows.append(
            ForecastSealedAuditHorizonStatus(
                horizon_days=horizon,
                captured_count=prediction_counts[horizon],
                matured_count=len(selected),
                required_count=manifest.min_cases_per_horizon,
                sample_ready=len(selected) >= manifest.min_cases_per_horizon,
                rmse=_mean(squared_errors).sqrt() if squared_errors else None,
                direction_accuracy=(
                    Decimal(sum(direction_hits)) / Decimal(len(direction_hits))
                    if direction_hits
                    else None
                ),
                interval_sample_count=len(interval_points),
                interval_coverage=(
                    Decimal(sum(coverages)) / Decimal(len(coverages)) if coverages else None
                ),
                mean_interval_width=_mean(widths) if widths else None,
                mean_interval_score=_mean(scores) if scores else None,
            )
        )
    warnings: list[str] = []
    if not predictions:
        warnings.append("予測snapshotがまだありません。")
    if any(not row.sample_ready for row in rows):
        warnings.append("必要な成熟case数に達していないhorizonがあります。")
    generated = generated_at or datetime.now(UTC)
    _require_aware(generated, "generated_at")
    return ForecastSealedAuditSummary(
        manifest_id=manifest_id,
        generated_at=generated,
        prediction_count=len(predictions),
        matured_count=len(points),
        pending_count=len(predictions) - len(points),
        horizon_rows=rows,
        warnings=warnings,
    )


def write_forecast_sealed_audit_artifacts(
    repository: SealedForecastAuditRepository,
    manifest_id: str,
    output_dir: Path,
) -> dict[str, Path]:
    """Write immutable manifest, compatible points, status CSV, and Japanese report."""

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = repository.get_manifest(manifest_id)
    points = forecast_sealed_validation_points(repository, manifest_id)
    summary = summarize_forecast_sealed_audit(repository, manifest_id)
    paths = {
        "manifest": output_dir / "sealed_forecast_audit_manifest.json",
        "validation_points": output_dir / "forecast_model_validation_points.csv",
        "summary_csv": output_dir / "sealed_forecast_audit_summary.csv",
        "report": output_dir / "sealed_forecast_audit_report.md",
    }
    paths["manifest"].write_text(
        manifest.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    _write_model_csv(paths["validation_points"], ForecastValidationPoint, points)
    _write_model_csv(paths["summary_csv"], ForecastSealedAuditHorizonStatus, summary.horizon_rows)
    paths["report"].write_text(
        _sealed_audit_markdown(manifest, summary), encoding="utf-8", newline="\n"
    )
    return paths


def _validate_prediction_against_manifest(
    prediction: ForecastSealedPrediction,
    manifest: ForecastSealedAuditManifest,
) -> None:
    if prediction.manifest_id != manifest.manifest_id:
        raise ValueError("prediction manifest does not match")
    if prediction.symbol not in manifest.symbols:
        raise ValueError("prediction symbol is outside the frozen cohort")
    if prediction.horizon_days not in manifest.horizons:
        raise ValueError("prediction horizon is outside the frozen manifest")
    expected_identifier = _prediction_identifier(
        prediction.manifest_id,
        prediction.symbol,
        prediction.horizon_days,
        prediction.origin_at,
    )
    if prediction.prediction_id != expected_identifier:
        raise ValueError("prediction identifier does not match its immutable key")
    if prediction.origin_at < manifest.accept_origins_at_or_after:
        raise ValueError("prediction origin predates the sealed audit boundary")
    origin_age = prediction.recorded_at - prediction.origin_at
    if origin_age.total_seconds() > manifest.max_origin_age_days * 86400:
        raise ValueError("prediction origin is too old for a sealed capture")
    if prediction.selection_policy_version != manifest.expected_selection_policy_version:
        raise ValueError("prediction selection policy differs from the frozen manifest")
    if prediction.confidence_policy_version != manifest.expected_confidence_policy_version:
        raise ValueError("prediction confidence policy differs from the frozen manifest")
    if prediction.interval_policy_version != manifest.interval_policy_version:
        raise ValueError("prediction interval policy differs from the frozen manifest")


def _validate_outcome_against_prediction(
    outcome: ForecastSealedOutcome,
    prediction: ForecastSealedPrediction,
) -> None:
    if outcome.prediction_id != prediction.prediction_id:
        raise ValueError("outcome prediction does not match")
    if outcome.target_at <= prediction.recorded_at:
        raise ValueError("target was already observable when prediction was recorded")
    if outcome.target_at <= prediction.origin_at:
        raise ValueError("target must follow origin")
    if outcome.target_bar_offset != prediction.horizon_days:
        raise ValueError("target bar offset does not match forecast horizon")
    if outcome.target_provider != prediction.source_provider:
        raise ValueError("target provider does not match the origin provider")
    expected = (outcome.target_close / prediction.origin_close) - Decimal("1")
    if outcome.actual_return != expected:
        raise ValueError("actual return does not match frozen origin and target close")


def _bar_history_digest(bars: list[Bar]) -> str:
    payload = [bar.model_dump(mode="json") for bar in bars]
    return _sha256(_canonical_json(payload))


def _prediction_identifier(
    manifest_id: str,
    symbol: str,
    horizon_days: int,
    origin_at: datetime,
) -> str:
    raw = f"{manifest_id}|{symbol}|{horizon_days}|{origin_at.isoformat()}"
    return f"fsp_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _maturation_skip(
    prediction: ForecastSealedPrediction,
    reason: str,
) -> ForecastSealedAuditMaturationSkip:
    return ForecastSealedAuditMaturationSkip(
        prediction_id=prediction.prediction_id,
        reason=reason,
    )


def _encoded_model(model: StrictBaseModel) -> tuple[str, str]:
    payload = _canonical_json(model.model_dump(mode="json"))
    return payload, _sha256(payload)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_symbol(value: str) -> str:
    return value.strip().upper()


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _direction(value: Decimal) -> int:
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _mean(values: list[Decimal]) -> Decimal:
    return sum(values, Decimal("0")) / Decimal(len(values))


def _interval_score(
    *,
    actual: Decimal,
    lower: Decimal,
    upper: Decimal,
    target_coverage: Decimal,
) -> Decimal:
    alpha = Decimal("1") - target_coverage
    score = upper - lower
    if actual < lower:
        score += (Decimal("2") / alpha) * (lower - actual)
    elif actual > upper:
        score += (Decimal("2") / alpha) * (actual - upper)
    return score


def _write_model_csv(
    path: Path,
    model_type: type[StrictBaseModel],
    rows: Sequence[StrictBaseModel],
) -> None:
    fieldnames = list(model_type.model_fields)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.model_dump(mode="json"))


def _sealed_audit_markdown(
    manifest: ForecastSealedAuditManifest,
    summary: ForecastSealedAuditSummary,
) -> str:
    lines = [
        "# Forecast Sealed Audit",
        "",
        f"- Manifest: `{manifest.manifest_id}`",
        f"- Cohort: `{manifest.cohort}`",
        f"- 受付origin境界: {manifest.accept_origins_at_or_after.isoformat()}",
        f"- 予測snapshot: {summary.prediction_count}",
        f"- 成熟済み: {summary.matured_count}",
        f"- 未成熟: {summary.pending_count}",
        "",
        "| Horizon | Captured | Matured | Required | Ready | RMSE | Direction | Coverage | Interval score |",
        "| ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary.horizon_rows:
        lines.append(
            f"| {row.horizon_days} | {row.captured_count} | {row.matured_count} | "
            f"{row.required_count} | {'yes' if row.sample_ready else 'no'} | "
            f"{_display_decimal(row.rmse)} | {_display_decimal(row.direction_accuracy)} | "
            f"{_display_decimal(row.interval_coverage)} | "
            f"{_display_decimal(row.mean_interval_score)} |"
        )
    if summary.warnings:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in summary.warnings)
    lines.extend(
        [
            "",
            "このartifactは新しい時点で保存した予測の監査用であり、runtime modelを自動変更しない。",
        ]
    )
    return "\n".join(lines) + "\n"


def _display_decimal(value: Decimal | None) -> str:
    return "-" if value is None else str(value.quantize(Decimal("0.000001")))
