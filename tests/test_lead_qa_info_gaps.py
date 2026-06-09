import logging
from dataclasses import replace, asdict
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


def test_show_info_html_error_rendering(capsys, mock_logger, default_settings):
    """Test that errors are correctly rendered in HTML format in show_info."""
    html_settings = replace(default_settings, format="html")

    with patch("pyqwk.core.load_data") as mock_load:
        # Return too short data to trigger "Invalid or empty file" error in show_info
        mock_load.return_value = (bytearray(b"short"), {})

        show_info(["bad_file.zip"], html_settings, mock_logger)

        captured = capsys.readouterr()
        output = captured.out

        assert "<h2>File: bad_file.zip</h2>" in output
        assert "<p>Invalid or empty file.</p>" in output
        assert "</div>" in output


def test_show_info_markdown_error_rendering(capsys, mock_logger, default_settings):
    """Test that errors are correctly rendered in Markdown format in show_info."""
    md_settings = replace(default_settings, format="markdown")

    with patch("pyqwk.core.load_data") as mock_load:
        mock_load.return_value = (bytearray(b"short"), {})

        show_info(["bad_file.zip"], md_settings, mock_logger)

        captured = capsys.readouterr()
        output = captured.out

        assert "## File: bad_file.zip" in output
        assert "Invalid or empty file." in output


def test_show_info_location_rendering(capsys, mock_logger, default_settings):
    """Test that BBS location is rendered in HTML and Markdown formats."""
    bbs_info = BBSInfo(
        name="Test BBS",
        sysop="Sysop",
        location="Test Location",
        bbs_id="TEST",
        packet_at="2023-01-01",
    )

    mock_board_dict = MagicMock()
    mock_board_dict.bbs_info = bbs_info
    mock_board_dict.get.return_value = "Test Conf"

    # Test HTML
    html_settings = replace(default_settings, format="html")
    with patch("pyqwk.core.load_data", return_value=([], mock_board_dict)):
        show_info(["test.zip"], html_settings, mock_logger)
        output = capsys.readouterr().out
        assert "<strong>Location:</strong> Test Location" in output

    # Test Markdown
    md_settings = replace(default_settings, format="markdown")
    with patch("pyqwk.core.load_data", return_value=([], mock_board_dict)):
        show_info(["test.zip"], md_settings, mock_logger)
        output = capsys.readouterr().out
        assert "**Location:** Test Location" in output


def test_show_info_my_name_propagation(capsys, mock_logger, default_settings):
    """Test that settings.my_name is correctly propagated to bbs_info in show_info."""
    my_name = "Agent Jules"
    settings = replace(default_settings, my_name=my_name, format="json")

    bbs_info = BBSInfo(
        name="Test BBS",
        sysop="Sysop",
        location="Test Location",
        bbs_id="TEST",
        packet_at="2023-01-01",
    )

    mock_board_dict = MagicMock()
    mock_board_dict.bbs_info = bbs_info

    with patch("pyqwk.core.load_data", return_value=([], mock_board_dict)):
        show_info(["test.zip"], settings, mock_logger)

        output = capsys.readouterr().out
        import json
        data = json.loads(output)

        assert data[0]["bbs_info"]["user_name"] == my_name
