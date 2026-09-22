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
    m1 = message_factory(1, 0, "Vintage BBS Computing", confnum=1)
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "Bob"
    m1.text = "Welcome to vintage computing! Vintage computers are super cool and retro."
    m1.datetime = datetime.datetime(2024, 1, 1, 10, 0)

    m2 = message_factory(2, 0, "Retro Hardware", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.text = "I love vintage computing systems and retro hardware."
    m2.datetime = datetime.datetime(2024, 1, 2, 11, 0)

    m3 = message_factory(3, 0, "Off Topic", confnum=2)
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "David"
    m3.text = "the and for with this 123 4567"
    m3.datetime = datetime.datetime(2024, 1, 5, 15, 0)

    board = ConferenceMap({1: "General", 2: "Tech"})
    board.bbs_info = BBSInfo(name="Vintage BBS", bbs_id="VINTAGE", user_name="Alice")

    return [m1, m2, m3], board


def test_render_keywords_formats():
    keyword_list = [
        {
            "keyword": "computing-and-vintage-retro-systems",
            "frequency": 10,
            "authors_count": 3,
            "first_active": "2024-01-01",
            "last_active": "2024-01-10",
            "bbs_name": "Vintage BBS Very Long BBS Name",
        },
        {
            "keyword": "vintage",
            "frequency": 5,
            "authors_count": 2,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    # Text format without colors
    text_out = render_keywords_as_text(keyword_list, use_colors=False)
    assert "Extracted Keywords" in text_out
    assert "computing-and-vintag..." in text_out
    assert "vintage" in text_out
    assert "Total Keywords: 2" in text_out

    # Text format with colors
    text_color_out = render_keywords_as_text(keyword_list, use_colors=True)
    assert "Extracted Keywords" in text_color_out
    assert "Total Keywords: 2" in text_color_out

    # HTML format
    html_out = _render_keywords_html(keyword_list, "Test Keywords")
    assert "<h1>Test Keywords</h1>" in html_out
    assert "<td>vintage</td>" in html_out
    assert "<td>N/A</td>" in html_out

    # Markdown format
    md_out = _render_keywords_markdown(keyword_list, "Test Keywords")
    assert "# Test Keywords" in md_out
    assert "| Keyword | Frequency | Authors | First Active | Last Active | BBS Name |" in md_out
    assert "| vintage | 5 | 2 | N/A | N/A | Unknown |" in md_out

    # CSV format
    csv_out = _render_keywords_csv(keyword_list)
    assert "keyword,frequency,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "vintage,5,2,,," in csv_out


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

            assert len(keywords_out) > 0
            # Top keyword: "vintage" (3 times: m1 x2, m2 x1) or "computing" (2 times)
            top_kw = keywords_out[0]
            assert top_kw["keyword"] in ("vintage", "computing")
            assert top_kw["frequency"] >= 2
            assert top_kw["authors_count"] >= 1
            assert top_kw["first_active"] == "2024-01-01"


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
                    assert len(output) > 0


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
                assert "vintage" in out or "computing" in out


def test_show_list_keywords_raw_bytes(message_factory):
    m = message_factory(1, 0, "Subj")
    m.text = "Retro computing is awesome."
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
    logger = logging.getLogger("test_keywords_bytes")

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
                show_list_keywords(
                    ["short.qwk", "long.qwk", "valid.json"], settings, logger
                )
                mock_write.assert_called_once()


def test_show_list_keywords_edge_cases(message_factory):
    m_excluded = message_factory(1, 0, "Subj 1", confnum=99)
    m_excluded.text = "secret confidential data"

    m1 = message_factory(2, 0, "Subj 2", confnum=1)
    m1.header.msgfrom = "   "
    m1.datetime = None
    m1.header.msgdate = "01-01-20"
    m1.header.msgtime = "10:00"
    m1.text = "telecommunication systems"
    m1.bbs_name = None
    m1.bbs_id = "SYS_BBS_1"

    m2 = message_factory(3, 0, "Subj 3", confnum=1)
    m2.header.msgfrom = "Bob"
    m2.datetime = None
    m2.header.msgdate = "01-02-20"
    m2.header.msgtime = "12:00"
    m2.text = "telecommunication software"
    m2.bbs_name = "Main BBS"
    m2.bbs_id = "SYS_BBS_1"

    board = ConferenceMap({1: "General", 99: "Excluded"})

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
        exclude_conferences=["99"],
    )
    logger = logging.getLogger("test_keywords_branches")

    with patch("pyqwk.core.load_data", return_value=([m_excluded, m1, m2], board)):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_list_keywords(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            out = json.loads(mock_write.call_args[0][0])
            kw_entry = [x for x in out if x["keyword"] == "telecommunication"][0]
            assert kw_entry["frequency"] == 2
            assert kw_entry["authors_count"] == 1
            assert kw_entry["first_active"] == "2020-01-01"
            assert kw_entry["last_active"] == "2020-01-02"
            assert "Main BBS" in kw_entry["bbs_name"]
