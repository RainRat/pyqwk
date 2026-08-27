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
    show_list_urls,
    render_urls_as_text,
    _render_urls_html,
    _render_urls_markdown,
    _render_urls_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_url_data(message_factory):
    m1 = message_factory(1, 0, "Subj 1", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.text = "Check out https://example.com/item and http://bbs.org/info"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Subj 2", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.text = "Here is https://example.com/item again!"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Subj 3", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "David"
    m3.text = "No links here at all."
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_urls_formats():
    url_list = [
        {
            "url": "https://extremely-long-domain-name-and-path.example.com/very/long/url/path",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "url": "http://bbs.org",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_urls_as_text(url_list, use_colors=False)
    assert "Extracted URLs" in text_out
    assert "https://extremely-long-domain-name-and-p..." in text_out
    assert "http://bbs.org" in text_out
    assert "Total URLs: 2" in text_out

    # Text format with colors
    text_color_out = render_urls_as_text(url_list, use_colors=True)
    assert "Extracted URLs" in text_color_out
    assert "Total URLs: 2" in text_color_out

    # HTML format
    html_out = _render_urls_html(url_list, "Test URLs")
    assert "<h1>Test URLs</h1>" in html_out
    assert "<td>http://bbs.org</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_urls_markdown(url_list, "Test URLs")
    assert "# Test URLs" in md_out
    assert "| URL | Messages | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| http://bbs.org | 5 | 1 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_urls_csv(url_list)
    assert "url,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "http://bbs.org,5,1,,," in csv_out


def test_show_list_urls_stdout(mock_url_data):
    msgs, board = mock_url_data

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

    logger = logging.getLogger("test_list_urls")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_urls(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            urls_out = json.loads(output_content)

            assert len(urls_out) == 2
            # Sorted by count descending: "https://example.com/item" (2 msgs, 2 authors), "http://bbs.org/info" (1 msg, 1 author)
            assert urls_out[0]["url"] == "https://example.com/item"
            assert urls_out[0]["message_count"] == 2
            assert urls_out[0]["authors_count"] == 2
            assert urls_out[0]["first_active"] == "2024-01-01"
            assert urls_out[0]["last_active"] == "2024-01-02"
            assert urls_out[0]["bbs_name"] == "Vintage BBS"

            assert urls_out[1]["url"] == "http://bbs.org/info"
            assert urls_out[1]["message_count"] == 1
            assert urls_out[1]["authors_count"] == 1


def test_show_list_urls_empty():
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
    logger = logging.getLogger("test_urls_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_urls(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No URLs found across messages.")


def test_cli_list_urls_integration(tmp_path, mock_url_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_url_data

    test_args = ["qwk.py", str(test_file), "--list-urls", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["url"] == "https://example.com/item"
                    assert output[0]["message_count"] == 2


def test_show_list_urls_all_formats(mock_url_data):
    msgs, board = mock_url_data
    logger = logging.getLogger("test_urls_all_formats")

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
                show_list_urls(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "https://example.com/item" in out


def test_show_list_urls_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    m.text = "Visit http://example.org for details."
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
    logger = logging.getLogger("test_urls_bytes")

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
                show_list_urls(
                    ["short.qwk", "long.qwk", "valid.json"], settings, logger
                )
                mock_write.assert_called_once()
