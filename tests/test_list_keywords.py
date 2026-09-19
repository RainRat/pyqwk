import json
import logging
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    render_keywords_as_text,
    _render_keywords_html,
    _render_keywords_markdown,
    _render_keywords_csv,
    show_list_keywords,
)
from pyqwk.cli import main


@pytest.fixture
def base_settings():
    return ProcessingSettings(
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
        separator="auto",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
    )


def create_sample_message(
    text="Sample message text with python and qwk keywords.",
    msgnum=1,
    confnum=101,
    author="Alice",
    to="Bob",
    subject="Hello World",
    msgdate="10-12-23",
    msgtime="12:00",
    bbs_name="Test BBS",
    source_file="archive1.qwk",
):
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate=msgdate,
        msgtime=msgtime,
        msgto=to,
        msgfrom=author,
        msgsubject=subject,
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=1,
        nettag="",
    )
    return ParsedMessage(
        text=text,
        msgnum=msgnum,
        refnum=None,
        confnum=confnum,
        header=header,
        bbs_name=bbs_name,
        source_file=source_file,
    )


def test_render_keywords_functions():
    keywords = [
        {
            "keyword": "python",
            "message_count": 10,
            "authors_count": 3,
            "first_active": "2023-10-12",
            "last_active": "2023-10-15",
            "bbs_name": "Digital Horizon BBS",
        },
        {
            "keyword": "very_long_keyword_name_that_gets_truncated_for_display",
            "message_count": 5,
            "authors_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    text_colored = render_keywords_as_text(keywords, use_colors=True)
    assert "Extracted Keywords" in text_colored
    assert "python" in text_colored
    assert "Total Keywords: 2" in text_colored

    text_plain = render_keywords_as_text(keywords, use_colors=False)
    assert "=== Extracted Keywords ===" in text_plain

    empty_text = render_keywords_as_text([], use_colors=False)
    assert "No keywords found." in empty_text

    html_out = _render_keywords_html(keywords, "Extracted Keywords")
    assert "<h1>Extracted Keywords</h1>" in html_out
    assert "<td>python</td>" in html_out

    md_out = _render_keywords_markdown(keywords, "Extracted Keywords")
    assert "# Extracted Keywords" in md_out
    assert "| python | 10 | 3 | 2023-10-12 | 2023-10-15 | Digital Horizon BBS |" in md_out

    csv_out = _render_keywords_csv(keywords)
    assert "keyword,message_count,authors_count,first_active,last_active,bbs_name" in csv_out
    assert "python,10,3,2023-10-12,2023-10-15,Digital Horizon BBS" in csv_out


def test_show_list_keywords_formats(tmp_path, base_settings, mocker):
    logger = logging.getLogger("pyqwk.test")

    msg1 = create_sample_message(text="Python and QWK archive testing.", msgnum=1, author="Alice", source_file="src_a.json", bbs_name="BBS A")
    msg2 = create_sample_message(text="Python coding with QWK protocol.", msgnum=2, author="Bob", source_file="src_a.json", bbs_name="BBS A")
    msg3 = create_sample_message(text="Python programming language.", msgnum=3, author="Charlie", source_file="src_b.json", bbs_name="BBS B")

    def mock_load(path, log, enc):
        if "src_a" in path:
            return [msg1, msg2], {1: "General"}
        return [msg3], {1: "General"}

    mocker.patch("pyqwk.core.load_data", side_effect=mock_load)

    paths = [str(tmp_path / "src_a.json"), str(tmp_path / "src_b.json")]

    # 1. Plain Text stdout
    mock_stdout = mocker.patch("sys.stdout.write")
    show_list_keywords(paths, base_settings, logger)
    written_text = "".join(call[0][0] for call in mock_stdout.call_args_list)
    assert "Extracted Keywords" in written_text
    assert "python" in written_text

    # 2. JSON export
    json_path = str(tmp_path / "keywords.json")
    json_settings = base_settings
    json_settings.format = "json"
    json_settings.output_path = json_path
    show_list_keywords(paths, json_settings, logger)

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    assert len(json_data) > 0
    python_entry = next(item for item in json_data if item["keyword"] == "python")
    assert python_entry["message_count"] == 3
    assert python_entry["authors_count"] == 3

    # 3. CSV export
    csv_path = str(tmp_path / "keywords.csv")
    csv_settings = base_settings
    csv_settings.format = "csv"
    csv_settings.output_path = csv_path
    show_list_keywords(paths, csv_settings, logger)

    with open(csv_path, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert "python,3,3" in csv_content

    # 4. HTML export
    html_path = str(tmp_path / "keywords.html")
    html_settings = base_settings
    html_settings.format = "html"
    html_settings.output_path = html_path
    show_list_keywords(paths, html_settings, logger)

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    assert "<h1>Extracted Keywords</h1>" in html_content

    # 5. Markdown export
    md_path = str(tmp_path / "keywords.md")
    md_settings = base_settings
    md_settings.format = "markdown"
    md_settings.output_path = md_path
    show_list_keywords(paths, md_settings, logger)

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    assert "# Extracted Keywords" in md_content


def test_show_list_keywords_empty(tmp_path, base_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    mock_log_warn = mocker.patch.object(logger, "warning")
    mocker.patch("pyqwk.core.load_data", return_value=([], {}))

    show_list_keywords([str(tmp_path / "empty.qwk")], base_settings, logger)
    mock_log_warn.assert_called_once_with("No keywords found across messages.")


def test_cli_list_keywords_flag(tmp_path, mocker):
    qwk_file = tmp_path / "test.qwk"
    qwk_file.write_bytes(b"\x00" * 128)

    mock_show = mocker.patch("pyqwk.cli.show_list_keywords")

    mocker.patch("sys.argv", ["qwk", str(qwk_file), "--list-keywords"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert mock_show.called
