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
    show_list_msg_links,
    render_msg_links_as_text,
    _render_msg_links_html,
    _render_msg_links_markdown,
    _render_msg_links_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_msg_link_data(message_factory):
    m1 = message_factory(1, 0, "Subj 1", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.text = "Check out msg #42 and message 100 for details."
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Subj 2", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.text = "Regarding MSG #42, it was great!"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Subj 3", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "David"
    m3.text = "No message links here at all."
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_msg_links_formats():
    msg_link_list = [
        {
            "msg_link": "msg #42",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "msg_link": "message 100",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_msg_links_as_text(msg_link_list, use_colors=False)
    assert "Extracted Message Links" in text_out
    assert "msg #42" in text_out
    assert "message 100" in text_out
    assert "Total Message Links: 2" in text_out

    # Text format with colors
    text_color_out = render_msg_links_as_text(msg_link_list, use_colors=True)
    assert "Extracted Message Links" in text_color_out
    assert "Total Message Links: 2" in text_color_out

    # HTML format
    html_out = _render_msg_links_html(msg_link_list, "Test Message Links")
    assert "<h1>Test Message Links</h1>" in html_out
    assert "<td>message 100</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_msg_links_markdown(msg_link_list, "Test Message Links")
    assert "# Test Message Links" in md_out
    assert "| Message Link | Messages | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| message 100 | 5 | 1 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_msg_links_csv(msg_link_list)
    assert "msg_link,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "message 100,5,1,,," in csv_out


def test_show_list_msg_links_stdout(mock_msg_link_data):
    msgs, board = mock_msg_link_data

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

    logger = logging.getLogger("test_list_msg_links")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_msg_links(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            links_out = json.loads(output_content)

            assert len(links_out) == 2
            # Sorted by count descending: "msg #42" (2 msgs, 2 authors, 2024-01-01..2024-01-02), "message 100" (1 msg, 1 author)
            assert links_out[0]["msg_link"].lower() == "msg #42"
            assert links_out[0]["message_count"] == 2
            assert links_out[0]["authors_count"] == 2
            assert links_out[0]["first_active"] == "2024-01-01"
            assert links_out[0]["last_active"] == "2024-01-02"
            assert links_out[0]["bbs_name"] == "Vintage BBS"

            assert links_out[1]["msg_link"].lower() == "message 100"
            assert links_out[1]["message_count"] == 1
            assert links_out[1]["authors_count"] == 1


def test_show_list_msg_links_empty():
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
    logger = logging.getLogger("test_msg_links_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_msg_links(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No message links found across messages.")


def test_cli_list_msg_links_integration(tmp_path, mock_msg_link_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_msg_link_data

    for flag in ["--list-msg-links", "--list-message-links"]:
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
                        assert output[0]["msg_link"].lower() == "msg #42"
                        assert output[0]["message_count"] == 2


def test_show_list_msg_links_all_formats(mock_msg_link_data):
    msgs, board = mock_msg_link_data
    logger = logging.getLogger("test_msg_links_all_formats")

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
                show_list_msg_links(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "msg #42" in out or "MSG #42" in out


def test_show_list_msg_links_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    m.text = "See MSG 789 for details."
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
    logger = logging.getLogger("test_msg_links_bytes")

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
                show_list_msg_links(
                    ["short.qwk", "long.qwk", "valid.json"], settings, logger
                )
                mock_write.assert_called_once()


def test_show_list_msg_links_edge_cases(message_factory):
    m1 = message_factory(1, 0, "Subj 1")
    m1.header.msgdate = "INVALID-DATE"
    m1.header.msgtime = "INVALID-TIME"
    m1.datetime = None
    m1.text = "Check msg #99 and   "
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
    logger = logging.getLogger("test_msg_links_edge_cases")

    with patch("pyqwk.core.load_data", return_value=([m1], board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            with patch("pyqwk.core._parse_qwk_date", return_value=None):
                show_list_msg_links(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = json.loads(mock_write.call_args[0][0])
                assert len(out) == 1
                assert out[0]["msg_link"] == "msg #99"
                assert out[0]["first_active"] is None
                assert out[0]["last_active"] is None
                assert out[0]["bbs_name"] == "Unknown"
