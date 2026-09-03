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
    show_list_phones,
    render_phones_as_text,
    _render_phones_html,
    _render_phones_markdown,
    _render_phones_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_phone_data(message_factory):
    m1 = message_factory(1, 0, "Subj 1", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.text = "Call me at 555-123-4567 or BBS line 800-555-0199"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Subj 2", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.text = "My phone is 555-123-4567 as well!"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Subj 3", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "David"
    m3.text = "No phone numbers here at all."
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_phones_formats():
    phone_list = [
        {
            "phone": "+1-800-555-0199-ext-1234567890-very-long-phone-number",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "phone": "555-123-4567",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_phones_as_text(phone_list, use_colors=False)
    assert "Extracted Phone Numbers" in text_out
    assert "+1-800-555-0199-ext-1234567890-very-lon..." in text_out
    assert "555-123-4567" in text_out
    assert "Total Phone Numbers: 2" in text_out

    # Text format with colors
    text_color_out = render_phones_as_text(phone_list, use_colors=True)
    assert "Extracted Phone Numbers" in text_color_out
    assert "Total Phone Numbers: 2" in text_color_out

    # HTML format
    html_out = _render_phones_html(phone_list, "Test Phones")
    assert "<h1>Test Phones</h1>" in html_out
    assert "<td>555-123-4567</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_phones_markdown(phone_list, "Test Phones")
    assert "# Test Phones" in md_out
    assert "| Phone Number | Messages | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| 555-123-4567 | 5 | 1 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_phones_csv(phone_list)
    assert "phone,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "555-123-4567,5,1,,," in csv_out


def test_show_list_phones_stdout(mock_phone_data):
    msgs, board = mock_phone_data

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

    logger = logging.getLogger("test_list_phones")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_phones(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            phones_out = json.loads(output_content)

            assert len(phones_out) == 2
            # Sorted by count descending: "555-123-4567" (2 msgs, 2 authors), "800-555-0199" (1 msg, 1 author)
            assert phones_out[0]["phone"] == "555-123-4567"
            assert phones_out[0]["message_count"] == 2
            assert phones_out[0]["authors_count"] == 2
            assert phones_out[0]["first_active"] == "2024-01-01"
            assert phones_out[0]["last_active"] == "2024-01-02"
            assert phones_out[0]["bbs_name"] == "Vintage BBS"

            assert phones_out[1]["phone"] == "800-555-0199"
            assert phones_out[1]["message_count"] == 1
            assert phones_out[1]["authors_count"] == 1


def test_show_list_phones_empty():
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
    logger = logging.getLogger("test_phones_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_phones(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No phone numbers found across messages.")


def test_cli_list_phones_integration(tmp_path, mock_phone_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_phone_data

    test_args = ["qwk.py", str(test_file), "--list-phones", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["phone"] == "555-123-4567"
                    assert output[0]["message_count"] == 2


def test_show_list_phones_all_formats(mock_phone_data):
    msgs, board = mock_phone_data
    logger = logging.getLogger("test_phones_all_formats")

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
                show_list_phones(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "555-123-4567" in out


def test_show_list_phones_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    m.text = "Call 800-555-0199 for help."
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
    logger = logging.getLogger("test_phones_bytes")

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
                show_list_phones(
                    ["short.qwk", "long.qwk", "valid.json"], settings, logger
                )
                mock_write.assert_called_once()


def test_show_list_phones_edge_cases(message_factory):
    m1 = message_factory(1, 0, "Subj 1")
    m1.header.msgdate = "INVALID-DATE"
    m1.header.msgtime = "INVALID-TIME"
    m1.datetime = None
    m1.text = "Call 555-123-4567 and   "
    m1.bbs_name = None
    m1.bbs_id = None

    board = ConferenceMap()

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
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_phones_edge_cases")

    with patch("pyqwk.core.load_data", return_value=([m1], board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            with patch("pyqwk.core._parse_qwk_date", return_value=None):
                show_list_phones(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = json.loads(mock_write.call_args[0][0])
                assert len(out) == 1
                assert out[0]["phone"] == "555-123-4567"
                assert out[0]["first_active"] is None
                assert out[0]["last_active"] is None
                assert out[0]["bbs_name"] == "Unknown"
