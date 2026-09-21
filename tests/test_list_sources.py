import json
import logging
import pytest

from pyqwk.core import (
    BBSInfo,
    ConferenceMap,
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    render_sources_as_text,
    _render_sources_html,
    _render_sources_markdown,
    _render_sources_csv,
    show_list_sources,
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
        text="Sample message text.",
        msgnum=msgnum,
        refnum=None,
        confnum=confnum,
        header=header,
        bbs_name=bbs_name,
        source_file=source_file,
    )


def test_render_sources_functions():
    sources = [
        {
            "source_file": "archive1.qwk",
            "message_count": 10,
            "authors_count": 3,
            "conferences_count": 2,
            "first_active": "2023-10-12",
            "last_active": "2023-10-15",
            "bbs_name": "Digital Horizon BBS",
        },
        {
            "source_file": "very_long_source_filename_that_gets_truncated_for_display.qwk",
            "message_count": 5,
            "authors_count": 1,
            "conferences_count": 1,
            "first_active": None,
            "last_active": None,
            "bbs_name": None,
        },
    ]

    text_colored = render_sources_as_text(sources, use_colors=True)
    assert "Source Files" in text_colored
    assert "archive1.qwk" in text_colored
    assert "Total Source Files: 2" in text_colored

    text_plain = render_sources_as_text(sources, use_colors=False)
    assert "=== Source Files ===" in text_plain

    html_out = _render_sources_html(sources, "Source Files")
    assert "<h1>Source Files</h1>" in html_out
    assert "<td>archive1.qwk</td>" in html_out

    md_out = _render_sources_markdown(sources, "Source Files")
    assert "# Source Files" in md_out
    assert "| archive1.qwk | 10 | 3 | 2 | 2023-10-12 | 2023-10-15 | Digital Horizon BBS |" in md_out

    csv_out = _render_sources_csv(sources)
    assert "source_file,message_count,authors_count,conferences_count,first_active,last_active,bbs_name" in csv_out
    assert "archive1.qwk,10,3,2,2023-10-12,2023-10-15,Digital Horizon BBS" in csv_out


