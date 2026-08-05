from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.core.data_contracts import Bar, Symbol
from backend.llm_factor import (
    PointInTimeEventAnchor,
    PointInTimeEvidence,
    SourceMemoryConfig,
    SourceMemoryFeedback,
    assign_to_next_decision_time,
    classify_event_type,
    compute_market_residual_impact_label,
    rerank_with_source_memory,
    select_point_in_time_evidence,
    update_source_memory,
)

UTC = timezone.utc


def test_event_type_uses_anchor_text_only_and_ties_fall_back() -> None:
    assert classify_event_type("通期業績予想を上方修正") == "earnings_guidance"
    assert classify_event_type("CEO resignation announced") == "management_operations"
    assert classify_event_type("profit lawsuit") == "other_mixed"
    assert classify_event_type("New product update") == "other_mixed"


def test_event_is_assigned_to_first_available_decision_time() -> None:
    first = datetime(2026, 7, 20, 6, tzinfo=UTC)
    second = datetime(2026, 7, 21, 6, tzinfo=UTC)

    assert (
        assign_to_next_decision_time(
            datetime(2026, 7, 20, 1, tzinfo=UTC),
            [first, second],
        )
        == first
    )
    assert (
        assign_to_next_decision_time(
            datetime(2026, 7, 20, 8, tzinfo=UTC),
            [first, second],
        )
        == second
    )
    with pytest.raises(ValueError, match="timezone-aware"):
        assign_to_next_decision_time(datetime(2026, 7, 20), [first])


def test_evidence_selection_removes_future_late_duplicates_and_excess_peers() -> None:
    decision_at = datetime(2026, 7, 20, 6, tzinfo=UTC)
    event = _event(decision_at=decision_at)
    evidence = [
        _evidence("direct-1", relevance="0.90"),
        _evidence("direct-2", relevance="0.80"),
        _evidence("direct-3", relevance="0.65"),
        _evidence("peer-1", relevance="0.70", symbol="PEER", is_peer=True),
        _evidence("peer-2", relevance="0.60", symbol="PEER2", is_peer=True),
        _evidence(
            "future",
            relevance="0.99",
            available_at=decision_at + timedelta(minutes=1),
            archived_at=decision_at + timedelta(minutes=1),
        ),
        _evidence(
            "late-archive",
            relevance="0.98",
            archived_at=decision_at + timedelta(minutes=1),
        ),
        _evidence("anchor-copy", relevance="0.97", title=event.headline),
        _evidence(
            "duplicate-url",
            relevance="0.50",
            source_url="https://example.test/direct-1?utm_source=test",
        ),
        _evidence("unrelated", relevance="0.40", symbol="OTHER"),
    ]

    result = select_point_in_time_evidence(event, evidence, max_peer_ratio=Decimal("0.25"))

    assert [item.evidence_id for item in result.candidates] == [
        "direct-1",
        "direct-2",
        "peer-1",
        "direct-3",
    ]
    assert result.audit.future_count == 1
    assert result.audit.archive_late_count == 1
    assert result.audit.anchor_duplicate_count == 1
    assert result.audit.duplicate_count == 1
    assert result.audit.unrelated_count == 1
    assert result.audit.peer_cap_count == 1


def test_source_memory_updates_only_matured_valid_citations_and_is_bounded() -> None:
    evidence = {
        "a": _evidence("a", source_family="official"),
        "b": _evidence("b", source_family="newswire"),
    }
    feedback = SourceMemoryFeedback(
        event_id="event-1",
        event_type="earnings_guidance",
        horizon_days=20,
        target_at=datetime(2026, 8, 20, tzinfo=UTC),
        predicted_label=1,
        actual_label=1,
        cited_evidence_ids=["a", "b", "hallucinated"],
    )

    unchanged, immature = update_source_memory(
        {},
        feedback,
        evidence,
        valid_evidence_ids=evidence,
        as_of=datetime(2026, 8, 19, tzinfo=UTC),
    )
    assert unchanged == {}
    assert immature.reason == "target_not_matured"

    updated, result = update_source_memory(
        {},
        feedback,
        evidence,
        valid_evidence_ids=evidence,
        as_of=feedback.target_at,
        class_proportions={-1: Decimal("0.2"), 0: Decimal("0.6"), 1: Decimal("0.2")},
    )

    assert result.applied is True
    assert result.ignored_evidence_ids == ["hallucinated"]
    assert result.class_weight == Decimal("1") / Decimal("0.6")
    assert len(updated) == 2
    assert sum(cell.positive_mass for cell in updated.values()) == result.class_weight

    ranked = rerank_with_source_memory(
        evidence.values(),
        updated,
        event_type="earnings_guidance",
        horizon_days=20,
    )
    assert len(ranked) == 2
    assert all(Decimal("0") < item.posterior_utility < Decimal("1") for item in ranked)
    assert all(abs(item.memory_adjustment) <= Decimal("0.06") for item in ranked)


