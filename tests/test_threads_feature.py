import pytest
import sys
import json
import csv
import io
import logging
from unittest.mock import patch, MagicMock
from pyqwk.core import (
    ParsedMessage,
    MessageHeader,
    ProcessingSettings,
    show_threads,
    render_threads_as_text,
    _render_threads_html,
    _render_threads_markdown,
    _render_threads_csv,
)
from pyqwk.cli import main


@pytest.fixture
def test_messages(message_factory):
    # Thread 1: msgnum=1 (root), msgnum=2 (reply to 1), msgnum=3 (reply to 2)
    m1 = message_factory(1, 0, "Initial post", confnum=1, text="Original text\n")
    m1.header.msgfrom = "Alice"
    m1.header.msgto = "All"
    m1.header.msgdate = "01-01-24"
    m1.header.msgtime = "10:00"

    m2 = message_factory(2, 1, "Re: Initial post", confnum=1, text="First reply\n")
    m2.header.msgfrom = "Bob"
    m2.header.msgto = "Alice"
    m2.header.msgdate = "01-01-24"
    m2.header.msgtime = "10:05"

    m3 = message_factory(3, 2, "Re: Initial post", confnum=1, text="Second reply\n")
    m3.header.msgfrom = "Charlie"
    m3.header.msgto = "Bob"
    m3.header.msgdate = "01-01-24"
    m3.header.msgtime = "10:10"

    # Thread 4: msgnum=4 (root), msgnum=5 (reply to 4)
    m4 = message_factory(4, 0, "Second topic", confnum=1, text="Another topic\n")
    m4.header.msgfrom = "Bob"
    m4.header.msgto = "All"
    m4.header.msgdate = "01-02-24"
    m4.header.msgtime = "12:00"

    m5 = message_factory(5, 4, "Re: Second topic", confnum=1, text="Reply to second topic\n")
    m5.header.msgfrom = "Alice"
    m5.header.msgto = "Bob"
    m5.header.msgdate = "01-02-24"
    m5.header.msgtime = "13:00"

    return [m1, m2, m3, m4, m5]


def test_render_threads_formats():
    thread_metrics = [
        {
            "thread_id": "1",
            "root_subject": "Initial post",
            "starter": "Alice",
            "reply_count": 2,
            "deepest_depth": 2,
            "last_activity": "01-01-24 10:10",
        },
        {
            "thread_id": "4",
            "root_subject": "Second topic",
            "starter": "Bob",
            "reply_count": 1,
            "deepest_depth": 1,
            "last_activity": "01-02-24 13:00",
        }
    ]

    # Test Text
    text_out = render_threads_as_text(thread_metrics, use_colors=False)
    assert "Conversation Threads:" in text_out
    assert "Initial post" in text_out
    assert "Alice" in text_out
    assert "1" in text_out

    # Test HTML
    html_out = _render_threads_html(thread_metrics, "Test Title")
    assert "<title>Test Title</title>" in html_out
    assert "Initial post" in html_out
    assert "Alice" in html_out
    assert "<td>1</td>" in html_out

    # Test Markdown
    md_out = _render_threads_markdown(thread_metrics, "Test Title")
    assert "# Test Title" in md_out
    assert "| Thread ID | Root Subject |" in md_out
    assert "| 1 | Initial post |" in md_out

    # Test CSV
    csv_out = _render_threads_csv(thread_metrics)
    assert '"thread_id","root_subject"' in csv_out
    assert '"1","Initial post","Alice","2","2","01-01-24 10:10"' in csv_out


def test_show_threads_stdout(test_messages):
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
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )

    logger = logging.getLogger("test_threads")

    with patch("pyqwk.core.load_data", return_value=(test_messages, {})):
        with patch("pyqwk.core._write_text_output") as mock_write:
            show_threads(["dummy.qwk"], settings, logger)
            mock_write.assert_called_once()
            output_content = mock_write.call_args[0][0]
            metrics = json.loads(output_content)

            assert len(metrics) == 2
            # Thread 1 metrics
            t1 = metrics[0]
            assert t1["thread_id"] == "1"
            assert t1["root_subject"] == "Initial post"
            assert t1["starter"] == "Alice"
            assert t1["reply_count"] == 2
            assert t1["deepest_depth"] == 2
            assert t1["last_activity"] == "01-01-24 10:10"

            # Thread 4 metrics
            t2 = metrics[1]
            assert t2["thread_id"] == "4"
            assert t2["root_subject"] == "Second topic"
            assert t2["starter"] == "Bob"
            assert t2["reply_count"] == 1
            assert t2["deepest_depth"] == 1
            assert t2["last_activity"] == "01-02-24 13:00"


def test_show_threads_no_messages():
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
        format="json",
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        quiet=True,
    )
    logger = logging.getLogger("test_threads_empty")
    with patch("pyqwk.core.load_data", return_value=([], {})):
        with patch("logging.Logger.warning") as mock_warn:
            show_threads(["dummy.qwk"], settings, logger)
            mock_warn.assert_called_with("No messages loaded. Thread-listing aborted.")


def test_cli_threads_integration(tmp_path):
    test_file = tmp_path / "dummy.qwk"
    test_file.touch()

    # Create dummy messages
    m1 = MessageHeader(
        status=" ",
        msgnum=10,
        msgdate="02-02-24",
        msgtime="12:00",
        msgto="All",
        msgfrom="User1",
        msgsubject="CLI Thread topic",
        msgpassword="",
        refnum=0,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" ",
    )
    m2 = MessageHeader(
        status=" ",
        msgnum=11,
        msgdate="02-02-24",
        msgtime="12:30",
        msgto="User1",
        msgfrom="User2",
        msgsubject="Re: CLI Thread topic",
        msgpassword="",
        refnum=10,
        numblocks=1,
        msgflag=" ",
        confnum=1,
        lognum=0,
        nettag=" ",
    )

    from pyqwk.core import ParsedMessage
    msgs = [
        ParsedMessage(text="B1", msgnum=10, refnum=0, confnum=1, header=m1),
        ParsedMessage(text="B2", msgnum=11, refnum=10, confnum=1, header=m2),
    ]

    test_args = ["qwk.py", str(test_file), "--threads", "--format", "json"]

    with patch("sys.argv", test_args):
        with patch("pyqwk.cli.expand_paths", return_value=[str(test_file)]):
            with patch("pyqwk.core.load_data", return_value=(msgs, {})):
                with patch("sys.stdout", new=io.StringIO()) as fake_out:
                    with pytest.raises(SystemExit) as exc_info:
                        main()
                    assert exc_info.value.code == 0
                    output = json.loads(fake_out.getvalue())
                    assert len(output) == 1
                    t = output[0]
                    assert t["thread_id"] == "10"
                    assert t["root_subject"] == "CLI Thread topic"
                    assert t["starter"] == "User1"
                    assert t["reply_count"] == 1
                    assert t["deepest_depth"] == 1
                    assert t["last_activity"] == "02-02-24 12:30"
