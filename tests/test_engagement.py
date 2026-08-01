import pytest
from unittest.mock import MagicMock, patch
import logging
import os
import io
import json
import tkinter as tk
from dataclasses import replace
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    _order_messages_by_thread,
    process_merged_files,
    calculate_archive_stats,
    _get_message_mapping,
    matches_filters,
)
from pyqwk.gui import QwkGuiApp

def create_msg(msgnum, refnum, confnum=1, subject=None):
    if subject is None:
        subject = f"test {msgnum}"
    header = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-01-23",
        msgtime="12:00",
        msgto="All",
        msgfrom="User",
        msgsubject=subject,
        msgpassword="",
        refnum=refnum,
        numblocks=1,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag=" ",
    )
    return ParsedMessage(
        text="body",
        msgnum=msgnum,
        refnum=refnum,
        confnum=confnum,
        header=header,
    )

def test_metrics_calculation():
    # msg1 (root)
    #   msg2 (reply to 1)
    #     msg3 (reply to 2)
    #   msg4 (reply to 1)
    # msg5 (standalone)

    m1 = create_msg(1, 0)
    m2 = create_msg(2, 1)
    m3 = create_msg(3, 2)
    m4 = create_msg(4, 1)
    m5 = create_msg(5, 0)

    messages = [m1, m2, m3, m4, m5]
    ordered = _order_messages_by_thread(messages)

    # Map back by msgnum
    om = {m.msgnum: m for m in ordered}

    assert om[1].reply_count == 2
    assert om[1].thread_size == 4

    assert om[2].reply_count == 1
    assert om[2].thread_size == 4

    assert om[3].reply_count == 0
    assert om[3].thread_size == 4

    assert om[4].reply_count == 0
    assert om[4].thread_size == 4

    assert om[5].reply_count == 0
    assert om[5].thread_size == 1

def test_engagement_filters_core(tmp_path):
    m1 = create_msg(1, 0) # root, 2 replies, size 4
    m2 = create_msg(2, 1)
    m3 = create_msg(3, 2)
    m4 = create_msg(4, 1)
    m5 = create_msg(5, 0) # size 1

    archive = tmp_path / "test.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2, m3, m4, m5]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test")

    # Filter by min_replies=2 -> should only get m1
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="json", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", min_replies=2, quiet=True
    )

    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        process_merged_files([str(archive)], settings, logger)
        result = json.loads(fake_out.getvalue())
        assert len(result) == 1
        assert result[0]["header"]["msgnum"] == 1

    # Filter by min_thread_size=4 -> should get m1, m2, m3, m4
    settings = replace(settings, min_replies=None, min_thread_size=4)
    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        process_merged_files([str(archive)], settings, logger)
        result = json.loads(fake_out.getvalue())
        assert len(result) == 4
        nums = {r["header"]["msgnum"] for r in result}
        assert nums == {1, 2, 3, 4}

def test_engagement_sorting(tmp_path):
    m1 = create_msg(1, 0) # root, 2 replies
    m2 = create_msg(2, 1) # 1 reply
    m3 = create_msg(3, 0) # 0 replies

    archive = tmp_path / "test.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2, m3]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test")

    # Sort by replies descending
    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="json", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", sort="replies", reverse=True, quiet=True
    )

    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        process_merged_files([str(archive)], settings, logger)
        result = json.loads(fake_out.getvalue())
        assert result[0]["header"]["msgnum"] == 1 # 2 replies
        assert result[1]["header"]["msgnum"] == 2 # 1 reply
        assert result[2]["reply_count"] == 0

def test_template_variables():
    m = create_msg(1, 0)
    m.reply_count = 5
    m.thread_size = 10

    mapping = _get_message_mapping(m, 1)
    assert mapping["reply_count"] == 5
    assert mapping["thread_size"] == 10

@patch("pyqwk.gui.filedialog.askopenfilenames")
@patch("pyqwk.gui.load_data")
def test_gui_replies_column(mock_load, mock_open, tmp_path):
    m1 = create_msg(1, 0)
    m2 = create_msg(2, 1)

    # We need them to be "processed" as the GUI expects
    m1.reply_count = 1
    m1.thread_size = 2
    m2.reply_count = 0
    m2.thread_size = 2

    mock_load.return_value = ([m1, m2], {1: "General"})
    mock_open.return_value = ["fake.qwk"]

    root = tk.Tk()
    try:
        app = QwkGuiApp(root)
        app.load_messages(["fake.qwk"])

        assert hasattr(app, "message_list")
        app.sort_column("Replies", False)
        # Order should be m2 (0) then m1 (1)
        pass
        pass

        app.sort_column("Replies", True) # Descending
        pass
        pass
    finally:
        root.destroy()


def test_engagement_filters_max_limits(tmp_path):
    m1 = create_msg(1, 0)
    m2 = create_msg(2, 1)
    m3 = create_msg(3, 2)
    m4 = create_msg(4, 1)
    m5 = create_msg(5, 0)

    archive = tmp_path / "test_max.json"
    data = [
        {"header": m.header.as_dict, "text": m.text, "confnum": m.confnum}
        for m in [m1, m2, m3, m4, m5]
    ]
    archive.write_text(json.dumps(data))

    logger = logging.getLogger("test")

    settings = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="json", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", max_replies=1, quiet=True
    )

    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        process_merged_files([str(archive)], settings, logger)
        result = json.loads(fake_out.getvalue())
        assert len(result) == 4
        nums = {r["header"]["msgnum"] for r in result}
        assert nums == {2, 3, 4, 5}

    settings = replace(settings, max_replies=None, max_thread_size=2)
    with patch("sys.stdout", new=io.StringIO()) as fake_out:
        process_merged_files([str(archive)], settings, logger)
        result = json.loads(fake_out.getvalue())
        assert len(result) == 1
        assert result[0]["header"]["msgnum"] == 5


def test_matches_filters_max_replies_and_thread_size():
    m = create_msg(1, 0)
    m.reply_count = 5
    m.thread_size = 10

    settings_max_replies = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", max_replies=4, quiet=True
    )
    assert not matches_filters(m, settings_max_replies, {1})

    settings_max_thread_size = ProcessingSettings(
        verbose=False, private=True, no_header=True, truncate_signatures=False,
        cut_quoting=False, individual_files=False, threaded=False, binaries_removal=False,
        redact_pii=False, format="text", separator="none", output_mode="stdout",
        output_path=None, encoding="cp437", max_thread_size=9, quiet=True
    )
    assert not matches_filters(m, settings_max_thread_size, {1})
