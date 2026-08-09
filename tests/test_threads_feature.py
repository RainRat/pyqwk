import json
import csv
import io
import os
import logging
from unittest.mock import MagicMock, patch
import pytest

from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    show_threads,
)


@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)


@pytest.fixture
def base_settings():
    return ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        quiet=True,
        format="text",
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        sort=None,
        reverse=False,
        threads=True,
    )


@pytest.fixture
def sample_messages():
    h1 = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-94", msgtime="12:00:00",
        msgto="All", msgfrom="Starter Alice", msgsubject="Discussion A", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=1, nettag=" "
    )
    # Reply with subject indicating it is a reply
    h2 = MessageHeader(
        status=" ", msgnum=2, msgdate="01-02-94", msgtime="10:00:00",
        msgto="Starter Alice", msgfrom="Reply Bob", msgsubject="Re: Discussion A", msgpassword="",
        refnum=1, numblocks=1, msgflag=" ", confnum=1, lognum=2, nettag=" "
    )
    # Another thread
    h3 = MessageHeader(
        status=" ", msgnum=3, msgdate="01-01-94", msgtime="08:00:00",
        msgto="All", msgfrom="Starter Charlie", msgsubject="Discussion B", msgpassword="",
        refnum=None, numblocks=1, msgflag=" ", confnum=1, lognum=3, nettag=" "
    )

    msg1 = ParsedMessage(text="First post", msgnum=1, refnum=None, confnum=1, header=h1)
    msg2 = ParsedMessage(text="Reply to first", msgnum=2, refnum=1, confnum=1, header=h2)
    msg3 = ParsedMessage(text="Second thread starter", msgnum=3, refnum=None, confnum=1, header=h3)

    return [msg1, msg2, msg3]


def test_show_threads_text_format(capsys, mock_logger, base_settings, sample_messages):
    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], base_settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    # Text output should have headers and rows
    assert "ID" in output
    assert "Subject" in output
    assert "Discussion A" in output
    assert "Discussion B" in output
    assert "Starter Alice" in output
    assert "Starter Charlie" in output


def test_show_threads_json_format(capsys, mock_logger, base_settings, sample_messages):
    settings = base_settings
    settings.format = "json"

    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    data = json.loads(output)
    assert isinstance(data, list)
    assert len(data) == 2  # Two threads

    # Verify fields of thread 1 (Discussion B, as it started earlier on 01-01-94 at 08:00 vs 12:00)
    # Actually, default order is sorted by started_at ascending.
    # Charlie's thread starts at 08:00:00. Alice's at 12:00:00.
    t0 = data[0]
    assert t0["thread_id"] == "3"
    assert t0["subject"] == "Discussion B"
    assert t0["started_by"] == "Starter Charlie"
    assert t0["message_count"] == 1
    assert t0["max_depth"] == 0

    t1 = data[1]
    assert t1["thread_id"] == "1"
    assert t1["subject"] == "Discussion A"
    assert t1["started_by"] == "Starter Alice"
    assert t1["message_count"] == 2
    assert t1["max_depth"] == 1


def test_show_threads_csv_format(capsys, mock_logger, base_settings, sample_messages):
    settings = base_settings
    settings.format = "csv"

    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    reader = csv.DictReader(io.StringIO(output))
    rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["thread_id"] == "3"
    assert rows[0]["subject"] == "Discussion B"
    assert rows[1]["thread_id"] == "1"
    assert rows[1]["subject"] == "Discussion A"


def test_show_threads_markdown_format(capsys, mock_logger, base_settings, sample_messages):
    settings = base_settings
    settings.format = "markdown"

    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    assert "# Conversation Threads" in output
    assert "| ID | Subject | Started By |" in output
    assert "| 3 | Discussion B |" in output
    assert "| 1 | Discussion A |" in output


def test_show_threads_html_format(capsys, mock_logger, base_settings, sample_messages):
    settings = base_settings
    settings.format = "html"

    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    output = captured.out

    assert "<!DOCTYPE html>" in output
    assert "<h1>Conversation Threads</h1>" in output
    assert "<table>" in output
    assert "<td>Discussion A</td>" in output
    assert "<td>Discussion B</td>" in output


def test_show_threads_sorting(capsys, mock_logger, base_settings, sample_messages):
    # Sort by subject
    settings = base_settings
    settings.format = "json"
    settings.sort = "subject"

    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Discussion A should come before Discussion B
    assert data[0]["subject"] == "Discussion A"
    assert data[1]["subject"] == "Discussion B"

    # Sort by subject reverse
    settings.reverse = True
    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data[0]["subject"] == "Discussion B"
    assert data[1]["subject"] == "Discussion A"

    # Sort by author
    settings.sort = "author"
    settings.reverse = False
    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Alice before Charlie
    assert data[0]["started_by"] == "Starter Alice"
    assert data[1]["started_by"] == "Starter Charlie"

    # Sort by size (message_count)
    settings.sort = "size"
    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Default is ascending (thread with 1 msg before thread with 2 msgs)
    assert data[0]["message_count"] == 1
    assert data[1]["message_count"] == 2

    # Sort by size descending
    settings.reverse = True
    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data[0]["message_count"] == 2
    assert data[1]["message_count"] == 1

    # Sort by last_activity descending
    settings.sort = "last_activity"
    settings.reverse = True
    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    # Discussion A last activity was 01-02-94, whereas B was 01-01-94. So A should be first.
    assert data[0]["subject"] == "Discussion A"
    assert data[1]["subject"] == "Discussion B"

    # Sort by random
    settings.sort = "random"
    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 2


def test_show_threads_filtering(capsys, mock_logger, base_settings, sample_messages):
    settings = base_settings
    settings.format = "json"
    # Filter only Starter Charlie's messages
    settings.authors = ["Charlie"]

    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert len(data) == 1
    assert data[0]["started_by"] == "Starter Charlie"


def test_show_threads_output_to_file(tmp_path, mock_logger, base_settings, sample_messages):
    output_file = tmp_path / "threads.csv"
    settings = base_settings
    settings.format = "csv"
    settings.output_path = str(output_file)

    with patch("pyqwk.core.load_data", return_value=(sample_messages, {1: "General"})):
        show_threads(["dummy.qwk"], settings, mock_logger)

    assert output_file.exists()
    content = output_file.read_text(encoding="utf-8")
    assert "thread_id" in content
    assert "Discussion A" in content
    assert "Discussion B" in content


def test_show_threads_no_messages(mock_logger, base_settings):
    with patch("pyqwk.core.load_data", return_value=([], {})):
        show_threads(["dummy.qwk"], base_settings, mock_logger)

    mock_logger.info.assert_called_with("No matching messages/threads found.")
