import pytest
import logging
from dataclasses import replace
from pyqwk.core import (
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    _get_message_mapping,
)

@pytest.fixture
def mock_logger():
    return logging.getLogger("test_behavioral_filters")

@pytest.fixture
def base_header():
    return MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Everyone",
        msgfrom="Alice",
        msgsubject="Topic",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )

def test_filter_has_questions(tmp_path, base_header, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"
    msgs = [
        ParsedMessage(text="Hello world.", msgnum=1, refnum=None, confnum=1, header=replace(base_header, msgnum=1)),
        ParsedMessage(text="How are you?", msgnum=2, refnum=None, confnum=1, header=replace(base_header, msgnum=2)),
    ]

    monkeypatch.setattr("pyqwk.core.load_data", lambda *a, **k: (bytearray(), {1: "General"}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *a, **k: iter(msgs))

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        has_questions=True
    )

    process_merged_files(["dummy"], settings, mock_logger)
    content = output_path.read_text()
    assert "How are you?" in content
    assert "Hello world." not in content

def test_filter_has_quotes(tmp_path, base_header, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"
    msgs = [
        ParsedMessage(text="Regular text.", msgnum=1, refnum=None, confnum=1, header=replace(base_header, msgnum=1)),
        ParsedMessage(text="> Quoted text.", msgnum=2, refnum=None, confnum=1, header=replace(base_header, msgnum=2)),
    ]

    monkeypatch.setattr("pyqwk.core.load_data", lambda *a, **k: (bytearray(), {1: "General"}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *a, **k: iter(msgs))

    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        has_quotes=True
    )

    process_merged_files(["dummy"], settings, mock_logger)
    content = output_path.read_text()
    assert "> Quoted text." in content
    assert "Regular text." not in content

def test_filter_replies_and_no_replies(tmp_path, base_header, mock_logger, monkeypatch):
    output_path_r = tmp_path / "replies.txt"
    output_path_nr = tmp_path / "no_replies.txt"

    msgs = [
        ParsedMessage(text="Original", msgnum=1, refnum=None, confnum=1, header=replace(base_header, msgnum=1)),
        ParsedMessage(text="Reply by ref", msgnum=2, refnum=1, confnum=1, header=replace(base_header, msgnum=2, refnum=1)),
        ParsedMessage(text="Reply by subject", msgnum=3, refnum=None, confnum=1, header=replace(base_header, msgnum=3, msgsubject="Re: Topic")),
    ]

    monkeypatch.setattr("pyqwk.core.load_data", lambda *a, **k: (bytearray(), {1: "General"}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *a, **k: iter(msgs))

    # Test --replies
    settings_r = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path_r), encoding="cp437", quiet=True,
        replies=True
    )
    process_merged_files(["dummy"], settings_r, mock_logger)
    content_r = output_path_r.read_text()
    assert "Reply by ref" in content_r
    assert "Reply by subject" in content_r
    assert "Original" not in content_r

    # Test --no-replies
    settings_nr = replace(settings_r, output_path=str(output_path_nr), replies=False, no_replies=True)
    process_merged_files(["dummy"], settings_nr, mock_logger)
    content_nr = output_path_nr.read_text()
    assert "Original" in content_nr
    assert "Reply by ref" not in content_nr
    assert "Reply by subject" not in content_nr

def test_filter_word_count(tmp_path, base_header, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"
    msgs = [
        ParsedMessage(text="One two", msgnum=1, refnum=None, confnum=1, header=replace(base_header, msgnum=1)), # 2 words
        ParsedMessage(text="One two three four", msgnum=2, refnum=None, confnum=1, header=replace(base_header, msgnum=2)), # 4 words
        ParsedMessage(text="One two three four five six", msgnum=3, refnum=None, confnum=1, header=replace(base_header, msgnum=3)), # 6 words
    ]

    monkeypatch.setattr("pyqwk.core.load_data", lambda *a, **k: (bytearray(), {1: "General"}))
    monkeypatch.setattr("pyqwk.core.parse_messages", lambda *a, **k: iter(msgs))

    # Test min_words=4
    settings = ProcessingSettings(
        verbose=False, private=False, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="file",
        output_path=str(output_path), encoding="cp437", quiet=True,
        min_words=4
    )
    process_merged_files(["dummy"], settings, mock_logger)
    content = output_path.read_text()
    assert "One two three four" in content
    assert "six" in content
    assert "One two" not in content.replace("One two three", "") # Check for exactly "One two" message

    # Test max_words=4
    output_path.unlink()
    settings = replace(settings, min_words=None, max_words=4)
    process_merged_files(["dummy"], settings, mock_logger)
    content = output_path.read_text()
    assert "One two" in content
    assert "One two three four" in content
    assert "six" not in content

def test_mapping_variables(base_header):
    msg1 = ParsedMessage(text="Question?", msgnum=1, refnum=None, confnum=1, header=replace(base_header, msgnum=1))
    mapping1 = _get_message_mapping(msg1, 1)
    assert mapping1["has_questions"] == "true"
    assert mapping1["has_quotes"] == "false"

    msg2 = ParsedMessage(text="> Quote\nAnswer", msgnum=2, refnum=None, confnum=1, header=replace(base_header, msgnum=2))
    mapping2 = _get_message_mapping(msg2, 2)
    assert mapping2["has_questions"] == "false"
    assert mapping2["has_quotes"] == "true"