def test_show_list_sources_formats(tmp_path, base_settings, mocker):
    logger = logging.getLogger("pyqwk.test")

    msg1 = create_sample_message(msgnum=1, author="Alice", confnum=1, source_file="src_a.json", bbs_name="BBS A")
    msg2 = create_sample_message(msgnum=2, author="Bob", confnum=2, source_file="src_a.json", bbs_name="BBS A")
    msg3 = create_sample_message(msgnum=3, author="Charlie", confnum=1, source_file="src_b.json", bbs_name="BBS B")

    def mock_load(path, log, enc):
        if "src_a" in path:
            return [msg1, msg2], {1: "General", 2: "Tech"}
        return [msg3], {1: "General"}

    mocker.patch("pyqwk.core.load_data", side_effect=mock_load)

    paths = [str(tmp_path / "src_a.json"), str(tmp_path / "src_b.json")]

    mock_stdout = mocker.patch("sys.stdout.write")
    show_list_sources(paths, base_settings, logger)
    written_text = "".join(call[0][0] for call in mock_stdout.call_args_list)
    assert "Source Files" in written_text

    json_path = str(tmp_path / "sources.json")
    json_settings = base_settings
    json_settings.format = "json"
    json_settings.output_path = json_path
    show_list_sources(paths, json_settings, logger)

    with open(json_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    assert len(json_data) == 2
    assert json_data[0]["source_file"] == "src_a.json"
    assert json_data[0]["message_count"] == 2
    assert json_data[0]["authors_count"] == 2

    csv_path = str(tmp_path / "sources.csv")
    csv_settings = base_settings
    csv_settings.format = "csv"
    csv_settings.output_path = csv_path
    show_list_sources(paths, csv_settings, logger)

    with open(csv_path, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert "src_a.json" in csv_content
    assert "src_b.json" in csv_content

    html_path = str(tmp_path / "sources.html")
    html_settings = base_settings
    html_settings.format = "html"
    html_settings.output_path = html_path
    show_list_sources(paths, html_settings, logger)

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    assert "<h1>Source Files</h1>" in html_content

    md_path = str(tmp_path / "sources.md")
    md_settings = base_settings
    md_settings.format = "markdown"
    md_settings.output_path = md_path
    show_list_sources(paths, md_settings, logger)

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()
    assert "# Source Files" in md_content


def test_show_list_sources_empty(tmp_path, base_settings, mocker):
    logger = logging.getLogger("pyqwk.test")
    mock_log_warn = mocker.patch.object(logger, "warning")
    mocker.patch("pyqwk.core.load_data", return_value=([], {}))

    show_list_sources([str(tmp_path / "empty.qwk")], base_settings, logger)
    mock_log_warn.assert_called_once_with("No source files found.")


def test_cli_list_sources_flags(tmp_path, mocker):
    qwk_file = tmp_path / "test.qwk"
    qwk_file.write_bytes(b"\x00" * 128)

    mock_show = mocker.patch("pyqwk.cli.show_list_sources")

    mocker.patch("sys.argv", ["qwk", str(qwk_file), "--list-sources"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert mock_show.called

    mock_show.reset_mock()
    mocker.patch("sys.argv", ["qwk", str(qwk_file), "--list-files"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 0
    assert mock_show.called


def test_show_list_sources_load_archive_error_logging(tmp_path, base_settings, mocker):
    logger = mocker.MagicMock(spec=logging.Logger)
    mocker.patch("pyqwk.core.load_data", side_effect=RuntimeError("Corrupted archive"))

    show_list_sources([str(tmp_path / "failing.qwk")], base_settings, logger)
    logger.error.assert_called_once()
    assert "Failed to load archive" in logger.error.call_args[0][0]


def test_show_list_sources_bytearray_and_edge_case_handling(tmp_path, base_settings, mocker):
    logger = mocker.MagicMock(spec=logging.Logger)

    hdr_excluded = MessageHeader(
        status=" ", msgnum=10, msgdate="10-12-23", msgtime="12:00",
        msgto="Bob", msgfrom="ExcludedAuthor", msgsubject="Secret",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=1, lognum=1, nettag=""
    )
    msg_excluded = ParsedMessage(
        text="Excluded message", msgnum=10, refnum=None, confnum=1,
        header=hdr_excluded, source_file="src_exclude.qwk", bbs_name="BBS X"
    )

    hdr_edge = MessageHeader(
        status=" ", msgnum=11, msgdate="INVALID_DATE", msgtime="INVALID",
        msgto="Bob", msgfrom="   ", msgsubject="No Author",
        msgpassword="", refnum=None, numblocks=1, msgflag=" ",
        confnum=99, lognum=1, nettag=""
    )
    msg_edge = ParsedMessage(
        text="Edge case message", msgnum=11, refnum=None, confnum=99,
        header=hdr_edge, source_file="src_edge.qwk", bbs_name="", bbs_id=""
    )
    msg_edge.confnum = None

    board_dict1 = ConferenceMap()
    board_dict1.bbs_info = BBSInfo(user_name="BBSUser")

    raw_header = MessageHeader(
        status=" ", msgnum=1, msgdate="01-01-24", msgtime="10:00",
        msgto="Alice", msgfrom="Bob", msgsubject="Byte Record",
        msgpassword="", refnum=None, numblocks=2, msgflag=" ",
        confnum=5, lognum=1, nettag=""
    )
    valid_bytes = bytearray(b"Produced QWK    " + b"\x00" * 112 + raw_header.to_bytes() + b"Hello byte msg\x00" * 8)

    def mock_load(path, log, enc):
        if "short_bytes.qwk" in path:
            return bytearray(b"too_short"), ConferenceMap()
        if "valid_bytes.qwk" in path:
            return valid_bytes, ConferenceMap()
        return [msg_excluded, msg_edge], board_dict1

    mocker.patch("pyqwk.core.load_data", side_effect=mock_load)

    settings = base_settings
    settings.exclude_authors = ["ExcludedAuthor"]
    settings.output_path = str(tmp_path / "out_sources.json")
    settings.format = "json"

    paths = [
        str(tmp_path / "short_bytes.qwk"),
        str(tmp_path / "valid_bytes.qwk"),
        str(tmp_path / "mixed.json"),
    ]

    show_list_sources(paths, settings, logger)

    with open(settings.output_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) >= 1
