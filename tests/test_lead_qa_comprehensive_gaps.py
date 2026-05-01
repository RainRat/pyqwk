import logging
import json
import pytest
from pyqwk.core import (
    load_data,
    _apply_highlighting,
    calculate_archive_stats,
    _serialize_rfc822,
    _write_html,
    _write_markdown,
    _write_text_output,
    _render_single_message_html,
    _render_single_message_markdown,
    _parse_markdown_messages,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    BBSInfo,
    _message_to_dict
)

@pytest.fixture
def logger():
    logger = logging.getLogger("pyqwk.tests.gaps")
    logger.addHandler(logging.NullHandler())
    return logger

def test_load_data_jsonl_blank_lines(tmp_path, logger):
    jsonl_path = tmp_path / "test.jsonl"
    msg = {
        "header": {"confnum": 1, "msgnum": 1, "msgdate": "01-01-70", "msgtime": "00:00", "msgfrom": "A", "msgto": "B", "msgsubject": "S"},
        "text": "Body"
    }
    content = json.dumps(msg) + "\n\n" + json.dumps(msg) + "\n   \n"
    jsonl_path.write_text(content, encoding="utf-8")

    messages, _ = load_data(str(jsonl_path), logger)
    assert len(messages) == 2

def test_apply_highlighting_start_match():
    # Match at the very beginning of the string
    text = "Hello world"
    result = _apply_highlighting(text, "Hello", start_tag="[", end_tag="]")
    assert result == "[Hello] world"

def test_calculate_archive_stats_limit_zero(tmp_path, logger):
    json_path = tmp_path / "test.json"
    msg = _message_to_dict(ParsedMessage("Text", 1, None, 1, MessageHeader(" ", 1, "01-01-70", "00:00", "B", "A", "S", "", None, None, "", 1, 0, "")))
    json_path.write_text(json.dumps([msg]), encoding="utf-8")

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="json", separator="auto", output_mode="stdout",
        output_path=None, encoding="latin1", limit=0, quiet=True
    )
    stats = calculate_archive_stats([str(json_path)], settings, logger)
    assert stats["matching_messages"] == 0

def test_calculate_archive_stats_skip_and_reply_regex(tmp_path, logger):
    json_path = tmp_path / "test.json"
    def make_msg(i, subject):
        h = MessageHeader(" ", i, "01-01-70", "00:00", "B", "A", subject, "", None, None, "", 1, 0, "")
        return _message_to_dict(ParsedMessage("Text", i, None, 1, h))

    messages = [
        make_msg(1, "Original"),
        make_msg(2, "Re: Reply"),
        make_msg(3, "fw: Forward"),
        make_msg(4, "Another")
    ]
    json_path.write_text(json.dumps(messages), encoding="utf-8")

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="json", separator="auto", output_mode="stdout",
        output_path=None, encoding="latin1", skip=1, quiet=True
    )
    stats = calculate_archive_stats([str(json_path)], settings, logger)
    # matching_count becomes 1 after first msg, skip=1 means we skip it.
    # matching_count becomes 2 after second msg, we process it.
    # matching_count becomes 3 after third msg, we process it.
    # matching_count becomes 4 after fourth msg, we process it.
    assert stats["matching_messages"] == 3
    assert stats["reply_count"] == 2 # "Re: Reply" and "fw: Forward" should be detected via regex

def test_calculate_archive_stats_empty_text(tmp_path, logger):
    json_path = tmp_path / "test.json"
    h = MessageHeader(" ", 1, "01-01-70", "00:00", "B", "A", "S", "", None, None, "", 1, 0, "")
    msg = _message_to_dict(ParsedMessage("", 1, None, 1, h))
    json_path.write_text(json.dumps([msg]), encoding="utf-8")

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="json", separator="auto", output_mode="stdout",
        output_path=None, encoding="latin1", quiet=True
    )
    stats = calculate_archive_stats([str(json_path)], settings, logger)
    assert stats["matching_messages"] == 1
    assert stats["avg_message_length"] == 0.0

