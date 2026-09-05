import logging
import unittest.mock as mock
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    _order_messages_by_thread,
    process_merged_files,
    show_attachments,
    show_list_authors,
    show_list_bbs,
    show_list_conferences,
    show_list_phones,
    show_threads,
)
from pyqwk.gui import ToolTip


def test_tooltip_exception_branches():
    widget = mock.MagicMock()
    tt = ToolTip(widget, "Test Tooltip")
    tt._timer_id = "timer123"

    # 1. _unschedule exception in widget.after_cancel
    widget.after_cancel.side_effect = Exception("cancel error")
    tt._unschedule()
    assert tt._timer_id is None

    # 2. show exception in widget.winfo_rootx
    widget.winfo_rootx.side_effect = Exception("geom error")
    tt.show()
    assert tt.tooltip_window is None

    # 3. show exception in tw.attributes
    widget.winfo_rootx.side_effect = None
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 100
    widget.winfo_height.return_value = 20

    with mock.patch("pyqwk.gui.tk.Toplevel") as mock_toplevel:
        top_inst = mock.MagicMock()
        mock_toplevel.return_value = top_inst
        top_inst.attributes.side_effect = Exception("attr error")
        tt.show()
        assert tt.tooltip_window is top_inst

    # 4. hide exception in tw.destroy
    top_inst.destroy.side_effect = Exception("destroy error")
    tt.hide()
    assert tt.tooltip_window is None


def test_show_list_phones_empty_match_and_filter_exclusion():
    hdr1 = MessageHeader(
        " ", 1, "01-01-24", "10:00", "To", "Alice", "Test", "", None, 1, " ", 1, 0, " "
    )
    hdr2 = MessageHeader(
        " ", 2, "01-01-24", "10:05", "To", "Bob", "Test", "", None, 1, " ", 1, 0, " "
    )
    msg1 = ParsedMessage("555-1234", 1, None, 1, hdr1)
    msg2 = ParsedMessage("555-5678", 2, None, 1, hdr2)

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
        separator="dashes",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        authors=["Alice"],
    )

    logger = logging.getLogger("test")

    mock_re = mock.MagicMock()
    mock_re.findall.return_value = ["   "]

    with mock.patch("pyqwk.core.load_data", return_value=([msg1, msg2], {})):
        with mock.patch("pyqwk.core.RE_PHONE_PATTERN", mock_re):
            show_list_phones(["test.qwk"], settings, logger)


def test_process_merged_files_individual_archive_dry_run():
    hdr = MessageHeader(
        " ", 1, "01-01-24", "10:00", "To", "From", "Test", "", None, 1, " ", 1, 0, " "
    )
    msg = ParsedMessage("Hello world", 1, None, 1, hdr)

    settings = ProcessingSettings(
        verbose=False,
        private=False,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=True,
        threaded=False,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="dashes",
        output_mode="file",
        output_path="archive.zip",
        encoding="cp437",
        dry_run=True,
    )

    logger = logging.getLogger("test")

    with mock.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"})):
        process_merged_files(["test.qwk"], settings, logger)


def test_listing_reports_filter_exclusions():
    hdr1 = MessageHeader(
        " ", 1, "01-01-24", "10:00", "To", "Alice", "Test", "", None, 1, " ", 1, 0, " "
    )
    hdr2 = MessageHeader(
        " ", 2, "01-01-24", "10:05", "To", "Bob", "Test", "", None, 1, " ", 1, 0, " "
    )
    msg1 = ParsedMessage("begin 644 file.txt\nM`\nend\n", 1, None, 1, hdr1)
    msg2 = ParsedMessage("Plain text no attachment", 2, None, 1, hdr2)

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
        separator="dashes",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        authors=["Alice"],
    )

    logger = logging.getLogger("test")

    with mock.patch("pyqwk.core.load_data", return_value=([msg1, msg2], {1: "General"})):
        show_list_bbs(["test.qwk"], settings, logger)
        show_threads(["test.qwk"], settings, logger)
        show_attachments(["test.qwk"], settings, logger)
        show_list_conferences(["test.qwk"], settings, logger)
        show_list_authors(["test.qwk"], settings, logger)
