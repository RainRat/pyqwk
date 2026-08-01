import io
import os
import sys
import logging
import pytest
from unittest.mock import MagicMock

from pyqwk.core import detect_extension, check_and_handle_stdin, _temp_files_to_clean


def test_detect_extension_formats():
    # SQLite
    assert detect_extension(b"SQLite format 3\x00someextra") == ".db"

    # ZIP
    assert detect_extension(b"PK\x03\x04zipdata") == ".zip"

    # GZIP / TAR
    assert detect_extension(b"\x1f\x8badditional") == ".tar.gz"

    # BZIP2
    assert detect_extension(b"BZhadditional") == ".tar.bz2"

    # TAR signature
    tar_signature = b"\x00" * 257 + b"ustar" + b"\x00" * 5
    assert detect_extension(tar_signature) == ".tar"

    # Empty
    assert detect_extension(b"") == ".txt"

    # JSON
    assert detect_extension(b'{"type": "qwk_archive", "messages": []}') == ".json"

    # JSONL
    assert detect_extension(b'{"msgfrom": "A"}\n{"msgfrom": "B"}') == ".jsonl"

    # XML
    assert detect_extension(b'<?xml version="1.0"?><message></message>') == ".xml"

    # RSS
    assert detect_extension(b'<rss><channel><item></item></channel></rss>') == ".rss"

    # HTML
    assert detect_extension(b'<!DOCTYPE html><html></html>') == ".html"

    # mbox
    assert detect_extension(b'From test@example.com\nDate: ...') == ".mbox"

    # EML
    eml_data = b'Date: ...\nFrom: ...\nTo: ...\nSubject: ...\n\nBody'
    assert detect_extension(eml_data) == ".eml"

    # Markdown
    md_data = b'## Subject\n- **Date:** ...\n- **From:** ...\n- **To:** ...\n---\nBody'
    assert detect_extension(md_data) == ".md"

    # CSV
    csv_data = b'msgfrom,msgto,msgsubject,text\n"A","B","C","D"\n'
    assert detect_extension(csv_data) == ".csv"

    # Default Text
    assert detect_extension(b"Normal random text") == ".txt"


def test_check_and_handle_stdin_no_paths():
    logger = logging.getLogger("test")
    assert check_and_handle_stdin([], logger) == []


def test_check_and_handle_stdin_no_stdin():
    logger = logging.getLogger("test")
    paths = ["file1.qwk", "file2.json"]
    assert check_and_handle_stdin(paths, logger) == paths


def test_check_and_handle_stdin_with_piping(monkeypatch, tmp_path):
    logger = logging.getLogger("test")
    json_bytes = b'{"type": "qwk_archive", "messages": []}'

    # Mock sys.stdin with an object having buffer
    class MockStdin:
        buffer = io.BytesIO(json_bytes)

    monkeypatch.setattr(sys, "stdin", MockStdin())

    paths = ["-", "file1.qwk"]
    result = check_and_handle_stdin(paths, logger)

    assert len(result) == 2
    assert result[1] == "file1.qwk"

    temp_path = result[0]
    assert temp_path.endswith(".json")
    assert os.path.exists(temp_path)
    assert temp_path in _temp_files_to_clean

    with open(temp_path, "rb") as f:
        assert f.read() == json_bytes


def test_check_and_handle_stdin_read_failure(monkeypatch):
    logger = logging.getLogger("test")

    class FailingBuffer:
        def read(self, *args, **kwargs):
            raise IOError("Mock read failure")

    class MockStdin:
        buffer = FailingBuffer()

    monkeypatch.setattr(sys, "stdin", MockStdin())

    # It should call sys.exit(1) on failure
    with pytest.raises(SystemExit) as excinfo:
        check_and_handle_stdin(["-"], logger)
    assert excinfo.value.code == 1


def test_cli_integration_with_piping(monkeypatch, tmp_path):
    # Test main CLI with stdin
    from pyqwk.cli import main

    json_bytes = b'{"type": "qwk_archive", "messages": []}'
    class MockStdin:
        buffer = io.BytesIO(json_bytes)

    monkeypatch.setattr(sys, "stdin", MockStdin())

    # Set arguments to pass '-' as input path
    monkeypatch.setattr(sys, "argv", ["qwk", "-"])

    # Prevent sys.exit from actually quitting the test runner (if raised)
    try:
        main()
    except SystemExit as e:
        assert e.code in (0, None)


def test_gui_integration_with_piping(monkeypatch, tmp_path):
    # Test main GUI with stdin
    from pyqwk.gui import main

    json_bytes = b'{"type": "qwk_archive", "messages": []}'
    class MockStdin:
        buffer = io.BytesIO(json_bytes)

    monkeypatch.setattr(sys, "stdin", MockStdin())

    # Set arguments to pass '-'
    monkeypatch.setattr(sys, "argv", ["qwk-gui", "-"])

    # Mock Tk.mainloop to avoid blocking
    import tkinter as tk
    monkeypatch.setattr(tk.Tk, "mainloop", lambda self: None)

    # Mock QwkGuiApp.__init__ or load_messages to avoid actual loading which might fail on empty json messages
    from pyqwk.gui import QwkGuiApp
    monkeypatch.setattr(QwkGuiApp, "__init__", lambda self, root, initial_paths, my_name: None)

    # main() should run and instantiate Tk
    main()
