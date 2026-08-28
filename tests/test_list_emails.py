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
    show_list_emails,
    render_emails_as_text,
    _render_emails_html,
    _render_emails_markdown,
    _render_emails_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_email_data(message_factory):
    m1 = message_factory(1, 0, "Subj 1", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.text = "Contact me at alice@example.com or support@bbs.org"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Subj 2", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.text = "Here is alice@example.com again!"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Subj 3", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "David"
    m3.text = "No email addresses here at all."
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_emails_formats():
    email_list = [
        {
            "email": "extremely-long-email-address-for-testing@example-domain.com",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "email": "user@bbs.org",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_emails_as_text(email_list, use_colors=False)
    assert "Extracted Emails" in text_out
    assert "extremely-long-email-address-for-testing..." in text_out
    assert "user@bbs.org" in text_out
    assert "Total Emails: 2" in text_out

    # Text format with colors
    text_color_out = render_emails_as_text(email_list, use_colors=True)
    assert "Extracted Emails" in text_color_out
    assert "Total Emails: 2" in text_color_out

    # HTML format
    html_out = _render_emails_html(email_list, "Test Emails")
    assert "<h1>Test Emails</h1>" in html_out
    assert "<td>user@bbs.org</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_emails_markdown(email_list, "Test Emails")
    assert "# Test Emails" in md_out
    assert "| Email | Messages | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| user@bbs.org | 5 | 1 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_emails_csv(email_list)
    assert "email,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "user@bbs.org,5,1,,," in csv_out


def test_show_list_emails_stdout(mock_email_data):
    msgs, board = mock_email_data

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

    logger = logging.getLogger("test_list_emails")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_emails(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            emails_out = json.loads(output_content)

            assert len(emails_out) == 2
            # Sorted by count descending: "alice@example.com" (2 msgs, 2 authors), "support@bbs.org" (1 msg, 1 author)
            assert emails_out[0]["email"] == "alice@example.com"
            assert emails_out[0]["message_count"] == 2
            assert emails_out[0]["authors_count"] == 2
            assert emails_out[0]["first_active"] == "2024-01-01"
            assert emails_out[0]["last_active"] == "2024-01-02"
            assert emails_out[0]["bbs_name"] == "Vintage BBS"

            assert emails_out[1]["email"] == "support@bbs.org"
            assert emails_out[1]["message_count"] == 1
            assert emails_out[1]["authors_count"] == 1


def test_show_list_emails_empty():
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
    logger = logging.getLogger("test_emails_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_emails(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No email addresses found across messages.")


def test_cli_list_emails_integration(tmp_path, mock_email_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_email_data

    test_args = ["qwk.py", str(test_file), "--list-emails", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["email"] == "alice@example.com"
                    assert output[0]["message_count"] == 2


def test_show_list_emails_all_formats(mock_email_data):
    msgs, board = mock_email_data
    logger = logging.getLogger("test_emails_all_formats")

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

        with patch("pyqwk.core.load_data", return_value=(msgs, board)):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_emails(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "alice@example.com" in out


def test_show_list_emails_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    m.text = "Write to user@example.org for details."
    board_map = ConferenceMap()

    settings = ProcessingSettings(
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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_emails_bytes")

    short_bytes = b"short"
    long_bytes = bytearray(256)

    def mock_load(path, logger_arg, enc):
        if path == "short.qwk":
            return short_bytes, board_map
        if path == "long.qwk":
            return long_bytes, board_map
        return [m], board_map

    with patch("pyqwk.core.load_data", side_effect=mock_load):
        with patch("pyqwk.core.parse_messages", return_value=[m]):
            with patch("pyqwk.core._write_text_output") as mock_write:
                show_list_emails(
                    ["short.qwk", "long.qwk", "valid.json"], settings, logger
                )
                mock_write.assert_called_once()
