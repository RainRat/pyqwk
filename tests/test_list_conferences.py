import pytest
import sys
import json
import csv
import io
import logging
from unittest.mock import patch, MagicMock

from pyqwk.core import (
    ConferenceMap,
    BBSInfo,
    ParsedMessage,
    ProcessingSettings,
    show_list_conferences,
    render_conferences_as_text,
    _render_conferences_html,
    _render_conferences_markdown,
    _render_conferences_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_conference_data(message_factory):
    m1 = message_factory(1, 0, "General Post", confnum=1)
    m2 = message_factory(2, 0, "Tech Post 1", confnum=2)
    m3 = message_factory(3, 0, "Tech Post 2", confnum=2)

    board = ConferenceMap({1: "General Discussion", 2: "Tech Talk Very Long Conference Area Name That Will Be Truncated"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Sysop")

    return [m1, m2, m3], board


def test_render_conferences_formats():
    conf_list = [
        {
            "number": 1,
            "name": "General Discussion",
            "message_count": 10,
            "bbs_name": "Vintage BBS",
        },
        {
            "number": 2,
            "name": "Tech Talk",
            "message_count": 25,
            "bbs_name": "Telegard BBS",
        },
    ]

    # Text format without colors
    text_out = render_conferences_as_text(conf_list, use_colors=False)
    assert "Conference Areas" in text_out
    assert "General Discussion" in text_out
    assert "Vintage BBS" in text_out
    assert "Total Conferences: 2" in text_out

    # Text format with colors
    text_color_out = render_conferences_as_text(conf_list, use_colors=True)
    assert "Conference Areas" in text_color_out
    assert "Total Conferences: 2" in text_color_out

    # HTML format
    html_out = _render_conferences_html(conf_list, "Test Title")
    assert "<h1>Test Title</h1>" in html_out
    assert "<td>General Discussion</td>" in html_out
    assert "<td>Vintage BBS</td>" in html_out

    # Markdown format
    md_out = _render_conferences_markdown(conf_list, "Test Title")
    assert "# Test Title" in md_out
    assert "| # | Conference Name | Messages | BBS Name |" in md_out
    assert "| 1 | General Discussion | 10 | Vintage BBS |" in md_out

    # CSV format
    csv_out = _render_conferences_csv(conf_list)
    assert "number,name,message_count,bbs_name" in csv_out
    assert "1,General Discussion,10,Vintage BBS" in csv_out


def test_show_list_conferences_stdout(mock_conference_data):
    msgs, board = mock_conference_data

    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )

    logger = logging.getLogger("test_list_conf")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_conferences(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            conf_out = json.loads(output_content)

            assert len(conf_out) == 2
            assert conf_out[0]["number"] == 1
            assert conf_out[0]["name"] == "General Discussion"
            assert conf_out[0]["message_count"] == 1
            assert conf_out[0]["bbs_name"] == "Vintage BBS"

            assert conf_out[1]["number"] == 2
            assert conf_out[1]["message_count"] == 2


def test_show_list_conferences_empty():
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_conf_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_conferences(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No conferences found.")


def test_cli_list_conferences_integration(tmp_path, mock_conference_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_conference_data

    test_args = ["qwk.py", str(test_file), "--list-conferences", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["name"] == "General Discussion"
                    assert output[0]["bbs_name"] == "Vintage BBS"
