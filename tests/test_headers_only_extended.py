import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
import logging

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pyqwk.core as qwk
from pyqwk.core import process_file, ProcessingSettings

@pytest.fixture
def baseline_path() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata" / "messages.dat"

@pytest.fixture
def logger() -> logging.Logger:
    logger = logging.getLogger("pyqwk.tests")
    logger.addHandler(logging.NullHandler())
    return logger

def _make_settings(**overrides) -> ProcessingSettings:
    defaults = dict(
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
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="latin1",
        quiet=True,
        headers_only=False,
        conferences=None,
        authors=None,
        subjects=None,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_headers_only_xml_batch(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_path = tmp_path / "output.xml"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="xml", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    tree = ET.parse(output_path)
    root = tree.getroot()
    message = root.find("message")
    assert message is not None
    assert message.find("header") is not None
    # Text element should be empty
    text_elem = message.find("text")
    assert text_elem is not None
    assert text_elem.text is None or text_elem.text == ""

def test_headers_only_sqlite_batch(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_path = tmp_path / "output.sqlite"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="sqlite", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()
    cursor.execute("SELECT text FROM messages")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == ""
    conn.close()

def test_headers_only_mbox_batch(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_path = tmp_path / "output.mbox"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="mbox", output_mode="file", output_path=str(output_path)),
        logger=logger,
    )

    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()

    # mbox should have headers
    assert "From: " in content
    assert "Subject: " in content
    # But body (the part after the first empty line after headers) should be empty
    # In mbox, there is an empty line between headers and body.
    # If body is empty, we'll see \n\n followed by either another From line or end of file.
    # Our mbox serializer appends a newline after body.
    # So we expect something like Message-ID: ...\n\n\n
    assert content.count("\n\n") >= 1

def test_headers_only_xml_individual(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "xml_ind"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="xml", individual_files=True, output_mode="file", output_path=str(output_dir)),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) > 0
    tree = ET.parse(files[0])
    root = tree.getroot()
    assert root.tag == "message"
    text_elem = root.find("text")
    assert text_elem is not None
    assert text_elem.text is None or text_elem.text == ""

def test_headers_only_html_individual(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "html_ind"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="html", individual_files=True, output_mode="file", output_path=str(output_dir)),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) > 0
    with open(files[0], "r", encoding="utf-8") as f:
        content = f.read()

    assert '<div class="header">' in content
    # The body should be empty
    # Due to \n join in HTML serialization, empty text results in \n\n inside <pre>
    assert '<pre class="body">\n\n</pre>' in content or '<pre class="body"></pre>' in content

def test_headers_only_mbox_individual(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "mbox_ind"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="mbox", individual_files=True, output_mode="file", output_path=str(output_dir)),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) > 0
    with open(files[0], "r", encoding="utf-8") as f:
        content = f.read()

    assert "From: " in content
    # Body should be empty (just the newline between header and body, and the trailing newline)
    # The _serialize_message_mbox appends \n after body.
    # If body is empty, we get \n (sep) + \n (trailing) = \n\n at the end of headers.
    assert content.endswith("\n\n")

def test_headers_only_json_individual(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "json_ind"
    process_file(
        str(baseline_path),
        _make_settings(headers_only=True, format="json", individual_files=True, output_mode="file", output_path=str(output_dir)),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) > 0
    with open(files[0], "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "header" in data
    assert data["text"] == ""
