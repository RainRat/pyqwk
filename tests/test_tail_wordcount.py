import pytest
import logging
from dataclasses import replace
from pyqwk.core import (
    process_merged_files,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    _get_message_mapping,
    calculate_archive_stats,
)

@pytest.fixture
def mock_logger():
    return logging.getLogger("test_tail_wordcount")

@pytest.fixture
def mock_messages():
    header_template = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="Everyone",
        msgfrom="Alice",
        msgsubject="Subject",
        msgpassword="",
        refnum=None,
        numblocks=2,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )

    msgs = []
    for i in range(1, 11):
        # Different word counts: i words
        text = " ".join([f"word{j}" for j in range(i)])
        msgs.append(
            ParsedMessage(
                text=text,
                msgnum=i,
                refnum=None,
                confnum=1,
                header=replace(header_template, msgnum=i),
            )
        )
    return msgs

def test_tail_restricts_output(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    tail = 3
    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        tail=tail,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    # Should contain Message 8, 9, 10 but not 7
    # Note: our messages have text "word0 word1 ..."
    assert "word0" in content # Message 1-10 all have word0
    assert "word7" in content # Message 8, 9, 10
    assert "word9" in content # Message 10

    # Verify count of messages by counting "word0" which appears once per message
    assert content.count("word0") == 3

def test_word_count_variable(mock_messages):
    msg = mock_messages[4] # Message 5, should have 5 words
    mapping = _get_message_mapping(msg, 1)
    assert mapping["word_count"] == 5

def test_avg_word_count_stats(mock_messages, mock_logger, monkeypatch):
    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
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
        encoding="cp437",
        quiet=True,
    )

    stats = calculate_archive_stats(["dummy.qwk"], settings, mock_logger)
    # Total words: 1+2+3+4+5+6+7+8+9+10 = 55
    # Average: 55 / 10 = 5.5
    assert stats["avg_word_count"] == 5.5

def test_tail_with_skip_and_limit(tmp_path, mock_messages, mock_logger, monkeypatch):
    output_path = tmp_path / "output.txt"

    def fake_load_data(*args, **kwargs):
        return bytearray(), {1: "General"}

    def fake_parse_messages(*args, **kwargs):
        yield from mock_messages

    monkeypatch.setattr("pyqwk.core.load_data", fake_load_data)
    monkeypatch.setattr("pyqwk.core.parse_messages", fake_parse_messages)

    # Original: 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
    # skip 2: 3, 4, 5, 6, 7, 8, 9, 10
    # limit 5: 3, 4, 5, 6, 7
    # tail 2: 6, 7

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=True,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(output_path),
        encoding="cp437",
        quiet=True,
        skip=2,
        limit=5,
        tail=2,
    )

    process_merged_files(["dummy.qwk"], settings, mock_logger)

    content = output_path.read_text(encoding="latin1")
    assert content.count("word0") == 2
    assert "word5" in content # Message 6 has word0..word5
    assert "word6" in content # Message 7 has word0..word6
    assert "word7" not in content # Message 8+ would have word7
