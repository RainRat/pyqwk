import pytest
import json
import io
import logging
import datetime
from unittest.mock import patch

from pyqwk.core import (
    ConferenceMap,
    BBSInfo,
    ProcessingSettings,
    show_list_bbs,
    render_bbs_as_text,
    _render_bbs_html,
    _render_bbs_markdown,
    _render_bbs_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_bbs_data(message_factory):
    m1 = message_factory(1, 0, "Hello World", confnum=1)
    m1.header.msgdate = "01-01-24"
    m1.header.msgtime = "10:00"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Re: Hello World", confnum=1)
    m2.header.msgdate = "01-02-24"
    m2.header.msgtime = "11:00"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Another post", confnum=2)
    m3.header.msgdate = "01-05-24"
    m3.header.msgtime = "15:00"
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(
        name="Vintage BBS",
        bbs_id="VINTAGE",
        sysop="Sysop Joe",
        location="Seattle, WA",
    )

    return [m1, m2, m3], board


def test_render_bbs_formats():
    bbs_list = [
        {
            "bbs_name": "The Digital Horizon Bulletin Board System",
            "bbs_id": "DIGIHORIZON",
            "sysop": "Sysop Alexander",
            "location": "San Francisco, CA",
            "conference_count": 5,
            "message_count": 120,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
        },
        {
            "bbs_name": "Telegard",
            "bbs_id": None,
            "sysop": None,
            "location": None,
            "conference_count": 1,
            "message_count": 2,
            "first_active": None,
            "last_active": None,
        },
    ]

    # Text format without colors
    text_out = render_bbs_as_text(bbs_list, use_colors=False)
    assert "Bulletin Board Systems" in text_out
    assert "The Digital Horizon ..." in text_out
    assert "DIGIHORI" in text_out
    assert "Sysop Alex..." in text_out
    assert "Telegard" in text_out
    assert "Total BBSes: 2" in text_out

    # Text format with colors
    text_color_out = render_bbs_as_text(bbs_list, use_colors=True)
    assert "Bulletin Board Systems" in text_color_out
    assert "Total BBSes: 2" in text_color_out

    # HTML format
    html_out = _render_bbs_html(bbs_list, "Test BBS List")
    assert "<h1>Test BBS List</h1>" in html_out
    assert "<td>Telegard</td>" in html_out
    assert "<td>San Francisco, CA</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_bbs_markdown(bbs_list, "Test BBS List")
    assert "# Test BBS List" in md_out
    assert "| BBS Name | BBS ID | Sysop | Location | Conferences | Messages | First Active | Last Active |" in md_out
    assert "| Telegard | N/A | N/A | N/A | 1 | 2 | N/A | N/A |" in md_out

    # CSV format
    csv_out = _render_bbs_csv(bbs_list)
    assert "bbs_name,bbs_id,sysop,location,conference_count,message_count,first_active,last_active" in csv_out
    assert "Telegard,,,,1,2,," in csv_out


def test_show_list_bbs_stdout(mock_bbs_data):
    msgs, board = mock_bbs_data

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

    logger = logging.getLogger("test_list_bbs")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_bbs(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            bbs_out = json.loads(output_content)

            assert len(bbs_out) == 1
            assert bbs_out[0]["bbs_name"] == "Vintage BBS"
            assert bbs_out[0]["bbs_id"] == "VINTAGE"
            assert bbs_out[0]["sysop"] == "Sysop Joe"
            assert bbs_out[0]["location"] == "Seattle, WA"
            assert bbs_out[0]["conference_count"] == 2
            assert bbs_out[0]["message_count"] == 3
            assert bbs_out[0]["first_active"] == "2024-01-01"
            assert bbs_out[0]["last_active"] == "2024-01-05"


def test_show_list_bbs_other_formats(mock_bbs_data):
    msgs, board = mock_bbs_data

    for fmt in ["html", "markdown", "csv", "text"]:
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
            format=fmt,
            separator="none",
            output_mode="stdout",
            output_path=None,
            encoding="cp437",
            quiet=True,
        )

        logger = logging.getLogger("test_list_bbs_formats")

        with patch("pyqwk.core.load_data", return_value=(msgs, board)):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_bbs(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()


def test_show_list_bbs_empty():
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
    logger = logging.getLogger("test_bbs_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_bbs(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No Bulletin Board Systems found.")


def test_show_list_bbs_fallback_date_parsing(message_factory):
    m1 = message_factory(1, 0, "Test Date Fallback", confnum=1)
    m1.header.msgdate = "05-10-23"
    m1.header.msgtime = "12:30"
    m1.datetime = None  # Remove explicit datetime attribute to force _parse_qwk_date fallback

    board = ConferenceMap({1: "General"})
    board.bbs_info = BBSInfo(name="Fallback BBS", bbs_id="FALLBACK")

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
    logger = logging.getLogger("test_bbs_date_fallback")

    with patch("pyqwk.core.load_data", return_value=([m1], board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_bbs(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            bbs_out = json.loads(mock_write.call_args[0][0])
            assert bbs_out[0]["first_active"] == "2023-05-10"
            assert bbs_out[0]["last_active"] == "2023-05-10"


def test_cli_list_bbs_integration(tmp_path, mock_bbs_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_bbs_data

    test_args = ["qwk.py", str(test_file), "--list-bbs", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 1
                    assert output[0]["bbs_name"] == "Vintage BBS"
                    assert output[0]["message_count"] == 3
