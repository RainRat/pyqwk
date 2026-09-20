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
    show_list_keywords,
    render_keywords_as_text,
    _render_keywords_html,
    _render_keywords_markdown,
    _render_keywords_csv,
)
from pyqwk.cli import main


@pytest.fixture
def mock_keyword_data(message_factory):
    m1 = message_factory(1, 0, "Python Programming", confnum=1)
    m1.text = "Python is a great programming language for developers and software projects."
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Python Discussion", confnum=1)
    m2.text = "Python programming has many great libraries for software developers."
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Hardware Talk", confnum=2)
    m3.text = "Discussing modern computer hardware and retro vintage systems."
    m3.header.msgfrom = "Alice"
    m3.header.msgto = "Bob"
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_keywords_formats():
    keyword_list = [
        {
            "keyword": "programming",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "keyword": "python",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_keywords_as_text(keyword_list, use_colors=False)
    assert "Extracted Keywords" in text_out
    assert "programming" in text_out
    assert "python" in text_out
    assert "Total Keywords: 2" in text_out

    # Text format with colors
    text_color_out = render_keywords_as_text(keyword_list, use_colors=True)
    assert "Extracted Keywords" in text_color_out
    assert "Total Keywords: 2" in text_color_out

    # HTML format
    html_out = _render_keywords_html(keyword_list, "Test Keywords")
    assert "<h1>Test Keywords</h1>" in html_out
    assert "<td>python</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_keywords_markdown(keyword_list, "Test Keywords")
    assert "# Test Keywords" in md_out
    assert "| Keyword | Messages | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| python | 5 | 1 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_keywords_csv(keyword_list)
    assert "keyword,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "python,5,1,,," in csv_out


def test_show_list_keywords_stdout(mock_keyword_data):
    msgs, board = mock_keyword_data

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

    logger = logging.getLogger("test_list_keywords")

    with patch("pyqwk.core.load_data", return_value=(msgs, board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_keywords(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            keywords_out = json.loads(output_content)

            kw_dict = {item["keyword"]: item for item in keywords_out}
            assert "programming" in kw_dict
            assert kw_dict["programming"]["message_count"] == 2
            assert kw_dict["programming"]["authors_count"] == 2
            assert kw_dict["programming"]["first_active"] == "2024-01-01"
            assert kw_dict["programming"]["last_active"] == "2024-01-02"
            assert kw_dict["programming"]["bbs_name"] == "Vintage BBS"

            assert "hardware" in kw_dict
            assert kw_dict["hardware"]["message_count"] == 1


def test_show_list_keywords_empty():
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
    logger = logging.getLogger("test_keywords_empty")

    with patch("pyqwk.core.load_data", side_effect=Exception("Load error")):
        with patch("logging.Logger.warning") as mock_warn:
            show_list_keywords(["invalid.qwk"], settings, logger)
            mock_warn.assert_called_with("No keywords found across messages.")


def test_cli_list_keywords_integration(tmp_path, mock_keyword_data):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    msgs, board = mock_keyword_data

    test_args = ["qwk.py", str(test_file), "--list-keywords", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, board)):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    kw_dict = {item["keyword"]: item for item in output}
                    assert "programming" in kw_dict


def test_show_list_keywords_all_formats(mock_keyword_data):
    msgs, board = mock_keyword_data
    logger = logging.getLogger("test_keywords_all_formats")

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
                show_list_keywords(["dummy.qwk"], settings, logger)
                mock_write.assert_called_once()
                out = mock_write.call_args[0][0]
                assert "programming" in out
