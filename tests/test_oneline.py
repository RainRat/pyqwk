from pyqwk.core import MessageHeader, ProcessingSettings, _write_text, ParsedMessage
from io import StringIO
import sys

def test_format_oneline():
    header = MessageHeader(
        status=" ",
        msgnum=123,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Hello World",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    board_dict = {1: "General"}

    # Test normal
    oneline = header.format_oneline(board_dict)
    assert "General" in oneline
    assert "01-01-24" in oneline
    assert "Bob" in oneline
    assert "Hello World" in oneline
    assert "123" not in oneline # MsgNum not in oneline by default

    # Test verbose
    oneline_v = header.format_oneline(board_dict, verbose=True)
    assert "123" in oneline_v

def test_write_text_oneline():
    header = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Test Subject",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    msg = ParsedMessage(
        text="Oneline summary\r\n",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header
    )

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
        oneline=True
    )

    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        _write_text([msg], None, settings=settings)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    assert "Conference" in output
    assert "Date" in output
    assert "From" in output
    assert "Subject" in output
    assert "----------------" in output
    assert "Test Subject" in output

def test_cli_oneline(tmp_path):
    # This is a bit harder to test without running the actual CLI,
    # but we can check if the settings are correctly populated.
    from pyqwk.cli import main
    from unittest.mock import patch

    test_qwk = "testdata/test1_qwk.zip"

    with patch("sys.argv", ["qwk.py", test_qwk, "--oneline", "--dry-run"]):
        with patch("pyqwk.cli.process_merged_files") as mock_process:
            try:
                main()
            except SystemExit:
                pass

            args, kwargs = mock_process.call_args
            settings = args[1]
            assert settings.oneline is True


def test_write_text_threaded_oneline():
    header1 = MessageHeader(
        status=" ",
        msgnum=1,
        msgdate="01-01-24",
        msgtime="12:00",
        msgto="All",
        msgfrom="Alice",
        msgsubject="Parent",
        msgpassword="",
        refnum=None,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )
    header2 = MessageHeader(
        status=" ",
        msgnum=2,
        msgdate="01-01-24",
        msgtime="12:05",
        msgto="Alice",
        msgfrom="Bob",
        msgsubject="Parent",
        msgpassword="",
        refnum=1,
        numblocks=1,
        msgflag="",
        confnum=1,
        lognum=0,
        nettag="",
    )

    msg1 = ParsedMessage(
        text="Parent text",
        msgnum=1,
        refnum=None,
        confnum=1,
        header=header1,
        confname="General",
        depth=0
    )
    msg2 = ParsedMessage(
        text="Child text",
        msgnum=2,
        refnum=1,
        confnum=1,
        header=header2,
        confname="General",
        depth=1
    )

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
        separator="none",
        output_mode="stdout",
        output_path=None,
        encoding="cp437",
        oneline=True
    )

    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        _write_text([msg1, msg2], None, settings=settings)
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = old_stdout

    assert "General" in output
    assert "Parent" in output
    assert "└ Parent" in output
