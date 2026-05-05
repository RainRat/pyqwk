import os
import logging
import datetime
from pyqwk.core import (
    _parse_qwk_date,
    MessageHeader,
    ProcessingSettings,
    ParsedMessage,
    load_data,
    _generate_safe_filename,
    process_merged_files,
    _write_html,
    _write_markdown,
    _write_text,
    _write_index,
    show_info,
    show_stats,
    process_multiple_files,
    _order_messages_by_thread,
    organize_by_bbs,
    matches_filters,
    _parse_html_messages,
    _parse_markdown_messages,
)
from unittest.mock import MagicMock, patch


def test_parse_qwk_date_iso():
    """Cover line 2932: ISO 8601 format."""
    dt_str = "2023-10-27T12:34:56"
    dt = _parse_qwk_date(dt_str, "")
    assert dt == datetime.datetime(2023, 10, 27, 12, 34, 56)

    # Also test non-ISO path
    dt = _parse_qwk_date("10-27-23", "12:34:56")
    assert dt.year == 2023


def test_load_data_control_dat_search():
    """Cover lines 1500-1506: Searching for case-insensitive CONTROL.DAT."""
    logger = logging.getLogger("test")

    # We want os.path.exists("control.dat") to be False first, then True after search
    exists_map = {"control.dat": False, "CONTROL.DAT": True, "messages.dat": True}

    def mock_exists(p):
        return exists_map.get(os.path.basename(p), False)

    with (
        patch("os.path.isdir", return_value=True),
        patch("os.listdir", return_value=["messages.dat", "CONTROL.DAT"]),
        patch("os.path.exists", side_effect=mock_exists),
        patch("zipfile.is_zipfile", return_value=False),
        patch("builtins.open", MagicMock()) as m_open,
    ):
        m_open.return_value.__enter__.return_value.read.return_value = (
            b"Produced by pyqwk"
        )
        m_open.return_value.__enter__.return_value.splitlines.return_value = [
            b"BBS"
        ] * 11

        load_data("messages.dat", logger)

    # Also test the case where is_isdir is False to cover that branch
    with (
        patch("os.path.isdir", return_value=False),
        patch("os.path.exists", return_value=False),
        patch("zipfile.is_zipfile", return_value=False),
        patch("builtins.open", MagicMock()),
    ):
        load_data("messages.dat", logger)


def test_generate_safe_filename_extension_check():
    """Cover lines 1993-1994: if not filename.endswith(ext)."""
    header = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " "
    )
    msg = ParsedMessage("text", 1, None, 1, header)
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="none",
        output_mode="file",
        output_path="out",
        encoding="cp437",
        filename_pattern="myname",
    )
    # Case 1: Doesn't end with ext
    filename = _generate_safe_filename(msg, settings, 1)
    assert filename == "myname.txt"

    # Case 2: Already ends with ext
    settings.filename_pattern = "myname.txt"
    filename = _generate_safe_filename(msg, settings, 1)
    assert filename == "myname.txt"


def test_process_merged_files_invalid_sort(tmp_path):
    """Cover lines 2391-2395: Invalid sort key and reversal_needed."""
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
        format="text",
        separator="none",
        output_mode="file",
        output_path=str(tmp_path / "out.txt"),
        encoding="cp437",
        sort="invalid",
        reverse=True,
    )

    header = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " "
    )
    msg = ParsedMessage("text", 1, None, 1, header)

    logger = logging.getLogger("test")
    with patch("pyqwk.core.load_data", return_value=([msg], {})):
        process_merged_files(["dummy.qwk"], settings, logger)


def test_write_toc_empty_confs():
    """Cover lines 2813, 2891, 3198: TOC generation with messages but avoiding double entries."""
    header = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " "
    )
    msg = ParsedMessage("text", 1, None, 1, header, confname="TestConf")
    msgs = [msg, msg]  # Two messages in same conference

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
        format="html",
        separator="none",
        output_mode="file",
        output_path=None,
        encoding="cp437",
        include_toc=True,
    )

    # HTML TOC
    with patch("pyqwk.core._write_text_output"):
        _write_html(msgs, None, settings=settings)

    # Markdown TOC
    settings.format = "markdown"
    with patch("pyqwk.core._write_text_output"):
        _write_markdown(msgs, None, settings=settings)

    # Text TOC
    settings.format = "text"
    with patch("pyqwk.core._write_text_output"):
        _write_text(msgs, None, settings=settings)


def test_write_index_other_format(tmp_path):
    """Cover line 3507-3509 exit path."""
    info = [
        {
            "conf_num": 1,
            "conf_name": "Test",
            "path": "msg.md",
            "subject": "Subj",
            "from": "Me",
            "to": "You",
            "date": "now",
            "msgnum": 1,
            "attachments": [],
        }
    ]
    settings = MagicMock(format="text")  # Neither html nor markdown
    _write_index(info, str(tmp_path), settings)


