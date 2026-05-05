from pyqwk.core import (
    _highlight_quotes,
    ProcessingSettings,
    ParsedMessage,
    MessageHeader,
    process_merged_files,
)
import logging
import io
from unittest.mock import MagicMock, patch


def test_highlight_quotes_no_colors():
    text = "> This is a quote\nThis is not."
    assert _highlight_quotes(text, use_colors=False) == text


def test_highlight_quotes_basic():
    text = "> This is a quote\nThis is not."
    highlighted = _highlight_quotes(text, use_colors=True)
    assert "\x1b[32m> This is a quote\x1b[0m\n" in highlighted
    assert "This is not." in highlighted
    assert "\x1b[32m" not in "This is not."


def test_highlight_quotes_different_markers():
    text = "│ This is a quote\n| This is also a quote\n} And this\nThis is not."
    highlighted = _highlight_quotes(text, use_colors=True)
    assert "\x1b[32m│ This is a quote\x1b[0m\n" in highlighted
    assert "\x1b[32m| This is also a quote\x1b[0m\n" in highlighted
    assert "\x1b[32m} And this\x1b[0m\n" in highlighted


def test_highlight_quotes_with_prefix():
    text = "JS> This is a quote\n  > Indented quote"
    highlighted = _highlight_quotes(text, use_colors=True)
    assert "\x1b[32mJS> This is a quote\x1b[0m\n" in highlighted
    assert "\x1b[32m  > Indented quote\x1b[0m" in highlighted


def test_process_merged_files_separator_colors():
    # Mock sys.stdout.isatty to True
    with (
        patch("sys.stdout.isatty", return_value=True),
        patch("shutil.get_terminal_size", return_value=MagicMock(columns=80)),
    ):
        # Mock load_data to return a simple message
        header = MessageHeader(
            status=" ",
            msgnum=1,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="Alice",
            msgfrom="Bob",
            msgsubject="Test",
            msgpassword="",
            refnum=None,
            numblocks=1,
            msgflag=" ",
            confnum=1,
            lognum=1,
            nettag="",
        )
        msg = ParsedMessage(
            text="Hello", msgnum=1, refnum=None, confnum=1, header=header
        )

        with patch("pyqwk.core.load_data", return_value=([msg], {1: "General"})):
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
                output_mode="stdout",
                output_path=None,
                encoding="cp437",
                quiet=True,
            )

            # Capture stdout
            stdout = io.StringIO()
            stdout.isatty = lambda: True
            with patch("sys.stdout", stdout):
                process_merged_files(["dummy.qwk"], settings, logging.getLogger())

            output = stdout.getvalue()
            # Check for dimmed separator
            assert (
                "\x1b[90m--------------------------------------------------------------------------------\r\n\x1b[0m"
                in output
            )


def test_process_merged_files_quote_highlighting():
    # Mock sys.stdout.isatty to True
    stdout = io.StringIO()
    stdout.isatty = lambda: True
    with patch("sys.stdout", stdout):
        # Mock load_data to return a message with a quote
        header = MessageHeader(
            status=" ",
            msgnum=1,
            msgdate="01-01-23",
            msgtime="12:00",
            msgto="Alice",
            msgfrom="Bob",
            msgsubject="Test",
            msgpassword="",
            refnum=None,
            numblocks=1,
            msgflag=" ",
            confnum=1,
            lognum=1,
            nettag="",
        )
        # Fixed call to ParsedMessage
        msg = ParsedMessage(
            text="> This is a quote\nHello",
            msgnum=1,
            refnum=None,
            confnum=1,
            header=header,
        )

        with patch("pyqwk.core.load_data", return_value=([msg], {1: "General"})):
            settings = ProcessingSettings(
                verbose=False,
                private=True,
                no_header=True,
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

            process_merged_files(["dummy.qwk"], settings, logging.getLogger())

            output = stdout.getvalue()
            # Check for green highlighted quote
            assert "\x1b[32m> This is a quote\x1b[0m\r\n" in output
