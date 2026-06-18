import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from backend.research.external_contracts import (
    ExternalResearchFetchManifestEntry,
    ExternalResearchFetchRequest,
    ExternalResearchSourcePayload,
)
from backend.research.external_registration import (
    external_fetch_manifest_entry,
    external_payload_content_digest,
    external_payload_markdown,
    external_research_content_summary,
    external_source_freshness,
    external_source_freshness_rank,
    find_registered_external_document,
    safe_cache_fragment,
    stale_external_source_warning,
    write_external_fetch_manifest,
    write_external_payload_archive,
)


@dataclass(frozen=True)
class RegisteredDocument:
    document_id: str
    provider: str
    source_type: str
    title: str = "7203 External IR Update"
    symbol: str = "7203.T"
    published_at: date | None = date(2026, 5, 24)


def _payload(
    *, content: str = "Revenue growth and dividend policy."
) -> ExternalResearchSourcePayload:
    return ExternalResearchSourcePayload(
        symbol="7203.T",
        title="7203 External IR Update",
        content=content,
        source_type="provider_profile",
        source_url="https://example.com/7203-ir",
        provider="fake_external",
        company_name="Toyota",
        published_at=date(2026, 5, 24),
        fetched_at=datetime(2026, 5, 25, 9, 0, tzinfo=UTC),
        reliability=Decimal("0.80"),
    )


def test_external_payload_markdown_contains_stable_source_markers():
    payload = _payload()

    markdown = external_payload_markdown(payload)

    assert markdown.startswith("# 7203 External IR Update")
    assert "- Provider: fake_external" in markdown
    assert "- Source URL: https://example.com/7203-ir" in markdown
    assert "- Symbol: 7203.T" in markdown
    assert f"- Content digest: {external_payload_content_digest(payload)}" in markdown
    assert "not a buy/sell recommendation" in markdown


def test_find_registered_external_document_matches_url_and_digest():
    payload = _payload()
    matching = RegisteredDocument(
        document_id="doc-match",
        provider="fake_external",
        source_type="provider_profile",
    )
    other_provider = RegisteredDocument(
        document_id="doc-other",
        provider="other",
        source_type="provider_profile",
    )
    raw_text = {
        matching.document_id: external_payload_markdown(payload),
        other_provider.document_id: external_payload_markdown(payload),
    }

    result = find_registered_external_document(
        [other_provider, matching],
        raw_text,
        payload,
    )

    assert result == matching
    changed_payload = _payload(content="Different content")
    assert find_registered_external_document([matching], raw_text, changed_payload) is None


def test_external_payload_archive_and_manifest_writers(tmp_path):
    payload = _payload()
    payload_path = write_external_payload_archive(tmp_path, payload)

    assert payload_path.exists()
    assert payload_path.name.startswith("7203.T_provider_profile_fake_external_20260525090000_")
    assert "Content digest" in payload_path.read_text(encoding="utf-8")

    entry = ExternalResearchFetchManifestEntry(
        title=payload.title,
        symbol=payload.symbol,
        source_type=payload.source_type,
        source_url=payload.source_url,
        provider=payload.provider,
        published_at=payload.published_at,
        fetched_at=payload.fetched_at,
        freshness_status="latest",
        document_id="research-doc-1",
        retention_policy="archive",
        content_summary=external_research_content_summary(payload),
        local_path=str(payload_path),
        document_hash="hash-1",
    )
    manifest_path = write_external_fetch_manifest(
        tmp_path,
        request=ExternalResearchFetchRequest(
            symbol="7203.T",
            provider="fake_external",
            allow_network=True,
        ),
        provider="fake_external",
        fetched_at=payload.fetched_at,
        entries=[entry],
        warnings=["check freshness"],
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "external-research-fetch-manifest-v1"
    assert manifest["symbol"] == "7203.T"
    assert manifest["provider"] == "fake_external"
    assert manifest["entry_count"] == 1
    assert manifest["warnings"] == ["check freshness"]


def test_external_fetch_manifest_entry_builds_archive_and_session_rows(tmp_path):
    payload = _payload()
    document = RegisteredDocument(
        document_id="doc-1",
        provider="fake_external",
        source_type="provider_profile",
    )
    local_path = tmp_path / "payload.md"

    entry = external_fetch_manifest_entry(
        payload=payload,
        document=document,
        as_of=date(2026, 5, 25),
        retention_policy="archive",
        local_path=local_path,
        document_hash="hash-1",
    )

    assert entry.title == payload.title
    assert entry.symbol == payload.symbol
    assert entry.source_url == payload.source_url
    assert entry.freshness_status == "latest"
    assert entry.retention_policy == "archive"
    assert entry.local_path == str(local_path)
    assert entry.document_hash == "hash-1"


def test_external_source_freshness_and_warning_text():
    as_of = date(2026, 5, 25)

    assert external_source_freshness(date(2026, 5, 25), as_of=as_of) == "latest"
    assert external_source_freshness(date(2026, 5, 1), as_of=as_of) == "recent"
    assert external_source_freshness(date(2026, 1, 1), as_of=as_of) == "stale"
    assert external_source_freshness(None, as_of=as_of) == "unknown"
    assert external_source_freshness_rank("latest") == 0
    assert external_source_freshness_rank("stale") == 3
    assert stale_external_source_warning("Old News") == (
        "Old News: 公開日が古いため、最新資料と合わせて確認してください。"
    )


def test_safe_cache_fragment_falls_back_for_empty_values():
    assert safe_cache_fragment("7203.T") == "7203.T"
    assert safe_cache_fragment("fake external/provider") == "fake_external_provider"
    assert safe_cache_fragment("   ") == "source"
