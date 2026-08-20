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
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.header.msgdate = "01-01-24"
    m1.header.msgtime = "10:00"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)
    m1.bbs_name = "Vintage BBS System Name Very Long Truncated"
    m1.bbs_id = "VINTAGE1"

    m2 = message_factory(2, 0, "Re: Hello World", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.header.msgdate = "01-02-24"
    m2.header.msgtime = "11:00"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)
    m2.bbs_name = "Vintage BBS System Name Very Long Truncated"
    m2.bbs_id = "VINTAGE1"

    m3 = message_factory(3, 0, "Another post", confnum=2)
    m3.header.msgfrom = "Alice"
    m3.header.msgto = "Bob"
    m3.header.msgdate = "01-05-24"
    m3.header.msgtime = "15:00"
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)
    m3.bbs_name = "RetroNet BBS"
    m3.bbs_id = "RETRONET"

    board1 = ConferenceMap({1: "General", 2: "Tech"})
    board1.bbs_info = BBSInfo(
        name="Vintage BBS System Name Very Long Truncated",
        bbs_id="VINTAGE1",
        sysop="Sysop John",
        location="New York, NY",
        user_name="Alice",
    )

    board2 = ConferenceMap({2: "Tech"})
    board2.bbs_info = BBSInfo(
        name="RetroNet BBS",
        bbs_id="RETRONET",
        sysop="Sysop Jane",
        location="Seattle, WA",
        user_name="Alice",
    )

    return [(m1, m2), board1], [(m3,), board2]


def test_render_bbs_formats():
    bbs_list = [
        {
            "bbs_name": "Vintage BBS System Name Very Long Truncated",
            "bbs_id": "VINTAGE123",
            "sysop": "Sysop John",
            "location": "New York, NY",
            "conference_count": 5,
            "message_count": 42,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
        },
        {
            "bbs_name": "RetroNet BBS",
            "bbs_id": None,
            "sysop": None,
            "location": None,
            "conference_count": 2,
            "message_count": 10,
            "first_active": None,
            "last_active": None,
        },
    ]

    # Text format without colors
    text_out = render_bbs_as_text(bbs_list, use_colors=False)
    assert "Bulletin Board Systems (BBS)" in text_out
    assert "Vintage BBS System Name..." in text_out
    assert "RetroNet BBS" in text_out
    assert "Total BBS Systems: 2" in text_out

    # Text format with colors
    text_color_out = render_bbs_as_text(bbs_list, use_colors=True)
    assert "Bulletin Board Systems (BBS)" in text_color_out
    assert "Total BBS Systems: 2" in text_color_out

    # HTML format
    html_out = _render_bbs_html(bbs_list, "Test BBS List")
    assert "<h1>Test BBS List</h1>" in html_out
    assert "<td>Vintage BBS System Name Very Long Truncated</td>" in html_out
    assert "<td>RetroNet BBS</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_bbs_markdown(bbs_list, "Test BBS List")
    assert "# Test BBS List" in md_out
    assert "| BBS Name | ID | Sysop | Location | Conferences | Messages | First Active | Last Active |" in md_out
    assert "| RetroNet BBS | N/A | N/A | N/A | 2 | 10 | N/A | N/A |" in md_out

    # CSV format
    csv_out = _render_bbs_csv(bbs_list)
    assert "bbs_name,bbs_id,sysop,location,conference_count,message_count,first_active,last_active" in csv_out
    assert "RetroNet BBS,,,,2,10,," in csv_out


def test_show_list_bbs_stdout(mock_bbs_data):
    (msgs1, board1), (msgs2, board2) = mock_bbs_data

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

    def mock_load(path, log, enc):
        if "1" in path:
            return list(msgs1), board1
        return list(msgs2), board2

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_bbs(["archive1.qwk", "archive2.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            bbs_out = json.loads(output_content)

            assert len(bbs_out) == 2
            # Sorted by count descending: Vintage BBS (2 msgs), RetroNet BBS (1 msg)
            assert bbs_out[0]["bbs_name"] == "Vintage BBS System Name Very Long Truncated"
            assert bbs_out[0]["bbs_id"] == "VINTAGE1"
            assert bbs_out[0]["message_count"] == 2
            assert bbs_out[0]["conference_count"] == 1
            assert bbs_out[0]["sysop"] == "Sysop John"
            assert bbs_out[0]["first_active"] == "2024-01-01"
            assert bbs_out[0]["last_active"] == "2024-01-02"

            assert bbs_out[1]["bbs_name"] == "RetroNet BBS"
            assert bbs_out[1]["message_count"] == 1


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
            mock_warn.assert_called_with("No BBS entries found.")


def test_cli_list_bbs_integration(tmp_path, mock_bbs_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    (msgs1, board1), _ = mock_bbs_data

    test_args = ["qwk.py", str(test_file), "--list-bbs", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(list(msgs1), board1)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 1
                    assert output[0]["bbs_name"] == "Vintage BBS System Name Very Long Truncated"
                    assert output[0]["message_count"] == 2
