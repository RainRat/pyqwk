"""Tests for branch edge cases in core and gui modules (v7)."""

import logging
from unittest.mock import MagicMock
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    _order_messages_by_thread,
    process_merged_files,
    show_list_authors,
    show_list_conferences,
    show_list_phones,
    show_list_recipients,
    show_list_subjects,
    show_threads,
)
from pyqwk.gui import ToolTip


def _make_settings(tmp_path, **kwargs):
    defaults = dict(
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
        output_mode="export",
        output_path=str(tmp_path / "out.qwk"),
        encoding="utf-8",
    )
    defaults.update(kwargs)
    return ProcessingSettings(**defaults)


def _make_header(**kwargs):
    defaults = {
        "status": " ",
        "msgnum": 1,
        "msgdate": "01-01-24",
        "msgtime": "12:00",
        "msgto": "Bob",
        "msgfrom": "Alice",
        "msgsubject": "Test",
        "msgpassword": "",
        "refnum": None,
        "numblocks": 1,
        "msgflag": "",
        "confnum": 1,
        "lognum": 1,
        "nettag": "",
    }
    defaults.update(kwargs)
    return MessageHeader(**defaults)


def _make_msg(header=None, text="Test", confnum=1, msgnum=1, refnum=None, **kwargs):
    if header is None:
        header = _make_header(confnum=confnum, msgnum=msgnum, refnum=refnum)
    return ParsedMessage(
        header=header,
        text=text,
        confnum=confnum,
        msgnum=msgnum,
        refnum=refnum,
        **kwargs,
    )


def test_process_merged_files_dry_run_pack_skip(tmp_path, mocker):
    archive_path = tmp_path / "test.qwk"
    archive_path.touch()

    logger = logging.getLogger("test")
    settings = _make_settings(tmp_path, dry_run=True, output_path=str(tmp_path / "out.qwk"))

    mocker.patch("pyqwk.core.load_data", return_value=([], {}))
    mock_pack = mocker.patch("pyqwk.core._pack_directory_to_archive")

    process_merged_files([str(archive_path)], settings, logger)
    mock_pack.assert_not_called()


def test_show_list_phones_whitespace_match(tmp_path, mocker):
    hdr = _make_header(msgfrom="Alice", msgto="Bob", msgsubject="Test")
    msg = _make_msg(header=hdr, text="(   )   -    ", confnum=1, msgnum=10)
    msg.bbs_name = "TestBBS"

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

    logger = logging.getLogger("test")
    settings = _make_settings(tmp_path)

    show_list_phones(["test.qwk"], settings, logger)


def test_show_list_conferences_invalid_date_handling(tmp_path, mocker):
    hdr = _make_header(msgdate="INVALID", msgtime="INVALID")
    msg = _make_msg(header=hdr, text="Hello", confnum=1, msgnum=10)
    msg.datetime = None

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

    logger = logging.getLogger("test")
    settings = _make_settings(tmp_path)

    show_list_conferences(["test.qwk"], settings, logger)


def test_order_messages_by_thread_cycle_reentry():
    hdr = _make_header()
    m0 = _make_msg(header=hdr, text="", confnum=1, msgnum=1, refnum=2)
    m1 = _make_msg(header=hdr, text="", confnum=1, msgnum=2, refnum=1)
    m2 = _make_msg(header=hdr, text="", confnum=1, msgnum=3, refnum=1)

    res = _order_messages_by_thread([m0, m1, m2])
    assert len(res) == 3


def test_show_threads_message_thread_id_none(tmp_path, mocker):
    hdr = _make_header()
    msg = _make_msg(header=hdr, text="Test", confnum=1, msgnum=1)
    msg.thread_id = None

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

    logger = logging.getLogger("test")
    settings = _make_settings(tmp_path)

    show_threads(["test.qwk"], settings, logger)


def test_list_reports_invalid_date_and_empty_bbs(tmp_path, mocker):
    hdr = _make_header(msgfrom="Alice", msgto="Bob", msgsubject="Test", msgdate="INVALID", msgtime="INVALID")
    msg = _make_msg(header=hdr, text="Test", confnum=1, msgnum=1)
    msg.datetime = None
    msg.bbs_name = ""
    msg.bbs_id = ""

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

    logger = logging.getLogger("test")
    settings = _make_settings(tmp_path)

    show_list_authors(["test.qwk"], settings, logger)
    show_list_recipients(["test.qwk"], settings, logger)
    show_list_subjects(["test.qwk"], settings, logger)


def test_tooltip_exception_branches():
    widget = MagicMock()
    widget.after_cancel.side_effect = Exception("Cancel failed")
    widget.winfo_rootx.side_effect = Exception("RootX failed")

    tt = ToolTip(widget, "Tooltip text")
    tt._timer_id = "timer123"

    tt._unschedule()
    assert tt._timer_id is None

    tt.show()
    assert tt.tooltip_window is None

    mock_tw = MagicMock()
    mock_tw.attributes.side_effect = Exception("Attributes failed")
    mock_tw.destroy.side_effect = Exception("Destroy failed")

    widget.winfo_rootx.side_effect = None
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 100
    widget.winfo_height.return_value = 20

    mocker_toplevel = MagicMock(return_value=mock_tw)
    with pytest.MonkeyPatch.context() as m:
        m.setattr("pyqwk.gui.tk.Toplevel", mocker_toplevel)
        tt.show()
        assert tt.tooltip_window == mock_tw
        tt.hide()
        assert tt.tooltip_window is None
