import logging
from dataclasses import replace
from unittest.mock import MagicMock, patch
import pytest
from pyqwk.core import show_info, ProcessingSettings, BBSInfo

@pytest.fixture
def mock_logger():
    return MagicMock(spec=logging.Logger)

@pytest.fixture
def default_settings():
    return ProcessingSettings(
        verbose=False,
        private=False,
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
        conferences=None,
    )

def test_show_info_html_error_and_location(capsys, mock_logger, default_settings):
    """Cover lines 5543-5545 and 5559 in pyqwk/core.py."""
    html_settings = replace(default_settings, format="html")

    # Mock load_data to return a board with BBS location
    mock_bbs = BBSInfo(name="Test BBS", location="Mars")
    mock_board = MagicMock()
    mock_board.bbs_info = mock_bbs
    mock_board.get.side_effect = lambda n, d: d

    with patch("pyqwk.core.load_data", return_value=([], mock_board)):
        # Test location (5559)
        show_info(["test.qwk"], html_settings, mock_logger)
        out = capsys.readouterr().out
        assert "<strong>Location:</strong> Mars" in out

        # Test error (5543-5545)
        # We need to trigger the error branch in _render_info_html.
        # This happens if an entry in all_info has "error".
        # In show_info, this happens if len(file_data) < BLOCK_SIZE and not a list.
        with patch("pyqwk.core.load_data", return_value=(bytearray(b"short"), mock_board)):
            show_info(["short.qwk"], html_settings, mock_logger)
            out = capsys.readouterr().out
            assert "Invalid or empty file." in out
            assert "short.qwk" in out

def test_show_info_markdown_error_and_location(capsys, mock_logger, default_settings):
    """Cover lines 5599-5600 and 5609 in pyqwk/core.py."""
    md_settings = replace(default_settings, format="markdown")

    # Mock load_data to return a board with BBS location
    mock_bbs = BBSInfo(name="Test BBS", location="Mars")
    mock_board = MagicMock()
    mock_board.bbs_info = mock_bbs
    mock_board.get.side_effect = lambda n, d: d

    with patch("pyqwk.core.load_data", return_value=([], mock_board)):
        # Test location (5609)
        show_info(["test.qwk"], md_settings, mock_logger)
        out = capsys.readouterr().out
        assert "**Location:** Mars" in out

        # Test error (5599-5600)
        with patch("pyqwk.core.load_data", return_value=(bytearray(b"short"), mock_board)):
            show_info(["short.qwk"], md_settings, mock_logger)
            out = capsys.readouterr().out
            assert "Invalid or empty file." in out

def test_show_info_my_name_propagation(capsys, mock_logger, default_settings):
    """Cover line 5650 in pyqwk/core.py."""
    settings = replace(default_settings, my_name="Jules Verne", format="json")

    mock_bbs = BBSInfo(name="Test BBS")
    mock_board = MagicMock()
    mock_board.bbs_info = mock_bbs

    with patch("pyqwk.core.load_data", return_value=([], mock_board)):
        show_info(["test.qwk"], settings, mock_logger)
        out = capsys.readouterr().out
        import json
        data = json.loads(out)
        assert data[0]["bbs_info"]["user_name"] == "Jules Verne"
