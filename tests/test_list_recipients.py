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
    show_list_recipients,
    render_recipients_as_text,
    _render_recipients_html,
    _render_recipients_markdown,
    _render_recipients_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_recipient_data(message_factory):
    m1 = message_factory(1, 0, "Hello World", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Re: Hello World", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Another post", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "Bob"
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_recipients_formats():
    recipient_list = [
        {
            "recipient": "Bob Extremely Long Recipient Name Truncated",
            "message_count": 10,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "recipient": "Alice",
            "message_count": 5,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_recipients_as_text(recipient_list, use_colors=False)
    assert "Message Recipients" in text_out
    assert "Bob Extremely Long Recipi..." in text_out
    assert "Alice" in text_out
    assert "Total Recipients: 2" in text_out

    # Text format with colors
    text_color_out = render_recipients_as_text(recipient_list, use_colors=True)
    assert "Message Recipients" in text_color_out
    assert "Total Recipients: 2" in text_color_out

    # HTML format
    html_out = _render_recipients_html(recipient_list, "Test Recipients")
    assert "<h1>Test Recipients</h1>" in html_out
    assert "<td>Alice</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_recipients_markdown(recipient_list, "Test Recipients")
    assert "# Test Recipients" in md_out
    assert "| Recipient | Messages | First Active | Last Active | BBS Name |" in md_out
    assert "| Alice | 5 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_recipients_csv(recipient_list)
    assert "recipient,message_count,first_active,last_active,bbs_name" in csv_out
    assert "Alice,5,,," in csv_out


def test_show_list_recipients_stdout(mock_recipient_data):
    msgs, board = mock_recipient_data

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

    logger = logging.getLogger("test_list_recipients")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_recipients(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            recipients_out = json.loads(output_content)

            assert len(recipients_out) == 2
            # Sorted by count descending: Bob (2), Alice (1)
            assert recipients_out[0]["recipient"] == "Bob"
            assert recipients_out[0]["message_count"] == 2
            assert recipients_out[0]["first_active"] == "2024-01-01"
            assert recipients_out[0]["last_active"] == "2024-01-05"
            assert recipients_out[0]["bbs_name"] == "Vintage BBS"

            assert recipients_out[1]["recipient"] == "Alice"
            assert recipients_out[1]["message_count"] == 1


def test_show_list_recipients_empty():
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
    logger = logging.getLogger("test_recipients_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_recipients(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No message recipients found.")


@pytest.mark.parametrize("flag", ["--list-recipients", "--list-to"])
def test_cli_list_recipients_integration(tmp_path, mock_recipient_data, flag):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_recipient_data

    test_args = ["qwk.py", str(test_file), flag, "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["recipient"] == "Bob"
                    assert output[0]["message_count"] == 2


def test_show_list_recipients_real_parsed_message(message_factory):
    m1 = message_factory(1, 0, "Real Parsed Message", confnum=1)
    m1.header.msgto = "David"
    m1.header.msgdate = "01-01-24"
    m1.header.msgtime = "12:00"

    board = ConferenceMap({1: "General"})
    board.bbs_info = BBSInfo(name="Test BBS")
    logger = logging.getLogger("test_real_msg")

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

        with patch("pyqwk.core.load_data", return_value=([m1], board)):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_recipients(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "David" in out
