import pytest
import io
from contextlib import redirect_stdout
from pyqwk.core import (
    ProcessingSettings,
    process_merged_files,
    ParsedMessage,
    MessageHeader,
)
import logging


def _make_msg(text, author="Alice", subject="Hello", confnum=1, msgnum=101):
    h = MessageHeader(
        status=" ",
        msgnum=msgnum,
        msgdate="01-23-24",
        msgtime="12:34",
        msgto="Bob",
        msgfrom=author,
        msgsubject=subject,
        msgpassword="",
        refnum=None,
        numblocks=None,
        msgflag=" ",
        confnum=confnum,
        lognum=0,
        nettag="",
    )
    return ParsedMessage(
        text=text, msgnum=msgnum, refnum=None, confnum=confnum, header=h
    )


def test_oneline_pattern(tmp_path, mocker):
    # Mock load_data to return our test messages
    msg = _make_msg(
        "This is a snippet.\nSecond line.", author="Alice", subject="Custom Pattern"
    )
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))

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
        oneline=True,
        oneline_pattern="[{confnum}] {author}: {subject} -> {snippet}",
    )

    logger = logging.getLogger("test")
    f = io.StringIO()
    with redirect_stdout(f):
        process_merged_files(["dummy.qwk"], settings, logger)

    output = f.getvalue()
    assert "[1] Alice: Custom Pattern -> This is a snippet." in output


def test_oneline_pattern_fallback(tmp_path, mocker):
    # Invalid pattern should fallback to default oneline
    msg = _make_msg("Body", author="Alice", subject="Fallback")
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))

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
        oneline=True,
        oneline_pattern="{invalid_variable}",
    )

    logger = logging.getLogger("test")
    f = io.StringIO()
    with redirect_stdout(f):
        process_merged_files(["dummy.qwk"], settings, logger)

    output = f.getvalue()
    # Should contain standard oneline elements
    assert "General" in output
    assert "Fallback" in output


def test_oneline_pattern_iso_dates(tmp_path, mocker):
    msg = _make_msg("Body", author="Alice")
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {1: "General"}))

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
        oneline=True,
        oneline_pattern="{year}-{month}-{day} {hour}:{minute}",
    )

    logger = logging.getLogger("test")
    f = io.StringIO()
    with redirect_stdout(f):
        process_merged_files(["dummy.qwk"], settings, logger)

    output = f.getvalue()
    assert "2024-01-23 12:34" in output