def test_show_info_empty_file_non_json(capfd):
    """Cover line 3750: if settings.format != 'json' in show_info empty file path."""
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
    )
    logger = logging.getLogger("test")
    # Case 1: format != 'json'
    with patch("pyqwk.core.load_data", return_value=(bytearray(b"short"), {})):
        show_info(["short.qwk"], settings, logger)
        out, err = capfd.readouterr()
        assert "Invalid or empty file." in out

    # Case 2: format == 'json'
    settings.format = "json"
    with patch("pyqwk.core.load_data", return_value=(bytearray(b"short"), {})):
        show_info(["short.qwk"], settings, logger)
        out, err = capfd.readouterr()
        assert "File:" not in out


def test_show_stats_merged_json():
    """Cover line 4097: if settings.format != 'json' in show_stats merged path."""
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
        merge_stats=True,
        quiet=True,
    )
    logger = logging.getLogger("test")
    # Case 1: format == 'json'
    with patch("pyqwk.core.calculate_archive_stats", return_value={}):
        with patch("pyqwk.core.load_data", return_value=([], {})):
            show_stats(["dummy.qwk"], settings, logger)

    # Case 2: format != 'json'
    settings.format = "text"
    with patch("pyqwk.core.calculate_archive_stats", return_value={}):
        with patch("pyqwk.core.load_data", return_value=([], {})):
            with patch("pyqwk.core.render_stats_as_text", return_value="stats"):
                show_stats(["dummy.qwk"], settings, logger)


def test_process_multiple_files_dry_run():
    """Cover line 4122: if not settings.dry_run in process_multiple_files."""
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        dry_run=True,
    )
    logger = logging.getLogger("test")
    with patch("os.makedirs") as mock_mkdir:
        process_multiple_files(["in.qwk"], "out_dir", settings, logger)
        mock_mkdir.assert_not_called()


def test_order_messages_no_msgnum():
    """Cover line 4180: if message.msgnum is not None: is False."""
    header = MessageHeader(
        " ",
        None,
        "01-01-23",
        "12:00",
        "To",
        "From",
        "Subj",
        "",
        None,
        1,
        " ",
        1,
        1,
        " ",
    )
    msg = ParsedMessage("text", None, None, 1, header)
    ordered = _order_messages_by_thread([msg])
    assert len(ordered) == 1


def test_threading_cycle_nested_report(caplog):
    """Cover line 4280-4288: cycle detection in nested traversal."""
    # A -> B -> A
    header1 = MessageHeader(
        " ", 1, "01-01-23", "12:00", "To", "From", "Subj A", "", 2, 1, " ", 1, 1, " "
    )
    header2 = MessageHeader(
        " ", 2, "01-01-23", "12:00", "To", "From", "Subj B", "", 1, 1, " ", 1, 1, " "
    )
    msg1 = ParsedMessage("text A", 1, 2, 1, header1)
    msg2 = ParsedMessage("text B", 2, 1, 1, header2)

    with caplog.at_level(logging.WARNING):
        # We need to trigger line 4281 specifically (cycle_reported check)
        # The logic:
        # children[1] = [2]
        # children[2] = [1]
        # visit_iterative(1):
        #   enter_node(1)
        #   enter_node(2)
        #   child_idx=1 is in path -> report cycle
        #   second time we see the cycle, it shouldn't report? No, cycle_reported handles that.
        _order_messages_by_thread([msg1, msg2])
        assert "Circular reference detected" in caplog.text


def test_organize_by_bbs_exists(tmp_path):
    """Cover line 4338: if not os.path.exists(safe_folder_name) is False."""
    archive = tmp_path / "test.qwk"
    archive.write_text("dummy")

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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        dry_run=False,
    )
    logger = logging.getLogger("test")

    from pyqwk.core import BBSInfo, ConferenceMap

    bbs_info = BBSInfo(name="Test BBS", bbs_id="123")
    board_dict = ConferenceMap()
    board_dict.bbs_info = bbs_info

    with (
        patch("pyqwk.core.load_data", return_value=("data", board_dict)),
        patch("os.path.isfile", return_value=True),
        patch("shutil.move"),
        patch("os.path.exists", return_value=True),
        patch("os.makedirs") as mock_mkdir,
    ):
        organize_by_bbs([str(archive)], settings, logger)
        mock_mkdir.assert_not_called()


def test_matches_filters_password():
    """Cover line 1848: message.header.is_password is True."""
    header = MessageHeader(
        "%", 1, "01-01-23", "12:00", "To", "From", "Subj", "", None, 1, " ", 1, 1, " "
    )
    msg = ParsedMessage("text", 1, None, 1, header)
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
        format="text",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
    )
    # Passworded messages are always filtered out
    assert not matches_filters(msg, settings, set())


