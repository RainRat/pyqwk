import json
import logging
import pytest

from pyqwk.core import (
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

    # Mock load_data to return pre-constructed message lists
    def mock_load(path, log, enc):
        if "src_a" in path:
            return [msg1, msg2], {1: "General", 2: "Tech"}
        return [msg3], {1: "General"}

    mocker.patch("pyqwk.core.load_data", side_effect=mock_load)

    paths = [str(tmp_path / "src_a.json"), str(tmp_path / "src_b.json")]

    # 1. Plain Text stdout
    mock_stdout = mocker.patch("sys.stdout.write")
    show_list_sources(paths, base_settings, logger)
    written_text = "".join(call[0][0] for call in mock_stdout.call_args_list)
    assert "Source Files" in written_text

    # 2. JSON export
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

    # 3. CSV export
    csv_path = str(tmp_path / "sources.csv")
    csv_settings = base_settings
    csv_settings.format = "csv"
    csv_settings.output_path = csv_path
    show_list_sources(paths, csv_settings, logger)

    with open(csv_path, "r", encoding="utf-8") as f:
        csv_content = f.read()
    assert "src_a.json" in csv_content
    assert "src_b.json" in csv_content

    # 4. HTML export
    html_path = str(tmp_path / "sources.html")
    html_settings = base_settings
    html_settings.format = "html"
    html_settings.output_path = html_path
    show_list_sources(paths, html_settings, logger)

    with open(html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    assert "<h1>Source Files</h1>" in html_content

    # 5. Markdown export
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
    # Test --list-sources and --list-files CLI invocation
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


def test_show_list_sources_coverage_gaps(tmp_path, base_settings, mocker):
    from pyqwk.core import BBSInfo, ConferenceMap

    logger = logging.getLogger("pyqwk.test")
    mock_log_err = mocker.patch.object(logger, "error")

    board_dict_with_bbs = ConferenceMap()
    board_dict_with_bbs.bbs_info = BBSInfo(user_name="SysopUser")
    msg1 = create_sample_message(msgnum=1, author="Alice", source_file="src_a.qwk")

    short_data = bytearray(b"too_short")
    full_data = bytearray(b"\x00" * 128)
    board_dict_bytes = ConferenceMap()

    def mock_load(path, log, enc):
        if "failing" in path:
            raise RuntimeError("Archive load error")
        if "short" in path:
            return short_data, board_dict_bytes
        if "bytes" in path:
            return full_data, board_dict_bytes
        return [msg1], board_dict_with_bbs

    mocker.patch("pyqwk.core.load_data", side_effect=mock_load)

    paths = [
        str(tmp_path / "valid.qwk"),
        str(tmp_path / "short.qwk"),
        str(tmp_path / "bytes.qwk"),
        str(tmp_path / "failing.qwk"),
    ]

    base_settings.my_name = None
    mock_stdout = mocker.patch("sys.stdout.write")
    show_list_sources(paths, base_settings, logger)

    mock_log_err.assert_called_once()
    assert "Failed to load archive" in mock_log_err.call_args[0][0]

    written_text = "".join(call[0][0] for call in mock_stdout.call_args_list)
    assert "src_a.qwk" in written_text


def test_show_list_sources_filtering_and_edge_branches(tmp_path, base_settings, mocker):
    logger = logging.getLogger("pyqwk.test")

    # Message 1: Matches search filter, but has empty author, confnum=None, valid date, empty BBS name
    hdr1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto="Bob",
        msgfrom="   ",
        msgsubject="Test Match",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=None,
        lognum=1,
        nettag="",
    )
    msg1 = ParsedMessage(
        text="Target search term here",
        msgnum=1,
        refnum=None,
        confnum=None,
        header=hdr1,
        bbs_name="   ",
        bbs_id=None,
        source_file="edge_src.qwk",
    )

    # Message 2: Does NOT match search filter (filtered out)
    hdr2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="10-12-23",
        msgtime="12:00",
        msgto="Bob",
        msgfrom="Alice",
        msgsubject="Unrelated Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg2 = ParsedMessage(
        text="Other text without target",
        msgnum=2,
        refnum=None,
        confnum=1,
        header=hdr2,
        bbs_name="Sample BBS",
        source_file="edge_src.qwk",
    )

    mocker.patch("pyqwk.core.load_data", return_value=([msg1, msg2], {}))

    base_settings.search = "Target"
    mock_stdout = mocker.patch("sys.stdout.write")
    show_list_sources([str(tmp_path / "edge_src.qwk")], base_settings, logger)

    written_text = "".join(call[0][0] for call in mock_stdout.call_args_list)
    assert "edge_src.qwk" in written_text