def test_serialize_rfc822_no_msgnum():
    h = MessageHeader(" ", None, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Body", None, None, 1, h)
    output = _serialize_rfc822(msg)
    assert "Message-ID: <1.x@qwk>" in output

def test_write_html_toc_no_bbs_info(monkeypatch):
    captured = []
    monkeypatch.setattr("pyqwk.core._write_text_output", lambda c, p, encoding: captured.append(c))

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Body", 1, None, 1, h, confname="General")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='html', separator='none',
        output_mode='stdout', output_path=None, encoding='utf-8', quiet=True,
        include_toc=True
    )

    _write_html([msg], None, 'utf-8', settings, bbs_info=None)
    assert "<h1>QWK Messages</h1>" in captured[0]
    assert "Conferences" in captured[0]

def test_write_markdown_toc_no_bbs_info(monkeypatch):
    captured = []
    monkeypatch.setattr("pyqwk.core._write_text_output", lambda c, p, encoding: captured.append(c))

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Body", 1, None, 1, h, confname="General")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='markdown', separator='none',
        output_mode='stdout', output_path=None, encoding='utf-8', quiet=True,
        include_toc=True
    )

    _write_markdown([msg], None, 'utf-8', settings, bbs_info=None)
    assert "# QWK Messages" in captured[0]
    assert "## Table of Contents" in captured[0]

def test_parse_markdown_no_body(tmp_path):
    md_content = "## Subject\n- **Date:** 01-01-24 12:00\n- **From:** Me\n- **To:** You\n- **Conference:** General (1)\n"
    md_path = tmp_path / "nobody.md"
    md_path.write_text(md_content, encoding="utf-8")

    messages = _parse_markdown_messages(str(md_path))
    assert len(messages) == 1
    assert messages[0].text == ""

def test_write_text_output_stdout_no_newline(mocker):
    mock_stdout = mocker.patch("sys.stdout.write")
    _write_text_output("No newline", None)
    mock_stdout.assert_called_once_with("No newline\n")

def test_render_single_message_html_optional_fields():
    h = MessageHeader(" ", None, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Body", None, None, 1, h, attachments=None)
    parts = _render_single_message_html(msg)
    html_out = "".join(parts)
    assert "<strong>Number:</strong>" not in html_out
    assert "<strong>Attachments:</strong>" not in html_out

def test_render_single_message_markdown_optional_fields():
    h = MessageHeader(" ", None, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Body", None, None, 1, h, attachments=None)
    parts = _render_single_message_markdown(msg)
    md_out = "".join(parts)
    assert "- **Number:**" not in md_out
    assert "- **Attachments:**" not in md_out

def test_write_html_toc_empty_bbs_fields(monkeypatch):
    captured = []
    monkeypatch.setattr("pyqwk.core._write_text_output", lambda c, p, encoding: captured.append(c))

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Body", 1, None, 1, h, confname="General")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='html', separator='none',
        output_mode='stdout', output_path=None, encoding='utf-8', quiet=True,
        include_toc=True
    )
    bbs = BBSInfo(name="Test") # Other fields empty
    _write_html([msg], None, 'utf-8', settings, bbs_info=bbs)
    html_out = captured[0]
    assert "SysOp:" not in html_out
    assert "Location:" not in html_out
    assert "Packet Date:" not in html_out

def test_write_markdown_toc_empty_bbs_fields(monkeypatch):
    captured = []
    monkeypatch.setattr("pyqwk.core._write_text_output", lambda c, p, encoding: captured.append(c))

    h = MessageHeader(" ", 1, "01-01-70", "00:00", "To", "From", "Sub", "", None, None, "", 1, 0, "")
    msg = ParsedMessage("Body", 1, None, 1, h, confname="General")
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=False, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, strip_ansi=False, format='markdown', separator='none',
        output_mode='stdout', output_path=None, encoding='utf-8', quiet=True,
        include_toc=True
    )
    bbs = BBSInfo(name="Test") # Other fields empty
    _write_markdown([msg], None, 'utf-8', settings, bbs_info=bbs)
    md_out = captured[0]
    assert "**SysOp:**" not in md_out
    assert "**Location:**" not in md_out
    assert "**Packet Date:**" not in md_out
