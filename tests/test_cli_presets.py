import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock
import pyqwk.cli as cli
from pyqwk.cli import main

@pytest.fixture
def testdata_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "testdata"

def test_preset_blog(monkeypatch, testdata_dir):
    """Verify that the 'blog' preset sets HTML format, threading, cleaning, and embedded attachments."""
    input_file = testdata_dir / "messages.dat"

    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-P", "blog"]
    )

    mock_process = MagicMock()
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]

    assert settings.format == "html"
    assert settings.threaded is True
    assert settings.truncate_signatures is True
    assert settings.cut_quoting is True
    assert settings.binaries_removal is True
    assert settings.embed_attachments is True

def test_preset_email(monkeypatch, testdata_dir):
    """Verify that the 'email' preset sets EML format, individual files, and extracted attachments."""
    input_file = testdata_dir / "messages.dat"

    # EML with individual files normally requires a folder as output path
    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-P", "email", "-o", "output_dir/"]
    )

    mock_process = MagicMock()
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]

    assert settings.format == "eml"
    assert settings.individual_files is True
    assert settings.extract_attachments is True

def test_preset_backup(monkeypatch, testdata_dir):
    """Verify that the 'backup' preset sets SQLite format and includes private messages."""
    input_file = testdata_dir / "messages.dat"

    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-P", "backup", "-o", "messages.db"]
    )

    mock_process = MagicMock()
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]

    assert settings.format == "sqlite"
    assert settings.private is True

def test_preset_digest(monkeypatch, testdata_dir):
    """Verify that the 'digest' preset sets oneline summary, threading, and sorting by date."""
    input_file = testdata_dir / "messages.dat"

    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-P", "digest"]
    )

    mock_process = MagicMock()
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]

    assert settings.oneline is True
    assert settings.threaded is True
    assert settings.sort == "date"

def test_preset_text_archive(monkeypatch, testdata_dir):
    """Verify that the 'text-archive' preset sets text format, dashes separator, headers, and cleaning."""
    input_file = testdata_dir / "messages.dat"

    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-P", "text-archive"]
    )

    mock_process = MagicMock()
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]

    assert settings.format == "text"
    assert settings.separator == "dashes"
    assert settings.no_header is False
    assert settings.truncate_signatures is True
    assert settings.cut_quoting is True
    assert settings.binaries_removal is True

def test_preset_override(monkeypatch, testdata_dir):
    """Verify that explicit CLI arguments override the defaults applied by presets."""
    input_file = testdata_dir / "messages.dat"

    # Apply blog preset but override format to JSON and disable threaded view
    monkeypatch.setattr(
        sys,
        "argv",
        ["qwk", str(input_file), "-P", "blog", "--format", "json"]
    )

    mock_process = MagicMock()
    with monkeypatch.context() as m:
        m.setattr(cli, "process_merged_files", mock_process)
        main()

    mock_process.assert_called_once()
    settings = mock_process.call_args[0][1]

    # Format should be explicitly json, not HTML from the blog preset
    assert settings.format == "json"
    # Threaded and others should still receive their preset defaults since they were not overridden
    assert settings.threaded is True
    assert settings.truncate_signatures is True