def test_source_memory_ignores_feedback_without_valid_citation() -> None:
    feedback = SourceMemoryFeedback(
        event_id="event-1",
        event_type="other_mixed",
        horizon_days=20,
        target_at=datetime(2026, 8, 20, tzinfo=UTC),
        predicted_label=0,
        actual_label=-1,
        cited_evidence_ids=["unknown"],
    )

    updated, result = update_source_memory(
        {},
        feedback,
        {},
        valid_evidence_ids=[],
        as_of=feedback.target_at,
    )

    assert updated == {}
    assert result.applied is False
    assert result.reason == "no_valid_citations"


def test_source_memory_configuration_cannot_exceed_six_point_adjustment() -> None:
    with pytest.raises(ValueError, match="must not exceed 0.06"):
        SourceMemoryConfig(
            utility_clip=Decimal("0.30"),
            rerank_lambda=Decimal("0.30"),
        )


def test_market_residual_label_is_unavailable_until_target_matures() -> None:
    start = datetime(2025, 1, 1, tzinfo=UTC)
    market_bars = _bars("BENCH", start, count=380, shock_index=None)
    stock_bars = _bars("STOCK", start, count=380, shock_index=350)
    decision_at = start + timedelta(days=330)
    event = _event(decision_at=decision_at)

    immature = compute_market_residual_impact_label(
        event,
        stock_bars,
        market_bars,
        horizon_days=20,
        as_of=decision_at + timedelta(days=19),
    )
    assert immature is None

    label = compute_market_residual_impact_label(
        event,
        stock_bars,
        market_bars,
        horizon_days=20,
        as_of=decision_at + timedelta(days=20),
    )

    assert label is not None
    assert label.target_at == decision_at + timedelta(days=20)
    assert label.fit_window_end_at == decision_at - timedelta(days=20)
    assert label.fit_sample_count == 252
    assert label.label == 1
    assert label.standardized_residual > 1


def _event(*, decision_at: datetime) -> PointInTimeEventAnchor:
    return PointInTimeEventAnchor(
        event_id="event-1",
        symbol="STOCK",
        occurred_at=decision_at - timedelta(hours=1),
        decision_at=decision_at,
        headline="Earnings guidance update",
        summary="Management updated full-year profit guidance.",
        source_url="https://issuer.test/anchor",
        event_type="earnings_guidance",
    )


def _evidence(
    evidence_id: str,
    *,
    relevance: str = "0.50",
    title: str | None = None,
    source_url: str | None = None,
    symbol: str = "STOCK",
    is_peer: bool = False,
    source_family: str = "official",
    available_at: datetime | None = None,
    archived_at: datetime | None = None,
) -> PointInTimeEvidence:
    default_time = datetime(2026, 7, 20, 5, tzinfo=UTC)
    return PointInTimeEvidence(
        evidence_id=evidence_id,
        symbol=symbol,
        source_family=source_family,
        title=title or f"Evidence {evidence_id}",
        summary=f"Summary for {evidence_id}",
        source_url=source_url or f"https://example.test/{evidence_id}",
        published_at=default_time - timedelta(minutes=5),
        available_at=available_at or default_time,
        archived_at=archived_at or available_at or default_time,
        static_relevance=Decimal(relevance),
        is_peer_context=is_peer,
    )


def _bars(
    code: str,
    start: datetime,
    *,
    count: int,
    shock_index: int | None,
) -> list[Bar]:
    symbol = Symbol(raw=code, exchange="TEST", code=code, currency="USD")
    bars: list[Bar] = []
    for index in range(count):
        market_component = Decimal(str(100 + index * 0.04))
        cycle = Decimal(str(math.sin(index / 9) * (0.35 if code == "BENCH" else 0.8)))
        close = market_component + cycle
        if code != "BENCH":
            close = Decimal("0.85") * close + Decimal("12")
        if shock_index is not None and index >= shock_index:
            close *= Decimal("1.15")
        bars.append(
            Bar(
                symbol=symbol,
                ts=start + timedelta(days=index),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=Decimal("1000"),
                interval="1d",
                provider="test",
            )
        )
    return bars