def test_format_text_private():
    header = MessageHeader(
        status="*",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subject",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )
    formatted = header.format_text({1: "General"}, verbose=False)
    assert "Status:         [PRIVATE]" in formatted


def test_format_oneline_flags():
    header = MessageHeader(
        status="*",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="To",
        msgfrom="From",
        msgsubject="Subject",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=1,
        nettag="",
    )

    formatted = header.format_oneline({1: "General"}, is_private=True)
    assert "*  Subject" in formatted

    formatted = header.format_oneline({1: "General"}, has_attachments=True)
    assert "@  Subject" in formatted

    formatted = header.format_oneline(
        {1: "General"}, is_private=True, has_attachments=True
    )
    assert "*@ Subject" in formatted

    formatted = header.format_oneline({1: "General"}, is_private=True, use_colors=True)
    assert "\x1b[90m* \x1b[0m Subject" in formatted


def test_parse_html_empty_attachments(tmp_path):
    html_content = """
    <div class="message">
    <div class="header">
    <strong>Number:</strong> 1<br>
    <strong>Date:</strong> 01-01-24 12:00<br>
    <strong>From:</strong> Alice<br>
    <strong>To:</strong> Bob<br>
    <strong>Subject:</strong> Hello<br>
    <strong>Conference:</strong> General (1)<br>
    <strong>Attachments:</strong>  </div>
    <pre class="body">Hello world</pre>
    </div>
    """
    p = tmp_path / "test.html"
    p.write_text(html_content)

    messages = list(_parse_html_messages(str(p)))
    assert len(messages) == 1
    assert messages[0].attachments is None


def test_parse_markdown_empty_attachments(tmp_path):
    md_content = """
## Message 1
- **Date:** 01-01-24 12:00
- **From:** Alice
- **To:** Bob
- **Subject:** Hello
- **Conference:** General (1)
- **Attachments:**

Hello world
"""
    p = tmp_path / "test.md"
    p.write_text(md_content)

    messages = list(_parse_markdown_messages(str(p)))
    assert len(messages) == 1
    assert messages[0].attachments is None


def test_parse_rss_messages_no_channel():
    import xml.etree.ElementTree as ET
    from pyqwk.core import _parse_rss_messages

    root = ET.Element("rss")
    # No channel element
    messages = _parse_rss_messages(root)
    assert messages == []


def test_parse_rss_messages_generic_title():
    import xml.etree.ElementTree as ET
    from pyqwk.core import _parse_rss_messages

    xml_data = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
    <channel>
        <title>QWK Message Archive</title>
        <item>
            <title>Test Subject</title>
            <author>Tester</author>
            <description>Test Body</description>
        </item>
    </channel>
    </rss>
    """
    root = ET.fromstring(xml_data)
    messages = _parse_rss_messages(root)
    assert len(messages) == 1
    assert messages[0].bbs_name is None


def test_parse_rss_messages_invalid_pubdate():
    import xml.etree.ElementTree as ET
    from pyqwk.core import _parse_rss_messages

    xml_data = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
    <channel>
        <item>
            <pubDate>Invalid Date</pubDate>
        </item>
    </channel>
    </rss>
    """
    root = ET.fromstring(xml_data)
    messages = _parse_rss_messages(root)
    assert len(messages) == 1
    assert messages[0].header.msgdate == "01-01-70"
    assert messages[0].header.msgtime == "00:00"


def test_parse_rss_messages_guid_parsing():
    import xml.etree.ElementTree as ET
    from pyqwk.core import _parse_rss_messages

    xml_data = """<?xml version="1.0" encoding="UTF-8" ?>
    <rss version="2.0">
    <channel>
        <title>Test Archive</title>
        <item>
            <title>Test Subject</title>
            <guid>123.456@qwk</guid>
        </item>
    </channel>
    </rss>
    """
    root = ET.fromstring(xml_data)
    messages = _parse_rss_messages(root)
    assert len(messages) == 1
    assert messages[0].confnum == 123
    assert messages[0].msgnum == 456


def test_parse_markdown_messages_empty_attachments_list(tmp_path):
    from pyqwk.core import _parse_markdown_messages

    md_content = """## Message 1
- **Attachments:** , ,

Body
"""
    p = tmp_path / "test_empty_attach_v2.md"
    p.write_text(md_content)
    messages = list(_parse_markdown_messages(str(p)))
    assert len(messages) == 1
    assert messages[0].attachments is None


def test_parse_markdown_messages_no_blank_line_v2(tmp_path):
    from pyqwk.core import _parse_markdown_messages

    md_content = """## Message 1
- **From:** Alice
- **To:** Bob
- **Subject:** Hello
Body text immediately following metadata.
"""
    p = tmp_path / "test_v2.md"
    p.write_text(md_content)
    messages = list(_parse_markdown_messages(str(p)))
    assert len(messages) == 1
    assert "Body text immediately following metadata." in messages[0].text
