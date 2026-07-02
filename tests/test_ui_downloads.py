from pathlib import Path

import pytest

from ui.components.downloads import (
    CSV_MIME,
    JSON_MIME,
    MARKDOWN_MIME,
    PDF_MIME,
    ZIP_MIME,
    csv_download_contract,
    json_download_contract,
    markdown_download_contract,
    pdf_download_contract,
    zip_download_contract,
)


@pytest.mark.parametrize(
    ("contract", "file_name", "mime"),
    [
        (lambda: csv_download_contract(data=b"a,b\n", file_name="rows.csv"), "rows.csv", CSV_MIME),
        (
            lambda: json_download_contract(data='{"ok":true}', file_name="data.json"),
            "data.json",
            JSON_MIME,
        ),
        (
            lambda: markdown_download_contract(data="# Memo", file_name="memo.md"),
            "memo.md",
            MARKDOWN_MIME,
        ),
        (
            lambda: pdf_download_contract(data=b"%PDF", file_name="report.pdf"),
            "report.pdf",
            PDF_MIME,
        ),
        (
            lambda: zip_download_contract(data=b"PK", file_name="bundle.zip"),
            "bundle.zip",
            ZIP_MIME,
        ),
    ],
)
def test_download_contracts_are_attachment_only(contract, file_name, mime) -> None:
    result = contract()
    assert result["file_name"] == file_name
    assert result["mime"] == mime
    assert result["data"]
    assert "href" not in result
    assert "target" not in result


def test_download_contract_rejects_wrong_extension() -> None:
    with pytest.raises(ValueError):
        json_download_contract(data="{}", file_name="unsafe.txt")


def test_generated_file_links_do_not_use_data_uri_or_blank_target() -> None:
    copilot_source = Path("ui/views/copilot.py").read_text(encoding="utf-8")
    assert 'href="data:' not in copilot_source
    assert "_download_action_link_html" not in copilot_source


def test_external_news_links_remain_available() -> None:
    news_source = Path("ui/views/news.py").read_text(encoding="utf-8")
    assert 'target="_blank"' in news_source
    assert 'rel="noopener noreferrer"' in news_source
