import io
from contextlib import redirect_stdout
from pyqwk.core import (
    ProcessingSettings,
    process_merged_files,
    ParsedMessage,
    MessageHeader,
    _get_message_mapping,
    _write_text,
)
import logging


def _make_msg(
    text,
    author="Alice",
    subject="Hello",
    confnum=1,
    msgnum=101,
    status=" ",
    attachments=None,
    depth=0,
):
    h = MessageHeader(
        status=status,
        msgnum=msgnum,
        msgdate="01-23-24",
        msgtime="12:34:56",
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
        text=text,
        msgnum=msgnum,
        refnum=None,
        confnum=confnum,
        header=h,
        attachments=attachments,
        depth=depth,
    )


def test_get_message_mapping_flags_and_indent():
    # Covers lines 2469, 2471, 2493
    msg = _make_msg("Body", status="*", attachments=["file.txt"], depth=1)
    mapping = _get_message_mapping(msg, 1)

    assert mapping["flags"] == "*@"
    assert mapping["indent"] == "└ "

    # Check deeper depth for coverage of indent logic
    msg_deep = _make_msg("Body", depth=2)
    mapping_deep = _get_message_mapping(msg_deep, 1)
    assert mapping_deep["indent"] == "  └ "


def test_process_merged_files_confname_fallback(mocker):
    # Covers line 2728
    # msg.confname is None by default in _make_msg
    msg = _make_msg("Body", confnum=42)
    # Return empty board_dict to ensure mapping['confname'] remains empty initially
    mocker.patch("pyqwk.core.load_data", return_value=([msg], {}))

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
        oneline_pattern="{confname}: {subject}",
    )

    logger = logging.getLogger("test")
    f = io.StringIO()
    with redirect_stdout(f):
        process_merged_files(["dummy.qwk"], settings, logger)

    output = f.getvalue()
    assert "Conference 42: Hello" in output


def test_write_text_confname_fallback():
    # Covers line 4051
    msg = _make_msg("Body", confnum=99)
    # Ensure confname is None
    msg.confname = None

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
        oneline_pattern="[{confname}] {author}",
    )

    f = io.StringIO()
    with redirect_stdout(f):
        _write_text([msg], None, settings=settings)

    output = f.getvalue()
    assert "[Conference 99] Alice" in output
