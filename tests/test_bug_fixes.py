import pytest
import sys
import os
import html
from pathlib import Path
from pyqwk.core import MessageHeader, MessagesDatFormatError, _get_html_header
from pyqwk.cli import main

def test_bug1_html_title_escaping():
    """Verify that dynamic title in HTML header is escaped."""
    title = '<b>Dangerous</b>'
    header_lines = _get_html_header(title)
    # Join lines to search
    header_text = "".join(header_lines)
    assert f"<title>{html.escape(title)}</title>" in header_text
    assert "<title><b>Dangerous</b></title>" not in header_text

def test_bug2_parser_crash_invalid_encoding():
    """Verify that invalid encoding in MessageHeader.from_bytes raises MessagesDatFormatError."""
    # Create a 128-byte record with an invalid byte for UTF-8
    record = bytearray(128)
    record[21] = 0xFF # msgto field
    
    with pytest.raises(MessagesDatFormatError) as excinfo:
        MessageHeader.from_bytes(bytes(record), encoding='utf-8')
    assert "Failed to decode header field" in str(excinfo.value)

def test_bug3_cli_conflict_threaded_eml(monkeypatch, capsys):
    """Verify that --threaded with --format eml raises a parser error."""
    monkeypatch.setattr(sys, "argv", ["qwk", "dummy.qwk", "--format", "eml", "--threaded", "-o", "out_dir"])
    with pytest.raises(SystemExit):
        main()
    stderr = capsys.readouterr().err
    assert "You cannot use --threaded with EML format." in stderr


