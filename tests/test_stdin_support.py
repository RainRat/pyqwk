import io
import sys
import os
import pytest
from unittest.mock import patch, MagicMock

from pyqwk.core import detect_extension, FORMAT_EXTENSIONS
from pyqwk.cli import main as cli_main
from pyqwk.gui import main as gui_main


def test_detect_extension_explicit_format():
    """Verify that specifying a format argument skips auto-detection and returns its extension."""
    assert detect_extension(b"{}", "json") == ".json"
    assert detect_extension(b"some text", "html") == ".html"
    assert detect_extension(b"", "xml") == ".xml"


def test_detect_extension_empty_input():
    """Verify that empty bytes default to .txt."""
    assert detect_extension(b"") == ".txt"
    assert detect_extension(b"   \n  ") == ".txt"


def test_detect_extension_archives():
    """Verify ZIP and TAR/compressed TAR signature detection."""
    # ZIP magic bytes: PK\x03\x04
    assert detect_extension(b"PK\x03\x04abc") == ".zip"

    # gzip: \x1f\x8b\x08
    assert detect_extension(b"\x1f\x8b\x08abc") == ".tar.gz"

    # bzip2: BZh
    assert detect_extension(b"BZh9abc") == ".tar.bz2"

    # tar: ustar at offset 257
    tar_bytes = b"\x00" * 257 + b"ustar" + b"\x00" * 10
    assert detect_extension(tar_bytes) == ".tar"


def test_detect_extension_json_and_jsonl():
    """Verify JSON and JSONL structure detection."""
    # Full single JSON object
    assert detect_extension(b'{"key": "val"}') == ".json"

    # Full single JSON array
    assert detect_extension(b'[{"key": "val"}]') == ".json"

    # JSONL (line-by-line JSON objects)
    assert detect_extension(b'{"key": "val1"}\n{"key": "val2"}') == ".jsonl"

    # Invalid JSON block starting with {
    assert detect_extension(b'{\nincomplete json') == ".jsonl"


def test_detect_extension_markup_and_feeds():
    """Verify XML, RSS, and HTML auto-detection."""
    assert detect_extension(b"<rss version='2.0'><channel></channel></rss>") == ".rss"
    assert detect_extension(b"<feed xmlns='http://www.w3.org/2005/Atom'></feed>") == ".rss"
    assert detect_extension(b"<!DOCTYPE html><html></html>") == ".html"
    assert detect_extension(b"<html><head></head><body></body></html>") == ".html"
    assert detect_extension(b"<root><child></child></root>") == ".xml"


def test_detect_extension_emails_and_csv():
    """Verify mbox, EML, and CSV auto-detection."""
    assert detect_extension(b"From author@domain.com Mon Jan 1 00:00:00 2023") == ".mbox"

    eml_data = b"Subject: Greetings\nDate: Mon, 1 Jan 2023\n\nHello World"
    assert detect_extension(eml_data) == ".eml"

    csv_data = b"author,to,subject,body\nAlice,Bob,Hello,Hi there"
    assert detect_extension(csv_data) == ".csv"


def test_detect_extension_markdown():
    """Verify Markdown auto-detection."""
    assert detect_extension(b"# Heading 1\nSome text") == ".md"
    assert detect_extension(b"Check [this link](http://example.com) out!") == ".md"


def test_cli_stdin_json(monkeypatch):
    """Test reading JSON messages from stdin via CLI with '-' argument."""
    json_payload = b"""[
        {
            "header": {
                "msgfrom": "Alice",
                "msgto": "Bob",
                "msgsubject": "Testing stdin",
                "date": "01-01-23",
                "time": "12:00",
                "confnum": 1,
                "status": " "
            },
            "text": "Hello via standard input!"
        }
    ]"""

    # Mock stdin
    mock_stdin = MagicMock()
    mock_stdin.buffer = io.BytesIO(json_payload)
    monkeypatch.setattr(sys, "stdin", mock_stdin)

    # Mock CLI arguments
    test_args = ["qwk", "-", "--oneline"]
    monkeypatch.setattr(sys, "argv", test_args)

    # Mock stdout to capture output
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)

    # Call CLI main
    with patch("sys.exit") as mock_exit:
        cli_main()
        # It shouldn't crash and should print output containing "Testing stdin"
        output = captured_stdout.getvalue()
        assert "Testing stdin" in output


def test_cli_stdin_explicit_format(monkeypatch):
    """Test reading standard input via CLI with explicit format overriding."""
    jsonl_payload = b'{"header": {"msgfrom": "Alice", "msgto": "Bob", "msgsubject": "Explicit JSONL", "date": "01-01-23", "time": "12:00", "confnum": 1, "status": " "}, "text": "Explicit test"}\n'

    mock_stdin = MagicMock()
    mock_stdin.buffer = io.BytesIO(jsonl_payload)
    monkeypatch.setattr(sys, "stdin", mock_stdin)

    test_args = ["qwk", "-", "-F", "jsonl", "--oneline"]
    monkeypatch.setattr(sys, "argv", test_args)

    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)

    with patch("sys.exit") as mock_exit:
        cli_main()
        output = captured_stdout.getvalue()
        assert "Explicit JSONL" in output


def test_gui_stdin_json(monkeypatch):
    """Test gui entrypoint with stdin support."""
    json_payload = b'[]'

    mock_stdin = MagicMock()
    mock_stdin.buffer = io.BytesIO(json_payload)
    monkeypatch.setattr(sys, "stdin", mock_stdin)

    test_args = ["qwk-gui", "-"]
    monkeypatch.setattr(sys, "argv", test_args)

    # Mock Tkinter Tk so it doesn't open a real window
    mock_tk = MagicMock()
    monkeypatch.setattr("tkinter.Tk", mock_tk)

    # Mock QwkGuiApp
    mock_app = MagicMock()
    monkeypatch.setattr("pyqwk.gui.QwkGuiApp", mock_app)

    # Call GUI main
    gui_main()

    # Verify that it expanded paths and initialized QwkGuiApp with a temporary file path
    assert mock_app.called
    init_args = mock_app.call_args[1]
    assert "initial_paths" in init_args
    assert len(init_args["initial_paths"]) == 1
    assert init_args["initial_paths"][0].endswith(".json")


def test_cli_stdin_read_error(monkeypatch):
    """Test that failed stdin read displays standard error and exits."""
    # Mock a read error
    mock_buffer = MagicMock()
    mock_buffer.read.side_effect = Exception("Read timed out")

    mock_stdin = MagicMock()
    mock_stdin.buffer = mock_buffer
    monkeypatch.setattr(sys, "stdin", mock_stdin)

    test_args = ["qwk", "-"]
    monkeypatch.setattr(sys, "argv", test_args)

    # We expect parser.error to be triggered, raising SystemExit or printing error
    with pytest.raises(SystemExit):
        cli_main()
