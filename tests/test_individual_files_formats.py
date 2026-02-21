import json
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
        conferences=None,
        authors=None,
        subjects=None,
    )
    defaults.update(overrides)
    return ProcessingSettings(**defaults)

def test_individual_files_json_format(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "json_out"

    # Run process_file with individual_files=True and format='json'
    process_file(
        str(baseline_path),
        _make_settings(
            individual_files=True,
            format="json",
            output_mode="file",
            output_path=str(output_dir),
        ),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) > 0

    # Check that the content is valid JSON
    with files[0].open("r", encoding="utf-8") as f:
        content = f.read()
        try:
            data = json.loads(content)
            # Verify it has expected fields
            assert isinstance(data, dict)
            assert "header" in data
            assert "text" in data
        except json.JSONDecodeError:
            pytest.fail(f"File content is not valid JSON: {content[:100]}...")

def test_individual_files_xml_format(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "xml_out"

    process_file(
        str(baseline_path),
        _make_settings(
            individual_files=True,
            format="xml",
            output_mode="file",
            output_path=str(output_dir),
        ),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) > 0

    # Check that the content is valid XML
    with files[0].open("r", encoding="utf-8") as f:
        content = f.read()
        try:
            root = ET.fromstring(content)
            assert root.tag == "message"
            assert root.find("header") is not None
            assert root.find("text") is not None
        except ET.ParseError:
             pytest.fail(f"File content is not valid XML: {content[:100]}...")

def test_individual_files_html_format(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "html_out"

    process_file(
        str(baseline_path),
        _make_settings(
            individual_files=True,
            format="html",
            output_mode="file",
            output_path=str(output_dir),
        ),
        logger=logger,
    )

    files = [f for f in output_dir.iterdir() if f.name not in ("index.html", "README.md")]
    assert len(files) > 0

    # Check that the content is valid HTML (contains doctype or html tag)
    with files[0].open("r", encoding="utf-8") as f:
        content = f.read()
        assert "<!DOCTYPE html>" in content or "<html>" in content
        assert '<div class="message">' in content

def test_individual_files_markdown_format(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "md_out"

    process_file(
        str(baseline_path),
        _make_settings(
            individual_files=True,
            format="markdown",
            output_mode="file",
            output_path=str(output_dir),
        ),
        logger=logger,
    )

    files = [f for f in output_dir.iterdir() if f.name not in ("index.html", "README.md")]
    assert len(files) > 0
    with files[0].open("r", encoding="utf-8") as f:
        content = f.read()
        assert "# QWK Message" in content
        assert "## " in content

def test_individual_files_mbox_format(tmp_path: Path, baseline_path: Path, logger: logging.Logger):
    output_dir = tmp_path / "mbox_out"

    process_file(
        str(baseline_path),
        _make_settings(
            individual_files=True,
            format="mbox",
            output_mode="file",
            output_path=str(output_dir),
        ),
        logger=logger,
    )

    files = list(output_dir.iterdir())
    assert len(files) > 0
    with files[0].open("r", encoding="utf-8") as f:
        content = f.read()
        assert content.startswith("From ")
        assert "Subject: " in content
