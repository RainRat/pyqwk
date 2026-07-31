import io
import sys
import os
import atexit
import pytest
from unittest.mock import patch, MagicMock
import tempfile
import json
import zipfile

from pyqwk.core import detect_extension, load_data, validate_archive, _cleanup_temp_files, _temp_files
from pyqwk.cli import main as cli_main

def test_detect_extension():
    # Test JSON detection
    assert detect_extension(b'{"key": "value"}') == ".json"
    assert detect_extension(b'[{"key": "value"}]') == ".json"

    # Test JSONL detection
    jsonl_data = b'{"a": 1}\n{"b": 2}'
    assert detect_extension(jsonl_data) == ".jsonl"

    # Test XML/RSS detection
    assert detect_extension(b'<?xml version="1.0"?><rss></rss>') == ".xml"
    assert detect_extension(b'<message><header></header></message>') == ".xml"

    # Test HTML detection
    assert detect_extension(b'<!DOCTYPE html><html></html>') == ".html"
    assert detect_extension(b'<html><div class="message"></div></html>') == ".html"

    # Test ZIP detection
    assert detect_extension(b'PK\x03\x04\x00\x00\x00\x00') == ".zip"

    # Test SQLite detection
    assert detect_extension(b'SQLite format 3\x00\x00') == ".db"

    # Test TAR detection
    tar_header = b'\x00' * 257 + b'ustar\x00'
    assert detect_extension(tar_header) == ".tar"

    # Test mbox detection
    assert detect_extension(b'From author@example.com Sat Jan 1 00:00:00 2000\nSubject: Hi') == ".mbox"

    # Test EML detection
    eml_data = b'From: author@example.com\nTo: recipient@example.com\nSubject: Hello\n\nBody'
    assert detect_extension(eml_data) == ".eml"

    # Test CSV detection
    csv_data = b'msgfrom,msgto,msgsubject,text\n"me","you","hi","text"'
    assert detect_extension(csv_data) == ".csv"

    # Test Markdown detection
    assert detect_extension(b'# Title\n- **Date:** 2023-10-12') == ".md"
    assert detect_extension(b'## Header') == ".md"

    # Test raw DAT detection
    assert detect_extension(b'Produced by pyqwk') == ".dat"

    # Test fallback
    assert detect_extension(b'Some random text') == ".txt"
    assert detect_extension(b'') == ".txt"

def test_load_data_stdin_tty():
    # Simulate sys.stdin.isatty() returning True
    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = True
    with patch("sys.stdin", mock_stdin):
        with pytest.raises(ValueError, match="Standard input is an interactive terminal"):
            load_data("-", MagicMock())

def test_load_data_stdin_empty():
    # Simulate sys.stdin.isatty() returning False and empty stream
    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = False
    mock_stdin.buffer.read.return_value = b""
    with patch("sys.stdin", mock_stdin):
        with pytest.raises(ValueError, match="Standard input is empty"):
            load_data("-", MagicMock())

def test_load_data_stdin_json():
    # Simulate piping a valid JSON archive
    json_payload = {
        "type": "qwk_archive",
        "messages": [
            {
                "text": "Hello from stdin!",
                "header": {
                    "msgfrom": "Alice",
                    "msgto": "Bob",
                    "msgsubject": "Standard Input Support",
                    "msgnum": 42,
                    "confnum": 1,
                    "status": " "
                }
            }
        ]
    }
    encoded = json.dumps(json_payload).encode("utf-8")

    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = False
    mock_stdin.buffer.read.return_value = encoded
    with patch("sys.stdin", mock_stdin):
        messages, board_dict = load_data("-", MagicMock())
        assert len(messages) == 1
        assert messages[0].text == "Hello from stdin!"
        assert messages[0].header.msgfrom == "Alice"

def test_validate_archive_stdin():
    # Simulate validate_archive with stdin JSON
    json_payload = {
        "type": "qwk_archive",
        "messages": [
            {
                "text": "Integrity Check",
                "header": {
                    "msgfrom": "Alice",
                    "msgto": "Bob",
                    "msgsubject": "Validation test",
                    "msgnum": 1,
                    "confnum": 1,
                    "status": " "
                }
            }
        ]
    }
    encoded = json.dumps(json_payload).encode("utf-8")

    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = False
    mock_stdin.buffer.read.return_value = encoded
    with patch("sys.stdin", mock_stdin):
        res = validate_archive("-", MagicMock())
        assert res["valid"] is True
        assert res["format"] == "json"
        assert res["messages_count"] == 1

def test_validate_archive_stdin_empty_and_tty():
    mock_stdin_tty = MagicMock()
    mock_stdin_tty.isatty.return_value = True
    with patch("sys.stdin", mock_stdin_tty):
        res = validate_archive("-", MagicMock())
        assert res["valid"] is False
        assert "interactive terminal" in res["errors"][0]

    mock_stdin_empty = MagicMock()
    mock_stdin_empty.isatty.return_value = False
    mock_stdin_empty.buffer.read.return_value = b""
    with patch("sys.stdin", mock_stdin_empty):
        res = validate_archive("-", MagicMock())
        assert res["valid"] is False
        assert "empty" in res["errors"][0]

def test_cleanup_temp_files():
    # Verify that standard input temp files are deleted by _cleanup_temp_files
    fd, path = tempfile.mkstemp()
    os.close(fd)
    _temp_files.append(path)
    assert os.path.exists(path)

    _cleanup_temp_files()
    assert not os.path.exists(path)

def test_cli_stdin_error():
    # Test CLI behavior with stdin and missing individual files output directory
    mock_stdin = MagicMock()
    mock_stdin.isatty.return_value = False
    mock_stdin.buffer.read.return_value = b'{"messages": []}'
    with patch("sys.argv", ["qwk", "-", "-i"]):
        with patch("sys.stdin", mock_stdin):
            with pytest.raises(SystemExit):
                cli_main()
