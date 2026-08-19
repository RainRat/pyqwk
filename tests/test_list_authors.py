import pytest
import sys
import json
import csv
import io
import logging
import datetime
from unittest.mock import patch, MagicMock

from pyqwk.core import (
    ConferenceMap,
    BBSInfo,
    ParsedMessage,
    ProcessingSettings,
    show_list_authors,
    render_authors_as_text,
    _render_authors_html,
    _render_authors_markdown,
    _render_authors_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_author_data(message_factory):
    m1 = message_factory(1, 0, "Hello World", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Re: Hello World", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Another post", confnum=2)
    m3.header.msgfrom = "Alice"
    m3.header.msgto = "Bob"
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_authors_formats():
    author_list = [
        {
            "author": "Alice Extremely Long Author Name Truncated",
            "message_count": 10,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "author": "Bob",
            "message_count": 5,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_authors_as_text(author_list, use_colors=False)
    assert "Message Authors" in text_out
    assert "Alice Extremely Long Auth..." in text_out
    assert "Bob" in text_out
    assert "Total Authors: 2" in text_out

    # Text format with colors
    text_color_out = render_authors_as_text(author_list, use_colors=True)
    assert "Message Authors" in text_color_out
    assert "Total Authors: 2" in text_color_out

    # HTML format
    html_out = _render_authors_html(author_list, "Test Authors")
    assert "<h1>Test Authors</h1>" in html_out
    assert "<td>Bob</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_authors_markdown(author_list, "Test Authors")
    assert "# Test Authors" in md_out
    assert "| Author | Messages | First Active | Last Active | BBS Name |" in md_out
    assert "| Bob | 5 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_authors_csv(author_list)
    assert "author,message_count,first_active,last_active,bbs_name" in csv_out
    assert "Bob,5,,," in csv_out


def test_show_list_authors_stdout(mock_author_data):
    msgs, board = mock_author_data

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

    logger = logging.getLogger("test_list_authors")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_authors(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            authors_out = json.loads(output_content)

            assert len(authors_out) == 2
            # Sorted by count descending: Alice (2), Bob (1)
            assert authors_out[0]["author"] == "Alice"
            assert authors_out[0]["message_count"] == 2
            assert authors_out[0]["first_active"] == "2024-01-01"
            assert authors_out[0]["last_active"] == "2024-01-05"
            assert authors_out[0]["bbs_name"] == "Vintage BBS"

            assert authors_out[1]["author"] == "Bob"
            assert authors_out[1]["message_count"] == 1


def test_show_list_authors_empty():
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
    logger = logging.getLogger("test_authors_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_authors(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No message authors found.")


def test_cli_list_authors_integration(tmp_path, mock_author_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_author_data

    test_args = ["qwk.py", str(test_file), "--list-authors", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 2
                    assert output[0]["author"] == "Alice"
                    assert output[0]["message_count"] == 2
