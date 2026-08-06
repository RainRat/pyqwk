import os
import json
import html
import logging
import pytest
from pyqwk.core import (
    ProcessingSettings,
    show_validation_report,
    _render_validation_html,
    _render_validation_markdown,
    render_validation_as_text,
)


@pytest.fixture
def logger():
    return logging.getLogger("test_validation_reporting")


def test_render_validation_html():
    results = [
        {
            "file": "test1.qwk",
            "valid": True,
            "format": "qwk",
            "messages_count": 5,
            "errors": [],
            "warnings": ["CONTROL.DAT is missing from the QWK archive."]
        },
        {
            "file": "test2.json",
            "valid": False,
            "format": "json",
            "messages_count": 0,
            "errors": ["JSON syntax error"],
            "warnings": []
        }
    ]
    html_parts = _render_validation_html(results)
    html_str = "\n".join(html_parts)

    assert "File: test1.qwk" in html_str
    assert "Status:</strong> <span style=\"color: #4e9a06; font-weight: bold;\">VALID" in html_str
    assert "CONTROL.DAT is missing from the QWK archive." in html_str

    assert "File: test2.json" in html_str
    assert "Status:</strong> <span style=\"color: #cc0000; font-weight: bold;\">INVALID" in html_str
    assert "JSON syntax error" in html_str


def test_render_validation_markdown():
    results = [
        {
            "file": "test1.qwk",
            "valid": True,
            "format": "qwk",
            "messages_count": 5,
            "errors": [],
            "warnings": ["CONTROL.DAT is missing."]
        },
        {
            "file": "test2.json",
            "valid": False,
            "format": "json",
            "messages_count": 0,
            "errors": ["Syntax error"],
            "warnings": []
        }
    ]
    md_parts = _render_validation_markdown(results)
    md_str = "\n".join(md_parts)

    assert "## File: test1.qwk" in md_str
    assert "- **Status:** ✅ VALID" in md_str
    assert "CONTROL.DAT is missing." in md_str

    assert "## File: test2.json" in md_str
    assert "- **Status:** ❌ INVALID" in md_str
    assert "Syntax error" in md_str


def test_render_validation_as_text_and_colors():
    results = [
        {
            "file": "test1.qwk",
            "valid": True,
            "format": "qwk",
            "messages_count": 5,
            "errors": [],
            "warnings": ["Warning 1"]
        },
        {
            "file": "test2.json",
            "valid": False,
            "format": "json",
            "messages_count": 0,
            "errors": ["Error 1"],
            "warnings": []
        }
    ]
    # Without colors
    text_plain = render_validation_as_text(results, use_colors=False)
    assert "File: test1.qwk (qwk, 5 messages) - [VALID]" in text_plain
    assert "  - [Warning] Warning 1" in text_plain
    assert "File: test2.json (json, 0 messages) - [INVALID]" in text_plain
    assert "  - [Error] Error 1" in text_plain

    # With colors
    text_colored = render_validation_as_text(results, use_colors=True)
    assert "\033[1;32mVALID\033[0m" in text_colored
    assert "\033[1;31mINVALID\033[0m" in text_colored
    assert "\033[1;31mError\033[0m" in text_colored
    assert "\033[1;33mWarning\033[0m" in text_colored


def test_show_validation_report_json(tmp_path, logger):
    p = tmp_path / "valid.json"
    p.write_text('{"type": "qwk_archive", "messages": []}')

    report_file = tmp_path / "report.json"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="file",
        output_path=str(report_file),
        encoding="utf-8"
    )

    valid_all = show_validation_report([str(p)], settings, logger)
    assert valid_all is True

    assert report_file.exists()
    report_data = json.loads(report_file.read_text(encoding="utf-8"))
    assert len(report_data) == 1
    assert report_data[0]["file"] == str(p)
    assert report_data[0]["valid"] is True
    assert report_data[0]["format"] == "json"


def test_show_validation_report_html(tmp_path, logger):
    p = tmp_path / "invalid.json"
    p.write_text('{invalid json')

    report_file = tmp_path / "report.html"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="html",
        separator="none",
        output_mode="file",
        output_path=str(report_file),
        encoding="utf-8"
    )

    valid_all = show_validation_report([str(p)], settings, logger)
    assert valid_all is False

    assert report_file.exists()
    html_content = report_file.read_text(encoding="utf-8")
    assert "<title>Archive Validation Report</title>" in html_content
    assert "File: " + html.escape(str(p)) in html_content
    assert "JSON syntax error" in html_content


def test_show_validation_report_markdown(tmp_path, logger):
    p = tmp_path / "invalid.json"
    p.write_text('{invalid json')

    report_file = tmp_path / "report.md"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="markdown",
        separator="none",
        output_mode="file",
        output_path=str(report_file),
        encoding="utf-8"
    )

    valid_all = show_validation_report([str(p)], settings, logger)
    assert valid_all is False

    assert report_file.exists()
    md_content = report_file.read_text(encoding="utf-8")
    assert "# Archive Validation Report" in md_content
    assert "- **Status:** ❌ INVALID" in md_content
    assert "JSON syntax error" in md_content


def test_show_validation_report_exception_handling(tmp_path, logger, mocker):
    from pyqwk.core import validate_archive
    # Mock validate_archive to raise an exception
    mocker.patch("pyqwk.core.validate_archive", side_effect=ValueError("Test Exception"))

    report_file = tmp_path / "report_err.txt"
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(report_file),
        encoding="utf-8"
    )

    valid_all = show_validation_report(["some_path.qwk"], settings, logger)
    assert valid_all is False

    assert report_file.exists()
    text_content = report_file.read_text(encoding="utf-8")
    assert "Validation failed: Test Exception" in text_content


def test_show_validation_report_empty_paths(logger):
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="utf-8"
    )
    valid_all = show_validation_report([], settings, logger)
    assert valid_all is True
