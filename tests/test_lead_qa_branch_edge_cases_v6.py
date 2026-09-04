import logging
import pyqwk.gui
import tkinter as tk
from unittest.mock import MagicMock
import pytest

from pyqwk.core import (
    MessageHeader,
    ParsedMessage,
    ProcessingSettings,
    _order_messages_by_thread,
    show_list_authors,
    show_list_phones,
    show_list_recipients,
    show_list_subjects,
    show_threads,
)
from pyqwk.gui import ToolTip


def test_order_messages_by_thread_cycle_already_reported(mocker):
    hdr0 = MessageHeader(
        status=" ",
        msgnum=100,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="All",
        msgfrom="Alice",
        msgsubject="Cycle Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg0 = ParsedMessage(text="Root", msgnum=100, refnum=None, confnum=1, header=hdr0)

    hdr1 = MessageHeader(
        status=" ",
        msgnum=101,
        msgdate="01-01-24",
        msgtime="12:05",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Re: Cycle Test",
        msgpassword="",
        refnum=100,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg1 = ParsedMessage(text="Child 1", msgnum=101, refnum=100, confnum=1, header=hdr1)

    hdr2 = MessageHeader(
        status=" ",
        msgnum=102,
        msgdate="01-01-24",
        msgtime="12:10",
        msgto="Bob",
        msgfrom="Charlie",
        msgsubject="Re: Cycle Test",
        msgpassword="",
        refnum=101,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg2 = ParsedMessage(text="Child 2", msgnum=102, refnum=101, confnum=1, header=hdr2)

    hdr3 = MessageHeader(
        status=" ",
        msgnum=103,
        msgdate="01-01-24",
        msgtime="12:15",
        msgto="Charlie",
        msgfrom="Alice",
        msgsubject="Re: Cycle Test",
        msgpassword="",
        refnum=102,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg3 = ParsedMessage(text="Cycle link back to 101", msgnum=103, refnum=102, confnum=1, header=hdr3)

    hdr4 = MessageHeader(
        status=" ",
        msgnum=104,
        msgdate="01-01-24",
        msgtime="12:20",
        msgto="Alice",
        msgfrom="Dave",
        msgsubject="Re: Cycle Test",
        msgpassword="",
        refnum=102,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg4 = ParsedMessage(text="Second link from 102", msgnum=104, refnum=102, confnum=1, header=hdr4)

    msgs = [msg0, msg1, msg2, msg3, msg4]
    ordered = _order_messages_by_thread(msgs)
    assert len(ordered) == 5


def test_show_threads_message_without_thread_id(mocker, tmp_path):
    logger = logging.getLogger("pyqwk.test")
    hdr = MessageHeader(
        status=" ",
        msgnum=100,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="All",
        msgfrom="Alice",
        msgsubject="Thread Test",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg = ParsedMessage(text="Hello", msgnum=100, refnum=None, confnum=1, header=hdr, thread_id=None)

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))
    mocker.patch("pyqwk.core._order_messages_by_thread", return_value=[msg])

    output_path = str(tmp_path / "threads.txt")
    settings = ProcessingSettings(
        verbose=False,
        private=True,
        no_header=False,
        truncate_signatures=False,
        cut_quoting=False,
        individual_files=False,
        threaded=True,
        binaries_removal=False,
        redact_pii=False,
        format="text",
        separator="auto",
        output_mode="file",
        output_path=output_path,
        encoding="cp437",
    )

    show_threads(["fake.qwk"], settings, logger)
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Conversation Threads:" in content


def test_list_reports_invalid_date_and_none_msg_dt(mocker, tmp_path):
    logger = logging.getLogger("pyqwk.test")

    hdr = MessageHeader(
        status=" ",
        msgnum=100,
        msgdate="",
        msgtime="",
        msgto="Recipient One",
        msgfrom="Author One",
        msgsubject="Subject One",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    msg = ParsedMessage(text="Call me at 555-123-4567", msgnum=100, refnum=None, confnum=1, header=hdr)

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))
    mocker.patch("pyqwk.core._parse_qwk_date", return_value=None)

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
        separator="auto",
        output_mode="file",
        output_path=str(tmp_path / "out.txt"),
        encoding="cp437",
    )

    # Test show_list_authors with msg_dt=None
    out_authors = str(tmp_path / "authors.txt")
    settings.output_path = out_authors
    show_list_authors(["fake.qwk"], settings, logger)
    with open(out_authors, "r", encoding="utf-8") as f:
        assert "Author One" in f.read()

    # Test show_list_recipients with msg_dt=None
    out_recipients = str(tmp_path / "recipients.txt")
    settings.output_path = out_recipients
    show_list_recipients(["fake.qwk"], settings, logger)
    with open(out_recipients, "r", encoding="utf-8") as f:
        assert "Recipient One" in f.read()

    # Test show_list_subjects with msg_dt=None
    out_subjects = str(tmp_path / "subjects.txt")
    settings.output_path = out_subjects
    show_list_subjects(["fake.qwk"], settings, logger)
    with open(out_subjects, "r", encoding="utf-8") as f:
        assert "Subject One" in f.read()

    # Test show_list_phones with msg_dt=None
    out_phones = str(tmp_path / "phones.txt")
    settings.output_path = out_phones
    show_list_phones(["fake.qwk"], settings, logger)
    with open(out_phones, "r", encoding="utf-8") as f:
        assert "555-123-4567" in f.read()


def test_show_list_phones_whitespace_match_handling(mocker, tmp_path):
    logger = logging.getLogger("pyqwk.test")

    hdr = MessageHeader(
        status=" ",
        msgnum=100,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="To User",
        msgfrom="From User",
        msgsubject="Test Phone",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=1,
        nettag="",
    )
    # White-space only phone match should be filtered out
    msg = ParsedMessage(text="  ", msgnum=100, refnum=None, confnum=1, header=hdr)

    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))

    out_path = str(tmp_path / "phones_ws.txt")
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
        separator="auto",
        output_mode="file",
        output_path=out_path,
        encoding="cp437",
    )

    show_list_phones(["fake.qwk"], settings, logger)
    assert not (tmp_path / "phones_ws.txt").exists()


def test_tooltip_exception_branches():
    widget = MagicMock()
    tooltip = ToolTip(widget, "Help text")

    # 1. Test _unschedule exception in after_cancel
    tooltip._timer_id = "timer123"
    widget.after_cancel.side_effect = Exception("Cancel failed")
    tooltip._unschedule()
    assert tooltip._timer_id is None

    # 2. Test show exception in winfo_rootx
    widget.winfo_rootx.side_effect = Exception("Geometry error")
    tooltip.show()
    assert tooltip.tooltip_window is None

    # 3. Test attributes topmost exception and destroy exception in hide
    widget.winfo_rootx.side_effect = None
    widget.winfo_rootx.return_value = 100
    widget.winfo_rooty.return_value = 100
    widget.winfo_height.return_value = 20

    tt = ToolTip(widget, "Sample")
    mock_tw = MagicMock()
    mock_tw.attributes.side_effect = Exception("Topmost unsupported")
    mock_tw.destroy.side_effect = Exception("Destroy error")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(pyqwk.gui.tk, "Toplevel", lambda w: mock_tw)
        mp.setattr(pyqwk.gui.tk, "Label", lambda *args, **kwargs: MagicMock())
        tt.show()
        assert tt.tooltip_window == mock_tw
        tt.hide()
        assert tt.tooltip_window is None
